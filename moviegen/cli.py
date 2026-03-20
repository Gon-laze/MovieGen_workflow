from __future__ import annotations

import hashlib
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer
import yaml

from .config import load_project_spec
from .models import ORDERED_STAGES, ProjectSpec, Stage, resolve_stage_sequence
from .storage import (
    complete_run,
    connect,
    delete_artifact_rows,
    fetch_artifacts,
    fetch_human_gates,
    fetch_run,
    fetch_stage_runs,
    init_db,
    insert_artifact,
    insert_run,
    insert_stage_run,
    list_runs,
    row_to_dict,
    upsert_human_gate,
)
from .workflow import RunContext, execute_stage

app = typer.Typer(no_args_is_help=True, add_completion=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


def ensure_runtime_dirs(root: Path) -> None:
    dirs = [
        root / "config",
        root / "workspace" / "raw_videos",
        root / "workspace" / "raw_images",
        root / "workspace" / "shots",
        root / "workspace" / "keyframes",
        root / "workspace" / "style_refs",
        root / "workspace" / "motion_refs",
        root / "workspace" / "bibles",
        root / "workspace" / "prompts",
        root / "workspace" / "jobs",
        root / "workspace" / "candidates",
        root / "workspace" / "downloads",
        root / "workspace" / "review",
        root / "workspace" / "post",
        root / "workspace" / "assemble",
        root / "workspace" / "release",
        root / "workspace" / "reports",
        root / "workspace" / "logs" / "runs",
        root / "workspace" / "logs" / "stages",
        root / "workspace" / "logs" / "jobs",
        root / "state",
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_summary(spec: ProjectSpec, run_id: str, stages: list[Stage], dry_run: bool) -> dict[str, object]:
    return {
        "run_id": run_id,
        "project_id": spec.project.id,
        "project_title": spec.project.title,
        "stage_request": [stage.value for stage in stages],
        "dry_run": dry_run,
        "preferred_a_pool": spec.providers.preferred_a_pool,
        "preferred_b_pool": spec.providers.preferred_b_pool,
        "preferred_c_pool": spec.providers.preferred_c_pool,
        "benchmark_suite_id": spec.benchmark.suite_id,
        "benchmark_must_test": spec.benchmark.must_test,
        "routing_keys": sorted(spec.routing.route_matrix.keys()),
        "execution_primary_provider": spec.execution.primary_provider,
        "execution_optional_provider": spec.execution.optional_provider,
        "execution_live_mode": spec.execution.live_mode,
        "execution_submission_strategy": spec.execution.submission_strategy,
        "execution_poll_after_submit": spec.execution.poll_after_submit,
        "execution_poll_max_attempts": spec.execution.poll_max_attempts,
        "execution_poll_interval_sec": spec.execution.poll_interval_sec,
    }


def resolve_requested_stages(stage: Stage, force_stage: Optional[str]) -> list[Stage]:
    stages = resolve_stage_sequence(stage)
    if force_stage and stage == Stage.ALL:
        target = next((item for item in ORDERED_STAGES if item.value == force_stage), None)
        if target is None:
            raise typer.Exit(code=11)
        start_index = ORDERED_STAGES.index(target)
        return ORDERED_STAGES[start_index:].copy()
    return stages


def load_shot_specs_file(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("shot_specs", []) or []
    if isinstance(payload, list):
        return payload
    return []


def load_structured_file(path: Path) -> object:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    if value in {None, ""}:
        return []
    return [str(value)]


def build_provider_score_indexes(shot_specs: list[dict[str, object]], review_payload: dict[str, object]) -> dict[str, dict[str, float]]:
    shot_meta = {str(shot.get("shot_id")): shot for shot in shot_specs}
    shot_scores: dict[str, dict[str, float]] = {}
    sequence_scores: dict[str, dict[str, float]] = {}
    character_scores: dict[str, dict[str, float]] = {}
    for section in ("review_candidates", "regenerate_candidates", "approved_candidates"):
        for item in review_payload.get(section, []) or []:
            shot_id = str(item.get("shot_id"))
            provider = str(item.get("provider"))
            score = float(item.get("weighted_total_score") or 0.0)
            shot_scores.setdefault(shot_id, {})
            shot_scores[shot_id][provider] = shot_scores[shot_id].get(provider, 0.0) + score

            shot = shot_meta.get(shot_id, {})
            sequence_id = str(shot.get("sequence_id") or "")
            if sequence_id:
                sequence_scores.setdefault(sequence_id, {})
                sequence_scores[sequence_id][provider] = sequence_scores[sequence_id].get(provider, 0.0) + score

            continuity = shot.get("continuity", {}) or {}
            for character_id in normalize_str_list(continuity.get("character_ids")):
                character_scores.setdefault(character_id, {})
                character_scores[character_id][provider] = character_scores[character_id].get(provider, 0.0) + score
    return {
        "shot": shot_scores,
        "sequence": sequence_scores,
        "character": character_scores,
    }


def choose_provider_by_score(scores: dict[str, float], fallback_provider: str) -> str:
    if not scores:
        return fallback_provider
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def write_run_artifacts(root: Path, run_id: str, summary: dict[str, object]) -> tuple[Path, Path]:
    reports_dir = root / "workspace" / "reports"
    summary_path = reports_dir / f"{run_id}__run_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    status_path = reports_dir / f"{run_id}__status.txt"
    status_path.write_text("completed scaffold dry-run\n" if summary["dry_run"] else "completed scaffold run\n", encoding="utf-8")
    return summary_path, status_path


def execute_run(
    *,
    root: Path,
    project_file: Path,
    stage: Stage,
    run_id: Optional[str],
    force_stage: Optional[str],
    dry_run: bool,
) -> dict[str, object]:
    ensure_runtime_dirs(root)
    spec = load_project_spec(project_file)
    stages = resolve_requested_stages(stage, force_stage)
    current_run_id = run_id or make_run_id()
    db_path = root / "state" / "moviegen.db"
    conn = connect(db_path)
    init_db(conn)
    started_at = now_iso()
    run_note = "minimal Kling-first submit/poll/download flow is available; final media-aware judging and provider-specific post are still pending"
    insert_run(
        conn,
        run_id=current_run_id,
        project_id=spec.project.id,
        project_file=str(project_file),
        requested_stage=stage.value,
        dry_run=dry_run,
        status="running",
        notes=run_note,
        started_at=started_at,
    )

    run_log = root / "workspace" / "logs" / "runs" / f"{current_run_id}.jsonl"
    append_jsonl(
        run_log,
        {
            "timestamp": started_at,
            "run_id": current_run_id,
            "stage_name": None,
            "shot_id": None,
            "job_id": None,
            "provider": None,
            "level": "INFO",
            "event_type": "run_started",
            "message": "Run started",
            "error_code": None,
            "metadata": {"dry_run": dry_run, "force_stage": force_stage, "stages": [s.value for s in stages]},
        },
    )

    ctx = RunContext(root=root, run_id=current_run_id, conn=conn)
    current_stage: Stage | None = None
    try:
        for current_stage in stages:
            stage_started = now_iso()
            result = execute_stage(ctx, spec, current_stage, project_file)
            note = f"{result.note} (dry-run)" if dry_run else result.note
            finished_stage = now_iso()
            insert_stage_run(
                conn,
                run_id=current_run_id,
                stage_name=current_stage.value,
                status="succeeded",
                notes=note,
                started_at=stage_started,
                finished_at=finished_stage,
            )
            append_jsonl(
                root / "workspace" / "logs" / "stages" / f"{current_run_id}__{current_stage.value}.jsonl",
                {
                    "timestamp": stage_started,
                    "run_id": current_run_id,
                    "stage_name": current_stage.value,
                    "shot_id": None,
                    "job_id": None,
                    "provider": None,
                    "level": "INFO",
                    "event_type": "stage_completed",
                    "message": note,
                    "error_code": None,
                    "metadata": result.metadata,
                },
            )

        summary = build_summary(spec, current_run_id, stages, dry_run)
        summary_path, status_path = write_run_artifacts(root, current_run_id, summary)
        finished_at = now_iso()
        complete_run(conn, current_run_id, "completed", run_note, finished_at)

        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=current_run_id,
            artifact_type="report",
            artifact_path=str(summary_path),
            source_stage="report",
            source_id=current_run_id,
            content_hash=sha256_file(summary_path),
            file_size_bytes=summary_path.stat().st_size,
            retention_policy="keep",
            created_at=finished_at,
        )
        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=current_run_id,
            artifact_type="report",
            artifact_path=str(status_path),
            source_stage="report",
            source_id=current_run_id,
            content_hash=sha256_file(status_path),
            file_size_bytes=status_path.stat().st_size,
            retention_policy="keep",
            created_at=finished_at,
        )

        append_jsonl(
            run_log,
            {
                "timestamp": finished_at,
                "run_id": current_run_id,
                "stage_name": None,
                "shot_id": None,
                "job_id": None,
                "provider": None,
                "level": "INFO",
                "event_type": "run_completed",
                "message": "Run completed",
                "error_code": None,
                "metadata": {"summary_path": str(summary_path)},
            },
        )
        return {"run_id": current_run_id, "status": "completed", "summary_path": str(summary_path)}
    except Exception as exc:
        failed_at = now_iso()
        stage_name = current_stage.value if current_stage else "unknown"
        error_text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        insert_stage_run(
            conn,
            run_id=current_run_id,
            stage_name=stage_name,
            status="failed",
            notes=error_text,
            started_at=failed_at,
            finished_at=failed_at,
        )
        complete_run(conn, current_run_id, "failed", error_text, failed_at)
        append_jsonl(
            run_log,
            {
                "timestamp": failed_at,
                "run_id": current_run_id,
                "stage_name": stage_name,
                "shot_id": None,
                "job_id": None,
                "provider": None,
                "level": "ERROR",
                "event_type": "run_failed",
                "message": error_text,
                "error_code": "MG_SYSTEM_001",
                "metadata": {},
            },
        )
        raise


@app.command()
def run(
    project_file: Path = typer.Argument(..., exists=True, readable=True),
    stage: Stage = typer.Option(Stage.ALL, "--stage"),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
    force_stage: Optional[str] = typer.Option(None, "--force-stage"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    root = Path.cwd()
    payload = execute_run(root=root, project_file=project_file, stage=stage, run_id=run_id, force_stage=force_stage, dry_run=dry_run)
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command()
def benchmark(
    project_file: Path = typer.Argument(..., exists=True, readable=True),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    root = Path.cwd()
    payload = execute_run(root=root, project_file=project_file, stage=Stage.BENCHMARK, run_id=run_id, force_stage=None, dry_run=dry_run)
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command()
def doctor() -> None:
    import os

    payload = {
        "execution_default_primary": "kling_3_0",
        "execution_default_optional": "vidu_q3",
        "local_tools": {
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")),
        },
        "env": {
            "MOVIEGEN_KLING_SUBMIT_URL": bool(os.getenv("MOVIEGEN_KLING_SUBMIT_URL")),
            "MOVIEGEN_KLING_POLL_URL_TEMPLATE": bool(os.getenv("MOVIEGEN_KLING_POLL_URL_TEMPLATE")),
            "MOVIEGEN_KLING_TOKEN": bool(os.getenv("MOVIEGEN_KLING_TOKEN")),
            "MOVIEGEN_VIDU_SUBMIT_URL": bool(os.getenv("MOVIEGEN_VIDU_SUBMIT_URL")),
            "MOVIEGEN_VIDU_POLL_URL_TEMPLATE": bool(os.getenv("MOVIEGEN_VIDU_POLL_URL_TEMPLATE")),
            "MOVIEGEN_VIDU_TOKEN": bool(os.getenv("MOVIEGEN_VIDU_TOKEN")),
        },
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def resume(
    run_id: str = typer.Option(..., "--run-id"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    root = Path.cwd()
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    row = fetch_run(conn, run_id)
    if row is None:
        raise typer.Exit(code=30)
    review_summary_path = root / "workspace" / "review" / f"{run_id}__review_summary.json"
    if not review_summary_path.exists():
        typer.echo(json.dumps({"run_id": run_id, "status": row["status"], "message": "review summary is missing; nothing to resume"}, ensure_ascii=False))
        return

    review_payload = json.loads(review_summary_path.read_text(encoding="utf-8"))
    gates = {gate_row["gate_name"]: row_to_dict(gate_row) for gate_row in fetch_human_gates(conn, run_id)}
    review_gate = gates.get("gate_3_review")

    if review_payload.get("review_candidates") and (review_gate is None or review_gate.get("status") == "waiting"):
        typer.echo(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": row["status"],
                    "message": "review gate is still waiting; approve or reject candidates before resume",
                    "gate": review_gate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    candidate_map: dict[str, dict[str, object]] = {}
    for section in ("review_candidates", "regenerate_candidates", "approved_candidates"):
        for item in review_payload.get(section, []):
            candidate_map[item["candidate_clip_id"]] = item

    gate_payload = {}
    if review_gate and review_gate.get("decision_payload"):
        gate_payload = json.loads(str(review_gate["decision_payload"]))

    rerun_candidate_ids = {item["candidate_clip_id"] for item in review_payload.get("regenerate_candidates", [])}
    rerun_candidate_ids.update(gate_payload.get("rejected_ids", []))
    approved_candidate_ids = set(gate_payload.get("approved_ids", []))
    if not approved_candidate_ids:
        approved_candidate_ids = {item["candidate_clip_id"] for item in review_payload.get("approved_candidates", [])}
    rerun_shot_ids = sorted(
        {
            str(candidate_map[candidate_id]["shot_id"])
            for candidate_id in rerun_candidate_ids
            if candidate_id in candidate_map
        }
    )
    approved_candidates = [candidate_map[candidate_id] for candidate_id in approved_candidate_ids if candidate_id in candidate_map]

    resume_plan = {
        "source_run_id": run_id,
        "source_project_file": row["project_file"],
        "review_gate": review_gate,
        "rerun_candidate_ids": sorted(rerun_candidate_ids),
        "rerun_shot_ids": rerun_shot_ids,
        "approved_candidate_ids": sorted(approved_candidate_ids),
        "created_at": now_iso(),
    }
    resume_plan_path = root / "workspace" / "review" / f"{run_id}__resume_plan.json"
    resume_plan_path.write_text(json.dumps(resume_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    insert_artifact(
        conn,
        artifact_id=f"artifact_{uuid4().hex[:12]}",
        run_id=run_id,
        artifact_type="resume_plan",
        artifact_path=str(resume_plan_path),
        source_stage="review",
        source_id=run_id,
        content_hash=sha256_file(resume_plan_path),
        file_size_bytes=resume_plan_path.stat().st_size,
        retention_policy="keep",
        created_at=now_iso(),
    )

    source_project_file = Path(str(row["project_file"]))
    if not source_project_file.is_absolute():
        source_project_file = root / source_project_file
    source_spec = load_project_spec(source_project_file)
    project_payload = yaml.safe_load(source_project_file.read_text(encoding="utf-8")) or {}
    planning = project_payload.setdefault("planning", {})
    followup_payloads: dict[str, object] = {}

    if rerun_shot_ids:
        shot_specs_file = planning.get("shot_specs_file")
        if not shot_specs_file:
            raise typer.Exit(code=31)
        shot_specs_path = Path(str(shot_specs_file))
        if not shot_specs_path.is_absolute():
            shot_specs_path = root / shot_specs_path
        shot_specs = load_shot_specs_file(shot_specs_path)
        filtered_shots = [shot for shot in shot_specs if str(shot.get("shot_id")) in rerun_shot_ids]
        if not filtered_shots:
            typer.echo(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": row["status"],
                        "message": "rerun shot ids were resolved, but no matching shot specs were found",
                        "rerun_shot_ids": rerun_shot_ids,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        continuity_report_path = root / "workspace" / "review" / f"{run_id}__continuity_report.json"
        continuity_payload = {}
        if continuity_report_path.exists():
            continuity_payload = json.loads(continuity_report_path.read_text(encoding="utf-8"))
        continuity_issue_index: dict[str, list[dict[str, object]]] = {}
        for issue in continuity_payload.get("issues", []) or []:
            scope_id = str(issue.get("scope_id") or "")
            if scope_id:
                continuity_issue_index.setdefault(scope_id, []).append(issue)
        provider_score_indexes = build_provider_score_indexes(shot_specs, review_payload)
        primary_provider = source_spec.execution.primary_provider
        known_providers = set(
            source_spec.providers.preferred_a_pool
            + source_spec.providers.preferred_b_pool
            + source_spec.providers.preferred_c_pool
        )
        for shot in filtered_shots:
            shot_id = str(shot.get("shot_id"))
            sequence_id = str(shot.get("sequence_id") or "")
            continuity = shot.get("continuity", {}) or {}
            character_ids = normalize_str_list(continuity.get("character_ids"))
            issue_types = {str(issue.get("issue_type")) for issue in continuity_issue_index.get(shot_id, [])}
            issue_types.update(str(issue.get("issue_type")) for issue in continuity_issue_index.get(sequence_id, []))
            for character_id in character_ids:
                issue_types.update(str(issue.get("issue_type")) for issue in continuity_issue_index.get(character_id, []))
            continuity_mixture_types = {
                "shot_provider_mixture",
                "sequence_provider_mixture",
                "character_provider_mixture",
            }
            if not issue_types.intersection(continuity_mixture_types):
                continue

            candidate_scores: dict[str, float] = {}
            candidate_scores.update(provider_score_indexes["shot"].get(shot_id, {}))
            for provider, score in provider_score_indexes["sequence"].get(sequence_id, {}).items():
                candidate_scores[provider] = candidate_scores.get(provider, 0.0) + score
            for character_id in character_ids:
                for provider, score in provider_score_indexes["character"].get(character_id, {}).items():
                    candidate_scores[provider] = candidate_scores.get(provider, 0.0) + score
            preferred_provider = choose_provider_by_score(candidate_scores, primary_provider)
            constraints = dict(shot.get("provider_constraints", {}) or {})
            constraints["allowed_providers"] = [preferred_provider]
            constraints["banned_providers"] = sorted(
                provider
                for provider in known_providers
                if provider != preferred_provider
            )
            constraints["preferred_first_tier"] = True
            constraints["continuity_reroute_reason"] = sorted(issue_types)
            constraints["continuity_preferred_provider"] = preferred_provider
            shot["provider_constraints"] = constraints

        continuity_reroutes = [
            {
                "shot_id": str(shot.get("shot_id")),
                "allowed_providers": (shot.get("provider_constraints", {}) or {}).get("allowed_providers", []),
                "continuity_preferred_provider": (shot.get("provider_constraints", {}) or {}).get("continuity_preferred_provider"),
                "continuity_reroute_reason": (shot.get("provider_constraints", {}) or {}).get("continuity_reroute_reason", []),
            }
            for shot in filtered_shots
            if (shot.get("provider_constraints", {}) or {}).get("continuity_preferred_provider")
        ]
        resume_plan["continuity_reroutes"] = continuity_reroutes

        rerun_followup_run_id = make_run_id()
        resume_shots_path = root / "workspace" / "review" / f"{rerun_followup_run_id}__resume_shot_specs.yaml"
        resume_project_path = root / "workspace" / "review" / f"{rerun_followup_run_id}__resume_project.yaml"
        resume_shots_path.write_text(
            yaml.safe_dump({"shot_specs": filtered_shots}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        rerun_project_payload = yaml.safe_load(source_project_file.read_text(encoding="utf-8")) or {}
        rerun_planning = rerun_project_payload.setdefault("planning", {})
        rerun_planning["shot_specs_file"] = str(resume_shots_path.relative_to(root)).replace("\\", "/")
        rerun_project_path_text = yaml.safe_dump(rerun_project_payload, allow_unicode=True, sort_keys=False)
        resume_project_path.write_text(rerun_project_path_text, encoding="utf-8")
        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=run_id,
            artifact_type="resume_shot_specs",
            artifact_path=str(resume_shots_path),
            source_stage="review",
            source_id=rerun_followup_run_id,
            content_hash=sha256_file(resume_shots_path),
            file_size_bytes=resume_shots_path.stat().st_size,
            retention_policy="keep",
            created_at=now_iso(),
        )
        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=run_id,
            artifact_type="resume_project_file",
            artifact_path=str(resume_project_path),
            source_stage="review",
            source_id=rerun_followup_run_id,
            content_hash=sha256_file(resume_project_path),
            file_size_bytes=resume_project_path.stat().st_size,
            retention_policy="keep",
            created_at=now_iso(),
        )
        followup_payloads["rerun_followup_run"] = execute_run(
            root=root,
            project_file=resume_project_path,
            stage=Stage.ALL,
            run_id=rerun_followup_run_id,
            force_stage=Stage.PLAN.value,
            dry_run=dry_run,
        )

    if approved_candidates:
        post_followup_run_id = make_run_id()
        approved_candidates_path = root / "workspace" / "review" / f"{post_followup_run_id}__approved_candidates.yaml"
        approved_project_path = root / "workspace" / "review" / f"{post_followup_run_id}__post_project.yaml"
        approved_candidates_path.write_text(
            yaml.safe_dump(
                {
                    "source_run_id": run_id,
                    "source_review_gate": review_gate,
                    "approved_candidates": approved_candidates,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        post_project_payload = yaml.safe_load(source_project_file.read_text(encoding="utf-8")) or {}
        post_planning = post_project_payload.setdefault("planning", {})
        post_planning["approved_candidates_file"] = str(approved_candidates_path.relative_to(root)).replace("\\", "/")
        approved_project_path.write_text(
            yaml.safe_dump(post_project_payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=run_id,
            artifact_type="approved_candidates_file",
            artifact_path=str(approved_candidates_path),
            source_stage="review",
            source_id=post_followup_run_id,
            content_hash=sha256_file(approved_candidates_path),
            file_size_bytes=approved_candidates_path.stat().st_size,
            retention_policy="keep",
            created_at=now_iso(),
        )
        insert_artifact(
            conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=run_id,
            artifact_type="post_project_file",
            artifact_path=str(approved_project_path),
            source_stage="review",
            source_id=post_followup_run_id,
            content_hash=sha256_file(approved_project_path),
            file_size_bytes=approved_project_path.stat().st_size,
            retention_policy="keep",
            created_at=now_iso(),
        )
        followup_payloads["post_followup_run"] = execute_run(
            root=root,
            project_file=approved_project_path,
            stage=Stage.ALL,
            run_id=post_followup_run_id,
            force_stage=Stage.POST.value,
            dry_run=dry_run,
        )

    if not followup_payloads:
        typer.echo(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": row["status"],
                    "message": "no rerun or approved candidates were selected; resume completed without launching a follow-up run",
                    "resume_plan_path": str(resume_plan_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    typer.echo(
        json.dumps(
            {
                "source_run_id": run_id,
                "resume_plan_path": str(resume_plan_path),
                **followup_payloads,
                "rerun_shot_ids": rerun_shot_ids,
                "approved_candidate_ids": sorted(approved_candidate_ids),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command()
def status(run_id: Optional[str] = typer.Option(None, "--run-id")) -> None:
    root = Path.cwd()
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    if run_id:
        row = fetch_run(conn, run_id)
        if row is None:
            raise typer.Exit(code=30)
        payload = row_to_dict(row)
        payload["stages"] = [row_to_dict(stage_row) for stage_row in fetch_stage_runs(conn, run_id)]
        payload["gates"] = [row_to_dict(gate_row) for gate_row in fetch_human_gates(conn, run_id)]
        payload["artifacts"] = [row_to_dict(artifact_row) for artifact_row in fetch_artifacts(conn, run_id)]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    payload = [row_to_dict(row) for row in list_runs(conn)]
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def report(run_id: str = typer.Option(..., "--run-id")) -> None:
    root = Path.cwd()
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    row = fetch_run(conn, run_id)
    if row is None:
        raise typer.Exit(code=30)
    payload = row_to_dict(row)
    payload["stages"] = [row_to_dict(stage_row) for stage_row in fetch_stage_runs(conn, run_id)]
    payload["gates"] = [row_to_dict(gate_row) for gate_row in fetch_human_gates(conn, run_id)]
    payload["artifacts"] = [row_to_dict(artifact_row) for artifact_row in fetch_artifacts(conn, run_id)]
    reports_dir = root / "workspace" / "reports"
    payload["report_files"] = sorted(
        str(path)
        for path in reports_dir.glob(f"{run_id}__*")
        if path.is_file()
    )
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def gate(
    run_id: str = typer.Option(..., "--run-id"),
    gate_name: str = typer.Option(..., "--gate"),
    status: str = typer.Option(..., "--status"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    decision_summary: Optional[str] = typer.Option(None, "--decision-summary"),
    approve: Optional[str] = typer.Option(None, "--approve"),
    reject: Optional[str] = typer.Option(None, "--reject"),
) -> None:
    root = Path.cwd()
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    if fetch_run(conn, run_id) is None:
        raise typer.Exit(code=30)
    existing_gate = next(
        (row_to_dict(gate_row) for gate_row in fetch_human_gates(conn, run_id) if gate_row["gate_name"] == gate_name),
        None,
    )
    approved_ids = [item for item in (approve or "").split(",") if item]
    rejected_ids = [item for item in (reject or "").split(",") if item]
    payload = {
        "approved_ids": approved_ids,
        "rejected_ids": rejected_ids,
    }
    timestamp = now_iso()
    gate_id = f"{run_id}__{gate_name}"
    upsert_human_gate(
        conn,
        gate_id=gate_id,
        run_id=run_id,
        gate_name=gate_name,
        status=status,
        reviewer=reviewer or (existing_gate or {}).get("reviewer"),
        decision_summary=decision_summary if decision_summary is not None else (existing_gate or {}).get("decision_summary"),
        decision_payload=json.dumps(payload, ensure_ascii=False),
        created_at=timestamp,
        updated_at=timestamp,
    )
    typer.echo(
        json.dumps(
            {
                "run_id": run_id,
                "gate_id": gate_id,
                "status": status,
                "approved_ids": approved_ids,
                "rejected_ids": rejected_ids,
            },
            ensure_ascii=False,
        )
    )


@app.command()
def clean(scope: str = typer.Option(..., "--scope"), run_id: Optional[str] = typer.Option(None, "--run-id")) -> None:
    root = Path.cwd()
    allowed = {"cache", "tmp", "all_safe"}
    if scope not in allowed:
        raise typer.Exit(code=10)
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    deleted: list[str] = []
    deleted_artifact_ids: list[str] = []
    if scope in {"cache", "all_safe"}:
        for artifact_row in fetch_artifacts(conn, run_id):
            artifact = row_to_dict(artifact_row)
            retention = artifact["retention_policy"]
            if retention not in {"cache", "delete_after_run"}:
                continue
            artifact_path = Path(str(artifact["artifact_path"]))
            if artifact_path.exists() and artifact_path.is_file():
                artifact_path.unlink()
                deleted.append(str(artifact_path))
            deleted_artifact_ids.append(str(artifact["artifact_id"]))
        delete_artifact_rows(conn, deleted_artifact_ids)
    if scope in {"tmp", "all_safe"}:
        tmp_dir = root / "tmp"
        if tmp_dir.exists():
            for child in tmp_dir.rglob("*"):
                if child.is_file():
                    child.unlink()
                    deleted.append(str(child))
    typer.echo(json.dumps({"scope": scope, "run_id": run_id, "deleted_count": len(deleted), "deleted_artifact_rows": len(deleted_artifact_ids)}, ensure_ascii=False))


if __name__ == "__main__":
    app()

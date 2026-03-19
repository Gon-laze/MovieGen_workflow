from __future__ import annotations

import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer

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
    stages = resolve_stage_sequence(stage)
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
def resume(run_id: str = typer.Option(..., "--run-id")) -> None:
    root = Path.cwd()
    conn = connect(root / "state" / "moviegen.db")
    init_db(conn)
    row = fetch_run(conn, run_id)
    if row is None:
        raise typer.Exit(code=30)
    typer.echo(json.dumps({"run_id": run_id, "status": row["status"], "message": "resume scaffold currently performs no additional work"}, ensure_ascii=False))


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
        reviewer=reviewer,
        decision_summary=decision_summary,
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

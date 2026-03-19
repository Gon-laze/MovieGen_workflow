from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .models import ORDERED_STAGES, ProjectSpec, Stage
from .storage import insert_artifact, upsert_generation_job


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_reference_role(path: Path, asset_type: str) -> str:
    lowered = str(path).lower()
    for token, role in [
        ("style", "style"),
        ("character", "character"),
        ("scene", "scene"),
        ("motion", "motion"),
        ("prop", "prop"),
        ("dialogue", "dialogue"),
        ("camera", "camera"),
    ]:
        if token in lowered:
            return role
    if asset_type == "video":
        return "motion"
    if asset_type == "image":
        return "style"
    return "style"


def classify_asset(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if suffix in {".pdf", ".md", ".txt", ".csv"}:
        return "text"
    return None


def extract_text_metadata(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        raw = ""
    lines = [line for line in raw.splitlines() if line.strip()]
    preview = "\n".join(lines[:10])[:1200]
    return {
        "char_count": len(raw),
        "line_count": len(lines),
        "preview": preview,
    }


def tokenize_terms(text: str) -> list[str]:
    english = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    stopwords = {
        "with",
        "from",
        "this",
        "that",
        "have",
        "will",
        "into",
        "your",
        "they",
        "them",
        "using",
        "video",
        "model",
        "models",
        "stage",
        "shot",
        "prompt",
        "provider",
        "生成",
        "视频",
        "模型",
        "工作流",
        "系统",
        "阶段",
        "镜头",
    }
    tokens = [token.lower() for token in english] + chinese
    return [token for token in tokens if token not in stopwords]


@dataclass
class StageResult:
    note: str
    artifacts: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    root: Path
    run_id: str
    conn: Any

    def record_artifact(
        self,
        *,
        path: Path,
        artifact_type: str,
        source_stage: str,
        source_id: str | None = None,
        retention_policy: str = "keep",
    ) -> None:
        insert_artifact(
            self.conn,
            artifact_id=f"artifact_{uuid4().hex[:12]}",
            run_id=self.run_id,
            artifact_type=artifact_type,
            artifact_path=str(path),
            source_stage=source_stage,
            source_id=source_id,
            content_hash=sha256_file(path),
            file_size_bytes=path.stat().st_size,
            retention_policy=retention_policy,
            created_at=now_iso(),
        )


def stage_ingest(ctx: RunContext, spec: ProjectSpec, project_file: Path) -> StageResult:
    imported_assets: list[dict[str, Any]] = []
    failed_assets: list[dict[str, Any]] = []
    dedup: dict[str, list[str]] = {}

    def handle_path(path: Path) -> None:
        if not path.exists():
            failed_assets.append({"path": str(path), "reason": "missing_input"})
            return
        if path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file()):
                handle_path(child)
            return
        if path.name.startswith("."):
            return
        asset_type = classify_asset(path)
        if asset_type is None:
            failed_assets.append({"path": str(path), "reason": "unsupported_format"})
            return
        file_hash = sha256_file(path)
        asset = {
            "reference_asset_id": f"ref_{uuid4().hex[:12]}",
            "asset_type": asset_type,
            "source_path": str(path),
            "derived_from": None,
            "language": spec.project.language if asset_type == "text" else None,
            "duration_sec": None,
            "frame_range": None,
            "tags": {
                "role": infer_reference_role(path, asset_type),
                "confidence": 0.6,
            },
            "labels": [asset_type, infer_reference_role(path, asset_type)],
            "quality_flags": {
                "blurry": False,
                "watermark": False,
                "low_light": False,
                "duplicate_suspect": file_hash in dedup,
            },
            "content_hash": file_hash,
            "text_metadata": extract_text_metadata(path) if asset_type == "text" else None,
            "created_at": now_iso(),
        }
        imported_assets.append(asset)
        dedup.setdefault(file_hash, []).append(asset["reference_asset_id"])

    for ref in spec.references.video_dirs:
        handle_path(ctx.root / ref)
    for ref in spec.references.image_dirs:
        handle_path(ctx.root / ref)
    for ref in spec.references.text_notes:
        handle_path(ctx.root / ref)

    manifest = {
        "manifest_id": f"manifest_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "project_file": str(project_file),
        "imported_assets": imported_assets,
        "failed_assets": failed_assets,
        "dedup_groups": [ids for ids in dedup.values() if len(ids) > 1],
        "shot_segments": [],
        "keyframes": [],
        "stats": {
            "num_videos": sum(1 for a in imported_assets if a["asset_type"] == "video"),
            "num_images": sum(1 for a in imported_assets if a["asset_type"] == "image"),
            "num_text_notes": sum(1 for a in imported_assets if a["asset_type"] == "text"),
            "num_shot_segments": 0,
            "num_keyframes": 0,
        },
        "implementation_note": "Directory scan, hashing, role inference, and manifest generation implemented. Media segmentation remains pending.",
        "created_at": now_iso(),
    }
    pack = {
        "reference_pack_id": f"pack_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "manifest_id": manifest["manifest_id"],
        "style_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "style"],
        "character_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "character"],
        "scene_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "scene"],
        "motion_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "motion"],
        "prop_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "prop"],
        "dialogue_assets": [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "dialogue"],
        "excluded_assets": [],
        "pack_version": "v0",
        "created_at": now_iso(),
    }

    manifest_path = ctx.root / "workspace" / "reference_manifest.json"
    pack_path = ctx.root / "workspace" / "reference_pack.json"
    manifest_snapshot_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__reference_manifest.json"
    pack_snapshot_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__reference_pack.json"
    write_json(manifest_path, manifest)
    write_json(pack_path, pack)
    write_json(manifest_snapshot_path, manifest)
    write_json(pack_snapshot_path, pack)
    ctx.record_artifact(path=manifest_path, artifact_type="reference_manifest", source_stage=Stage.INGEST.value)
    ctx.record_artifact(path=pack_path, artifact_type="reference_pack", source_stage=Stage.INGEST.value)
    ctx.record_artifact(path=manifest_snapshot_path, artifact_type="reference_manifest", source_stage=Stage.INGEST.value)
    ctx.record_artifact(path=pack_snapshot_path, artifact_type="reference_pack", source_stage=Stage.INGEST.value)
    return StageResult(
        note=f"Imported {len(imported_assets)} reference assets; {len(failed_assets)} inputs could not be imported.",
        artifacts=[manifest_path, pack_path, manifest_snapshot_path, pack_snapshot_path],
        metadata={"imported_count": len(imported_assets), "failed_count": len(failed_assets)},
    )


def stage_analyze(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    pack_path = ctx.root / "workspace" / "reference_pack.json"
    manifest_path = ctx.root / "workspace" / "reference_manifest.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    imported_assets = manifest["imported_assets"]

    counts_by_role: dict[str, int] = {}
    counts_by_type: dict[str, int] = {}
    term_counts: dict[str, int] = {}
    text_previews: list[dict[str, str]] = []
    for asset in imported_assets:
        counts_by_role[asset["tags"]["role"]] = counts_by_role.get(asset["tags"]["role"], 0) + 1
        counts_by_type[asset["asset_type"]] = counts_by_type.get(asset["asset_type"], 0) + 1
        if asset["asset_type"] == "text":
            text_meta = asset.get("text_metadata")
            if not text_meta:
                source_path = Path(asset["source_path"])
                if source_path.exists():
                    text_meta = extract_text_metadata(source_path)
            if not text_meta:
                continue
            preview = text_meta.get("preview", "")
            text_previews.append(
                {
                    "reference_asset_id": asset["reference_asset_id"],
                    "source_path": asset["source_path"],
                    "preview": preview[:300],
                }
            )
            for term in tokenize_terms(preview):
                term_counts[term] = term_counts.get(term, 0) + 1

    analysis = {
        "analysis_id": f"analysis_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "reference_pack_id": pack["reference_pack_id"],
        "counts_by_role": counts_by_role,
        "counts_by_type": counts_by_type,
        "dominant_role": max(counts_by_role, key=counts_by_role.get) if counts_by_role else None,
        "top_terms": sorted(term_counts.items(), key=lambda item: (-item[1], item[0]))[:20],
        "text_previews": text_previews[:10],
        "notes": [
            "This is a metadata-level analysis pass.",
            "Visual clustering and segmentation are not implemented yet.",
            "Text-note preview extraction and simple keyword mining are implemented.",
            "Legacy manifests without text_metadata are backfilled during analysis.",
        ],
        "created_at": now_iso(),
    }
    analysis_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__analysis_summary.json"
    write_json(analysis_path, analysis)
    ctx.record_artifact(path=analysis_path, artifact_type="analysis_report", source_stage=Stage.ANALYZE.value)
    return StageResult(
        note=f"Analyzed {len(imported_assets)} assets across {len(counts_by_role)} inferred roles.",
        artifacts=[analysis_path],
        metadata=analysis,
    )


def stage_bibles(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    manifest = json.loads((ctx.root / "workspace" / "reference_manifest.json").read_text(encoding="utf-8"))
    imported_assets = manifest["imported_assets"]
    style_assets = [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "style"][:20]
    character_assets = [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "character"]
    scene_assets = [a["reference_asset_id"] for a in imported_assets if a["tags"]["role"] == "scene"]

    style_bible = {
        "style_bible_id": f"style_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "era_target": spec.style.target_era,
        "tone_keywords": spec.style.tone_keywords,
        "palette_keywords": ["low saturation", "controlled highlights"],
        "texture_keywords": ["cinematic grain", "realistic sci-fi surfaces"],
        "lens_language": ["medium closeup", "controlled handheld", "wide establishing"],
        "camera_movement_rules": ["favor restrained motion", "use vertical rise sparingly"],
        "negative_style_rules": ["avoid social-video aesthetics", "avoid oversaturated neon by default"],
        "hero_reference_assets": style_assets,
        "locked": False,
        "version": "v0",
    }
    character_bible = {
        "character_bible_id": f"character_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "characters": [
            {
                "character_id": "char_lead_001",
                "display_name": "Lead Placeholder",
                "role_type": "lead",
                "reference_assets": character_assets[:12],
                "identity_keywords": ["consistent face", "grounded performance"],
                "wardrobe_ids": ["wd_lead_default"],
                "prop_ids": [],
                "continuity_rules": ["preserve identity across scene changes"],
                "allow_lora": True,
                "allow_face_reference": True,
            }
        ]
        if character_assets
        else [],
        "locked": False,
        "version": "v0",
    }
    scene_bible = {
        "scene_bible_id": f"scene_{uuid4().hex[:12]}",
        "project_id": spec.project.id,
        "locations": [
            {
                "location_id": "loc_primary_001",
                "display_name": "Primary Location Placeholder",
                "category": "interior",
                "reference_assets": scene_assets[:12],
                "geometry_proxy_type": "depth_proxy" if scene_assets else "none",
                "lighting_states": ["base"],
                "continuity_rules": ["keep geometry anchors stable"],
            }
        ]
        if scene_assets
        else [],
        "props": [],
        "locked": False,
        "version": "v0",
    }

    bibles_dir = ctx.root / "workspace" / "bibles"
    style_path = bibles_dir / "style_bible.json"
    char_path = bibles_dir / "character_bible.json"
    scene_path = bibles_dir / "scene_bible.json"
    style_snapshot = bibles_dir / f"{ctx.run_id}__style_bible.json"
    char_snapshot = bibles_dir / f"{ctx.run_id}__character_bible.json"
    scene_snapshot = bibles_dir / f"{ctx.run_id}__scene_bible.json"
    write_json(style_path, style_bible)
    write_json(char_path, character_bible)
    write_json(scene_path, scene_bible)
    write_json(style_snapshot, style_bible)
    write_json(char_snapshot, character_bible)
    write_json(scene_snapshot, scene_bible)
    for artifact_path, artifact_type in [
        (style_path, "style_bible"),
        (char_path, "character_bible"),
        (scene_path, "scene_bible"),
        (style_snapshot, "style_bible"),
        (char_snapshot, "character_bible"),
        (scene_snapshot, "scene_bible"),
    ]:
        ctx.record_artifact(path=artifact_path, artifact_type=artifact_type, source_stage=Stage.BIBLES.value)
    return StageResult(
        note="Built initial style, character, and scene bibles from current references.",
        artifacts=[style_path, char_path, scene_path, style_snapshot, char_snapshot, scene_snapshot],
    )


def benchmark_suite_v1() -> list[dict[str, Any]]:
    return [
        {"benchmark_id": "B01_closeup_emotion", "focus": ["identity_consistency", "image_quality"]},
        {"benchmark_id": "B02_dialogue_ots", "focus": ["scene_consistency", "camera_language"]},
        {"benchmark_id": "B03_walk_and_talk", "focus": ["motion_stability", "continuity"]},
        {"benchmark_id": "B04_hand_object_interaction", "focus": ["motion_stability", "instruction_fidelity"]},
        {"benchmark_id": "B05_vertical_rise_establishing", "focus": ["task_ceiling", "camera_control"]},
        {"benchmark_id": "B06_reference_consistency", "focus": ["identity_consistency", "scene_consistency"]},
        {"benchmark_id": "B07_motion_control_stress", "focus": ["motion_stability", "camera_control"]},
        {"benchmark_id": "B08_task_ceiling_stress", "focus": ["task_ceiling", "continuity"]},
    ]


def stage_benchmark(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    providers = spec.benchmark.must_test + spec.benchmark.optional_test
    provider_profiles = {
        "seedance_2_0": {"tier": "first", "specialties": ["narrative_multi_shot", "reference_storytelling", "task_ceiling"]},
        "kling_3_0": {"tier": "first", "specialties": ["motion_control", "action_heavy", "task_ceiling"]},
        "runway_gen_4": {"tier": "second", "specialties": ["hero_cinematic", "image_to_video"]},
        "vidu_q3": {"tier": "second", "specialties": ["dialogue_native_audio", "reference_consistency"]},
        "hailuo_current": {"tier": "second", "specialties": ["insert_cutaway", "creative_variation"]},
    }
    report = {
        "benchmark_report_id": f"benchmark_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "suite_id": spec.benchmark.suite_id,
        "execution_mode": "planning_only",
        "benchmarks": benchmark_suite_v1(),
        "provider_scores": [
            {
                "provider": provider,
                "priority_tier": provider_profiles.get(provider, {}).get("tier", "unknown"),
                "expected_specialties": provider_profiles.get(provider, {}).get("specialties", []),
                "manual_eval_required": True,
            }
            for provider in providers
        ],
        "tier_assignments": {
            "first_tier": [provider for provider in providers if provider_profiles.get(provider, {}).get("tier") == "first"],
            "second_tier": [provider for provider in providers if provider_profiles.get(provider, {}).get("tier") == "second"],
        },
        "routing_recommendation": {
            "narrative_multi_shot": ["seedance_2_0", "kling_3_0"],
            "motion_control": ["kling_3_0", "seedance_2_0"],
            "dialogue_native_audio": ["vidu_q3", "seedance_2_0"],
        },
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__benchmark_report.json"
    write_json(out, report)
    ctx.record_artifact(path=out, artifact_type="benchmark_report", source_stage=Stage.BENCHMARK.value)
    return StageResult(
        note=f"Prepared benchmark suite {spec.benchmark.suite_id} for {len(providers)} providers.",
        artifacts=[out],
        metadata=report,
    )


def stage_plan(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    shot_specs: list[dict[str, Any]] = []
    shot_specs_file = spec.planning.shot_specs_file
    if shot_specs_file:
        source = ctx.root / shot_specs_file
        if source.exists():
            if source.suffix.lower() in {".yaml", ".yml"}:
                payload = yaml.safe_load(source.read_text(encoding="utf-8")) or []
            else:
                payload = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                shot_specs = payload.get("shot_specs", [])
            elif isinstance(payload, list):
                shot_specs = payload
    plan_payload = {
        "plan_id": f"plan_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "shot_specs": shot_specs,
        "note": "Shot plan loaded from planning.shot_specs_file." if shot_specs else "No screenplay or beat sheet input exists yet. Planning scaffold created with empty shot list.",
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__shot_plan.json"
    write_json(out, plan_payload)
    ctx.record_artifact(path=out, artifact_type="shot_plan", source_stage=Stage.PLAN.value)
    return StageResult(note=plan_payload["note"], artifacts=[out], metadata=plan_payload)


def stage_compile_prompts(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    shot_plan_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__shot_plan.json"
    shot_specs: list[dict[str, Any]] = []
    if shot_plan_path.exists():
        shot_specs = json.loads(shot_plan_path.read_text(encoding="utf-8")).get("shot_specs", [])

    packets: list[dict[str, Any]] = []
    for shot in shot_specs:
        archetype = shot.get("archetype", "insert_cutaway")
        provider_chain = shot.get("provider_constraints", {}).get("allowed_providers") or spec.routing.route_matrix.get(archetype, spec.providers.preferred_c_pool)
        for provider in provider_chain[:3]:
            packet = {
                "packet_id": f"packet_{uuid4().hex[:12]}",
                "shot_id": shot["shot_id"],
                "provider": provider,
                "provider_model": provider,
                "prompt_main": " | ".join(
                    [
                        shot.get("subject", ""),
                        shot.get("location", ""),
                        shot.get("action", ""),
                        shot.get("camera", ""),
                        shot.get("style", ""),
                    ]
                ).strip(" |"),
                "prompt_blocks": {
                    "subject": shot.get("subject", ""),
                    "location": shot.get("location", ""),
                    "action": shot.get("action", ""),
                    "camera": shot.get("camera", ""),
                    "style": shot.get("style", ""),
                    "continuity": json.dumps(shot.get("continuity", {}), ensure_ascii=False),
                    "negative_or_avoid": "",
                    "provider_hints": f"archetype={archetype}",
                },
                "negative_prompt": None,
                "reference_assets": {
                    "image_refs": shot.get("references", {}).get("image_refs", []),
                    "video_refs": shot.get("references", {}).get("video_refs", []),
                },
                "generation_params": {
                    "duration_sec": shot.get("duration_target_sec", 8),
                    "aspect_ratio": shot.get("aspect_ratio", "16:9"),
                    "resolution_tier": "standard",
                    "native_audio": shot.get("needs_native_audio", False),
                    "camera_control_mode": "strong" if archetype in {"hero_cinematic", "motion_control"} else "light",
                    "motion_control_mode": "video_drive" if shot.get("needs_motion_control", False) else "none",
                },
                "retry_context": {"retry_count": 0, "prior_fail_reasons": []},
                "compiler_version": "v0",
            }
            packets.append(packet)

    payload = {
        "compile_id": f"compile_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "packets": packets,
        "note": "Compiled provider-specific prompt packets from shot specs." if packets else "Prompt compiler schema ready; no ShotSpec inputs available yet.",
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "prompts" / f"{ctx.run_id}__prompt_packets.json"
    write_json(out, payload)
    ctx.record_artifact(path=out, artifact_type="prompt_packet", source_stage=Stage.COMPILE_PROMPTS.value, retention_policy="cache")
    return StageResult(note=payload["note"], artifacts=[out], metadata={"packet_count": len(packets)})


def stage_route(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    shot_plan_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__shot_plan.json"
    shot_specs: list[dict[str, Any]] = []
    if shot_plan_path.exists():
        shot_specs = json.loads(shot_plan_path.read_text(encoding="utf-8")).get("shot_specs", [])
    packet_path = ctx.root / "workspace" / "prompts" / f"{ctx.run_id}__prompt_packets.json"
    packets: list[dict[str, Any]] = []
    if packet_path.exists():
        packets = json.loads(packet_path.read_text(encoding="utf-8")).get("packets", [])
    packet_index = {(packet["shot_id"], packet["provider"]): packet for packet in packets}

    routed_jobs: list[dict[str, Any]] = []
    created_at = now_iso()
    for shot in shot_specs:
        shot_id = shot["shot_id"]
        archetype = shot.get("archetype", "insert_cutaway")
        provider_chain = spec.routing.route_matrix.get(archetype, spec.providers.preferred_c_pool)
        for rank, provider in enumerate(provider_chain[:2], start=1):
            job_id = f"job_{uuid4().hex[:12]}"
            provider_model = provider
            packet = packet_index.get((shot_id, provider))
            routed_job = {
                "job_id": job_id,
                "shot_id": shot_id,
                "packet_id": packet["packet_id"] if packet else None,
                "provider": provider,
                "provider_model": provider_model,
                "provider_rank": rank,
                "selected_reason": f"route_matrix:{archetype}",
                "archetype": archetype,
                "grade": shot.get("grade", "B"),
                "budget_class": shot.get("budget_class", "standard"),
                "estimated_cost_usd": 0.0,
                "queue_policy": "normal",
                "fallback_chain": provider_chain,
                "status": "queued",
                "external_job_id": None,
                "created_at": created_at,
                "updated_at": created_at,
            }
            routed_jobs.append(routed_job)
            upsert_generation_job(
                ctx.conn,
                job_id=job_id,
                shot_id=shot_id,
                packet_id=routed_job["packet_id"],
                provider=provider,
                provider_model=provider_model,
                provider_rank=rank,
                selected_reason=routed_job["selected_reason"],
                archetype=archetype,
                grade=routed_job["grade"],
                budget_class=routed_job["budget_class"],
                estimated_cost_usd=routed_job["estimated_cost_usd"],
                queue_policy=routed_job["queue_policy"],
                fallback_chain=json.dumps(provider_chain, ensure_ascii=False),
                status="queued",
                external_job_id=None,
                created_at=created_at,
                updated_at=created_at,
            )

    payload = {
        "route_id": f"route_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "route_matrix": spec.routing.route_matrix,
        "first_tier_providers": spec.benchmark.must_test,
        "generation_jobs": routed_jobs,
        "note": "Router matrix materialized and GenerationJob plans created." if routed_jobs else "Router matrix materialized. No ShotSpec inputs available yet, so no GenerationJob records were created.",
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__route_plan.json"
    jobs_out = ctx.root / "workspace" / "jobs" / f"{ctx.run_id}__generation_jobs.json"
    write_json(out, payload)
    write_json(jobs_out, routed_jobs)
    ctx.record_artifact(path=out, artifact_type="route_plan", source_stage=Stage.ROUTE.value)
    ctx.record_artifact(path=jobs_out, artifact_type="generation_job_plan", source_stage=Stage.ROUTE.value, retention_policy="cache")
    return StageResult(note=payload["note"], artifacts=[out, jobs_out], metadata=payload)


def stage_noop(ctx: RunContext, spec: ProjectSpec, stage: Stage) -> StageResult:
    payload = {
        "stage": stage.value,
        "run_id": ctx.run_id,
        "status": "placeholder",
        "note": f"{stage.value} is scaffolded but not implemented yet.",
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__{stage.value}_placeholder.json"
    write_json(out, payload)
    ctx.record_artifact(path=out, artifact_type="report", source_stage=stage.value)
    return StageResult(note=payload["note"], artifacts=[out], metadata=payload)


STAGE_HANDLERS = {
    Stage.INGEST: stage_ingest,
    Stage.ANALYZE: stage_analyze,
    Stage.BIBLES: stage_bibles,
    Stage.BENCHMARK: stage_benchmark,
    Stage.PLAN: stage_plan,
    Stage.COMPILE_PROMPTS: stage_compile_prompts,
    Stage.ROUTE: stage_route,
}


def execute_stage(ctx: RunContext, spec: ProjectSpec, stage: Stage, project_file: Path) -> StageResult:
    handler = STAGE_HANDLERS.get(stage)
    if handler is None:
        return stage_noop(ctx, spec, stage)
    if stage == Stage.INGEST:
        return handler(ctx, spec, project_file)
    return handler(ctx, spec)

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import yaml
import imageio.v2 as imageio
from PIL import Image

from .models import ORDERED_STAGES, ProjectSpec, Stage
from .providers import TERMINAL_PROVIDER_STATES, infer_media_extension, resolve_adapter
from .storage import fetch_human_gates, insert_artifact, row_to_dict, upsert_candidate_clip, upsert_generation_job, upsert_human_gate, upsert_judge_score


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


LIVE_SUBMIT_SUCCESS_STATUSES = {"queued", "submitted"}
JUDGE_READY_CANDIDATE_STATUSES = {"ready", "ready_for_judge"}


def serialize_fallback_chain(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def sync_generation_job_state(
    ctx: RunContext,
    job: dict[str, Any],
    *,
    status: str,
    external_job_id: str | None,
    actual_provider: str | None = None,
    actual_provider_model: str | None = None,
) -> None:
    upsert_generation_job(
        ctx.conn,
        job_id=job["job_id"],
        shot_id=job["shot_id"],
        packet_id=job.get("packet_id"),
        provider=actual_provider or job["provider"],
        provider_model=actual_provider_model or job.get("provider_model", actual_provider or job["provider"]),
        provider_rank=job.get("provider_rank"),
        selected_reason=job.get("selected_reason"),
        archetype=job.get("archetype"),
        grade=job.get("grade"),
        budget_class=job.get("budget_class"),
        estimated_cost_usd=job.get("estimated_cost_usd"),
        queue_policy=job.get("queue_policy"),
        fallback_chain=serialize_fallback_chain(job.get("fallback_chain")),
        status=status,
        external_job_id=external_job_id,
        created_at=job.get("created_at", now_iso()),
        updated_at=now_iso(),
    )


def select_submit_packet(
    job: dict[str, Any],
    submit_provider: str,
    packet_index_by_id: dict[str, dict[str, Any]],
    packet_index_by_shot_provider: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    direct_packet = packet_index_by_shot_provider.get((job["shot_id"], submit_provider))
    if direct_packet is not None:
        return dict(direct_packet)
    fallback_packet = packet_index_by_id.get(job.get("packet_id"))
    if fallback_packet is None:
        return None
    packet = dict(fallback_packet)
    if submit_provider != packet.get("provider"):
        packet["provider"] = submit_provider
        packet["provider_model"] = submit_provider
    return packet


def persist_candidate_record(
    ctx: RunContext,
    *,
    job: dict[str, Any],
    packet: dict[str, Any] | None,
    submit_provider: str,
    planned_provider: str,
    adapter_result: dict[str, Any],
    status: str,
    source_type: str,
    candidate_clip_id: str | None = None,
    media_artifact_path: str | None = None,
    poll_result: dict[str, Any] | None = None,
    download_result: dict[str, Any] | None = None,
    media_probe: dict[str, Any] | None = None,
    media_gate: dict[str, Any] | None = None,
    record_artifact: bool = True,
) -> dict[str, Any]:
    candidate_clip_id = candidate_clip_id or f"candidate_{uuid4().hex[:12]}"
    generation_params = (packet or {}).get("generation_params", {})
    candidate_payload = {
        "run_id": ctx.run_id,
        "candidate_clip_id": candidate_clip_id,
        "job_id": job["job_id"],
        "shot_id": job["shot_id"],
        "provider": submit_provider,
        "planned_provider": planned_provider,
        "provider_model": (packet or {}).get("provider_model", submit_provider),
        "external_job_id": adapter_result.get("external_job_id"),
        "duration_sec": generation_params.get("duration_sec", 0.0),
        "resolution": generation_params.get("resolution_tier", "unknown"),
        "has_native_audio": bool(generation_params.get("native_audio", False)),
        "source_type": source_type,
        "status": status,
        "adapter_result": adapter_result,
        "poll_result": poll_result,
        "download_result": download_result,
        "media_probe": media_probe,
        "media_gate": media_gate,
        "media_artifact_path": media_artifact_path,
        "created_at": now_iso(),
    }
    candidate_path = (
        ctx.root
        / "workspace"
        / "candidates"
        / f"{ctx.run_id}__{job['shot_id']}__{submit_provider}__{candidate_clip_id}.json"
    )
    write_json(candidate_path, candidate_payload)
    artifact_hash = sha256_file(candidate_path)
    upsert_candidate_clip(
        ctx.conn,
        candidate_clip_id=candidate_clip_id,
        job_id=job["job_id"],
        shot_id=job["shot_id"],
        provider=submit_provider,
        provider_model=candidate_payload["provider_model"],
        artifact_path=str(candidate_path),
        duration_sec=float(candidate_payload["duration_sec"]),
        resolution=str(candidate_payload["resolution"]),
        has_native_audio=bool(candidate_payload["has_native_audio"]),
        source_type=source_type,
        artifact_hash=artifact_hash,
        status=status,
        created_at=candidate_payload["created_at"],
    )
    if record_artifact:
        ctx.record_artifact(
            path=candidate_path,
            artifact_type="candidate_clip",
            source_stage=Stage.GENERATE.value,
            source_id=candidate_clip_id,
            retention_policy="cache",
        )
    return candidate_payload


def poll_until_terminal(adapter: Any, external_job_id: str, spec: ProjectSpec) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    poll_events: list[dict[str, Any]] = []
    latest = {
        "provider": adapter.provider_name,
        "mode": "live" if spec.execution.live_mode else "mock",
        "status": "poll_not_started",
        "external_job_id": external_job_id,
    }
    attempts = max(1, spec.execution.poll_max_attempts)
    for attempt in range(1, attempts + 1):
        latest = adapter.poll(external_job_id)
        poll_events.append(
            {
                "phase": "poll",
                "attempt_index": attempt,
                "provider": adapter.provider_name,
                "mode": latest.get("mode"),
                "status": latest.get("status"),
                "external_job_id": external_job_id,
                "request": latest.get("request"),
                "response": latest.get("response"),
                "asset_url": latest.get("asset_url"),
                "error": latest.get("error"),
            }
        )
        if latest.get("status") in TERMINAL_PROVIDER_STATES:
            return latest, poll_events
        if latest.get("status") != "processing":
            return latest, poll_events
        if attempt < attempts and spec.execution.poll_interval_sec > 0:
            time.sleep(spec.execution.poll_interval_sec)
    return latest, poll_events


def should_retry_submit(status: str | None) -> bool:
    return status in {"http_error", "request_failed"}


def should_retry_download(status: str | None) -> bool:
    return status in {"http_error", "download_failed"}


def submit_with_retries(adapter: Any, submit_payload: dict[str, Any], spec: ProjectSpec) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    max_attempts = max(1, spec.workflow.max_api_retries)
    latest: dict[str, Any] = {
        "provider": adapter.provider_name,
        "mode": "live" if spec.execution.live_mode else "mock",
        "status": "request_not_started",
    }
    for retry_index in range(1, max_attempts + 1):
        latest = adapter.submit(submit_payload)
        events.append(
            {
                "phase": "submit",
                "retry_index": retry_index,
                "provider": adapter.provider_name,
                "mode": latest.get("mode"),
                "status": latest.get("status"),
                "external_job_id": latest.get("external_job_id"),
                "request": latest.get("request"),
                "response": latest.get("response"),
                "error": latest.get("error"),
            }
        )
        if latest.get("status") in LIVE_SUBMIT_SUCCESS_STATUSES:
            return latest, events
        if not should_retry_submit(latest.get("status")) or retry_index == max_attempts:
            return latest, events
        time.sleep(min(0.5 * retry_index, 2.0))
    return latest, events


def download_with_retries(adapter: Any, asset_url: str | None, media_path: Path, spec: ProjectSpec) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    max_attempts = max(1, spec.workflow.max_api_retries)
    latest: dict[str, Any] = {
        "provider": adapter.provider_name,
        "mode": "live" if spec.execution.live_mode else "mock",
        "status": "download_not_started",
    }
    for retry_index in range(1, max_attempts + 1):
        latest = adapter.download(asset_url, media_path)
        events.append(
            {
                "phase": "download",
                "retry_index": retry_index,
                "provider": adapter.provider_name,
                "mode": latest.get("mode"),
                "status": latest.get("status"),
                "download_url": asset_url,
                "media_path": str(media_path),
                "response": latest,
                "error": latest.get("error"),
            }
        )
        if latest.get("status") == "downloaded":
            return latest, events
        if not should_retry_download(latest.get("status")) or retry_index == max_attempts:
            return latest, events
        time.sleep(min(0.5 * retry_index, 2.0))
    return latest, events


def probe_media_file(path: Path) -> dict[str, Any]:
    probe = {
        "path": str(path),
        "exists": path.exists(),
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "suffix": path.suffix.lower(),
        "sha256": sha256_file(path) if path.exists() else None,
        "ffprobe_available": bool(shutil.which("ffprobe")),
        "ffprobe_status": "not_run",
        "duration_sec": None,
        "width": None,
        "height": None,
        "codec_name": None,
        "stream_count": None,
    }
    if not path.exists():
        probe["ffprobe_status"] = "missing_file"
        return probe
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        probe["ffprobe_status"] = "ffprobe_unavailable"
        return probe
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            probe["ffprobe_status"] = "ffprobe_failed"
            probe["ffprobe_stderr"] = result.stderr.strip()[:500]
            return probe
        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        fmt = payload.get("format", {})
        probe["ffprobe_status"] = "ok"
        probe["duration_sec"] = float(fmt["duration"]) if fmt.get("duration") not in {None, ""} else None
        probe["stream_count"] = len(streams)
        if video_stream:
            probe["width"] = video_stream.get("width")
            probe["height"] = video_stream.get("height")
            probe["codec_name"] = video_stream.get("codec_name")
        return probe
    except Exception as exc:  # noqa: BLE001
        probe["ffprobe_status"] = "ffprobe_exception"
        probe["ffprobe_error"] = str(exc)
        return probe


def evaluate_media_gate(media_probe: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    status = "pass"
    judge_eligible = True

    if not media_probe.get("exists"):
        reasons.append("missing_media_file")
    if int(media_probe.get("file_size_bytes") or 0) <= 0:
        reasons.append("empty_media_file")

    ffprobe_status = media_probe.get("ffprobe_status")
    if ffprobe_status in {"ffprobe_failed", "ffprobe_exception", "missing_file"}:
        reasons.append(f"probe_error:{ffprobe_status}")
    elif ffprobe_status == "ffprobe_unavailable":
        warnings.append("ffprobe_unavailable")

    if media_probe.get("ffprobe_status") == "ok":
        if int(media_probe.get("stream_count") or 0) <= 0:
            reasons.append("no_streams_detected")
        if not media_probe.get("codec_name"):
            warnings.append("codec_unknown")

    if int(media_probe.get("file_size_bytes") or 0) < 1024:
        warnings.append("tiny_media_file")

    if reasons:
        status = "fail"
        judge_eligible = False
    elif warnings:
        status = "warn"

    return {
        "status": status,
        "judge_eligible": judge_eligible,
        "reasons": reasons,
        "warnings": warnings,
        "created_at": now_iso(),
    }


def compute_next_release_version(root: Path, project_id: str) -> str:
    release_root = root / "workspace" / "release"
    pattern = re.compile(rf"^{re.escape(project_id)}__v(\d{{3}})(?:__.*)?$")
    max_version = 0
    if release_root.exists():
        for path in release_root.iterdir():
            match = pattern.match(path.stem if path.is_file() else path.name)
            if not match:
                continue
            max_version = max(max_version, int(match.group(1)))
    return f"v{max_version + 1:03d}"


VISUAL_SIMILARITY_WARN_THRESHOLD = 10


def build_ffmpeg_post_command(spec: ProjectSpec, source_media_path: Path, processed_path: Path) -> list[str]:
    template = spec.post.processing_template
    ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
    if template == "stream_copy_fast":
        return [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_media_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(processed_path),
        ]
    return [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_media_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        spec.post.ffmpeg_preset,
        "-crf",
        str(spec.post.ffmpeg_crf),
        "-c:a",
        "aac",
        "-b:a",
        spec.post.audio_bitrate,
        "-movflags",
        "+faststart",
        str(processed_path),
    ]


def build_live_submission_attempts(spec: ProjectSpec, shot_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not shot_jobs:
        return []
    primary = spec.execution.primary_provider
    optional = spec.execution.optional_provider
    strategy = spec.execution.submission_strategy
    first_job = shot_jobs[0]
    if strategy == "primary_only":
        return [
            {
                "job": first_job,
                "submit_provider": primary,
                "remapped_from_provider": first_job["provider"] if first_job["provider"] != primary else None,
                "attempt_reason": "primary_only",
            }
        ]
    if strategy == "primary_with_optional_fallback":
        attempts = [
            {
                "job": first_job,
                "submit_provider": primary,
                "remapped_from_provider": first_job["provider"] if first_job["provider"] != primary else None,
                "attempt_reason": "primary_first",
            }
        ]
        if optional != primary and spec.execution.allow_optional_provider_live:
            attempts.append(
                {
                    "job": first_job,
                    "submit_provider": optional,
                    "remapped_from_provider": first_job["provider"] if first_job["provider"] != optional else None,
                    "attempt_reason": "optional_fallback",
                }
            )
        return attempts
    attempts: list[dict[str, Any]] = []
    for job in shot_jobs:
        if job["provider"] == optional and not spec.execution.allow_optional_provider_live:
            continue
        attempts.append(
            {
                "job": job,
                "submit_provider": job["provider"],
                "remapped_from_provider": None,
                "attempt_reason": "planned",
            }
        )
    if attempts:
        return attempts
    return [
        {
            "job": first_job,
            "submit_provider": primary,
            "remapped_from_provider": first_job["provider"] if first_job["provider"] != primary else None,
            "attempt_reason": "planned_fallback_to_primary",
        }
    ]


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
        provider_chain = resolve_provider_chain_for_shot(spec, shot)
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
        provider_chain = resolve_provider_chain_for_shot(spec, shot)
        constraints = shot.get("provider_constraints", {}) or {}
        if constraints.get("continuity_preferred_provider"):
            selected_reason = f"continuity_reroute:{constraints['continuity_preferred_provider']}"
        elif normalize_str_list(constraints.get("allowed_providers")):
            selected_reason = "provider_constraints:allowed_providers"
        elif normalize_str_list(constraints.get("banned_providers")):
            selected_reason = "provider_constraints:banned_providers"
        else:
            selected_reason = f"route_matrix:{archetype}"
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
                "selected_reason": selected_reason,
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


def stage_generate(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    jobs_path = ctx.root / "workspace" / "jobs" / f"{ctx.run_id}__generation_jobs.json"
    routed_jobs: list[dict[str, Any]] = []
    if jobs_path.exists():
        routed_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    packets_path = ctx.root / "workspace" / "prompts" / f"{ctx.run_id}__prompt_packets.json"
    packets: list[dict[str, Any]] = []
    if packets_path.exists():
        packets = json.loads(packets_path.read_text(encoding="utf-8")).get("packets", [])
    packet_index = {packet["packet_id"]: packet for packet in packets}
    packet_index_by_shot_provider = {(packet["shot_id"], packet["provider"]): packet for packet in packets}

    generated_candidates: list[dict[str, Any]] = []
    provider_requests: list[dict[str, Any]] = []
    attempt_summaries: list[dict[str, Any]] = []
    jobs_by_shot: dict[str, list[dict[str, Any]]] = {}
    for job in routed_jobs:
        jobs_by_shot.setdefault(job["shot_id"], []).append(job)

    if not spec.execution.live_mode:
        for job in routed_jobs:
            packet = packet_index.get(job.get("packet_id"))
            submit_payload = dict(job)
            if packet:
                submit_payload.update(packet)
            submit_payload["planned_provider"] = job["provider"]
            submit_payload["submit_provider"] = job["provider"]
            submit_payload["remapped_from_provider"] = None
            adapter = resolve_adapter(spec, job["provider"])
            adapter_result = adapter.submit(submit_payload)
            sync_generation_job_state(
                ctx,
                job,
                status=adapter_result.get("status", "queued"),
                external_job_id=adapter_result.get("external_job_id"),
            )
            provider_requests.append(
                {
                    "phase": "submit",
                    "shot_id": job["shot_id"],
                    "job_id": job["job_id"],
                    "attempt_index": 1,
                    "provider": job["provider"],
                    "planned_provider": job["provider"],
                    "remapped_from_provider": None,
                    "attempt_reason": "dry_run_or_mock",
                    "mode": adapter_result.get("mode"),
                    "status": adapter_result.get("status"),
                    "external_job_id": adapter_result.get("external_job_id"),
                    "request": adapter_result.get("request"),
                    "response": adapter_result.get("response"),
                    "error": adapter_result.get("error"),
                }
            )
            generated_candidates.append(
                persist_candidate_record(
                    ctx,
                    job=job,
                    packet=packet,
                    submit_provider=job["provider"],
                    planned_provider=job["provider"],
                    adapter_result=adapter_result,
                    status="ready",
                    source_type="mock_candidate",
                )
            )
    else:
        for shot_id in sorted(jobs_by_shot):
            shot_jobs = sorted(jobs_by_shot[shot_id], key=lambda item: int(item.get("provider_rank") or 999))
            attempts = build_live_submission_attempts(spec, shot_jobs)
            attempted_job_ids: set[str] = set()
            success = False
            last_attempt_context: dict[str, Any] | None = None
            shot_summary = {
                "shot_id": shot_id,
                "planned_provider_chain": [job["provider"] for job in shot_jobs],
                "attempt_count": 0,
                "attempted_providers": [],
                "fallback_used": False,
                "fallback_trigger_reason": None,
                "final_provider": None,
                "final_status": "not_started",
                "candidate_clip_id": None,
                "judge_ready": False,
                "media_gate_status": None,
                "attempts": [],
            }
            for attempt_index, attempt in enumerate(attempts, start=1):
                job = attempt["job"]
                submit_provider = attempt["submit_provider"]
                remapped_from_provider = attempt["remapped_from_provider"]
                fallback_trigger_reason = None
                if attempt_index > 1 and last_attempt_context is not None:
                    fallback_trigger_reason = f"{last_attempt_context['provider']}:{last_attempt_context['status']}"
                    shot_summary["fallback_used"] = True
                    if shot_summary["fallback_trigger_reason"] is None:
                        shot_summary["fallback_trigger_reason"] = fallback_trigger_reason
                attempted_job_ids.add(job["job_id"])
                shot_summary["attempt_count"] = attempt_index
                shot_summary["attempted_providers"].append(submit_provider)
                packet = select_submit_packet(job, submit_provider, packet_index, packet_index_by_shot_provider)
                submit_payload = dict(job)
                if packet:
                    submit_payload.update(packet)
                submit_payload["provider"] = submit_provider
                submit_payload["provider_model"] = (packet or {}).get("provider_model", submit_provider)
                submit_payload["planned_provider"] = job["provider"]
                submit_payload["submit_provider"] = submit_provider
                submit_payload["remapped_from_provider"] = remapped_from_provider
                adapter = resolve_adapter(spec, submit_provider)
                adapter_result, submit_events = submit_with_retries(adapter, submit_payload, spec)
                sync_generation_job_state(
                    ctx,
                    job,
                    status=adapter_result.get("status", "request_failed"),
                    external_job_id=adapter_result.get("external_job_id"),
                    actual_provider=submit_provider,
                    actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                )
                for event in submit_events:
                    event.update(
                        {
                            "shot_id": shot_id,
                            "job_id": job["job_id"],
                            "attempt_index": attempt_index,
                            "planned_provider": job["provider"],
                            "remapped_from_provider": remapped_from_provider,
                            "attempt_reason": attempt["attempt_reason"],
                            "fallback_trigger_reason": fallback_trigger_reason,
                        }
                    )
                provider_requests.extend(submit_events)
                attempt_summary = {
                    "attempt_index": attempt_index,
                    "planned_provider": job["provider"],
                    "submit_provider": submit_provider,
                    "attempt_reason": attempt["attempt_reason"],
                    "fallback_trigger_reason": fallback_trigger_reason,
                    "submit_status": adapter_result.get("status"),
                    "poll_status": None,
                    "download_status": None,
                    "final_candidate_status": None,
                    "media_gate_status": None,
                }
                shot_summary["attempts"].append(attempt_summary)
                if adapter_result.get("status") in LIVE_SUBMIT_SUCCESS_STATUSES:
                    shot_summary["final_provider"] = submit_provider
                    shot_summary["final_status"] = adapter_result.get("status")
                    candidate_payload = persist_candidate_record(
                        ctx,
                        job=job,
                        packet=packet,
                        submit_provider=submit_provider,
                        planned_provider=job["provider"],
                        adapter_result=adapter_result,
                        status="submitted",
                        source_type="provider_submission_receipt",
                    )
                    generated_candidates.append(candidate_payload)
                    external_job_id = adapter_result.get("external_job_id")
                    if spec.execution.poll_after_submit and external_job_id:
                        poll_result, poll_events = poll_until_terminal(adapter, external_job_id, spec)
                        attempt_summary["poll_status"] = poll_result.get("status")
                        for event in poll_events:
                            event["shot_id"] = shot_id
                            event["job_id"] = job["job_id"]
                            event["fallback_trigger_reason"] = fallback_trigger_reason
                        provider_requests.extend(poll_events)
                        if poll_result.get("status") == "completed":
                            asset_url = poll_result.get("asset_url")
                            media_path = (
                                ctx.root
                                / "workspace"
                                / "downloads"
                                / f"{ctx.run_id}__{shot_id}__{submit_provider}__{candidate_payload['candidate_clip_id']}{infer_media_extension(asset_url)}"
                            )
                            download_result, download_events = download_with_retries(adapter, asset_url, media_path, spec)
                            for event in download_events:
                                event.update(
                                    {
                                        "shot_id": shot_id,
                                        "job_id": job["job_id"],
                                        "attempt_index": attempt_index,
                                        "planned_provider": job["provider"],
                                        "remapped_from_provider": remapped_from_provider,
                                        "external_job_id": external_job_id,
                                        "mode": download_result.get("mode"),
                                        "request": {"download_url": asset_url, "media_path": str(media_path)},
                                        "fallback_trigger_reason": fallback_trigger_reason,
                                    }
                                )
                            provider_requests.extend(download_events)
                            attempt_summary["download_status"] = download_result.get("status")
                            if download_result.get("status") == "downloaded":
                                sync_generation_job_state(
                                    ctx,
                                    job,
                                    status="downloaded",
                                    external_job_id=external_job_id,
                                    actual_provider=submit_provider,
                                    actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                                )
                                media_probe = probe_media_file(media_path)
                                media_gate = evaluate_media_gate(media_probe)
                                probe_path = media_path.with_suffix(f"{media_path.suffix}.probe.json")
                                gate_path = media_path.with_suffix(f"{media_path.suffix}.gate.json")
                                write_json(probe_path, media_probe)
                                write_json(gate_path, media_gate)
                                ctx.record_artifact(
                                    path=media_path,
                                    artifact_type="candidate_media",
                                    source_stage=Stage.GENERATE.value,
                                    source_id=candidate_payload["candidate_clip_id"],
                                    retention_policy="cache",
                                )
                                ctx.record_artifact(
                                    path=gate_path,
                                    artifact_type="candidate_media_gate",
                                    source_stage=Stage.GENERATE.value,
                                    source_id=candidate_payload["candidate_clip_id"],
                                    retention_policy="cache",
                                )
                                ctx.record_artifact(
                                    path=probe_path,
                                    artifact_type="candidate_media_probe",
                                    source_stage=Stage.GENERATE.value,
                                    source_id=candidate_payload["candidate_clip_id"],
                                    retention_policy="cache",
                                )
                                candidate_payload = persist_candidate_record(
                                    ctx,
                                    job=job,
                                    packet=packet,
                                    submit_provider=submit_provider,
                                    planned_provider=job["provider"],
                                    adapter_result=adapter_result,
                                    status="ready_for_judge" if media_gate["judge_eligible"] else "media_gate_failed",
                                    source_type="downloaded_candidate",
                                    candidate_clip_id=candidate_payload["candidate_clip_id"],
                                    media_artifact_path=str(media_path),
                                    poll_result=poll_result,
                                    download_result=download_result,
                                    media_probe=media_probe,
                                    media_gate=media_gate,
                                    record_artifact=False,
                                )
                                generated_candidates[-1] = candidate_payload
                                shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                                shot_summary["judge_ready"] = bool(media_gate["judge_eligible"])
                                shot_summary["media_gate_status"] = media_gate["status"]
                                shot_summary["final_status"] = candidate_payload["status"]
                                attempt_summary["final_candidate_status"] = candidate_payload["status"]
                                attempt_summary["media_gate_status"] = media_gate["status"]
                            else:
                                sync_generation_job_state(
                                    ctx,
                                    job,
                                    status="download_failed",
                                    external_job_id=external_job_id,
                                    actual_provider=submit_provider,
                                    actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                                )
                                candidate_payload = persist_candidate_record(
                                    ctx,
                                    job=job,
                                    packet=packet,
                                    submit_provider=submit_provider,
                                    planned_provider=job["provider"],
                                    adapter_result=adapter_result,
                                    status="download_failed",
                                    source_type="provider_submission_receipt",
                                    candidate_clip_id=candidate_payload["candidate_clip_id"],
                                    poll_result=poll_result,
                                    download_result=download_result,
                                    record_artifact=False,
                                )
                                generated_candidates[-1] = candidate_payload
                                shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                                shot_summary["final_status"] = candidate_payload["status"]
                                attempt_summary["final_candidate_status"] = candidate_payload["status"]
                        elif poll_result.get("status") == "failed":
                            sync_generation_job_state(
                                ctx,
                                job,
                                status="provider_failed",
                                external_job_id=external_job_id,
                                actual_provider=submit_provider,
                                actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                            )
                            candidate_payload = persist_candidate_record(
                                ctx,
                                job=job,
                                packet=packet,
                                submit_provider=submit_provider,
                                planned_provider=job["provider"],
                                adapter_result=adapter_result,
                                status="provider_failed",
                                source_type="provider_submission_receipt",
                                candidate_clip_id=candidate_payload["candidate_clip_id"],
                                poll_result=poll_result,
                                record_artifact=False,
                            )
                            generated_candidates[-1] = candidate_payload
                            shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                            shot_summary["final_status"] = candidate_payload["status"]
                            attempt_summary["final_candidate_status"] = candidate_payload["status"]
                        elif poll_result.get("status") == "processing":
                            sync_generation_job_state(
                                ctx,
                                job,
                                status="processing",
                                external_job_id=external_job_id,
                                actual_provider=submit_provider,
                                actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                            )
                            shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                            shot_summary["final_status"] = "processing"
                            attempt_summary["final_candidate_status"] = "processing"
                        elif poll_result.get("status") not in {"processing", "unknown"}:
                            sync_generation_job_state(
                                ctx,
                                job,
                                status=str(poll_result.get("status") or "submitted"),
                                external_job_id=external_job_id,
                                actual_provider=submit_provider,
                                actual_provider_model=(packet or {}).get("provider_model", submit_provider),
                            )
                            candidate_payload = persist_candidate_record(
                                ctx,
                                job=job,
                                packet=packet,
                                submit_provider=submit_provider,
                                planned_provider=job["provider"],
                                adapter_result=adapter_result,
                                status="submitted",
                                source_type="provider_submission_receipt",
                                candidate_clip_id=candidate_payload["candidate_clip_id"],
                                poll_result=poll_result,
                                record_artifact=False,
                            )
                            generated_candidates[-1] = candidate_payload
                            shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                            shot_summary["final_status"] = candidate_payload["status"]
                            attempt_summary["final_candidate_status"] = candidate_payload["status"]
                    else:
                        shot_summary["candidate_clip_id"] = candidate_payload["candidate_clip_id"]
                        shot_summary["final_status"] = candidate_payload["status"]
                        attempt_summary["final_candidate_status"] = candidate_payload["status"]
                    success = True
                    break
                last_attempt_context = {"provider": submit_provider, "status": adapter_result.get("status")}
                shot_summary["final_status"] = adapter_result.get("status") or "request_failed"
            for job in shot_jobs:
                if job["job_id"] in attempted_job_ids:
                    continue
                residual_status = "not_attempted_after_success" if success else "suppressed_by_strategy"
                sync_generation_job_state(ctx, job, status=residual_status, external_job_id=None)
            attempt_summaries.append(shot_summary)

    status_counts: dict[str, int] = {}
    for entry in provider_requests:
        key = str(entry.get("status") or "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    ready_candidate_count = sum(1 for candidate in generated_candidates if candidate.get("status") in JUDGE_READY_CANDIDATE_STATUSES)
    submitted_receipt_count = sum(1 for candidate in generated_candidates if candidate.get("status") == "submitted")
    gated_out_candidate_count = sum(1 for candidate in generated_candidates if candidate.get("status") == "media_gate_failed")
    media_gate_status_counts: dict[str, int] = {}
    for candidate in generated_candidates:
        media_gate = candidate.get("media_gate")
        if not isinstance(media_gate, dict):
            continue
        key = str(media_gate.get("status") or "unknown")
        media_gate_status_counts[key] = media_gate_status_counts.get(key, 0) + 1
    summary = {
        "generate_id": f"generate_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "candidate_count": len(generated_candidates),
        "ready_candidate_count": ready_candidate_count,
        "submitted_receipt_count": submitted_receipt_count,
        "gated_out_candidate_count": gated_out_candidate_count,
        "candidates": generated_candidates,
        "attempt_summaries": attempt_summaries,
        "provider_requests": provider_requests,
        "provider_request_status_counts": status_counts,
        "media_gate_status_counts": media_gate_status_counts,
        "note": (
            (
                "Submitted live provider requests, polled results, and materialized judge-ready candidate media."
                if ready_candidate_count
                else "Submitted live provider requests and downloaded media, but all candidates were gated out before judge."
                if gated_out_candidate_count
                else "Submitted live provider requests and recorded provider submission receipts."
                if generated_candidates
                else "Attempted live provider submission, but no provider submission receipts were created."
            )
            if spec.execution.live_mode
            else "Created mock candidate clip placeholders from generation jobs."
        ),
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__generate_summary.json"
    requests_out = ctx.root / "workspace" / "jobs" / f"{ctx.run_id}__provider_requests.json"
    write_json(out, summary)
    if spec.execution.save_provider_requests:
        write_json(requests_out, provider_requests)
    ctx.record_artifact(path=out, artifact_type="report", source_stage=Stage.GENERATE.value)
    if spec.execution.save_provider_requests:
        ctx.record_artifact(path=requests_out, artifact_type="provider_request_log", source_stage=Stage.GENERATE.value, retention_policy="cache")
    return StageResult(
        note=summary["note"],
        artifacts=[out, requests_out] if spec.execution.save_provider_requests else [out],
        metadata={
            "candidate_count": len(generated_candidates),
            "ready_candidate_count": ready_candidate_count,
            "submitted_receipt_count": submitted_receipt_count,
            "gated_out_candidate_count": gated_out_candidate_count,
        },
    )


def evaluate_candidate(provider: str, archetype: str, grade: str) -> dict[str, Any]:
    base = {
        "identity_consistency": 7.4,
        "scene_consistency": 7.2,
        "instruction_fidelity": 7.3,
        "motion_stability": 7.1,
        "camera_language": 7.0,
        "image_quality": 7.5,
        "audio_sync": None,
        "narrative_utility": 7.2,
        "artifact_penalty": 0.0,
    }
    if provider == "seedance_2_0" and archetype == "narrative_multi_shot":
        base.update({"scene_consistency": 8.6, "instruction_fidelity": 8.5, "narrative_utility": 8.8, "motion_stability": 8.1})
    elif provider == "kling_3_0" and archetype == "motion_control":
        base.update({"identity_consistency": 8.4, "motion_stability": 8.8, "camera_language": 8.2})
    elif provider == "vidu_q3" and archetype == "dialogue_native_audio":
        base.update({"audio_sync": 8.5, "narrative_utility": 8.0, "instruction_fidelity": 7.9})
    elif provider == "seedance_2_0" and archetype == "dialogue_native_audio":
        base.update({"audio_sync": 7.8, "narrative_utility": 7.8})
    elif provider == "kling_3_0" and archetype == "narrative_multi_shot":
        base.update({"scene_consistency": 8.0, "motion_stability": 8.2, "narrative_utility": 8.0})

    weights = {
        "identity_consistency": 0.18,
        "scene_consistency": 0.14,
        "instruction_fidelity": 0.14,
        "motion_stability": 0.14,
        "camera_language": 0.10,
        "image_quality": 0.12,
        "audio_sync": 0.08,
        "narrative_utility": 0.10,
    }
    values = {k: v for k, v in base.items() if k in weights and v is not None}
    effective_total = sum(weights[k] for k in values)
    weighted = sum(values[k] * weights[k] for k in values) / effective_total
    weighted -= float(base["artifact_penalty"])

    if grade == "A":
        pass_threshold, review_threshold = 8.4, 7.8
    elif grade == "B":
        pass_threshold, review_threshold = 7.8, 7.2
    else:
        pass_threshold, review_threshold = 7.0, 6.5

    if weighted >= pass_threshold:
        decision = "pass"
        route_back_stage = None
    elif weighted >= review_threshold:
        decision = "review"
        route_back_stage = None
    else:
        decision = "regenerate_same_provider"
        route_back_stage = "generate"

    return {
        "metrics": base,
        "weighted_total_score": round(weighted, 3),
        "decision": decision,
        "route_back_stage": route_back_stage,
        "hard_fail": False,
        "hard_fail_reasons": [],
    }


def apply_media_gate_decision(candidate: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    media_gate = candidate.get("media_gate")
    if not isinstance(media_gate, dict):
        evaluation["decision_reasons"] = []
        evaluation["media_gate_status"] = None
        return evaluation

    gate_status = str(media_gate.get("status") or "unknown")
    gate_reasons = [str(item) for item in media_gate.get("reasons", [])]
    gate_warnings = [str(item) for item in media_gate.get("warnings", [])]
    decision_reasons: list[str] = []

    evaluation["media_gate_status"] = gate_status
    if not media_gate.get("judge_eligible", True):
        evaluation["weighted_total_score"] = 0.0
        evaluation["decision"] = "regenerate_same_provider"
        evaluation["route_back_stage"] = "generate"
        evaluation["hard_fail"] = True
        evaluation["hard_fail_reasons"] = (
            [f"media_gate:{reason}" for reason in gate_reasons]
            if gate_reasons
            else [f"media_gate:{gate_status}"]
        )
        decision_reasons.append("media_gate_blocked")
    elif gate_status == "warn" and evaluation["decision"] != "regenerate_same_provider":
        evaluation["decision"] = "review"
        evaluation["route_back_stage"] = "review"
        decision_reasons.append("media_gate_warn")

    if gate_reasons:
        decision_reasons.extend(f"media_gate_reason:{reason}" for reason in gate_reasons)
    if gate_warnings:
        decision_reasons.extend(f"media_gate_warning:{warning}" for warning in gate_warnings)
    evaluation["decision_reasons"] = decision_reasons
    return evaluation


def normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    if value in {"", None}:
        return []
    return [str(value)]


def classify_image_path(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def classify_visual_ref_path(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".webm", ".mkv"}


def resolve_existing_visual_ref_paths(root: Path, refs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for ref in refs:
        candidate = Path(ref)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file() and classify_visual_ref_path(candidate):
            paths.append(candidate)
    return paths


def load_visual_ref_image(path: Path) -> Image.Image | None:
    try:
        if classify_image_path(path):
            with Image.open(path) as img:
                return img.convert("RGB")
        frames = imageio.mimread(path, memtest=False)
        if not frames:
            return None
        frame = frames[0]
        return Image.fromarray(frame).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def compute_image_signature(path: Path) -> dict[str, Any] | None:
    try:
        loaded = load_visual_ref_image(path)
        if loaded is None:
            return None
        rgb = loaded.resize((32, 32))
        gray = loaded.convert("L").resize((8, 8))
        gray_arr = np.asarray(gray, dtype=np.float32)
        rgb_arr = np.asarray(rgb, dtype=np.float32)
        mean = float(gray_arr.mean())
        bits = (gray_arr > mean).astype(np.uint8).flatten().tolist()
        return {
            "path": str(path),
            "source_type": "image" if classify_image_path(path) else "video_frame",
            "hash_bits": bits,
            "mean_rgb": rgb_arr.mean(axis=(0, 1)).round(3).tolist(),
            "width": int(rgb_arr.shape[1]),
            "height": int(rgb_arr.shape[0]),
        }
    except Exception:  # noqa: BLE001
        return None


def hamming_distance(bits_a: list[int], bits_b: list[int]) -> int:
    return sum(int(a != b) for a, b in zip(bits_a, bits_b, strict=False))


def rgb_mean_distance(rgb_a: list[float], rgb_b: list[float]) -> float:
    arr_a = np.asarray(rgb_a, dtype=np.float32)
    arr_b = np.asarray(rgb_b, dtype=np.float32)
    return float(np.linalg.norm(arr_a - arr_b))


def build_visual_continuity_report(root: Path, shot_specs: list[dict[str, Any]]) -> dict[str, Any]:
    shot_images: dict[str, list[dict[str, Any]]] = {}
    skipped_shots: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    sequence_index: dict[str, list[dict[str, Any]]] = {}
    character_index: dict[str, list[dict[str, Any]]] = {}

    for shot in shot_specs:
        shot_id = str(shot["shot_id"])
        references = shot.get("references", {}) or {}
        refs = normalize_str_list(references.get("image_refs")) + normalize_str_list(references.get("video_refs"))
        visual_paths = resolve_existing_visual_ref_paths(root, refs)
        if not visual_paths:
            skipped_shots.append(
                {
                    "shot_id": shot_id,
                    "reason": "missing_visual_refs",
                }
            )
            continue
        signatures = [signature for signature in (compute_image_signature(path) for path in visual_paths) if signature]
        if not signatures:
            skipped_shots.append(
                {
                    "shot_id": shot_id,
                    "reason": "visual_signature_failed",
                }
            )
            continue
        entry = {
            "shot_id": shot_id,
            "sequence_id": str(shot.get("sequence_id") or ""),
            "character_ids": normalize_str_list(((shot.get("continuity", {}) or {}).get("character_ids"))),
            "signatures": signatures,
        }
        shot_images[shot_id] = signatures
        sequence_index.setdefault(entry["sequence_id"], []).append(entry)
        for character_id in entry["character_ids"]:
            character_index.setdefault(character_id, []).append(entry)

    pairwise_checks: list[dict[str, Any]] = []
    for character_id, entries in sorted(character_index.items()):
        if len(entries) < 2:
            continue
        for idx, left in enumerate(entries):
            for right in entries[idx + 1 :]:
                left_sig = left["signatures"][0]
                right_sig = right["signatures"][0]
                distance = hamming_distance(left_sig["hash_bits"], right_sig["hash_bits"])
                pairwise = {
                    "scope": "character",
                    "scope_id": character_id,
                    "left_shot_id": left["shot_id"],
                    "right_shot_id": right["shot_id"],
                    "distance": distance,
                    "color_distance": round(rgb_mean_distance(left_sig["mean_rgb"], right_sig["mean_rgb"]), 3),
                }
                pairwise_checks.append(pairwise)
                if distance >= VISUAL_SIMILARITY_WARN_THRESHOLD or pairwise["color_distance"] >= 80.0:
                    issues.append(
                        {
                            "issue_id": f"vcont_{uuid4().hex[:10]}",
                            "severity": "warn",
                            "scope": "character",
                            "scope_id": character_id,
                            "issue_type": "visual_character_similarity_low",
                            "message": f"{character_id} has visually divergent references between {left['shot_id']} and {right['shot_id']}",
                        }
                    )

    for sequence_id, entries in sorted(sequence_index.items()):
        if len(entries) < 2:
            continue
        sequence_distances: list[int] = []
        for idx, left in enumerate(entries):
            for right in entries[idx + 1 :]:
                left_sig = left["signatures"][0]
                right_sig = right["signatures"][0]
                distance = hamming_distance(left_sig["hash_bits"], right_sig["hash_bits"])
                sequence_distances.append(distance)
        color_distances = [
            rgb_mean_distance(left["signatures"][0]["mean_rgb"], right["signatures"][0]["mean_rgb"])
            for idx, left in enumerate(entries)
            for right in entries[idx + 1 :]
        ]
        if sequence_distances and (
            max(sequence_distances) >= VISUAL_SIMILARITY_WARN_THRESHOLD
            or (color_distances and max(color_distances) >= 80.0)
        ):
            issues.append(
                {
                    "issue_id": f"vcont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "sequence",
                    "scope_id": sequence_id,
                    "issue_type": "visual_sequence_similarity_low",
                    "message": f"{sequence_id} has visually divergent shot references",
                }
            )

    return {
        "available_shot_images": len(shot_images),
        "available_shot_visual_refs": len(shot_images),
        "pairwise_checks": pairwise_checks,
        "issues": issues,
        "skipped_shots": skipped_shots,
        "counts": {
            "shots_with_images": len(shot_images),
            "shots_with_visual_refs": len(shot_images),
            "pairwise_checks": len(pairwise_checks),
            "issues": len(issues),
            "skipped_shots": len(skipped_shots),
        },
    }


def build_continuity_report(
    *,
    root: Path,
    run_id: str,
    shot_specs: list[dict[str, Any]],
    review_records: list[dict[str, Any]],
) -> dict[str, Any]:
    shot_meta: dict[str, dict[str, Any]] = {}
    for shot in shot_specs:
        continuity = shot.get("continuity", {}) or {}
        shot_meta[str(shot["shot_id"])] = {
            "shot_id": str(shot["shot_id"]),
            "sequence_id": str(shot.get("sequence_id") or "unknown_sequence"),
            "scene_id": str(shot.get("scene_id") or "unknown_scene"),
            "character_ids": normalize_str_list(continuity.get("character_ids")),
            "wardrobe_ids": normalize_str_list(continuity.get("wardrobe_ids")),
            "location_id": str(continuity.get("location_id") or ""),
            "prop_ids": normalize_str_list(continuity.get("prop_ids")),
            "archetype": shot.get("archetype"),
            "grade": shot.get("grade"),
        }

    shot_decisions: dict[str, list[dict[str, Any]]] = {}
    for record in review_records:
        shot_decisions.setdefault(str(record["shot_id"]), []).append(record)

    issues: list[dict[str, Any]] = []
    sequence_index: dict[str, list[dict[str, Any]]] = {}
    character_index: dict[str, list[dict[str, Any]]] = {}
    shot_contexts: list[dict[str, Any]] = []

    for shot_id, meta in shot_meta.items():
        decisions = shot_decisions.get(shot_id, [])
        providers = sorted({str(item.get("provider")) for item in decisions if item.get("provider")})
        decision_types = sorted({str(item.get("decision")) for item in decisions if item.get("decision")})
        shot_context = {
            **meta,
            "providers": providers,
            "decisions": decision_types,
            "candidate_count": len(decisions),
        }
        shot_contexts.append(shot_context)
        sequence_index.setdefault(meta["sequence_id"], []).append(shot_context)
        for character_id in meta["character_ids"]:
            character_index.setdefault(character_id, []).append(shot_context)

        if not meta["character_ids"]:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "shot",
                    "scope_id": shot_id,
                    "issue_type": "missing_character_ids",
                    "message": f"{shot_id} is missing continuity.character_ids",
                }
            )
        if not meta["location_id"]:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "shot",
                    "scope_id": shot_id,
                    "issue_type": "missing_location_id",
                    "message": f"{shot_id} is missing continuity.location_id",
                }
            )
        if len(providers) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "shot",
                    "scope_id": shot_id,
                    "issue_type": "shot_provider_mixture",
                    "message": f"{shot_id} has multiple candidate providers: {', '.join(providers)}",
                }
            )

    sequence_summaries: list[dict[str, Any]] = []
    for sequence_id, shots in sorted(sequence_index.items()):
        location_ids = sorted({shot["location_id"] for shot in shots if shot["location_id"]})
        wardrobe_ids = sorted({wardrobe_id for shot in shots for wardrobe_id in shot["wardrobe_ids"]})
        providers = sorted({provider for shot in shots for provider in shot["providers"]})
        decisions = sorted({decision for shot in shots for decision in shot["decisions"]})
        summary = {
            "sequence_id": sequence_id,
            "shot_ids": [shot["shot_id"] for shot in shots],
            "location_ids": location_ids,
            "wardrobe_ids": wardrobe_ids,
            "providers": providers,
            "decisions": decisions,
        }
        sequence_summaries.append(summary)
        if len(location_ids) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "sequence",
                    "scope_id": sequence_id,
                    "issue_type": "sequence_location_variation",
                    "message": f"{sequence_id} spans multiple continuity locations: {', '.join(location_ids)}",
                }
            )
        if len(wardrobe_ids) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "sequence",
                    "scope_id": sequence_id,
                    "issue_type": "sequence_wardrobe_variation",
                    "message": f"{sequence_id} spans multiple wardrobe ids: {', '.join(wardrobe_ids)}",
                }
            )
        if len(providers) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "sequence",
                    "scope_id": sequence_id,
                    "issue_type": "sequence_provider_mixture",
                    "message": f"{sequence_id} mixes providers: {', '.join(providers)}",
                }
            )
        if len(decisions) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "sequence",
                    "scope_id": sequence_id,
                    "issue_type": "sequence_decision_divergence",
                    "message": f"{sequence_id} has mixed review decisions: {', '.join(decisions)}",
                }
            )

    character_summaries: list[dict[str, Any]] = []
    for character_id, shots in sorted(character_index.items()):
        providers = sorted({provider for shot in shots for provider in shot["providers"]})
        wardrobe_ids = sorted({wardrobe_id for shot in shots for wardrobe_id in shot["wardrobe_ids"]})
        summary = {
            "character_id": character_id,
            "shot_ids": [shot["shot_id"] for shot in shots],
            "providers": providers,
            "wardrobe_ids": wardrobe_ids,
        }
        character_summaries.append(summary)
        if len(providers) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "character",
                    "scope_id": character_id,
                    "issue_type": "character_provider_mixture",
                    "message": f"{character_id} is represented by multiple providers: {', '.join(providers)}",
                }
            )
        if len(wardrobe_ids) > 1:
            issues.append(
                {
                    "issue_id": f"cont_{uuid4().hex[:10]}",
                    "severity": "warn",
                    "scope": "character",
                    "scope_id": character_id,
                    "issue_type": "character_wardrobe_variation",
                    "message": f"{character_id} spans multiple wardrobe ids: {', '.join(wardrobe_ids)}",
                }
            )

    visual_report = build_visual_continuity_report(root, shot_specs)
    issues.extend(visual_report["issues"])
    return {
        "continuity_id": f"continuity_{uuid4().hex[:12]}",
        "run_id": run_id,
        "shot_contexts": shot_contexts,
        "sequence_summaries": sequence_summaries,
        "character_summaries": character_summaries,
        "visual_checks": visual_report,
        "issues": issues,
        "counts": {
            "shots": len(shot_contexts),
            "sequences": len(sequence_summaries),
            "characters": len(character_summaries),
            "issues": len(issues),
            "visual_issues": len(visual_report["issues"]),
            "visual_skipped_shots": len(visual_report["skipped_shots"]),
        },
        "created_at": now_iso(),
    }


def build_continuity_issue_index(continuity_report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for issue in continuity_report.get("issues", []) or []:
        scope_id = str(issue.get("scope_id") or "")
        if scope_id:
            index.setdefault(scope_id, []).append(issue)
    return index


def resolve_existing_file_path(value: Any) -> Path | None:
    if value in {None, ""}:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = Path(str(value))
    if path.exists() and path.is_file():
        return path
    return None


def resolve_provider_chain_for_shot(spec: ProjectSpec, shot: dict[str, Any]) -> list[str]:
    archetype = shot.get("archetype", "insert_cutaway")
    constraints = shot.get("provider_constraints", {}) or {}
    allowed = normalize_str_list(constraints.get("allowed_providers"))
    banned = set(normalize_str_list(constraints.get("banned_providers")))
    if allowed:
        chain = [provider for provider in allowed if provider not in banned]
    else:
        chain = [provider for provider in spec.routing.route_matrix.get(archetype, spec.providers.preferred_c_pool) if provider not in banned]
        if constraints.get("preferred_first_tier"):
            first_tier = [provider for provider in spec.benchmark.must_test if provider in chain]
            remainder = [provider for provider in chain if provider not in first_tier]
            chain = first_tier + remainder
    return chain


def stage_judge(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    jobs_path = ctx.root / "workspace" / "jobs" / f"{ctx.run_id}__generation_jobs.json"
    routed_jobs: list[dict[str, Any]] = []
    if jobs_path.exists():
        routed_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    job_index = {job["job_id"]: job for job in routed_jobs}

    candidate_dir = ctx.root / "workspace" / "candidates"
    candidates = sorted(candidate_dir.glob(f"{ctx.run_id}__*.json"))
    judge_entries: list[dict[str, Any]] = []
    skipped_candidates: list[dict[str, Any]] = []
    heuristic_scored_count = 0
    media_gate_blocked_count = 0
    media_gate_warn_review_count = 0
    for candidate_path in candidates:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        candidate_status = candidate.get("status")
        if candidate_status not in JUDGE_READY_CANDIDATE_STATUSES and candidate_status != "media_gate_failed":
            skipped_candidates.append(
                {
                    "candidate_clip_id": candidate["candidate_clip_id"],
                    "shot_id": candidate["shot_id"],
                    "provider": candidate["provider"],
                    "reason": f"candidate_status:{candidate_status}",
                }
            )
            continue
        job = job_index.get(candidate["job_id"], {})
        if candidate_status == "media_gate_failed":
            evaluation = {
                "metrics": {},
                "weighted_total_score": 0.0,
                "decision": "regenerate_same_provider",
                "route_back_stage": "generate",
                "hard_fail": True,
                "hard_fail_reasons": [],
            }
        else:
            evaluation = evaluate_candidate(candidate["provider"], job.get("archetype", "insert_cutaway"), job.get("grade", "B"))
            heuristic_scored_count += 1
        evaluation = apply_media_gate_decision(candidate, evaluation)
        if evaluation["hard_fail"]:
            media_gate_blocked_count += 1
        if evaluation.get("media_gate_status") == "warn" and evaluation["decision"] == "review":
            media_gate_warn_review_count += 1
        judge_score_id = f"judge_{uuid4().hex[:12]}"
        entry = {
            "judge_score_id": judge_score_id,
            "candidate_clip_id": candidate["candidate_clip_id"],
            "shot_id": candidate["shot_id"],
            "provider": candidate["provider"],
            "grade": job.get("grade", "B"),
            **evaluation,
            "judge_model": "heuristic_judge_v0",
            "judge_prompt_version": "v0",
            "created_at": now_iso(),
        }
        judge_entries.append(entry)
        upsert_judge_score(
            ctx.conn,
            judge_score_id=judge_score_id,
            candidate_clip_id=entry["candidate_clip_id"],
            shot_id=entry["shot_id"],
            provider=entry["provider"],
            grade=entry["grade"],
            weighted_total_score=entry["weighted_total_score"],
            decision=entry["decision"],
            hard_fail=entry["hard_fail"],
            hard_fail_reasons=json.dumps(entry["hard_fail_reasons"], ensure_ascii=False),
            route_back_stage=entry["route_back_stage"],
            judge_model=entry["judge_model"],
            judge_prompt_version=entry["judge_prompt_version"],
            created_at=entry["created_at"],
        )

    summary = {
        "judge_id": f"judge_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "judge_scores": judge_entries,
        "skipped_candidates": skipped_candidates,
        "heuristic_scored_count": heuristic_scored_count,
        "media_gate_blocked_count": media_gate_blocked_count,
        "media_gate_warn_review_count": media_gate_warn_review_count,
        "note": (
            "Applied media gate decisions and computed heuristic judge scores for eligible candidates."
            if heuristic_scored_count
            else "Applied media gate decisions; no judge-ready candidates advanced to heuristic scoring."
            if media_gate_blocked_count
            else "No judge-ready candidates were available for this run."
        ),
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "review" / f"{ctx.run_id}__judge_scores.json"
    write_json(out, summary)
    ctx.record_artifact(path=out, artifact_type="judge_report", source_stage=Stage.JUDGE.value)
    return StageResult(note=summary["note"], artifacts=[out], metadata={"judge_count": len(judge_entries)})


def stage_review(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    judge_path = ctx.root / "workspace" / "review" / f"{ctx.run_id}__judge_scores.json"
    if not judge_path.exists():
        payload = {
            "review_id": f"review_{uuid4().hex[:12]}",
            "run_id": ctx.run_id,
            "review_candidates": [],
            "regenerate_candidates": [],
            "approved_candidates": [],
            "note": "Review stage found no judge report for this run.",
            "created_at": now_iso(),
        }
        out = ctx.root / "workspace" / "review" / f"{ctx.run_id}__review_summary.json"
        write_json(out, payload)
        ctx.record_artifact(path=out, artifact_type="review_report", source_stage=Stage.REVIEW.value)
        return StageResult(note=payload["note"], artifacts=[out], metadata=payload)

    judge_payload = json.loads(judge_path.read_text(encoding="utf-8"))
    judge_scores = judge_payload.get("judge_scores", [])
    shot_plan_path = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__shot_plan.json"
    shot_specs: list[dict[str, Any]] = []
    if shot_plan_path.exists():
        shot_specs = json.loads(shot_plan_path.read_text(encoding="utf-8")).get("shot_specs", [])

    candidate_dir = ctx.root / "workspace" / "candidates"
    candidate_index: dict[str, dict[str, Any]] = {}
    for candidate_path in sorted(candidate_dir.glob(f"{ctx.run_id}__*.json")):
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        candidate_index[candidate["candidate_clip_id"]] = candidate

    review_candidates: list[dict[str, Any]] = []
    regenerate_candidates: list[dict[str, Any]] = []
    approved_candidates: list[dict[str, Any]] = []

    for entry in judge_scores:
        candidate = candidate_index.get(entry["candidate_clip_id"], {})
        record = {
            "candidate_clip_id": entry["candidate_clip_id"],
            "shot_id": entry["shot_id"],
            "provider": entry["provider"],
            "grade": entry.get("grade"),
            "decision": entry.get("decision"),
            "route_back_stage": entry.get("route_back_stage"),
            "hard_fail": entry.get("hard_fail", False),
            "hard_fail_reasons": entry.get("hard_fail_reasons", []),
            "decision_reasons": entry.get("decision_reasons", []),
            "media_gate_status": entry.get("media_gate_status"),
            "weighted_total_score": entry.get("weighted_total_score"),
            "candidate_status": candidate.get("status"),
            "planned_provider": candidate.get("planned_provider"),
            "source_type": candidate.get("source_type"),
            "media_artifact_path": candidate.get("media_artifact_path"),
        }
        if entry.get("decision") == "review" or entry.get("route_back_stage") == "review":
            review_candidates.append(record)
        elif entry.get("decision") == "regenerate_same_provider" or entry.get("route_back_stage") == "generate":
            regenerate_candidates.append(record)
        else:
            approved_candidates.append(record)

    continuity_report = build_continuity_report(
        root=ctx.root,
        run_id=ctx.run_id,
        shot_specs=shot_specs,
        review_records=review_candidates + regenerate_candidates + approved_candidates,
    )
    continuity_issue_index = build_continuity_issue_index(continuity_report)

    def apply_continuity_review_policy(record: dict[str, Any]) -> dict[str, Any]:
        shot_id = str(record["shot_id"])
        shot_issues = list(continuity_issue_index.get(shot_id, []))
        sequence_id = next((str(shot.get("sequence_id") or "") for shot in shot_specs if str(shot.get("shot_id")) == shot_id), "")
        character_ids = []
        for shot in shot_specs:
            if str(shot.get("shot_id")) != shot_id:
                continue
            continuity = shot.get("continuity", {}) or {}
            character_ids = normalize_str_list(continuity.get("character_ids"))
            break
        for issue in continuity_issue_index.get(sequence_id, []):
            if issue not in shot_issues:
                shot_issues.append(issue)
        for character_id in character_ids:
            for issue in continuity_issue_index.get(character_id, []):
                if issue not in shot_issues:
                    shot_issues.append(issue)

        if not shot_issues:
            return record

        issue_types = sorted({str(issue.get("issue_type")) for issue in shot_issues})
        decision_reasons = list(record.get("decision_reasons", []))
        decision_reasons.extend(f"continuity_issue:{issue_type}" for issue_type in issue_types)
        record["decision_reasons"] = decision_reasons
        record["continuity_issue_types"] = issue_types
        record["continuity_issue_count"] = len(shot_issues)

        severe_types = {
            "character_provider_mixture",
            "sequence_provider_mixture",
            "visual_character_similarity_low",
            "visual_sequence_similarity_low",
        }
        if any(issue_type in severe_types for issue_type in issue_types):
            record["decision"] = "review"
            record["route_back_stage"] = "review"
        if len(shot_issues) >= 4 and not record.get("hard_fail", False):
            record["decision"] = "regenerate_same_provider"
            record["route_back_stage"] = "generate"
            record["hard_fail"] = True
            hard_fail_reasons = list(record.get("hard_fail_reasons", []))
            hard_fail_reasons.append("continuity_issue_threshold")
            record["hard_fail_reasons"] = hard_fail_reasons
        return record

    review_candidates = [apply_continuity_review_policy(dict(item)) for item in review_candidates]
    regenerate_candidates = [apply_continuity_review_policy(dict(item)) for item in regenerate_candidates]
    approved_candidates = [apply_continuity_review_policy(dict(item)) for item in approved_candidates]

    review_candidates.extend([item for item in approved_candidates if item.get("decision") == "review"])
    regenerate_candidates.extend([item for item in approved_candidates if item.get("decision") == "regenerate_same_provider"])
    approved_candidates = [
        item
        for item in approved_candidates
        if item.get("decision") not in {"review", "regenerate_same_provider"}
    ]
    gate_status = "approved"
    gate_summary = "No manual review queue was created."
    if review_candidates:
        gate_status = "waiting"
        gate_summary = f"{len(review_candidates)} candidates require manual review."
    gate_payload = {
        "review_candidate_ids": [item["candidate_clip_id"] for item in review_candidates],
        "regenerate_candidate_ids": [item["candidate_clip_id"] for item in regenerate_candidates],
        "approved_candidate_ids": [item["candidate_clip_id"] for item in approved_candidates],
    }
    if spec.workflow.enable_human_gates:
        timestamp = now_iso()
        upsert_human_gate(
            ctx.conn,
            gate_id=f"{ctx.run_id}__gate_3_review",
            run_id=ctx.run_id,
            gate_name="gate_3_review",
            status=gate_status,
            reviewer=None,
            decision_summary=gate_summary,
            decision_payload=json.dumps(gate_payload, ensure_ascii=False),
            created_at=timestamp,
            updated_at=timestamp,
        )

    payload = {
        "review_id": f"review_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "review_candidates": review_candidates,
        "regenerate_candidates": regenerate_candidates,
        "approved_candidates": approved_candidates,
        "gate": {
            "gate_name": "gate_3_review",
            "status": gate_status,
            "summary": gate_summary,
            "enabled": spec.workflow.enable_human_gates,
        },
        "counts": {
            "review": len(review_candidates),
            "regenerate": len(regenerate_candidates),
            "approved": len(approved_candidates),
        },
        "note": (
            f"Prepared review queue for {len(review_candidates)} candidates and flagged {len(regenerate_candidates)} for regenerate."
            if review_candidates or regenerate_candidates
            else "No manual review or regenerate actions were needed for this run."
        ),
        "created_at": now_iso(),
    }
    payload["continuity_summary"] = {
        "issue_count": continuity_report["counts"]["issues"],
        "sequence_count": continuity_report["counts"]["sequences"],
        "character_count": continuity_report["counts"]["characters"],
        "visual_issue_count": continuity_report["counts"]["visual_issues"],
        "visual_skipped_shots": continuity_report["counts"]["visual_skipped_shots"],
        "top_issue_types": sorted({issue["issue_type"] for issue in continuity_report["issues"]}),
    }
    out = ctx.root / "workspace" / "review" / f"{ctx.run_id}__review_summary.json"
    continuity_out = ctx.root / "workspace" / "review" / f"{ctx.run_id}__continuity_report.json"
    write_json(out, payload)
    write_json(continuity_out, continuity_report)
    ctx.record_artifact(path=out, artifact_type="review_report", source_stage=Stage.REVIEW.value)
    ctx.record_artifact(path=continuity_out, artifact_type="continuity_report", source_stage=Stage.REVIEW.value)
    return StageResult(
        note=payload["note"],
        artifacts=[out, continuity_out],
        metadata={
            "review_count": len(review_candidates),
            "regenerate_count": len(regenerate_candidates),
            "approved_count": len(approved_candidates),
            "gate_status": gate_status,
            "continuity_issue_count": continuity_report["counts"]["issues"],
        },
    )


def stage_post(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    approved_candidates_file = spec.planning.approved_candidates_file
    approved_candidates: list[dict[str, Any]] = []
    pending_review_candidates: list[dict[str, Any]] = []
    regenerate_candidates: list[dict[str, Any]] = []
    source_review_gate: dict[str, Any] | None = None

    if approved_candidates_file:
        source_path = Path(approved_candidates_file)
        if not source_path.is_absolute():
            source_path = ctx.root / source_path
        if source_path.exists():
            payload = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
            approved_candidates = payload.get("approved_candidates", []) or []
            source_review_gate = payload.get("source_review_gate")
    else:
        review_path = ctx.root / "workspace" / "review" / f"{ctx.run_id}__review_summary.json"
        if review_path.exists():
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            pending_review_candidates = review_payload.get("review_candidates", []) or []
            regenerate_candidates = review_payload.get("regenerate_candidates", []) or []
            approved_candidates = review_payload.get("approved_candidates", []) or []
            source_review_gate = review_payload.get("gate")

    ffmpeg_path = shutil.which("ffmpeg")
    requested_template = spec.post.processing_template
    processing_mode = requested_template if ffmpeg_path else f"file_copy_fallback:{requested_template}"
    processed_dir = ctx.root / "workspace" / "post" / "processed" / ctx.run_id
    processed_dir.mkdir(parents=True, exist_ok=True)

    post_candidates: list[dict[str, Any]] = []
    post_jobs: list[dict[str, Any]] = []
    post_blocked_items: list[dict[str, Any]] = []
    for index, item in enumerate(sorted(approved_candidates, key=lambda entry: str(entry.get("shot_id") or "")), start=1):
        source_media_path = resolve_existing_file_path(item.get("media_artifact_path"))
        if source_media_path is None:
            post_blocked_items.append(
                {
                    "candidate_clip_id": item["candidate_clip_id"],
                    "shot_id": item["shot_id"],
                    "provider": item.get("provider"),
                    "reason": "missing_source_media",
                    "source_media_artifact_path": str(item.get("media_artifact_path") or ""),
                }
            )
            continue

        processed_filename = f"{index:03d}__{item['shot_id']}__{item['candidate_clip_id']}{source_media_path.suffix}"
        processed_path = processed_dir / processed_filename
        operation = {
            "mode": processing_mode,
            "requested_template": requested_template,
            "source_media_artifact_path": str(source_media_path),
            "processed_media_path": str(processed_path),
            "ffmpeg_path": ffmpeg_path,
        }
        try:
            if ffmpeg_path:
                cmd = build_ffmpeg_post_command(spec, source_media_path, processed_path)
                operation["ffmpeg_command"] = cmd
                result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
                operation["returncode"] = result.returncode
                if result.returncode != 0:
                    operation["stderr"] = result.stderr.strip()[:1000]
                    raise RuntimeError("ffmpeg_post_processing_failed")
            else:
                if not spec.post.fallback_copy_enabled:
                    raise RuntimeError("fallback_copy_disabled")
                shutil.copy2(source_media_path, processed_path)

            processed_probe = probe_media_file(processed_path)
            processed_gate = evaluate_media_gate(processed_probe)
            processed_record = {
                "candidate_clip_id": item["candidate_clip_id"],
                "shot_id": item["shot_id"],
                "provider": item.get("provider"),
                "planned_provider": item.get("planned_provider"),
                "source_type": item.get("source_type"),
                "source_media_artifact_path": str(source_media_path),
                "media_artifact_path": str(processed_path),
                "media_gate_status": item.get("media_gate_status"),
                "weighted_total_score": item.get("weighted_total_score"),
                "post_processing_mode": processing_mode,
                "post_processing_status": "processed",
                "post_processing_template": requested_template,
                "post_processing_details": operation,
                "processed_media_probe": processed_probe,
                "processed_media_gate": processed_gate,
            }
            post_candidates.append(processed_record)
            post_jobs.append(
                {
                    "candidate_clip_id": item["candidate_clip_id"],
                    "shot_id": item["shot_id"],
                    "provider": item.get("provider"),
                    "status": "processed",
                    "processing_mode": processing_mode,
                    "processing_template": requested_template,
                    "processed_media_path": str(processed_path),
                }
            )
            ctx.record_artifact(
                path=processed_path,
                artifact_type="post_processed_media",
                source_stage=Stage.POST.value,
                source_id=item["candidate_clip_id"],
                retention_policy="keep",
            )
            probe_path = processed_path.with_suffix(f"{processed_path.suffix}.probe.json")
            gate_path = processed_path.with_suffix(f"{processed_path.suffix}.gate.json")
            write_json(probe_path, processed_probe)
            write_json(gate_path, processed_gate)
            ctx.record_artifact(
                path=probe_path,
                artifact_type="post_processed_probe",
                source_stage=Stage.POST.value,
                source_id=item["candidate_clip_id"],
                retention_policy="keep",
            )
            ctx.record_artifact(
                path=gate_path,
                artifact_type="post_processed_gate",
                source_stage=Stage.POST.value,
                source_id=item["candidate_clip_id"],
                retention_policy="keep",
            )
        except Exception as exc:  # noqa: BLE001
            post_blocked_items.append(
                {
                    "candidate_clip_id": item["candidate_clip_id"],
                    "shot_id": item["shot_id"],
                    "provider": item.get("provider"),
                    "reason": "post_processing_failed",
                    "source_media_artifact_path": str(source_media_path),
                    "processed_media_path": str(processed_path),
                    "error": str(exc),
                    "processing_mode": processing_mode,
                    "processing_template": requested_template,
                }
            )

    blocked_candidates = [
        {
            "candidate_clip_id": item["candidate_clip_id"],
            "shot_id": item["shot_id"],
            "provider": item.get("provider"),
            "reason": "pending_review",
        }
        for item in pending_review_candidates
    ]
    blocked_candidates.extend(
        {
            "candidate_clip_id": item["candidate_clip_id"],
            "shot_id": item["shot_id"],
            "provider": item.get("provider"),
            "reason": "needs_regenerate",
        }
        for item in regenerate_candidates
    )
    blocked_candidates.extend(post_blocked_items)

    payload = {
        "post_id": f"post_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "post_jobs": post_jobs,
        "post_candidates": post_candidates,
        "blocked_candidates": blocked_candidates,
        "source_review_gate": source_review_gate,
        "processing_mode": processing_mode,
        "processing_template": requested_template,
        "counts": {
            "post_candidates": len(post_candidates),
            "blocked_candidates": len(blocked_candidates),
        },
        "note": (
            f"Prepared post outputs for {len(post_candidates)} approved candidates."
            if post_candidates
            else "Post stage found no approved candidates to continue."
        ),
        "created_at": now_iso(),
    }
    out = ctx.root / "workspace" / "post" / f"{ctx.run_id}__post_summary.json"
    write_json(out, payload)
    ctx.record_artifact(path=out, artifact_type="post_report", source_stage=Stage.POST.value)
    return StageResult(
        note=payload["note"],
        artifacts=[out],
        metadata={
            "post_candidate_count": len(post_candidates),
            "blocked_candidate_count": len(blocked_candidates),
        },
    )


def stage_assemble(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    post_path = ctx.root / "workspace" / "post" / f"{ctx.run_id}__post_summary.json"
    if not post_path.exists():
        payload = {
            "assemble_id": f"assemble_{uuid4().hex[:12]}",
            "run_id": ctx.run_id,
            "timeline_items": [],
            "delivery_items": [],
            "blocked_items": [],
            "note": "Assemble stage found no post summary for this run.",
            "created_at": now_iso(),
        }
        out = ctx.root / "workspace" / "assemble" / f"{ctx.run_id}__assembly_summary.json"
        write_json(out, payload)
        ctx.record_artifact(path=out, artifact_type="assemble_report", source_stage=Stage.ASSEMBLE.value)
        return StageResult(note=payload["note"], artifacts=[out], metadata=payload)

    post_payload = json.loads(post_path.read_text(encoding="utf-8"))
    post_candidates = post_payload.get("post_candidates", []) or []
    blocked_candidates = list(post_payload.get("blocked_candidates", []) or [])

    timeline_items: list[dict[str, Any]] = []
    delivery_items: list[dict[str, Any]] = []
    missing_media_items: list[dict[str, Any]] = []
    sorted_candidates = sorted(post_candidates, key=lambda item: str(item.get("shot_id") or ""))
    for index, item in enumerate(sorted_candidates, start=1):
        media_path = Path(str(item.get("media_artifact_path") or ""))
        timeline_item = {
            "sequence_index": index,
            "shot_id": item.get("shot_id"),
            "candidate_clip_id": item.get("candidate_clip_id"),
            "provider": item.get("provider"),
            "planned_provider": item.get("planned_provider"),
            "media_artifact_path": str(media_path) if media_path else None,
            "media_exists": bool(media_path and media_path.exists()),
            "media_gate_status": item.get("media_gate_status"),
            "weighted_total_score": item.get("weighted_total_score"),
        }
        timeline_items.append(timeline_item)

        if not media_path or not media_path.exists():
            missing_media_items.append(
                {
                    "candidate_clip_id": item.get("candidate_clip_id"),
                    "shot_id": item.get("shot_id"),
                    "provider": item.get("provider"),
                    "reason": "missing_media_artifact",
                }
            )
            continue

        delivery_items.append(
            {
                "sequence_index": index,
                "candidate_clip_id": item.get("candidate_clip_id"),
                "shot_id": item.get("shot_id"),
                "delivery_filename": f"{index:03d}__{item.get('shot_id')}__{item.get('candidate_clip_id')}{media_path.suffix}",
                "source_media_path": str(media_path),
                "provider": item.get("provider"),
                "planned_provider": item.get("planned_provider"),
                "media_gate_status": item.get("media_gate_status"),
                "weighted_total_score": item.get("weighted_total_score"),
            }
        )

    blocked_items = blocked_candidates + missing_media_items
    timeline_manifest = {
        "assemble_id": f"timeline_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "timeline_items": timeline_items,
        "created_at": now_iso(),
    }
    delivery_manifest = {
        "delivery_manifest_id": f"delivery_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "source_post_summary": str(post_path),
        "source_review_gate": post_payload.get("source_review_gate"),
        "delivery_items": delivery_items,
        "blocked_items": blocked_items,
        "created_at": now_iso(),
    }
    summary = {
        "assemble_id": f"assemble_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "timeline_items": timeline_items,
        "delivery_items": delivery_items,
        "blocked_items": blocked_items,
        "counts": {
            "timeline_items": len(timeline_items),
            "delivery_items": len(delivery_items),
            "blocked_items": len(blocked_items),
        },
        "note": (
            f"Prepared assemble timeline for {len(delivery_items)} deliverable candidates."
            if delivery_items
            else "Assemble stage found no deliverable candidates."
        ),
        "created_at": now_iso(),
    }

    assemble_dir = ctx.root / "workspace" / "assemble"
    timeline_path = assemble_dir / f"{ctx.run_id}__timeline_manifest.json"
    delivery_path = assemble_dir / f"{ctx.run_id}__delivery_manifest.json"
    summary_path = assemble_dir / f"{ctx.run_id}__assembly_summary.json"
    write_json(timeline_path, timeline_manifest)
    write_json(delivery_path, delivery_manifest)
    write_json(summary_path, summary)
    ctx.record_artifact(path=timeline_path, artifact_type="timeline_manifest", source_stage=Stage.ASSEMBLE.value)
    ctx.record_artifact(path=delivery_path, artifact_type="delivery_manifest", source_stage=Stage.ASSEMBLE.value)
    ctx.record_artifact(path=summary_path, artifact_type="assemble_report", source_stage=Stage.ASSEMBLE.value)
    return StageResult(
        note=summary["note"],
        artifacts=[timeline_path, delivery_path, summary_path],
        metadata=summary["counts"],
    )


def stage_report(ctx: RunContext, spec: ProjectSpec) -> StageResult:
    assemble_dir = ctx.root / "workspace" / "assemble"
    summary_path = assemble_dir / f"{ctx.run_id}__assembly_summary.json"
    delivery_path = assemble_dir / f"{ctx.run_id}__delivery_manifest.json"
    timeline_path = assemble_dir / f"{ctx.run_id}__timeline_manifest.json"
    post_path = ctx.root / "workspace" / "post" / f"{ctx.run_id}__post_summary.json"
    continuity_path = ctx.root / "workspace" / "review" / f"{ctx.run_id}__continuity_report.json"

    if not summary_path.exists() or not delivery_path.exists():
        payload = {
            "report_id": f"report_{uuid4().hex[:12]}",
            "run_id": ctx.run_id,
            "deliverables": [],
            "blocked_items": [],
            "gates": [row_to_dict(row) for row in fetch_human_gates(ctx.conn, ctx.run_id)],
            "note": "Report stage found no assemble outputs for this run.",
            "created_at": now_iso(),
        }
        out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__delivery_report.json"
        write_json(out, payload)
        ctx.record_artifact(path=out, artifact_type="delivery_report", source_stage=Stage.REPORT.value)
        return StageResult(note=payload["note"], artifacts=[out], metadata=payload)

    assemble_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    delivery_manifest = json.loads(delivery_path.read_text(encoding="utf-8"))
    timeline_manifest = json.loads(timeline_path.read_text(encoding="utf-8")) if timeline_path.exists() else {"timeline_items": []}
    post_summary = json.loads(post_path.read_text(encoding="utf-8")) if post_path.exists() else {}
    continuity_summary = json.loads(continuity_path.read_text(encoding="utf-8")) if continuity_path.exists() else {}
    gates = [row_to_dict(row) for row in fetch_human_gates(ctx.conn, ctx.run_id)]

    deliverables = delivery_manifest.get("delivery_items", []) or []
    blocked_items = delivery_manifest.get("blocked_items", []) or []
    source_review_gate = delivery_manifest.get("source_review_gate")
    payload = {
        "report_id": f"report_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "source_post_summary": str(post_path) if post_path.exists() else None,
        "source_assembly_summary": str(summary_path),
        "source_delivery_manifest": str(delivery_path),
        "source_timeline_manifest": str(timeline_path) if timeline_path.exists() else None,
        "source_continuity_report": str(continuity_path) if continuity_path.exists() else None,
        "source_review_gate": source_review_gate,
        "gates": gates,
        "counts": {
            "deliverables": len(deliverables),
            "blocked_items": len(blocked_items),
            "timeline_items": len(timeline_manifest.get("timeline_items", [])),
            "post_candidates": len(post_summary.get("post_candidates", []) or []),
            "continuity_issues": len(continuity_summary.get("issues", []) or []),
            "visual_continuity_issues": len(((continuity_summary.get("visual_checks") or {}).get("issues") or [])),
        },
        "continuity_summary": continuity_summary.get("counts"),
        "deliverables": deliverables,
        "blocked_items": blocked_items,
        "next_actions": (
            ["Proceed to export/release packaging."]
            if deliverables and not blocked_items
            else ["Resolve blocked items before packaging."]
            if blocked_items
            else ["No deliverables were prepared for this run."]
        ),
        "note": (
            f"Prepared delivery report for {len(deliverables)} deliverables."
            if deliverables
            else "Prepared delivery report with no deliverables."
        ),
        "created_at": now_iso(),
    }

    lines = [
        "# Delivery Report",
        "",
        f"- Run ID: `{ctx.run_id}`",
        f"- Deliverables: `{len(deliverables)}`",
        f"- Blocked Items: `{len(blocked_items)}`",
        f"- Timeline Items: `{len(timeline_manifest.get('timeline_items', []))}`",
        f"- Continuity Issues: `{len(continuity_summary.get('issues', []) or [])}`",
    ]
    if source_review_gate:
        lines.append(f"- Source Review Gate: `{source_review_gate.get('gate_name')}` / `{source_review_gate.get('status')}`")
    if payload["next_actions"]:
        lines.append("")
        lines.append("## Next Actions")
        for item in payload["next_actions"]:
            lines.append(f"- {item}")
    if deliverables:
        lines.append("")
        lines.append("## Deliverables")
        for item in deliverables:
            lines.append(
                f"- `{item.get('delivery_filename')}` from `{item.get('shot_id')}` via `{item.get('provider')}` "
                f"(score={item.get('weighted_total_score')}, gate={item.get('media_gate_status')})"
            )
    if blocked_items:
        lines.append("")
        lines.append("## Blocked Items")
        for item in blocked_items:
            lines.append(
                f"- `{item.get('shot_id')}` / `{item.get('candidate_clip_id')}` reason=`{item.get('reason')}`"
            )
    markdown = "\n".join(lines) + "\n"

    json_out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__delivery_report.json"
    md_out = ctx.root / "workspace" / "reports" / f"{ctx.run_id}__delivery_report.md"
    write_json(json_out, payload)
    md_out.write_text(markdown, encoding="utf-8")

    release_version = compute_next_release_version(ctx.root, spec.project.id)
    release_name = f"{spec.project.id}__{release_version}__{ctx.run_id}"
    release_dir = ctx.root / "workspace" / "release" / release_name
    release_media_dir = release_dir / "media"
    release_docs_dir = release_dir / "docs"
    release_media_dir.mkdir(parents=True, exist_ok=True)
    release_docs_dir.mkdir(parents=True, exist_ok=True)

    exported_media: list[dict[str, Any]] = []
    export_blocked_items: list[dict[str, Any]] = []
    for item in deliverables:
        source_media_path = Path(str(item.get("source_media_path") or ""))
        destination = release_media_dir / str(item.get("delivery_filename") or source_media_path.name)
        if not source_media_path.exists():
            export_blocked_items.append(
                {
                    "candidate_clip_id": item.get("candidate_clip_id"),
                    "shot_id": item.get("shot_id"),
                    "reason": "missing_source_media",
                    "source_media_path": str(source_media_path),
                }
            )
            continue
        try:
            shutil.copy2(source_media_path, destination)
            exported_media.append(
                {
                    "candidate_clip_id": item.get("candidate_clip_id"),
                    "shot_id": item.get("shot_id"),
                    "provider": item.get("provider"),
                    "delivery_filename": destination.name,
                    "source_media_path": str(source_media_path),
                    "exported_media_path": str(destination),
                    "file_size_bytes": destination.stat().st_size,
                }
            )
        except Exception as exc:  # noqa: BLE001
            export_blocked_items.append(
                {
                    "candidate_clip_id": item.get("candidate_clip_id"),
                    "shot_id": item.get("shot_id"),
                    "reason": "export_copy_failed",
                    "source_media_path": str(source_media_path),
                    "error": str(exc),
                }
            )

    copied_docs: list[dict[str, Any]] = []
    for source in [json_out, md_out, summary_path, delivery_path, timeline_path, post_path, continuity_path]:
        if source is None or not Path(source).exists():
            continue
        source_path = Path(source)
        destination = release_docs_dir / source_path.name
        shutil.copy2(source_path, destination)
        copied_docs.append(
            {
                "source_path": str(source_path),
                "exported_path": str(destination),
            }
        )

    release_manifest = {
        "release_manifest_id": f"release_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "release_dir": str(release_dir),
        "exported_media": exported_media,
        "copied_docs": copied_docs,
        "blocked_items": blocked_items + export_blocked_items,
        "counts": {
            "exported_media": len(exported_media),
            "copied_docs": len(copied_docs),
            "blocked_items": len(blocked_items) + len(export_blocked_items),
        },
        "created_at": now_iso(),
    }
    release_manifest_path = release_dir / "release_manifest.json"
    write_json(release_manifest_path, release_manifest)
    checksum_entries: list[dict[str, Any]] = []
    for path in sorted(p for p in release_dir.rglob("*") if p.is_file()):
        checksum_entries.append(
            {
                "relative_path": str(path.relative_to(release_dir)).replace("\\", "/"),
                "absolute_path": str(path),
                "sha256": sha256_file(path),
                "file_size_bytes": path.stat().st_size,
            }
        )
    checksums_manifest = {
        "checksums_manifest_id": f"checksums_{uuid4().hex[:12]}",
        "run_id": ctx.run_id,
        "release_dir": str(release_dir),
        "release_name": release_name,
        "release_version": release_version,
        "entries": checksum_entries,
        "created_at": now_iso(),
    }
    checksums_manifest_path = ctx.root / "workspace" / "release" / f"{release_name}__checksums.json"
    write_json(checksums_manifest_path, checksums_manifest)
    checksums_txt_path = ctx.root / "workspace" / "release" / f"{release_name}.sha256"
    checksums_lines = [f"{entry['sha256']} *{entry['relative_path']}" for entry in checksum_entries]
    checksums_txt_path.write_text("\n".join(checksums_lines) + ("\n" if checksums_lines else ""), encoding="utf-8")

    zip_path = ctx.root / "workspace" / "release" / f"{release_name}.zip"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in release_dir.rglob("*") if p.is_file()):
            arcname = f"{release_name}/{str(path.relative_to(release_dir)).replace('\\', '/')}"
            archive.write(path, arcname=arcname)
    zip_sha256 = sha256_file(zip_path)
    payload["release_export"] = {
        "release_name": release_name,
        "release_version": release_version,
        "release_dir": str(release_dir),
        "exported_media_count": len(exported_media),
        "copied_docs_count": len(copied_docs),
        "blocked_items_count": len(blocked_items) + len(export_blocked_items),
        "release_manifest_path": str(release_manifest_path),
        "checksums_manifest_path": str(checksums_manifest_path),
        "checksums_text_path": str(checksums_txt_path),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha256,
    }
    payload["next_actions"] = (
        [f"Review exported release directory: {release_dir}", f"Validate checksums via {checksums_manifest_path}", f"Use text checksums: {checksums_txt_path}", f"Distribute archive: {zip_path}"]
        if exported_media and not (blocked_items or export_blocked_items)
        else [f"Review partial export in: {release_dir}", f"Inspect checksum manifest: {checksums_manifest_path}", f"Inspect text checksums: {checksums_txt_path}", "Resolve blocked export items before delivery."]
        if exported_media
        else ["No media was exported; resolve blocked items first."]
    )
    payload["blocked_items"] = blocked_items + export_blocked_items
    payload["note"] = (
        f"Prepared delivery report and exported {len(exported_media)} deliverables."
        if exported_media
        else "Prepared delivery report with no exported deliverables."
    )
    write_json(json_out, payload)
    md_lines = markdown.rstrip().splitlines()
    md_lines.extend(
        [
            "",
            "## Release Export",
            f"- Release Name: `{release_name}`",
            f"- Release Version: `{release_version}`",
            f"- Release Dir: `{release_dir}`",
            f"- Exported Media: `{len(exported_media)}`",
            f"- Copied Docs: `{len(copied_docs)}`",
            f"- Blocked Export Items: `{len(blocked_items) + len(export_blocked_items)}`",
            f"- Checksum Manifest: `{checksums_manifest_path}`",
            f"- Checksum Text: `{checksums_txt_path}`",
            f"- Zip Archive: `{zip_path}`",
            f"- Zip SHA256: `{zip_sha256}`",
        ]
    )
    md_out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    ctx.record_artifact(path=json_out, artifact_type="delivery_report", source_stage=Stage.REPORT.value)
    ctx.record_artifact(path=md_out, artifact_type="delivery_report_markdown", source_stage=Stage.REPORT.value)
    ctx.record_artifact(path=release_manifest_path, artifact_type="release_manifest", source_stage=Stage.REPORT.value)
    ctx.record_artifact(path=checksums_manifest_path, artifact_type="release_checksums", source_stage=Stage.REPORT.value)
    ctx.record_artifact(path=checksums_txt_path, artifact_type="release_checksums_text", source_stage=Stage.REPORT.value)
    ctx.record_artifact(path=zip_path, artifact_type="release_zip_archive", source_stage=Stage.REPORT.value)
    for item in exported_media:
        exported_path = Path(item["exported_media_path"])
        ctx.record_artifact(
            path=exported_path,
            artifact_type="release_media",
            source_stage=Stage.REPORT.value,
            source_id=item.get("candidate_clip_id"),
            retention_policy="keep",
        )
    for item in copied_docs:
        exported_path = Path(item["exported_path"])
        ctx.record_artifact(
            path=exported_path,
            artifact_type="release_doc",
            source_stage=Stage.REPORT.value,
            retention_policy="keep",
        )
    return StageResult(
        note=payload["note"],
        artifacts=[json_out, md_out, release_manifest_path],
        metadata={
            **payload["counts"],
            **payload["release_export"],
        },
    )


STAGE_HANDLERS = {
    Stage.INGEST: stage_ingest,
    Stage.ANALYZE: stage_analyze,
    Stage.BIBLES: stage_bibles,
    Stage.BENCHMARK: stage_benchmark,
    Stage.PLAN: stage_plan,
    Stage.COMPILE_PROMPTS: stage_compile_prompts,
    Stage.ROUTE: stage_route,
    Stage.GENERATE: stage_generate,
    Stage.JUDGE: stage_judge,
    Stage.REVIEW: stage_review,
    Stage.POST: stage_post,
    Stage.ASSEMBLE: stage_assemble,
    Stage.REPORT: stage_report,
}


def execute_stage(ctx: RunContext, spec: ProjectSpec, stage: Stage, project_file: Path) -> StageResult:
    handler = STAGE_HANDLERS.get(stage)
    if handler is None:
        return stage_noop(ctx, spec, stage)
    if stage == Stage.INGEST:
        return handler(ctx, spec, project_file)
    return handler(ctx, spec)

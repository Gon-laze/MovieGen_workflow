from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from .models import ProjectSpec

TERMINAL_PROVIDER_STATES = {"completed", "failed", "downloaded", "not_configured", "unsupported_provider", "http_error", "request_failed"}
COMPLETED_PROVIDER_STATES = {"completed", "succeeded", "success", "done", "finished", "ready"}
PENDING_PROVIDER_STATES = {"queued", "pending", "submitted", "running", "processing", "in_progress"}
FAILED_PROVIDER_STATES = {"failed", "error", "canceled", "cancelled", "timed_out", "timeout"}


def parse_json_payload(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith(("{", "[")):
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {"data": parsed}
    return {"raw": raw}


def normalize_provider_state(value: Any) -> str:
    if value is None:
        return "unknown"
    lowered = str(value).strip().lower()
    if lowered in COMPLETED_PROVIDER_STATES:
        return "completed"
    if lowered in PENDING_PROVIDER_STATES:
        return "processing"
    if lowered in FAILED_PROVIDER_STATES:
        return "failed"
    return lowered or "unknown"


def dig_first_string(payload: Any, candidate_keys: set[str]) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in candidate_keys and isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = dig_first_string(value, candidate_keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = dig_first_string(item, candidate_keys)
            if found:
                return found
    return None


def infer_media_extension(download_url: str | None) -> str:
    if not download_url:
        return ".mp4"
    parsed = parse.urlparse(download_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv", ".json", ".bin"}:
        return suffix
    return ".mp4"


def open_url(req_or_url: Any, timeout_sec: int) -> Any:
    url = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
    hostname = parse.urlparse(url).hostname
    if hostname in {"127.0.0.1", "localhost"}:
        opener = request.build_opener(request.ProxyHandler({}))
        return opener.open(req_or_url, timeout=timeout_sec)
    return request.urlopen(req_or_url, timeout=timeout_sec)


@dataclass
class ProviderAdapter:
    provider_name: str
    live_mode: bool = False
    timeout_sec: int = 60

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "url": None,
            "headers": {},
            "body": payload,
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = self.build_request(payload)
        return {
            "provider": self.provider_name,
            "mode": "live" if self.live_mode else "mock",
            "status": "queued",
            "external_job_id": None,
            "request": request_payload,
            "submitted_payload_keys": sorted(payload.keys()),
        }

    def build_poll_request(self, external_job_id: str) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "url": None,
            "headers": {},
            "external_job_id": external_job_id,
        }

    def poll(self, external_job_id: str) -> dict[str, Any]:
        poll_request = self.build_poll_request(external_job_id)
        if not self.live_mode:
            return {
                "provider": self.provider_name,
                "mode": "mock",
                "status": "completed",
                "external_job_id": external_job_id,
                "request": poll_request,
                "response": {"status": "completed"},
                "asset_url": None,
            }
        return {
            "provider": self.provider_name,
            "mode": "live",
            "status": "unsupported_provider",
            "external_job_id": external_job_id,
            "request": poll_request,
            "error": f"Live polling is not implemented for provider '{self.provider_name}'",
        }

    def download(self, download_url: str | None, destination: Path) -> dict[str, Any]:
        if not self.live_mode:
            return {
                "provider": self.provider_name,
                "mode": "mock",
                "status": "downloaded",
                "download_url": download_url,
                "media_path": str(destination),
                "byte_count": 0,
            }
        return {
            "provider": self.provider_name,
            "mode": "live",
            "status": "unsupported_provider",
            "download_url": download_url,
            "media_path": str(destination),
            "error": f"Live download is not implemented for provider '{self.provider_name}'",
        }


@dataclass
class HTTPVideoProviderAdapter(ProviderAdapter):
    env_prefix: str = "MOVIEGEN_GENERIC"

    def _auth_header(self) -> str:
        return f"Bearer {os.getenv(f'{self.env_prefix}_TOKEN', '')}".strip()

    def _json_request(
        self,
        *,
        url: str,
        headers: dict[str, str],
        method: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(url, data=encoded, headers=headers, method=method)
        try:
            with open_url(req, self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            return {"ok": True, "parsed": parse_json_payload(raw)}
        except error.HTTPError as exc:
            return {"ok": False, "status": "http_error", "error": f"HTTP {exc.code}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": "request_failed", "error": str(exc)}

    def _extract_external_job_id(self, payload: dict[str, Any]) -> str | None:
        return dig_first_string(payload, {"id", "task_id", "job_id", "request_id"})

    def _extract_poll_state(self, payload: dict[str, Any]) -> str:
        return normalize_provider_state(dig_first_string(payload, {"status", "state", "task_status", "phase"}))

    def _extract_asset_url(self, payload: dict[str, Any]) -> str | None:
        return dig_first_string(payload, {"video_url", "download_url", "asset_url", "result_url", "url", "media_url"})

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model_name": payload.get("provider_model", self.provider_name),
            "prompt": payload.get("prompt_main", ""),
            "duration_sec": payload.get("generation_params", {}).get("duration_sec"),
            "aspect_ratio": payload.get("generation_params", {}).get("aspect_ratio"),
            "native_audio": payload.get("generation_params", {}).get("native_audio", False),
            "image_refs": payload.get("reference_assets", {}).get("image_refs", []),
            "video_refs": payload.get("reference_assets", {}).get("video_refs", []),
            "shot_id": payload.get("shot_id"),
            "packet_id": payload.get("packet_id"),
        }
        return {
            "provider": self.provider_name,
            "url": os.getenv(f"{self.env_prefix}_SUBMIT_URL"),
            "headers": {
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            "body": body,
        }

    def build_poll_request(self, external_job_id: str) -> dict[str, Any]:
        template = os.getenv(f"{self.env_prefix}_POLL_URL_TEMPLATE")
        url = template.format(job_id=external_job_id) if template else None
        return {
            "provider": self.provider_name,
            "url": url,
            "headers": {
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            "external_job_id": external_job_id,
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = self.build_request(payload)
        if not self.live_mode:
            return super().submit(payload)
        url = request_payload["url"]
        auth = request_payload["headers"].get("Authorization", "")
        if not url or not auth or auth == "Bearer":
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "not_configured",
                "external_job_id": None,
                "request": request_payload,
                "error": f"{self.env_prefix}_SUBMIT_URL or {self.env_prefix}_TOKEN is missing",
            }
        result = self._json_request(url=url, headers=request_payload["headers"], method="POST", body=request_payload["body"])
        if not result["ok"]:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": result["status"],
                "external_job_id": None,
                "request": request_payload,
                "error": result["error"],
            }
        parsed = result["parsed"]
        return {
            "provider": self.provider_name,
            "mode": "live",
            "status": "submitted",
            "external_job_id": self._extract_external_job_id(parsed),
            "request": request_payload,
            "response": parsed,
        }

    def poll(self, external_job_id: str) -> dict[str, Any]:
        poll_request = self.build_poll_request(external_job_id)
        if not self.live_mode:
            return super().poll(external_job_id)
        url = poll_request["url"]
        auth = poll_request["headers"].get("Authorization", "")
        if not url or not auth or auth == "Bearer":
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "not_configured",
                "external_job_id": external_job_id,
                "request": poll_request,
                "error": f"{self.env_prefix}_POLL_URL_TEMPLATE or {self.env_prefix}_TOKEN is missing",
            }
        result = self._json_request(url=url, headers=poll_request["headers"], method="GET")
        if not result["ok"]:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": result["status"],
                "external_job_id": external_job_id,
                "request": poll_request,
                "error": result["error"],
            }
        parsed = result["parsed"]
        normalized_status = self._extract_poll_state(parsed)
        return {
            "provider": self.provider_name,
            "mode": "live",
            "status": normalized_status,
            "external_job_id": external_job_id,
            "request": poll_request,
            "response": parsed,
            "asset_url": self._extract_asset_url(parsed),
        }

    def download(self, download_url: str | None, destination: Path) -> dict[str, Any]:
        if not self.live_mode:
            return super().download(download_url, destination)
        if not download_url:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "no_asset_url",
                "download_url": download_url,
                "media_path": str(destination),
                "error": "Provider poll response did not include a downloadable asset URL",
            }
        destination.parent.mkdir(parents=True, exist_ok=True)
        parsed = parse.urlparse(download_url)
        try:
            if parsed.scheme in {"http", "https"}:
                with open_url(download_url, self.timeout_sec) as resp:
                    payload = resp.read()
            elif parsed.scheme == "file":
                payload = Path(parsed.path).read_bytes()
            else:
                payload = Path(download_url).read_bytes()
            destination.write_bytes(payload)
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "downloaded",
                "download_url": download_url,
                "media_path": str(destination),
                "byte_count": len(payload),
            }
        except error.HTTPError as exc:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "http_error",
                "download_url": download_url,
                "media_path": str(destination),
                "error": f"HTTP {exc.code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "download_failed",
                "download_url": download_url,
                "media_path": str(destination),
                "error": str(exc),
            }


class KlingAdapter(HTTPVideoProviderAdapter):
    def __init__(self, live_mode: bool = False, timeout_sec: int = 60) -> None:
        super().__init__(provider_name="kling_3_0", live_mode=live_mode, timeout_sec=timeout_sec, env_prefix="MOVIEGEN_KLING")


class ViduAdapter(HTTPVideoProviderAdapter):
    def __init__(self, live_mode: bool = False, timeout_sec: int = 60) -> None:
        super().__init__(provider_name="vidu_q3", live_mode=live_mode, timeout_sec=timeout_sec, env_prefix="MOVIEGEN_VIDU")


class GenericAdapter(ProviderAdapter):
    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = self.build_request(payload)
        if self.live_mode:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "unsupported_provider",
                "external_job_id": None,
                "request": request_payload,
                "error": f"Live submission is not implemented for provider '{self.provider_name}'",
            }
        return super().submit(payload)


def resolve_adapter(spec: ProjectSpec, provider_name: str) -> ProviderAdapter:
    live_mode = spec.execution.live_mode
    if provider_name == "kling_3_0":
        return KlingAdapter(live_mode=live_mode, timeout_sec=spec.execution.request_timeout_sec)
    if provider_name == "vidu_q3":
        return ViduAdapter(live_mode=live_mode, timeout_sec=spec.execution.request_timeout_sec)
    return GenericAdapter(provider_name=provider_name, live_mode=live_mode, timeout_sec=spec.execution.request_timeout_sec)

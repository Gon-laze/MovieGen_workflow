from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .models import ProjectSpec


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


class KlingAdapter(ProviderAdapter):
    def __init__(self, live_mode: bool = False, timeout_sec: int = 60) -> None:
        super().__init__(provider_name="kling_3_0", live_mode=live_mode, timeout_sec=timeout_sec)

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model_name": payload.get("provider_model", "kling_3_0"),
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
            "url": os.getenv("MOVIEGEN_KLING_SUBMIT_URL"),
            "headers": {
                "Authorization": f"Bearer {os.getenv('MOVIEGEN_KLING_TOKEN', '')}".strip(),
                "Content-Type": "application/json",
            },
            "body": body,
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = self.build_request(payload)
        if not self.live_mode:
            return {
                "provider": self.provider_name,
                "mode": "mock",
                "status": "queued",
                "external_job_id": None,
                "request": request_payload,
                "submitted_payload_keys": sorted(payload.keys()),
            }
        url = request_payload["url"]
        auth = request_payload["headers"].get("Authorization", "")
        if not url or not auth or auth == "Bearer":
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "not_configured",
                "external_job_id": None,
                "request": request_payload,
                "error": "MOVIEGEN_KLING_SUBMIT_URL or MOVIEGEN_KLING_TOKEN is missing",
            }
        data = json.dumps(request_payload["body"]).encode("utf-8")
        req = request.Request(url, data=data, headers=request_payload["headers"], method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            parsed = json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "submitted",
                "external_job_id": parsed.get("id") or parsed.get("task_id") or parsed.get("job_id"),
                "request": request_payload,
                "response": parsed,
            }
        except error.HTTPError as exc:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "http_error",
                "external_job_id": None,
                "request": request_payload,
                "error": f"HTTP {exc.code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "request_failed",
                "external_job_id": None,
                "request": request_payload,
                "error": str(exc),
            }


class ViduAdapter(ProviderAdapter):
    def __init__(self, live_mode: bool = False, timeout_sec: int = 60) -> None:
        super().__init__(provider_name="vidu_q3", live_mode=live_mode, timeout_sec=timeout_sec)

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model_name": payload.get("provider_model", "vidu_q3"),
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
            "url": os.getenv("MOVIEGEN_VIDU_SUBMIT_URL"),
            "headers": {
                "Authorization": f"Bearer {os.getenv('MOVIEGEN_VIDU_TOKEN', '')}".strip(),
                "Content-Type": "application/json",
            },
            "body": body,
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = self.build_request(payload)
        if not self.live_mode:
            return {
                "provider": self.provider_name,
                "mode": "mock",
                "status": "queued",
                "external_job_id": None,
                "request": request_payload,
                "submitted_payload_keys": sorted(payload.keys()),
            }
        url = request_payload["url"]
        auth = request_payload["headers"].get("Authorization", "")
        if not url or not auth or auth == "Bearer":
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "not_configured",
                "external_job_id": None,
                "request": request_payload,
                "error": "MOVIEGEN_VIDU_SUBMIT_URL or MOVIEGEN_VIDU_TOKEN is missing",
            }
        data = json.dumps(request_payload["body"]).encode("utf-8")
        req = request.Request(url, data=data, headers=request_payload["headers"], method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            parsed = json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "submitted",
                "external_job_id": parsed.get("id") or parsed.get("task_id") or parsed.get("job_id"),
                "request": request_payload,
                "response": parsed,
            }
        except error.HTTPError as exc:
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "http_error",
                "external_job_id": None,
                "request": request_payload,
                "error": f"HTTP {exc.code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": self.provider_name,
                "mode": "live",
                "status": "request_failed",
                "external_job_id": None,
                "request": request_payload,
                "error": str(exc),
            }


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

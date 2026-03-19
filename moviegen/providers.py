from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ProjectSpec


@dataclass
class ProviderAdapter:
    provider_name: str
    live_mode: bool = False

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "mode": "live" if self.live_mode else "mock",
            "status": "queued",
            "external_job_id": None,
            "submitted_payload_keys": sorted(payload.keys()),
        }


class KlingAdapter(ProviderAdapter):
    def __init__(self, live_mode: bool = False) -> None:
        super().__init__(provider_name="kling_3_0", live_mode=live_mode)


class ViduAdapter(ProviderAdapter):
    def __init__(self, live_mode: bool = False) -> None:
        super().__init__(provider_name="vidu_q3", live_mode=live_mode)


class GenericAdapter(ProviderAdapter):
    pass


def resolve_adapter(spec: ProjectSpec, provider_name: str) -> ProviderAdapter:
    live_mode = spec.execution.live_mode
    if provider_name == spec.execution.primary_provider:
        return KlingAdapter(live_mode=live_mode)
    if provider_name == spec.execution.optional_provider:
        return ViduAdapter(live_mode=live_mode)
    return GenericAdapter(provider_name=provider_name, live_mode=live_mode)

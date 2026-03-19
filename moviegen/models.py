from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Stage(str, Enum):
    INGEST = "ingest"
    ANALYZE = "analyze"
    BIBLES = "bibles"
    BENCHMARK = "benchmark"
    PLAN = "plan"
    COMPILE_PROMPTS = "compile-prompts"
    ROUTE = "route"
    GENERATE = "generate"
    JUDGE = "judge"
    REVIEW = "review"
    POST = "post"
    ASSEMBLE = "assemble"
    REPORT = "report"
    ALL = "all"


ORDERED_STAGES: list[Stage] = [
    Stage.INGEST,
    Stage.ANALYZE,
    Stage.BIBLES,
    Stage.BENCHMARK,
    Stage.PLAN,
    Stage.COMPILE_PROMPTS,
    Stage.ROUTE,
    Stage.GENERATE,
    Stage.JUDGE,
    Stage.REVIEW,
    Stage.POST,
    Stage.ASSEMBLE,
    Stage.REPORT,
]


class ProjectSection(BaseModel):
    id: str
    title: str
    language: str = "zh-CN"
    target_runtime_min: int = Field(ge=1)
    budget_usd_cap: float = Field(gt=0)


class ReferencesSection(BaseModel):
    video_dirs: list[str] = Field(default_factory=list)
    image_dirs: list[str] = Field(default_factory=list)
    text_notes: list[str] = Field(default_factory=list)


class StyleSection(BaseModel):
    target_era: str
    tone_keywords: list[str] = Field(default_factory=list)


class ProvidersSection(BaseModel):
    preferred_a_pool: list[str] = Field(default_factory=list)
    preferred_b_pool: list[str] = Field(default_factory=list)
    preferred_c_pool: list[str] = Field(default_factory=list)

    @field_validator("preferred_a_pool", "preferred_b_pool", "preferred_c_pool")
    @classmethod
    def no_empty_items(cls, value: list[str]) -> list[str]:
        return [item for item in value if item]


class WorkflowSection(BaseModel):
    enable_human_gates: bool = True
    max_api_retries: int = Field(default=3, ge=0)
    budget_warning_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    budget_hard_stop_ratio: float = Field(default=1.0, ge=0.0, le=1.0)


class BenchmarkWeights(BaseModel):
    task_ceiling: float
    continuity: float
    motion_stability: float
    identity_consistency: float
    instruction_fidelity: float
    camera_control: float
    cost_efficiency: float


class BenchmarkThresholds(BaseModel):
    minimum_total_score: float
    minimum_task_ceiling_for_tier1: float
    close_margin_keep_both_tier1: float
    clear_win_for_archetype: float


class BenchmarkSection(BaseModel):
    suite_id: str
    must_test: list[str] = Field(default_factory=list)
    optional_test: list[str] = Field(default_factory=list)
    weights: BenchmarkWeights
    thresholds: BenchmarkThresholds


class RoutingSection(BaseModel):
    max_queue_wait_min: int = Field(ge=0)
    fuse_after_failures: int = Field(ge=1)
    fuse_cooldown_min: int = Field(ge=0)
    route_matrix: dict[str, list[str]]


class PlanningSection(BaseModel):
    shot_specs_file: str | None = None
    approved_candidates_file: str | None = None


class PostSection(BaseModel):
    processing_template: Literal["stream_copy_fast", "normalize_h264_faststart"] = "normalize_h264_faststart"
    ffmpeg_preset: str = "medium"
    ffmpeg_crf: int = Field(default=18, ge=0, le=51)
    audio_bitrate: str = "192k"
    fallback_copy_enabled: bool = True


class ExecutionSection(BaseModel):
    primary_provider: str = "kling_3_0"
    optional_provider: str = "vidu_q3"
    live_mode: bool = False
    request_timeout_sec: int = Field(default=60, ge=1)
    poll_after_submit: bool = True
    poll_max_attempts: int = Field(default=1, ge=1)
    poll_interval_sec: float = Field(default=0.0, ge=0.0)
    save_provider_requests: bool = True
    submission_strategy: Literal["primary_only", "primary_with_optional_fallback", "planned"] = "primary_only"
    allow_optional_provider_live: bool = True


class ProjectSpec(BaseModel):
    project: ProjectSection
    references: ReferencesSection
    style: StyleSection
    providers: ProvidersSection
    workflow: WorkflowSection
    benchmark: BenchmarkSection
    routing: RoutingSection
    planning: PlanningSection = Field(default_factory=PlanningSection)
    post: PostSection = Field(default_factory=PostSection)
    execution: ExecutionSection = Field(default_factory=ExecutionSection)


RunStatus = Literal["created", "running", "paused_for_gate", "failed", "completed", "canceled"]
StageRunStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]
GateStatus = Literal["waiting", "approved", "rejected", "expired"]


def resolve_stage_sequence(stage: Stage) -> list[Stage]:
    if stage == Stage.ALL:
        return ORDERED_STAGES.copy()
    return [stage]

"""Pydantic models for config, manifests, and job metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    transient = "transient"
    rate_limit = "rate_limit"
    safety = "safety"
    validation = "validation"
    permanent = "permanent"


class SceneStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class StageName(str, Enum):
    story = "story"
    preview = "preview"
    video = "video"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class SceneError(BaseModel):
    category: ErrorCategory
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class SceneRecord(BaseModel):
    scene_id: str
    title: str | None = None
    status: SceneStatus = SceneStatus.pending
    image_prompt: str | None = None
    video_prompt: str | None = None
    preview_path: str | None = None
    video_path: str | None = None
    error: SceneError | None = None
    updated_at: datetime | None = None


class ManifestEnvelope(BaseModel):
    schema_version: str = "1.0"
    job_id: UUID
    stage: StageName
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scenes: list[SceneRecord] = Field(default_factory=list)


class JobStageState(BaseModel):
    name: StageName
    status: StageStatus = StageStatus.pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None


class JobMetadata(BaseModel):
    job_id: UUID
    idea: str
    config_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stages: list[JobStageState] = Field(default_factory=list)
    reference_images: list[str] = Field(default_factory=list)


class RetryConfig(BaseModel):
    max_attempts: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter: bool = True


class ConcurrencyConfig(BaseModel):
    preview_max: int = 4
    video_submit_max: int = 4
    video_poll_max: int = 8


class ModelConfig(BaseModel):
    story: str = "gemini-2.0-flash"
    preview: str = "gemini-2.5-flash-image"
    config_generator: str = "gemini-2.0-flash"
    video: str = "veo-2.0-generate-001"


class PathsConfig(BaseModel):
    jobs_dir: str = "jobs"
    reference_image_a: str
    reference_image_b: str


class PromptsConfig(BaseModel):
    story_template: str
    preview_template: str
    video_template: str
    config_generator_template: str


class VideoConfig(BaseModel):
    aspect_ratio: str = "16:9"
    duration_seconds: int = 5
    poll_interval_seconds: float = 10.0


class WorkflowConfig(BaseModel):
    idea: str
    job_id: UUID | None = None
    paths: PathsConfig
    models: ModelConfig = Field(default_factory=ModelConfig)
    prompts: PromptsConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)


class StageResult(BaseModel):
    stage: StageName
    success: bool
    manifest_path: str
    message: str | None = None

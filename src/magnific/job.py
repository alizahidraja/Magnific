"""Job directory lifecycle and status reporting."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from magnific.manifests import ManifestManager
from magnific.models import (
    JobMetadata,
    JobStageState,
    PathsConfig,
    PromptsConfig,
    StageName,
    StageStatus,
    WorkflowConfig,
)
from magnific.utils import paths as path_utils


class JobManager:
    """Creates isolated per-job directories and tracks stage state."""

    def __init__(self, config: WorkflowConfig, config_path: Path) -> None:
        self.config = config
        self.config_path = config_path
        self.jobs_dir = Path(config.paths.jobs_dir).resolve()
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.job_id = config.job_id or uuid4()
        self.job_dir = path_utils.job_root(self.jobs_dir, self.job_id)
        self.manifests = ManifestManager(self.job_dir, self.job_id)

    def ensure_layout(self) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        (self.job_dir / "manifests").mkdir(exist_ok=True)
        path_utils.previews_dir(self.job_dir).mkdir(exist_ok=True)
        path_utils.videos_dir(self.job_dir).mkdir(exist_ok=True)

    def load_or_create_metadata(self) -> JobMetadata:
        meta_path = path_utils.job_metadata_path(self.job_dir)
        if meta_path.exists():
            return JobMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
        stages = [
            JobStageState(name=StageName.story),
            JobStageState(name=StageName.preview),
            JobStageState(name=StageName.video),
        ]
        meta = JobMetadata(
            job_id=self.job_id,
            idea=self.config.idea,
            config_path=str(self.config_path),
            reference_images=[
                self.config.paths.reference_image_a,
                self.config.paths.reference_image_b,
            ],
            stages=stages,
        )
        self.save_metadata(meta)
        return meta

    def save_metadata(self, meta: JobMetadata) -> None:
        meta.updated_at = datetime.now(timezone.utc)
        path = path_utils.job_metadata_path(self.job_dir)
        path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def update_stage_status(
        self,
        meta: JobMetadata,
        stage: StageName,
        status: StageStatus,
        message: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        for s in meta.stages:
            if s.name == stage:
                s.status = status
                s.message = message
                if status == StageStatus.running and s.started_at is None:
                    s.started_at = now
                if status in (StageStatus.completed, StageStatus.failed, StageStatus.partial):
                    s.finished_at = now
                break
        self.save_metadata(meta)

    @classmethod
    def from_existing_job(cls, jobs_dir: Path, job_id: UUID) -> JobManager:
        """Load job manager for status-only operations."""
        job_dir = path_utils.job_root(jobs_dir, job_id)
        meta_path = path_utils.job_metadata_path(job_dir)
        if not meta_path.exists():
            raise FileNotFoundError(f"Job not found: {job_id}")
        meta = JobMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
        config = WorkflowConfig(
            idea=meta.idea,
            job_id=meta.job_id,
            paths=PathsConfig(
                jobs_dir=str(jobs_dir),
                reference_image_a=meta.reference_images[0] if meta.reference_images else "",
                reference_image_b=meta.reference_images[1]
                if len(meta.reference_images) > 1
                else "",
            ),
            prompts=PromptsConfig(
                story_template="",
                preview_template="",
                video_template="",
                config_generator_template="",
            ),
        )
        mgr = cls(config, Path(meta.config_path))
        mgr.job_id = job_id
        mgr.job_dir = job_dir
        mgr.manifests = ManifestManager(job_dir, job_id)
        return mgr

    def status_summary(self) -> dict[str, object]:
        meta = self.load_or_create_metadata()
        manifests = {}
        for stage in StageName:
            m = self.manifests.read(stage)
            if m:
                manifests[stage.value] = {
                    "scenes": len(m.scenes),
                    "completed": sum(
                        1 for s in m.scenes if s.status.value == "completed"
                    ),
                    "failed": sum(1 for s in m.scenes if s.status.value == "failed"),
                }
        return {
            "job_id": str(self.job_id),
            "job_dir": str(self.job_dir),
            "idea": meta.idea,
            "stages": [s.model_dump(mode="json") for s in meta.stages],
            "manifests": manifests,
        }

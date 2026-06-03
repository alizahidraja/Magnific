"""Pipeline orchestration with stage resume support."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from magnific.config import save_workflow_config
from magnific.google_clients import build_clients
from magnific.job import JobManager
from magnific.models import StageName, WorkflowConfig
from magnific.stages import STAGE_ORDER, STAGE_REGISTRY
from magnific.stages.base import StageContext

logger = logging.getLogger("magnific.orchestrator")


class Orchestrator:
    """Runs stages in order, optionally starting mid-pipeline."""

    def __init__(
        self,
        config: WorkflowConfig,
        config_path: Path,
        *,
        from_stage: StageName | None = None,
        to_stage: StageName | None = None,
        use_mock: bool = False,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.config_dir = config_path.parent
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.use_mock = use_mock

    def _stages_to_run(self) -> list[StageName]:
        start = 0 if self.from_stage is None else STAGE_ORDER.index(self.from_stage)
        end = len(STAGE_ORDER) - 1 if self.to_stage is None else STAGE_ORDER.index(self.to_stage)
        if end < start:
            raise ValueError(f"Invalid stage range: {self.from_stage} -> {self.to_stage}")
        return STAGE_ORDER[start : end + 1]

    def _prerequisite_ok(self, job: JobManager, stage: StageName) -> bool:
        if stage == StageName.story:
            return True
        if stage == StageName.preview:
            return job.manifests.read(StageName.story) is not None
        if stage == StageName.video:
            return job.manifests.read(StageName.preview) is not None
        return False

    async def run(self) -> dict[str, str | list[str]]:
        job = JobManager(self.config, self.config_path)
        job.ensure_layout()
        if self.use_mock:
            logger.warning("Pipeline running in MOCK mode (--mock). Outputs are placeholders.")
        else:
            logger.info("Pipeline running in LIVE mode (GOOGLE_API_KEY required).")
        gemini, veo = build_clients(use_mock=self.use_mock, retry=self.config.retry)
        ctx = StageContext(
            config=self.config,
            config_dir=self.config_dir,
            job=job,
            gemini=gemini,
            veo=veo,
        )
        manifest_paths: list[str] = []
        for stage_name in self._stages_to_run():
            if not self._prerequisite_ok(job, stage_name):
                raise FileNotFoundError(
                    f"Cannot run stage '{stage_name.value}': prior manifest missing"
                )
            stage = STAGE_REGISTRY[stage_name]
            logger.info("Running stage: %s", stage_name.value)
            t0 = time.perf_counter()
            result = await stage.run(ctx)
            elapsed = time.perf_counter() - t0
            manifest_paths.append(result.manifest_path)
            logger.info(
                "Stage %s finished in %.1fs success=%s path=%s %s",
                stage_name.value,
                elapsed,
                result.success,
                result.manifest_path,
                result.message or "",
            )
            if not self.use_mock and elapsed < 2.0 and stage_name.value != "story":
                logger.warning(
                    "Stage %s completed very quickly (%.1fs) — check for mock artifacts or API errors.",
                    stage_name.value,
                    elapsed,
                )
        self.config.job_id = job.job_id
        save_workflow_config(self.config, self.config_path)
        return {
            "job_id": str(job.job_id),
            "job_dir": str(job.job_dir),
            "manifests": manifest_paths,
        }

"""Stage 2: concurrent preview still generation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from magnific.config import load_prompt_template
from magnific.manifests import ManifestManager
from magnific.models import (
    ManifestEnvelope,
    SceneRecord,
    SceneStatus,
    StageName,
    StageResult,
    StageStatus,
)
from magnific.retry import scene_error_from_exception
from magnific.stages.base import BaseStage, StageContext
from magnific.utils import paths as path_utils


class PreviewStage(BaseStage):
    name = StageName.preview

    async def run(self, ctx: StageContext) -> StageResult:
        meta = ctx.job.load_or_create_metadata()
        ctx.job.update_stage_status(meta, StageName.preview, StageStatus.running)

        story = ctx.job.manifests.read(StageName.story)
        if not story:
            raise FileNotFoundError("story_manifest.json required before preview stage")

        envelope = ctx.job.manifests.read(StageName.preview)
        if envelope is None:
            envelope = ctx.job.manifests.init_from_story(story)
            ctx.job.manifests.write(envelope)

        template = load_prompt_template(
            ctx.config.prompts.preview_template, ctx.config_dir
        )
        refs = [
            Path(ctx.config.paths.reference_image_a),
            Path(ctx.config.paths.reference_image_b),
        ]
        previews_root = path_utils.previews_dir(ctx.job.job_dir)
        output_map = {
            s.scene_id: previews_root / f"{s.scene_id}.png" for s in envelope.scenes
        }
        todo = ManifestManager.find_resumable_scenes(envelope, output_map)
        sem = asyncio.Semaphore(ctx.config.concurrency.preview_max)

        async def process(scene: SceneRecord) -> None:
            async with sem:
                scene.status = SceneStatus.running
                ctx.job.manifests.merge_scene(envelope, scene)
                try:
                    formatted = template.format(image_prompt=scene.image_prompt or "")
                    data = await ctx.gemini.generate_preview_image(
                        image_prompt=scene.image_prompt or "",
                        ref_paths=refs,
                        prompt_template=formatted,
                        model=ctx.config.models.preview,
                        aspect_ratio=ctx.config.video.aspect_ratio,
                    )
                    out = output_map[scene.scene_id]
                    out.write_bytes(data)
                    scene.preview_path = str(out)
                    scene.status = SceneStatus.completed
                    scene.error = None
                except Exception as exc:  # noqa: BLE001 — per-scene isolation
                    scene.status = SceneStatus.failed
                    scene.error = scene_error_from_exception(exc)
                scene.updated_at = datetime.now(timezone.utc)
                ctx.job.manifests.merge_scene(envelope, scene)

        await asyncio.gather(*[process(s) for s in todo], return_exceptions=True)

        failed = sum(1 for s in envelope.scenes if s.status == SceneStatus.failed)
        completed = sum(1 for s in envelope.scenes if s.status == SceneStatus.completed)
        stage_status = (
            StageStatus.completed
            if failed == 0
            else StageStatus.partial
            if completed > 0
            else StageStatus.failed
        )
        path = ctx.job.manifests.write(envelope)
        ctx.job.update_stage_status(meta, StageName.preview, stage_status)
        return StageResult(
            stage=StageName.preview,
            success=failed == 0,
            manifest_path=str(path),
            message=f"{completed} completed, {failed} failed",
        )

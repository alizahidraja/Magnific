"""Stage 3: Veo video generation with concurrent submit and poll pools."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from magnific.config import load_prompt_template
from magnific.google_clients import VeoOperation
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


class VideoStage(BaseStage):
    name = StageName.video

    async def run(self, ctx: StageContext) -> StageResult:
        meta = ctx.job.load_or_create_metadata()
        ctx.job.update_stage_status(meta, StageName.video, StageStatus.running)

        preview = ctx.job.manifests.read(StageName.preview)
        if not preview:
            raise FileNotFoundError("preview_manifest.json required before video stage")

        envelope = ctx.job.manifests.read(StageName.video)
        if envelope is None:
            envelope = ManifestEnvelope(
                job_id=ctx.job.job_id,
                stage=StageName.video,
                scenes=[
                    SceneRecord(
                        scene_id=s.scene_id,
                        title=s.title,
                        status=SceneStatus.pending,
                        image_prompt=s.image_prompt,
                        video_prompt=s.video_prompt,
                        preview_path=s.preview_path,
                    )
                    for s in preview.scenes
                    if s.status == SceneStatus.completed
                ],
            )
            ctx.job.manifests.write(envelope)

        template = load_prompt_template(
            ctx.config.prompts.video_template, ctx.config_dir
        )
        videos_root = path_utils.videos_dir(ctx.job.job_dir)
        output_map = {
            s.scene_id: videos_root / f"{s.scene_id}.mp4" for s in envelope.scenes
        }
        todo = ManifestManager.find_resumable_scenes(envelope, output_map)

        submit_sem = asyncio.Semaphore(ctx.config.concurrency.video_submit_max)
        poll_sem = asyncio.Semaphore(ctx.config.concurrency.video_poll_max)
        operations: list[tuple[SceneRecord, VeoOperation]] = []

        async def submit(scene: SceneRecord) -> None:
            async with submit_sem:
                scene.status = SceneStatus.running
                ctx.job.manifests.merge_scene(envelope, scene)
                preview_path = Path(scene.preview_path or "")
                if not preview_path.exists():
                    scene.status = SceneStatus.failed
                    scene.error = scene_error_from_exception(
                        FileNotFoundError(f"Missing preview: {preview_path}")
                    )
                    ctx.job.manifests.merge_scene(envelope, scene)
                    return
                try:
                    formatted = template.format(video_prompt=scene.video_prompt or "")
                    op = await ctx.veo.submit_video(
                        scene_id=scene.scene_id,
                        video_prompt=scene.video_prompt or "",
                        preview_path=preview_path,
                        model=ctx.config.models.video,
                        aspect_ratio=ctx.config.video.aspect_ratio,
                        duration_seconds=ctx.config.video.duration_seconds,
                        prompt_template=formatted,
                    )
                    operations.append((scene, op))
                except Exception as exc:  # noqa: BLE001
                    scene.status = SceneStatus.failed
                    scene.error = scene_error_from_exception(exc)
                    ctx.job.manifests.merge_scene(envelope, scene)

        await asyncio.gather(*[submit(s) for s in todo], return_exceptions=True)

        async def poll_and_save(scene: SceneRecord, op: VeoOperation) -> None:
            async with poll_sem:
                try:
                    uri = await ctx.veo.poll_until_done(
                        op,
                        poll_interval_seconds=ctx.config.video.poll_interval_seconds,
                    )
                    dest = output_map[scene.scene_id]
                    await ctx.veo.download_video(
                        uri, dest, video_handle=op.video_asset
                    )
                    scene.video_path = str(dest)
                    scene.status = SceneStatus.completed
                    scene.error = None
                except Exception as exc:  # noqa: BLE001
                    scene.status = SceneStatus.failed
                    scene.error = scene_error_from_exception(exc)
                scene.updated_at = datetime.now(timezone.utc)
                ctx.job.manifests.merge_scene(envelope, scene)

        await asyncio.gather(
            *[poll_and_save(s, op) for s, op in operations],
            return_exceptions=True,
        )

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
        ctx.job.update_stage_status(meta, StageName.video, stage_status)
        return StageResult(
            stage=StageName.video,
            success=failed == 0,
            manifest_path=str(path),
            message=f"{completed} completed, {failed} failed",
        )

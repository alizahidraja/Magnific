"""Stage 1: structured story / scene prompts via Gemini."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from magnific.config import load_prompt_template
from magnific.models import (
    ManifestEnvelope,
    SceneRecord,
    SceneStatus,
    StageName,
    StageResult,
    StageStatus,
)
from magnific.stages.base import BaseStage, StageContext


class StoryStage(BaseStage):
    name = StageName.story

    async def run(self, ctx: StageContext) -> StageResult:
        meta = ctx.job.load_or_create_metadata()
        ctx.job.update_stage_status(meta, StageName.story, StageStatus.running)

        template = load_prompt_template(
            ctx.config.prompts.story_template, ctx.config_dir
        ).format(idea=ctx.config.idea)
        refs = [
            Path(ctx.config.paths.reference_image_a),
            Path(ctx.config.paths.reference_image_b),
        ]
        scenes_payload = await ctx.gemini.generate_story(
            idea=ctx.config.idea,
            ref_paths=refs,
            prompt_template=template,
            model=ctx.config.models.story,
        )
        records = [
            SceneRecord(
                scene_id=s.scene_id,
                title=s.title,
                status=SceneStatus.completed,
                image_prompt=s.image_prompt,
                video_prompt=s.video_prompt,
                updated_at=datetime.now(timezone.utc),
            )
            for s in scenes_payload
        ]
        envelope = ManifestEnvelope(
            job_id=ctx.job.job_id,
            stage=StageName.story,
            scenes=records,
        )
        path = ctx.job.manifests.write(envelope)
        ctx.job.update_stage_status(meta, StageName.story, StageStatus.completed)
        return StageResult(
            stage=StageName.story,
            success=True,
            manifest_path=str(path),
        )

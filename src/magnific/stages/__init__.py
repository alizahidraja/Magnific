"""Stage registry for orchestrator."""

from __future__ import annotations

from magnific.models import StageName
from magnific.stages.base import BaseStage
from magnific.stages.preview import PreviewStage
from magnific.stages.story import StoryStage
from magnific.stages.video import VideoStage

STAGE_ORDER: list[StageName] = [
    StageName.story,
    StageName.preview,
    StageName.video,
]

STAGE_REGISTRY: dict[StageName, BaseStage] = {
    StageName.story: StoryStage(),
    StageName.preview: PreviewStage(),
    StageName.video: VideoStage(),
}

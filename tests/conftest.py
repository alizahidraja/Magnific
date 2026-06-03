"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from magnific.google_clients import MockGeminiClient, MockVeoClient, StoryScenePayload
from magnific.models import (
    ConcurrencyConfig,
    ModelConfig,
    PathsConfig,
    PromptsConfig,
    RetryConfig,
    WorkflowConfig,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"


@pytest.fixture
def configs_dir() -> Path:
    return CONFIGS


@pytest.fixture
def workflow_config(tmp_path: Path, configs_dir: Path) -> WorkflowConfig:
    ref_a = tmp_path / "ref_a.png"
    ref_b = tmp_path / "ref_b.png"
    ref_a.write_bytes(b"\x89PNG\r\n\x1a\n")
    ref_b.write_bytes(b"\x89PNG\r\n\x1a\n")
    return WorkflowConfig(
        idea="Test idea",
        paths=PathsConfig(
            jobs_dir=str(tmp_path / "jobs"),
            reference_image_a=str(ref_a),
            reference_image_b=str(ref_b),
        ),
        prompts=PromptsConfig(
            story_template=str(configs_dir / "prompts" / "story.txt"),
            preview_template=str(configs_dir / "prompts" / "preview.txt"),
            video_template=str(configs_dir / "prompts" / "video.txt"),
            config_generator_template=str(configs_dir / "prompts" / "config_generator.json"),
        ),
        models=ModelConfig(),
        concurrency=ConcurrencyConfig(preview_max=2, video_submit_max=2, video_poll_max=2),
        retry=RetryConfig(max_attempts=2, base_delay_seconds=0.01, max_delay_seconds=0.05),
    )


@pytest.fixture
def mock_clients() -> tuple[MockGeminiClient, MockVeoClient]:
    scenes = [
        StoryScenePayload(
            scene_id="scene_01",
            title="A",
            narrative="n1",
            image_prompt="img1",
            video_prompt="vid1",
        ),
    ]
    return MockGeminiClient(scenes=scenes), MockVeoClient()

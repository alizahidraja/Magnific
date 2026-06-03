"""Generate workflow.yaml from a creative idea."""

from __future__ import annotations

from pathlib import Path

from magnific.config import load_prompt_template, save_workflow_config
from magnific.google_clients import build_clients
from magnific.models import (
    ConcurrencyConfig,
    ModelConfig,
    PathsConfig,
    PromptsConfig,
    RetryConfig,
    VideoConfig,
    WorkflowConfig,
)


def default_workflow_from_idea(
    idea: str,
    *,
    configs_dir: Path,
    reference_a: str = "assets/ref_a.png",
    reference_b: str = "assets/ref_b.png",
    jobs_dir: str = "jobs",
    use_mock: bool = True,
) -> WorkflowConfig:
    """Build workflow config using template + optional Gemini expansion."""
    template_path = configs_dir / "prompts" / "config_generator.json"
    template = load_prompt_template(template_path, configs_dir)
    gemini, _ = build_clients(use_mock=use_mock)
    skeleton = gemini.generate_workflow_skeleton(
        idea=idea,
        template=template,
        model=ModelConfig().config_generator,
    )
    # Merge skeleton with required paths/prompts from repo defaults
    return WorkflowConfig(
        idea=idea,
        job_id=None,
        paths=PathsConfig(
            jobs_dir=jobs_dir,
            reference_image_a=skeleton.get("reference_image_a", reference_a),
            reference_image_b=skeleton.get("reference_image_b", reference_b),
        ),
        models=ModelConfig(**skeleton.get("models", {})) if skeleton.get("models") else ModelConfig(),
        prompts=PromptsConfig(
            story_template="configs/prompts/story.txt",
            preview_template="configs/prompts/preview.txt",
            video_template="configs/prompts/video.txt",
            config_generator_template="configs/prompts/config_generator.json",
        ),
        concurrency=ConcurrencyConfig(**skeleton.get("concurrency", {}))
        if skeleton.get("concurrency")
        else ConcurrencyConfig(),
        retry=RetryConfig(**skeleton.get("retry", {})) if skeleton.get("retry") else RetryConfig(),
        video=VideoConfig(**skeleton.get("video", {})) if skeleton.get("video") else VideoConfig(),
    )


def generate_config_file(
    idea: str,
    output: Path,
    *,
    configs_dir: Path | None = None,
    use_mock: bool = True,
) -> Path:
    root = configs_dir or Path(__file__).resolve().parents[2] / "configs"
    config = default_workflow_from_idea(idea, configs_dir=root, use_mock=use_mock)
    return save_workflow_config(config, output)

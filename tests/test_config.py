"""Config loading tests."""

from pathlib import Path

from magnific.config import load_prompt_template, load_workflow_config, save_workflow_config


def test_load_workflow_yaml(configs_dir: Path) -> None:
    cfg = load_workflow_config(configs_dir / "workflow.example.yaml")
    assert cfg.idea
    assert cfg.paths.reference_image_a


def test_save_roundtrip(tmp_path: Path, workflow_config) -> None:
    out = tmp_path / "w.yaml"
    save_workflow_config(workflow_config, out)
    loaded = load_workflow_config(out)
    assert loaded.idea == workflow_config.idea


def test_load_prompt_template(configs_dir: Path) -> None:
    text = load_prompt_template("prompts/story.txt", configs_dir)
    assert "{idea}" in text

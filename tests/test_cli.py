"""CLI parsing tests."""

from pathlib import Path
from uuid import UUID

from typer.testing import CliRunner

from magnific.cli import app
from magnific.job import JobManager


def test_generate_config_command(tmp_path: Path, configs_dir: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "workflow.yaml"
    result = runner.invoke(
        app,
        [
            "generate-config",
            "--idea",
            "Mars forest",
            "--output",
            str(out),
            "--configs-dir",
            str(configs_dir),
            "--mock",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out.exists()


def test_run_mock_pipeline(workflow_config, tmp_path: Path, configs_dir: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    from magnific.config import save_workflow_config

    save_workflow_config(workflow_config, cfg_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "--config", str(cfg_path), "--mock"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def test_status_command(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    mgr = JobManager(workflow_config, cfg_path)
    mgr.ensure_layout()
    mgr.load_or_create_metadata()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["status", "--job-id", str(mgr.job_id), "--jobs-dir", workflow_config.paths.jobs_dir],
    )
    assert result.exit_code == 0
    assert str(mgr.job_id) in result.stdout

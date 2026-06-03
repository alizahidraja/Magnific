"""Orchestrator integration tests with mocks."""

from pathlib import Path
from uuid import UUID

import pytest

from magnific.config import load_workflow_config, save_workflow_config
from magnific.models import StageName
from magnific.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_full_pipeline_mock(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    save_workflow_config(workflow_config, cfg_path)
    orch = Orchestrator(workflow_config, cfg_path, use_mock=True)
    result = await orch.run()
    assert len(result["manifests"]) == 3
    reloaded = load_workflow_config(cfg_path)
    assert reloaded.job_id is not None


@pytest.mark.asyncio
async def test_resume_from_preview(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    jobs_dir = tmp_path / "jobs"
    workflow_config.paths.jobs_dir = str(jobs_dir)
    save_workflow_config(workflow_config, cfg_path)
    orch = Orchestrator(workflow_config, cfg_path, use_mock=True)
    first = await orch.run()
    workflow_config.job_id = UUID(first["job_id"])
    orch2 = Orchestrator(
        workflow_config,
        cfg_path,
        from_stage=StageName.preview,
        use_mock=True,
    )
    result = await orch2.run()
    assert len(result["manifests"]) == 2


@pytest.mark.asyncio
async def test_story_stage_only(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    save_workflow_config(workflow_config, cfg_path)
    result = await Orchestrator(
        workflow_config,
        cfg_path,
        from_stage=StageName.story,
        to_stage=StageName.story,
        use_mock=True,
    ).run()
    assert len(result["manifests"]) == 1

"""Job manager tests."""

from pathlib import Path

from magnific.job import JobManager
from magnific.models import StageName, StageStatus


def test_job_layout_and_metadata(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    cfg_path.write_text("idea: x\n", encoding="utf-8")
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    mgr = JobManager(workflow_config, cfg_path)
    mgr.ensure_layout()
    meta = mgr.load_or_create_metadata()
    assert meta.job_id == mgr.job_id
    assert (mgr.job_dir / "manifests").is_dir()


def test_update_stage_status(workflow_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "workflow.yaml"
    workflow_config.paths.jobs_dir = str(tmp_path / "jobs")
    mgr = JobManager(workflow_config, cfg_path)
    mgr.ensure_layout()
    meta = mgr.load_or_create_metadata()
    mgr.update_stage_status(meta, StageName.story, StageStatus.running)
    meta2 = mgr.load_or_create_metadata()
    story = next(s for s in meta2.stages if s.name == StageName.story)
    assert story.status == StageStatus.running

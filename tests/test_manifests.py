"""Manifest manager tests."""

from uuid import uuid4

from magnific.manifests import ManifestManager
from magnific.models import ManifestEnvelope, SceneRecord, SceneStatus, StageName


def test_write_read_roundtrip(tmp_path) -> None:
    job_id = uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    mgr = ManifestManager(job_dir, job_id)
    env = ManifestEnvelope(
        job_id=job_id,
        stage=StageName.story,
        scenes=[SceneRecord(scene_id="s1", title="T", status=SceneStatus.completed)],
    )
    mgr.write(env)
    loaded = mgr.read(StageName.story)
    assert loaded is not None
    assert loaded.scenes[0].scene_id == "s1"


def test_find_resumable_scenes(tmp_path) -> None:
    job_id = uuid4()
    job_dir = tmp_path / str(job_id)
    mgr = ManifestManager(job_dir, job_id)
    env = ManifestEnvelope(
        job_id=job_id,
        stage=StageName.preview,
        scenes=[
            SceneRecord(scene_id="a", status=SceneStatus.completed),
            SceneRecord(scene_id="b", status=SceneStatus.failed),
        ],
    )
    out = { "a": tmp_path / "a.png", "b": tmp_path / "b.png" }
    out["a"].write_bytes(b"x")
    resumable = ManifestManager.find_resumable_scenes(env, out)
    ids = {s.scene_id for s in resumable}
    assert "b" in ids
    assert "a" not in ids

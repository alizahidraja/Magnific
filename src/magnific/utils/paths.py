"""Path helpers for job layout."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID


def job_root(jobs_dir: Path, job_id: UUID) -> Path:
    return jobs_dir / str(job_id)


def job_manifests_dir(job_dir: Path) -> Path:
    return job_dir / "manifests"


def story_manifest_path(job_dir: Path) -> Path:
    return job_manifests_dir(job_dir) / "story_manifest.json"


def preview_manifest_path(job_dir: Path) -> Path:
    return job_manifests_dir(job_dir) / "preview_manifest.json"


def video_manifest_path(job_dir: Path) -> Path:
    return job_manifests_dir(job_dir) / "video_manifest.json"


def previews_dir(job_dir: Path) -> Path:
    return job_dir / "previews"


def videos_dir(job_dir: Path) -> Path:
    return job_dir / "videos"


def job_metadata_path(job_dir: Path) -> Path:
    return job_dir / "job.json"

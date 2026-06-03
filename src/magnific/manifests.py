"""Manifest read/write and scene resumption helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from magnific.models import (
    ManifestEnvelope,
    SceneRecord,
    SceneStatus,
    StageName,
)
from magnific.utils.artifacts import (
    MIN_VALID_PREVIEW_BYTES,
    MIN_VALID_VIDEO_BYTES,
    is_placeholder_file,
)


class ManifestManager:
    """Persists stage manifests as versioned JSON envelopes."""

    def __init__(self, job_dir: Path, job_id: UUID) -> None:
        self.job_dir = job_dir
        self.job_id = job_id
        self.manifests_dir = job_dir / "manifests"
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def path_for_stage(self, stage: StageName) -> Path:
        return self.manifests_dir / f"{stage.value}_manifest.json"

    def read(self, stage: StageName) -> ManifestEnvelope | None:
        path = self.path_for_stage(stage)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ManifestEnvelope.model_validate(data)

    def write(self, envelope: ManifestEnvelope) -> Path:
        envelope.updated_at = datetime.now(timezone.utc)
        path = self.path_for_stage(envelope.stage)
        path.write_text(
            envelope.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def init_from_story(self, story: ManifestEnvelope) -> ManifestEnvelope:
        """Seed preview/video manifest scene list from story manifest."""
        scenes = [
            SceneRecord(
                scene_id=s.scene_id,
                title=s.title,
                status=SceneStatus.pending,
                image_prompt=s.image_prompt,
                video_prompt=s.video_prompt,
            )
            for s in story.scenes
        ]
        return ManifestEnvelope(
            job_id=self.job_id,
            stage=StageName.preview,
            scenes=scenes,
        )

    def merge_scene(self, envelope: ManifestEnvelope, updated: SceneRecord) -> None:
        for i, scene in enumerate(envelope.scenes):
            if scene.scene_id == updated.scene_id:
                envelope.scenes[i] = updated
                break
        else:
            envelope.scenes.append(updated)
        self.write(envelope)

    @staticmethod
    def find_resumable_scenes(
        envelope: ManifestEnvelope,
        output_check: dict[str, Path] | None = None,
        *,
        min_output_bytes: int | None = None,
    ) -> list[SceneRecord]:
        """Scenes that still need work (not completed or missing/placeholder output)."""
        default_threshold = (
            MIN_VALID_PREVIEW_BYTES
            if envelope.stage == StageName.preview
            else MIN_VALID_VIDEO_BYTES
        )
        threshold = min_output_bytes or default_threshold
        resumable: list[SceneRecord] = []
        for scene in envelope.scenes:
            out = output_check.get(scene.scene_id) if output_check else None
            if scene.status in (SceneStatus.pending, SceneStatus.failed, SceneStatus.running):
                resumable.append(scene)
                continue
            if scene.status != SceneStatus.completed:
                continue
            if out is None:
                resumable.append(scene)
            elif is_placeholder_file(out, min_bytes=threshold):
                resumable.append(scene)
        return resumable

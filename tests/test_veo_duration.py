"""Veo duration normalization tests."""

from magnific.google_api import normalize_veo_duration_seconds


def test_veo31_image_to_video_forces_8() -> None:
    assert (
        normalize_veo_duration_seconds(5, model="veo-3.1-generate-preview", image_to_video=True)
        == 8
    )


def test_veo31_text_snaps_to_allowed() -> None:
    assert normalize_veo_duration_seconds(7, model="veo-3.1-generate-preview", image_to_video=False) == 6


def test_veo2_clamps_range() -> None:
    assert normalize_veo_duration_seconds(5, model="veo-2.0-generate-001", image_to_video=True) == 5

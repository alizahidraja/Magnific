"""Detect mock/placeholder pipeline outputs."""

from __future__ import annotations

from pathlib import Path

# Mock client writes a 1x1 PNG (~70 bytes) and minimal ftyp MP4 (~28 bytes).
MIN_VALID_PREVIEW_BYTES = 512
MIN_VALID_VIDEO_BYTES = 1024


def is_placeholder_file(path: Path, *, min_bytes: int) -> bool:
    """True if missing or too small to be a real generated asset."""
    if not path.exists():
        return True
    try:
        return path.stat().st_size < min_bytes
    except OSError:
        return True

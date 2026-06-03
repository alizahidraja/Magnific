"""Google client mock tests."""

import pytest

from magnific.google_clients import MockGeminiClient, MockVeoClient, build_clients


@pytest.mark.asyncio
async def test_mock_gemini_story() -> None:
    client = MockGeminiClient()
    scenes = await client.generate_story(
        idea="x",
        ref_paths=[],
        prompt_template="",
        model="m",
    )
    assert len(scenes) >= 1


@pytest.mark.asyncio
async def test_mock_veo_flow(tmp_path) -> None:
    client = MockVeoClient()
    preview = tmp_path / "p.png"
    preview.write_bytes(b"\x89PNG")
    op = await client.submit_video(
        scene_id="s1",
        video_prompt="move",
        preview_path=preview,
        model="veo",
        aspect_ratio="16:9",
        duration_seconds=5,
        prompt_template="",
    )
    uri = await client.poll_until_done(op)
    dest = tmp_path / "out.mp4"
    await client.download_video(uri, dest)
    assert dest.exists()


def test_build_clients_mock_env(monkeypatch) -> None:
    monkeypatch.setenv("MAGNIFIC_MOCK_APIS", "1")
    g, v = build_clients()
    assert isinstance(g, MockGeminiClient)
    assert isinstance(v, MockVeoClient)

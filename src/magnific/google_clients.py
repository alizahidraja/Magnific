"""Mockable Google API client boundary (Gemini + Veo)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from magnific.google_api import (
    StoryResponseSchema,
    extract_image_bytes_from_response,
    extract_text_from_response,
    is_imagen_model,
    map_genai_exception,
    mime_type_for_path,
    normalize_veo_duration_seconds,
    parse_story_response_text,
)
from magnific.models import ErrorCategory, RetryConfig
from magnific.retry import NonRetryableError, retry_async

logger = logging.getLogger("magnific.google_clients")


@dataclass
class StoryScenePayload:
    scene_id: str
    title: str
    narrative: str
    image_prompt: str
    video_prompt: str


@dataclass
class VeoOperation:
    operation_id: str
    scene_id: str
    handle: Any = field(default=None, repr=False)
    video_asset: Any = field(default=None, repr=False)


class GeminiClientProtocol(Protocol):
    async def generate_story(
        self,
        *,
        idea: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
    ) -> list[StoryScenePayload]: ...

    async def generate_preview_image(
        self,
        *,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str = "16:9",
    ) -> bytes: ...

    def generate_workflow_skeleton(
        self,
        *,
        idea: str,
        template: str,
        model: str,
    ) -> dict[str, Any]: ...


class VeoClientProtocol(Protocol):
    async def submit_video(
        self,
        *,
        scene_id: str,
        video_prompt: str,
        preview_path: Path,
        model: str,
        aspect_ratio: str,
        duration_seconds: int,
        prompt_template: str,
    ) -> VeoOperation: ...

    async def poll_until_done(
        self, operation: VeoOperation, *, poll_interval_seconds: float = 10.0
    ) -> str: ...

    async def download_video(self, uri: str, dest: Path, *, video_handle: Any = None) -> Path: ...


class BaseGeminiClient(ABC):
    @abstractmethod
    async def generate_story(
        self,
        *,
        idea: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
    ) -> list[StoryScenePayload]: ...

    @abstractmethod
    async def generate_preview_image(
        self,
        *,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str = "16:9",
    ) -> bytes: ...

    @abstractmethod
    def generate_workflow_skeleton(
        self,
        *,
        idea: str,
        template: str,
        model: str,
    ) -> dict[str, Any]: ...


class BaseVeoClient(ABC):
    @abstractmethod
    async def submit_video(
        self,
        *,
        scene_id: str,
        video_prompt: str,
        preview_path: Path,
        model: str,
        aspect_ratio: str,
        duration_seconds: int,
        prompt_template: str,
    ) -> VeoOperation: ...

    @abstractmethod
    async def poll_until_done(
        self, operation: VeoOperation, *, poll_interval_seconds: float = 10.0
    ) -> str: ...

    @abstractmethod
    async def download_video(self, uri: str, dest: Path, *, video_handle: Any = None) -> Path: ...


def _require_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise NonRetryableError(
            "GOOGLE_API_KEY is not set",
            category=ErrorCategory.permanent,
        )
    return key


def _story_payloads_from_schema(schema: StoryResponseSchema) -> list[StoryScenePayload]:
    return [
        StoryScenePayload(
            scene_id=s.scene_id,
            title=s.title,
            narrative=s.narrative,
            image_prompt=s.image_prompt,
            video_prompt=s.video_prompt,
        )
        for s in schema.scenes
    ]


class HttpGeminiClient(BaseGeminiClient):
    """Live Gemini / Imagen client via google-genai SDK."""

    def __init__(self, retry: RetryConfig | None = None) -> None:
        self.retry = retry or RetryConfig()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        _require_api_key()
        try:
            from google import genai  # type: ignore[import-untyped]

            self._client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        except ImportError as exc:
            raise NonRetryableError(
                "google-genai package required. Install: pip install -e '.[dev]'",
                category=ErrorCategory.permanent,
            ) from exc
        return self._client

    async def generate_story(
        self,
        *,
        idea: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
    ) -> list[StoryScenePayload]:
        return await retry_async(
            lambda: self._generate_story_impl(prompt_template, ref_paths, model),
            max_attempts=self.retry.max_attempts,
            base_delay_seconds=self.retry.base_delay_seconds,
            max_delay_seconds=self.retry.max_delay_seconds,
            jitter=self.retry.jitter,
        )

    async def _generate_story_impl(
        self, prompt: str, ref_paths: list[Path], model: str
    ) -> list[StoryScenePayload]:
        from google.genai import types  # type: ignore[import-untyped]

        client = self._get_client()
        parts: list[Any] = [types.Part.from_text(text=prompt)]
        for ref in ref_paths:
            if not ref.exists():
                raise NonRetryableError(
                    f"Reference image not found: {ref}",
                    category=ErrorCategory.validation,
                )
            parts.append(
                types.Part.from_bytes(
                    data=ref.read_bytes(),
                    mime_type=mime_type_for_path(ref),
                )
            )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=StoryResponseSchema.model_json_schema(),
        )
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            raise map_genai_exception(exc) from exc
        text = extract_text_from_response(response)
        schema = parse_story_response_text(text)
        return _story_payloads_from_schema(schema)

    async def generate_preview_image(
        self,
        *,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str = "16:9",
    ) -> bytes:
        return await retry_async(
            lambda: self._generate_preview_impl(
                image_prompt, ref_paths, prompt_template, model, aspect_ratio
            ),
            max_attempts=self.retry.max_attempts,
            base_delay_seconds=self.retry.base_delay_seconds,
            max_delay_seconds=self.retry.max_delay_seconds,
            jitter=self.retry.jitter,
        )

    async def _generate_preview_impl(
        self,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str,
    ) -> bytes:
        if is_imagen_model(model):
            return await self._preview_via_imagen(prompt_template, model)
        return await self._preview_via_gemini_image(
            image_prompt, ref_paths, prompt_template, model, aspect_ratio
        )

    async def _preview_via_imagen(self, prompt: str, model: str) -> bytes:
        from google.genai import types  # type: ignore[import-untyped]

        client = self._get_client()
        try:
            response = await client.aio.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise map_genai_exception(exc) from exc
        if not response.generated_images:
            raise NonRetryableError(
                "Imagen returned no images",
                category=ErrorCategory.safety,
            )
        image = response.generated_images[0].image
        if image and image.image_bytes:
            return image.image_bytes
        raise NonRetryableError("Imagen response missing image bytes", category=ErrorCategory.validation)

    async def _preview_via_gemini_image(
        self,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str,
    ) -> bytes:
        from google.genai import types  # type: ignore[import-untyped]

        client = self._get_client()
        parts: list[Any] = [types.Part.from_text(text=prompt_template)]
        for ref in ref_paths:
            if ref.exists():
                parts.append(
                    types.Part.from_bytes(
                        data=ref.read_bytes(),
                        mime_type=mime_type_for_path(ref),
                    )
                )
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            raise map_genai_exception(exc) from exc
        _ = image_prompt
        return extract_image_bytes_from_response(response)

    def generate_workflow_skeleton(
        self,
        *,
        idea: str,
        template: str,
        model: str,
    ) -> dict[str, Any]:
        _ = model
        return json.loads(template.replace("__IDEA__", idea))


class HttpVeoClient(BaseVeoClient):
    """Live Veo client: submit operation, poll, download MP4."""

    def __init__(self, retry: RetryConfig | None = None) -> None:
        self.retry = retry or RetryConfig()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        _require_api_key()
        from google import genai  # type: ignore[import-untyped]

        self._client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        return self._client

    async def submit_video(
        self,
        *,
        scene_id: str,
        video_prompt: str,
        preview_path: Path,
        model: str,
        aspect_ratio: str,
        duration_seconds: int,
        prompt_template: str,
    ) -> VeoOperation:
        _ = prompt_template
        return await retry_async(
            lambda: self._submit_impl(
                scene_id,
                video_prompt,
                preview_path,
                model,
                aspect_ratio,
                duration_seconds,
            ),
            max_attempts=self.retry.max_attempts,
            base_delay_seconds=self.retry.base_delay_seconds,
            max_delay_seconds=self.retry.max_delay_seconds,
            jitter=self.retry.jitter,
        )

    async def _submit_impl(
        self,
        scene_id: str,
        video_prompt: str,
        preview_path: Path,
        model: str,
        aspect_ratio: str,
        duration_seconds: int,
    ) -> VeoOperation:
        from google.genai import types  # type: ignore[import-untyped]

        if not preview_path.exists():
            raise NonRetryableError(
                f"Preview not found: {preview_path}",
                category=ErrorCategory.validation,
            )
        client = self._get_client()
        image = types.Image.from_file(location=str(preview_path))
        effective_duration = normalize_veo_duration_seconds(
            duration_seconds,
            model=model,
            image_to_video=True,
        )
        if effective_duration != duration_seconds:
            logger.info(
                "Adjusted Veo duration_seconds %s -> %s for model %s (image-to-video)",
                duration_seconds,
                effective_duration,
                model,
            )
        config = types.GenerateVideosConfig(
            number_of_videos=1,
            aspect_ratio=aspect_ratio,
            duration_seconds=effective_duration,
        )
        try:
            operation = await client.aio.models.generate_videos(
                model=model,
                prompt=video_prompt,
                image=image,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            raise map_genai_exception(exc) from exc
        op_name = getattr(operation, "name", None) or f"veo-{scene_id}"
        return VeoOperation(operation_id=str(op_name), scene_id=scene_id, handle=operation)

    async def poll_until_done(
        self, operation: VeoOperation, *, poll_interval_seconds: float = 10.0
    ) -> str:
        if operation.handle is None:
            raise NonRetryableError("Missing Veo operation handle", category=ErrorCategory.validation)

        async def _poll() -> str:
            client = self._get_client()
            op = operation.handle
            while not op.done:
                await asyncio.sleep(poll_interval_seconds)
                op = await client.aio.operations.get(operation=op)
            if getattr(op, "error", None):
                raise NonRetryableError(
                    f"Veo operation failed: {op.error}",
                    category=ErrorCategory.permanent,
                )
            result = op.result
            if not result or not result.generated_videos:
                raise NonRetryableError(
                    "Veo returned no videos",
                    category=ErrorCategory.safety,
                )
            video = result.generated_videos[0].video
            operation.handle = op
            operation.video_asset = video
            return video.uri or f"veo-file:{operation.scene_id}"

        return await retry_async(
            _poll,
            max_attempts=self.retry.max_attempts,
            base_delay_seconds=self.retry.base_delay_seconds,
            max_delay_seconds=self.retry.max_delay_seconds,
            jitter=self.retry.jitter,
        )

    async def download_video(
        self, uri: str, dest: Path, *, video_handle: Any = None
    ) -> Path:
        _ = uri

        async def _download() -> Path:
            client = self._get_client()
            video = video_handle
            if video is None:
                raise NonRetryableError(
                    "Video handle required for download",
                    category=ErrorCategory.validation,
                )
            await client.aio.files.download(file=video)
            data = getattr(video, "video_bytes", None)
            if not data:
                raise NonRetryableError(
                    "Downloaded video has no bytes",
                    category=ErrorCategory.validation,
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return dest

        return await retry_async(
            _download,
            max_attempts=self.retry.max_attempts,
            base_delay_seconds=self.retry.base_delay_seconds,
            max_delay_seconds=self.retry.max_delay_seconds,
            jitter=self.retry.jitter,
        )


class MockGeminiClient(BaseGeminiClient):
    """Deterministic client for pytest."""

    def __init__(self, scenes: list[StoryScenePayload] | None = None) -> None:
        self.scenes = scenes or _default_story_scenes()

    async def generate_story(
        self,
        *,
        idea: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
    ) -> list[StoryScenePayload]:
        _ = (idea, ref_paths, prompt_template, model)
        return list(self.scenes)

    async def generate_preview_image(
        self,
        *,
        image_prompt: str,
        ref_paths: list[Path],
        prompt_template: str,
        model: str,
        aspect_ratio: str = "16:9",
    ) -> bytes:
        _ = (image_prompt, ref_paths, prompt_template, model, aspect_ratio)
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )

    def generate_workflow_skeleton(
        self,
        *,
        idea: str,
        template: str,
        model: str,
    ) -> dict[str, Any]:
        _ = (model,)
        return json.loads(template.replace("__IDEA__", idea))


class MockVeoClient(BaseVeoClient):
    def __init__(self) -> None:
        self._done: dict[str, asyncio.Event] = {}

    async def submit_video(
        self,
        *,
        scene_id: str,
        video_prompt: str,
        preview_path: Path,
        model: str,
        aspect_ratio: str,
        duration_seconds: int,
        prompt_template: str,
    ) -> VeoOperation:
        _ = (video_prompt, preview_path, model, aspect_ratio, duration_seconds, prompt_template)
        op_id = f"mock-{scene_id}"
        self._done[op_id] = asyncio.Event()
        asyncio.create_task(self._finish(op_id))
        return VeoOperation(operation_id=op_id, scene_id=scene_id, handle=op_id)

    async def _finish(self, op_id: str) -> None:
        await asyncio.sleep(0.02)
        ev = self._done.get(op_id)
        if ev:
            ev.set()

    async def poll_until_done(
        self, operation: VeoOperation, *, poll_interval_seconds: float = 10.0
    ) -> str:
        _ = poll_interval_seconds
        ev = self._done.get(operation.operation_id)
        if ev:
            await ev.wait()
        return f"mock://{operation.scene_id}"

    async def download_video(
        self, uri: str, dest: Path, *, video_handle: Any = None
    ) -> Path:
        _ = (uri, video_handle)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41")
        return dest


def _default_story_scenes(idea: str = "demo") -> list[StoryScenePayload]:
    return [
        StoryScenePayload(
            scene_id="scene_01",
            title="Opening",
            narrative=f"Opening for: {idea}",
            image_prompt="Wide shot, cinematic lighting",
            video_prompt="Slow dolly in, gentle motion",
        ),
        StoryScenePayload(
            scene_id="scene_02",
            title="Climax",
            narrative="Tension peaks",
            image_prompt="Close-up, dramatic contrast",
            video_prompt="Quick pan, energetic movement",
        ),
    ]


def build_clients(
    *,
    use_mock: bool = False,
    retry: RetryConfig | None = None,
) -> tuple[BaseGeminiClient, BaseVeoClient]:
    if use_mock:
        logger.warning(
            "MOCK mode: no real API calls (pass nothing, not --mock, for live Gemini/Veo)"
        )
        return MockGeminiClient(), MockVeoClient()
    _require_api_key()
    logger.info("LIVE mode: calling Google APIs via google-genai SDK")
    return HttpGeminiClient(retry=retry), HttpVeoClient(retry=retry)

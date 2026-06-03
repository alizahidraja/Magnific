"""Helpers for Google GenAI SDK calls and error mapping."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from magnific.models import ErrorCategory
from magnific.retry import NonRetryableError, RetryableError


class StorySceneSchema(BaseModel):
    scene_id: str
    title: str
    narrative: str
    image_prompt: str
    video_prompt: str


class StoryResponseSchema(BaseModel):
    scenes: list[StorySceneSchema] = Field(min_length=1)


def mime_type_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def map_genai_exception(exc: BaseException) -> BaseException:
    """Map SDK errors to Magnific retry taxonomy."""
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        return RetryableError(str(exc), category=ErrorCategory.transient)

    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None) or 400
        if code == 429:
            return RetryableError(str(exc), category=ErrorCategory.rate_limit)
        if code >= 500:
            return RetryableError(str(exc), category=ErrorCategory.transient)
        message = str(exc).lower()
        if code == 404 and ("model" in message or "not found" in message):
            return NonRetryableError(
                f"{exc}\nHint: update models in workflow.yaml "
                "(e.g. story: gemini-2.5-flash, preview: gemini-2.5-flash-image, "
                "video: veo-3.1-generate-preview).",
                category=ErrorCategory.validation,
            )
        if "safety" in message or "blocked" in message or "policy" in message:
            return NonRetryableError(str(exc), category=ErrorCategory.safety)
        if code in (400, 422):
            return NonRetryableError(str(exc), category=ErrorCategory.validation)
        return NonRetryableError(str(exc), category=ErrorCategory.permanent)
    if isinstance(exc, genai_errors.ServerError):
        return RetryableError(str(exc), category=ErrorCategory.transient)
    return RetryableError(str(exc), category=ErrorCategory.transient)


def parse_story_response_text(text: str) -> StoryResponseSchema:
    """Validate Gemini JSON story output."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NonRetryableError(
            f"Story response is not valid JSON: {exc}",
            category=ErrorCategory.validation,
        ) from exc
    try:
        return StoryResponseSchema.model_validate(payload)
    except ValidationError as exc:
        raise NonRetryableError(
            f"Story JSON failed schema validation: {exc}",
            category=ErrorCategory.validation,
        ) from exc


def extract_text_from_response(response: Any) -> str:
    if not response.candidates:
        raise NonRetryableError("Empty model response", category=ErrorCategory.validation)
    parts = response.candidates[0].content.parts or []
    chunks: list[str] = []
    for part in parts:
        if getattr(part, "text", None):
            chunks.append(part.text)
    if not chunks:
        raise NonRetryableError("No text in model response", category=ErrorCategory.validation)
    return "".join(chunks)


def extract_image_bytes_from_response(response: Any) -> bytes:
    if not response.candidates:
        raise NonRetryableError("Empty image response", category=ErrorCategory.validation)
    for part in response.candidates[0].content.parts or []:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            return inline.data
    raise NonRetryableError(
        "No image bytes in model response (safety filter or wrong model?)",
        category=ErrorCategory.safety,
    )


def is_imagen_model(model: str) -> bool:
    return model.lower().startswith("imagen")


VEO_31_ALLOWED_DURATIONS = (4, 6, 8)


def normalize_veo_duration_seconds(
    duration_seconds: int,
    *,
    model: str,
    image_to_video: bool = True,
) -> int:
    """
    Map config duration to a value the Veo API accepts.

    Veo 3.1 only supports 4, 6, or 8 seconds (not 5). Image-to-video on 3.1
    requires 8 seconds per Google docs.
    """
    model_lower = model.lower()
    if "veo-3" in model_lower:
        if image_to_video:
            return 8
        if duration_seconds in VEO_31_ALLOWED_DURATIONS:
            return duration_seconds
        return min(VEO_31_ALLOWED_DURATIONS, key=lambda d: abs(d - duration_seconds))
    # Veo 2.x: API message allows 4–8 inclusive
    return max(4, min(8, duration_seconds))

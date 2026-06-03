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

"""google_api helper tests."""

import pytest

from magnific.google_api import (
    StoryResponseSchema,
    map_genai_exception,
    parse_story_response_text,
)
from magnific.models import ErrorCategory
from magnific.retry import NonRetryableError, RetryableError


def test_parse_story_response_valid() -> None:
    raw = """{
      "scenes": [{
        "scene_id": "s1",
        "title": "T",
        "narrative": "N",
        "image_prompt": "I",
        "video_prompt": "V"
      }]
    }"""
    parsed = parse_story_response_text(raw)
    assert isinstance(parsed, StoryResponseSchema)
    assert parsed.scenes[0].scene_id == "s1"


def test_parse_story_response_invalid() -> None:
    with pytest.raises(NonRetryableError):
        parse_story_response_text("not json")


def test_map_genai_client_error_429() -> None:
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        pytest.skip("google-genai not installed")
    exc = genai_errors.ClientError(429, {"error": {"code": 429}}, None)
    mapped = map_genai_exception(exc)
    assert isinstance(mapped, RetryableError)
    assert mapped.category == ErrorCategory.rate_limit

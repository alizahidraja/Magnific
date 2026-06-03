"""Retry helper tests."""

import pytest

from magnific.models import ErrorCategory
from magnific.retry import (
    NonRetryableError,
    RetryableError,
    categorize_http_status,
    compute_delay,
    is_retryable_category,
    retry_async,
)


def test_categorize_http_status() -> None:
    assert categorize_http_status(429) == ErrorCategory.rate_limit
    assert categorize_http_status(503) == ErrorCategory.transient


def test_compute_delay_bounds() -> None:
    d = compute_delay(3, 1.0, 10.0, jitter=False)
    assert 4.0 <= d <= 10.0


@pytest.mark.asyncio
async def test_retry_async_success() -> None:
    calls = {"n": 0}

    async def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RetryableError("transient", category=ErrorCategory.transient)
        return "ok"

    result = await retry_async(
        fn,
        max_attempts=3,
        base_delay_seconds=0.01,
        max_delay_seconds=0.02,
        jitter=False,
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_async_non_retryable() -> None:
    async def fn():
        raise NonRetryableError("nope")

    with pytest.raises(NonRetryableError):
        await retry_async(
            fn,
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.02,
            jitter=False,
        )


def test_is_retryable_category() -> None:
    assert is_retryable_category(ErrorCategory.rate_limit)
    assert not is_retryable_category(ErrorCategory.safety)

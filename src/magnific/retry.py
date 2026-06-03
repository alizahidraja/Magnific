"""Retry utilities with exponential backoff and error categorization."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from magnific.models import ErrorCategory, SceneError

T = TypeVar("T")


class RetryableError(Exception):
    """Raised for errors that should be retried."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.transient) -> None:
        super().__init__(message)
        self.category = category


class NonRetryableError(Exception):
    """Raised for errors that must not be retried."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.permanent,
    ) -> None:
        super().__init__(message)
        self.category = category


def categorize_http_status(status: int) -> ErrorCategory:
    if status == 429:
        return ErrorCategory.rate_limit
    if status >= 500:
        return ErrorCategory.transient
    if status in (400, 422):
        return ErrorCategory.validation
    return ErrorCategory.permanent


def is_retryable_category(category: ErrorCategory) -> bool:
    return category in (ErrorCategory.transient, ErrorCategory.rate_limit)


def scene_error_from_exception(exc: BaseException) -> SceneError:
    if isinstance(exc, RetryableError):
        return SceneError(
            category=exc.category,
            message=str(exc),
            retryable=True,
        )
    if isinstance(exc, NonRetryableError):
        return SceneError(
            category=exc.category,
            message=str(exc),
            retryable=False,
        )
    return SceneError(
        category=ErrorCategory.transient,
        message=str(exc),
        retryable=True,
    )


def compute_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool,
) -> float:
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    if jitter:
        delay *= 0.5 + random.random()
    return delay


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter: bool,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except NonRetryableError:
            raise
        except RetryableError as exc:
            last_exc = exc
            if attempt >= max_attempts:
                raise
        except Exception as exc:  # noqa: BLE001 — boundary maps unknown to retry
            last_exc = exc
            if attempt >= max_attempts:
                raise RetryableError(str(exc)) from exc
        if attempt < max_attempts:
            delay = compute_delay(
                attempt, base_delay_seconds, max_delay_seconds, jitter
            )
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_async exhausted without result")


def retry_sync(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter: bool,
) -> T:
    import time

    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except NonRetryableError:
            raise
        except RetryableError as exc:
            last_exc = exc
            if attempt >= max_attempts:
                raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_attempts:
                raise RetryableError(str(exc)) from exc
        if attempt < max_attempts:
            delay = compute_delay(
                attempt, base_delay_seconds, max_delay_seconds, jitter
            )
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_sync exhausted without result")

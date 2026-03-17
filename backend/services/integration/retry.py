# backend/services/integration/retry.py

"""
Retry logic with exponential backoff for e-commerce API calls.
"""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: float = 0.1  # 10% random jitter

    # Status codes that should trigger a retry
    retry_status_codes: list[int] = field(
        default_factory=lambda: [
            408,  # Request Timeout
            429,  # Too Many Requests (rate limited)
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]
    )


# Default retry config
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_backoff_delay(attempt: int, config: RetryConfig, is_rate_limited: bool = False) -> float:
    """
    Calculate delay before next retry using exponential backoff with jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        is_rate_limited: If True, use longer delay for rate limits

    Returns:
        Delay in seconds
    """
    # Base exponential delay: 1s, 2s, 4s, 8s...
    delay = config.base_delay * (config.exponential_base**attempt)

    # Rate limited? Use longer base delay
    if is_rate_limited:
        delay = max(delay, 5.0)
        delay *= 2

    # Apply jitter (randomize +/- jitter%)
    jitter_range = delay * config.jitter
    delay += random.uniform(-jitter_range, jitter_range)

    # Cap at max delay
    return min(delay, config.max_delay)


def should_retry(exception: Exception | None, status_code: int | None, attempt: int, config: RetryConfig) -> bool:
    """
    Determine if request should be retried.

    Args:
        exception: Exception that was raised (if any)
        status_code: HTTP status code (if available)
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        True if should retry
    """
    if attempt >= config.max_retries:
        return False

    # Network errors - always retry
    if isinstance(exception, (httpx.ConnectError, httpx.TimeoutException)):
        return True

    # Retryable status codes
    if status_code and status_code in config.retry_status_codes:
        return True

    return False


async def execute_with_retry(
    func: Callable[..., T], *args, config: RetryConfig | None = None, operation_name: str = "operation", **kwargs
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration (uses default if None)
        operation_name: Name for logging
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        Last exception if all retries fail
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except httpx.HTTPStatusError as e:
            last_exception = e
            status_code = e.response.status_code
            is_rate_limited = status_code == 429

            if should_retry(e, status_code, attempt, config):
                delay = calculate_backoff_delay(attempt, config, is_rate_limited)
                logger.warning(
                    f"{operation_name} failed with status {status_code}, "
                    f"retrying in {delay:.2f}s (attempt {attempt + 1}/{config.max_retries + 1})"
                )
                await asyncio.sleep(delay)
                continue
            raise

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exception = e

            if should_retry(e, None, attempt, config):
                delay = calculate_backoff_delay(attempt, config)
                logger.warning(
                    f"{operation_name} failed with {type(e).__name__}, "
                    f"retrying in {delay:.2f}s (attempt {attempt + 1}/{config.max_retries + 1})"
                )
                await asyncio.sleep(delay)
                continue
            raise

        except httpx.RequestError as e:
            last_exception = e
            raise

    if last_exception:
        raise last_exception
    raise RuntimeError(f"{operation_name} failed after {config.max_retries + 1} attempts")


def with_retry(config: RetryConfig | None = None, operation_name: str | None = None):
    """
    Decorator to add retry logic to async methods.

    Usage:
        @with_retry(config=RetryConfig(max_retries=5))
        async def fetch_data(self, ...):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            name = operation_name or func.__name__
            return await execute_with_retry(func, *args, config=config, operation_name=name, **kwargs)

        return wrapper

    return decorator

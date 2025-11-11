"""Retry utility with exponential backoff for handling transient failures."""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff calculation
            jitter: Whether to add random jitter to delay
            retryable_exceptions: Tuple of exception types to retry on (None = all)
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(self.initial_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic with exponential backoff to functions.

    Args:
        config: RetryConfig instance (uses defaults if None)

    Example:
        @with_retry(RetryConfig(max_attempts=3))
        def my_function():
            # Function that might fail
            pass
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            # All attempts failed
            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            # All attempts failed
            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Pre-configured retry configs for common scenarios
FAST_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
)

STANDARD_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
)

SLOW_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
)

# Service-specific configs
OPENSEARCH_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    max_delay=5.0,
    retryable_exceptions=(ConnectionError, TimeoutError, Exception),
)

OLLAMA_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

REDIS_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.2,
    max_delay=2.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)


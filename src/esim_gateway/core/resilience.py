"""Resilience patterns: retry with exponential backoff and circuit breaker."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from esim_gateway.config import settings
from esim_gateway.core.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


# Exceptions that should trigger retry
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def with_retry(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to add retry logic with exponential backoff.

    Retries on network errors and timeouts, not on HTTP status errors.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        @retry(
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            stop=stop_after_attempt(settings.retry_max_attempts),
            wait=wait_exponential(
                multiplier=settings.retry_multiplier,
                min=settings.retry_min_wait,
                max=settings.retry_max_wait,
            ),
            reraise=True,
        )
        async def _inner() -> T:
            return await func(*args, **kwargs)

        try:
            return await _inner()
        except RetryError:
            # Re-raise the last exception
            raise

    return wrapper  # type: ignore[return-value]


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker pattern implementation.

    Tracks failures and opens circuit when threshold is exceeded.
    After timeout, allows one request through to test recovery.
    """

    name: str
    threshold: int = field(default_factory=lambda: settings.circuit_breaker_threshold)
    timeout: float = field(default_factory=lambda: settings.circuit_breaker_timeout)

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, handling timeout transition."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                logger.info(
                    "circuit_breaker_closed",
                    name=self.name,
                    previous_state=self._state.value,
                )
            self._failures = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()

            if self._failures >= self.threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        "circuit_breaker_opened",
                        name=self.name,
                        failures=self._failures,
                        threshold=self.threshold,
                        error=str(error),
                    )
                self._state = CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Check if a request can be executed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            # Allow one request through
            return True
        return False

    def __call__(
        self, func: Callable[P, T]
    ) -> Callable[P, T]:
        """Decorator to wrap a function with circuit breaker logic."""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not await self.can_execute():
                logger.warning(
                    "circuit_breaker_rejected",
                    name=self.name,
                    state=self.state.value,
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open"
                )

            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except Exception as e:
                await self.record_failure(e)
                raise

        return wrapper  # type: ignore[return-value]


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    pass


# Provider-specific circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a provider."""
    if provider not in _circuit_breakers:
        _circuit_breakers[provider] = CircuitBreaker(name=provider)
    return _circuit_breakers[provider]


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (useful for testing)."""
    _circuit_breakers.clear()

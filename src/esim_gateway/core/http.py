import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from esim_gateway.config import settings
from esim_gateway.core.exceptions import ProviderException
from esim_gateway.core.logging import get_logger
from esim_gateway.core.resilience import (
    RETRYABLE_EXCEPTIONS,
    CircuitBreakerOpenError,
    get_circuit_breaker,
)

logger = get_logger(__name__)


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive header values for logging."""
    sensitive = {"authorization", "x-api-key", "accesstoken"}
    return {
        k: "***" if k.lower() in sensitive else v
        for k, v in headers.items()
    }


class HTTPClient:
    """Async HTTP client wrapper for provider requests.

    Uses a shared client instance with connection pooling for better performance.
    Includes retry logic with exponential backoff and circuit breaker support.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_headers = headers or {}
        self.timeout = timeout or settings.http_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                http2=True,  # Enable HTTP/2 for multiplexing
                limits=httpx.Limits(
                    max_keepalive_connections=settings.http_max_keepalive,
                    max_connections=settings.http_max_connections,
                    keepalive_expiry=30.0,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        provider_name: str = "unknown",
        use_circuit_breaker: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the provider with retry and circuit breaker."""
        url = f"{self.base_url}{path}"
        merged_headers = {**self.default_headers, **(headers or {})}

        # Check circuit breaker
        if use_circuit_breaker:
            circuit_breaker = get_circuit_breaker(provider_name)
            if not await circuit_breaker.can_execute():
                logger.warning(
                    "circuit_breaker_rejected",
                    provider=provider_name,
                    method=method,
                    url=url,
                )
                raise ProviderException(
                    message=f"Service temporarily unavailable (circuit breaker open)",
                    provider=provider_name,
                    error_code="circuit_breaker_open",
                )

        # Log outgoing request
        logger.info(
            "provider_request",
            provider=provider_name,
            method=method,
            url=url,
            params=params,
            body=json,
            headers=_sanitize_headers(merged_headers),
        )

        # Inner function with retry logic
        @retry(
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            stop=stop_after_attempt(settings.retry_max_attempts),
            wait=wait_exponential(
                multiplier=settings.retry_multiplier,
                min=settings.retry_min_wait,
                max=settings.retry_max_wait,
            ),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                "request_retry",
                provider=provider_name,
                method=method,
                url=url,
                attempt=retry_state.attempt_number,
                error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
            ),
        )
        async def _do_request() -> httpx.Response:
            client = await self._get_client()
            return await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=merged_headers,
            )

        start_time = time.perf_counter()
        try:
            response = await _do_request()
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            response_body = response.json()

            # Log response
            logger.info(
                "provider_response",
                provider=provider_name,
                method=method,
                url=url,
                status=response.status_code,
                elapsed_ms=round(elapsed_ms, 2),
                body=response_body,
            )

            response.raise_for_status()

            # Record success for circuit breaker
            if use_circuit_breaker:
                await circuit_breaker.record_success()

            return response_body
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            error_body = None
            try:
                error_body = e.response.json()
            except Exception:
                error_body = {"raw": e.response.text}

            logger.warning(
                "provider_error",
                provider=provider_name,
                method=method,
                url=url,
                status=e.response.status_code,
                elapsed_ms=round(elapsed_ms, 2),
                error=error_body,
            )

            # Record failure for circuit breaker (5xx errors only)
            if use_circuit_breaker and e.response.status_code >= 500:
                await circuit_breaker.record_failure(e)

            raise ProviderException(
                message=f"Provider returned {e.response.status_code}",
                provider=provider_name,
                provider_code=str(e.response.status_code),
                provider_message=str(error_body),
            ) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "provider_connection_error",
                provider=provider_name,
                method=method,
                url=url,
                elapsed_ms=round(elapsed_ms, 2),
                error=str(e),
            )

            # Record failure for circuit breaker
            if use_circuit_breaker:
                await circuit_breaker.record_failure(e)

            raise ProviderException(
                message=f"Request to provider failed: {e}",
                provider=provider_name,
            ) from e

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        provider_name: str = "unknown",
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            provider_name=provider_name,
        )

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        provider_name: str = "unknown",
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self.request(
            "POST",
            path,
            json=json,
            params=params,
            headers=headers,
            provider_name=provider_name,
        )

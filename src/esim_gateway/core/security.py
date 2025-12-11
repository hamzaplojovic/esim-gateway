"""Security middleware and utilities for API authentication and rate limiting."""

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from esim_gateway.config import settings

# API Key authentication
api_key_header = APIKeyHeader(
    name=settings.api_key_header,
    auto_error=False,
)


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Verify the API key from the request header.

    Returns the API key if valid, raises HTTPException if invalid.
    Returns None if authentication is disabled.
    """
    # Skip auth if disabled (development only)
    if not settings.require_api_key:
        return None

    # Check if API keys are configured
    if not settings.get_api_keys():
        raise HTTPException(
            status_code=500,
            detail="API authentication is enabled but no API keys are configured",
        )

    # Check if key was provided
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include it in the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Validate the key
    if not settings.is_valid_api_key(api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return api_key


def get_client_identifier(request: Request) -> str:
    """Get a unique identifier for the client for rate limiting.

    Uses API key if available, otherwise falls back to IP address.
    """
    api_key = request.headers.get(settings.api_key_header)
    if api_key and settings.is_valid_api_key(api_key):
        # Use a hash of the API key to avoid exposing it
        return f"key:{api_key[:8]}..."
    return get_remote_address(request)


# Rate limiter instance
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=[f"{settings.rate_limit_requests}/{settings.rate_limit_window}"],
)

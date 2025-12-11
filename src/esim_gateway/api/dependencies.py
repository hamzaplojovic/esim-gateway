from fastapi import Header, HTTPException

from esim_gateway.providers.base import BaseProvider
from esim_gateway.providers.registry import get_provider_instance


async def get_provider(
    x_provider: str = Header(..., description="Provider name: esimgo, zetexa"),
) -> BaseProvider:
    """Extract and validate provider from header."""
    provider_name = x_provider.lower()

    try:
        return get_provider_instance(provider_name)
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider_name}. Valid: esimgo, zetexa",
        ) from e

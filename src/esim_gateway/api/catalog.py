from fastapi import APIRouter, Depends, Query

from esim_gateway.api.dependencies import get_provider
from esim_gateway.models.catalog import (
    GetPackageResponse,
    ListCountriesResponse,
    ListPackagesRequest,
    ListPackagesResponse,
    ListRegionsResponse,
)
from esim_gateway.providers.base import BaseProvider

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/countries", response_model=ListCountriesResponse)
async def list_countries(
    provider: BaseProvider = Depends(get_provider),
) -> ListCountriesResponse:
    """List all countries with available eSIM packages."""
    return await provider.list_countries()


@router.get("/regions", response_model=ListRegionsResponse)
async def list_regions(
    provider: BaseProvider = Depends(get_provider),
) -> ListRegionsResponse:
    """List all regions."""
    return await provider.list_regions()


@router.get("/packages", response_model=ListPackagesResponse)
async def list_packages(
    country: str | None = Query(None, description="Filter by ISO2 country code"),
    region: str | None = Query(None, description="Filter by region"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    provider: BaseProvider = Depends(get_provider),
) -> ListPackagesResponse:
    """List available eSIM packages."""
    request = ListPackagesRequest(
        country=country,
        region=region,
        page=page,
        limit=limit,
    )
    return await provider.list_packages(request)


@router.get("/packages/{package_id}", response_model=GetPackageResponse)
async def get_package(
    package_id: str,
    provider: BaseProvider = Depends(get_provider),
) -> GetPackageResponse:
    """Get a single package by ID."""
    return await provider.get_package(package_id)

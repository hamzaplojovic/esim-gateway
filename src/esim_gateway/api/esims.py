"""eSIM management API routes."""

from fastapi import APIRouter, Depends, Query

from esim_gateway.api.dependencies import get_provider
from esim_gateway.models.esim import (
    ApplyBundleRequest,
    ApplyBundleResponse,
    GetBundleStatusResponse,
    GetESimHistoryResponse,
    GetESimResponse,
    ListESimBundlesResponse,
    ListESimsRequest,
    ListESimsResponse,
    RevokeBundleRequest,
    RevokeBundleResponse,
)
from esim_gateway.models.usage import GetUsageResponse
from esim_gateway.providers.base import BaseProvider

router = APIRouter(prefix="/esims", tags=["esims"])


@router.get("", response_model=ListESimsResponse)
async def list_esims(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by eSIM status"),
    iccid: str | None = Query(None, description="Search by ICCID"),
    order_id: str | None = Query(None, description="Filter by order ID"),
    provider: BaseProvider = Depends(get_provider),
) -> ListESimsResponse:
    """List eSIMs with optional filters."""
    request = ListESimsRequest(
        page=page,
        limit=limit,
        status=status,
        iccid=iccid,
        order_id=order_id,
    )
    return await provider.list_esims(request)


@router.get("/{iccid}", response_model=GetESimResponse)
async def get_esim(
    iccid: str,
    provider: BaseProvider = Depends(get_provider),
) -> GetESimResponse:
    """Get eSIM details by ICCID."""
    return await provider.get_esim(iccid)


@router.post("/{iccid}/apply", response_model=ApplyBundleResponse)
async def apply_bundle(
    iccid: str,
    request: ApplyBundleRequest,
    provider: BaseProvider = Depends(get_provider),
) -> ApplyBundleResponse:
    """Apply a bundle/package to an eSIM."""
    request.iccid = iccid
    return await provider.apply_bundle(request)


@router.get("/{iccid}/bundles", response_model=ListESimBundlesResponse)
async def list_esim_bundles(
    iccid: str,
    provider: BaseProvider = Depends(get_provider),
) -> ListESimBundlesResponse:
    """List all bundles assigned to an eSIM."""
    return await provider.list_esim_bundles(iccid)


@router.get("/{iccid}/bundles/{bundle_name}", response_model=GetBundleStatusResponse)
async def get_bundle_status(
    iccid: str,
    bundle_name: str,
    provider: BaseProvider = Depends(get_provider),
) -> GetBundleStatusResponse:
    """Get status of a specific bundle on an eSIM."""
    return await provider.get_bundle_status(iccid, bundle_name)


@router.delete("/{iccid}/bundles/{bundle_name}", response_model=RevokeBundleResponse)
async def revoke_bundle(
    iccid: str,
    bundle_name: str,
    request: RevokeBundleRequest | None = None,
    provider: BaseProvider = Depends(get_provider),
) -> RevokeBundleResponse:
    """Revoke a bundle from an eSIM."""
    revoke_request = request or RevokeBundleRequest()
    return await provider.revoke_bundle(iccid, bundle_name, revoke_request)


@router.get("/{iccid}/usage", response_model=GetUsageResponse)
async def get_esim_usage(
    iccid: str,
    bundle_name: str | None = Query(None, description="Specific bundle to query"),
    provider: BaseProvider = Depends(get_provider),
) -> GetUsageResponse:
    """Get current usage statistics for an eSIM."""
    return await provider.get_usage(iccid, bundle_name)


@router.get("/{iccid}/history", response_model=GetESimHistoryResponse)
async def get_esim_history(
    iccid: str,
    provider: BaseProvider = Depends(get_provider),
) -> GetESimHistoryResponse:
    """Get lifecycle history of an eSIM."""
    return await provider.get_esim_history(iccid)

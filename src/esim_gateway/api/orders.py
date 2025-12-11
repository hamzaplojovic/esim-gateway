"""Orders API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from esim_gateway.api.dependencies import get_provider
from esim_gateway.models.order import (
    CreateOrderRequest,
    CreateOrderResponse,
    GetOrderResponse,
    ListOrdersRequest,
    ListOrdersResponse,
)
from esim_gateway.providers.base import BaseProvider

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=CreateOrderResponse)
async def create_order(
    request: CreateOrderRequest,
    provider: BaseProvider = Depends(get_provider),
) -> CreateOrderResponse:
    """Create an order for eSIM bundles."""
    return await provider.create_order(request)


@router.get("", response_model=ListOrdersResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_esims: bool = Query(True, description="Include eSIM details"),
    created_after: datetime | None = Query(None, description="Filter by creation date"),
    created_before: datetime | None = Query(None, description="Filter by creation date"),
    provider: BaseProvider = Depends(get_provider),
) -> ListOrdersResponse:
    """List orders with optional filters."""
    request = ListOrdersRequest(
        page=page,
        limit=limit,
        include_esims=include_esims,
        created_after=created_after,
        created_before=created_before,
    )
    return await provider.list_orders(request)


@router.get("/{order_id}", response_model=GetOrderResponse)
async def get_order(
    order_id: str,
    provider: BaseProvider = Depends(get_provider),
) -> GetOrderResponse:
    """Get order details by ID."""
    return await provider.get_order(order_id)

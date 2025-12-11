"""Account and wallet API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from esim_gateway.api.dependencies import get_provider
from esim_gateway.models.account import (
    GetBalanceResponse,
    ListTransactionsRequest,
    ListTransactionsResponse,
    RefundRequest,
    RefundResponse,
    TransactionStatus,
    TransactionType,
)
from esim_gateway.providers.base import BaseProvider

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/balance", response_model=GetBalanceResponse)
async def get_balance(
    provider: BaseProvider = Depends(get_provider),
) -> GetBalanceResponse:
    """Get current account balance."""
    return await provider.get_balance()


@router.get("/transactions", response_model=ListTransactionsResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    type: TransactionType | None = Query(None, description="Filter by transaction type"),
    status: TransactionStatus | None = Query(None, description="Filter by status"),
    order_id: str | None = Query(None, description="Filter by order ID"),
    iccid: str | None = Query(None, description="Filter by ICCID"),
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    provider: BaseProvider = Depends(get_provider),
) -> ListTransactionsResponse:
    """List account transactions."""
    request = ListTransactionsRequest(
        page=page,
        limit=limit,
        type=type,
        status=status,
        order_id=order_id,
        iccid=iccid,
        start_date=start_date,
        end_date=end_date,
    )
    return await provider.list_transactions(request)


@router.post("/refund", response_model=RefundResponse)
async def request_refund(
    request: RefundRequest,
    provider: BaseProvider = Depends(get_provider),
) -> RefundResponse:
    """Request a refund for an order or bundle."""
    return await provider.request_refund(request)

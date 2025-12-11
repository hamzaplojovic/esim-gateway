"""Account, wallet, and transaction models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────


class TransactionType(str, Enum):
    """Type of financial transaction."""

    PURCHASE = "purchase"  # Bundle/eSIM purchase
    REFUND = "refund"  # Refund issued
    TOPUP = "topup"  # Balance top-up
    CREDIT = "credit"  # Credit added
    DEBIT = "debit"  # Generic debit
    ADJUSTMENT = "adjustment"  # Manual adjustment


class TransactionStatus(str, Enum):
    """Transaction processing status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT MODELS
# ─────────────────────────────────────────────────────────────────────────────


class AccountBalance(BaseModel):
    """Account balance information."""

    balance: float  # Current available balance
    currency: str  # ISO currency code (USD, EUR, etc.)

    # Credit/Limits
    credit_limit: float | None = None  # Credit line if applicable
    available_credit: float | None = None

    # Pending amounts
    pending_charges: float | None = None  # Uncommitted charges
    reserved: float | None = None  # Reserved for pending orders

    # Thresholds
    low_balance_threshold: float | None = None
    auto_topup_enabled: bool = False
    auto_topup_amount: float | None = None

    # Last activity
    last_updated: datetime | None = None


class Transaction(BaseModel):
    """Financial transaction record."""

    id: str  # Unique transaction ID
    type: TransactionType
    status: TransactionStatus = TransactionStatus.COMPLETED

    # Amounts
    amount: float  # Positive for credits, negative for debits
    currency: str
    balance_after: float | None = None  # Balance after transaction

    # References
    order_id: str | None = None  # Related order
    reference: str | None = None  # External reference
    description: str | None = None

    # Related entities
    iccid: str | None = None  # Related eSIM
    package_id: str | None = None  # Related package

    # Timestamps
    created_at: datetime
    completed_at: datetime | None = None

    # Metadata
    metadata: dict[str, str] | None = None


class AccountInfo(BaseModel):
    """Full account information."""

    # Account identification
    account_id: str | None = None
    organization_name: str | None = None
    reseller_id: str | None = None

    # Contact
    email: str | None = None
    contact_name: str | None = None

    # Balance
    balance: AccountBalance

    # Account status
    is_active: bool = True
    tier: str | None = None  # Account tier/level

    # Timestamps
    created_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class GetBalanceResponse(BaseModel):
    """Response for getting account balance."""

    balance: AccountBalance


class GetAccountInfoResponse(BaseModel):
    """Response for getting full account info."""

    account: AccountInfo


class ListTransactionsRequest(BaseModel):
    """Request parameters for listing transactions."""

    page: int = 1
    limit: int = 50

    # Filters
    type: TransactionType | None = None
    status: TransactionStatus | None = None
    order_id: str | None = None
    iccid: str | None = None

    # Date range
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Sorting
    sort_by: str = "created_at"
    sort_order: str = "desc"  # "asc" or "desc"


class ListTransactionsResponse(BaseModel):
    """Response for listing transactions."""

    transactions: list[Transaction]
    total: int | None = None
    page: int
    limit: int

    # Aggregates for the query
    total_credits: float | None = None
    total_debits: float | None = None


class RefundRequest(BaseModel):
    """Request to issue a refund."""

    # What to refund (provide one of these)
    order_id: str | None = None  # Full order refund
    iccid: str | None = None  # Refund specific eSIM
    bundle_name: str | None = None  # Refund specific bundle

    # Refund details
    amount: float | None = None  # Partial refund amount (None = full)
    reason: str | None = None  # Reason for refund
    reference: str | None = None  # External reference


class RefundResponse(BaseModel):
    """Response from a refund request."""

    success: bool
    refund_id: str | None = None  # New refund transaction ID
    amount: float | None = None  # Amount refunded
    currency: str | None = None
    message: str | None = None

    # New balance after refund
    new_balance: float | None = None


class TopUpRequest(BaseModel):
    """Request to top up account balance."""

    amount: float
    currency: str = "USD"
    payment_method: str | None = None
    reference: str | None = None


class TopUpResponse(BaseModel):
    """Response from a top-up request."""

    success: bool
    transaction_id: str | None = None
    amount: float
    currency: str
    new_balance: float | None = None
    message: str | None = None

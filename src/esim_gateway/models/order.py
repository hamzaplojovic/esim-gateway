"""Order models for eSIM providers."""

from datetime import datetime

from pydantic import BaseModel, Field


class ESimActivation(BaseModel):
    """eSIM activation details for QR code generation."""

    iccid: str
    matching_id: str | None = None
    smdp_address: str | None = None
    lpa_string: str | None = None  # Full LPA string for QR


class OrderItem(BaseModel):
    """Single item in an order."""

    package_id: str
    package_name: str | None = None
    quantity: int = 1
    price_per_unit: float | None = None
    subtotal: float | None = None
    esims: list[ESimActivation] = []


class CustomerInfo(BaseModel):
    """Customer information for order (required by some providers)."""

    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None


class CreateOrderRequest(BaseModel):
    """Request to create an order."""

    items: list[OrderItem] = Field(..., min_length=1)
    customer: CustomerInfo | None = None
    assign: bool = True  # Auto-assign bundles to eSIMs
    iccids: list[str] | None = None  # Specific ICCIDs to assign to
    allow_reassign: bool = False  # Allow new eSIM if incompatible
    reference: str | None = None  # External reference ID


class Order(BaseModel):
    """Order details returned by provider."""

    order_id: str
    status: str
    status_message: str | None = None
    items: list[OrderItem] = []
    total: float
    currency: str = "USD"
    created_at: datetime | None = None
    assigned: bool = False
    reference: str | None = None  # External reference


class CreateOrderResponse(BaseModel):
    """Response from creating an order."""

    order: Order


class GetOrderResponse(BaseModel):
    """Response from getting an order."""

    order: Order


class ListOrdersRequest(BaseModel):
    """Request parameters for listing orders."""

    page: int = 1
    limit: int = 50
    include_esims: bool = True
    created_after: datetime | None = None
    created_before: datetime | None = None


class ListOrdersResponse(BaseModel):
    """Response from listing orders."""

    orders: list[Order]
    total: int | None = None
    page: int
    limit: int

"""Inventory and bundle management models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────


class InventoryType(str, Enum):
    """Type of inventory item."""

    PREPAID_ESIM = "prepaid_esim"  # Pre-provisioned eSIMs
    BUNDLE = "bundle"  # Data/voice bundle
    VOUCHER = "voucher"  # Recharge voucher


class BundleGroupType(str, Enum):
    """Bundle group classification."""

    COUNTRY = "country"  # Single country bundles
    REGIONAL = "regional"  # Multi-country/region bundles
    GLOBAL = "global"  # Worldwide bundles
    SPECIAL = "special"  # Promotional/special bundles


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY MODELS
# ─────────────────────────────────────────────────────────────────────────────


class InventoryItem(BaseModel):
    """Bundle/eSIM inventory item."""

    bundle_name: str  # Bundle/package identifier
    bundle_id: str | None = None

    # Counts
    available_count: int  # Ready to assign
    assigned_count: int = 0  # Currently in use
    total_count: int  # Total ever purchased/provisioned
    reserved_count: int = 0  # Reserved for pending orders

    # Inventory type
    type: InventoryType = InventoryType.BUNDLE

    # Pricing info
    cost_per_unit: float | None = None
    currency: str = "USD"

    # Metadata
    description: str | None = None
    countries: list[str] = []  # ISO2 codes
    validity_days: int | None = None
    data_mb: int | None = None

    # Status
    is_active: bool = True
    last_restocked: datetime | None = None


class BundleGroup(BaseModel):
    """Group of related bundles."""

    id: str
    name: str
    type: BundleGroupType = BundleGroupType.COUNTRY
    description: str | None = None
    image_url: str | None = None

    # Bundles in this group
    bundle_names: list[str] = []
    bundle_count: int = 0

    # Coverage
    countries: list[str] = []  # ISO2 codes


class InventorySummary(BaseModel):
    """Overall inventory summary."""

    total_bundles: int = 0
    total_available: int = 0
    total_assigned: int = 0
    total_value: float | None = None
    currency: str = "USD"

    # By type
    by_type: dict[str, int] = {}  # {type: count}

    # Low stock alerts
    low_stock_items: list[str] = []  # Bundle names with low inventory


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class ListInventoryRequest(BaseModel):
    """Request parameters for listing inventory."""

    page: int = 1
    limit: int = 100

    # Filters
    type: InventoryType | None = None
    country: str | None = None  # ISO2 filter
    bundle_name: str | None = None  # Search by name
    available_only: bool = False  # Only show items with available stock
    low_stock_only: bool = False  # Only show low stock items


class ListInventoryResponse(BaseModel):
    """Response for listing inventory."""

    items: list[InventoryItem]
    summary: InventorySummary | None = None
    total: int | None = None
    page: int
    limit: int


class GetInventoryItemResponse(BaseModel):
    """Response for getting a single inventory item."""

    item: InventoryItem


class ListBundleGroupsResponse(BaseModel):
    """Response for listing bundle groups."""

    groups: list[BundleGroup]
    total: int


class GetBundleGroupResponse(BaseModel):
    """Response for getting a single bundle group."""

    group: BundleGroup


class RestockRequest(BaseModel):
    """Request to restock inventory (provider-specific)."""

    bundle_name: str
    quantity: int
    reference: str | None = None


class RestockResponse(BaseModel):
    """Response from restocking inventory."""

    success: bool
    bundle_name: str
    quantity_added: int
    new_available_count: int
    cost: float | None = None
    currency: str | None = None
    message: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# ASSIGNMENT MODELS (For eSIM Go's /esims/assignments)
# ─────────────────────────────────────────────────────────────────────────────


class AssignmentInfo(BaseModel):
    """eSIM assignment/installation information."""

    iccid: str
    order_id: str | None = None

    # Installation codes
    lpa_string: str | None = None
    smdp_address: str | None = None
    matching_id: str | None = None
    confirmation_code: str | None = None

    # QR code data
    qr_code_url: str | None = None
    qr_code_base64: str | None = None

    # Installation status
    is_installed: bool = False
    installed_at: datetime | None = None

    # Bundle info
    bundle_name: str | None = None
    package_id: str | None = None


class ListAssignmentsRequest(BaseModel):
    """Request parameters for listing assignments."""

    page: int = 1
    limit: int = 50
    order_id: str | None = None
    iccid: str | None = None
    installed: bool | None = None  # Filter by installation status


class ListAssignmentsResponse(BaseModel):
    """Response for listing assignments."""

    assignments: list[AssignmentInfo]
    total: int | None = None
    page: int
    limit: int

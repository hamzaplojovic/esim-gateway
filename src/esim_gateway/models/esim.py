"""eSIM management models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────


class ESimStatus(str, Enum):
    """eSIM lifecycle status."""

    UNUSED = "unused"  # Not yet installed/activated
    INSTALLED = "installed"  # Downloaded to device (BPP_INSTALLATION)
    ACTIVE = "active"  # Currently enabled and operational
    DISABLED = "disabled"  # Temporarily disabled
    DELETED = "deleted"  # Permanently removed


class BundleStatus(str, Enum):
    """Bundle/package assignment status."""

    ACTIVE = "active"  # Currently usable
    INACTIVE = "inactive"  # Not yet activated
    EXPIRED = "expired"  # Validity period ended
    DEPLETED = "depleted"  # Data/allowances exhausted


# ─────────────────────────────────────────────────────────────────────────────
# BUNDLE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class AssignedBundle(BaseModel):
    """A bundle/package assigned to an eSIM."""

    name: str  # Bundle name/identifier
    package_id: str  # Reference to Package.id
    status: BundleStatus = BundleStatus.INACTIVE

    # Data allowance tracking
    data_total_mb: int | None = None
    data_remaining_mb: int | None = None
    data_used_mb: int | None = None
    is_unlimited: bool = False

    # Validity period
    start_date: datetime | None = None
    expiry_date: datetime | None = None
    auto_renew: bool = False

    # Voice/SMS (if applicable)
    voice_minutes_remaining: int | None = None
    sms_remaining: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# ESIM MODELS
# ─────────────────────────────────────────────────────────────────────────────


class ESim(BaseModel):
    """eSIM profile information."""

    # Core identifiers
    iccid: str  # Integrated Circuit Card ID (unique)
    eid: str | None = None  # eUICC ID (device identifier)
    imsi: str | None = None  # International Mobile Subscriber Identity

    # Status
    status: ESimStatus = ESimStatus.UNUSED

    # Activation/Installation data
    lpa_string: str | None = None  # Full LPA activation code for QR
    smdp_address: str | None = None  # SM-DP+ server address
    matching_id: str | None = None  # Activation code component
    confirmation_code: str | None = None

    # Timestamps
    created_at: datetime | None = None
    installed_at: datetime | None = None
    last_seen_at: datetime | None = None

    # Assigned bundles
    bundles: list[AssignedBundle] = []

    # Order reference
    order_id: str | None = None

    # Metadata
    label: str | None = None  # User-defined label
    tags: list[str] = []


class ESimHistory(BaseModel):
    """eSIM lifecycle event."""

    timestamp: datetime
    event_type: str  # CREATED, INSTALLED, ENABLED, DISABLED, BUNDLE_ASSIGNED, etc.
    description: str | None = None
    bundle_name: str | None = None
    metadata: dict | None = None


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class ListESimsRequest(BaseModel):
    """Request parameters for listing eSIMs."""

    page: int = 1
    limit: int = 50
    status: ESimStatus | None = None  # Filter by status
    iccid: str | None = None  # Filter by ICCID (partial match)
    order_id: str | None = None  # Filter by order


class ListESimsResponse(BaseModel):
    """Response for listing eSIMs."""

    esims: list[ESim]
    total: int | None = None
    page: int
    limit: int


class GetESimResponse(BaseModel):
    """Response for getting a single eSIM."""

    esim: ESim


class ApplyBundleRequest(BaseModel):
    """Request to apply a bundle/package to an eSIM."""

    iccid: str | None = None  # Apply to existing eSIM
    package_id: str  # Bundle/package to apply
    quantity: int = 1  # Number of eSIMs to provision (if creating new)
    allow_new_esim: bool = False  # Create new eSIM if ICCID not provided
    reference: str | None = None  # External reference


class ApplyBundleResponse(BaseModel):
    """Response from applying a bundle."""

    success: bool
    esims: list[ESim]  # eSIMs with the bundle applied
    order_id: str | None = None  # Created order reference


class ListESimBundlesResponse(BaseModel):
    """Response for listing bundles on an eSIM."""

    iccid: str
    bundles: list[AssignedBundle]
    total: int


class GetBundleStatusResponse(BaseModel):
    """Response for getting a specific bundle status."""

    iccid: str
    bundle: AssignedBundle


class RevokeBundleRequest(BaseModel):
    """Request to revoke a bundle from an eSIM."""

    reason: str | None = None


class RevokeBundleResponse(BaseModel):
    """Response from revoking a bundle."""

    success: bool
    message: str | None = None
    refund_amount: float | None = None
    refund_currency: str | None = None


class GetESimHistoryResponse(BaseModel):
    """Response for getting eSIM history."""

    iccid: str
    history: list[ESimHistory]
    total: int

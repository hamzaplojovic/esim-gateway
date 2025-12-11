"""Usage and statistics models for eSIM tracking."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────


class UsageType(str, Enum):
    """Type of usage event."""

    DATA = "data"
    VOICE = "voice"
    SMS = "sms"


class UsageUnit(str, Enum):
    """Unit of measurement for usage."""

    BYTES = "bytes"
    KILOBYTES = "KB"
    MEGABYTES = "MB"
    GIGABYTES = "GB"
    MINUTES = "minutes"
    SECONDS = "seconds"
    COUNT = "count"


# ─────────────────────────────────────────────────────────────────────────────
# USAGE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class UsageRecord(BaseModel):
    """Single usage event record."""

    timestamp: datetime
    event_type: UsageType
    amount: float
    unit: UsageUnit
    country: str | None = None  # ISO2 where usage occurred
    network: str | None = None  # Carrier name
    session_id: str | None = None


class DataUsage(BaseModel):
    """Data usage breakdown."""

    used_mb: float = 0
    remaining_mb: float | None = None  # None if unlimited
    total_mb: float | None = None
    is_unlimited: bool = False

    # Breakdown by direction (if available)
    upload_mb: float | None = None
    download_mb: float | None = None


class VoiceUsage(BaseModel):
    """Voice usage breakdown."""

    used_minutes: float = 0
    remaining_minutes: float | None = None
    total_minutes: float | None = None
    is_unlimited: bool = False
    is_included: bool = False


class SmsUsage(BaseModel):
    """SMS usage breakdown."""

    used_count: int = 0
    remaining_count: int | None = None
    total_count: int | None = None
    is_unlimited: bool = False
    is_included: bool = False


class UsageStats(BaseModel):
    """Comprehensive usage statistics for an eSIM or bundle."""

    iccid: str
    bundle_name: str | None = None  # Specific bundle or overall

    # Usage breakdown
    data: DataUsage
    voice: VoiceUsage | None = None
    sms: SmsUsage | None = None

    # Period information
    period_start: datetime | None = None
    period_end: datetime | None = None

    # Status
    last_activity: datetime | None = None
    is_active: bool = True


class UsageHistory(BaseModel):
    """Historical usage records."""

    iccid: str
    records: list[UsageRecord]
    total: int

    # Aggregated stats for the period
    total_data_mb: float = 0
    total_voice_minutes: float = 0
    total_sms_count: int = 0

    # Query parameters (for reference)
    period_start: datetime | None = None
    period_end: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class GetUsageRequest(BaseModel):
    """Request to get usage for an eSIM."""

    iccid: str
    bundle_name: str | None = None  # Specific bundle or overall
    include_history: bool = False


class GetUsageResponse(BaseModel):
    """Response containing usage statistics."""

    usage: UsageStats


class GetUsageHistoryRequest(BaseModel):
    """Request to get usage history."""

    iccid: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    usage_type: UsageType | None = None  # Filter by type
    page: int = 1
    limit: int = 100


class GetUsageHistoryResponse(BaseModel):
    """Response containing usage history."""

    history: UsageHistory
    page: int
    limit: int

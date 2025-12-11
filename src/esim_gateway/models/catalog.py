from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# COUNTRY
# ─────────────────────────────────────────────────────────────────────────────


class Network(BaseModel):
    """Network/carrier information."""

    name: str  # "Vodafone Germany"
    brand_name: str | None = None  # "Vodafone"
    speeds: list[str] = []  # ["2G", "3G", "4G", "5G"]


class Country(BaseModel):
    """Country with available eSIM packages."""

    iso2: str  # "US", "DE"
    iso3: str | None = None  # "USA", "DEU"
    name: str  # "United States"
    region: str | None = None  # "North America"
    image_url: str | None = None  # Flag image URL
    networks: list[Network] = []  # Available carriers in this country


# ─────────────────────────────────────────────────────────────────────────────
# REGION
# ─────────────────────────────────────────────────────────────────────────────


class Region(BaseModel):
    """Region grouping countries."""

    id: str  # "europe", "asia"
    name: str  # "Europe", "Asia"
    image_url: str | None = None
    countries: list[str] = []  # ISO2 codes: ["DE", "FR", "IT"]


# ─────────────────────────────────────────────────────────────────────────────
# ALLOWANCES
# ─────────────────────────────────────────────────────────────────────────────


class DataAllowance(BaseModel):
    """Data allowance for a package."""

    amount_mb: int | None = None  # Null if unlimited
    is_unlimited: bool = False
    fup_policy: str | None = None  # Fair usage policy text


class VoiceAllowance(BaseModel):
    """Voice allowance for a package."""

    minutes: int | None = None  # Null if not included or unlimited
    is_unlimited: bool = False
    is_included: bool = False


class SmsAllowance(BaseModel):
    """SMS allowance for a package."""

    count: int | None = None  # Null if not included or unlimited
    is_unlimited: bool = False
    is_included: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# PACKAGE
# ─────────────────────────────────────────────────────────────────────────────


class Package(BaseModel):
    """eSIM package."""

    # Identity
    id: str  # Provider's package ID
    name: str  # Display name
    description: str | None = None

    # Coverage
    countries: list[Country]  # Where it works
    roaming_countries: list[Country] = []  # Additional countries where roaming works
    is_regional: bool = False  # Multi-country package

    # Allowances
    data: DataAllowance
    voice: VoiceAllowance | None = None
    sms: SmsAllowance | None = None

    # Validity & Price
    validity_days: int
    price: float
    currency: str = "USD"
    billing_type: str | None = None  # "FixedCost", "PayAsYouGo", etc.

    # Technical
    network_speed: list[str] = []  # ["4G", "5G"]
    networks: list[str] = []  # Carrier names (simple list)
    autostart: bool = False
    is_active: bool = True

    # Metadata
    groups: list[str] = []
    image_url: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────


class ListCountriesResponse(BaseModel):
    """Response for listing countries."""

    countries: list[Country]
    total: int


class ListRegionsResponse(BaseModel):
    """Response for listing regions."""

    regions: list[Region]
    total: int


class ListPackagesRequest(BaseModel):
    """Request parameters for listing packages."""

    country: str | None = None  # ISO2 filter
    region: str | None = None  # Region filter
    page: int = 1
    limit: int = 50


class ListPackagesResponse(BaseModel):
    """Response for listing packages."""

    packages: list[Package]
    total: int | None = None  # If provider returns it
    page: int
    limit: int


class GetPackageResponse(BaseModel):
    """Response for getting a single package."""

    package: Package


# ─────────────────────────────────────────────────────────────────────────────
# ERROR MODELS
# ─────────────────────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Error details."""

    code: str  # Machine-readable code
    message: str  # Human-readable message
    provider_code: str | None = None  # Original provider error code
    provider_message: str | None = None


class ErrorResponse(BaseModel):
    """Error response envelope."""

    success: bool = False
    error: ErrorDetail
    provider: str | None = None

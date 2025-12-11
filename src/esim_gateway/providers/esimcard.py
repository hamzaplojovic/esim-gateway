"""esimCard provider implementation.

Provider: esimCard
Website: https://esimcard.com
API Docs: https://portal.esimcard.com/api/documentation

Endpoints:
    Auth: POST /developer/reseller/login
    Catalog: /developer/reseller/packages, /developer/reseller/packages/country,
             /developer/reseller/packages/continent
    Orders: /developer/reseller/package/purchase, /developer/reseller/order/{id}
    eSIMs: /developer/reseller/my-esims, /developer/reseller/my-esims/{iccid}
    Usage: /developer/reseller/my-sim/{iccid}/usage
    Account: /developer/reseller/balance
"""

import time
from typing import Any

from esim_gateway.core.exceptions import (
    BundleNotFoundException,
    ESimNotFoundException,
    PackageNotFoundException,
    ProviderException,
)
from esim_gateway.core.http import HTTPClient
from esim_gateway.core.utils import MultiCache, map_status, parse_datetime, parse_price
from esim_gateway.models.account import (
    AccountBalance,
    GetBalanceResponse,
    ListTransactionsRequest,
    ListTransactionsResponse,
)
from esim_gateway.models.catalog import (
    Country,
    DataAllowance,
    GetPackageResponse,
    ListCountriesResponse,
    ListPackagesRequest,
    ListPackagesResponse,
    ListRegionsResponse,
    Package,
    Region,
    SmsAllowance,
    VoiceAllowance,
)
from esim_gateway.models.esim import (
    ApplyBundleRequest,
    ApplyBundleResponse,
    AssignedBundle,
    BundleStatus,
    ESim,
    ESimStatus,
    GetBundleStatusResponse,
    GetESimResponse,
    ListESimBundlesResponse,
    ListESimsRequest,
    ListESimsResponse,
)
from esim_gateway.models.order import (
    CreateOrderRequest,
    CreateOrderResponse,
    ESimActivation,
    GetOrderResponse,
    ListOrdersRequest,
    ListOrdersResponse,
    Order,
    OrderItem,
)
from esim_gateway.models.usage import (
    DataUsage,
    GetUsageResponse,
    UsageStats,
)
from esim_gateway.providers.base import BaseProvider

# Status mappings - esimCard values to unified enums
ESIM_STATUS_MAP: dict[str, ESimStatus] = {
    "released": ESimStatus.UNUSED,
    "initiated": ESimStatus.UNUSED,
    "installed": ESimStatus.INSTALLED,
    "active": ESimStatus.ACTIVE,
    "enabled": ESimStatus.ACTIVE,
    "disabled": ESimStatus.DISABLED,
    "revoked": ESimStatus.DELETED,
    "failed": ESimStatus.DELETED,
}

BUNDLE_STATUS_MAP: dict[str, BundleStatus] = {
    "released": BundleStatus.ACTIVE,
    "installed": BundleStatus.ACTIVE,
    "active": BundleStatus.ACTIVE,
    "completed": BundleStatus.DEPLETED,
    "expired": BundleStatus.EXPIRED,
    "revoked": BundleStatus.INACTIVE,
    "failed": BundleStatus.INACTIVE,
    "initiated": BundleStatus.INACTIVE,
    "processing": BundleStatus.INACTIVE,
}


class ESimCardProvider(BaseProvider):
    """esimCard eSIM provider implementation.

    Provides access to esimCard's eSIM services including:
    - Data-only packages
    - Data + Voice + SMS packages
    - Global and regional coverage

    Authentication uses email/password to obtain a Bearer token.
    """

    name = "esimcard"
    base_url_live = "https://esimcard.com/api"
    base_url_sandbox = "https://esimcard.com/api"  # Same URL for both environments
    TOKEN_TTL = 86400  # 24 hours (adjust based on actual token expiry)

    def __init__(
        self,
        api_key: str,  # Not used for esimCard, kept for interface compatibility
        sandbox: bool = False,
        email: str = "",
        password: str = "",
    ):
        super().__init__(api_key, sandbox)
        self.email = email
        self.password = password
        self.base_url = self.base_url_sandbox if sandbox else self.base_url_live

        # HTTP client (set after auth)
        self._client: HTTPClient | None = None
        self._access_token: str | None = None
        self._access_token_time: float = 0

        # Cache for catalog data (5 minutes TTL)
        self._cache = MultiCache(ttl=300)

    async def _ensure_auth(self) -> HTTPClient:
        """Ensure we have a valid access token and return configured client."""
        now = time.time()
        if self._access_token and (now - self._access_token_time) < self.TOKEN_TTL:
            return self._client  # type: ignore

        # Login to get new access token
        login_client = HTTPClient(
            base_url=self.base_url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        response = await login_client.post(
            "/developer/reseller/login",
            json={"email": self.email, "password": self.password},
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ProviderException(
                message="Failed to authenticate with esimCard",
                provider=self.name,
                provider_message=str(response.get("message", response)),
            )

        self._access_token = response.get("access_token")
        self._access_token_time = now

        # Create authenticated client
        self._client = HTTPClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        return self._client

    # ─────────────────────────────────────────────────────────────────────────
    # CATALOG METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def _get_countries_raw(self) -> list[dict[str, Any]]:
        """Get raw countries data with caching."""
        if self._cache.is_valid("countries"):
            return self._cache.get("countries")

        client = await self._ensure_auth()
        response = await client.get(
            "/developer/reseller/packages/country",
            provider_name=self.name,
        )

        data = response.get("data", []) if isinstance(response, dict) else response
        self._cache.set("countries", data)
        return data

    async def _get_regions_raw(self) -> list[dict[str, Any]]:
        """Get raw regions/continents data with caching."""
        if self._cache.is_valid("regions"):
            return self._cache.get("regions")

        client = await self._ensure_auth()
        response = await client.get(
            "/developer/reseller/packages/continent",
            provider_name=self.name,
        )

        data = response.get("data", []) if isinstance(response, dict) else response
        self._cache.set("regions", data)
        return data

    async def _get_all_packages(self) -> list[dict[str, Any]]:
        """Get all packages with caching."""
        if self._cache.is_valid("packages"):
            return self._cache.get("packages")

        client = await self._ensure_auth()
        response = await client.get(
            "/developer/reseller/packages",
            params={"package_type": "DATA-ONLY"},
            provider_name=self.name,
        )

        packages: dict[str, dict[str, Any]] = {}
        data = response.get("data", []) if isinstance(response, dict) else response

        for pkg in data:
            pkg_id = str(pkg.get("id", ""))
            if pkg_id:
                packages[pkg_id] = pkg

        # Also fetch DATA-VOICE-SMS packages
        response_dvs = await client.get(
            "/developer/reseller/packages",
            params={"package_type": "DATA-VOICE-SMS"},
            provider_name=self.name,
        )
        data_dvs = response_dvs.get("data", []) if isinstance(response_dvs, dict) else response_dvs

        for pkg in data_dvs:
            pkg_id = str(pkg.get("id", ""))
            if pkg_id and pkg_id not in packages:
                packages[pkg_id] = pkg

        result = list(packages.values())
        self._cache.set("packages", result)
        return result

    async def list_countries(self) -> ListCountriesResponse:
        """List all countries with available packages."""
        data = await self._get_countries_raw()

        countries = sorted(
            [
                Country(
                    iso2=c.get("code", c.get("iso2", "")).upper(),
                    iso3=c.get("code_alpha3", c.get("iso3")),
                    name=c.get("name", c.get("country_name", "")),
                    image_url=c.get("image_url", c.get("image", c.get("flag_url"))),
                )
                for c in data
                if c.get("code") or c.get("iso2")
            ],
            key=lambda x: x.name,
        )
        return ListCountriesResponse(countries=countries, total=len(countries))

    async def list_regions(self) -> ListRegionsResponse:
        """List all regions/continents."""
        data = await self._get_regions_raw()

        regions = [
            Region(
                id=str(r.get("id", "")),
                name=r.get("name", r.get("continent_name", "")),
                image_url=r.get("image"),
                countries=[],
            )
            for r in data
        ]
        return ListRegionsResponse(regions=regions, total=len(regions))

    async def list_packages(self, request: ListPackagesRequest) -> ListPackagesResponse:
        """List packages with optional filters."""
        client = await self._ensure_auth()

        if request.country:
            # Get packages for specific country
            countries = await self._get_countries_raw()
            country_id = None
            for c in countries:
                if c.get("iso2") == request.country or c.get("country_iso2") == request.country:
                    country_id = c.get("id")
                    break

            if country_id:
                response = await client.get(
                    f"/developer/reseller/packages/country/{country_id}/DATA-ONLY",
                    provider_name=self.name,
                )
                data = response.get("data", []) if isinstance(response, dict) else response
            else:
                data = []

        elif request.region:
            # Get packages for specific region
            regions = await self._get_regions_raw()
            region_id = None
            for r in regions:
                if r.get("name", "").lower() == request.region.lower() or str(r.get("id")) == request.region:
                    region_id = r.get("id")
                    break

            if region_id:
                response = await client.get(
                    f"/developer/reseller/packages/continent/{region_id}/DATA-ONLY",
                    provider_name=self.name,
                )
                data = response.get("data", []) if isinstance(response, dict) else response
            else:
                data = []
        else:
            # Get all packages
            data = await self._get_all_packages()

        # Parse packages
        packages = [self._parse_package(p) for p in data]

        # Paginate
        start = (request.page - 1) * request.limit
        end = start + request.limit
        paginated = packages[start:end]

        return ListPackagesResponse(
            packages=paginated,
            total=len(packages),
            page=request.page,
            limit=request.limit,
        )

    async def get_package(self, package_id: str) -> GetPackageResponse:
        """Get a single package by ID."""
        client = await self._ensure_auth()

        response = await client.get(
            f"/developer/reseller/package/detail/{package_id}",
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise PackageNotFoundException(f"Package '{package_id}' not found")

        data = response.get("data", response)
        return GetPackageResponse(package=self._parse_package(data))

    def _parse_package(self, pkg: dict[str, Any]) -> Package:
        """Parse esimCard package to unified Package model."""
        # Parse countries
        countries: list[Country] = []
        country_data = pkg.get("countries", [])
        if isinstance(country_data, list):
            for c in country_data:
                if isinstance(c, dict):
                    countries.append(
                        Country(
                            iso2=c.get("iso2", c.get("country_iso2", "")),
                            name=c.get("name", c.get("country_name", "")),
                            image_url=c.get("flag_url", c.get("image")),
                        )
                    )
        elif pkg.get("country_iso2"):
            countries.append(
                Country(
                    iso2=pkg.get("country_iso2", ""),
                    name=pkg.get("country_name", ""),
                )
            )

        # Parse data allowance
        data_amount = pkg.get("data", 0)
        data_unit = pkg.get("data_unit", "GB").upper()

        # Convert to MB
        if data_unit == "GB":
            data_mb = int(data_amount * 1024) if data_amount else None
        elif data_unit == "MB":
            data_mb = int(data_amount) if data_amount else None
        else:
            data_mb = None

        is_unlimited = pkg.get("unlimited_data", False) or data_amount == 0

        data_allowance = DataAllowance(
            amount_mb=data_mb if not is_unlimited else None,
            is_unlimited=is_unlimited,
        )

        # Parse voice allowance
        voice = None
        voice_minutes = pkg.get("voice_minutes", pkg.get("call_minutes", 0))
        if voice_minutes and voice_minutes > 0:
            voice = VoiceAllowance(minutes=voice_minutes, is_included=True)

        # Parse SMS allowance
        sms = None
        sms_count = pkg.get("sms", pkg.get("sms_count", 0))
        if sms_count and sms_count > 0:
            sms = SmsAllowance(count=sms_count, is_included=True)

        # Parse price
        price = parse_price(pkg.get("price", pkg.get("selling_price", 0))) or 0.0

        return Package(
            id=str(pkg.get("id", pkg.get("package_type_id", ""))),
            name=pkg.get("name", pkg.get("package_name", "")),
            description=pkg.get("description"),
            countries=countries,
            is_regional=len(countries) > 1,
            data=data_allowance,
            voice=voice,
            sms=sms,
            validity_days=pkg.get("validity", pkg.get("duration_days", 0)),
            price=price,
            currency=pkg.get("currency", "USD"),
            network_speed=pkg.get("speeds", []),
            is_active=pkg.get("status", True) if isinstance(pkg.get("status"), bool) else True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ORDER METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_order(self, request: CreateOrderRequest) -> CreateOrderResponse:
        """Create an order for eSIM bundles."""
        client = await self._ensure_auth()

        all_esims: list[ESimActivation] = []
        all_items: list[OrderItem] = []
        order_id = ""
        total_price = 0.0

        for item in request.items:
            for _ in range(item.quantity):
                payload: dict[str, Any] = {
                    "package_type_id": item.package_id,
                }

                # If specific ICCID provided (topup existing eSIM)
                if request.iccids:
                    payload["iccid"] = request.iccids[0]

                response = await client.post(
                    "/developer/reseller/package/purchase",
                    json=payload,
                    provider_name=self.name,
                )

                if not response.get("status", False):
                    raise ProviderException(
                        message=response.get("message", "Purchase failed"),
                        provider=self.name,
                        provider_message=str(response),
                    )

                data = response.get("data", response)
                order_id = str(data.get("order_id", data.get("id", "")))

                # Parse eSIM activation details
                esim = ESimActivation(
                    iccid=data.get("iccid", ""),
                    matching_id=data.get("matching_id", data.get("matchingID")),
                    smdp_address=data.get("smdp_address", data.get("smdpAddress")),
                    lpa_string=data.get("lpa_string", data.get("lpa")),
                )
                all_esims.append(esim)

                price = parse_price(data.get("price", data.get("amount", 0))) or 0.0
                total_price += price

            all_items.append(
                OrderItem(
                    package_id=item.package_id,
                    package_name=item.package_name,
                    quantity=item.quantity,
                    price_per_unit=parse_price(item.price_per_unit),
                    esims=all_esims[-item.quantity:],
                )
            )

        order = Order(
            order_id=order_id,
            status="completed",
            items=all_items,
            total=total_price,
            currency="USD",
            assigned=True,
            reference=request.reference,
        )

        return CreateOrderResponse(order=order)

    async def get_order(self, order_id: str) -> GetOrderResponse:
        """Get order details by ID."""
        client = await self._ensure_auth()

        response = await client.get(
            f"/developer/reseller/order/{order_id}",
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ProviderException(
                message=f"Order '{order_id}' not found",
                provider=self.name,
            )

        data = response.get("data", response)
        return GetOrderResponse(order=self._parse_order(data))

    async def list_orders(self, request: ListOrdersRequest) -> ListOrdersResponse:
        """List orders with optional filters."""
        client = await self._ensure_auth()

        params: dict[str, Any] = {
            "page": request.page,
            "per_page": request.limit,
        }

        response = await client.get(
            "/developer/reseller/my-bundles",
            params=params,
            provider_name=self.name,
        )

        if not response.get("status", True):
            return ListOrdersResponse(
                orders=[],
                total=0,
                page=request.page,
                limit=request.limit,
            )

        data = response.get("data", [])
        meta = response.get("meta", {})

        orders = [self._parse_order(o) for o in data]

        return ListOrdersResponse(
            orders=orders,
            total=meta.get("total", len(orders)),
            page=request.page,
            limit=request.limit,
        )

    def _parse_order(self, data: dict[str, Any]) -> Order:
        """Parse esimCard order to unified Order model."""
        esims: list[ESimActivation] = []

        if data.get("iccid"):
            esims.append(
                ESimActivation(
                    iccid=data.get("iccid", ""),
                    matching_id=data.get("matching_id"),
                    smdp_address=data.get("smdp_address"),
                    lpa_string=data.get("lpa_string", data.get("lpa")),
                )
            )

        items: list[OrderItem] = []
        if data.get("package_name") or data.get("package_type_id"):
            items.append(
                OrderItem(
                    package_id=str(data.get("package_type_id", "")),
                    package_name=data.get("package_name"),
                    quantity=1,
                    price_per_unit=parse_price(data.get("price")),
                    esims=esims,
                )
            )

        return Order(
            order_id=str(data.get("order_id", data.get("id", ""))),
            status=data.get("status", "unknown"),
            items=items,
            total=parse_price(data.get("total", data.get("price", 0))) or 0.0,
            currency=data.get("currency", "USD"),
            created_at=parse_datetime(data.get("created_at")),
            assigned=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ESIM MANAGEMENT METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def list_esims(self, request: ListESimsRequest) -> ListESimsResponse:
        """List eSIMs with optional filters."""
        client = await self._ensure_auth()

        params: dict[str, Any] = {
            "page": request.page,
            "per_page": request.limit,
        }

        response = await client.get(
            "/developer/reseller/my-esims",
            params=params,
            provider_name=self.name,
        )

        if not response.get("status", True):
            return ListESimsResponse(
                esims=[],
                total=0,
                page=request.page,
                limit=request.limit,
            )

        data = response.get("data", [])
        meta = response.get("meta", {})

        esims = [self._parse_esim(e) for e in data]

        # Filter by status if provided
        if request.status:
            esims = [e for e in esims if e.status == request.status]

        # Filter by ICCID if provided
        if request.iccid:
            esims = [e for e in esims if request.iccid in e.iccid]

        return ListESimsResponse(
            esims=esims,
            total=meta.get("total", len(esims)),
            page=request.page,
            limit=request.limit,
        )

    async def get_esim(self, iccid: str) -> GetESimResponse:
        """Get eSIM details by ICCID."""
        client = await self._ensure_auth()

        response = await client.get(
            f"/developer/reseller/my-esims/{iccid}",
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ESimNotFoundException(f"eSIM with ICCID '{iccid}' not found")

        data = response.get("data", response)
        return GetESimResponse(esim=self._parse_esim(data))

    async def apply_bundle(self, request: ApplyBundleRequest) -> ApplyBundleResponse:
        """Apply a bundle/package to an eSIM.

        For esimCard, this purchases a new bundle. If ICCID is provided,
        it tops up the existing eSIM. Otherwise, a new eSIM is created.
        """
        client = await self._ensure_auth()

        payload: dict[str, Any] = {
            "package_type_id": request.package_id,
        }

        if request.iccid:
            payload["iccid"] = request.iccid

        response = await client.post(
            "/developer/reseller/package/purchase",
            json=payload,
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ProviderException(
                message=response.get("message", "Failed to apply bundle"),
                provider=self.name,
                provider_message=str(response),
            )

        data = response.get("data", response)

        esim = ESim(
            iccid=data.get("iccid", ""),
            status=ESimStatus.ACTIVE,
            lpa_string=data.get("lpa_string", data.get("lpa")),
            smdp_address=data.get("smdp_address"),
            matching_id=data.get("matching_id"),
            bundles=[],
        )

        return ApplyBundleResponse(
            success=True,
            esims=[esim],
            order_id=str(data.get("order_id", data.get("id", ""))),
        )

    async def list_esim_bundles(self, iccid: str) -> ListESimBundlesResponse:
        """List all bundles assigned to an eSIM."""
        client = await self._ensure_auth()

        response = await client.get(
            f"/developer/reseller/my-esims/{iccid}",
            provider_name=self.name,
        )

        if not response.get("status", False):
            return ListESimBundlesResponse(iccid=iccid, bundles=[], total=0)

        data = response.get("data", response)
        bundles: list[AssignedBundle] = []

        # Parse packages/bundles from eSIM data
        packages = data.get("packages", data.get("bundles", []))
        if isinstance(packages, list):
            for pkg in packages:
                bundles.append(self._parse_assigned_bundle(pkg))
        elif data.get("package_name"):
            # Single package attached
            bundles.append(self._parse_assigned_bundle(data))

        return ListESimBundlesResponse(
            iccid=iccid,
            bundles=bundles,
            total=len(bundles),
        )

    async def get_bundle_status(
        self, iccid: str, bundle_name: str
    ) -> GetBundleStatusResponse:
        """Get status of a specific bundle on an eSIM."""
        bundles_response = await self.list_esim_bundles(iccid)

        for bundle in bundles_response.bundles:
            if bundle.name == bundle_name or bundle.package_id == bundle_name:
                return GetBundleStatusResponse(iccid=iccid, bundle=bundle)

        raise BundleNotFoundException(
            f"Bundle '{bundle_name}' not found on eSIM '{iccid}'"
        )

    def _parse_esim(self, data: dict[str, Any]) -> ESim:
        """Parse esimCard eSIM data to unified ESim model."""
        bundles: list[AssignedBundle] = []

        packages = data.get("packages", data.get("bundles", []))
        if isinstance(packages, list):
            for pkg in packages:
                bundles.append(self._parse_assigned_bundle(pkg))
        elif data.get("package_name"):
            bundles.append(self._parse_assigned_bundle(data))

        status_str = str(data.get("status", "")).lower()

        return ESim(
            iccid=data.get("iccid", ""),
            eid=data.get("eid"),
            imsi=data.get("imsi"),
            status=map_status(status_str, ESIM_STATUS_MAP, ESimStatus.UNUSED),
            lpa_string=data.get("lpa_string", data.get("lpa")),
            smdp_address=data.get("smdp_address"),
            matching_id=data.get("matching_id"),
            created_at=parse_datetime(data.get("created_at")),
            installed_at=parse_datetime(data.get("installed_at")),
            bundles=bundles,
            order_id=str(data.get("order_id", "")) if data.get("order_id") else None,
        )

    def _parse_assigned_bundle(self, data: dict[str, Any]) -> AssignedBundle:
        """Parse bundle data to AssignedBundle model."""
        status_str = str(data.get("status", "")).lower()

        # Parse data remaining
        initial_data = data.get("initial_data_quantity", data.get("data", 0))
        initial_unit = data.get("initial_data_unit", data.get("data_unit", "GB"))
        remaining_data = data.get("rem_data_quantity", data.get("remaining_data", 0))
        remaining_unit = data.get("rem_data_unit", initial_unit)

        # Convert to MB
        def to_mb(amount: Any, unit: str) -> int | None:
            if amount is None:
                return None
            try:
                amt = float(amount)
            except (ValueError, TypeError):
                return None
            if unit.upper() == "GB":
                return int(amt * 1024)
            return int(amt)

        data_total_mb = to_mb(initial_data, initial_unit)
        data_remaining_mb = to_mb(remaining_data, remaining_unit)
        data_used_mb = None
        if data_total_mb is not None and data_remaining_mb is not None:
            data_used_mb = data_total_mb - data_remaining_mb

        return AssignedBundle(
            name=data.get("package_name", data.get("name", "Unknown")),
            package_id=str(data.get("package_type_id", data.get("id", ""))),
            status=map_status(status_str, BUNDLE_STATUS_MAP, BundleStatus.INACTIVE),
            data_total_mb=data_total_mb,
            data_remaining_mb=data_remaining_mb,
            data_used_mb=data_used_mb,
            is_unlimited=data.get("unlimited_data", False),
            start_date=parse_datetime(data.get("start_date", data.get("activated_at"))),
            expiry_date=parse_datetime(data.get("expiry_date", data.get("expires_at"))),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # USAGE METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_usage(
        self, iccid: str, bundle_name: str | None = None
    ) -> GetUsageResponse:
        """Get current usage statistics for an eSIM."""
        client = await self._ensure_auth()

        response = await client.get(
            f"/developer/reseller/my-sim/{iccid}/usage",
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ESimNotFoundException(f"Usage not found for eSIM '{iccid}'")

        data = response.get("data", response)

        # Parse data usage
        initial_data = data.get("initial_data_quantity", 0)
        initial_unit = data.get("initial_data_unit", "GB")
        remaining_data = data.get("rem_data_quantity", 0)
        remaining_unit = data.get("rem_data_unit", initial_unit)

        # Convert to MB
        def to_mb(amount: float, unit: str) -> float:
            if unit.upper() == "GB":
                return amount * 1024
            return amount

        total_mb = to_mb(initial_data, initial_unit) if initial_data else None
        remaining_mb = to_mb(remaining_data, remaining_unit) if remaining_data else None
        used_mb = (total_mb - remaining_mb) if total_mb and remaining_mb else 0

        data_usage = DataUsage(
            used_mb=used_mb,
            remaining_mb=remaining_mb,
            total_mb=total_mb,
            is_unlimited=data.get("unlimited_data", False),
        )

        stats = UsageStats(
            iccid=iccid,
            bundle_name=bundle_name or data.get("package_name"),
            data=data_usage,
        )

        return GetUsageResponse(usage=stats)

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_balance(self) -> GetBalanceResponse:
        """Get current account balance."""
        client = await self._ensure_auth()

        response = await client.get(
            "/developer/reseller/balance",
            provider_name=self.name,
        )

        if not response.get("status", False):
            raise ProviderException(
                message="Failed to get balance",
                provider=self.name,
                provider_message=str(response),
            )

        data = response.get("data", response)

        balance = AccountBalance(
            balance=float(data.get("balance", data.get("amount", 0))),
            currency=data.get("currency", "USD"),
        )

        return GetBalanceResponse(balance=balance)

    async def list_transactions(
        self, request: ListTransactionsRequest
    ) -> ListTransactionsResponse:
        """List account transactions - not supported by esimCard."""
        # esimCard doesn't have a transactions endpoint in the provided API docs
        return ListTransactionsResponse(
            transactions=[],
            total=0,
            page=request.page,
            limit=request.limit,
        )

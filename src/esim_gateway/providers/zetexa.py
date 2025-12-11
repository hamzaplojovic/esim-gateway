"""Zetexa provider implementation."""

import time
from datetime import datetime
from typing import Any

from esim_gateway.core.exceptions import (
    ESimNotFoundException,
    PackageNotFoundException,
    ProviderException,
)
from esim_gateway.core.http import HTTPClient
from esim_gateway.core.utils import MultiCache, parse_datetime, parse_price
from esim_gateway.models.account import (
    AccountBalance,
    GetBalanceResponse,
    ListTransactionsRequest,
    ListTransactionsResponse,
    RefundRequest,
    RefundResponse,
    Transaction,
    TransactionStatus,
    TransactionType,
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

# Status mappings - provider values to unified enums
ESIM_STATUS_MAP: dict[str, ESimStatus] = {
    "completed": ESimStatus.ACTIVE,
    "active": ESimStatus.ACTIVE,
    "enabled": ESimStatus.ACTIVE,
    "installed": ESimStatus.INSTALLED,
    "downloaded": ESimStatus.INSTALLED,
    "disabled": ESimStatus.DISABLED,
    "suspended": ESimStatus.DISABLED,
    "deleted": ESimStatus.DELETED,
}

TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
    "purchase": TransactionType.PURCHASE,
    "refund": TransactionType.REFUND,
    "topup": TransactionType.TOPUP,
    "credit": TransactionType.CREDIT,
    "debit": TransactionType.DEBIT,
}

TRANSACTION_STATUS_MAP: dict[str, TransactionStatus] = {
    "completed": TransactionStatus.COMPLETED,
    "pending": TransactionStatus.PENDING,
    "failed": TransactionStatus.FAILED,
    "cancelled": TransactionStatus.CANCELLED,
    "refunded": TransactionStatus.REFUNDED,
}


class ZetexaProvider(BaseProvider):
    """Zetexa eSIM provider implementation.

    Endpoints:
        Catalog: /v2/Countries-List, /v2/Regions-List, /v2/Packages-List
        Orders: /v2/Create-Order, /v1/Orders-List, /v1/get-qrcode-details
        Usage: /v1/Get-Sim-Usage
        Account: /v1/Reseller/Balance, /v1/Transactions-List, /v1/Plan-Refund
    """

    name = "zetexa"
    base_url_live = "https://api.zetexa.com"
    base_url_sandbox = "https://apistg.zetexa.com"
    TOKEN_TTL = 86400 * 9  # 9 days

    def __init__(
        self,
        api_key: str,
        sandbox: bool = False,
        email: str = "",
        password: str = "",
        reseller_id: str = "",
        access_token: str = "",
    ):
        super().__init__(api_key, sandbox)
        self.email = email
        self.password = password
        self.reseller_id = reseller_id
        self.access_token = access_token
        self.base_url = self.base_url_sandbox if sandbox else self.base_url_live

        # Auth client (AccessToken only)
        self._auth_client = HTTPClient(
            base_url=self.base_url,
            headers={"AccessToken": access_token, "Content-Type": "application/json"},
        )

        # API client (set after auth)
        self._client: HTTPClient | None = None
        self._session_token: str | None = None
        self._session_token_time: float = 0

        # Cache for catalog data
        self._cache = MultiCache(ttl=300)

    async def _ensure_auth(self) -> HTTPClient:
        """Ensure we have valid auth token and return client."""
        now = time.time()
        if self._session_token and (now - self._session_token_time) < self.TOKEN_TTL:
            return self._client  # type: ignore

        # Get new session token
        response = await self._auth_client.post(
            "/v1/Create-Token",
            json={"email": self.email, "password": self.password},
            provider_name=self.name,
        )

        if not response.get("success"):
            raise ProviderException(
                message="Failed to create session token",
                provider=self.name,
                provider_message=str(response),
            )

        self._session_token = response.get("session_token")
        self._session_token_time = now

        # Create API client with both headers
        self._client = HTTPClient(
            base_url=self.base_url,
            headers={
                "AccessToken": self.access_token,
                "Authorization": f"Bearer {self._session_token}",
                "Content-Type": "application/json",
            },
        )
        return self._client

    async def _get_countries(self) -> list[Any]:
        """Get countries with caching."""
        if self._cache.is_valid("countries"):
            return self._cache.get("countries")

        client = await self._ensure_auth()
        response = await client.get("/v2/Countries-List", provider_name=self.name)
        data = response if isinstance(response, list) else response.get("data", [])
        self._cache.set("countries", data)
        return data

    async def _get_regions(self) -> list[Any]:
        """Get regions with caching."""
        if self._cache.is_valid("regions"):
            return self._cache.get("regions")

        client = await self._ensure_auth()
        response = await client.get("/v2/Regions-List", provider_name=self.name)
        data = response if isinstance(response, list) else response.get("data", [])
        self._cache.set("regions", data)
        return data

    async def _get_all_packages(self) -> list[Any]:
        """Get all packages (by region) with caching."""
        if self._cache.is_valid("packages"):
            return self._cache.get("packages")

        regions = await self._get_regions()
        client = await self._ensure_auth()
        all_packages: dict[str, Any] = {}

        for region in regions:
            region_name = region.get("name", "")
            if not region_name:
                continue
            response = await client.get(
                "/v2/Packages-List",
                params={"filterby": "Region", "region_name": region_name},
                provider_name=self.name,
            )
            packages = response if isinstance(response, list) else response.get("data", [])
            for pkg in packages:
                pkg_id = str(pkg.get("package_id", ""))
                if pkg_id and pkg_id not in all_packages:
                    all_packages[pkg_id] = pkg

        result = list(all_packages.values())
        self._cache.set("packages", result)
        return result

    async def _get_countries_lookup(self) -> dict[str, dict[str, Any]]:
        """Build country lookup for enrichment."""
        countries = await self._get_countries()
        return {c.get("iso2", ""): c for c in countries if c.get("iso2")}

    async def list_countries(self) -> ListCountriesResponse:
        """List all countries."""
        data = await self._get_countries()
        countries = sorted(
            [
                Country(
                    iso2=c.get("iso2", ""),
                    iso3=c.get("iso3"),
                    name=c.get("name", ""),
                    image_url=c.get("image"),
                )
                for c in data
            ],
            key=lambda x: x.name,
        )
        return ListCountriesResponse(countries=countries, total=len(countries))

    async def list_regions(self) -> ListRegionsResponse:
        """List all regions."""
        data = await self._get_regions()
        regions = [
            Region(
                id=str(r.get("id", "")),
                name=r.get("name", ""),
                image_url=r.get("image"),
                countries=[],
            )
            for r in data
        ]
        return ListRegionsResponse(regions=regions, total=len(regions))

    async def list_packages(self, request: ListPackagesRequest) -> ListPackagesResponse:
        """List packages with optional filters."""
        lookup = await self._get_countries_lookup()

        if request.country or request.region:
            client = await self._ensure_auth()
            params: dict[str, Any] = {}
            if request.country:
                params["filterby"] = "Country"
                params["country_code"] = request.country
            elif request.region:
                params["filterby"] = "Region"
                params["region_name"] = request.region

            response = await client.get(
                "/v2/Packages-List", params=params, provider_name=self.name
            )
            data = response if isinstance(response, list) else response.get("data", [])
        else:
            data = await self._get_all_packages()

        packages = [self._parse_package(p, lookup) for p in data]

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
        """Get single package by ID."""
        lookup = await self._get_countries_lookup()
        packages = await self._get_all_packages()

        for pkg in packages:
            if str(pkg.get("package_id")) == package_id:
                return GetPackageResponse(package=self._parse_package(pkg, lookup))

        raise PackageNotFoundException(f"Package '{package_id}' not found")

    def _parse_package(
        self, pkg: dict[str, Any], lookup: dict[str, dict[str, Any]]
    ) -> Package:
        """Parse package with country enrichment."""
        # Parse countries with enrichment
        countries = []
        for c in pkg.get("countries", []):
            iso2 = c.get("countryiso2", "")
            name = c.get("countryname", "")
            iso3 = image = None
            if iso2 in lookup:
                full = lookup[iso2]
                iso3 = full.get("iso3")
                image = full.get("image")
                name = full.get("name") or name
            countries.append(Country(iso2=iso2, iso3=iso3, name=name, image_url=image))

        # Parse allowances
        data_mb = pkg.get("data_in_mb", 0)
        data_str = pkg.get("data", "")
        is_unlimited = data_str == "Unlimited" or data_mb == 0

        data = DataAllowance(
            amount_mb=data_mb if not is_unlimited else None,
            is_unlimited=is_unlimited,
            fup_policy=pkg.get("fup_policy"),
        )

        voice = None
        if pkg.get("call", 0) > 0:
            voice = VoiceAllowance(minutes=pkg["call"], is_included=True)

        sms = None
        if pkg.get("sms", 0) > 0:
            sms = SmsAllowance(count=pkg["sms"], is_included=True)

        return Package(
            id=str(pkg.get("package_id", "")),
            name=pkg.get("package_name", ""),
            countries=countries,
            is_regional=len(countries) > 1,
            data=data,
            voice=voice,
            sms=sms,
            validity_days=pkg.get("validity", 0),
            price=float(pkg.get("price", 0)),
            currency="USD",
            network_speed=[pkg["coverage"]] if pkg.get("coverage") else [],
            networks=[pkg["network"]] if pkg.get("network") else [],
            is_active=pkg.get("status", True),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ORDER METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_order(self, request: CreateOrderRequest) -> CreateOrderResponse:
        """Create an order for eSIM bundles."""
        client = await self._ensure_auth()

        if not request.customer:
            raise ProviderException(
                message="Customer info required for Zetexa orders",
                provider=self.name,
            )

        # Zetexa creates one order per item, we'll batch them
        all_orders = []
        for item in request.items:
            payload: dict[str, Any] = {
                "package_id": item.package_id,
                "quantity": item.quantity,
                "email": request.customer.email,
                "first_name": request.customer.first_name or "",
                "last_name": request.customer.last_name or "",
                "country": request.customer.country or "US",
            }

            if request.customer.phone:
                payload["phone_number"] = request.customer.phone
            if request.customer.address:
                payload["address"] = request.customer.address
            if request.customer.city:
                payload["city"] = request.customer.city
            if request.customer.state:
                payload["state"] = request.customer.state
            if request.customer.postal_code:
                payload["pincode"] = request.customer.postal_code
            if request.reference:
                payload["reseller_orderid"] = request.reference
            if request.iccids:
                payload["iccid"] = request.iccids[0]

            response = await client.post(
                "/v2/Create-Order", json=payload, provider_name=self.name
            )

            if not response.get("success"):
                raise ProviderException(
                    message=response.get("message", "Order creation failed"),
                    provider=self.name,
                    provider_message=str(response),
                )

            all_orders.append(response)

        # Parse combined response
        order = self._parse_zetexa_order(all_orders[0] if len(all_orders) == 1 else all_orders)
        return CreateOrderResponse(order=order)

    async def get_order(self, order_id: str) -> GetOrderResponse:
        """Get order details - Zetexa uses QR code endpoint for order details."""
        client = await self._ensure_auth()
        response = await client.get(
            "/v1/get-qrcode-details",
            params={"order_id": order_id},
            provider_name=self.name,
        )

        if not response.get("success", True):
            raise ProviderException(
                message=response.get("message", "Order not found"),
                provider=self.name,
            )

        return GetOrderResponse(order=self._parse_qrcode_response(order_id, response))

    async def list_orders(self, request: ListOrdersRequest) -> ListOrdersResponse:
        """List orders using /v1/Orders-List endpoint."""
        client = await self._ensure_auth()

        params: dict[str, Any] = {
            "page": request.page,
            "page_size": request.limit,
        }

        response = await client.get(
            "/v1/Orders-List", params=params, provider_name=self.name
        )

        if not response.get("success", True):
            return ListOrdersResponse(
                orders=[],
                total=0,
                page=request.page,
                limit=request.limit,
            )

        orders_data = response.get("data", [])
        orders = [self._parse_order_list_item(o) for o in orders_data]

        return ListOrdersResponse(
            orders=orders,
            total=response.get("total_records"),
            page=request.page,
            limit=request.limit,
        )

    def _parse_zetexa_order(self, data: dict[str, Any] | list[Any]) -> Order:
        """Parse order from Zetexa create response."""
        if isinstance(data, list):
            data = data[0]

        items = []
        for sim in data.get("sims", []):
            lpa = sim.get("lpa_server", "")
            esim = ESimActivation(
                iccid=sim.get("iccid", ""),
                matching_id=sim.get("matchingID"),
                smdp_address=sim.get("smdpAddress"),
                lpa_string=lpa if lpa else None,
            )
            items.append(
                OrderItem(
                    package_id="",
                    package_name=sim.get("package_name"),
                    quantity=1,
                    price_per_unit=parse_price(sim.get("unit_price_net_amount")),
                    esims=[esim],
                )
            )

        return Order(
            order_id=data.get("order_id", ""),
            status=data.get("status", "unknown"),
            items=items,
            total=parse_price(data.get("total")) or 0.0,
            currency="USD",
            assigned=data.get("status") == "Completed",
        )

    def _parse_qrcode_response(self, order_id: str, data: dict[str, Any]) -> Order:
        """Parse order from QR code details response."""
        lpa = data.get("lpa_server", "")
        esim = ESimActivation(
            iccid=data.get("iccid", ""),
            matching_id=data.get("matchingID"),
            smdp_address=data.get("smdpAddress"),
            lpa_string=lpa if lpa else None,
        )

        item = OrderItem(
            package_id="",
            package_name=data.get("package_name"),
            quantity=1,
            esims=[esim],
        )

        return Order(
            order_id=order_id,
            status=data.get("status", "unknown"),
            items=[item],
            total=0.0,
            currency="USD",
            assigned=True,
        )

    def _parse_order_list_item(self, data: dict[str, Any]) -> Order:
        """Parse order from Orders-List response."""
        return Order(
            order_id=data.get("order_id", ""),
            status=data.get("order_status", "unknown"),
            items=[],  # Orders-List doesn't include item details
            total=parse_price(data.get("total_value")) or 0.0,
            currency=data.get("currency", "USD"),
            created_at=parse_datetime(data.get("created_on")),
            assigned=data.get("order_status") == "Completed",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ESIM MANAGEMENT METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def list_esims(self, request: ListESimsRequest) -> ListESimsResponse:
        """List eSIMs - Zetexa doesn't have direct eSIM list, aggregated from orders."""
        client = await self._ensure_auth()

        params: dict[str, Any] = {
            "page": request.page,
            "page_size": request.limit,
        }

        if request.order_id:
            params["order_id"] = request.order_id

        response = await client.get(
            "/v1/Orders-List", params=params, provider_name=self.name
        )

        if not response.get("success", True):
            return ListESimsResponse(
                esims=[],
                total=0,
                page=request.page,
                limit=request.limit,
            )

        orders_data = response.get("data", [])
        esims: list[ESim] = []

        for order in orders_data:
            iccid = order.get("iccid")
            if iccid:
                esims.append(
                    ESim(
                        iccid=iccid,
                        status=self._map_esim_status(order.get("order_status", "")),
                        provider_esim_id=order.get("order_id"),
                        created_at=parse_datetime(order.get("created_on")),
                        assigned_bundles=[],
                    )
                )

        return ListESimsResponse(
            esims=esims,
            total=response.get("total_records"),
            page=request.page,
            limit=request.limit,
        )

    async def get_esim(self, iccid: str) -> GetESimResponse:
        """Get eSIM details by ICCID using QR code endpoint."""
        client = await self._ensure_auth()

        response = await client.get(
            "/v1/get-qrcode-details",
            params={"iccid": iccid},
            provider_name=self.name,
        )

        if not response.get("success", True):
            raise ESimNotFoundException(f"eSIM with ICCID '{iccid}' not found")

        return GetESimResponse(esim=self._parse_esim_detail(response))

    async def apply_bundle(self, request: ApplyBundleRequest) -> ApplyBundleResponse:
        """Apply bundle to eSIM - Zetexa creates new order/eSIM per bundle."""
        client = await self._ensure_auth()

        payload: dict[str, Any] = {
            "package_id": request.package_id,
            "quantity": request.quantity,
        }

        if request.iccid:
            payload["iccid"] = request.iccid

        if request.email:
            payload["email"] = request.email

        response = await client.post(
            "/v2/Create-Order", json=payload, provider_name=self.name
        )

        if not response.get("success"):
            raise ProviderException(
                message=response.get("message", "Failed to apply bundle"),
                provider=self.name,
                provider_message=str(response),
            )

        esims: list[ESim] = []
        for sim in response.get("sims", []):
            esim = ESim(
                iccid=sim.get("iccid", ""),
                status=ESimStatus.ACTIVE,
                lpa_string=sim.get("lpa_server"),
                smdp_address=sim.get("smdpAddress"),
                matching_id=sim.get("matchingID"),
                assigned_bundles=[],
            )
            esims.append(esim)

        return ApplyBundleResponse(
            success=True,
            esims=esims,
            order_id=response.get("order_id"),
        )

    async def list_esim_bundles(self, iccid: str) -> ListESimBundlesResponse:
        """List bundles on an eSIM - derived from usage data."""
        client = await self._ensure_auth()

        response = await client.post(
            "/v1/Get-Sim-Usage",
            json={"iccid": iccid},
            provider_name=self.name,
        )

        if not response.get("success", True):
            return ListESimBundlesResponse(bundles=[], iccid=iccid)

        bundles: list[AssignedBundle] = []
        usage_data = response.get("data", {})

        if usage_data:
            bundle = AssignedBundle(
                name=usage_data.get("package_name", "Unknown"),
                package_id=usage_data.get("package_id", ""),
                status=self._map_bundle_status(usage_data),
                initial_data_mb=usage_data.get("total_data_mb"),
                data_remaining_mb=usage_data.get("remaining_data_mb"),
                is_unlimited=usage_data.get("total_data_mb") == 0,
            )
            bundles.append(bundle)

        return ListESimBundlesResponse(bundles=bundles, iccid=iccid)

    async def get_bundle_status(
        self, iccid: str, bundle_name: str
    ) -> GetBundleStatusResponse:
        """Get status of a specific bundle on an eSIM."""
        bundles_response = await self.list_esim_bundles(iccid)

        for bundle in bundles_response.bundles:
            if bundle.name == bundle_name or bundle.package_id == bundle_name:
                return GetBundleStatusResponse(bundle=bundle, iccid=iccid)

        return GetBundleStatusResponse(
            bundle=AssignedBundle(
                name=bundle_name,
                package_id=bundle_name,
                status=BundleStatus.INACTIVE,
            ),
            iccid=iccid,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # USAGE METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_usage(
        self, iccid: str, bundle_name: str | None = None
    ) -> GetUsageResponse:
        """Get current usage statistics for an eSIM."""
        client = await self._ensure_auth()

        response = await client.post(
            "/v1/Get-Sim-Usage",
            json={"iccid": iccid},
            provider_name=self.name,
        )

        if not response.get("success", True):
            raise ESimNotFoundException(f"Usage not found for ICCID '{iccid}'")

        usage_data = response.get("data", {})

        total_mb = usage_data.get("total_data_mb", 0)
        remaining_mb = usage_data.get("remaining_data_mb", 0)
        used_mb = total_mb - remaining_mb if total_mb > 0 else 0

        data_usage = DataUsage(
            used_mb=used_mb,
            remaining_mb=remaining_mb if total_mb > 0 else None,
            total_mb=total_mb if total_mb > 0 else None,
            is_unlimited=total_mb == 0,
        )

        stats = UsageStats(
            iccid=iccid,
            data=data_usage,
            bundle_name=usage_data.get("package_name"),
        )

        return GetUsageResponse(usage=stats)

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_balance(self) -> GetBalanceResponse:
        """Get current account balance."""
        client = await self._ensure_auth()

        response = await client.post(
            "/v1/Reseller/Balance",
            json={"reseller_id": self.reseller_id},
            provider_name=self.name,
        )

        if not response.get("success", True):
            raise ProviderException(
                message="Failed to get balance",
                provider=self.name,
                provider_message=str(response),
            )

        balance = AccountBalance(
            balance=float(response.get("balance", 0)),
            currency=response.get("currency", "USD"),
        )

        return GetBalanceResponse(balance=balance)

    async def list_transactions(
        self, request: ListTransactionsRequest
    ) -> ListTransactionsResponse:
        """List account transactions."""
        client = await self._ensure_auth()

        params: dict[str, Any] = {
            "page": request.page,
            "page_size": request.limit,
        }

        if request.start_date:
            params["start_date"] = request.start_date.strftime("%Y-%m-%d")
        if request.end_date:
            params["end_date"] = request.end_date.strftime("%Y-%m-%d")

        response = await client.get(
            "/v1/Transactions-List", params=params, provider_name=self.name
        )

        if not response.get("success", True):
            return ListTransactionsResponse(
                transactions=[],
                total=0,
                page=request.page,
                limit=request.limit,
            )

        transactions_data = response.get("data", [])
        transactions: list[Transaction] = []

        for txn in transactions_data:
            transactions.append(self._parse_transaction(txn))

        return ListTransactionsResponse(
            transactions=transactions,
            total=response.get("total_records"),
            page=request.page,
            limit=request.limit,
        )

    async def request_refund(self, request: RefundRequest) -> RefundResponse:
        """Request a refund for an order or bundle."""
        client = await self._ensure_auth()

        payload: dict[str, Any] = {}

        if request.order_id:
            payload["order_id"] = request.order_id
        if request.iccid:
            payload["iccid"] = request.iccid
        if request.reason:
            payload["reason"] = request.reason

        response = await client.post(
            "/v1/Plan-Refund", json=payload, provider_name=self.name
        )

        success = response.get("success", False)

        return RefundResponse(
            success=success,
            refund_id=response.get("refund_id"),
            amount=parse_price(response.get("amount")),
            currency=response.get("currency"),
            message=response.get("message"),
            new_balance=parse_price(response.get("new_balance")),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_esim_detail(self, data: dict[str, Any]) -> ESim:
        """Parse eSIM from QR code details response."""
        bundles: list[AssignedBundle] = []

        if data.get("package_name"):
            bundles.append(
                AssignedBundle(
                    name=data.get("package_name", ""),
                    package_id=data.get("package_id", ""),
                    status=self._map_bundle_status(data),
                )
            )

        return ESim(
            iccid=data.get("iccid", ""),
            status=self._map_esim_status(data.get("status", "")),
            lpa_string=data.get("lpa_server"),
            smdp_address=data.get("smdpAddress"),
            matching_id=data.get("matchingID"),
            assigned_bundles=bundles,
        )

    def _map_esim_status(self, status: str) -> ESimStatus:
        """Map Zetexa status to unified ESimStatus."""
        return ESIM_STATUS_MAP.get(status.lower(), ESimStatus.UNUSED)

    def _map_bundle_status(self, data: dict[str, Any]) -> BundleStatus:
        """Map bundle data to BundleStatus."""
        status = data.get("status", "").lower()
        remaining = data.get("remaining_data_mb", 0)

        if status == "expired" or remaining == 0:
            return BundleStatus.EXPIRED
        elif status in ("active", "enabled"):
            return BundleStatus.ACTIVE
        return BundleStatus.INACTIVE

    def _parse_transaction(self, data: dict[str, Any]) -> Transaction:
        """Parse transaction from Zetexa response."""
        txn_type = data.get("type", "").lower()
        status_str = data.get("status", "").lower()

        return Transaction(
            id=data.get("transaction_id", ""),
            type=TRANSACTION_TYPE_MAP.get(txn_type, TransactionType.DEBIT),
            status=TRANSACTION_STATUS_MAP.get(status_str, TransactionStatus.COMPLETED),
            amount=parse_price(data.get("amount")) or 0.0,
            currency=data.get("currency", "USD"),
            order_id=data.get("order_id"),
            reference=data.get("reference"),
            description=data.get("description"),
            created_at=parse_datetime(data.get("created_on")) or datetime.now(),
        )

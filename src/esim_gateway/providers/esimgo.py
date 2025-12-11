"""eSIM Go provider implementation."""

from typing import Any

from esim_gateway.core.exceptions import (
    ESimNotFoundException,
    OrderNotFoundException,
    PackageNotFoundException,
)
from esim_gateway.core.http import HTTPClient
from esim_gateway.core.utils import TTLCache, map_status, parse_datetime
from esim_gateway.models.account import (
    AccountBalance,
    GetBalanceResponse,
    ListTransactionsRequest,
    ListTransactionsResponse,
    RefundRequest,
    RefundResponse,
)
from esim_gateway.models.catalog import (
    Country,
    DataAllowance,
    GetPackageResponse,
    ListCountriesResponse,
    ListPackagesRequest,
    ListPackagesResponse,
    ListRegionsResponse,
    Network,
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
    ESimHistory,
    ESimStatus,
    GetBundleStatusResponse,
    GetESimHistoryResponse,
    GetESimResponse,
    ListESimBundlesResponse,
    ListESimsRequest,
    ListESimsResponse,
    RevokeBundleRequest,
    RevokeBundleResponse,
)
from esim_gateway.models.inventory import (
    AssignmentInfo,
    BundleGroup,
    BundleGroupType,
    InventoryItem,
    InventorySummary,
    InventoryType,
    ListAssignmentsRequest,
    ListAssignmentsResponse,
    ListBundleGroupsResponse,
    ListInventoryRequest,
    ListInventoryResponse,
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
    "NEW": ESimStatus.UNUSED,
    "RELEASED": ESimStatus.UNUSED,
    "BPP_INSTALLATION": ESimStatus.INSTALLED,
    "ENABLE": ESimStatus.ACTIVE,
    "DISABLE": ESimStatus.DISABLED,
    "DELETED": ESimStatus.DELETED,
}

BUNDLE_STATUS_MAP: dict[str, BundleStatus] = {
    "ACTIVE": BundleStatus.ACTIVE,
    "INACTIVE": BundleStatus.INACTIVE,
    "EXPIRED": BundleStatus.EXPIRED,
    "DEPLETED": BundleStatus.DEPLETED,
}

BUNDLE_GROUP_TYPE_MAP: dict[str, BundleGroupType] = {
    "regional": BundleGroupType.REGIONAL,
    "global": BundleGroupType.GLOBAL,
}


class ESimGoProvider(BaseProvider):
    """eSIM Go provider implementation."""

    name = "esimgo"
    base_url = "https://api.esim-go.com/v2.5"

    def __init__(self, api_key: str, sandbox: bool = False):
        super().__init__(api_key, sandbox)
        self._client = HTTPClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
        )
        self._catalog_cache = TTLCache(ttl=300)

    async def _get_catalog(self) -> dict[str, Any]:
        """Get full catalog with caching."""
        if self._catalog_cache.is_valid():
            cached = self._catalog_cache.get()
            return dict(cached) if cached else {}

        response = await self._client.get(
            "/catalogue", params={"perPage": 1000}, provider_name=self.name
        )
        self._catalog_cache.set(response)
        return dict(response)

    # ─────────────────────────────────────────────────────────────────────────
    # CATALOG
    # ─────────────────────────────────────────────────────────────────────────

    async def list_countries(self) -> ListCountriesResponse:
        """List countries extracted from catalog bundles."""
        response = await self._get_catalog()
        bundles = response.get("bundles", [])

        # Extract unique countries
        countries_map: dict[str, Country] = {}
        for bundle in bundles:
            for c in bundle.get("countries", []):
                iso2 = c.get("iso", "")
                if iso2 and iso2 not in countries_map:
                    countries_map[iso2] = Country(
                        iso2=iso2,
                        name=c.get("name", ""),
                        region=c.get("region"),
                    )

        countries = sorted(countries_map.values(), key=lambda x: x.name)
        return ListCountriesResponse(countries=countries, total=len(countries))

    async def list_regions(self) -> ListRegionsResponse:
        """List regions extracted from catalog bundles."""
        response = await self._get_catalog()
        bundles = response.get("bundles", [])

        # Extract unique regions with their countries
        regions_map: dict[str, set[str]] = {}
        for bundle in bundles:
            for c in bundle.get("countries", []):
                region_name = c.get("region")
                iso2 = c.get("iso", "")
                if region_name and iso2:
                    if region_name not in regions_map:
                        regions_map[region_name] = set()
                    regions_map[region_name].add(iso2)

        regions = [
            Region(
                id=name.lower().replace(" ", "_"),
                name=name,
                countries=sorted(countries),
            )
            for name, countries in sorted(regions_map.items())
        ]
        return ListRegionsResponse(regions=regions, total=len(regions))

    async def list_packages(self, request: ListPackagesRequest) -> ListPackagesResponse:
        """List packages with filters."""
        params: dict[str, Any] = {"page": request.page, "perPage": request.limit}
        if request.country:
            params["countries"] = request.country
        if request.region:
            params["region"] = request.region

        response = await self._client.get("/catalogue", params=params, provider_name=self.name)
        packages = [self._parse_package(b) for b in response.get("bundles", [])]

        return ListPackagesResponse(
            packages=packages,
            total=response.get("total"),
            page=request.page,
            limit=request.limit,
        )

    async def get_package(self, package_id: str) -> GetPackageResponse:
        """Get single package by ID."""
        try:
            response = await self._client.get(
                f"/catalogue/bundle/{package_id}", provider_name=self.name
            )
        except Exception as e:
            if "404" in str(e):
                raise PackageNotFoundException(f"Package '{package_id}' not found") from e
            raise

        bundle = response.get("bundle", response)
        return GetPackageResponse(package=self._parse_package_detail(bundle))

    def _parse_package(self, bundle: dict[str, Any]) -> Package:
        """Parse package from catalog listing."""
        countries = [self._parse_country(c) for c in bundle.get("countries", [])]
        roaming = [self._parse_country(c) for c in bundle.get("roamingEnabled", [])]
        data, voice, sms = self._parse_allowances(bundle)

        return Package(
            id=bundle.get("name", ""),
            name=bundle.get("description", ""),
            description=bundle.get("description"),
            countries=countries,
            roaming_countries=roaming,
            is_regional=len(countries) > 1 or len(roaming) > 1,
            data=data,
            voice=voice,
            sms=sms,
            validity_days=bundle.get("duration", 0),
            price=float(bundle.get("price", 0)),
            currency="USD",
            billing_type=bundle.get("billingType"),
            network_speed=self._parse_speed(bundle.get("speed")),
            autostart=bundle.get("autostart", False),
            is_active=True,
            groups=bundle.get("groups", []),
            image_url=bundle.get("imageUrl"),
        )

    def _parse_package_detail(self, bundle: dict[str, Any]) -> Package:
        """Parse package from detail endpoint (includes networks)."""
        countries = []
        for c in bundle.get("countries", []):
            if "country" in c:
                inner = c["country"]
                networks = [
                    Network(
                        name=n.get("name", ""),
                        brand_name=n.get("brandName"),
                        speeds=n.get("speeds", []),
                    )
                    for n in c.get("networks", [])
                ]
                countries.append(
                    Country(
                        iso2=inner.get("iso", ""),
                        name=inner.get("name", ""),
                        region=inner.get("region"),
                        networks=networks,
                    )
                )
            else:
                countries.append(self._parse_country(c))

        roaming = []
        for c in bundle.get("roamingEnabled", []):
            if "country" in c:
                inner = c["country"]
                networks = [
                    Network(
                        name=n.get("name", ""),
                        brand_name=n.get("brandName"),
                        speeds=n.get("speeds", []),
                    )
                    for n in c.get("networks", [])
                ]
                roaming.append(
                    Country(
                        iso2=inner.get("iso", ""),
                        name=inner.get("name", ""),
                        region=inner.get("region"),
                        networks=networks,
                    )
                )
            else:
                roaming.append(self._parse_country(c))

        data, voice, sms = self._parse_allowances(bundle)

        return Package(
            id=bundle.get("name", ""),
            name=bundle.get("description", ""),
            description=bundle.get("description"),
            countries=countries,
            roaming_countries=roaming,
            is_regional=len(countries) > 1 or len(roaming) > 1,
            data=data,
            voice=voice,
            sms=sms,
            validity_days=bundle.get("duration", 0),
            price=float(bundle.get("price", 0)),
            currency="USD",
            billing_type=bundle.get("billingType"),
            network_speed=self._parse_speed(bundle.get("speed")),
            autostart=bundle.get("autostart", False),
            is_active=True,
            groups=bundle.get("groups", []),
            image_url=bundle.get("imageUrl"),
        )

    def _parse_country(self, data: dict[str, Any]) -> Country:
        """Parse country from simple format."""
        return Country(
            iso2=data.get("iso", ""),
            name=data.get("name", ""),
            region=data.get("region"),
        )

    def _parse_allowances(
        self, bundle: dict[str, Any]
    ) -> tuple[DataAllowance, VoiceAllowance | None, SmsAllowance | None]:
        """Parse data/voice/sms allowances."""
        data = DataAllowance(
            amount_mb=bundle.get("dataAmount"),
            is_unlimited=bundle.get("unlimited", False),
        )
        voice = sms = None
        for a in bundle.get("allowances", []):
            t = a.get("type", "").upper()
            if t == "VOICE":
                voice = VoiceAllowance(
                    minutes=a.get("amount"),
                    is_unlimited=a.get("unlimited", False),
                    is_included=True,
                )
            elif t == "SMS":
                sms = SmsAllowance(
                    count=a.get("amount"),
                    is_unlimited=a.get("unlimited", False),
                    is_included=True,
                )
        return data, voice, sms

    def _parse_speed(self, speed: Any) -> list[str]:
        """Parse network speed from various formats."""
        if isinstance(speed, dict):
            return list(speed.get("speeds", []))
        if isinstance(speed, list):
            return list(speed)
        if isinstance(speed, str) and speed:
            return [speed]
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # ORDERS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_order(self, request: CreateOrderRequest) -> CreateOrderResponse:
        """Create an order for eSIM bundles."""
        order_type = "validate" if self.sandbox else "transaction"

        order_items = []
        for item in request.items:
            order_item: dict[str, Any] = {
                "type": "bundle",
                "item": item.package_id,
                "quantity": item.quantity,
                "allowReassign": request.allow_reassign,
            }
            if request.iccids:
                order_item["iccids"] = request.iccids
            order_items.append(order_item)

        payload = {
            "type": order_type,
            "assign": request.assign,
            "order": order_items,
        }

        response = await self._client.post("/orders", json=payload, provider_name=self.name)
        return CreateOrderResponse(order=self._parse_order(response))

    async def get_order(self, order_id: str) -> GetOrderResponse:
        """Get order details by reference."""
        try:
            response = await self._client.get(f"/orders/{order_id}", provider_name=self.name)
        except Exception as e:
            if "404" in str(e):
                raise OrderNotFoundException(f"Order '{order_id}' not found") from e
            raise
        return GetOrderResponse(order=self._parse_order(response))

    async def list_orders(self, request: ListOrdersRequest) -> ListOrdersResponse:
        """List orders with optional filters."""
        params: dict[str, Any] = {
            "includeIccids": request.include_esims,
            "page": request.page,
            "limit": request.limit,
        }

        if request.created_after:
            params["createdAt"] = f"gte:{request.created_after.isoformat()}"
        if request.created_before:
            existing = params.get("createdAt", "")
            sep = "&" if existing else ""
            params["createdAt"] = f"{existing}{sep}lte:{request.created_before.isoformat()}"

        response = await self._client.get("/orders", params=params, provider_name=self.name)

        orders = [self._parse_order(o) for o in response.get("orders", []) if o]

        return ListOrdersResponse(
            orders=orders,
            total=response.get("rows"),
            page=request.page,
            limit=request.limit,
        )

    def _parse_order(self, data: dict[str, Any]) -> Order:
        """Parse order from API response."""
        items = []
        for item in data.get("order", []):
            esims = [
                ESimActivation(
                    iccid=e.get("iccid", ""),
                    matching_id=e.get("matchingId"),
                    smdp_address=e.get("smdpAddress"),
                )
                for e in item.get("esims", [])
            ]
            items.append(
                OrderItem(
                    package_id=item.get("item", ""),
                    package_name=item.get("item"),
                    quantity=item.get("quantity", 1),
                    price_per_unit=item.get("pricePerUnit"),
                    subtotal=item.get("subTotal"),
                    esims=esims,
                )
            )

        return Order(
            order_id=data.get("orderReference", ""),
            status=data.get("status", "unknown"),
            status_message=data.get("statusMessage"),
            items=items,
            total=float(data.get("total", 0)),
            currency=data.get("currency", "USD"),
            created_at=parse_datetime(data.get("createdDate")),
            assigned=data.get("assigned", False),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ESIM MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    async def list_esims(self, request: ListESimsRequest) -> ListESimsResponse:
        """List eSIMs with optional filters."""
        params: dict[str, Any] = {"page": request.page, "perPage": request.limit}
        if request.iccid:
            params["iccid"] = request.iccid

        response = await self._client.get("/esims", params=params, provider_name=self.name)

        esims = [self._parse_esim(e) for e in response.get("esims", [])]

        return ListESimsResponse(
            esims=esims,
            total=response.get("total"),
            page=request.page,
            limit=request.limit,
        )

    async def get_esim(self, iccid: str) -> GetESimResponse:
        """Get eSIM details by ICCID."""
        try:
            response = await self._client.get(f"/esims/{iccid}", provider_name=self.name)
        except Exception as e:
            if "404" in str(e):
                raise ESimNotFoundException(f"eSIM '{iccid}' not found") from e
            raise

        esim = response.get("esim", response)
        return GetESimResponse(esim=self._parse_esim_detail(esim))

    async def apply_bundle(self, request: ApplyBundleRequest) -> ApplyBundleResponse:
        """Apply a bundle to an eSIM."""
        payload: dict[str, Any] = {
            "type": "validate" if self.sandbox else "transaction",
            "assign": True,
            "order": [
                {
                    "type": "bundle",
                    "item": request.package_id,
                    "quantity": request.quantity,
                }
            ],
        }

        if request.iccid:
            payload["order"][0]["iccids"] = [request.iccid]

        response = await self._client.post("/esims/apply", json=payload, provider_name=self.name)

        esims = []
        for item in response.get("order", []):
            for e in item.get("esims", []):
                esims.append(
                    ESim(
                        iccid=e.get("iccid", ""),
                        lpa_string=e.get("lpaString"),
                        smdp_address=e.get("smdpAddress"),
                        matching_id=e.get("matchingId"),
                        status=ESimStatus.ACTIVE,
                    )
                )

        return ApplyBundleResponse(
            success=True,
            esims=esims,
            order_id=response.get("orderReference"),
        )

    async def list_esim_bundles(self, iccid: str) -> ListESimBundlesResponse:
        """List all bundles assigned to an eSIM."""
        try:
            response = await self._client.get(f"/esims/{iccid}/bundles", provider_name=self.name)
        except Exception as e:
            if "404" in str(e):
                raise ESimNotFoundException(f"eSIM '{iccid}' not found") from e
            raise

        bundles = [self._parse_bundle(b) for b in response.get("bundles", [])]

        return ListESimBundlesResponse(
            iccid=iccid,
            bundles=bundles,
            total=len(bundles),
        )

    async def get_bundle_status(self, iccid: str, bundle_name: str) -> GetBundleStatusResponse:
        """Get status of a specific bundle on an eSIM."""
        try:
            response = await self._client.get(
                f"/esims/{iccid}/bundles/{bundle_name}", provider_name=self.name
            )
        except Exception as e:
            if "404" in str(e):
                raise ESimNotFoundException(
                    f"Bundle '{bundle_name}' not found on eSIM '{iccid}'"
                ) from e
            raise

        bundle = response.get("bundle", response)
        return GetBundleStatusResponse(
            iccid=iccid,
            bundle=self._parse_bundle(bundle),
        )

    async def revoke_bundle(
        self, iccid: str, bundle_name: str, request: RevokeBundleRequest
    ) -> RevokeBundleResponse:
        """Revoke a bundle from an eSIM."""
        try:
            response = await self._client.delete(
                f"/esims/{iccid}/bundles/{bundle_name}", provider_name=self.name
            )
        except Exception as e:
            if "404" in str(e):
                raise ESimNotFoundException(
                    f"Bundle '{bundle_name}' not found on eSIM '{iccid}'"
                ) from e
            raise

        return RevokeBundleResponse(
            success=True,
            message=response.get("message", "Bundle revoked successfully"),
            refund_amount=response.get("refundAmount"),
            refund_currency=response.get("currency"),
        )

    async def get_esim_history(self, iccid: str) -> GetESimHistoryResponse:
        """Get eSIM lifecycle history."""
        try:
            response = await self._client.get(f"/esims/{iccid}/history", provider_name=self.name)
        except Exception as e:
            if "404" in str(e):
                raise ESimNotFoundException(f"eSIM '{iccid}' not found") from e
            raise

        history = [self._parse_history(h) for h in response.get("history", [])]

        return GetESimHistoryResponse(
            iccid=iccid,
            history=history,
            total=len(history),
        )

    def _parse_esim(self, data: dict[str, Any]) -> ESim:
        """Parse eSIM from list response."""
        return ESim(
            iccid=data.get("iccid", ""),
            eid=data.get("eid"),
            status=map_status(data.get("status", ""), ESIM_STATUS_MAP, ESimStatus.UNUSED),
            lpa_string=data.get("lpaString"),
            smdp_address=data.get("smdpAddress"),
            matching_id=data.get("matchingId"),
            created_at=parse_datetime(data.get("createdDate")),
        )

    def _parse_esim_detail(self, data: dict[str, Any]) -> ESim:
        """Parse eSIM from detail response (includes bundles)."""
        esim = self._parse_esim(data)
        esim.bundles = [self._parse_bundle(b) for b in data.get("bundles", [])]
        return esim

    def _parse_bundle(self, data: dict[str, Any]) -> AssignedBundle:
        """Parse an assigned bundle."""
        initial = data.get("initialAmount")
        remaining = data.get("remainingAmount")
        used = (initial or 0) - (remaining or 0) if initial is not None else None

        return AssignedBundle(
            name=data.get("name", ""),
            package_id=data.get("name", ""),
            status=map_status(data.get("status", ""), BUNDLE_STATUS_MAP, BundleStatus.INACTIVE),
            data_total_mb=initial,
            data_remaining_mb=remaining,
            data_used_mb=used,
            is_unlimited=data.get("unlimited", False),
            start_date=parse_datetime(data.get("startTime")),
            expiry_date=parse_datetime(data.get("expiryTime")),
        )

    def _parse_history(self, data: dict[str, Any]) -> ESimHistory:
        """Parse eSIM history event."""
        from datetime import datetime as dt

        return ESimHistory(
            timestamp=parse_datetime(data.get("date")) or dt.now(),
            event_type=data.get("type", "UNKNOWN"),
            description=data.get("description"),
            bundle_name=data.get("bundleName"),
            metadata=data.get("metadata"),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # USAGE
    # ─────────────────────────────────────────────────────────────────────────

    async def get_usage(self, iccid: str, bundle_name: str | None = None) -> GetUsageResponse:
        """Get usage statistics for an eSIM (aggregated from bundles)."""
        bundles_response = await self.list_esim_bundles(iccid)

        bundles = bundles_response.bundles
        if bundle_name:
            bundles = [b for b in bundles if b.name == bundle_name]

        # Aggregate usage
        total_used = 0.0
        total_remaining: float | None = 0.0
        total_mb: float | None = 0.0
        is_unlimited = False

        for bundle in bundles:
            if bundle.is_unlimited:
                is_unlimited = True
                total_remaining = None
                total_mb = None
            else:
                if bundle.data_used_mb:
                    total_used += bundle.data_used_mb
                if total_remaining is not None and bundle.data_remaining_mb:
                    total_remaining += bundle.data_remaining_mb
                if total_mb is not None and bundle.data_total_mb:
                    total_mb += bundle.data_total_mb

        return GetUsageResponse(
            usage=UsageStats(
                iccid=iccid,
                bundle_name=bundle_name,
                data=DataUsage(
                    used_mb=total_used,
                    remaining_mb=total_remaining,
                    total_mb=total_mb,
                    is_unlimited=is_unlimited,
                ),
                is_active=any(b.status == BundleStatus.ACTIVE for b in bundles),
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT
    # ─────────────────────────────────────────────────────────────────────────

    async def get_balance(self) -> GetBalanceResponse:
        """Get account balance from organisation endpoint."""
        response = await self._client.get("/organisation", provider_name=self.name)
        org = response.get("organisation", response)

        return GetBalanceResponse(
            balance=AccountBalance(
                balance=float(org.get("balance", 0)),
                currency=org.get("currency", "USD"),
            )
        )

    async def list_transactions(self, request: ListTransactionsRequest) -> ListTransactionsResponse:
        """List transactions - eSIM Go doesn't have direct transaction API."""
        return ListTransactionsResponse(
            transactions=[],
            total=0,
            page=request.page,
            limit=request.limit,
        )

    async def request_refund(self, request: RefundRequest) -> RefundResponse:
        """Request a refund through inventory endpoint."""
        payload: dict[str, Any] = {}
        if request.iccid:
            payload["iccid"] = request.iccid
        if request.bundle_name:
            payload["bundleName"] = request.bundle_name
        if request.order_id:
            payload["orderReference"] = request.order_id
        if request.reason:
            payload["reason"] = request.reason

        response = await self._client.post(
            "/inventory/refund", json=payload, provider_name=self.name
        )

        return RefundResponse(
            success=response.get("success", True),
            refund_id=response.get("refundId"),
            amount=response.get("amount"),
            currency=response.get("currency", "USD"),
            message=response.get("message"),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # INVENTORY
    # ─────────────────────────────────────────────────────────────────────────

    async def list_inventory(self, request: ListInventoryRequest) -> ListInventoryResponse:
        """List bundle inventory."""
        params: dict[str, Any] = {"page": request.page, "perPage": request.limit}

        response = await self._client.get("/inventory", params=params, provider_name=self.name)

        items = [
            InventoryItem(
                bundle_name=item.get("bundleName", ""),
                bundle_id=item.get("bundleName"),
                available_count=item.get("available", 0),
                assigned_count=item.get("assigned", 0),
                total_count=item.get("total", 0),
                type=InventoryType.BUNDLE,
                cost_per_unit=item.get("price"),
                currency=item.get("currency", "USD"),
                validity_days=item.get("duration"),
                data_mb=item.get("dataAmount"),
            )
            for item in response.get("inventory", [])
        ]

        return ListInventoryResponse(
            items=items,
            summary=InventorySummary(
                total_bundles=len(items),
                total_available=sum(i.available_count for i in items),
                total_assigned=sum(i.assigned_count for i in items),
            ),
            total=response.get("total"),
            page=request.page,
            limit=request.limit,
        )

    async def list_bundle_groups(self) -> ListBundleGroupsResponse:
        """List bundle groups from organisation."""
        response = await self._client.get("/organisation/groups", provider_name=self.name)

        groups = [
            BundleGroup(
                id=g.get("name", ""),
                name=g.get("description", g.get("name", "")),
                type=BUNDLE_GROUP_TYPE_MAP.get(g.get("type", ""), BundleGroupType.COUNTRY),
                description=g.get("description"),
                bundle_names=g.get("bundles", []),
                bundle_count=len(g.get("bundles", [])),
                countries=g.get("countries", []),
            )
            for g in response.get("groups", [])
        ]

        return ListBundleGroupsResponse(groups=groups, total=len(groups))

    async def list_assignments(self, request: ListAssignmentsRequest) -> ListAssignmentsResponse:
        """List eSIM assignments with installation details."""
        params: dict[str, Any] = {"page": request.page, "perPage": request.limit}
        if request.order_id:
            params["orderReference"] = request.order_id
        if request.iccid:
            params["iccid"] = request.iccid

        response = await self._client.get(
            "/esims/assignments", params=params, provider_name=self.name
        )

        assignments = [
            AssignmentInfo(
                iccid=a.get("iccid", ""),
                order_id=a.get("orderReference"),
                lpa_string=a.get("lpaString"),
                smdp_address=a.get("smdpAddress"),
                matching_id=a.get("matchingId"),
                confirmation_code=a.get("confirmationCode"),
                is_installed=a.get("installed", False),
                installed_at=parse_datetime(a.get("installedDate")),
                bundle_name=a.get("bundleName"),
                package_id=a.get("bundleName"),
            )
            for a in response.get("assignments", [])
        ]

        return ListAssignmentsResponse(
            assignments=assignments,
            total=response.get("total"),
            page=request.page,
            limit=request.limit,
        )

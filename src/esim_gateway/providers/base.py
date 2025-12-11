"""Base provider abstract class defining the unified eSIM gateway interface."""

from abc import ABC, abstractmethod

from esim_gateway.models.account import (
    GetBalanceResponse,
    ListTransactionsRequest,
    ListTransactionsResponse,
    RefundRequest,
    RefundResponse,
)
from esim_gateway.models.catalog import (
    GetPackageResponse,
    ListCountriesResponse,
    ListPackagesRequest,
    ListPackagesResponse,
    ListRegionsResponse,
)
from esim_gateway.models.esim import (
    ApplyBundleRequest,
    ApplyBundleResponse,
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
    ListAssignmentsRequest,
    ListAssignmentsResponse,
    ListBundleGroupsResponse,
    ListInventoryRequest,
    ListInventoryResponse,
)
from esim_gateway.models.order import (
    CreateOrderRequest,
    CreateOrderResponse,
    GetOrderResponse,
    ListOrdersRequest,
    ListOrdersResponse,
)
from esim_gateway.models.usage import (
    GetUsageHistoryRequest,
    GetUsageHistoryResponse,
    GetUsageResponse,
)


class ProviderNotSupportedError(Exception):
    """Raised when a provider doesn't support a specific operation."""

    def __init__(self, provider: str, operation: str):
        self.provider = provider
        self.operation = operation
        super().__init__(f"Provider '{provider}' does not support operation '{operation}'")


class BaseProvider(ABC):
    """Abstract base class for eSIM providers.

    Defines the unified interface that all provider implementations must follow.
    Core methods are abstract and must be implemented by all providers.
    Optional methods have default implementations that raise ProviderNotSupportedError.
    """

    name: str
    base_url: str

    def __init__(self, api_key: str, sandbox: bool = False):
        self.api_key = api_key
        self.sandbox = sandbox

    # ─────────────────────────────────────────────────────────────────────────
    # CATALOG - Core (Required)
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def list_countries(self) -> ListCountriesResponse:
        """List all countries with available packages."""

    @abstractmethod
    async def list_regions(self) -> ListRegionsResponse:
        """List all regions."""

    @abstractmethod
    async def list_packages(self, request: ListPackagesRequest) -> ListPackagesResponse:
        """List packages with optional filters."""

    @abstractmethod
    async def get_package(self, package_id: str) -> GetPackageResponse:
        """Get a single package by ID."""

    # ─────────────────────────────────────────────────────────────────────────
    # ORDERS - Core (Required)
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def create_order(self, request: CreateOrderRequest) -> CreateOrderResponse:
        """Create an order for eSIM bundles."""

    @abstractmethod
    async def get_order(self, order_id: str) -> GetOrderResponse:
        """Get order details by ID."""

    @abstractmethod
    async def list_orders(self, request: ListOrdersRequest) -> ListOrdersResponse:
        """List orders with optional filters."""

    # ─────────────────────────────────────────────────────────────────────────
    # ESIM MANAGEMENT - Core (Required)
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def list_esims(self, request: ListESimsRequest) -> ListESimsResponse:
        """List eSIMs with optional filters.

        Args:
            request: Filter and pagination parameters

        Returns:
            List of eSIMs matching the criteria
        """

    @abstractmethod
    async def get_esim(self, iccid: str) -> GetESimResponse:
        """Get eSIM details by ICCID.

        Args:
            iccid: The eSIM's ICCID

        Returns:
            eSIM details including bundles and status
        """

    @abstractmethod
    async def apply_bundle(self, request: ApplyBundleRequest) -> ApplyBundleResponse:
        """Apply a bundle/package to an eSIM.

        For providers like eSIM Go, this applies to existing eSIMs.
        For providers like Zetexa, this may create a new eSIM with the bundle.

        Args:
            request: Bundle application parameters

        Returns:
            Result including affected eSIMs
        """

    @abstractmethod
    async def list_esim_bundles(self, iccid: str) -> ListESimBundlesResponse:
        """List all bundles assigned to an eSIM.

        Args:
            iccid: The eSIM's ICCID

        Returns:
            List of assigned bundles with their status
        """

    @abstractmethod
    async def get_bundle_status(self, iccid: str, bundle_name: str) -> GetBundleStatusResponse:
        """Get status of a specific bundle on an eSIM.

        Args:
            iccid: The eSIM's ICCID
            bundle_name: The bundle identifier

        Returns:
            Bundle status including remaining data/validity
        """

    # ─────────────────────────────────────────────────────────────────────────
    # ESIM MANAGEMENT - Optional
    # ─────────────────────────────────────────────────────────────────────────

    async def revoke_bundle(
        self, iccid: str, bundle_name: str, request: RevokeBundleRequest
    ) -> RevokeBundleResponse:
        """Revoke a bundle from an eSIM.

        Optional - not all providers support bundle revocation.

        Args:
            iccid: The eSIM's ICCID
            bundle_name: The bundle to revoke
            request: Revocation details

        Returns:
            Revocation result including any refund info
        """
        raise ProviderNotSupportedError(self.name, "revoke_bundle")

    async def get_esim_history(self, iccid: str) -> GetESimHistoryResponse:
        """Get lifecycle history of an eSIM.

        Optional - provides historical events for the eSIM.

        Args:
            iccid: The eSIM's ICCID

        Returns:
            List of historical events
        """
        raise ProviderNotSupportedError(self.name, "get_esim_history")

    # ─────────────────────────────────────────────────────────────────────────
    # USAGE & STATISTICS - Core (Required)
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_usage(self, iccid: str, bundle_name: str | None = None) -> GetUsageResponse:
        """Get current usage statistics for an eSIM.

        Args:
            iccid: The eSIM's ICCID
            bundle_name: Optional specific bundle to query

        Returns:
            Usage statistics including data remaining
        """

    # ─────────────────────────────────────────────────────────────────────────
    # USAGE & STATISTICS - Optional
    # ─────────────────────────────────────────────────────────────────────────

    async def get_usage_history(
        self, request: GetUsageHistoryRequest
    ) -> GetUsageHistoryResponse:
        """Get historical usage records.

        Optional - detailed usage history over time.

        Args:
            request: Query parameters including date range

        Returns:
            Historical usage records
        """
        raise ProviderNotSupportedError(self.name, "get_usage_history")

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT & WALLET - Core (Required)
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_balance(self) -> GetBalanceResponse:
        """Get current account balance.

        Returns:
            Account balance information
        """

    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT & WALLET - Optional
    # ─────────────────────────────────────────────────────────────────────────

    async def list_transactions(
        self, request: ListTransactionsRequest
    ) -> ListTransactionsResponse:
        """List account transactions.

        Optional - transaction history may not be available from all providers.

        Args:
            request: Filter and pagination parameters

        Returns:
            List of transactions
        """
        raise ProviderNotSupportedError(self.name, "list_transactions")

    async def request_refund(self, request: RefundRequest) -> RefundResponse:
        """Request a refund for an order or bundle.

        Optional - refund capabilities vary by provider.

        Args:
            request: Refund request details

        Returns:
            Refund result
        """
        raise ProviderNotSupportedError(self.name, "request_refund")

    # ─────────────────────────────────────────────────────────────────────────
    # INVENTORY - Optional
    # ─────────────────────────────────────────────────────────────────────────

    async def list_inventory(self, request: ListInventoryRequest) -> ListInventoryResponse:
        """List bundle inventory.

        Optional - inventory tracking varies by provider.

        Args:
            request: Filter and pagination parameters

        Returns:
            Inventory items
        """
        raise ProviderNotSupportedError(self.name, "list_inventory")

    async def list_bundle_groups(self) -> ListBundleGroupsResponse:
        """List bundle groups/categories.

        Optional - bundle grouping varies by provider.

        Returns:
            List of bundle groups
        """
        raise ProviderNotSupportedError(self.name, "list_bundle_groups")

    async def list_assignments(
        self, request: ListAssignmentsRequest
    ) -> ListAssignmentsResponse:
        """List eSIM assignment/installation details.

        Optional - provides QR codes and installation info.

        Args:
            request: Filter parameters

        Returns:
            Assignment details including LPA strings
        """
        raise ProviderNotSupportedError(self.name, "list_assignments")

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def supports(self, operation: str) -> bool:
        """Check if provider supports a specific operation.

        Args:
            operation: Method name to check

        Returns:
            True if supported, False otherwise
        """
        method = getattr(self, operation, None)
        if method is None:
            return False

        # Check if it's the default implementation that raises NotSupported
        try:
            import inspect
            source = inspect.getsource(method)
            return "ProviderNotSupportedError" not in source
        except (TypeError, OSError):
            # If we can't get source, assume it's overridden
            return True

    @property
    def supported_operations(self) -> list[str]:
        """Get list of operations this provider supports.

        Returns:
            List of supported operation names
        """
        operations = [
            # Core - always supported
            "list_countries",
            "list_regions",
            "list_packages",
            "get_package",
            "create_order",
            "get_order",
            "list_orders",
            "list_esims",
            "get_esim",
            "apply_bundle",
            "list_esim_bundles",
            "get_bundle_status",
            "get_usage",
            "get_balance",
            # Optional
            "revoke_bundle",
            "get_esim_history",
            "get_usage_history",
            "list_transactions",
            "request_refund",
            "list_inventory",
            "list_bundle_groups",
            "list_assignments",
        ]
        return [op for op in operations if self.supports(op)]

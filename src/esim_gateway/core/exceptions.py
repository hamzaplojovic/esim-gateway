class GatewayException(Exception):
    """Base exception for all gateway errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ProviderException(GatewayException):
    """Error from upstream provider."""

    status_code = 502
    error_code = "provider_error"

    def __init__(
        self,
        message: str,
        provider: str,
        provider_code: str | None = None,
        provider_message: str | None = None,
    ):
        self.provider = provider
        self.provider_code = provider_code
        self.provider_message = provider_message
        super().__init__(message)


class ProviderNotFoundException(GatewayException):
    """Provider not found or not enabled."""

    status_code = 400
    error_code = "provider_not_found"


class PackageNotFoundException(GatewayException):
    """Package not found."""

    status_code = 404
    error_code = "package_not_found"


class OrderNotFoundException(GatewayException):
    """Order not found."""

    status_code = 404
    error_code = "order_not_found"


class ValidationException(GatewayException):
    """Request validation failed."""

    status_code = 422
    error_code = "validation_error"


class ESimNotFoundException(GatewayException):
    """eSIM not found."""

    status_code = 404
    error_code = "esim_not_found"


class BundleNotFoundException(GatewayException):
    """Bundle not found."""

    status_code = 404
    error_code = "bundle_not_found"

import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gateway
    env: str = "development"
    debug: bool = False

    # API Security
    api_keys: str = ""  # Comma-separated list of valid API keys
    api_key_header: str = "X-API-Key"
    require_api_key: bool = True  # Set to False to disable auth (dev only)

    # Rate Limiting
    rate_limit_requests: int = 100  # requests per window
    rate_limit_window: str = "minute"  # second, minute, hour, day

    # Retry Settings
    retry_max_attempts: int = 3
    retry_min_wait: float = 1.0  # seconds
    retry_max_wait: float = 10.0  # seconds
    retry_multiplier: float = 2.0  # exponential backoff multiplier

    # Circuit Breaker
    circuit_breaker_threshold: int = 5  # failures before opening
    circuit_breaker_timeout: float = 60.0  # seconds before half-open

    # HTTP Client
    http_timeout: float = 30.0
    http_max_connections: int = 20
    http_max_keepalive: int = 10

    # eSIM Go
    esimgo_api_key: str = ""
    esimgo_sandbox: bool = True

    # Zetexa - Production (api.zetexa.com)
    zetexa_api_key: str = ""
    zetexa_email: str = ""
    zetexa_password: str = ""
    zetexa_reseller_id: str = ""
    zetexa_access_token: str = ""

    # Zetexa - Sandbox/Staging (apistg.zetexa.com)
    zetexa_sandbox_api_key: str = ""
    zetexa_sandbox_email: str = ""
    zetexa_sandbox_password: str = ""
    zetexa_sandbox_reseller_id: str = ""
    zetexa_sandbox_access_token: str = ""

    # Which environment to use
    zetexa_sandbox: bool = True  # True = staging, False = production

    # esimCard - Production (portal.esimcard.com)
    esimcard_email: str = ""
    esimcard_password: str = ""

    # esimCard - Sandbox (sandbox.esimcard.com)
    esimcard_sandbox_email: str = ""
    esimcard_sandbox_password: str = ""

    # Which environment to use
    esimcard_sandbox: bool = True  # True = sandbox, False = production

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_api_keys(self) -> set[str]:
        """Get the set of valid API keys."""
        if not self.api_keys:
            return set()
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    def is_valid_api_key(self, key: str) -> bool:
        """Check if the given API key is valid."""
        return key in self.get_api_keys()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a new secure API key."""
        return secrets.token_urlsafe(32)


settings = Settings()

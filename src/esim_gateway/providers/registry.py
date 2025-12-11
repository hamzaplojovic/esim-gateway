"""Provider registry - creates provider instances from YAML configs + hooks."""

from esim_gateway.config import settings
from esim_gateway.providers.base import BaseProvider

_provider_instances: dict[str, BaseProvider] = {}


def get_provider_instance(provider_name: str) -> BaseProvider:
    """Get or create a provider instance."""
    provider_name = provider_name.lower()

    if provider_name in _provider_instances:
        return _provider_instances[provider_name]

    instance: BaseProvider

    if provider_name == "esimgo":
        from esim_gateway.providers.esimgo import ESimGoProvider

        instance = ESimGoProvider(
            api_key=settings.esimgo_api_key,
            sandbox=settings.esimgo_sandbox,
        )

    elif provider_name == "zetexa":
        from esim_gateway.providers.zetexa import ZetexaProvider

        if settings.zetexa_sandbox:
            instance = ZetexaProvider(
                api_key=settings.zetexa_sandbox_api_key,
                sandbox=True,
                email=settings.zetexa_sandbox_email,
                password=settings.zetexa_sandbox_password,
                reseller_id=settings.zetexa_sandbox_reseller_id,
                access_token=settings.zetexa_sandbox_access_token,
            )
        else:
            instance = ZetexaProvider(
                api_key=settings.zetexa_api_key,
                sandbox=False,
                email=settings.zetexa_email,
                password=settings.zetexa_password,
                reseller_id=settings.zetexa_reseller_id,
                access_token=settings.zetexa_access_token,
            )

    elif provider_name == "esimcard":
        from esim_gateway.providers.esimcard import ESimCardProvider

        if settings.esimcard_sandbox:
            instance = ESimCardProvider(
                api_key="",  # Not used by esimCard
                sandbox=True,
                email=settings.esimcard_sandbox_email,
                password=settings.esimcard_sandbox_password,
            )
        else:
            instance = ESimCardProvider(
                api_key="",  # Not used by esimCard
                sandbox=False,
                email=settings.esimcard_email,
                password=settings.esimcard_password,
            )
    else:
        raise KeyError(f"Unknown provider: {provider_name}")

    _provider_instances[provider_name] = instance
    return instance


def get_available_providers() -> list[str]:
    """List available providers."""
    return ["esimgo", "zetexa", "esimcard"]


def clear_provider_cache() -> None:
    """Clear provider cache."""
    _provider_instances.clear()

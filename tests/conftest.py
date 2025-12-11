import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Disable API key authentication for tests
os.environ["REQUIRE_API_KEY"] = "false"

from esim_gateway.core.resilience import reset_circuit_breakers
from esim_gateway.main import app
from esim_gateway.providers.registry import clear_provider_cache


@pytest.fixture(autouse=True)
def reset_providers() -> Generator[None, None, None]:
    """Clear provider cache and circuit breakers before each test."""
    clear_provider_cache()
    reset_circuit_breakers()
    yield
    clear_provider_cache()
    reset_circuit_breakers()


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mocks_dir() -> Path:
    """Get mocks directory path."""
    return Path(__file__).parent / "mocks"


def load_mock(mocks_dir: Path, provider: str, filename: str) -> dict[str, Any] | list[Any]:
    """Load a mock response file."""
    mock_path = mocks_dir / provider / filename
    with open(mock_path) as f:
        return json.load(f)


@pytest.fixture
def esimgo_catalogue(mocks_dir: Path) -> dict[str, Any]:
    """Load eSIM Go catalogue mock."""
    return load_mock(mocks_dir, "esimgo", "catalogue.json")


@pytest.fixture
def zetexa_countries(mocks_dir: Path) -> list[dict[str, Any]]:
    """Load Zetexa countries mock."""
    return load_mock(mocks_dir, "zetexa", "countries.json")


@pytest.fixture
def zetexa_regions(mocks_dir: Path) -> list[dict[str, Any]]:
    """Load Zetexa regions mock."""
    return load_mock(mocks_dir, "zetexa", "regions.json")


@pytest.fixture
def zetexa_packages(mocks_dir: Path) -> list[dict[str, Any]]:
    """Load Zetexa packages mock."""
    return load_mock(mocks_dir, "zetexa", "packages.json")


# ─────────────────────────────────────────────────────────────────────────────
# eSIM Go Order Mocks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def esimgo_orders_list(mocks_dir: Path) -> dict[str, Any]:
    """Load eSIM Go orders list mock."""
    return load_mock(mocks_dir, "esimgo", "orders_list.json")


@pytest.fixture
def esimgo_order_single(mocks_dir: Path) -> dict[str, Any]:
    """Load eSIM Go single order mock."""
    return load_mock(mocks_dir, "esimgo", "order_single.json")


@pytest.fixture
def esimgo_order_create(mocks_dir: Path) -> dict[str, Any]:
    """Load eSIM Go order create response mock."""
    return load_mock(mocks_dir, "esimgo", "order_create.json")


# ─────────────────────────────────────────────────────────────────────────────
# Zetexa Order Mocks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def zetexa_token(mocks_dir: Path) -> dict[str, Any]:
    """Load Zetexa token mock."""
    return load_mock(mocks_dir, "zetexa", "token.json")


@pytest.fixture
def zetexa_orders_list(mocks_dir: Path) -> dict[str, Any]:
    """Load Zetexa orders list mock."""
    return load_mock(mocks_dir, "zetexa", "orders_list.json")


@pytest.fixture
def zetexa_order_qrcode(mocks_dir: Path) -> dict[str, Any]:
    """Load Zetexa order QR code details mock."""
    return load_mock(mocks_dir, "zetexa", "order_qrcode.json")


@pytest.fixture
def zetexa_order_create(mocks_dir: Path) -> dict[str, Any]:
    """Load Zetexa order create response mock."""
    return load_mock(mocks_dir, "zetexa", "order_create.json")


# ─────────────────────────────────────────────────────────────────────────────
# esimCard Mocks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def esimcard_login(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard login response mock."""
    return load_mock(mocks_dir, "esimcard", "login.json")


@pytest.fixture
def esimcard_countries(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard countries mock."""
    return load_mock(mocks_dir, "esimcard", "countries.json")


@pytest.fixture
def esimcard_regions(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard regions mock."""
    return load_mock(mocks_dir, "esimcard", "regions.json")


@pytest.fixture
def esimcard_packages(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard packages mock."""
    return load_mock(mocks_dir, "esimcard", "packages.json")


@pytest.fixture
def esimcard_package_detail(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard package detail mock."""
    return load_mock(mocks_dir, "esimcard", "package_detail.json")


@pytest.fixture
def esimcard_purchase(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard purchase response mock."""
    return load_mock(mocks_dir, "esimcard", "purchase.json")


@pytest.fixture
def esimcard_my_esims(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard my-esims mock."""
    return load_mock(mocks_dir, "esimcard", "my_esims.json")


@pytest.fixture
def esimcard_esim_detail(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard eSIM detail mock."""
    return load_mock(mocks_dir, "esimcard", "esim_detail.json")


@pytest.fixture
def esimcard_usage(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard usage mock."""
    return load_mock(mocks_dir, "esimcard", "usage.json")


@pytest.fixture
def esimcard_balance(mocks_dir: Path) -> dict[str, Any]:
    """Load esimCard balance mock."""
    return load_mock(mocks_dir, "esimcard", "balance.json")

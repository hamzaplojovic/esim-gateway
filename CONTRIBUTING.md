# Contributing to eSIM Gateway

Thank you for your interest in contributing to the eSIM Gateway! This guide will help you get started with development and adding new provider integrations.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Architecture Overview](#architecture-overview)
- [Adding a New Provider](#adding-a-new-provider)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

---

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/hamzaplojovic/esim-gateway.git
cd esim-gateway

# Install dependencies (including dev dependencies)
uv sync --dev

# Copy environment template
cp .env.example .env

# Verify setup
uv run pytest
uv run ruff check .
uv run mypy src/
```

---

## Code Style

We use automated tools to maintain consistent code quality:

### Linting & Formatting

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking
uv run mypy src/
```

### Guidelines

- **Type hints**: All functions must have complete type annotations
- **Docstrings**: Public functions and classes need docstrings
- **Line length**: 100 characters max
- **Imports**: Sorted automatically by ruff (isort rules)

### Pre-commit Checks

Before committing, ensure all checks pass:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest
```

---

## Architecture Overview

### Project Structure

```
src/esim_gateway/
├── api/                 # FastAPI route handlers
│   ├── catalog.py       # /catalog endpoints
│   ├── orders.py        # /orders endpoints
│   ├── esims.py         # /esims endpoints
│   ├── account.py       # /account endpoints
│   └── dependencies.py  # Provider injection
├── core/                # Core utilities
│   ├── http.py          # HTTP client with resilience
│   ├── resilience.py    # Retry & circuit breaker
│   ├── security.py      # Auth & rate limiting
│   └── exceptions.py    # Custom exceptions
├── models/              # Pydantic response models
│   ├── catalog.py       # Country, Package, Region
│   ├── order.py         # Order, OrderItem
│   ├── esim.py          # ESim, Bundle
│   ├── usage.py         # Usage statistics
│   └── account.py       # Balance, Transaction
├── providers/           # Provider implementations
│   ├── base.py          # Abstract base class
│   ├── esimgo.py        # eSIM Go
│   ├── zetexa.py        # Zetexa
│   ├── esimcard.py      # esimCard
│   └── registry.py      # Provider factory
└── config.py            # Settings
```

### Key Concepts

1. **Unified Schema**: All providers return the same Pydantic models
2. **BaseProvider**: Abstract class defining the provider interface
3. **HTTPClient**: Shared HTTP client with retry/circuit breaker
4. **Provider Registry**: Factory for creating provider instances

---

## Adding a New Provider

### Step 1: Document the API Mapping

Create `docs/providers/YOUR_PROVIDER_mapping.yaml`:

```yaml
provider:
  name: yourprovider
  website: https://yourprovider.com
  api_docs: https://docs.yourprovider.com

authentication:
  type: bearer_token  # or api_key, basic_auth, oauth2
  header: Authorization
  format: "Bearer {token}"

base_urls:
  production: https://api.yourprovider.com/v1
  sandbox: https://sandbox.yourprovider.com/v1

endpoints:
  list_countries:
    method: GET
    path: /destinations
    response_mapping:
      countries: data.countries
      iso2: country_code
      name: country_name
  # ... document all endpoint mappings
```

### Step 2: Create the Provider Class

Create `src/esim_gateway/providers/yourprovider.py`:

```python
"""YourProvider implementation."""

from typing import Any

from esim_gateway.core.http import HTTPClient
from esim_gateway.core.exceptions import PackageNotFoundException
from esim_gateway.models.catalog import (
    Country,
    ListCountriesResponse,
    ListPackagesRequest,
    ListPackagesResponse,
    # ... other imports
)
from esim_gateway.providers.base import BaseProvider


class YourProviderProvider(BaseProvider):
    """YourProvider eSIM provider implementation."""

    name = "yourprovider"
    base_url_live = "https://api.yourprovider.com/v1"
    base_url_sandbox = "https://sandbox.yourprovider.com/v1"

    def __init__(self, api_key: str, sandbox: bool = False):
        super().__init__(api_key, sandbox)
        self.base_url = self.base_url_sandbox if sandbox else self.base_url_live
        self._client = HTTPClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def list_countries(self) -> ListCountriesResponse:
        """List all countries with available packages."""
        response = await self._client.get("/destinations", provider_name=self.name)

        countries = [
            Country(
                iso2=item["country_code"],
                name=item["country_name"],
                image_url=item.get("flag_url"),
            )
            for item in response.get("data", [])
        ]

        return ListCountriesResponse(countries=countries, total=len(countries))

    # Implement all other required methods...
```

### Step 3: Add Status Mappings

Map provider-specific statuses to unified enums:

```python
from esim_gateway.models.esim import ESimStatus, BundleStatus

ESIM_STATUS_MAP: dict[str, ESimStatus] = {
    "ACTIVE": ESimStatus.ACTIVE,
    "NOT_INSTALLED": ESimStatus.UNUSED,
    "INSTALLED": ESimStatus.INSTALLED,
    "SUSPENDED": ESimStatus.DISABLED,
    "DELETED": ESimStatus.DELETED,
}

def _map_status(self, status: str) -> ESimStatus:
    return ESIM_STATUS_MAP.get(status.upper(), ESimStatus.UNUSED)
```

### Step 4: Register the Provider

Update `src/esim_gateway/providers/registry.py`:

```python
elif provider_name == "yourprovider":
    from esim_gateway.providers.yourprovider import YourProviderProvider

    instance = YourProviderProvider(
        api_key=settings.yourprovider_api_key,
        sandbox=settings.yourprovider_sandbox,
    )
```

Update `get_available_providers()`:

```python
def get_available_providers() -> list[str]:
    return ["esimgo", "zetexa", "esimcard", "yourprovider"]
```

### Step 5: Add Configuration

Update `src/esim_gateway/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # YourProvider
    yourprovider_api_key: str = ""
    yourprovider_sandbox: bool = True
```

Update `.env.example`:

```bash
# YourProvider
YOURPROVIDER_API_KEY=
YOURPROVIDER_SANDBOX=true
```

### Required Methods

Your provider must implement all methods from `BaseProvider`:

| Category | Method | Description |
|----------|--------|-------------|
| **Catalog** | `list_countries()` | List available countries |
| | `list_regions()` | List available regions |
| | `list_packages(request)` | List packages with filters |
| | `get_package(package_id)` | Get single package |
| **Orders** | `create_order(request)` | Create new order |
| | `get_order(order_id)` | Get order details |
| | `list_orders(request)` | List orders |
| **eSIM** | `list_esims(request)` | List eSIMs |
| | `get_esim(iccid)` | Get eSIM by ICCID |
| | `apply_bundle(request)` | Apply bundle to eSIM |
| | `list_esim_bundles(iccid)` | List bundles on eSIM |
| | `get_bundle_status(iccid, name)` | Get bundle status |
| **Usage** | `get_usage(iccid, bundle_name)` | Get usage stats |
| **Account** | `get_balance()` | Get account balance |

Optional methods (can raise `NotImplementedError`):
- `list_transactions(request)`
- `request_refund(request)`
- `revoke_bundle(iccid, name, request)`
- `get_esim_history(iccid)`

---

## Testing

### Create Test Mocks

Create mock response files in `tests/mocks/yourprovider/`:

```
tests/mocks/yourprovider/
├── countries.json
├── regions.json
├── packages.json
├── package_detail.json
├── orders_list.json
├── order_create.json
├── my_esims.json
├── esim_detail.json
├── usage.json
└── balance.json
```

### Write API Tests

Create `tests/test_api/test_yourprovider.py`:

```python
import pytest
from pytest_httpx import HTTPXMock

class TestYourProviderCatalog:
    def test_list_countries(
        self,
        client,
        httpx_mock: HTTPXMock,
        yourprovider_login,
        yourprovider_countries,
    ):
        # Mock authentication if needed
        httpx_mock.add_response(
            url="https://sandbox.yourprovider.com/v1/auth",
            json=yourprovider_login,
        )

        # Mock the actual endpoint
        httpx_mock.add_response(
            url="https://sandbox.yourprovider.com/v1/destinations",
            json=yourprovider_countries,
        )

        response = client.get(
            "/catalog/countries",
            headers={"X-Provider": "yourprovider"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert len(data["countries"]) > 0
```

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific provider tests
uv run pytest tests/test_api/ -k "yourprovider" -v

# Run with coverage
uv run pytest --cov=esim_gateway --cov-report=term-missing
```

---

## Submitting Changes

### Pull Request Process

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/add-yourprovider`
3. **Make changes** following the guidelines above
4. **Test thoroughly**: All tests must pass
5. **Commit** with clear messages
6. **Push** and create a Pull Request

### PR Checklist

- [ ] All required `BaseProvider` methods implemented
- [ ] Status mappings documented and implemented
- [ ] Error handling with appropriate exceptions
- [ ] Mock response files created
- [ ] Tests written and passing
- [ ] Configuration added to `config.py` and `.env.example`
- [ ] Provider registered in `registry.py`
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run mypy src/` passes
- [ ] `uv run pytest` passes

### PR Template

```markdown
## New Provider: [Provider Name]

### Provider Info
- Website: [URL]
- API Docs: [URL]

### Implemented Features
- [x] Catalog (countries, regions, packages)
- [x] Orders (create, list, get)
- [x] eSIM Management
- [x] Usage Statistics
- [x] Account Balance
- [ ] Transactions (not supported by provider)
- [ ] Refunds (not supported by provider)

### Testing
- [x] Unit tests passing
- [x] Tested with sandbox credentials

### Notes
[Any special considerations, limitations, or quirks]
```

---

## Need Help?

- **Reference implementations**: Check `esimgo.py`, `zetexa.py`, `esimcard.py`
- **Templates**: See `templates/` directory
- **Questions**: Open a [Discussion](https://github.com/hamzaplojovic/esim-gateway/discussions)
- **Bugs**: Open an [Issue](https://github.com/hamzaplojovic/esim-gateway/issues)

Thank you for contributing!

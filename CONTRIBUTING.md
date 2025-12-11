# Contributing to eSIM Gateway

Thank you for your interest in contributing to the eSIM Gateway! This guide will help you add new provider integrations.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Adding a New Provider](#adding-a-new-provider)
- [Step-by-Step Guide](#step-by-step-guide)
- [Testing](#testing)
- [Submitting Your PR](#submitting-your-pr)

---

## Overview

The eSIM Gateway provides a **unified API** that abstracts multiple eSIM provider APIs. Each provider implementation maps provider-specific endpoints and data formats to our unified schema.

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified Gateway API                       │
│  /countries, /packages, /orders, /esims, /account, etc.     │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │ eSIM Go │          │ Zetexa  │          │  Your   │
   │Provider │          │Provider │          │Provider │
   └─────────┘          └─────────┘          └─────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   Provider API          Provider API          Provider API
```

## Architecture

### Key Concepts

1. **Unified Schema**: All providers map to the same response models
2. **BaseProvider**: Abstract base class that all providers must extend
3. **HTTPClient**: Shared HTTP client with retry logic and error handling
4. **Models**: Pydantic models define the unified API contracts

### Directory Structure

```
src/esim_gateway/
├── providers/
│   ├── base.py          # BaseProvider abstract class
│   ├── esimgo.py        # eSIM Go implementation
│   ├── zetexa.py        # Zetexa implementation
│   └── your_provider.py # Your new provider
├── models/
│   ├── catalog.py       # Country, Region, Package models
│   ├── order.py         # Order models
│   ├── esim.py          # eSIM models
│   ├── usage.py         # Usage models
│   └── account.py       # Account/balance models
├── core/
│   ├── http.py          # HTTPClient
│   └── exceptions.py    # Exception classes
└── api/
    └── dependencies.py  # Provider registration
```

---

## Adding a New Provider

### Prerequisites

Before you start:

1. **Get API access** from the provider (sandbox/test credentials)
2. **Obtain API documentation** (ideally OpenAPI/Swagger spec)
3. **Understand the provider's** authentication method, endpoints, and data formats

### Required Methods

Your provider must implement these methods from `BaseProvider`:

| Category | Method | Description |
|----------|--------|-------------|
| **Catalog** | `list_countries()` | List available countries |
| | `list_regions()` | List available regions |
| | `list_packages(request)` | List packages with filters |
| | `get_package(package_id)` | Get single package details |
| **Orders** | `create_order(request)` | Create a new order |
| | `get_order(order_id)` | Get order details |
| | `list_orders(request)` | List orders with pagination |
| **eSIM** | `list_esims(request)` | List eSIMs |
| | `get_esim(iccid)` | Get eSIM by ICCID |
| | `apply_bundle(request)` | Apply bundle to eSIM |
| | `list_esim_bundles(iccid)` | List bundles on eSIM |
| | `get_bundle_status(iccid, name)` | Get bundle status |
| **Usage** | `get_usage(iccid, bundle_name)` | Get usage statistics |
| **Account** | `get_balance()` | Get account balance |

### Optional Methods

These can raise `NotImplementedError` if not supported:

- `list_transactions(request)` - Transaction history
- `request_refund(request)` - Process refunds
- `revoke_bundle(iccid, name)` - Revoke a bundle
- `get_esim_history(iccid)` - eSIM history

---

## Step-by-Step Guide

### Step 1: Document the Mapping

Before writing code, document how the provider's API maps to our unified schema.

1. Copy the mapping template:
   ```bash
   cp templates/provider_mapping.yaml docs/providers/YOUR_PROVIDER_mapping.yaml
   ```

2. Fill in all sections:
   - Provider info (name, website, API docs URL)
   - Authentication details
   - Base URLs (production and sandbox)
   - Endpoint mappings for each unified endpoint
   - Response field mappings
   - Status value mappings
   - Error code mappings

This document becomes your implementation guide.

### Step 2: Create the Provider File

1. Copy the provider template:
   ```bash
   cp templates/provider.py.template src/esim_gateway/providers/YOUR_PROVIDER.py
   ```

2. Update placeholders:
   - `${PROVIDER_NAME}` → `yourprovider` (lowercase)
   - `${PROVIDER_NAME_TITLE}` → `YourProvider`
   - `${PROVIDER_CLASS_NAME}` → `YourProvider`
   - `${BASE_URL_LIVE}` → Production API URL
   - `${BASE_URL_SANDBOX}` → Sandbox API URL

### Step 3: Implement Authentication

Configure the HTTP client with proper authentication in `__init__`:

```python
# API Key in header
self._client = HTTPClient(
    base_url=self.base_url,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
)

# Or Basic Auth
import base64
credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
self._client = HTTPClient(
    base_url=self.base_url,
    headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    },
)
```

### Step 4: Implement Methods

For each method:

1. **Make API call** using `self._client.get()` or `self._client.post()`
2. **Parse response** using helper methods
3. **Map to unified models** following the schema

Example implementation:

```python
async def list_countries(self) -> ListCountriesResponse:
    """List all countries with available packages."""
    response = await self._client.get("/destinations", provider_name=self.name)

    countries = []
    for item in response.get("data", []):
        countries.append(Country(
            iso2=item["country_code"],
            iso3=item.get("country_iso3"),
            name=item["country_name"],
            image_url=item.get("flag_url"),
        ))

    return ListCountriesResponse(countries=countries)
```

### Step 5: Map Status Values

Create mapping dictionaries for provider-specific statuses:

```python
def _map_esim_status(self, status: str) -> ESimStatus:
    """Map provider eSIM status to unified status."""
    status_map = {
        "ACTIVE": ESimStatus.ACTIVE,
        "NOT_INSTALLED": ESimStatus.UNUSED,
        "INSTALLED": ESimStatus.INSTALLED,
        "SUSPENDED": ESimStatus.DISABLED,
    }
    return status_map.get(status.upper(), ESimStatus.UNUSED)
```

### Step 6: Handle Errors

Map provider errors to appropriate exceptions:

```python
from esim_gateway.core.exceptions import (
    PackageNotFoundException,
    ESimNotFoundException,
    OrderNotFoundException,
    ProviderException,
)

# In your method:
if response.get("error_code") == "PACKAGE_NOT_FOUND":
    raise PackageNotFoundException(f"Package {package_id} not found")
```

### Step 7: Register the Provider

Add to `src/esim_gateway/api/dependencies.py`:

```python
from esim_gateway.providers.yourprovider import YourProviderProvider

PROVIDERS = {
    "esimgo": lambda: ESimGoProvider(...),
    "zetexa": lambda: ZetexaProvider(...),
    "yourprovider": lambda: YourProviderProvider(
        api_key=settings.yourprovider_api_key,
        sandbox=settings.yourprovider_sandbox,
    ),
}
```

### Step 8: Add Settings

Add to `src/esim_gateway/core/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # YourProvider
    yourprovider_api_key: str = ""
    yourprovider_sandbox: bool = True
```

---

## Testing

### Create Test Mocks

Create mock response files in `tests/mocks/yourprovider/`:

```
tests/mocks/yourprovider/
├── countries.json
├── packages.json
├── orders.json
├── esims.json
└── balance.json
```

### Write Unit Tests

Create `tests/test_providers/test_yourprovider.py`:

```python
import pytest
from esim_gateway.providers.yourprovider import YourProviderProvider

@pytest.fixture
def provider():
    return YourProviderProvider(api_key="test_key", sandbox=True)

@pytest.mark.asyncio
async def test_list_countries(provider, mock_response):
    mock_response("yourprovider/countries.json")
    response = await provider.list_countries()
    assert len(response.countries) > 0
    assert response.countries[0].iso2 == "US"
```

### Run Tests

```bash
# Run all tests
uv run pytest

# Run only your provider tests
uv run pytest tests/test_providers/test_yourprovider.py -v

# Run with coverage
uv run pytest --cov=esim_gateway --cov-report=term-missing
```

---

## Submitting Your PR

### Checklist

Before submitting, ensure:

- [ ] All required methods implemented
- [ ] Mapping document created at `docs/providers/PROVIDER_mapping.yaml`
- [ ] Provider registered in `dependencies.py`
- [ ] Settings added to `settings.py`
- [ ] Unit tests written and passing
- [ ] Mock response files created
- [ ] Code formatted with `ruff format`
- [ ] Linting passes with `ruff check`
- [ ] Type checking passes with `pyright`

### PR Template

```markdown
## New Provider: [Provider Name]

### Provider Info
- Website: [URL]
- API Docs: [URL]

### Implemented Endpoints
- [x] list_countries
- [x] list_packages
- [x] create_order
- [x] get_esim
- [x] get_usage
- [x] get_balance
- [ ] list_transactions (not supported by provider)

### Testing
- [ ] Unit tests passing
- [ ] Tested with sandbox credentials

### Notes
[Any special considerations or limitations]
```

### Code Quality Commands

```bash
# Format code
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run pyright

# Run all tests
uv run pytest
```

---

## Need Help?

- Review existing providers (`esimgo.py`, `zetexa.py`) for reference
- Check the mapping templates in `templates/`
- Open an issue for questions
- Join discussions for architecture decisions

Thank you for contributing!

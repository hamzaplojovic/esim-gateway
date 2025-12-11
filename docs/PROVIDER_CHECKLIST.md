# Provider Integration Checklist

Quick reference checklist for adding a new provider to the eSIM Gateway.

## Pre-Implementation

- [ ] Obtained API credentials (sandbox/production)
- [ ] Read provider's API documentation
- [ ] Identified authentication method
- [ ] Identified all available endpoints

## Documentation

- [ ] Created `docs/providers/PROVIDER_mapping.yaml` from template
- [ ] Mapped all endpoints to unified schema
- [ ] Documented status value mappings
- [ ] Documented error code mappings
- [ ] Noted any provider limitations

## Implementation

### Provider File

- [ ] Created `src/esim_gateway/providers/PROVIDER.py`
- [ ] Set `name`, `base_url_live`, `base_url_sandbox`
- [ ] Configured authentication in `__init__`
- [ ] Initialized HTTPClient properly

### Required Methods

**Catalog**
- [ ] `list_countries()` → `ListCountriesResponse`
- [ ] `list_regions()` → `ListRegionsResponse`
- [ ] `list_packages(request)` → `ListPackagesResponse`
- [ ] `get_package(package_id)` → `GetPackageResponse`

**Orders**
- [ ] `create_order(request)` → `CreateOrderResponse`
- [ ] `get_order(order_id)` → `GetOrderResponse`
- [ ] `list_orders(request)` → `ListOrdersResponse`

**eSIM Management**
- [ ] `list_esims(request)` → `ListESimsResponse`
- [ ] `get_esim(iccid)` → `GetESimResponse`
- [ ] `apply_bundle(request)` → `ApplyBundleResponse`
- [ ] `list_esim_bundles(iccid)` → `ListESimBundlesResponse`
- [ ] `get_bundle_status(iccid, bundle_name)` → `GetBundleStatusResponse`

**Usage**
- [ ] `get_usage(iccid, bundle_name)` → `GetUsageResponse`

**Account**
- [ ] `get_balance()` → `GetBalanceResponse`

### Optional Methods (NotImplementedError if unsupported)

- [ ] `list_transactions(request)` → `ListTransactionsResponse`
- [ ] `request_refund(request)` → `RefundResponse`
- [ ] `revoke_bundle(iccid, bundle_name)` → `RevokeBundleResponse`
- [ ] `get_esim_history(iccid, request)` → `GetESimHistoryResponse`

### Helper Methods

- [ ] Created `_parse_country(data)` helper
- [ ] Created `_parse_package(data)` helper
- [ ] Created `_parse_esim(data)` helper
- [ ] Created `_parse_order(data)` helper
- [ ] Created `_map_esim_status(status)` helper
- [ ] Created `_map_bundle_status(status)` helper
- [ ] Created `_map_order_status(status)` helper

### Error Handling

- [ ] Mapped provider errors to `PackageNotFoundException`
- [ ] Mapped provider errors to `ESimNotFoundException`
- [ ] Mapped provider errors to `OrderNotFoundException`
- [ ] Mapped provider errors to `ProviderException`

## Configuration

- [ ] Added provider to `PROVIDERS` dict in `dependencies.py`
- [ ] Added settings to `settings.py`:
  - [ ] `PROVIDER_api_key`
  - [ ] `PROVIDER_sandbox`
  - [ ] Any other provider-specific settings

## Testing

### Mock Data

- [ ] Created `tests/mocks/PROVIDER/` directory
- [ ] Created `countries.json` mock
- [ ] Created `packages.json` mock
- [ ] Created `orders.json` mock
- [ ] Created `esims.json` mock
- [ ] Created `balance.json` mock

### Test File

- [ ] Created `tests/test_providers/test_PROVIDER.py`
- [ ] Test `list_countries()`
- [ ] Test `list_packages()`
- [ ] Test `get_package()`
- [ ] Test `create_order()`
- [ ] Test `get_order()`
- [ ] Test `list_esims()`
- [ ] Test `get_esim()`
- [ ] Test `get_usage()`
- [ ] Test `get_balance()`
- [ ] Test error handling

### Quality Checks

- [ ] All tests pass: `uv run pytest`
- [ ] Code formatted: `uv run ruff format`
- [ ] Linting passes: `uv run ruff check`
- [ ] Type checking passes: `uv run pyright`

## PR Submission

- [ ] Branch created from `main`
- [ ] Commits are clean and descriptive
- [ ] PR description completed
- [ ] All checklist items above verified

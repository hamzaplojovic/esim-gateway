#!/usr/bin/env python3
"""
Provider Integration Script

This script helps integrate a new eSIM provider into the gateway by:
1. Creating scaffolding from templates
2. Reading an OpenAPI specification file (optional)
3. Invoking Claude Code to generate the provider implementation (optional)

Usage:
    # Generate scaffolding from templates
    python scripts/integrate_provider.py <provider_name> --scaffold

    # Generate with Claude Code from OpenAPI spec
    python scripts/integrate_provider.py <provider_name> <openapi_file>

Example:
    python scripts/integrate_provider.py airalo --scaffold
    python scripts/integrate_provider.py airalo ./specs/airalo-openapi.json
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template


PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
PROVIDERS_DIR = PROJECT_ROOT / "src" / "esim_gateway" / "providers"
DOCS_DIR = PROJECT_ROOT / "docs" / "providers"


def load_openapi_spec(file_path: Path) -> dict:
    """Load and parse OpenAPI specification."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    with open(file_path) as f:
        if file_path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                return yaml.safe_load(f)
            except ImportError:
                print("Error: PyYAML required for YAML files. Install with: pip install pyyaml")
                sys.exit(1)
        else:
            return json.load(f)


def extract_api_summary(spec: dict) -> str:
    """Extract a summary of API endpoints from OpenAPI spec."""
    info = spec.get("info", {})
    paths = spec.get("paths", {})

    summary_lines = [
        f"API: {info.get('title', 'Unknown')}",
        f"Version: {info.get('version', 'Unknown')}",
        f"Description: {info.get('description', 'N/A')[:200]}...",
        "",
        "Endpoints:",
    ]

    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                op_id = details.get("operationId", "")
                summary = details.get("summary", details.get("description", ""))[:80]
                summary_lines.append(f"  {method.upper():6} {path}")
                if op_id:
                    summary_lines.append(f"         operationId: {op_id}")
                if summary:
                    summary_lines.append(f"         {summary}")

    return "\n".join(summary_lines)


def extract_schemas(spec: dict) -> str:
    """Extract schema definitions from OpenAPI spec."""
    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        schemas = spec.get("definitions", {})  # OpenAPI 2.0

    schema_lines = ["Schemas/Models:"]
    for name, schema in list(schemas.items())[:20]:  # Limit to first 20
        props = schema.get("properties", {})
        prop_names = list(props.keys())[:10]
        schema_lines.append(f"  {name}: {', '.join(prop_names)}")

    if len(schemas) > 20:
        schema_lines.append(f"  ... and {len(schemas) - 20} more schemas")

    return "\n".join(schema_lines)


def create_scaffold(provider_name: str, display_name: str) -> None:
    """Create provider scaffolding from templates."""
    class_name = "".join(word.capitalize() for word in provider_name.split("_"))

    # Ensure directories exist
    PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Create provider file from template
    provider_template = TEMPLATES_DIR / "provider.py.template"
    provider_output = PROVIDERS_DIR / f"{provider_name}.py"

    if provider_output.exists():
        print(f"Warning: {provider_output} already exists")
        response = input("Overwrite? [y/N]: ")
        if response.lower() != "y":
            print("Skipping provider file...")
        else:
            _create_provider_file(provider_template, provider_output, provider_name, class_name, display_name)
    else:
        _create_provider_file(provider_template, provider_output, provider_name, class_name, display_name)

    # Create mapping file from template
    mapping_template = TEMPLATES_DIR / "provider_mapping.yaml"
    mapping_output = DOCS_DIR / f"{provider_name}_mapping.yaml"

    if mapping_output.exists():
        print(f"Warning: {mapping_output} already exists")
        response = input("Overwrite? [y/N]: ")
        if response.lower() != "y":
            print("Skipping mapping file...")
        else:
            shutil.copy(mapping_template, mapping_output)
            print(f"Created: {mapping_output}")
    else:
        shutil.copy(mapping_template, mapping_output)
        print(f"Created: {mapping_output}")

    # Create test directory and file stub
    tests_dir = PROJECT_ROOT / "tests" / "test_providers"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_file = tests_dir / f"test_{provider_name}.py"
    if not test_file.exists():
        test_content = f'''"""Tests for {display_name} provider."""

import pytest

from esim_gateway.providers.{provider_name} import {class_name}Provider


@pytest.fixture
def provider():
    """Create provider instance for testing."""
    return {class_name}Provider(api_key="test_key", sandbox=True)


@pytest.mark.asyncio
async def test_list_countries(provider):
    """Test list_countries method."""
    # TODO: Implement test with mock responses
    pass


@pytest.mark.asyncio
async def test_list_packages(provider):
    """Test list_packages method."""
    # TODO: Implement test with mock responses
    pass


@pytest.mark.asyncio
async def test_get_esim(provider):
    """Test get_esim method."""
    # TODO: Implement test with mock responses
    pass


@pytest.mark.asyncio
async def test_get_balance(provider):
    """Test get_balance method."""
    # TODO: Implement test with mock responses
    pass
'''
        test_file.write_text(test_content)
        print(f"Created: {test_file}")

    # Create mocks directory
    mocks_dir = PROJECT_ROOT / "tests" / "mocks" / provider_name
    mocks_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created: {mocks_dir}/")

    print("\n" + "=" * 60)
    print("Scaffolding complete!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"  1. Fill in the mapping document: docs/providers/{provider_name}_mapping.yaml")
    print(f"  2. Implement the provider: src/esim_gateway/providers/{provider_name}.py")
    print(f"  3. Add mock responses to: tests/mocks/{provider_name}/")
    print(f"  4. Complete the tests: tests/test_providers/test_{provider_name}.py")
    print("  5. Register provider in src/esim_gateway/api/dependencies.py")
    print("  6. Add settings to src/esim_gateway/core/settings.py")
    print("\nSee CONTRIBUTING.md for detailed instructions.")


def _create_provider_file(
    template_path: Path,
    output_path: Path,
    provider_name: str,
    class_name: str,
    display_name: str,
) -> None:
    """Create provider file from template with substitutions."""
    template_content = template_path.read_text()

    # Simple string replacements (template uses ${...} syntax)
    content = template_content
    content = content.replace("${PROVIDER_NAME}", provider_name)
    content = content.replace("${PROVIDER_NAME_TITLE}", display_name)
    content = content.replace("${PROVIDER_CLASS_NAME}", class_name)
    content = content.replace("${PROVIDER_WEBSITE}", "https://")
    content = content.replace("${PROVIDER_API_DOCS}", "https://")
    content = content.replace("${BASE_URL_LIVE}", "https://api.provider.com")
    content = content.replace("${BASE_URL_SANDBOX}", "https://sandbox.provider.com")

    # Replace endpoint placeholders with "Not documented"
    content = content.replace("${ENDPOINT_MAPPING}", "See mapping YAML for details")
    content = content.replace("${ENDPOINT_LIST_COUNTRIES}", "GET /countries (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_LIST_REGIONS}", "GET /regions (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_LIST_PACKAGES}", "GET /packages (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_PACKAGE}", "GET /packages/{id} (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_CREATE_ORDER}", "POST /orders (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_ORDER}", "GET /orders/{id} (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_LIST_ORDERS}", "GET /orders (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_LIST_ESIMS}", "GET /esims (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_ESIM}", "GET /esims/{iccid} (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_APPLY_BUNDLE}", "POST /esims/{iccid}/apply (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_LIST_ESIM_BUNDLES}", "GET /esims/{iccid}/bundles (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_BUNDLE_STATUS}", "GET /esims/{iccid}/bundles/{name} (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_USAGE}", "GET /esims/{iccid}/usage (provider endpoint TBD)")
    content = content.replace("${ENDPOINT_GET_BALANCE}", "GET /account/balance (provider endpoint TBD)")

    output_path.write_text(content)
    print(f"Created: {output_path}")


def build_claude_prompt(provider_name: str, spec: dict, spec_file: Path) -> str:
    """Build the prompt for Claude Code."""
    api_summary = extract_api_summary(spec)
    schemas = extract_schemas(spec)

    prompt = f"""I need to integrate a new eSIM provider called "{provider_name}" into this gateway.

The provider's OpenAPI specification is at: {spec_file.absolute()}

Here's a summary of their API:

{api_summary}

{schemas}

Please help me create a complete provider implementation by:

1. **Analyze the OpenAPI spec** at {spec_file.absolute()} to understand:
   - Authentication method (API key, OAuth, etc.)
   - Base URL structure
   - Request/response formats
   - Error handling patterns

2. **Create the endpoint mapping document** at `docs/providers/{provider_name}_mapping.yaml`:
   - Map each provider endpoint to our unified schema
   - Document response field mappings
   - Document status value mappings

3. **Create the provider file** at `src/esim_gateway/providers/{provider_name}.py`:
   - Use `templates/provider.py.template` as starting point
   - Extend `BaseProvider` from `esim_gateway.providers.base`
   - Implement all required abstract methods:
     - `list_countries()` -> `ListCountriesResponse`
     - `list_regions()` -> `ListRegionsResponse`
     - `list_packages(request)` -> `ListPackagesResponse`
     - `get_package(package_id)` -> `GetPackageResponse`
     - `create_order(request)` -> `CreateOrderResponse`
     - `get_order(order_id)` -> `GetOrderResponse`
     - `list_orders(request)` -> `ListOrdersResponse`
     - `list_esims(request)` -> `ListESimsResponse`
     - `get_esim(iccid)` -> `GetESimResponse`
     - `apply_bundle(request)` -> `ApplyBundleResponse`
     - `list_esim_bundles(iccid)` -> `ListESimBundlesResponse`
     - `get_bundle_status(iccid, bundle_name)` -> `GetBundleStatusResponse`
     - `get_usage(iccid, bundle_name)` -> `GetUsageResponse`
     - `get_balance()` -> `GetBalanceResponse`
   - Map provider-specific responses to our unified models
   - Handle provider-specific error codes

4. **Register the provider** in `src/esim_gateway/api/dependencies.py`:
   - Add to the PROVIDERS dict
   - Configure credentials from settings

5. **Add provider settings** to `src/esim_gateway/core/settings.py`:
   - API key/credentials
   - Base URL (sandbox/production)
   - Any provider-specific config

6. **Create tests** at `tests/test_providers/test_{provider_name}.py`:
   - Create mock responses in `tests/mocks/{provider_name}/`
   - Test each method
   - Test error handling

Look at the existing providers (esimgo.py and zetexa.py) for reference patterns.
See CONTRIBUTING.md and docs/PROVIDER_CHECKLIST.md for guidelines.

Start by reading the OpenAPI spec file and then implement the provider step by step.
"""
    return prompt


def run_claude_code(prompt: str) -> None:
    """Invoke Claude Code with the prompt."""
    print("\n" + "=" * 60)
    print("Launching Claude Code for provider integration...")
    print("=" * 60 + "\n")

    try:
        # Use subprocess to invoke claude with the prompt
        process = subprocess.Popen(
            ["claude", "--print", prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Stream output
        if process.stdout:
            for line in process.stdout:
                print(line, end="")

        process.wait()

        if process.returncode != 0:
            print(f"\nClaude Code exited with code {process.returncode}")

    except FileNotFoundError:
        print("Error: 'claude' command not found.")
        print("Make sure Claude Code CLI is installed and in your PATH.")
        print("\nAlternatively, copy the prompt below and paste it into Claude Code:\n")
        print("-" * 60)
        print(prompt)
        print("-" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Integrate a new eSIM provider into the gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create scaffolding only (for manual implementation)
    %(prog)s airalo --scaffold

    # Generate with Claude Code from OpenAPI spec
    %(prog)s airalo ./specs/airalo-openapi.json

    # Preview what would be generated
    %(prog)s airalo ./specs/airalo-openapi.json --dry-run
        """,
    )
    parser.add_argument(
        "provider_name",
        help="Name of the provider (lowercase, e.g., 'airalo')",
    )
    parser.add_argument(
        "openapi_file",
        nargs="?",
        type=Path,
        help="Path to OpenAPI specification file (JSON or YAML)",
    )
    parser.add_argument(
        "--scaffold",
        action="store_true",
        help="Only create scaffolding from templates (no Claude Code)",
    )
    parser.add_argument(
        "--display-name",
        help="Display name for the provider (default: capitalized provider_name)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt without invoking Claude Code",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save prompt to file instead of invoking Claude",
    )

    args = parser.parse_args()

    # Validate provider name
    provider_name = args.provider_name.lower().replace("-", "_").replace(" ", "_")
    if not provider_name.isidentifier():
        print(f"Error: Invalid provider name '{args.provider_name}'")
        print("Provider name must be a valid Python identifier (letters, numbers, underscores)")
        sys.exit(1)

    display_name = args.display_name or provider_name.replace("_", " ").title()

    # Scaffold mode - just create files from templates
    if args.scaffold:
        create_scaffold(provider_name, display_name)
        return

    # OpenAPI mode - requires spec file
    if not args.openapi_file:
        print("Error: Either --scaffold or an OpenAPI file is required")
        print("\nUsage:")
        print(f"  {sys.argv[0]} {provider_name} --scaffold")
        print(f"  {sys.argv[0]} {provider_name} ./specs/openapi.json")
        sys.exit(1)

    # Check if provider already exists
    provider_file = PROVIDERS_DIR / f"{provider_name}.py"
    if provider_file.exists():
        print(f"Warning: Provider file already exists: {provider_file}")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != "y":
            sys.exit(0)

    # Load and analyze OpenAPI spec
    print(f"Loading OpenAPI spec from: {args.openapi_file}")
    spec = load_openapi_spec(args.openapi_file)

    # Build the prompt
    prompt = build_claude_prompt(provider_name, spec, args.openapi_file)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Prompt that would be sent to Claude Code:")
        print("=" * 60 + "\n")
        print(prompt)
        return

    if args.output:
        args.output.write_text(prompt)
        print(f"Prompt saved to: {args.output}")
        return

    # Run Claude Code
    run_claude_code(prompt)


if __name__ == "__main__":
    main()

"""Tests for catalog endpoints."""

import re
from typing import Any

from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "esim-gateway"


class TestCatalogEndpointsWithoutProvider:
    """Test catalog endpoints without provider header."""

    def test_list_countries_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/catalog/countries")
        assert response.status_code == 422

    def test_list_regions_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/catalog/regions")
        assert response.status_code == 422

    def test_list_packages_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/catalog/packages")
        assert response.status_code == 422

    def test_get_package_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/catalog/packages/test-id")
        assert response.status_code == 422


class TestInvalidProvider:
    """Test invalid provider handling."""

    def test_invalid_provider_header(self, client: TestClient) -> None:
        """Test that invalid provider returns 400."""
        response = client.get(
            "/catalog/countries",
            headers={"X-Provider": "invalid"},
        )
        assert response.status_code == 400
        assert "Unknown provider" in response.json()["detail"]


class TestESimGoCatalog:
    """Test eSIM Go catalog endpoints."""

    def test_list_countries_esimgo(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_catalogue: dict[str, Any],
    ) -> None:
        """Test listing countries from eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/catalogue?perPage=1000",
            json=esimgo_catalogue,
        )

        response = client.get(
            "/catalog/countries",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "total" in data
        assert data["total"] == len(data["countries"])

        # Check country structure
        for country in data["countries"]:
            assert "iso2" in country
            assert "name" in country

    def test_list_regions_esimgo(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_catalogue: dict[str, Any],
    ) -> None:
        """Test listing regions from eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/catalogue?perPage=1000",
            json=esimgo_catalogue,
        )

        response = client.get(
            "/catalog/regions",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "regions" in data
        assert "total" in data

        # Check region structure
        for region in data["regions"]:
            assert "id" in region
            assert "name" in region
            assert "countries" in region

    def test_list_packages_esimgo(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_catalogue: dict[str, Any],
    ) -> None:
        """Test listing packages from eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/catalogue?page=1&perPage=50",
            json=esimgo_catalogue,
        )

        response = client.get(
            "/catalog/packages",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert "page" in data
        assert "limit" in data

        # Check package structure
        for package in data["packages"]:
            assert "id" in package
            assert "name" in package
            assert "countries" in package
            assert "data" in package
            assert "validity_days" in package
            assert "price" in package

    def test_list_packages_with_country_filter(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_catalogue: dict[str, Any],
    ) -> None:
        """Test listing packages with country filter."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/catalogue?page=1&perPage=50&countries=DE",
            json=esimgo_catalogue,
        )

        response = client.get(
            "/catalog/packages?country=DE",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200

    def test_get_package_esimgo(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_catalogue: dict[str, Any],
    ) -> None:
        """Test getting single package from eSIM Go."""
        bundle = esimgo_catalogue["bundles"][0]
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/catalogue/bundle/esim_1GB_7D_DE",
            json={"bundle": bundle},
        )

        response = client.get(
            "/catalog/packages/esim_1GB_7D_DE",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "package" in data
        assert data["package"]["id"] == "esim_1GB_7D_DE"


class TestZetexaCatalog:
    """Test Zetexa catalog endpoints."""

    def test_list_countries_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_countries: list[dict[str, Any]],
    ) -> None:
        """Test listing countries from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock countries
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Countries-List",
            json=zetexa_countries,
        )

        response = client.get(
            "/catalog/countries",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "total" in data
        assert data["total"] == 3

        # Check that Zetexa-specific fields are mapped
        countries = data["countries"]
        assert len(countries) == 3
        for country in countries:
            assert "iso2" in country
            assert "name" in country

    def test_list_regions_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_regions: list[dict[str, Any]],
    ) -> None:
        """Test listing regions from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock regions
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Regions-List",
            json=zetexa_regions,
        )

        response = client.get(
            "/catalog/regions",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "regions" in data
        assert "total" in data
        assert data["total"] == 3

    def test_list_packages_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_regions: list[dict[str, Any]],
        zetexa_packages: list[dict[str, Any]],
    ) -> None:
        """Test listing packages from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock countries (needed for country lookup)
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Countries-List",
            json=[{"iso2": "DE", "iso3": "DEU", "name": "Germany", "image": None}],
        )
        # Mock regions (needed to get all packages)
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Regions-List",
            json=zetexa_regions,
        )
        # Mock packages - use regex that matches URL-encoded region names
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )

        response = client.get(
            "/catalog/packages",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert len(data["packages"]) == 3

        # Check unlimited package detection
        unlimited_pkg = next(p for p in data["packages"] if "Unlimited" in p["name"])
        assert unlimited_pkg["data"]["is_unlimited"] is True

    def test_list_packages_by_country_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_packages: list[dict[str, Any]],
    ) -> None:
        """Test listing packages by country from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock countries lookup
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Countries-List",
            json=[{"iso2": "DE", "iso3": "DEU", "name": "Germany", "image": None}],
        )
        # Mock packages filtered by country
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*country_code=DE.*"),
            json=zetexa_packages,
        )

        response = client.get(
            "/catalog/packages?country=DE",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data

    def test_get_package_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_regions: list[dict[str, Any]],
        zetexa_packages: list[dict[str, Any]],
    ) -> None:
        """Test getting single package from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock countries lookup
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Countries-List",
            json=[{"iso2": "DE", "iso3": "DEU", "name": "Germany", "image": None}],
        )
        # Mock regions
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Regions-List",
            json=zetexa_regions,
        )
        # Mock packages - use regex that matches any request
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )

        response = client.get(
            "/catalog/packages/1001",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "package" in data
        assert data["package"]["id"] == "1001"

    def test_get_package_not_found_zetexa(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_regions: list[dict[str, Any]],
        zetexa_packages: list[dict[str, Any]],
    ) -> None:
        """Test getting non-existent package from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock countries lookup
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Countries-List",
            json=[{"iso2": "DE", "iso3": "DEU", "name": "Germany", "image": None}],
        )
        # Mock regions
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Regions-List",
            json=zetexa_regions,
        )
        # Mock packages - use regex that matches any request
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v2/Packages-List\?.*"),
            json=zetexa_packages,
        )

        response = client.get(
            "/catalog/packages/nonexistent",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "package_not_found"


class TestESimCardCatalog:
    """Test esimCard catalog endpoints."""

    def test_list_countries_esimcard(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_countries: dict[str, Any],
    ) -> None:
        """Test listing countries from esimCard."""
        # Mock auth
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        # Mock countries
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/packages/country",
            json=esimcard_countries,
        )

        response = client.get(
            "/catalog/countries",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "total" in data
        assert data["total"] == 4

        # Check country structure
        for country in data["countries"]:
            assert "iso2" in country
            assert "name" in country

    def test_list_regions_esimcard(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_regions: dict[str, Any],
    ) -> None:
        """Test listing regions from esimCard."""
        # Mock auth
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        # Mock regions
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/packages/continent",
            json=esimcard_regions,
        )

        response = client.get(
            "/catalog/regions",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "regions" in data
        assert "total" in data
        assert data["total"] == 3

        # Check region structure
        for region in data["regions"]:
            assert "id" in region
            assert "name" in region

    def test_list_packages_esimcard(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_packages: dict[str, Any],
    ) -> None:
        """Test listing packages from esimCard."""
        # Mock auth
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        # Mock packages (DATA-ONLY)
        httpx_mock.add_response(
            url=re.compile(r"https://sandbox\.esimcard\.com/api/developer/reseller/packages\?.*package_type=DATA-ONLY.*"),
            json=esimcard_packages,
        )
        # Mock packages (DATA-VOICE-SMS)
        httpx_mock.add_response(
            url=re.compile(r"https://sandbox\.esimcard\.com/api/developer/reseller/packages\?.*package_type=DATA-VOICE-SMS.*"),
            json={"status": True, "data": []},
        )

        response = client.get(
            "/catalog/packages",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert "page" in data
        assert "limit" in data

        # Check package structure
        for package in data["packages"]:
            assert "id" in package
            assert "name" in package
            assert "data" in package
            assert "validity_days" in package
            assert "price" in package

    def test_get_package_esimcard(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_package_detail: dict[str, Any],
    ) -> None:
        """Test getting single package from esimCard."""
        # Mock auth
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        # Mock package detail
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/package/detail/101",
            json=esimcard_package_detail,
        )

        response = client.get(
            "/catalog/packages/101",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "package" in data
        assert data["package"]["id"] == "101"
        assert data["package"]["name"] == "US 1GB 7 Days"

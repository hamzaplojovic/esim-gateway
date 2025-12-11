"""Tests for order endpoints."""

import re
from typing import Any

from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock


class TestOrderEndpointsWithoutProvider:
    """Test order endpoints without provider header."""

    def test_list_orders_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/orders")
        assert response.status_code == 422

    def test_get_order_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.get("/orders/test-order-id")
        assert response.status_code == 422

    def test_create_order_missing_provider(self, client: TestClient) -> None:
        """Test that missing provider header returns 422."""
        response = client.post(
            "/orders",
            json={"items": [{"package_id": "test-pkg", "quantity": 1}]},
        )
        assert response.status_code == 422


class TestESimGoOrders:
    """Test eSIM Go order endpoints."""

    def test_list_orders(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_orders_list: dict[str, Any],
    ) -> None:
        """Test listing orders from eSIM Go."""
        httpx_mock.add_response(
            url=re.compile(r"https://api\.esim-go\.com/v2\.5/orders\?.*"),
            json=esimgo_orders_list,
        )

        response = client.get(
            "/orders",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] == 2
        assert len(data["orders"]) == 2

        # Check order structure
        order = data["orders"][0]
        assert "order_id" in order
        assert "status" in order
        assert "total" in order
        assert "currency" in order
        assert "items" in order

    def test_list_orders_with_pagination(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_orders_list: dict[str, Any],
    ) -> None:
        """Test listing orders with pagination params."""
        httpx_mock.add_response(
            url=re.compile(r"https://api\.esim-go\.com/v2\.5/orders\?.*page=2.*"),
            json=esimgo_orders_list,
        )

        response = client.get(
            "/orders?page=2&limit=10",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_get_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_order_single: dict[str, Any],
    ) -> None:
        """Test getting single order from eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/orders/ORD-ESG-001",
            json=esimgo_order_single,
        )

        response = client.get(
            "/orders/ORD-ESG-001",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "ORD-ESG-001"
        assert order["status"] == "completed"
        assert order["total"] == 12.00
        assert order["assigned"] is True
        assert len(order["items"]) == 1

        # Check eSIM details
        item = order["items"][0]
        assert item["package_id"] == "esim_3GB_30D_EU"
        assert len(item["esims"]) == 1
        assert item["esims"][0]["iccid"] == "8901234567890123456"

    def test_get_order_not_found(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test getting non-existent order from eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/orders/nonexistent",
            status_code=404,
            json={"error": "Order not found"},
        )

        response = client.get(
            "/orders/nonexistent",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "order_not_found"

    def test_create_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_order_create: dict[str, Any],
    ) -> None:
        """Test creating an order with eSIM Go."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/orders",
            method="POST",
            json=esimgo_order_create,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "esimgo"},
            json={
                "items": [{"package_id": "esim_1GB_7D_DE", "quantity": 1}],
                "assign": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "ORD-ESG-003"
        assert order["status"] == "completed"
        assert len(order["items"]) == 1
        assert order["items"][0]["esims"][0]["iccid"] == "8901234567890123457"

    def test_create_order_multiple_items(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_order_create: dict[str, Any],
    ) -> None:
        """Test creating an order with multiple items."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/orders",
            method="POST",
            json=esimgo_order_create,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "esimgo"},
            json={
                "items": [
                    {"package_id": "esim_1GB_7D_DE", "quantity": 2},
                    {"package_id": "esim_UNL_7D_US", "quantity": 1},
                ],
                "assign": True,
                "allow_reassign": True,
            },
        )

        assert response.status_code == 200

    def test_create_order_empty_items_fails(
        self,
        client: TestClient,
    ) -> None:
        """Test that creating order with empty items fails validation."""
        response = client.post(
            "/orders",
            headers={"X-Provider": "esimgo"},
            json={"items": []},
        )

        assert response.status_code == 422


class TestZetexaOrders:
    """Test Zetexa order endpoints."""

    def test_list_orders(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_orders_list: dict[str, Any],
    ) -> None:
        """Test listing orders from Zetexa."""
        # Mock auth
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        # Mock orders list
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v1/Orders-List\?.*"),
            json=zetexa_orders_list,
        )

        response = client.get(
            "/orders",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["orders"]) == 3

        # Check order structure
        order = data["orders"][0]
        assert order["order_id"] == "ZTX-ORD-001"
        assert order["status"] == "Completed"
        assert order["total"] == 5.09
        assert order["currency"] == "USD"

    def test_list_orders_with_pagination(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_orders_list: dict[str, Any],
    ) -> None:
        """Test listing orders with pagination params."""
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v1/Orders-List\?.*page=2.*"),
            json=zetexa_orders_list,
        )

        response = client.get(
            "/orders?page=2&limit=25",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 25

    def test_get_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_order_qrcode: dict[str, Any],
    ) -> None:
        """Test getting single order from Zetexa (uses QR code endpoint)."""
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v1/get-qrcode-details\?.*"),
            json=zetexa_order_qrcode,
        )

        response = client.get(
            "/orders/ZTX-ORD-001",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "ZTX-ORD-001"
        assert order["status"] == "Active"
        assert order["assigned"] is True
        assert len(order["items"]) == 1

        # Check eSIM details
        item = order["items"][0]
        assert item["esims"][0]["iccid"] == "8944500000000000001"
        assert item["esims"][0]["lpa_string"] == "LPA:1$smdp.zetexa.com$ZTX-MATCH-001"

    def test_get_order_not_found(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
    ) -> None:
        """Test getting non-existent order from Zetexa."""
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://api\.zetexa\.com/v1/get-qrcode-details\?.*"),
            json={"success": False, "message": "Order not found"},
        )

        response = client.get(
            "/orders/nonexistent",
            headers={"X-Provider": "zetexa"},
        )

        assert response.status_code == 502
        data = response.json()
        assert "error" in data

    def test_create_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
        zetexa_order_create: dict[str, Any],
    ) -> None:
        """Test creating an order with Zetexa."""
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )
        httpx_mock.add_response(
            url="https://api.zetexa.com/v2/Create-Order",
            method="POST",
            json=zetexa_order_create,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "zetexa"},
            json={
                "items": [{"package_id": "1001", "quantity": 1}],
                "customer": {
                    "email": "test@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "country": "US",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "ZTX-ORD-004"
        assert order["status"] == "Completed"
        assert len(order["items"]) == 1
        assert order["items"][0]["esims"][0]["iccid"] == "8944500000000000002"

    def test_create_order_missing_customer_fails(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        zetexa_token: dict[str, Any],
    ) -> None:
        """Test that creating Zetexa order without customer fails."""
        httpx_mock.add_response(
            url="https://api.zetexa.com/v1/Create-Token",
            method="POST",
            json=zetexa_token,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "zetexa"},
            json={
                "items": [{"package_id": "1001", "quantity": 1}],
            },
        )

        # Zetexa requires customer info
        assert response.status_code == 502
        data = response.json()
        assert "Customer info required" in data["error"]["message"]


class TestESimCardOrders:
    """Test esimCard order endpoints."""

    def test_list_orders(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_my_esims: dict[str, Any],
    ) -> None:
        """Test listing orders from esimCard."""
        # Mock auth
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        # Mock orders list (esimCard uses my-bundles endpoint)
        httpx_mock.add_response(
            url=re.compile(r"https://sandbox\.esimcard\.com/api/developer/reseller/my-bundles\?.*"),
            json=esimcard_my_esims,
        )

        response = client.get(
            "/orders",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["orders"]) == 2

        # Check order structure
        order = data["orders"][0]
        assert "order_id" in order
        assert "status" in order
        assert "items" in order

    def test_list_orders_with_pagination(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_my_esims: dict[str, Any],
    ) -> None:
        """Test listing orders with pagination params."""
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        httpx_mock.add_response(
            url=re.compile(r"https://sandbox\.esimcard\.com/api/developer/reseller/my-bundles\?.*page=2.*"),
            json=esimcard_my_esims,
        )

        response = client.get(
            "/orders?page=2&limit=10",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_get_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_esim_detail: dict[str, Any],
    ) -> None:
        """Test getting single order from esimCard."""
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/order/8901234567890123456",
            json=esimcard_esim_detail,
        )

        response = client.get(
            "/orders/8901234567890123456",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "8901234567890123456"
        assert order["status"] == "completed"
        assert order["assigned"] is True
        assert len(order["items"]) == 1

        # Check eSIM details
        item = order["items"][0]
        assert item["esims"][0]["iccid"] == "8901234567890123456"
        assert item["esims"][0]["lpa_string"] == "LPA:1$smdp.io$K2-1234567890"

    def test_get_order_not_found(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
    ) -> None:
        """Test getting non-existent order from esimCard."""
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/order/nonexistent",
            json={"status": False, "message": "Order not found"},
        )

        response = client.get(
            "/orders/nonexistent",
            headers={"X-Provider": "esimcard"},
        )

        assert response.status_code == 502
        data = response.json()
        assert "error" in data

    def test_create_order(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimcard_login: dict[str, Any],
        esimcard_purchase: dict[str, Any],
    ) -> None:
        """Test creating an order with esimCard."""
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/login",
            method="POST",
            json=esimcard_login,
        )
        httpx_mock.add_response(
            url="https://sandbox.esimcard.com/api/developer/reseller/package/purchase",
            method="POST",
            json=esimcard_purchase,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "esimcard"},
            json={
                "items": [{"package_id": "101", "quantity": 1}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "order" in data
        order = data["order"]
        assert order["order_id"] == "8901234567890123458"
        assert order["status"] == "completed"
        assert len(order["items"]) == 1
        assert order["items"][0]["esims"][0]["iccid"] == "8901234567890123458"


class TestOrdersErrorHandling:
    """Test error handling for order endpoints."""

    def test_invalid_provider_for_orders(self, client: TestClient) -> None:
        """Test that invalid provider returns 400."""
        response = client.get(
            "/orders",
            headers={"X-Provider": "invalid"},
        )
        assert response.status_code == 400
        assert "Unknown provider" in response.json()["detail"]

    def test_provider_error_propagates(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test that provider errors are properly handled."""
        httpx_mock.add_response(
            url=re.compile(r"https://api\.esim-go\.com/v2\.5/orders\?.*"),
            status_code=500,
            json={"error": "Internal server error"},
        )

        response = client.get(
            "/orders",
            headers={"X-Provider": "esimgo"},
        )

        assert response.status_code == 502
        data = response.json()
        assert "error" in data


class TestOrderItemValidation:
    """Test order item validation."""

    def test_order_item_requires_package_id(
        self,
        client: TestClient,
    ) -> None:
        """Test that order item requires package_id."""
        response = client.post(
            "/orders",
            headers={"X-Provider": "esimgo"},
            json={"items": [{"quantity": 1}]},
        )
        assert response.status_code == 422

    def test_order_item_defaults_quantity_to_one(
        self,
        client: TestClient,
        httpx_mock: HTTPXMock,
        esimgo_order_create: dict[str, Any],
    ) -> None:
        """Test that order item defaults quantity to 1."""
        httpx_mock.add_response(
            url="https://api.esim-go.com/v2.5/orders",
            method="POST",
            json=esimgo_order_create,
        )

        response = client.post(
            "/orders",
            headers={"X-Provider": "esimgo"},
            json={"items": [{"package_id": "esim_1GB_7D_DE"}]},
        )

        assert response.status_code == 200

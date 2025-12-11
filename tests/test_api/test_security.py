"""Tests for security features: API key authentication configuration."""

from esim_gateway.config import Settings


class TestConfigHelpers:
    """Test configuration helper methods for API key authentication."""

    def test_get_api_keys_empty(self) -> None:
        """Test get_api_keys returns empty set when not configured."""
        settings = Settings(api_keys="")
        assert settings.get_api_keys() == set()

    def test_get_api_keys_single(self) -> None:
        """Test get_api_keys with single key."""
        settings = Settings(api_keys="my-key")
        assert settings.get_api_keys() == {"my-key"}

    def test_get_api_keys_multiple(self) -> None:
        """Test get_api_keys with multiple keys."""
        settings = Settings(api_keys="key1,key2,key3")
        assert settings.get_api_keys() == {"key1", "key2", "key3"}

    def test_get_api_keys_strips_whitespace(self) -> None:
        """Test get_api_keys strips whitespace from keys."""
        settings = Settings(api_keys="key1 , key2 , key3")
        assert settings.get_api_keys() == {"key1", "key2", "key3"}

    def test_get_api_keys_ignores_empty_entries(self) -> None:
        """Test get_api_keys ignores empty entries from extra commas."""
        settings = Settings(api_keys="key1,,key2,")
        assert settings.get_api_keys() == {"key1", "key2"}

    def test_is_valid_api_key_with_valid_key(self) -> None:
        """Test is_valid_api_key returns True for valid key."""
        settings = Settings(api_keys="valid-key,another-key")
        assert settings.is_valid_api_key("valid-key") is True
        assert settings.is_valid_api_key("another-key") is True

    def test_is_valid_api_key_with_invalid_key(self) -> None:
        """Test is_valid_api_key returns False for invalid key."""
        settings = Settings(api_keys="valid-key")
        assert settings.is_valid_api_key("invalid-key") is False

    def test_is_valid_api_key_with_no_keys_configured(self) -> None:
        """Test is_valid_api_key returns False when no keys configured."""
        settings = Settings(api_keys="")
        assert settings.is_valid_api_key("any-key") is False

    def test_generate_api_key_creates_unique_keys(self) -> None:
        """Test generate_api_key creates unique keys."""
        key1 = Settings.generate_api_key()
        key2 = Settings.generate_api_key()

        assert len(key1) > 30  # URL-safe base64 of 32 bytes
        assert key1 != key2

    def test_generate_api_key_produces_url_safe_keys(self) -> None:
        """Test generate_api_key produces URL-safe keys."""
        key = Settings.generate_api_key()
        # URL-safe base64 only contains alphanumeric, dash, underscore
        assert all(c.isalnum() or c in "-_" for c in key)


class TestDefaultSettings:
    """Test default security settings.

    Note: Tests for actual default values are limited because conftest.py sets
    REQUIRE_API_KEY=false for testing. We test explicit settings instead.
    """

    def test_require_api_key_can_be_enabled(self) -> None:
        """Test that API key requirement can be explicitly enabled."""
        settings = Settings(require_api_key=True)
        assert settings.require_api_key is True

    def test_default_rate_limit(self) -> None:
        """Test default rate limit settings."""
        settings = Settings()
        assert settings.rate_limit_requests == 100
        assert settings.rate_limit_window == "minute"

    def test_default_retry_settings(self) -> None:
        """Test default retry settings."""
        settings = Settings()
        assert settings.retry_max_attempts == 3
        assert settings.retry_min_wait == 1.0
        assert settings.retry_max_wait == 10.0

    def test_default_circuit_breaker_settings(self) -> None:
        """Test default circuit breaker settings."""
        settings = Settings()
        assert settings.circuit_breaker_threshold == 5
        assert settings.circuit_breaker_timeout == 60.0

    def test_default_http_settings(self) -> None:
        """Test default HTTP client settings."""
        settings = Settings()
        assert settings.http_timeout == 30.0
        assert settings.http_max_connections == 20
        assert settings.http_max_keepalive == 10

"""Shared utilities for eSIM Gateway providers.

This module contains common parsing, caching, and status mapping utilities
used across all provider implementations.
"""

import time
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T", bound=Enum)


def parse_datetime(date_str: str | None, formats: list[str] | None = None) -> datetime | None:
    """Parse datetime from various string formats.

    Args:
        date_str: Date string to parse
        formats: List of datetime formats to try. Defaults to common formats.

    Returns:
        Parsed datetime or None if parsing fails
    """
    if not date_str:
        return None

    if formats is None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d %b %Y %H:%M:%S",  # Zetexa format: "10 Dec 2025 10:29:44"
        ]

    # Handle ISO format with Z suffix
    normalized = date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue

    # Try fromisoformat as fallback
    try:
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def parse_price(price: Any) -> float | None:
    """Parse price from various formats.

    Handles formats like:
    - Numeric: 5.09, 5
    - String with currency: "$ 5.09", "$5.09", "USD 5.09"
    - String with commas: "1,234.56"

    Args:
        price: Price value in any format

    Returns:
        Float price or None if parsing fails
    """
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        # Remove currency symbols and whitespace
        cleaned = price.replace("$", "").replace("€", "").replace("£", "")
        cleaned = cleaned.replace("USD", "").replace("EUR", "").replace("GBP", "")
        cleaned = cleaned.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def map_status(value: str, mapping: dict[str, T], default: T) -> T:
    """Map a provider status string to a unified enum value.

    Args:
        value: Status string from provider
        mapping: Dictionary mapping provider values to enum values
        default: Default enum value if no match found

    Returns:
        Mapped enum value
    """
    if not value:
        return default
    # Try exact match first
    if value in mapping:
        return mapping[value]
    # Try uppercase
    if value.upper() in mapping:
        return mapping[value.upper()]
    # Try lowercase
    if value.lower() in mapping:
        return mapping[value.lower()]
    return default


class TTLCache:
    """Simple TTL-based cache for provider data.

    Usage:
        cache = TTLCache(ttl=300)  # 5 minutes

        # Check and get
        if not cache.is_valid():
            data = await fetch_data()
            cache.set(data)

        return cache.get()
    """

    def __init__(self, ttl: int = 300):
        """Initialize cache with TTL in seconds."""
        self._data: Any = None
        self._timestamp: float = 0
        self._ttl = ttl

    def is_valid(self) -> bool:
        """Check if cache has valid data."""
        if self._data is None:
            return False
        return (time.time() - self._timestamp) < self._ttl

    def get(self) -> Any:
        """Get cached data (may be stale or None)."""
        return self._data

    def set(self, data: Any) -> None:
        """Set cache data and update timestamp."""
        self._data = data
        self._timestamp = time.time()

    def clear(self) -> None:
        """Clear the cache."""
        self._data = None
        self._timestamp = 0

    def get_or_none(self) -> Any:
        """Get cached data if valid, otherwise None."""
        return self._data if self.is_valid() else None


class MultiCache:
    """Multiple TTL caches with named keys.

    Usage:
        caches = MultiCache(ttl=300)

        if not caches.is_valid("countries"):
            data = await fetch_countries()
            caches.set("countries", data)

        return caches.get("countries")
    """

    def __init__(self, ttl: int = 300):
        """Initialize with default TTL."""
        self._ttl = ttl
        self._caches: dict[str, TTLCache] = {}

    def _get_cache(self, key: str) -> TTLCache:
        """Get or create cache for key."""
        if key not in self._caches:
            self._caches[key] = TTLCache(self._ttl)
        return self._caches[key]

    def is_valid(self, key: str) -> bool:
        """Check if cache for key has valid data."""
        return self._get_cache(key).is_valid()

    def get(self, key: str) -> Any:
        """Get cached data for key."""
        return self._get_cache(key).get()

    def set(self, key: str, data: Any) -> None:
        """Set cached data for key."""
        self._get_cache(key).set(data)

    def clear(self, key: str | None = None) -> None:
        """Clear specific cache or all caches."""
        if key is None:
            self._caches.clear()
        elif key in self._caches:
            self._caches[key].clear()

"""Tests for resilience patterns: retry and circuit breaker."""

import asyncio

import pytest

from esim_gateway.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breakers,
)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset circuit breakers before each test."""
        reset_circuit_breakers()

    def test_initial_state_is_closed(self) -> None:
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_keeps_circuit_closed(self) -> None:
        """Test successful calls keep circuit closed."""
        cb = CircuitBreaker(name="test", threshold=3)

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_below_threshold_keep_circuit_closed(self) -> None:
        """Test failures below threshold don't open circuit."""
        cb = CircuitBreaker(name="test", threshold=3)

        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_at_threshold_open_circuit(self) -> None:
        """Test failures at threshold open the circuit."""
        cb = CircuitBreaker(name="test", threshold=3)

        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))
        await cb.record_failure(Exception("error 3"))

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_requests(self) -> None:
        """Test open circuit rejects requests."""
        cb = CircuitBreaker(name="test", threshold=2)

        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))

        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        cb = CircuitBreaker(name="test", threshold=2, timeout=0.1)

        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes_circuit(self) -> None:
        """Test success in half-open state closes circuit."""
        cb = CircuitBreaker(name="test", threshold=2, timeout=0.1)

        # Open the circuit
        await cb.record_failure(Exception("error 1"))
        await cb.record_failure(Exception("error 2"))

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record success
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_decorator_records_success(self) -> None:
        """Test circuit breaker decorator records success."""
        cb = CircuitBreaker(name="test", threshold=3)

        @cb
        async def successful_func() -> str:
            return "success"

        result = await successful_func()
        assert result == "success"
        assert cb._failures == 0

    @pytest.mark.asyncio
    async def test_decorator_records_failure(self) -> None:
        """Test circuit breaker decorator records failure."""
        cb = CircuitBreaker(name="test", threshold=3)

        @cb
        async def failing_func() -> str:
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await failing_func()

        assert cb._failures == 1

    @pytest.mark.asyncio
    async def test_decorator_rejects_when_open(self) -> None:
        """Test circuit breaker decorator rejects when open."""
        cb = CircuitBreaker(name="test", threshold=2)

        @cb
        async def some_func() -> str:
            raise ValueError("error")

        # Open the circuit
        with pytest.raises(ValueError):
            await some_func()
        with pytest.raises(ValueError):
            await some_func()

        # Now should reject
        with pytest.raises(CircuitBreakerOpenError):
            await some_func()


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry functions."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset circuit breakers before each test."""
        reset_circuit_breakers()

    def test_get_circuit_breaker_creates_new(self) -> None:
        """Test get_circuit_breaker creates new breaker if not exists."""
        cb = get_circuit_breaker("provider1")
        assert cb.name == "provider1"

    def test_get_circuit_breaker_returns_same_instance(self) -> None:
        """Test get_circuit_breaker returns same instance for same provider."""
        cb1 = get_circuit_breaker("provider1")
        cb2 = get_circuit_breaker("provider1")
        assert cb1 is cb2

    def test_get_circuit_breaker_different_providers(self) -> None:
        """Test get_circuit_breaker returns different instances for different providers."""
        cb1 = get_circuit_breaker("provider1")
        cb2 = get_circuit_breaker("provider2")
        assert cb1 is not cb2

    def test_reset_clears_all_breakers(self) -> None:
        """Test reset_circuit_breakers clears all breakers."""
        cb1 = get_circuit_breaker("provider1")
        get_circuit_breaker("provider2")

        reset_circuit_breakers()

        cb1_new = get_circuit_breaker("provider1")
        assert cb1 is not cb1_new

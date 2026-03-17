# backend/services/integration/circuit_breaker.py

"""
Circuit breaker pattern for e-commerce API resilience.

Prevents cascade failures by failing fast when a service is down.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 30.0  # Seconds before trying half-open
    excluded_exceptions: tuple = ()  # Exceptions that don't count


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""

    pass


class CircuitBreaker:
    """
    Circuit breaker prevents cascade failures.

    States:
    - CLOSED: Normal operation. Track failures.
    - OPEN: Service down. Reject all requests.
    - HALF_OPEN: Testing recovery. Allow limited requests.

    Usage:
        breaker = CircuitBreaker("store-url")
        async with breaker:
            response = await client.get(...)
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    async def _check_state(self):
        """Check and potentially transition state"""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout:
                        logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0

    async def record_success(self):
        """Record a successful call"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self, exception: Exception | None = None):
        """Record a failed call"""
        if exception and isinstance(exception, self.config.excluded_exceptions):
            return

        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN")
                self._state = CircuitState.OPEN

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(f"Circuit {self.name}: CLOSED -> OPEN ({self._failure_count} failures)")
                    self._state = CircuitState.OPEN

    async def __aenter__(self):
        """Check if request is allowed"""
        await self._check_state()

        if self._state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit {self.name} is OPEN. Try again in {self.config.timeout}s.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record result"""
        if exc_type is None:
            await self.record_success()
        else:
            await self.record_failure(exc_val)
        return False

    def get_status(self) -> dict:
        """Get current status"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitBreakerRegistry:
    """
    Registry of circuit breakers per store.
    Each store gets its own breaker.
    """

    def __init__(self, default_config: CircuitBreakerConfig | None = None):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_config = default_config or CircuitBreakerConfig()
        self._lock = asyncio.Lock()

    async def get(self, store_url: str) -> CircuitBreaker:
        """Get or create circuit breaker for a store"""
        async with self._lock:
            if store_url not in self._breakers:
                self._breakers[store_url] = CircuitBreaker(name=store_url, config=self._default_config)
            return self._breakers[store_url]

    async def reset(self, store_url: str):
        """Reset circuit breaker for a store"""
        async with self._lock:
            if store_url in self._breakers:
                del self._breakers[store_url]

    async def get_all_status(self) -> list[dict]:
        """Get status of all circuit breakers"""
        async with self._lock:
            return [b.get_status() for b in self._breakers.values()]


# Global instance
circuit_breaker_registry = CircuitBreakerRegistry()

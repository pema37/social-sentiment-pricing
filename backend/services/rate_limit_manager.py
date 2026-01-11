"""
Rate Limit Circuit Breaker Manager

Implements a circuit breaker pattern for external API rate limits.
When an API returns 429 Too Many Requests, the circuit opens and
all subsequent calls fail fast until the cooldown period expires.

Usage:
    from services.rate_limit_manager import (
        is_api_available,
        record_api_success,
        record_api_rate_limit,
    )
    
    if is_api_available("openai"):
        try:
            result = await openai_call()
            record_api_success("openai")
        except RateLimitError:
            record_api_rate_limit("openai", retry_after=60)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation, requests allowed
    OPEN = "open"           # Rate limited, requests blocked
    HALF_OPEN = "half_open" # Testing if rate limit has reset


@dataclass
class CircuitBreaker:
    """Circuit breaker for a specific API service."""
    name: str
    state: CircuitState = CircuitState.CLOSED
    opened_at: Optional[datetime] = None
    cooldown_seconds: int = 60
    failure_count: int = 0
    failure_threshold: int = 2
    last_failure_message: str = ""
    
    def is_available(self) -> bool:
        """Check if the API is available for requests."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self.opened_at:
                elapsed = (datetime.now(timezone.utc) - self.opened_at).total_seconds()
                if elapsed >= self.cooldown_seconds:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit {self.name} → HALF_OPEN after {elapsed:.0f}s")
                    return True
            return False
        
        # HALF_OPEN - allow one test request
        return True
    
    def record_success(self):
        """Record a successful API call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit {self.name} → CLOSED (success)")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        self.last_failure_message = ""
    
    def record_failure(self, error_message: str = "", is_rate_limit: bool = False):
        """Record a failed API call."""
        self.failure_count += 1
        self.last_failure_message = error_message
        
        # Rate limits immediately open the circuit
        if is_rate_limit or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.now(timezone.utc)
            logger.warning(
                f"Circuit {self.name} → OPEN for {self.cooldown_seconds}s. "
                f"Reason: {error_message}"
            )
    
    def get_status(self) -> dict:
        """Get current circuit status."""
        remaining = 0
        if self.state == CircuitState.OPEN and self.opened_at:
            elapsed = (datetime.now(timezone.utc) - self.opened_at).total_seconds()
            remaining = max(0, self.cooldown_seconds - elapsed)
        
        return {
            "name": self.name,
            "state": self.state.value,
            "cooldown_remaining": int(remaining),
            "failure_count": self.failure_count,
        }


class RateLimitManager:
    """Manages rate limit circuit breakers for multiple APIs."""
    
    _instance: Optional["RateLimitManager"] = None
    
    def __init__(self):
        self.circuits: dict[str, CircuitBreaker] = {}
        self._configs = {
            "openai": {"cooldown_seconds": 60, "failure_threshold": 2},
            "gemini": {"cooldown_seconds": 60, "failure_threshold": 2},
        }
    
    @classmethod
    def get_instance(cls) -> "RateLimitManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = RateLimitManager()
        return cls._instance
    
    def get_circuit(self, api_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for an API."""
        if api_name not in self.circuits:
            cfg = self._configs.get(api_name, {})
            self.circuits[api_name] = CircuitBreaker(
                name=api_name,
                cooldown_seconds=cfg.get("cooldown_seconds", 60),
                failure_threshold=cfg.get("failure_threshold", 2),
            )
        return self.circuits[api_name]
    
    def is_available(self, api_name: str) -> bool:
        """Check if an API is available (circuit not open)."""
        return self.get_circuit(api_name).is_available()
    
    def record_success(self, api_name: str):
        """Record a successful API call."""
        self.get_circuit(api_name).record_success()
    
    def record_rate_limit(self, api_name: str, retry_after: Optional[int] = None):
        """Record a rate limit (429) response."""
        circuit = self.get_circuit(api_name)
        if retry_after:
            circuit.cooldown_seconds = max(retry_after, circuit.cooldown_seconds)
        circuit.record_failure("Rate limit (429)", is_rate_limit=True)
    
    def record_failure(self, api_name: str, error_message: str = ""):
        """Record a non-rate-limit failure."""
        self.get_circuit(api_name).record_failure(error_message)
    
    def get_all_status(self) -> dict:
        """Get status of all circuit breakers."""
        return {name: c.get_status() for name, c in self.circuits.items()}


# ============================================================================
# Module-level convenience functions (import these in other files)
# ============================================================================

_manager: Optional[RateLimitManager] = None


def get_rate_limit_manager() -> RateLimitManager:
    """Get the global rate limit manager instance."""
    global _manager
    if _manager is None:
        _manager = RateLimitManager.get_instance()
    return _manager


def is_api_available(api_name: str) -> bool:
    """Check if an API is available."""
    return get_rate_limit_manager().is_available(api_name)


def record_api_success(api_name: str):
    """Record successful API call."""
    get_rate_limit_manager().record_success(api_name)


def record_api_rate_limit(api_name: str, retry_after: Optional[int] = None):
    """Record rate limit hit."""
    get_rate_limit_manager().record_rate_limit(api_name, retry_after)


def record_api_failure(api_name: str, error: str = ""):
    """Record API failure."""
    get_rate_limit_manager().record_failure(api_name, error)


    
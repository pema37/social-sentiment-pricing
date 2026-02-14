# backend/services/integration/rate_limit.py

"""
Rate limit tracking for e-commerce APIs.

Proactively tracks API rate limits to avoid hitting them.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    """Track rate limit state for a store"""
    remaining: Optional[int] = None
    limit: Optional[int] = None
    reset_at: Optional[datetime] = None
    is_limited: bool = False
    last_request_at: Optional[datetime] = None
    
    def update_from_shopify_headers(self, headers: dict):
        """Update state from Shopify response headers"""
        # Shopify: X-Shopify-Shop-Api-Call-Limit: 39/40
        call_limit = headers.get("X-Shopify-Shop-Api-Call-Limit")
        if call_limit and "/" in call_limit:
            current, limit = call_limit.split("/")
            self.remaining = int(limit) - int(current)
            self.limit = int(limit)
            self.is_limited = self.remaining <= 2
        self.last_request_at = datetime.now(UTC)
    
    def update_from_woocommerce_headers(self, headers: dict):
        """Update state from WooCommerce response headers"""
        # WooCommerce doesn't have standard rate limit headers
        self.last_request_at = datetime.now(UTC)
    
    def mark_rate_limited(self, retry_after: Optional[int] = None):
        """Mark as rate limited (e.g., after receiving 429)"""
        self.is_limited = True
        if retry_after:
            self.reset_at = datetime.now(UTC)
    
    def should_wait(self) -> bool:
        """Check if we should wait before making a request"""
        if self.is_limited:
            if self.reset_at and datetime.now(UTC) > self.reset_at:
                self.is_limited = False
                return False
            return True
        return False
    
    def get_wait_time(self) -> float:
        """Get recommended wait time in seconds"""
        if not self.is_limited:
            return 0.0
        if self.reset_at:
            delta = (self.reset_at - datetime.now(UTC)).total_seconds()
            return max(0.0, delta)
        return 1.0


class RateLimitTracker:
    """
    Track rate limits per store to proactively avoid hitting limits.
    Thread-safe for use across async tasks.
    """
    
    def __init__(self):
        self._states: dict[str, RateLimitState] = {}
        self._lock = asyncio.Lock()
    
    async def get_state(self, store_url: str) -> RateLimitState:
        """Get rate limit state for a store"""
        async with self._lock:
            if store_url not in self._states:
                self._states[store_url] = RateLimitState()
            return self._states[store_url]
    
    async def update_from_response(
        self, 
        store_url: str, 
        headers: dict,
        platform: str = "shopify"
    ):
        """Update rate limit state from response headers"""
        state = await self.get_state(store_url)
        async with self._lock:
            if platform == "shopify":
                state.update_from_shopify_headers(headers)
            elif platform == "woocommerce":
                state.update_from_woocommerce_headers(headers)
    
    async def mark_rate_limited(
        self, 
        store_url: str, 
        retry_after: Optional[int] = None
    ):
        """Mark a store as rate limited"""
        state = await self.get_state(store_url)
        async with self._lock:
            state.mark_rate_limited(retry_after)
    
    async def wait_if_needed(self, store_url: str) -> float:
        """
        Wait if rate limited. Returns actual wait time.
        """
        state = await self.get_state(store_url)
        if state.should_wait():
            wait_time = state.get_wait_time()
            if wait_time > 0:
                logger.info(
                    f"Rate limit active for {store_url}, waiting {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)
                return wait_time
        return 0.0
    
    async def clear(self, store_url: str):
        """Clear rate limit state for a store"""
        async with self._lock:
            if store_url in self._states:
                del self._states[store_url]


# Global instance
rate_limit_tracker = RateLimitTracker()

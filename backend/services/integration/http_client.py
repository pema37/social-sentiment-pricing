# backend/services/integration/http_client.py

"""
HTTP client with built-in retry, rate limiting, and circuit breaker.
"""

from typing import Optional

import httpx

from .retry import RetryConfig, DEFAULT_RETRY_CONFIG, execute_with_retry
from .rate_limit import rate_limit_tracker
from .circuit_breaker import circuit_breaker_registry, CircuitBreaker


class RetryableClient:
    """
    HTTP client with retry, rate limit, and circuit breaker.
    
    Usage:
        async with RetryableClient(store_url, "shopify") as client:
            response = await client.get(url, headers=headers)
    """
    
    def __init__(
        self,
        store_url: str,
        platform: str,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0,
        use_circuit_breaker: bool = True
    ):
        self.store_url = store_url
        self.platform = platform
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self.timeout = timeout
        self.use_circuit_breaker = use_circuit_breaker
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        if self.use_circuit_breaker:
            self._circuit_breaker = await circuit_breaker_registry.get(self.store_url)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    async def _request(
        self,
        method: str,
        url: str,
        operation_name: str = "request",
        **kwargs
    ) -> httpx.Response:
        """Make request with retry, rate limit, and circuit breaker"""
        
        if self._circuit_breaker:
            async with self._circuit_breaker:
                return await self._do_request_with_retry(
                    method, url, operation_name, **kwargs
                )
        else:
            return await self._do_request_with_retry(
                method, url, operation_name, **kwargs
            )
    
    async def _do_request_with_retry(
        self,
        method: str,
        url: str,
        operation_name: str,
        **kwargs
    ) -> httpx.Response:
        """Internal: handles retry and rate limiting"""
        
        await rate_limit_tracker.wait_if_needed(self.store_url)
        
        async def _do_request():
            response = await self._client.request(method, url, **kwargs)
            
            await rate_limit_tracker.update_from_response(
                self.store_url,
                dict(response.headers),
                self.platform
            )
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                await rate_limit_tracker.mark_rate_limited(
                    self.store_url,
                    int(retry_after) if retry_after else None
                )
            
            response.raise_for_status()
            return response
        
        return await execute_with_retry(
            _do_request,
            config=self.retry_config,
            operation_name=operation_name
        )
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("GET", url, f"GET {url}", **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("POST", url, f"POST {url}", **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("PUT", url, f"PUT {url}", **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("DELETE", url, f"DELETE {url}", **kwargs)
    
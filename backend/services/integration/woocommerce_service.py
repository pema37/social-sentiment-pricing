# backend/services/integration/woocommerce_service.py

"""
WooCommerce Integration Service.
"""

import hmac
import hashlib
import base64
import logging
from datetime import datetime
from typing import Optional, List

import httpx

from .base import EcommerceService
from .models import (
    OAuthResult,
    ExternalProduct,
    ExternalProductVariant,
    ProductSyncResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    PriceUpdateResult,
    WebhookRegistration,
    ConnectionStatus,
)
from .retry import RetryConfig
from .http_client import RetryableClient
from .circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)


class WooCommerceService(EcommerceService):
    """
    WooCommerce REST API integration.
    Uses consumer key/secret authentication.
    """
    
    API_VERSION = "wc/v3"
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=1.5,
            max_delay=45.0,
        )
        super().__init__(config)
    
    @property
    def platform_name(self) -> str:
        return "woocommerce"
    
    # ========== Auth ==========
    
    def generate_oauth_url(self, store_url: str, state: str, redirect_uri: str) -> str:
        base_url = self.normalize_store_url(store_url)
        return f"{base_url}/wp-admin/admin.php?page=wc-settings&tab=advanced&section=keys"
    
    async def exchange_oauth_code(self, store_url: str, code: str, redirect_uri: str) -> OAuthResult:
        return OAuthResult(success=False, error="WooCommerce uses API keys, not OAuth")
    
    async def refresh_access_token(self, store_url: str, refresh_token: str) -> OAuthResult:
        return OAuthResult(success=False, error="WooCommerce keys don't expire")
    
    async def verify_credentials(self, store_url: str, access_token: str) -> bool:
        try:
            base_url = self.normalize_store_url(store_url)
            key, secret = self._parse_credentials(access_token)
            async with RetryableClient(store_url, "woocommerce", self.retry_config, 15.0) as client:
                await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/system_status",
                    auth=(key, secret),
                )
                return True
        except Exception:
            return False
    
    # ========== Products ==========
    
    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 100
    ) -> ProductSyncResult:
        try:
            base_url = self.normalize_store_url(store_url)
            key, secret = self._parse_credentials(access_token)
            page = int(cursor) if cursor else 1
            
            async with RetryableClient(store_url, "woocommerce", self.retry_config, 30.0) as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/products",
                    auth=(key, secret),
                    params={"per_page": min(limit, 100), "page": page, "status": "publish"},
                )
                products_data = response.json()
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                has_more = page < total_pages
                
                return ProductSyncResult(
                    success=True,
                    products=[self._parse_product(p) for p in products_data],
                    has_more=has_more,
                    next_cursor=str(page + 1) if has_more else None,
                )
        except CircuitOpenError:
            return ProductSyncResult(success=False, error="Service temporarily unavailable")
        except ValueError as e:
            return ProductSyncResult(success=False, error=f"Invalid credentials: {e}")
        except httpx.HTTPStatusError as e:
            error_map = {401: "Unauthorized", 429: "Rate limited"}
            return ProductSyncResult(
                success=False,
                error=error_map.get(e.response.status_code, f"HTTP {e.response.status_code}")
            )
        except httpx.RequestError as e:
            return ProductSyncResult(success=False, error=f"Network error: {e}")
    
    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str
    ) -> Optional[ExternalProduct]:
        try:
            base_url = self.normalize_store_url(store_url)
            key, secret = self._parse_credentials(access_token)
            async with RetryableClient(store_url, "woocommerce", self.retry_config, 15.0) as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/products/{external_product_id}",
                    auth=(key, secret),
                )
                return self._parse_product(response.json())
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None
    
    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest
    ) -> PriceUpdateResponse:
        try:
            base_url = self.normalize_store_url(store_url)
            key, secret = self._parse_credentials(access_token)
            
            # Get old price
            current = await self.fetch_single_product(store_url, access_token, request.external_product_id)
            old_price = current.price if current else None
            
            # Build URL
            if request.external_variant_id:
                url = f"{base_url}/wp-json/{self.API_VERSION}/products/{request.external_product_id}/variations/{request.external_variant_id}"
            else:
                url = f"{base_url}/wp-json/{self.API_VERSION}/products/{request.external_product_id}"
            
            # Build payload
            update_data = {"regular_price": str(request.new_price)}
            if request.compare_at_price:
                update_data["sale_price"] = str(request.new_price)
                update_data["regular_price"] = str(request.compare_at_price)
            
            async with RetryableClient(store_url, "woocommerce", self.retry_config, 15.0) as client:
                await client.put(url, auth=(key, secret), json=update_data)
                return PriceUpdateResponse(
                    result=PriceUpdateResult.SUCCESS,
                    external_product_id=request.external_product_id,
                    old_price=old_price,
                    new_price=request.new_price,
                )
        except CircuitOpenError:
            return PriceUpdateResponse(
                result=PriceUpdateResult.FAILED,
                external_product_id=request.external_product_id,
                error="Service temporarily unavailable"
            )
        except httpx.HTTPStatusError as e:
            result_map = {
                401: PriceUpdateResult.UNAUTHORIZED,
                404: PriceUpdateResult.PRODUCT_NOT_FOUND,
                429: PriceUpdateResult.RATE_LIMITED,
            }
            return PriceUpdateResponse(
                result=result_map.get(e.response.status_code, PriceUpdateResult.FAILED),
                external_product_id=request.external_product_id,
                error=f"HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return PriceUpdateResponse(
                result=PriceUpdateResult.FAILED,
                external_product_id=request.external_product_id,
                error=str(e)
            )
    
    # ========== Webhooks ==========
    
    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str
    ) -> List[WebhookRegistration]:
        base_url = self.normalize_store_url(store_url)
        key, secret = self._parse_credentials(access_token)
        topics = [("product.created", "Created"), ("product.updated", "Updated"), ("product.deleted", "Deleted")]
        results = []
        
        async with RetryableClient(store_url, "woocommerce", self.retry_config, 15.0) as client:
            for topic, name in topics:
                try:
                    response = await client.post(
                        f"{base_url}/wp-json/{self.API_VERSION}/webhooks",
                        auth=(key, secret),
                        json={"name": f"SSP - {name}", "topic": topic, "delivery_url": callback_url, "status": "active"},
                    )
                    data = response.json()
                    results.append(WebhookRegistration(success=True, webhook_id=str(data.get("id")), topic=topic))
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    results.append(WebhookRegistration(success=False, topic=topic, error=str(e)))
        return results
    
    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str]
    ) -> bool:
        base_url = self.normalize_store_url(store_url)
        key, secret = self._parse_credentials(access_token)
        success = True
        
        async with RetryableClient(store_url, "woocommerce", self.retry_config, 15.0) as client:
            for wid in webhook_ids:
                try:
                    await client.delete(
                        f"{base_url}/wp-json/{self.API_VERSION}/webhooks/{wid}",
                        auth=(key, secret),
                        params={"force": "true"},
                    )
                except (httpx.HTTPStatusError, httpx.RequestError):
                    success = False
        return success
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        expected = base64.b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(signature, expected)
    
    # ========== Health ==========
    
    async def health_check(self, store_url: str, access_token: str) -> ConnectionStatus:
        try:
            base_url = self.normalize_store_url(store_url)
            key, secret = self._parse_credentials(access_token)
            async with RetryableClient(store_url, "woocommerce", RetryConfig(max_retries=1), 10.0) as client:
                await client.get(f"{base_url}/wp-json/{self.API_VERSION}/system_status", auth=(key, secret))
                return ConnectionStatus.HEALTHY
        except httpx.HTTPStatusError as e:
            status_map = {401: ConnectionStatus.UNAUTHORIZED, 429: ConnectionStatus.RATE_LIMITED}
            return status_map.get(e.response.status_code, ConnectionStatus.UNHEALTHY)
        except httpx.RequestError:
            return ConnectionStatus.UNHEALTHY
    
    # ========== Helpers ==========
    
    def _parse_credentials(self, access_token: str) -> tuple[str, str]:
        if ":" in access_token:
            parts = access_token.split(":", 1)
            return parts[0], parts[1]
        raise ValueError("Expected 'consumer_key:consumer_secret'")
    
    def _parse_product(self, data: dict) -> ExternalProduct:
        variants = [
            ExternalProductVariant(
                id=str(v.get("id")),
                title=v.get("attributes", [{}])[0].get("option", ""),
                price=float(v.get("price", 0)) if v.get("price") else None,
                sku=v.get("sku"),
                inventory_quantity=v.get("stock_quantity"),
                compare_at_price=float(v.get("regular_price", 0)) if v.get("regular_price") and v.get("sale_price") else None,
            )
            for v in data.get("variations", [])
        ]
        images = [img.get("src") for img in data.get("images", []) if img.get("src")]
        
        price, compare_at = None, None
        if data.get("sale_price"):
            price = float(data["sale_price"])
            compare_at = float(data.get("regular_price", 0)) if data.get("regular_price") else None
        elif data.get("price"):
            price = float(data["price"])
        
        return ExternalProduct(
            id=str(data.get("id")),
            title=data.get("name", ""),
            price=price,
            compare_at_price=compare_at,
            sku=data.get("sku"),
            description=data.get("description", ""),
            inventory_quantity=data.get("stock_quantity"),
            product_type=data.get("type", "simple"),
            vendor="",
            tags=[t.get("name") for t in data.get("tags", [])],
            images=images,
            variants=variants if variants else None,
            created_at=self._parse_datetime(data.get("date_created")),
            updated_at=self._parse_datetime(data.get("date_modified")),
        )
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
        
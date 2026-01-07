# backend/services/integration/shopify_service.py

"""
Shopify Integration Service.

PATCHED (2025-01-07): Added price verification after push to detect
when Shopify silently rejects or modifies price updates.
"""

import hmac
import hashlib
import base64
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from urllib.parse import urlencode

import httpx

from core.config import settings
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
from .retry import RetryConfig, execute_with_retry
from .http_client import RetryableClient
from .circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)


class ShopifyService(EcommerceService):
    """
    Shopify REST Admin API integration.
    
    Rate Limits: 40 requests per app per store (leaky bucket)
    """
    
    API_VERSION = "2024-01"
    REQUIRED_SCOPES = ["read_products", "write_products"]
    WEBHOOK_TOPICS = ["products/create", "products/update", "products/delete"]
    
    # ========== NEW: Price verification tolerance ==========
    # Allow small rounding differences (e.g., $19.999 -> $20.00)
    PRICE_VERIFICATION_TOLERANCE = Decimal("0.02")
    # ========== END NEW ==========
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
        )
        super().__init__(config)
    
    @property
    def platform_name(self) -> str:
        return "shopify"
    
    # ========== OAuth ==========
    
    def generate_oauth_url(
        self,
        store_url: str,
        state: str,
        redirect_uri: str
    ) -> str:
        shop_domain = self._get_shop_domain(store_url)
        params = {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "scope": ",".join(self.REQUIRED_SCOPES),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"
    
    async def exchange_oauth_code(
        self,
        store_url: str,
        code: str,
        redirect_uri: str
    ) -> OAuthResult:
        shop_domain = self._get_shop_domain(store_url)
        
        async def _exchange():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://{shop_domain}/admin/oauth/access_token",
                    json={
                        "client_id": settings.SHOPIFY_CLIENT_ID,
                        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                        "code": code,
                    },
                )
                response.raise_for_status()
                return response.json()
        
        try:
            data = await execute_with_retry(
                _exchange, config=self.retry_config, operation_name="shopify_oauth"
            )
            return OAuthResult(
                success=True,
                access_token=data.get("access_token"),
                scope=data.get("scope"),
            )
        except httpx.HTTPStatusError as e:
            return OAuthResult(success=False, error=f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            return OAuthResult(success=False, error=str(e))
    
    async def refresh_access_token(self, store_url: str, refresh_token: str) -> OAuthResult:
        return OAuthResult(success=False, error="Shopify tokens don't expire")
    
    async def verify_credentials(self, store_url: str, access_token: str) -> bool:
        try:
            shop_domain = self._get_shop_domain(store_url)
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as client:
                await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/shop.json",
                    headers=self._auth_headers(access_token),
                )
                return True
        except (httpx.HTTPStatusError, httpx.RequestError):
            return False
    
    # ========== Products ==========
    
    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> ProductSyncResult:
        shop_domain = self._get_shop_domain(store_url)
        params = {"limit": min(limit, 250)}
        if cursor:
            params["page_info"] = cursor
        
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 30.0) as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/products.json",
                    headers=self._auth_headers(access_token),
                    params=params,
                )
                data = response.json()
                products = [self._parse_product(p) for p in data.get("products", [])]
                next_cursor = self._extract_next_cursor(response.headers.get("Link"))
                
                return ProductSyncResult(
                    success=True,
                    products=products,
                    has_more=next_cursor is not None,
                    next_cursor=next_cursor,
                )
        except CircuitOpenError:
            return ProductSyncResult(success=False, error="Service temporarily unavailable")
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
        shop_domain = self._get_shop_domain(store_url)
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/products/{external_product_id}.json",
                    headers=self._auth_headers(access_token),
                )
                return self._parse_product(response.json().get("product", {}))
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None
    
    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest
    ) -> PriceUpdateResponse:
        shop_domain = self._get_shop_domain(store_url)
        
        try:
            # Get variant ID
            variant_id = request.external_variant_id
            if not variant_id:
                product = await self.fetch_single_product(store_url, access_token, request.external_product_id)
                if product and product.variants:
                    variant_id = product.variants[0].id
                else:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="No variant found"
                    )
            
            # Get old price
            current = await self.fetch_single_product(store_url, access_token, request.external_product_id)
            old_price = current.price if current else None
            
            # Update
            update_data = {"variant": {"id": variant_id, "price": str(request.new_price)}}
            if request.compare_at_price:
                update_data["variant"]["compare_at_price"] = str(request.compare_at_price)
            
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as client:
                await client.put(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/variants/{variant_id}.json",
                    headers=self._auth_headers(access_token),
                    json=update_data,
                )
                
                # ========== NEW: Verify price was actually set ==========
                verification_result = await self._verify_price_update(
                    store_url=store_url,
                    access_token=access_token,
                    external_product_id=request.external_product_id,
                    variant_id=variant_id,
                    expected_price=request.new_price
                )
                
                if not verification_result["success"]:
                    logger.error(
                        f"Price verification failed for product {request.external_product_id}: "
                        f"expected ${request.new_price}, got ${verification_result.get('actual_price')}. "
                        f"Reason: {verification_result.get('error')}"
                    )
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.FAILED,
                        external_product_id=request.external_product_id,
                        old_price=old_price,
                        new_price=request.new_price,
                        error=f"Price verification failed: {verification_result.get('error')}"
                    )
                
                logger.info(
                    f"Price update verified for product {request.external_product_id}: "
                    f"${old_price} -> ${request.new_price}"
                )
                # ========== END NEW ==========
                
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
    
    # ========== NEW: Price verification method ==========
    async def _verify_price_update(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str,
        variant_id: str,
        expected_price: Decimal
    ) -> dict:
        """
        Verify that a price update was actually applied in Shopify.
        
        This catches cases where:
        - Shopify silently rejects the update
        - A Shopify app modifies the price after our update
        - The price is changed by another process
        
        Args:
            store_url: Shopify store URL
            access_token: API credentials
            external_product_id: Product ID in Shopify
            variant_id: Variant ID that was updated
            expected_price: The price we tried to set
            
        Returns:
            dict with 'success' (bool), 'actual_price' (Decimal), 'error' (str if failed)
        """
        try:
            # Fetch the product to get current price
            updated_product = await self.fetch_single_product(
                store_url, access_token, external_product_id
            )
            
            if not updated_product:
                return {
                    "success": False,
                    "actual_price": None,
                    "error": "Could not fetch product after update"
                }
            
            # Find the variant we updated
            actual_price = None
            if updated_product.variants:
                for variant in updated_product.variants:
                    if str(variant.id) == str(variant_id):
                        actual_price = variant.price
                        break
            
            # Fallback to product price if no variant match
            if actual_price is None:
                actual_price = updated_product.price
            
            if actual_price is None:
                return {
                    "success": False,
                    "actual_price": None,
                    "error": "Product has no price after update"
                }
            
            # Convert to Decimal for comparison
            actual_price = Decimal(str(actual_price))
            expected_price = Decimal(str(expected_price))
            
            # Check if prices match (within tolerance for rounding)
            price_diff = abs(actual_price - expected_price)
            
            if price_diff <= self.PRICE_VERIFICATION_TOLERANCE:
                return {
                    "success": True,
                    "actual_price": actual_price,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "actual_price": actual_price,
                    "error": f"Expected ${expected_price}, but Shopify shows ${actual_price}"
                }
                
        except Exception as e:
            logger.exception(f"Error verifying price update for product {external_product_id}")
            return {
                "success": False,
                "actual_price": None,
                "error": f"Verification error: {str(e)}"
            }
    # ========== END NEW ==========
    
    # ========== Webhooks ==========
    
    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str
    ) -> List[WebhookRegistration]:
        shop_domain = self._get_shop_domain(store_url)
        results = []
        
        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as client:
            for topic in self.WEBHOOK_TOPICS:
                try:
                    response = await client.post(
                        f"https://{shop_domain}/admin/api/{self.API_VERSION}/webhooks.json",
                        headers=self._auth_headers(access_token),
                        json={"webhook": {"topic": topic, "address": callback_url, "format": "json"}},
                    )
                    data = response.json()
                    results.append(WebhookRegistration(
                        success=True,
                        webhook_id=str(data["webhook"]["id"]),
                        topic=topic,
                    ))
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    results.append(WebhookRegistration(success=False, topic=topic, error=str(e)))
        return results
    
    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str]
    ) -> bool:
        shop_domain = self._get_shop_domain(store_url)
        success = True
        
        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as client:
            for wid in webhook_ids:
                try:
                    await client.delete(
                        f"https://{shop_domain}/admin/api/{self.API_VERSION}/webhooks/{wid}.json",
                        headers=self._auth_headers(access_token),
                    )
                except (httpx.HTTPStatusError, httpx.RequestError):
                    success = False
        return success
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        computed = base64.b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(computed, signature)
    
    # ========== Health ==========
    
    async def health_check(self, store_url: str, access_token: str) -> ConnectionStatus:
        shop_domain = self._get_shop_domain(store_url)
        try:
            async with RetryableClient(store_url, "shopify", RetryConfig(max_retries=1), 10.0) as client:
                await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/shop.json",
                    headers=self._auth_headers(access_token),
                )
                return ConnectionStatus.HEALTHY
        except httpx.HTTPStatusError as e:
            status_map = {401: ConnectionStatus.UNAUTHORIZED, 429: ConnectionStatus.RATE_LIMITED}
            return status_map.get(e.response.status_code, ConnectionStatus.UNHEALTHY)
        except httpx.RequestError:
            return ConnectionStatus.UNHEALTHY
    
    # ========== Helpers ==========
    
    def _get_shop_domain(self, store_url: str) -> str:
        url = store_url.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
        if not url.endswith(".myshopify.com") and "." not in url:
            url = f"{url}.myshopify.com"
        return url
    
    def _auth_headers(self, access_token: str) -> dict:
        return {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}
    
    def _parse_product(self, data: dict) -> ExternalProduct:
        variants = [
            ExternalProductVariant(
                id=str(v.get("id")),
                title=v.get("title", ""),
                price=float(v.get("price", 0)),
                sku=v.get("sku"),
                inventory_quantity=v.get("inventory_quantity"),
                compare_at_price=float(v["compare_at_price"]) if v.get("compare_at_price") else None,
            )
            for v in data.get("variants", [])
        ]
        images = [img.get("src") for img in data.get("images", []) if img.get("src")]
        
        return ExternalProduct(
            id=str(data.get("id")),
            title=data.get("title", ""),
            price=variants[0].price if variants else None,
            compare_at_price=variants[0].compare_at_price if variants else None,
            sku=variants[0].sku if variants else None,
            description=data.get("body_html", ""),
            inventory_quantity=variants[0].inventory_quantity if variants else None,
            product_type=data.get("product_type", ""),
            vendor=data.get("vendor", ""),
            tags=data.get("tags", "").split(", ") if data.get("tags") else [],
            images=images,
            variants=variants,
            created_at=self._parse_datetime(data.get("created_at")),
            updated_at=self._parse_datetime(data.get("updated_at")),
        )
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    def _extract_next_cursor(self, link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        match = re.search(r'<[^>]*page_info=([^>&]+)[^>]*>;\s*rel="next"', link_header)
        return match.group(1) if match else None


        
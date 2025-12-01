# backend/services/integration/shopify_service.py

"""
Shopify Integration Service

Implements the EcommerceService interface for Shopify stores.
Handles OAuth, product sync, price updates, and webhooks.
"""

import hmac
import hashlib
import base64
import re
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlencode

import httpx

from backend.core.config import settings
from backend.services.integration.base import (
    EcommerceService,
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


class ShopifyService(EcommerceService):
    """
    Shopify REST Admin API integration.
    
    Docs: https://shopify.dev/docs/api/admin-rest
    """
    
    API_VERSION = "2024-01"
    REQUIRED_SCOPES = ["read_products", "write_products"]
    WEBHOOK_TOPICS = ["products/create", "products/update", "products/delete"]
    
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
        """Generate Shopify OAuth authorization URL."""
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
        """Exchange authorization code for access token."""
        shop_domain = self._get_shop_domain(store_url)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{shop_domain}/admin/oauth/access_token",
                    json={
                        "client_id": settings.SHOPIFY_CLIENT_ID,
                        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                        "code": code,
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return OAuthResult(
                        success=False,
                        error=f"Token exchange failed: {response.text}"
                    )
                
                data = response.json()
                
                return OAuthResult(
                    success=True,
                    access_token=data.get("access_token"),
                    scope=data.get("scope"),
                )
                
        except httpx.RequestError as e:
            return OAuthResult(success=False, error=str(e))
    
    async def refresh_access_token(
        self,
        store_url: str,
        refresh_token: str
    ) -> OAuthResult:
        """Shopify access tokens don't expire, so refresh is not needed."""
        return OAuthResult(
            success=False,
            error="Shopify access tokens don't expire"
        )
    
    async def verify_credentials(
        self,
        store_url: str,
        access_token: str
    ) -> bool:
        """Verify credentials by making a test API call."""
        try:
            shop_domain = self._get_shop_domain(store_url)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/shop.json",
                    headers=self._auth_headers(access_token),
                    timeout=10.0
                )
                return response.status_code == 200
                
        except httpx.RequestError:
            return False
    
    # ========== Product Operations ==========
    
    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> ProductSyncResult:
        """Fetch products from Shopify with pagination."""
        try:
            shop_domain = self._get_shop_domain(store_url)
            
            params = {"limit": min(limit, 250)}
            if cursor:
                params["page_info"] = cursor
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/products.json",
                    headers=self._auth_headers(access_token),
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code == 401:
                    return ProductSyncResult(success=False, error="Unauthorized")
                
                response.raise_for_status()
                data = response.json()
                
                products = [
                    self._parse_product(p) for p in data.get("products", [])
                ]
                
                # Check for next page via Link header
                next_cursor = self._extract_next_cursor(response.headers.get("Link"))
                
                return ProductSyncResult(
                    success=True,
                    products=products,
                    has_more=next_cursor is not None,
                    next_cursor=next_cursor,
                )
                
        except httpx.RequestError as e:
            return ProductSyncResult(success=False, error=str(e))
    
    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str
    ) -> Optional[ExternalProduct]:
        """Fetch a single product by ID."""
        try:
            shop_domain = self._get_shop_domain(store_url)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/products/{external_product_id}.json",
                    headers=self._auth_headers(access_token),
                    timeout=10.0
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                return self._parse_product(data.get("product", {}))
                
        except httpx.RequestError:
            return None
    
    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest
    ) -> PriceUpdateResponse:
        """Update a product variant's price in Shopify."""
        try:
            shop_domain = self._get_shop_domain(store_url)
            
            # Get variant ID - if not provided, get the first variant
            variant_id = request.external_variant_id
            if not variant_id:
                product = await self.fetch_single_product(
                    store_url, access_token, request.external_product_id
                )
                if product and product.variants:
                    variant_id = product.variants[0].id
                else:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="No variant found"
                    )
            
            # Get current price
            current_product = await self.fetch_single_product(
                store_url, access_token, request.external_product_id
            )
            old_price = current_product.price if current_product else None
            
            # Update the variant
            update_data = {
                "variant": {
                    "id": variant_id,
                    "price": str(request.new_price),
                }
            }
            
            if request.compare_at_price:
                update_data["variant"]["compare_at_price"] = str(request.compare_at_price)
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/variants/{variant_id}.json",
                    headers=self._auth_headers(access_token),
                    json=update_data,
                    timeout=10.0
                )
                
                if response.status_code == 401:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.UNAUTHORIZED,
                        external_product_id=request.external_product_id,
                        error="Invalid access token"
                    )
                
                if response.status_code == 404:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="Variant not found"
                    )
                
                if response.status_code == 429:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.RATE_LIMITED,
                        external_product_id=request.external_product_id,
                        error="Rate limited"
                    )
                
                response.raise_for_status()
                
                return PriceUpdateResponse(
                    result=PriceUpdateResult.SUCCESS,
                    external_product_id=request.external_product_id,
                    old_price=old_price,
                    new_price=request.new_price,
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
        """Register webhooks for product events."""
        shop_domain = self._get_shop_domain(store_url)
        results = []
        
        async with httpx.AsyncClient() as client:
            for topic in self.WEBHOOK_TOPICS:
                try:
                    response = await client.post(
                        f"https://{shop_domain}/admin/api/{self.API_VERSION}/webhooks.json",
                        headers=self._auth_headers(access_token),
                        json={
                            "webhook": {
                                "topic": topic,
                                "address": callback_url,
                                "format": "json",
                            }
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code in (200, 201):
                        data = response.json()
                        results.append(WebhookRegistration(
                            success=True,
                            webhook_id=str(data["webhook"]["id"]),
                            topic=topic,
                        ))
                    else:
                        results.append(WebhookRegistration(
                            success=False,
                            topic=topic,
                            error=f"HTTP {response.status_code}",
                        ))
                        
                except httpx.RequestError as e:
                    results.append(WebhookRegistration(
                        success=False,
                        topic=topic,
                        error=str(e),
                    ))
        
        return results
    
    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str]
    ) -> bool:
        """Unregister webhooks by ID."""
        shop_domain = self._get_shop_domain(store_url)
        all_success = True
        
        async with httpx.AsyncClient() as client:
            for webhook_id in webhook_ids:
                try:
                    response = await client.delete(
                        f"https://{shop_domain}/admin/api/{self.API_VERSION}/webhooks/{webhook_id}.json",
                        headers=self._auth_headers(access_token),
                        timeout=10.0
                    )
                    
                    if response.status_code not in (200, 204):
                        all_success = False
                        
                except httpx.RequestError:
                    all_success = False
        
        return all_success
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """Verify Shopify webhook HMAC signature."""
        computed = base64.b64encode(
            hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).digest()
        ).decode()
        
        return hmac.compare_digest(computed, signature)
    
    # ========== Health Check ==========
    
    async def health_check(
        self,
        store_url: str,
        access_token: str
    ) -> ConnectionStatus:
        """Check the health of the Shopify connection."""
        try:
            shop_domain = self._get_shop_domain(store_url)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{shop_domain}/admin/api/{self.API_VERSION}/shop.json",
                    headers=self._auth_headers(access_token),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return ConnectionStatus.HEALTHY
                elif response.status_code == 401:
                    return ConnectionStatus.UNAUTHORIZED
                elif response.status_code == 429:
                    return ConnectionStatus.RATE_LIMITED
                else:
                    return ConnectionStatus.UNHEALTHY
                    
        except httpx.RequestError:
            return ConnectionStatus.UNHEALTHY
    
    # ========== Helper Methods ==========
    
    def _get_shop_domain(self, store_url: str) -> str:
        """Extract or normalize shop domain."""
        url = store_url.strip().lower()
        
        # Remove protocol
        url = url.replace("https://", "").replace("http://", "")
        
        # Remove trailing slash
        url = url.rstrip("/")
        
        # Add .myshopify.com if not present
        if not url.endswith(".myshopify.com"):
            if "." not in url:
                url = f"{url}.myshopify.com"
        
        return url
    
    def _auth_headers(self, access_token: str) -> dict:
        """Get authorization headers for API requests."""
        return {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
    
    def _parse_product(self, data: dict) -> ExternalProduct:
        """Parse Shopify product JSON into ExternalProduct."""
        variants = []
        for v in data.get("variants", []):
            variants.append(ExternalProductVariant(
                id=str(v.get("id")),
                title=v.get("title", ""),
                price=float(v.get("price", 0)),
                sku=v.get("sku"),
                inventory_quantity=v.get("inventory_quantity"),
                compare_at_price=float(v["compare_at_price"]) if v.get("compare_at_price") else None,
            ))
        
        # Get first variant price as product price
        price = None
        compare_at_price = None
        if variants:
            price = variants[0].price
            compare_at_price = variants[0].compare_at_price
        
        images = [img.get("src") for img in data.get("images", []) if img.get("src")]
        
        return ExternalProduct(
            id=str(data.get("id")),
            title=data.get("title", ""),
            price=price,
            compare_at_price=compare_at_price,
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
        """Parse Shopify datetime string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    def _extract_next_cursor(self, link_header: Optional[str]) -> Optional[str]:
        """Extract next page cursor from Link header."""
        if not link_header:
            return None
        
        # Parse Link header for rel="next"
        match = re.search(r'<[^>]*page_info=([^>&]+)[^>]*>;\s*rel="next"', link_header)
        if match:
            return match.group(1)
        
        return None


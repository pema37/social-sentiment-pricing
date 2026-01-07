# backend/services/integration/product_sync_service.py
"""
Product Sync Service - Bi-directional product synchronization.

Handles:
1. Creating SSP products in WooCommerce (push)
2. Creating WooCommerce products in SSP (pull) - existing
3. Auto-creating ProductIntegrationLink after sync

This ensures every product has a proper link for price updates.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product
from models.integration import (
    Integration,
    ProductIntegrationLink,
    IntegrationStatus,
    EcommercePlatform,
)
from core.encryption import decrypt_token

logger = logging.getLogger(__name__)


class ProductSyncService:
    """
    Bi-directional product synchronization service.
    
    When a product is created in SSP:
    1. Check if user has active WooCommerce/Shopify integration
    2. Push product to the e-commerce platform
    3. Get back the external product ID
    4. Create ProductIntegrationLink to enable price sync
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_active_integration(
        self, 
        user_id: UUID,
        platform: Optional[EcommercePlatform] = None
    ) -> Optional[Integration]:
        """Get user's active integration, optionally filtered by platform."""
        stmt = select(Integration).where(
            Integration.user_id == user_id,
            Integration.status == IntegrationStatus.ACTIVE
        )
        if platform:
            stmt = stmt.where(Integration.platform == platform)
        
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_all_user_integrations(self, user_id: UUID) -> List[Integration]:
        """Get all active integrations for a user."""
        stmt = select(Integration).where(
            Integration.user_id == user_id,
            Integration.status == IntegrationStatus.ACTIVE
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def push_product_to_store(
        self,
        product: Product,
        integration: Integration,
    ) -> Dict[str, Any]:
        """
        Push a product from SSP to the e-commerce platform.
        
        Returns:
            dict with:
            - success: bool
            - external_product_id: str (if successful)
            - error: str (if failed)
            - link_id: UUID (ProductIntegrationLink ID if created)
        """
        try:
            # Check if link already exists
            existing_link = await self._get_existing_link(product.id, integration.id)
            if existing_link:
                logger.info(f"Product {product.id} already linked to integration {integration.id}")
                return {
                    "success": True,
                    "external_product_id": existing_link.external_product_id,
                    "link_id": str(existing_link.id),
                    "message": "Product already linked"
                }
            
            # Get the appropriate service
            if integration.platform == EcommercePlatform.WOOCOMMERCE:
                result = await self._push_to_woocommerce(product, integration)
            elif integration.platform == EcommercePlatform.SHOPIFY:
                result = await self._push_to_shopify(product, integration)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {integration.platform.value}"
                }
            
            if not result["success"]:
                return result
            
            # Create the ProductIntegrationLink
            link = await self._create_integration_link(
                product_id=product.id,
                integration_id=integration.id,
                external_product_id=result["external_product_id"],
                external_variant_id=result.get("external_variant_id"),
                external_price=float(product.current_price) if product.current_price else None,
            )
            
            result["link_id"] = str(link.id)
            logger.info(
                f"Successfully pushed product {product.id} to {integration.platform.value}, "
                f"external_id={result['external_product_id']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to push product {product.id} to store: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "PUSH_FAILED"
            }
    
    async def _push_to_woocommerce(
        self,
        product: Product,
        integration: Integration
    ) -> Dict[str, Any]:
        """Push product to WooCommerce via REST API."""
        import httpx
        
        try:
            # Decrypt credentials
            credentials = decrypt_token(integration.access_token_encrypted)
            
            # WooCommerce uses consumer_key:consumer_secret for Basic Auth
            # The credentials are stored as "consumer_key|consumer_secret"
            if "|" in credentials:
                consumer_key, consumer_secret = credentials.split("|", 1)
            else:
                # Fallback: might be stored differently
                consumer_key = credentials
                consumer_secret = integration.refresh_token_encrypted or ""
                if consumer_secret:
                    consumer_secret = decrypt_token(consumer_secret)
            
            # Build the WooCommerce API URL
            store_url = integration.store_url.rstrip("/")
            api_url = f"{store_url}/wp-json/wc/v3/products"
            
            # Prepare product data for WooCommerce
            wc_product = {
                "name": product.name,
                "type": "simple",
                "regular_price": str(product.current_price) if product.current_price else "0",
                "description": product.description or "",
                "short_description": product.description[:200] if product.description else "",
                "sku": product.sku or "",
                "manage_stock": False,
                "status": "publish" if product.is_active else "draft",
            }
            
            # Add categories if available
            if product.category:
                wc_product["categories"] = [{"name": product.category}]
            
            # Make the API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    json=wc_product,
                    auth=(consumer_key, consumer_secret),
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "external_product_id": str(data["id"]),
                        "external_url": data.get("permalink"),
                        "platform": "woocommerce"
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid WooCommerce credentials",
                        "error_code": "INVALID_CREDENTIALS"
                    }
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Bad request")
                    # Check for duplicate SKU error
                    if "sku" in error_msg.lower() and "duplicate" in error_msg.lower():
                        return {
                            "success": False,
                            "error": f"A product with SKU '{product.sku}' already exists in WooCommerce",
                            "error_code": "DUPLICATE_SKU"
                        }
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_code": "BAD_REQUEST"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"WooCommerce API error: {response.status_code}",
                        "error_code": "API_ERROR"
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "WooCommerce store not responding (timeout)",
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            logger.error(f"WooCommerce push error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "UNKNOWN_ERROR"
            }
    
    async def _push_to_shopify(
        self,
        product: Product,
        integration: Integration
    ) -> Dict[str, Any]:
        """Push product to Shopify via Admin API."""
        import httpx
        
        try:
            access_token = decrypt_token(integration.access_token_encrypted)
            store_url = integration.store_url.rstrip("/")
            
            # Shopify Admin API URL
            # Store URL format: mystore.myshopify.com
            api_url = f"https://{store_url}/admin/api/2024-01/products.json"
            
            # Prepare product data for Shopify
            shopify_product = {
                "product": {
                    "title": product.name,
                    "body_html": product.description or "",
                    "vendor": "",
                    "product_type": product.category or "",
                    "status": "active" if product.is_active else "draft",
                    "variants": [
                        {
                            "price": str(product.current_price) if product.current_price else "0",
                            "sku": product.sku or "",
                            "inventory_management": None,
                        }
                    ]
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    json=shopify_product,
                    headers={
                        "Content-Type": "application/json",
                        "X-Shopify-Access-Token": access_token
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    product_data = data["product"]
                    variant_id = product_data["variants"][0]["id"] if product_data.get("variants") else None
                    
                    return {
                        "success": True,
                        "external_product_id": str(product_data["id"]),
                        "external_variant_id": str(variant_id) if variant_id else None,
                        "platform": "shopify"
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid Shopify credentials",
                        "error_code": "INVALID_CREDENTIALS"
                    }
                else:
                    error_data = response.json() if response.content else {}
                    return {
                        "success": False,
                        "error": error_data.get("errors", f"Shopify API error: {response.status_code}"),
                        "error_code": "API_ERROR"
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Shopify store not responding (timeout)",
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            logger.error(f"Shopify push error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "UNKNOWN_ERROR"
            }
    
    async def _get_existing_link(
        self,
        product_id: UUID,
        integration_id: UUID
    ) -> Optional[ProductIntegrationLink]:
        """Check if a link already exists."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.product_id == product_id,
            ProductIntegrationLink.integration_id == integration_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def _create_integration_link(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: Optional[str] = None,
        external_price: Optional[float] = None,
    ) -> ProductIntegrationLink:
        """Create a new ProductIntegrationLink."""
        link = ProductIntegrationLink(
            product_id=product_id,
            integration_id=integration_id,
            external_product_id=external_product_id,
            external_variant_id=external_variant_id,
            external_price=Decimal(str(external_price)) if external_price else None,
            sync_enabled=True,
            last_synced_at=datetime.utcnow(),
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link
    
    async def sync_product_on_create(
        self,
        product: Product,
        user_id: UUID,
        auto_push: bool = True
    ) -> Dict[str, Any]:
        """
        Called when a new product is created in SSP.
        
        If auto_push is True and user has an active integration,
        automatically push the product to the e-commerce store.
        
        Returns:
            dict with sync results for each integration
        """
        if not auto_push:
            return {"synced": False, "reason": "auto_push disabled"}
        
        integrations = await self.get_all_user_integrations(user_id)
        
        if not integrations:
            return {"synced": False, "reason": "no_active_integrations"}
        
        results = []
        for integration in integrations:
            result = await self.push_product_to_store(product, integration)
            results.append({
                "integration_id": str(integration.id),
                "platform": integration.platform.value,
                "store_url": integration.store_url,
                **result
            })
        
        return {
            "synced": True,
            "integrations_count": len(integrations),
            "results": results
        }
    
    async def link_existing_product(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Manually link an existing SSP product to an existing e-commerce product.
        
        Used when:
        - Product already exists in both systems
        - User wants to manually specify the mapping
        """
        # Verify product exists
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalars().first()
        
        if not product:
            return {"success": False, "error": "Product not found"}
        
        # Verify integration exists
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration:
            return {"success": False, "error": "Integration not found"}
        
        # Check for existing link
        existing = await self._get_existing_link(product_id, integration_id)
        if existing:
            # Update existing link
            existing.external_product_id = external_product_id
            existing.external_variant_id = external_variant_id
            existing.sync_enabled = True
            existing.last_synced_at = datetime.utcnow()
            self.db.add(existing)
            await self.db.commit()
            return {
                "success": True,
                "link_id": str(existing.id),
                "message": "Updated existing link"
            }
        
        # Create new link
        link = await self._create_integration_link(
            product_id=product_id,
            integration_id=integration_id,
            external_product_id=external_product_id,
            external_variant_id=external_variant_id,
            external_price=float(product.current_price) if product.current_price else None,
        )
        
        return {
            "success": True,
            "link_id": str(link.id),
            "message": "Created new link"
        }
    
    async def bulk_push_products(
        self,
        user_id: UUID,
        product_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Push multiple products to all active integrations.
        
        If product_ids is None, push all products without links.
        """
        integrations = await self.get_all_user_integrations(user_id)
        
        if not integrations:
            return {"success": False, "error": "No active integrations"}
        
        # Get products to push
        if product_ids:
            stmt = select(Product).where(
                Product.id.in_(product_ids),
                Product.user_id == user_id
            )
        else:
            # Get products without any links
            subquery = select(ProductIntegrationLink.product_id).distinct()
            stmt = select(Product).where(
                Product.user_id == user_id,
                Product.id.notin_(subquery)
            )
        
        result = await self.db.execute(stmt)
        products = list(result.scalars().all())
        
        if not products:
            return {"success": True, "message": "No products to push", "pushed": 0}
        
        results = {
            "total_products": len(products),
            "total_integrations": len(integrations),
            "pushed": 0,
            "failed": 0,
            "details": []
        }
        
        for product in products:
            for integration in integrations:
                push_result = await self.push_product_to_store(product, integration)
                
                if push_result["success"]:
                    results["pushed"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append({
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "integration_id": str(integration.id),
                    "platform": integration.platform.value,
                    **push_result
                })
        
        return results
    

    
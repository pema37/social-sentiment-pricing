# backend/services/integration/product_sync_service.py
"""
Product Sync Service - Bi-directional product synchronization.

MIGRATED (2026-02-15): _push_to_shopify REST → GraphQL Admin API

Handles:
1. Creating SSP products in WooCommerce (push)
2. Creating WooCommerce products in SSP (pull) - existing
3. Auto-creating ProductIntegrationLink after sync

This ensures every product has a proper link for price updates.

PATCHED (2026-02-21):
- _get_existing_link: Added external_variant_id param for variant-level lookups
- _create_integration_link: Fixed Decimal→float type mismatch, removed nonexistent field
- link_existing_product: Variant-aware — won't overwrite wrong variant's link
"""

import logging
from datetime import datetime, UTC
from typing import Optional, Dict, Any
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

    # Shopify GraphQL API version (must match shopify_service.py)
    SHOPIFY_API_VERSION = "2024-01"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_active_integration(
        self,
        user_id: UUID,
        platform: Optional[EcommercePlatform] = None,
    ) -> Optional[Integration]:
        """Get user's active integration, optionally filtered by platform."""
        stmt = select(Integration).where(
            Integration.user_id == user_id,
            Integration.status.in_([IntegrationStatus.ACTIVE, IntegrationStatus.ERROR]),
        )
        if platform:
            stmt = stmt.where(Integration.platform == platform)

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_all_user_integrations(self, user_id: UUID) -> list[Integration]:
        """Get all active integrations for a user."""
        stmt = select(Integration).where(
            Integration.user_id == user_id,
            Integration.status.in_([IntegrationStatus.ACTIVE, IntegrationStatus.ERROR]),
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
            dict with success, external_product_id, error, link_id
        """
        try:
            existing_link = await self._get_existing_link(product.id, integration.id)
            if existing_link:
                logger.info(f"Product {product.id} already linked to integration {integration.id}")
                return {
                    "success": True,
                    "external_product_id": existing_link.external_product_id,
                    "external_variant_id": existing_link.external_variant_id,
                    "link_id": str(existing_link.id),
                    "message": "Product already linked",
                }

            if integration.platform == EcommercePlatform.WOOCOMMERCE:
                result = await self._push_to_woocommerce(product, integration)
            elif integration.platform == EcommercePlatform.SHOPIFY:
                result = await self._push_to_shopify(product, integration)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {integration.platform.value}",
                }

            if not result["success"]:
                return result

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
            return {"success": False, "error": str(e), "error_code": "PUSH_FAILED"}

    async def _push_to_woocommerce(
        self,
        product: Product,
        integration: Integration,
    ) -> Dict[str, Any]:
        """Push product to WooCommerce via REST API (WooCommerce still uses REST)."""
        import httpx

        try:
            credentials = decrypt_token(integration.access_token_encrypted)

            if "|" in credentials:
                consumer_key, consumer_secret = credentials.split("|", 1)
            else:
                consumer_key = credentials
                consumer_secret = integration.refresh_token_encrypted or ""
                if consumer_secret:
                    consumer_secret = decrypt_token(consumer_secret)

            store_url = integration.store_url.rstrip("/")
            api_url = f"{store_url}/wp-json/wc/v3/products"

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

            if product.category:
                wc_product["categories"] = [{"name": product.category}]

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    api_url,
                    json=wc_product,
                    auth=(consumer_key, consumer_secret),
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "external_product_id": str(data["id"]),
                        "external_url": data.get("permalink"),
                        "platform": "woocommerce",
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid WooCommerce credentials",
                        "error_code": "INVALID_CREDENTIALS",
                    }
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Bad request")
                    if "sku" in error_msg.lower() and "duplicate" in error_msg.lower():
                        return {
                            "success": False,
                            "error": f"A product with SKU '{product.sku}' already exists in WooCommerce",
                            "error_code": "DUPLICATE_SKU",
                        }
                    return {"success": False, "error": error_msg, "error_code": "BAD_REQUEST"}
                else:
                    return {
                        "success": False,
                        "error": f"WooCommerce API error: {response.status_code}",
                        "error_code": "API_ERROR",
                    }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "WooCommerce store not responding (timeout)",
                "error_code": "TIMEOUT",
            }
        except Exception as e:
            logger.error(f"WooCommerce push error: {e}")
            return {"success": False, "error": str(e), "error_code": "UNKNOWN_ERROR"}

    async def _push_to_shopify(
        self,
        product: Product,
        integration: Integration,
    ) -> Dict[str, Any]:
        """
        Push product to Shopify via GraphQL Admin API.

        MIGRATED from: POST /admin/api/2024-01/products.json
        MIGRATED to:   POST /admin/api/2024-01/graphql.json (productCreate mutation)
        """
        import httpx

        try:
            access_token = decrypt_token(integration.access_token_encrypted)
            store_url = integration.store_url.rstrip("/")

            # Normalize domain
            shop_domain = (
                store_url.lower()
                .replace("https://", "")
                .replace("http://", "")
                .rstrip("/")
            )
            if not shop_domain.endswith(".myshopify.com") and "." not in shop_domain:
                shop_domain = f"{shop_domain}.myshopify.com"

            graphql_url = f"https://{shop_domain}/admin/api/{self.SHOPIFY_API_VERSION}/graphql.json"

            mutation = """
                mutation ProductCreate($input: ProductInput!) {
                    productCreate(input: $input) {
                        product {
                            id
                            variants(first: 1) {
                                edges {
                                    node { id }
                                }
                            }
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
            """

            product_input: Dict[str, Any] = {
                "title": product.name,
                "bodyHtml": product.description or "",
                "vendor": "",
                "productType": product.category or "",
                "status": "ACTIVE" if product.is_active else "DRAFT",
                "variants": [
                    {
                        "price": str(product.current_price) if product.current_price else "0",
                        "sku": product.sku or "",
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    graphql_url,
                    json={"query": mutation, "variables": {"input": product_input}},
                    headers={
                        "Content-Type": "application/json",
                        "X-Shopify-Access-Token": access_token,
                    },
                )

                if response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid Shopify credentials",
                        "error_code": "INVALID_CREDENTIALS",
                    }

                response.raise_for_status()
                body = response.json()

                # Top-level GraphQL errors
                if body.get("errors"):
                    msgs = "; ".join(e.get("message", "") for e in body["errors"])
                    return {
                        "success": False,
                        "error": f"Shopify GraphQL error: {msgs}",
                        "error_code": "API_ERROR",
                    }

                data = body.get("data", {}).get("productCreate", {})

                # Mutation-level userErrors
                user_errors = data.get("userErrors", [])
                if user_errors:
                    msgs = "; ".join(e.get("message", "") for e in user_errors)
                    return {"success": False, "error": msgs, "error_code": "API_ERROR"}

                product_data = data.get("product")
                if not product_data:
                    return {
                        "success": False,
                        "error": "Shopify returned no product data",
                        "error_code": "API_ERROR",
                    }

                # Extract numeric IDs from GIDs (gid://shopify/Product/123 → 123)
                product_numeric_id = product_data["id"].rsplit("/", 1)[-1]

                variant_id = None
                variant_edges = product_data.get("variants", {}).get("edges", [])
                if variant_edges:
                    variant_id = variant_edges[0]["node"]["id"].rsplit("/", 1)[-1]

                return {
                    "success": True,
                    "external_product_id": product_numeric_id,
                    "external_variant_id": variant_id,
                    "platform": "shopify",
                }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Shopify store not responding (timeout)",
                "error_code": "TIMEOUT",
            }
        except Exception as e:
            logger.error(f"Shopify push error: {e}")
            return {"success": False, "error": str(e), "error_code": "UNKNOWN_ERROR"}

    # ─── Internal helpers ────────────────────────────────────────

    async def _get_existing_link(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_variant_id: Optional[str] = None,
    ) -> Optional[ProductIntegrationLink]:
        """Find existing link, optionally for a specific variant.
        
        FIX: Added external_variant_id param. Without it, for a product with
        3 variant links, this returns an arbitrary one — which could cause
        link_existing_product to overwrite the wrong variant's link.
        """
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.product_id == product_id,
            ProductIntegrationLink.integration_id == integration_id,
        )
        if external_variant_id is not None:
            stmt = stmt.where(
                ProductIntegrationLink.external_variant_id == external_variant_id
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
        """Create a new integration link.
        
        FIX: external_price uses float (matching model field), not Decimal.
        FIX: Removed last_synced_at — field doesn't exist on model.
              Model has last_price_pull_at instead.
        """
        link = ProductIntegrationLink(
            product_id=product_id,
            integration_id=integration_id,
            external_product_id=external_product_id,
            external_variant_id=external_variant_id,
            # FIX: Model field is Optional[float], not Decimal
            external_price=external_price,
            sync_enabled=True,
            # FIX: Was last_synced_at which doesn't exist on model.
            # Correct field is last_price_pull_at.
            last_price_pull_at=datetime.now(UTC),
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def sync_product_on_create(
        self, product: Product, user_id: UUID, auto_push: bool = True
    ) -> Dict[str, Any]:
        """Auto-push product to all active integrations on creation."""
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
                **result,
            })

        return {
            "synced": True,
            "integrations_count": len(integrations),
            "results": results,
        }

    async def link_existing_product(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually link an SSP product to an external product/variant.
        
        FIX: Passes external_variant_id to _get_existing_link so it won't
        accidentally overwrite a different variant's link.
        """
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        product = result.scalars().first()
        if not product:
            return {"success": False, "error": "Product not found"}

        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        if not integration:
            return {"success": False, "error": "Integration not found"}

        # FIX: Pass variant_id to avoid overwriting a different variant's link
        existing = await self._get_existing_link(
            product_id, integration_id, external_variant_id=external_variant_id
        )
        if existing:
            existing.external_product_id = external_product_id
            existing.external_variant_id = external_variant_id
            existing.sync_enabled = True
            existing.last_price_pull_at = datetime.now(UTC)
            existing.updated_at = datetime.now(UTC)
            self.db.add(existing)
            await self.db.commit()
            return {
                "success": True,
                "link_id": str(existing.id),
                "message": "Updated existing link",
            }

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
            "message": "Created new link",
        }

    async def bulk_push_products(
        self, user_id: UUID, product_ids: Optional[list[UUID]] = None
    ) -> Dict[str, Any]:
        """Push multiple products to all active integrations."""
        integrations = await self.get_all_user_integrations(user_id)
        if not integrations:
            return {"success": False, "error": "No active integrations"}

        if product_ids:
            stmt = select(Product).where(
                Product.id.in_(product_ids),
                Product.user_id == user_id,
            )
        else:
            subquery = select(ProductIntegrationLink.product_id).distinct()
            stmt = select(Product).where(
                Product.user_id == user_id,
                Product.id.notin_(subquery),
            )

        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if not products:
            return {"success": True, "message": "No products to push", "pushed": 0}

        results: Dict[str, Any] = {
            "total_products": len(products),
            "total_integrations": len(integrations),
            "pushed": 0,
            "failed": 0,
            "details": [],
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
                    **push_result,
                })

        return results



        
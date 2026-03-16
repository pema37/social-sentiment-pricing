# backend/api/v1/routes/diagnostic.py
"""
Diagnostic Endpoint - For debugging multi-platform integration issues.

Endpoints:
  - GET /api/v1/diagnostic/integration-health
  - GET /api/v1/diagnostic/product/{product_id}/push-status
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from core.deps import get_current_user
from core.encryption import decrypt_token
from models.user import User
from models.product import Product
from models.integration import Integration, ProductIntegrationLink, IntegrationStatus
from services.integration.shopify_service import ShopifyService
from services.integration.woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


@router.get("/integration-health")
async def check_integration_health(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Returns complete integration health status for current user.
    
    Use this to identify:
    - Which integrations are active/inactive
    - Which products are linked to which platforms
    - Missing or disabled links
    
    Returns:
        - summary: Quick stats
        - integrations: All integrations with status
        - products: Product-to-platform mapping
        - issues: Identified problems
    """
    
    # 1. Get all user's integrations
    int_stmt = select(Integration).where(Integration.user_id == current_user.id)
    int_result = await db.execute(int_stmt)
    integrations = list(int_result.scalars().all())
    
    integration_summary = []
    integration_map = {i.id: i for i in integrations}

    # Live price fetch helpers (manual diagnostic endpoint, safe to call per link)
    shopify_service = ShopifyService()
    woo_service = WooCommerceService()
    product_price_cache: Dict[tuple[str, str], Any] = {}
    for integration in integrations:
        integration_summary.append({
            "id": str(integration.id),
            "platform": integration.platform.value if hasattr(integration.platform, 'value') else str(integration.platform),
            "store_url": integration.store_url,
            "status": integration.status.value if hasattr(integration.status, 'value') else str(integration.status),
            "is_active": integration.status == IntegrationStatus.ACTIVE,
            "created_at": integration.created_at.isoformat() if integration.created_at else None,
            "last_sync_at": integration.last_sync_at.isoformat() if hasattr(integration, 'last_sync_at') and integration.last_sync_at else None,
        })
    
    # 2. Get all user's products
    prod_stmt = select(Product).where(Product.user_id == current_user.id)
    prod_result = await db.execute(prod_stmt)
    products = list(prod_result.scalars().all())
    
    # 3. Get all product integration links for user's integrations
    if integrations:
        link_stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id.in_([i.id for i in integrations])
        )
        link_result = await db.execute(link_stmt)
        links = list(link_result.scalars().all())
    else:
        links = []
    
    # Build product-to-platform mapping
    product_platform_map = {}
    for product in products:
        product_links = [l for l in links if l.product_id == product.id]
        
        platforms_linked = []
        for link in product_links:
            integration = integration_map.get(link.integration_id)
            if integration:
                platform_name = integration.platform.value if hasattr(integration.platform, 'value') else str(integration.platform)
                int_status = integration.status.value if hasattr(integration.status, 'value') else str(integration.status)

                live_external_price = await _get_live_external_price_for_link(
                    link=link,
                    integration=integration,
                    shopify_service=shopify_service,
                    woo_service=woo_service,
                    product_price_cache=product_price_cache,
                )
                
                platforms_linked.append({
                    "platform": platform_name,
                    "integration_id": str(integration.id),
                    "integration_status": int_status,
                    "sync_enabled": link.sync_enabled,
                    "external_product_id": link.external_product_id,
                    "external_price": live_external_price if live_external_price is not None else (float(link.external_price) if link.external_price is not None else None),
                    "last_price_push_at": link.last_price_push_at.isoformat() if link.last_price_push_at else None,
                    "would_push": link.sync_enabled and integration.status == IntegrationStatus.ACTIVE,
                })
        
        product_platform_map[str(product.id)] = {
            "product_name": product.name,
            "sku": getattr(product, 'sku', None),
            "current_price": float(product.current_price) if product.current_price else None,
            "platforms_linked": platforms_linked,
            "total_platforms": len(platforms_linked),
            "active_push_targets": sum(1 for p in platforms_linked if p["would_push"]),
        }
    
    # 4. Identify issues
    issues = []
    
    # Check for disconnected integrations
    for integration in integrations:
        if integration.status != IntegrationStatus.ACTIVE:
            platform_name = integration.platform.value if hasattr(integration.platform, 'value') else str(integration.platform)
            int_status = integration.status.value if hasattr(integration.status, 'value') else str(integration.status)
            issues.append({
                "type": "INTEGRATION_INACTIVE",
                "severity": "HIGH",
                "message": f"{platform_name} integration is {int_status}",
                "integration_id": str(integration.id),
                "suggestion": "Reconnect your store in the Integrations page",
            })
    
    # Check for products with no active push targets
    for product_id, data in product_platform_map.items():
        if data["active_push_targets"] == 0 and data["total_platforms"] > 0:
            issues.append({
                "type": "NO_ACTIVE_PUSH_TARGET",
                "severity": "HIGH",
                "message": f"Product '{data['product_name']}' is linked but has no active push targets",
                "product_id": product_id,
                "suggestion": "Check sync_enabled and integration status",
            })
        elif data["total_platforms"] == 0:
            issues.append({
                "type": "PRODUCT_NOT_LINKED",
                "severity": "MEDIUM",
                "message": f"Product '{data['product_name']}' is not linked to any platform",
                "product_id": product_id,
                "suggestion": "Sync products from your store in Integrations",
            })
        elif data["active_push_targets"] < data["total_platforms"]:
            issues.append({
                "type": "PARTIAL_PUSH_COVERAGE",
                "severity": "MEDIUM",
                "message": f"Product '{data['product_name']}' won't push to all linked platforms",
                "product_id": product_id,
                "platforms_linked": data["total_platforms"],
                "active_targets": data["active_push_targets"],
                "suggestion": "Check sync_enabled and integration status for all platforms",
            })
    
    # Check for price mismatches
    for product_id, data in product_platform_map.items():
        for platform in data["platforms_linked"]:
            if platform["external_price"] is not None and data["current_price"] is not None:
                diff = abs(platform["external_price"] - data["current_price"])
                if diff > 0.01:
                    issues.append({
                        "type": "PRICE_MISMATCH",
                        "severity": "LOW",
                        "message": f"Product '{data['product_name']}' has price mismatch on {platform['platform']}",
                        "product_id": product_id,
                        "local_price": data["current_price"],
                        "external_price": platform["external_price"],
                        "difference": round(diff, 2),
                    })
    
    return {
        "user_id": str(current_user.id),
        "summary": {
            "total_integrations": len(integrations),
            "active_integrations": sum(1 for i in integrations if i.status == IntegrationStatus.ACTIVE),
            "total_products": len(products),
            "total_links": len(links),
            "issues_found": len(issues),
        },
        "integrations": integration_summary,
        "products": product_platform_map,
        "issues": issues,
    }


@router.get("/product/{product_id}/push-status")
async def check_product_push_status(
    product_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Check exactly what would happen if we pushed a price for this product.
    
    Simulates the exact query from EcommercePushService.push_price() to show:
    - Which platforms it WOULD push to
    - Which platforms are SKIPPED and why
    """
    
    # Get the product
    product = await db.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Simulate the exact query from EcommercePushService.push_price()
    # This is the query that determines what gets pushed
    stmt = (
        select(ProductIntegrationLink)
        .join(Integration, ProductIntegrationLink.integration_id == Integration.id)
        .where(ProductIntegrationLink.product_id == product_id)
        .where(ProductIntegrationLink.sync_enabled == True)
        .where(Integration.status == IntegrationStatus.ACTIVE)
    )
    result = await db.execute(stmt)
    active_links = list(result.scalars().all())
    
    # Also get ALL links (including inactive/disabled) for comparison
    all_links_stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.product_id == product_id
    )
    all_links_result = await db.execute(all_links_stmt)
    all_links = list(all_links_result.scalars().all())
    
    # Get integrations for these links
    if all_links:
        int_stmt = select(Integration).where(
            Integration.id.in_([l.integration_id for l in all_links])
        )
        int_result = await db.execute(int_stmt)
        integrations = {str(i.id): i for i in int_result.scalars().all()}
    else:
        integrations = {}
    
    # Build detailed status for each link
    link_details = []
    for link in all_links:
        integration = integrations.get(str(link.integration_id))
        
        will_push = (
            link.sync_enabled and 
            integration and 
            integration.status == IntegrationStatus.ACTIVE
        )
        
        # Determine skip reason
        skip_reason = None
        if not integration:
            skip_reason = "Integration not found in database"
        elif integration.status != IntegrationStatus.ACTIVE:
            status_val = integration.status.value if hasattr(integration.status, 'value') else str(integration.status)
            skip_reason = f"Integration status is {status_val}"
        elif not link.sync_enabled:
            skip_reason = "sync_enabled is False for this product-integration link"
        
        platform_name = "unknown"
        int_status = "unknown"
        if integration:
            platform_name = integration.platform.value if hasattr(integration.platform, 'value') else str(integration.platform)
            int_status = integration.status.value if hasattr(integration.status, 'value') else str(integration.status)
        
        link_details.append({
            "platform": platform_name,
            "integration_id": str(link.integration_id),
            "integration_status": int_status,
            "sync_enabled": link.sync_enabled,
            "external_product_id": link.external_product_id,
            "external_variant_id": link.external_variant_id,
            "current_external_price": float(link.external_price) if link.external_price else None,
            "will_push": will_push,
            "skip_reason": skip_reason,
            "last_push_at": link.last_price_push_at.isoformat() if link.last_price_push_at else None,
        })
    
    push_targets = [d for d in link_details if d["will_push"]]
    skipped_targets = [d for d in link_details if not d["will_push"]]
    
    return {
        "product_id": str(product_id),
        "product_name": product.name,
        "current_price": float(product.current_price) if product.current_price else None,
        "total_links": len(all_links),
        "active_links_count": len(active_links),
        "would_succeed": len(active_links) > 0,
        "push_targets": push_targets,
        "skipped_targets": skipped_targets,
        "all_link_details": link_details,
        "diagnosis": _diagnose_push_status(push_targets, skipped_targets, link_details),
    }


def _diagnose_push_status(push_targets, skipped_targets, all_links):
    """Generate a human-readable diagnosis."""
    if not all_links:
        return {
            "status": "NO_LINKS",
            "message": "This product is not linked to any e-commerce platform.",
            "action": "Go to Integrations and sync your products from your store.",
        }
    
    if not push_targets:
        reasons = list(set(t["skip_reason"] for t in skipped_targets if t["skip_reason"]))
        return {
            "status": "ALL_SKIPPED",
            "message": f"Product is linked to {len(all_links)} platform(s), but all are skipped.",
            "skip_reasons": reasons,
            "action": "Check integration status and sync_enabled settings.",
        }
    
    if skipped_targets:
        return {
            "status": "PARTIAL",
            "message": f"Will push to {len(push_targets)} platform(s), skipping {len(skipped_targets)}.",
            "pushing_to": [t["platform"] for t in push_targets],
            "skipping": [{"platform": t["platform"], "reason": t["skip_reason"]} for t in skipped_targets],
            "action": "If you want all platforms, fix the skipped ones.",
        }
    
    return {
        "status": "OK",
        "message": f"Will push to all {len(push_targets)} linked platform(s).",
        "platforms": [t["platform"] for t in push_targets],
        "action": None,
    }


async def _get_live_external_price_for_link(
    link: ProductIntegrationLink,
    integration: Integration,
    shopify_service: ShopifyService,
    woo_service: WooCommerceService,
    product_price_cache: Dict[tuple[str, str], Any],
) -> Optional[float]:
    """Best-effort live price fetch for a link; returns None on any failure."""
    try:
        access_token = decrypt_token(integration.access_token_encrypted)
    except Exception:
        return None

    platform = integration.platform.value if hasattr(integration.platform, "value") else str(integration.platform)
    platform = platform.lower()
    cache_key = (str(integration.id), link.external_product_id)

    external_product = product_price_cache.get(cache_key)
    if external_product is None:
        try:
            if platform == "shopify":
                external_product = await shopify_service.fetch_single_product(
                    store_url=integration.store_url,
                    access_token=access_token,
                    external_product_id=link.external_product_id,
                )
            elif platform == "woocommerce":
                external_product = await woo_service.fetch_single_product(
                    store_url=integration.store_url,
                    access_token=access_token,
                    external_product_id=link.external_product_id,
                )
            else:
                return None
        except Exception:
            return None
        product_price_cache[cache_key] = external_product

    if not external_product:
        return None

    variant_price = _resolve_variant_price(external_product, link.external_variant_id)
    if variant_price is not None:
        return float(variant_price)

    if getattr(external_product, "price", None) is not None:
        return float(external_product.price)

    return None


def _resolve_variant_price(external_product: Any, external_variant_id: Optional[str]) -> Optional[float]:
    if not external_variant_id:
        return None

    variants = getattr(external_product, "variants", None)
    if not variants:
        return None

    for variant in variants:
        if str(getattr(variant, "id", "")) == str(external_variant_id):
            return getattr(variant, "price", None)

    return None



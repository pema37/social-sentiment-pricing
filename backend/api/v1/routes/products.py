# backend/api/v1/routes/products.py
"""
Products API Router
===================

Thin controller that handles HTTP routing and delegates to services.
All business logic lives in services/products/.

Best Practices Applied:
- Thin Controllers: Routes just validate, authenticate, and delegate
- Separation of Concerns: No business logic in route handlers
- Consistent Responses: All list endpoints return PaginatedResponse
- Proper HTTP Status Codes: 201 create, 204 delete, 404 not found

FIX (2026-02-21): Added platform link enrichment to list_products endpoint.
Products now include `platforms_linked` array showing which e-commerce
platforms each product is connected to. See BUG-005 in audit report.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from models.user import User
from models.integration import Integration, ProductIntegrationLink, IntegrationStatus
from schemas.product import ProductCreate, ProductUpdate, ProductRead, PriceSuggestion, PlatformLink
from schemas.common import PaginatedResponse
from api.v1.routes.auth import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT, ANALYSIS_RATE_LIMIT, BULK_RATE_LIMIT

# Import services
from services.products import ProductService, ProductImportService
from services.products.import_service import ImportProductRow


router = APIRouter(prefix="/products", tags=["products"])


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY - Service Factory
# Creates service instance with injected session
# ═══════════════════════════════════════════════════════════════════════════════

def get_product_service(
    session: AsyncSession = Depends(get_session),
) -> ProductService:
    """Dependency that creates ProductService with session."""
    return ProductService(session)


def get_import_service(
    session: AsyncSession = Depends(get_session),
) -> ProductImportService:
    """Dependency that creates ProductImportService with session."""
    return ProductImportService(session)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER - Platform Link Enrichment
# ═══════════════════════════════════════════════════════════════════════════════

async def _enrich_with_platform_links(
    products: list,
    user_id: UUID,
    session: AsyncSession,
) -> dict[UUID, list[PlatformLink]]:
    """
    Batch-fetch platform links for a list of products.
    
    Single query for all products — avoids N+1.
    Returns: { product_id: [PlatformLink, ...] }
    """
    if not products:
        return {}

    product_ids = [p.id for p in products]

    # Get all integrations for this user
    int_stmt = select(Integration).where(Integration.user_id == user_id)
    int_result = await session.execute(int_stmt)
    integrations = {i.id: i for i in int_result.scalars().all()}

    if not integrations:
        return {}

    # Get all links for these products in one query
    link_stmt = (
        select(ProductIntegrationLink)
        .where(ProductIntegrationLink.product_id.in_(product_ids))
        .where(ProductIntegrationLink.integration_id.in_(integrations.keys()))
    )
    link_result = await session.execute(link_stmt)
    links = list(link_result.scalars().all())

    # Build mapping
    platform_map: dict[UUID, list[PlatformLink]] = {pid: [] for pid in product_ids}
    for link in links:
        integration = integrations.get(link.integration_id)
        if not integration:
            continue
        platform_name = (
            integration.platform.value
            if hasattr(integration.platform, 'value')
            else str(integration.platform)
        )
        platform_map[link.product_id].append(PlatformLink(
            platform=platform_name,
            store_url=integration.store_url,
            external_price=float(link.external_price) if link.external_price else None,
            sync_enabled=link.sync_enabled,
        ))

    return platform_map


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_product(
    request: Request,
    payload: ProductCreate,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """Create a new product."""
    product = await service.create(current_user.id, payload)
    return product


# ═══════════════════════════════════════════════════════════════════════════════
# READ
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: Optional[bool] = Query(default=None),
    category: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_session),
):
    """List all products for the current user with pagination."""
    products, total = await service.list(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        is_active=is_active,
        category=category,
    )
    
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # ─────────────────────────────────────────────────────────────────────
    # FIX BUG-005: Enrich products with platform links (single batch query)
    # ─────────────────────────────────────────────────────────────────────
    platform_map = await _enrich_with_platform_links(
        products, current_user.id, session
    )

    # Convert ORM objects to response dicts with platform data
    items = []
    for product in products:
        product_dict = ProductRead.model_validate(product).model_dump()
        product_dict["platforms_linked"] = [
            pl.model_dump() for pl in platform_map.get(product.id, [])
        ]
        items.append(product_dict)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    request: Request,
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """Get a specific product by ID."""
    product = await service.get_by_id(product_id, current_user.id)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    return product


# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{product_id}", response_model=ProductRead)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_product(
    request: Request,
    product_id: UUID,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """Update a product (partial update)."""
    product = await service.update(product_id, current_user.id, payload)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    return product


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_product(
    request: Request,
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """Delete a product and all related data."""
    try:
        deleted = await service.delete(product_id, current_user.id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BULK IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field


class ImportProductsRequest(BaseModel):
    """Request body for bulk product import."""
    products: List[ImportProductRow] = Field(..., min_length=1, max_length=1000)


class ImportProductsResponse(BaseModel):
    """Response for bulk product import."""
    created: int
    updated: int = 0
    skipped: int = 0
    failed: int
    errors: List[str]


@router.post("/import", response_model=ImportProductsResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(BULK_RATE_LIMIT)
async def import_products(
    request: Request,
    payload: ImportProductsRequest,
    current_user: User = Depends(get_current_user),
    service: ProductImportService = Depends(get_import_service),
):
    """
    Import multiple products from CSV data.
    
    Compatible with WooCommerce and Shopify CSV exports.
    """
    try:
        result = await service.import_products(
            user_id=current_user.id,
            products=payload.products,
            skip_duplicates=True,
        )
        
        return ImportProductsResponse(
            created=result.created,
            updated=result.updated,
            skipped=result.skipped,
            failed=result.failed,
            errors=result.errors[:10],  # Limit errors in response
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AI PRICE SUGGESTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{product_id}/price-suggestion", response_model=PriceSuggestion)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def get_price_suggestion(
    request: Request,
    product_id: UUID,
    use_ai: bool = Query(False, description="Use AI for enhanced explanation"),
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """Get AI-powered price suggestion based on sentiment analysis."""
    suggestion = await service.get_price_suggestion(product_id, current_user.id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    # Enhance with AI explanation if requested
    if use_ai:
        from services.ai_generator import ai_generator
        
        if ai_generator.is_available():
            try:
                product = await service.get_by_id(product_id, current_user.id)
                ai_explanation = await ai_generator.generate_pricing_explanation(
                    product_name=product.name,
                    current_price=float(suggestion["current_price"]),
                    suggested_price=float(suggestion["suggested_price"]),
                    sentiment_score=float(suggestion["factors"].get("sentiment_score", 0)),
                    factors=[
                        f"Sentiment: {suggestion['factors'].get('trend', 'stable')}",
                        f"Mentions: {suggestion['factors'].get('mention_volume', 0)}",
                    ],
                )
                suggestion["reasoning"] = ai_explanation["explanation"]
                suggestion["factors"]["ai_key_factors"] = ai_explanation["key_factors"]
                suggestion["factors"]["ai_powered"] = True
            except Exception as e:
                # Fall back to basic reasoning if AI fails
                suggestion["factors"]["ai_powered"] = False
    
    return suggestion

# ═══════════════════════════════════════════════════════════════════════════════
# AI DESCRIPTION GENERATOR 
# ═══════════════════════════════════════════════════════════════════════════════

class GenerateDescriptionRequest(BaseModel):
    """Request for AI description generation."""
    tone: str = Field(default="professional", description="Tone: professional, casual, luxury, technical")
    length: str = Field(default="medium", description="Length: short, medium, long")


class GenerateDescriptionResponse(BaseModel):
    """Response from AI description generation."""
    description: str
    seo_title: str
    meta_description: str
    suggested_keywords: List[str]
    ai_generated: bool = True


@router.post("/{product_id}/generate-description", response_model=GenerateDescriptionResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def generate_description(
    request: Request,
    product_id: UUID,
    payload: GenerateDescriptionRequest,
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    """
    Generate AI-powered SEO-optimized product description.
    
    Uses GPT-4o-mini to create compelling product copy based on:
    - Product name and category
    - Keywords configured for sentiment tracking
    - Existing description (if any) for improvement
    """
    from services.ai_generator import ai_generator
    
    if not ai_generator.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not available. Please configure OPENAI_API_KEY.",
        )
    
    # Get product
    product = await service.get_by_id(product_id, current_user.id)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    try:
        result = await ai_generator.generate_product_description(
            name=product.name,
            category=product.category,
            keywords=product.keywords,
            current_description=product.description,
            tone=payload.tone,
            length=payload.length,
        )
        
        return GenerateDescriptionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    


    
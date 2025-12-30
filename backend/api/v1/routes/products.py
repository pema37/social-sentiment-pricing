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
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from models.user import User
from schemas.product import ProductCreate, ProductUpdate, ProductRead, PriceSuggestion
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
    
    return PaginatedResponse(
        items=products,
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
    
    return suggestion


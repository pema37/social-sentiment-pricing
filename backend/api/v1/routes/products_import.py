# backend/api/v1/routes/products_import.py
"""
Product Import Endpoint

Handles bulk product import from CSV data.
Compatible with WooCommerce and Shopify CSV exports.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from models import User, Product
from api.v1.routes.auth import get_current_user
from core.rate_limit import limiter, BULK_RATE_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ImportProductRow(BaseModel):
    """Single product row from CSV import."""
    name: str = Field(..., min_length=1, max_length=255)
    sku: Optional[str] = Field(default=None, max_length=100)
    base_price: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    image_url: Optional[str] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)

    @field_validator('base_price', mode='before')
    @classmethod
    def parse_price(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v.replace(',', '').replace('$', '').strip())
            except InvalidOperation:
                raise ValueError('Invalid price format')
        return v


class ImportProductsRequest(BaseModel):
    """Request body for bulk product import."""
    products: List[ImportProductRow] = Field(..., min_length=1, max_length=1000)


class ImportProductsResponse(BaseModel):
    """Response for bulk product import."""
    created: int
    failed: int
    errors: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/import",
    response_model=ImportProductsResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(BULK_RATE_LIMIT)
async def import_products(
    request: Request,
    payload: ImportProductsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Import multiple products from CSV data.
    
    Accepts an array of product objects. Each product must have:
    - name (required)
    - base_price (required, must be > 0)
    
    Optional fields: sku, description, category, image_url, stock_quantity
    
    Returns count of created products and any errors encountered.
    """
    # ═══════════════════════════════════════════════════════════════════════
    # DEBUG LOGGING - Remove after fixing the issue
    # ═══════════════════════════════════════════════════════════════════════
    logger.info(f"🔍 IMPORT DEBUG: Endpoint hit by user {current_user.id}")
    logger.info(f"🔍 IMPORT DEBUG: Received {len(payload.products)} products in payload")
    
    for i, p in enumerate(payload.products[:3]):  # Log first 3 for debugging
        logger.info(f"🔍 IMPORT DEBUG: Product {i}: name='{p.name}', price={p.base_price}, sku={p.sku}")
    # ═══════════════════════════════════════════════════════════════════════
    
    created = 0
    failed = 0
    errors: List[str] = []

    for idx, row in enumerate(payload.products):
        try:
            logger.info(f"🔍 IMPORT DEBUG: Processing row {idx + 1}: {row.name}")
            
            product = Product(
                user_id=current_user.id,
                name=row.name.strip(),
                sku=row.sku.strip() if row.sku else None,
                description=row.description.strip() if row.description else None,
                category=row.category.strip() if row.category else None,
                image_url=row.image_url.strip() if row.image_url else None,
                base_price=row.base_price,
                current_price=row.base_price,
                is_active=True,
                auto_pricing_enabled=False,
                keywords=[],
            )
            session.add(product)
            created += 1
            logger.info(f"🔍 IMPORT DEBUG: Row {idx + 1} added to session (created={created})")
            
        except Exception as e:
            failed += 1
            error_msg = f"Row {idx + 1} ({row.name}): {str(e)}"
            errors.append(error_msg)
            logger.error(f"🔍 IMPORT DEBUG: Row {idx + 1} FAILED: {e}")

    logger.info(f"🔍 IMPORT DEBUG: Loop complete. created={created}, failed={failed}")

    # Commit all successful products
    if created > 0:
        try:
            logger.info(f"🔍 IMPORT DEBUG: Attempting to commit {created} products...")
            await session.commit()
            logger.info(f"🔍 IMPORT DEBUG: Commit successful!")
        except Exception as e:
            # Rollback and report error
            await session.rollback()
            logger.error(f"🔍 IMPORT DEBUG: Commit FAILED: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save products: {str(e)}",
            )
    else:
        logger.warning(f"🔍 IMPORT DEBUG: No products to commit (created=0)")

    result = ImportProductsResponse(
        created=created,
        failed=failed,
        errors=errors[:10],
    )
    
    logger.info(f"🔍 IMPORT DEBUG: Returning response: created={result.created}, failed={result.failed}")
    
    return result




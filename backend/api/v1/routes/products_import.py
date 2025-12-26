# backend/api/v1/routes/products_import.py
"""
Product Import Endpoint

Handles bulk product import from CSV data.
Compatible with WooCommerce and Shopify CSV exports.
"""

from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from models import User, Product
from api.v1.routes.auth import get_current_user
from core.rate_limit import limiter, BULK_RATE_LIMIT

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
    created = 0
    failed = 0
    errors: List[str] = []

    for idx, row in enumerate(payload.products):
        try:
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
            
        except Exception as e:
            failed += 1
            errors.append(f"Row {idx + 1} ({row.name}): {str(e)}")

    # Commit all successful products
    if created > 0:
        try:
            await session.commit()
        except Exception as e:
            # Rollback and report error
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save products: {str(e)}",
            )

    return ImportProductsResponse(
        created=created,
        failed=failed,
        errors=errors[:10],  # Limit errors returned to prevent huge responses
    )

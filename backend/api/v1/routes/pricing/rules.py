# backend/api/v1/routes/pricing/rules.py
"""
Pricing Rules CRUD endpoints.

Provides endpoints for creating, reading, updating, and deleting
pricing rules that drive automatic price recommendations.

Best Practices Applied:
- Consistent paginated response structure across all list endpoints
- Proper HTTP status codes (201 for create, 204 for delete)
- Authorization checks on every request
- Rate limiting on write operations
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from db.session import get_session
from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from models.user import User
from models.product import Product
from models.pricing_rule import PricingRule
from schemas.pricing import (
    PricingRuleCreate,
    PricingRuleUpdate,
    PricingRuleResponse,
)
from schemas.common import PaginatedResponse

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/rules", response_model=PricingRuleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_rule(
    request: Request,
    data: PricingRuleCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new pricing rule.
    
    - Validates that the product exists and belongs to the user
    - Associates rule with the authenticated user
    - Returns 201 Created with the new rule
    """
    # Verify product ownership
    product = await db.get(Product, data.product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Create rule with user_id set from auth
    rule = PricingRule(user_id=current_user.id, **data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


# ═══════════════════════════════════════════════════════════════════════════════
# READ (LIST) - PAGINATED
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rules", response_model=PaginatedResponse[PricingRuleResponse])
async def list_rules(
    request: Request,
    product_id: Optional[UUID] = Query(default=None, description="Filter by product ID"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    List pricing rules with pagination and optional filters.
    
    Returns a consistent paginated response structure:
    {
        "items": [...],
        "total": 42,
        "page": 1,
        "page_size": 20,
        "total_pages": 3
    }
    
    Filters:
    - product_id: Only return rules for a specific product
    - is_active: Only return active (true) or inactive (false) rules
    
    Sorting: By priority descending (higher priority first)
    """
    # Build base query with user filter (security: only show user's rules)
    base_stmt = select(PricingRule).where(PricingRule.user_id == current_user.id)
    
    # Apply optional filters
    if product_id:
        base_stmt = base_stmt.where(PricingRule.product_id == product_id)
    if is_active is not None:
        base_stmt = base_stmt.where(PricingRule.is_active == is_active)
    
    # Get total count for pagination metadata
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    offset = (page - 1) * page_size
    
    # Get paginated items, sorted by priority (descending)
    items_stmt = (
        base_stmt
        .order_by(PricingRule.priority.desc(), PricingRule.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(items_stmt)
    rules = list(result.scalars().all())
    
    return PaginatedResponse(
        items=rules,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# READ (SINGLE)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rules/{rule_id}", response_model=PricingRuleResponse)
async def get_rule(
    request: Request,
    rule_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific pricing rule by ID.
    
    - Returns 404 if rule doesn't exist or doesn't belong to user
    """
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE (PARTIAL)
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/rules/{rule_id}", response_model=PricingRuleResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_rule(
    request: Request,
    rule_id: UUID,
    data: PricingRuleUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update a pricing rule (partial update).
    
    - Only updates fields provided in the request body
    - Automatically updates the updated_at timestamp
    - Returns 404 if rule doesn't exist or doesn't belong to user
    """
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Only update fields that were actually provided
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    # Update timestamp
    rule.updated_at = datetime.now(timezone.utc)
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_rule(
    request: Request,
    rule_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a pricing rule.
    
    - Returns 404 if rule doesn't exist or doesn't belong to user
    - Returns 204 No Content on success
    """
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    return None


# backend/api/v1/routes/pricing/rules.py
"""
Pricing Rules CRUD endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

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

router = APIRouter()


@router.post("/rules", response_model=PricingRuleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_rule(
    request: Request,
    data: PricingRuleCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new pricing rule."""
    product = await db.get(Product, data.product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    rule = PricingRule(user_id=current_user.id, **data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/rules", response_model=list[PricingRuleResponse])
async def list_rules(
    request: Request,
    product_id: Optional[UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List pricing rules."""
    stmt = select(PricingRule).where(PricingRule.user_id == current_user.id)
    
    if product_id:
        stmt = stmt.where(PricingRule.product_id == product_id)
    if is_active is not None:
        stmt = stmt.where(PricingRule.is_active == is_active)
    
    stmt = stmt.order_by(PricingRule.priority.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/rules/{rule_id}", response_model=PricingRuleResponse)
async def get_rule(
    request: Request,
    rule_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific pricing rule."""
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.patch("/rules/{rule_id}", response_model=PricingRuleResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_rule(
    request: Request,
    rule_id: UUID,
    data: PricingRuleUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a pricing rule."""
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_rule(
    request: Request,
    rule_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a pricing rule."""
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
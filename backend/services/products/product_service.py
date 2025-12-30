# backend/services/products/product_service.py
"""
Product Service
===============

Business logic for product CRUD operations.
Controllers call this service - they don't contain business logic themselves.

Best Practices Applied:
- Thin Controllers: Route handlers just validate and delegate
- Dependency Injection: Session passed in, not created
- Single Responsibility: Only handles product CRUD
- Reusability: Can be called from routes, background tasks, CLI, etc.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from models.product import Product
from models.user import User
from models.sentiment import Sentiment
from schemas.product import ProductCreate, ProductUpdate
from services.sentiment_analyzer import sentiment_analyzer
from services.pricing_engine import pricing_engine
from .cascade_delete import cascade_delete_product

logger = logging.getLogger(__name__)


class ProductService:
    """
    Product business logic service.
    
    Usage:
        service = ProductService(session)
        product = await service.create(user_id, data)
        products, total = await service.list(user_id, page=1, page_size=20)
        await service.delete(product_id, user_id)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ═══════════════════════════════════════════════════════════════════════
    # CREATE
    # ═══════════════════════════════════════════════════════════════════════
    
    async def create(
        self,
        user_id: UUID,
        data: ProductCreate,
    ) -> Product:
        """
        Create a new product.
        
        - Sets current_price = base_price initially
        - Associates with user
        - Returns created product with ID
        """
        product = Product(
            user_id=user_id,
            name=data.name,
            sku=data.sku,
            description=data.description,
            category=data.category,
            image_url=data.image_url,
            is_active=data.is_active,
            base_price=data.base_price,
            current_price=data.base_price,  # Start at base price
            cost=data.cost,
            min_price=data.min_price,
            max_price=data.max_price,
            sentiment_multiplier=data.sentiment_multiplier,
            auto_pricing_enabled=data.auto_pricing_enabled,
            keywords=data.keywords,
        )
        
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        
        logger.info(f"Created product {product.id} for user {user_id}")
        return product
    
    # ═══════════════════════════════════════════════════════════════════════
    # READ
    # ═══════════════════════════════════════════════════════════════════════
    
    async def get_by_id(
        self,
        product_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Product]:
        """
        Get a product by ID.
        
        Args:
            product_id: The product UUID
            user_id: If provided, verifies ownership
            
        Returns:
            Product or None if not found / not authorized
        """
        product = await self.session.get(Product, product_id)
        
        if not product:
            return None
        
        # If user_id provided, verify ownership
        if user_id and product.user_id != user_id:
            return None
        
        return product
    
    async def list(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> Tuple[List[Product], int]:
        """
        List products for a user with pagination.
        
        Returns:
            Tuple of (products, total_count)
        """
        # Build base query
        base_query = select(Product).where(Product.user_id == user_id)
        
        # Apply filters
        if is_active is not None:
            base_query = base_query.where(Product.is_active == is_active)
        if category:
            base_query = base_query.where(Product.category == category)
        
        # Get total count
        count_stmt = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0
        
        # Get paginated items
        offset = (page - 1) * page_size
        items_stmt = (
            base_query
            .order_by(Product.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(items_stmt)
        products = list(result.scalars().all())
        
        return products, total
    
    # ═══════════════════════════════════════════════════════════════════════
    # UPDATE
    # ═══════════════════════════════════════════════════════════════════════
    
    async def update(
        self,
        product_id: UUID,
        user_id: UUID,
        data: ProductUpdate,
    ) -> Optional[Product]:
        """
        Update a product (partial update).
        
        Returns:
            Updated product or None if not found / not authorized
        """
        product = await self.get_by_id(product_id, user_id)
        
        if not product:
            return None
        
        # Only update provided fields
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        product.updated_at = datetime.now(timezone.utc)
        
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        
        logger.info(f"Updated product {product_id}")
        return product
    
    # ═══════════════════════════════════════════════════════════════════════
    # DELETE
    # ═══════════════════════════════════════════════════════════════════════
    
    async def delete(
        self,
        product_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a product and all related data.
        
        Returns:
            True if deleted, False if not found / not authorized
        """
        product = await self.get_by_id(product_id, user_id)
        
        if not product:
            return False
        
        try:
            # Delete all related records first (FK constraints)
            deleted_counts = await cascade_delete_product(self.session, product_id)
            
            # Now delete the product itself
            await self.session.delete(product)
            await self.session.commit()
            
            logger.info(
                f"Deleted product {product_id} and {sum(deleted_counts.values())} related records"
            )
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete product {product_id}: {e}")
            raise
    
    # ═══════════════════════════════════════════════════════════════════════
    # AI PRICE SUGGESTION
    # ═══════════════════════════════════════════════════════════════════════
    
    async def get_price_suggestion(
        self,
        product_id: UUID,
        user_id: UUID,
    ) -> Optional[dict]:
        """
        Get AI-powered price suggestion based on sentiment.
        
        Returns:
            Price suggestion dict or None if product not found
        """
        product = await self.get_by_id(product_id, user_id)
        
        if not product:
            return None
        
        # Fetch sentiment records
        stmt = select(Sentiment).where(Sentiment.product_id == product_id)
        result = await self.session.execute(stmt)
        sentiments = result.scalars().all()
        
        if sentiments:
            sentiment_data = [
                {
                    "compound": s.compound_score,
                    "label": (
                        "positive" if s.compound_score > Decimal("0.05")
                        else "negative" if s.compound_score < Decimal("-0.05")
                        else "neutral"
                    )
                }
                for s in sentiments
            ]
            aggregate = sentiment_analyzer.calculate_aggregate(sentiment_data)
            sentiment_score = aggregate["average_compound"]
            mention_volume = aggregate["total_count"]
        else:
            sentiment_score = Decimal("0")
            mention_volume = 0
        
        # Generate suggestion
        suggestion = pricing_engine.calculate_suggestion(
            product=product,
            sentiment_score=sentiment_score,
            mention_volume=mention_volume,
        )
        
        return suggestion
    

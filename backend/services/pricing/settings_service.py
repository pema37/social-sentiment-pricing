# backend/services/pricing/settings_service.py
"""
Pricing Settings Service - Manages user pricing configuration.

FIX (2026-01-28) Priority 2: Creates default settings for new users,
enabling auto-approval to work out of the box.

NOTE: DEFAULT_SETTINGS aligns with PricingSettings model Field defaults.
"""

import logging
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product
from models.pricing_settings import PricingSettings

logger = logging.getLogger(__name__)


# Default settings for new users
# NOTE: These match the PricingSettings model Field(default=...) values
DEFAULT_SETTINGS = {
    "auto_approve_enabled": True,
    "auto_approve_min_confidence": Decimal("0.70"),
    "auto_approve_max_increase": Decimal("5.0"),   # Model default: 5%
    "auto_approve_max_decrease": Decimal("10.0"),  # Model default: 10%
    "min_margin_percent": Decimal("10.0"),
    "max_auto_changes_per_day": 3,
    "global_cooldown_hours": 24,
    "require_approval_above_price": None,
    "recommendation_valid_hours": 48,
    "blackout_hours_start": 0,   # Model default: 0 (midnight)
    "blackout_hours_end": 6,     # Model default: 6 (6am)
    "notify_on_auto_apply": True,
    "notify_on_pending": True,
}


class SettingsService:
    """Manages user pricing settings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create(self, user_id: UUID) -> PricingSettings:
        """
        Get user's pricing settings, creating defaults if none exist.
        
        This is the ONLY method that should be used to fetch settings,
        as it guarantees a PricingSettings row always exists.
        
        Returns:
            PricingSettings (never None)
        """
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        settings = result.scalars().first()
        
        if settings is None:
            settings = await self._create_default_settings(user_id)
        
        return settings
    
    async def get_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """
        Get user's pricing settings without creating defaults.
        
        DEPRECATED: Use get_or_create() instead to ensure settings exist.
        This method is kept for backwards compatibility only.
        """
        logger.warning(
            f"get_settings() called for user {user_id} - "
            "consider using get_or_create() instead"
        )
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def _create_default_settings(self, user_id: UUID) -> PricingSettings:
        """Create default settings for a new user."""
        logger.info(f"Creating default PricingSettings for user {user_id}")
        
        settings = PricingSettings(
            user_id=user_id,
            **DEFAULT_SETTINGS
        )
        
        self.db.add(settings)
        await self.db.commit()
        await self.db.refresh(settings)
        
        logger.info(
            f"Created default PricingSettings for user {user_id}: "
            f"auto_approve=True, min_confidence=0.70, "
            f"max_increase=5%, max_decrease=10%"
        )
        
        return settings
    
    async def update_settings(
        self,
        user_id: UUID,
        **kwargs
    ) -> PricingSettings:
        """
        Update user's pricing settings.
        
        Creates default settings first if they don't exist.
        """
        settings = await self.get_or_create(user_id)
        
        # Update only provided fields
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
            else:
                logger.warning(f"Unknown setting field: {key}")
        
        settings.updated_at = datetime.now(UTC)
        self.db.add(settings)
        await self.db.commit()
        await self.db.refresh(settings)
        
        logger.info(f"Updated PricingSettings for user {user_id}: {list(kwargs.keys())}")
        return settings
    
    def check_requires_approval(
        self,
        product: Product,
        change_percent: Decimal,
        confidence: Decimal,
        settings: Optional[PricingSettings]
    ) -> bool:
        """
        Determine if a recommendation requires manual approval.
        
        Args:
            product: The product being priced
            change_percent: Proposed price change percentage
            confidence: Recommendation confidence score
            settings: User's pricing settings
            
        Returns:
            True if manual approval required, False for auto-approval
        """
        # No settings = require approval (defensive)
        if settings is None:
            logger.warning("check_requires_approval called with None settings")
            return True
        
        # Auto-approve disabled
        if not settings.auto_approve_enabled:
            return True
        
        # Below confidence threshold
        if confidence < settings.auto_approve_min_confidence:
            logger.debug(
                f"Requires approval: confidence {confidence} < "
                f"threshold {settings.auto_approve_min_confidence}"
            )
            return True
        
        # Exceeds increase threshold
        if change_percent > 0 and change_percent > settings.auto_approve_max_increase:
            logger.debug(
                f"Requires approval: increase {change_percent}% > "
                f"threshold {settings.auto_approve_max_increase}%"
            )
            return True
        
        # Exceeds decrease threshold
        if change_percent < 0 and abs(change_percent) > settings.auto_approve_max_decrease:
            logger.debug(
                f"Requires approval: decrease {abs(change_percent)}% > "
                f"threshold {settings.auto_approve_max_decrease}%"
            )
            return True
        
        # High-value product check
        if settings.require_approval_above_price:
            if product.current_price > settings.require_approval_above_price:
                logger.debug(
                    f"Requires approval: price ${product.current_price} > "
                    f"threshold ${settings.require_approval_above_price}"
                )
                return True
        
        # Blackout hours check
        if self._is_blackout_period(settings):
            logger.debug("Requires approval: in blackout period")
            return True
        
        return False
    
    def _is_blackout_period(self, settings: PricingSettings) -> bool:
        """Check if current time is within blackout hours."""
        if settings.blackout_hours_start is None or settings.blackout_hours_end is None:
            return False
        
        current_hour = datetime.now(UTC).hour
        start = settings.blackout_hours_start
        end = settings.blackout_hours_end
        
        # Handle overnight blackouts (e.g., 22:00 - 06:00)
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end


        
               
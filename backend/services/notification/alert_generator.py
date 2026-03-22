# backend/services/notification/alert_generator.py
"""
Alert Generator Service.

Creates alerts from system events (sentiment drops, price recommendations,
competitor changes, trend detection) and triggers notifications.
"""

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from models.alert import (
    Alert,
    AlertChannel,
    AlertConfiguration,
    AlertSeverity,
    AlertStatus,
    AlertType,
)
from services.notification.notification_dispatcher import (
    DispatchResult,
    NotificationDispatcher,
)

logger = logging.getLogger(__name__)


class AlertGenerator:
    """
    Generates alerts from system events and dispatches notifications.

    Usage:
        generator = AlertGenerator(session)
        alert = await generator.generate_sentiment_alert(
            user_id=user.id,
            product_id=product.id,
            sentiment_score=-0.45,
            previous_score=0.12,
            mention_count=847
        )
    """

    def __init__(self, session: AsyncSession, use_celery: bool = True):
        """
        Initialize AlertGenerator.

        Args:
            session: Database session
            use_celery: If True, dispatch via Celery task (async).
                       If False, dispatch synchronously.
        """
        self.session = session
        self.dispatcher = NotificationDispatcher()
        self.use_celery = use_celery

    async def generate_sentiment_alert(
        self,
        user_id: UUID,
        product_id: UUID,
        product_name: str,
        sentiment_score: float,
        previous_score: float,
        mention_count: int = 0,
    ) -> Alert | None:
        """
        Generate alert for significant sentiment change.

        Args:
            user_id: Owner of the product
            product_id: Product with sentiment change
            product_name: Product name for message
            sentiment_score: Current sentiment score
            previous_score: Previous sentiment score
            mention_count: Number of mentions in period

        Returns:
            Created Alert or None if suppressed
        """
        change = sentiment_score - previous_score
        change_pct = abs(change) * 100

        # Determine severity based on change magnitude
        if abs(change) >= 0.5:
            severity = AlertSeverity.CRITICAL
        elif abs(change) >= 0.3:
            severity = AlertSeverity.HIGH
        elif abs(change) >= 0.15:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        direction = "dropped" if change < 0 else "improved"

        title = f"Sentiment {direction.title()} for {product_name}"
        message = (
            f"Sentiment {direction} from {previous_score:.2f} to {sentiment_score:.2f} "
            f"({change_pct:.1f}% change) based on {mention_count} mentions."
        )

        alert_data = {
            "product_name": product_name,
            "current_score": sentiment_score,
            "previous_score": previous_score,
            "change": change,
            "change_percent": change_pct,
            "mention_count": mention_count,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.SENTIMENT_DROP if change < 0 else AlertType.SENTIMENT_SPIKE,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
        )

    async def generate_price_recommendation_alert(
        self,
        user_id: UUID,
        product_id: UUID,
        product_name: str,
        current_price: float,
        recommended_price: float,
        confidence: float,
        recommendation_id: UUID,
        reasoning: str,
    ) -> Alert | None:
        """
        Generate alert for new price recommendation.
        """
        change_pct = ((recommended_price - current_price) / current_price) * 100 if current_price else 0.0
        direction = "increase" if change_pct > 0 else "decrease"

        # Severity based on confidence and change size
        if confidence >= 0.8 and abs(change_pct) >= 10:
            severity = AlertSeverity.HIGH
        elif confidence >= 0.6:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        title = f"Price {direction.title()} Recommended for {product_name}"
        message = (
            f"Recommended {direction} from ${current_price:.2f} to ${recommended_price:.2f} "
            f"({change_pct:+.1f}%) with {confidence:.0%} confidence.\n\n{reasoning}"
        )

        alert_data = {
            "product_name": product_name,
            "current_price": current_price,
            "recommended_price": recommended_price,
            "change_percent": change_pct,
            "confidence": confidence,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.PRICE_RECOMMENDATION,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
            recommendation_id=recommendation_id,
        )

    async def generate_price_applied_alert(
        self,
        user_id: UUID,
        product_id: UUID,
        product_name: str,
        old_price: float,
        new_price: float,
        recommendation_id: UUID | None = None,
        auto_applied: bool = False,
    ) -> Alert | None:
        """
        Generate alert when a price change is applied.
        """
        change_pct = ((new_price - old_price) / old_price) * 100 if old_price else 0.0
        direction = "increased" if change_pct > 0 else "decreased"

        severity = AlertSeverity.MEDIUM if auto_applied else AlertSeverity.LOW

        applied_by = "automatically" if auto_applied else "manually"
        title = f"Price {direction.title()} for {product_name}"
        message = f"Price was {applied_by} {direction} from ${old_price:.2f} to ${new_price:.2f} ({change_pct:+.1f}%)."

        alert_data = {
            "product_name": product_name,
            "old_price": old_price,
            "new_price": new_price,
            "change_percent": change_pct,
            "auto_applied": auto_applied,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.PRICE_APPLIED,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
            recommendation_id=recommendation_id,
        )

    async def generate_competitor_alert(
        self,
        user_id: UUID,
        competitor_id: UUID,
        competitor_name: str,
        product_id: UUID | None,
        product_name: str,
        old_price: float,
        new_price: float,
    ) -> Alert | None:
        """
        Generate alert for competitor price change.
        """
        change_pct = ((new_price - old_price) / old_price) * 100 if old_price else 0.0
        direction = "increased" if change_pct > 0 else "decreased"

        # Larger changes are more important
        if abs(change_pct) >= 20:
            severity = AlertSeverity.HIGH
        elif abs(change_pct) >= 10:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        title = f"Competitor Price Change: {competitor_name}"
        message = (
            f"{competitor_name} {direction} price for {product_name} "
            f"from ${old_price:.2f} to ${new_price:.2f} ({change_pct:+.1f}%)."
        )

        alert_data = {
            "competitor_name": competitor_name,
            "product_name": product_name,
            "old_price": old_price,
            "new_price": new_price,
            "change_percent": change_pct,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.COMPETITOR_PRICE_CHANGE,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
            competitor_id=competitor_id,
        )

    async def generate_volume_surge_alert(
        self,
        user_id: UUID,
        product_id: UUID,
        product_name: str,
        current_volume: int,
        average_volume: int,
        surge_multiplier: float,
    ) -> Alert | None:
        """
        Generate alert for unusual mention volume.
        """
        if surge_multiplier >= 5:
            severity = AlertSeverity.HIGH
        elif surge_multiplier >= 3:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        title = f"Volume Surge for {product_name}"
        message = (
            f"Mention volume is {surge_multiplier:.1f}x higher than average. "
            f"Current: {current_volume} mentions vs average: {average_volume}."
        )

        alert_data = {
            "product_name": product_name,
            "current_volume": current_volume,
            "average_volume": average_volume,
            "surge_multiplier": surge_multiplier,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.VOLUME_SURGE,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
        )

    async def generate_trend_alert(
        self,
        user_id: UUID,
        product_id: UUID | None,
        product_name: str,
        trend_type: str,
        description: str,
        impact_score: float,
    ) -> Alert | None:
        """
        Generate alert for detected trend (viral content, seasonal, etc).
        """
        if impact_score >= 0.7:
            severity = AlertSeverity.HIGH
        elif impact_score >= 0.4:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        title = f"Trend Detected: {trend_type.replace('_', ' ').title()}"
        message = f"{description}\n\nImpact score: {impact_score:.2f}"

        alert_data = {
            "product_name": product_name,
            "trend_type": trend_type,
            "impact_score": impact_score,
        }

        return await self._create_and_dispatch(
            user_id=user_id,
            alert_type=AlertType.TREND_DETECTED,
            severity=severity,
            title=title,
            message=message,
            alert_data=alert_data,
            product_id=product_id,
        )

    async def _create_and_dispatch(
        self,
        user_id: UUID,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        alert_data: dict[str, Any],
        product_id: UUID | None = None,
        competitor_id: UUID | None = None,
        recommendation_id: UUID | None = None,
    ) -> Alert | None:
        """
        Create alert in database and dispatch to configured channels.
        """
        # Find matching alert configuration
        config = await self._find_matching_config(
            user_id=user_id,
            alert_type=alert_type,
            product_id=product_id,
        )

        # Check if alert should be suppressed
        if config and not await self._check_limits(config):
            logger.debug(f"Alert suppressed due to limits: {title}")
            return None

        # Create alert record
        alert = Alert(
            user_id=user_id,
            configuration_id=config.id if config else None,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            product_id=product_id,
            competitor_id=competitor_id,
            recommendation_id=recommendation_id,
            data=alert_data,
            status=AlertStatus.PENDING,
        )

        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        logger.info(f"Alert created: {alert.id} - {title}")

        # Dispatch to external channels if configured
        if config and config.channels:
            await self._dispatch_alert(alert, config)

        return alert

    async def _find_matching_config(
        self,
        user_id: UUID,
        alert_type: AlertType,
        product_id: UUID | None,
    ) -> AlertConfiguration | None:
        """Find active alert configuration matching this alert."""
        stmt = select(AlertConfiguration).where(
            AlertConfiguration.user_id == user_id,
            AlertConfiguration.alert_type == alert_type,
            AlertConfiguration.is_active,
        )

        result = await self.session.execute(stmt)
        configs = result.scalars().all()

        for config in configs:
            # Check product filter
            if config.product_ids and product_id:
                if str(product_id) not in [str(p) for p in config.product_ids]:
                    continue
            return config

        return None

    async def _check_limits(self, config: AlertConfiguration) -> bool:
        """Check cooldown and daily limits."""
        now = datetime.now(UTC)

        # Check cooldown
        if config.last_triggered_at:
            cooldown_end = config.last_triggered_at + timedelta(minutes=config.cooldown_minutes)
            if now < cooldown_end:
                logger.debug(f"Config {config.id} in cooldown until {cooldown_end}")
                return False

        # Check daily limit
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(Alert.id)).where(
            Alert.configuration_id == config.id,
            Alert.created_at >= today_start,
        )
        result = await self.session.execute(stmt)
        today_count = result.scalar_one()

        if today_count >= config.max_per_day:
            logger.debug(f"Config {config.id} hit daily limit: {today_count}/{config.max_per_day}")
            return False

        return True

    async def _dispatch_alert(
        self,
        alert: Alert,
        config: AlertConfiguration,
    ) -> None:
        """Dispatch alert to configured channels."""

        # Use Celery task for async dispatch (recommended)
        if self.use_celery:
            try:
                from workers.tasks.notification_tasks import dispatch_alert_task

                dispatch_alert_task.delay(str(alert.id))
                logger.info(f"Alert {alert.id} queued for async dispatch")

                # Update config last_triggered_at
                config.last_triggered_at = datetime.now(UTC)
                self.session.add(config)
                await self.session.commit()
                return
            except Exception as e:
                logger.warning(f"Failed to queue Celery task, falling back to sync: {e}")

        # Fallback: synchronous dispatch
        await self._dispatch_alert_sync(alert, config)

    async def _dispatch_alert_sync(
        self,
        alert: Alert,
        config: AlertConfiguration,
    ) -> None:
        """Synchronously dispatch alert (fallback if Celery unavailable)."""
        # Get user email from database
        from models.user import User

        user = await self.session.get(User, alert.user_id)

        channels = []
        for c in config.channels:
            if isinstance(c, AlertChannel):
                channels.append(c)
            elif isinstance(c, str):
                with contextlib.suppress(ValueError):
                    channels.append(AlertChannel(c))

        # Get channel-specific settings
        settings = config.channel_settings or {}
        slack_webhook = settings.get("slack_webhook_url")
        webhook_url = settings.get("webhook_url")
        webhook_secret = settings.get("webhook_secret")

        result: DispatchResult = await self.dispatcher.dispatch(
            channels=channels,
            alert_title=alert.title,
            alert_message=alert.message,
            severity=alert.severity.value,
            alert_type=alert.alert_type.value,
            alert_id=str(alert.id),
            alert_data=alert.data,
            recipient_email=user.email if user else None,
            slack_webhook_url=slack_webhook,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )

        # Update alert with dispatch results
        alert.channels_sent = result.channels_sent
        alert.channels_failed = result.channels_failed

        if result.success:
            alert.status = AlertStatus.SENT
            alert.sent_at = datetime.now(UTC)
        else:
            alert.status = AlertStatus.FAILED

        # Update config last_triggered_at
        config.last_triggered_at = datetime.now(UTC)

        self.session.add(alert)
        self.session.add(config)
        await self.session.commit()

        logger.info(f"Alert {alert.id} dispatched: sent={result.channels_sent}, failed={result.channels_failed}")

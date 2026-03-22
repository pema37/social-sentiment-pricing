"""
Subscription Service

Business logic for subscription management, plan changes, and payment processing.
Separated from routes for testability and reusability.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.payment import Payment
from models.subscription import TIER_LIMITS_STR, Subscription
from models.user import User
from schemas.payment import (
    ConfirmPaymentResponse,
    PaymentInfo,
    PaymentRequest,
    PlanInfo,
    SubscriptionInfo,
    TransactionVerification,
)
from core.config import settings
from services.payment.base import PaymentServiceFactory

logger = logging.getLogger(__name__)


# =============================================================================
# PLAN DEFINITIONS
# =============================================================================

PLANS = [
    PlanInfo(
        tier="free",
        name="Free",
        price_monthly=0,
        price_yearly=0,
        product_limit=5,
        features=[
            "Up to 5 products",
            "Basic sentiment analysis",
            "Daily price updates",
            "Email support",
        ],
    ),
    PlanInfo(
        tier="starter",
        name="Starter",
        price_monthly=29,
        price_yearly=290,
        product_limit=50,
        features=[
            "Up to 50 products",
            "Advanced sentiment analysis",
            "Hourly price updates",
            "Competitor tracking (3 competitors)",
            "Priority email support",
        ],
    ),
    PlanInfo(
        tier="professional",
        name="Professional",
        price_monthly=99,
        price_yearly=990,
        product_limit=500,
        features=[
            "Up to 500 products",
            "Real-time sentiment analysis",
            "Real-time price updates",
            "Competitor tracking (10 competitors)",
            "API access",
            "Dedicated support",
        ],
    ),
    PlanInfo(
        tier="enterprise",
        name="Enterprise",
        price_monthly=299,
        price_yearly=2990,
        product_limit=-1,
        features=[
            "Unlimited products",
            "Real-time sentiment analysis",
            "Real-time price updates",
            "Unlimited competitor tracking",
            "Full API access",
            "Custom integrations",
            "24/7 dedicated support",
            "SLA guarantee",
        ],
    ),
]

VALID_TIERS = ["free", "starter", "professional", "enterprise"]


class SubscriptionService:
    """
    Service for managing subscriptions and payments.

    Handles:
    - Creating payment requests
    - Verifying blockchain payments
    - Activating/upgrading subscriptions
    - Subscription status queries
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        # BSV wallet address — from centralized config, no hardcoded fallback
        self.recipient_address = settings.SSP_MNEE_WALLET_ADDRESS
        # Ethereum wallet address — from centralized config
        self.eth_recipient = settings.SSP_ETH_WALLET_ADDRESS

    # =========================================================================
    # DOWNGRADE TO FREE
    # =========================================================================

    async def downgrade_to_free(self, user: User) -> SubscriptionInfo:
        """
        Downgrade a user's subscription to the free tier.

        This cancels any active paid subscription and moves them to free.

        Args:
            user: The user to downgrade

        Returns:
            Updated subscription info
        """
        # Find existing subscription
        result = await self.session.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

        if subscription:
            # Check if already on free
            if subscription.tier == "free":
                logger.info(f"User {user.id} already on free tier")
                return SubscriptionInfo(
                    tier="free",
                    status="active",
                    current_period_start=subscription.current_period_start,
                    current_period_end=subscription.current_period_end,
                    product_limit=self.get_product_limit("free"),
                    products_used=0,
                )

            # Downgrade to free
            old_tier = subscription.tier
            subscription.tier = "free"
            subscription.status = "active"
            subscription.monthly_price = "0.00"
            subscription.cancel_at_period_end = False
            subscription.cancelled_at = datetime.now(UTC)
            subscription.updated_at = datetime.now(UTC)
            # Keep period dates for record but they no longer matter for free

            self.session.add(subscription)
            await self.session.commit()
            await self.session.refresh(subscription)

            logger.info(f"User {user.id} downgraded from {old_tier} to free")

            return SubscriptionInfo(
                tier="free",
                status="active",
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                product_limit=self.get_product_limit("free"),
                products_used=0,
            )
        else:
            # No subscription exists, create a free one
            subscription = Subscription(
                user_id=user.id,
                tier="free",
                status="active",
                monthly_price="0.00",
            )
            self.session.add(subscription)
            await self.session.commit()
            await self.session.refresh(subscription)

            logger.info(f"Created free subscription for user {user.id}")

            return SubscriptionInfo(
                tier="free",
                status="active",
                current_period_start=None,
                current_period_end=None,
                product_limit=self.get_product_limit("free"),
                products_used=0,
            )

    # =========================================================================
    # PLANS
    # =========================================================================

    def get_all_plans(self) -> list[PlanInfo]:
        """Get all available subscription plans."""
        return PLANS

    def get_plan(self, tier: str) -> PlanInfo | None:
        """Get a specific plan by tier."""
        return next((p for p in PLANS if p.tier == tier), None)

    def get_product_limit(self, tier: str) -> int:
        """Get product limit for a tier."""
        tier_config = TIER_LIMITS_STR.get(tier, TIER_LIMITS_STR["free"])
        return tier_config.get("products", 5)

    # =========================================================================
    # SUBSCRIPTION QUERIES
    # =========================================================================

    async def get_user_subscription(self, user: User) -> SubscriptionInfo:
        """Get current subscription for a user."""
        result = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user.id).where(Subscription.status == "active")
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return SubscriptionInfo(
                tier="free",
                status="active",
                current_period_start=None,
                current_period_end=None,
                product_limit=self.get_product_limit("free"),
                products_used=0,
            )

        return SubscriptionInfo(
            tier=subscription.tier,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            product_limit=self.get_product_limit(subscription.tier),
            products_used=0,  # TODO: Count actual products
        )

    # =========================================================================
    # PAYMENT CREATION
    # =========================================================================

    def _get_recipient_for_network(self, network: str) -> str:
        """
        Get the correct recipient wallet address for the payment network.

        Args:
            network: 'ethereum' or 'bsv'

        Returns:
            Wallet address for that network

        Raises:
            ValueError: If network wallet is not configured
        """
        if network == "ethereum":
            if not self.eth_recipient:
                raise ValueError(
                    "Ethereum payments not configured. Please set SSP_ETH_WALLET_ADDRESS environment variable."
                )
            return self.eth_recipient
        else:  # bsv
            return self.recipient_address

    async def create_subscription_payment(
        self,
        user: User,
        tier: str,
        billing_cycle: str = "monthly",
        network: str = "bsv",  # NEW: Accept network parameter
    ) -> tuple[PaymentRequest, Payment]:
        """
        Create a payment request for a subscription.

        Args:
            user: The user subscribing
            tier: Subscription tier
            billing_cycle: 'monthly' or 'yearly'
            network: Payment network - 'ethereum' or 'bsv'

        Returns the payment request details and the Payment record.
        """
        # Validate tier
        if tier not in VALID_TIERS:
            raise ValueError(f"Invalid tier: {tier}. Must be one of: {VALID_TIERS}")

        if tier == "free":
            raise ValueError("Free tier doesn't require payment")

        # Validate network
        if network not in ["ethereum", "bsv"]:
            raise ValueError(f"Invalid network: {network}. Must be 'ethereum' or 'bsv'")

        # Get correct recipient address for the network
        recipient_address = self._get_recipient_for_network(network)

        # Get plan pricing
        plan = self.get_plan(tier)
        if not plan:
            raise ValueError(f"Plan not found: {tier}")

        # Calculate amount
        if billing_cycle == "yearly":
            amount = plan.price_yearly
        else:
            amount = plan.price_monthly

        # MNEE uses 5 decimal places (1 MNEE = $1)
        amount_raw = int(amount * 100000)

        # Create payment record
        payment_id = uuid4()
        payment = Payment(
            id=payment_id,
            user_id=user.id,
            amount=str(amount),
            amount_raw=amount_raw,
            payment_type="subscription",
            status="pending",
            metadata_json=json.dumps(
                {
                    "tier": tier,
                    "billing_cycle": billing_cycle,
                    "network": network,  # Store network for verification
                }
            ),
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)

        # Build payment request with CORRECT recipient address
        payment_id_str = str(payment.id)
        payment_request = PaymentRequest(
            payment_id=payment_id_str,
            amount=f"{amount:.2f}",
            amount_raw=amount_raw,
            currency="MNEE",
            recipient_address=recipient_address,  # FIXED: Network-aware!
            memo=f"SSP-{payment_id_str[:8]}",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            network=network,  # NEW: Tell frontend which network
            network_options=["bsv", "ethereum"],
        )

        logger.info(
            f"Created {network} payment for user {user.id}: "
            f"tier={tier}, amount={amount}, recipient={recipient_address[:16]}..."
        )

        return payment_request, payment

    # =========================================================================
    # PAYMENT VERIFICATION
    # =========================================================================

    async def confirm_payment(
        self,
        payment_id: UUID,
        user: User,
        transaction_hash: str,
        network: str = "bsv",
    ) -> ConfirmPaymentResponse:
        """
        Confirm a payment and activate the subscription.

        1. Find the payment record
        2. Verify transaction on blockchain
        3. Update payment status
        4. Create/update subscription
        """
        # Find payment
        payment = await self._get_user_payment(payment_id, user.id)
        if not payment:
            return ConfirmPaymentResponse(
                success=False,
                message="Payment not found",
            )

        # Check payment status
        if payment.status == "confirmed":
            return ConfirmPaymentResponse(
                success=False,
                message="Payment already confirmed",
                payment_id=str(payment.id),
                payment_status=payment.status,
            )

        if payment.status not in ["pending", "processing"]:
            return ConfirmPaymentResponse(
                success=False,
                message=f"Cannot confirm payment with status: {payment.status}",
                payment_id=str(payment.id),
                payment_status=payment.status,
            )

        # Verify on blockchain
        verification = await self._verify_blockchain_payment(
            transaction_hash=transaction_hash,
            network=network,
            expected_amount=payment.amount_raw,
            expected_memo=f"SSP-{str(payment.id)[:8]}",
        )

        # Get metadata
        metadata = self._get_payment_metadata(payment)
        tier = metadata.get("tier", "starter")
        billing_cycle = metadata.get("billing_cycle", "monthly")

        # Update payment record
        payment.status = "confirmed" if verification.verified else "processing"
        payment.txid = transaction_hash
        payment.updated_at = datetime.now(UTC)

        if verification.verified:
            payment.confirmed_at = datetime.now(UTC)
            payment.from_address = verification.from_address

        # Activate subscription only when blockchain verification succeeds
        should_activate = verification.verified

        if should_activate:
            payment.status = "confirmed"
            payment.confirmed_at = datetime.now(UTC)
            subscription = await self._activate_subscription(
                user=user,
                tier=tier,
                billing_cycle=billing_cycle,
                payment=payment,
            )

            await self.session.commit()

            return ConfirmPaymentResponse(
                success=True,
                message=f"Payment confirmed! Your {tier.title()} subscription is now active.",
                payment_id=str(payment.id),
                payment_status="confirmed",
                subscription_tier=subscription.tier,
                subscription_status=subscription.status,
                verified_on_chain=verification.verified,
            )

        await self.session.commit()

        return ConfirmPaymentResponse(
            success=False,
            message=f"Payment verification pending: {verification.error or 'Awaiting confirmation'}",
            payment_id=str(payment.id),
            payment_status=payment.status,
            verified_on_chain=False,
        )

    async def _verify_blockchain_payment(
        self,
        transaction_hash: str,
        network: str,
        expected_amount: int,
        expected_memo: str,
    ) -> TransactionVerification:
        """Verify payment on blockchain using appropriate service."""
        service = PaymentServiceFactory.get_service(network)

        if not service:
            logger.warning(f"No payment service for network: {network}")
            return TransactionVerification(
                verified=False,
                transaction_hash=transaction_hash,
                network=network,
                error=f"Network not supported: {network}",
            )

        # Get recipient based on network
        if network == "ethereum":
            recipient = self.eth_recipient
        else:
            recipient = self.recipient_address

        return await service.verify_transaction(
            transaction_hash=transaction_hash,
            expected_amount=expected_amount,
            expected_recipient=recipient,
            expected_memo=expected_memo,
        )

    # =========================================================================
    # SUBSCRIPTION ACTIVATION
    # =========================================================================

    async def _activate_subscription(
        self,
        user: User,
        tier: str,
        billing_cycle: str,
        payment: Payment,
    ) -> Subscription:
        """Create or update user's subscription."""
        # Calculate period
        if billing_cycle == "yearly":
            period_end = datetime.now(UTC) + timedelta(days=365)
        else:
            period_end = datetime.now(UTC) + timedelta(days=30)

        # Find existing subscription
        result = await self.session.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.tier = tier
            subscription.status = "active"
            subscription.current_period_start = datetime.now(UTC)
            subscription.current_period_end = period_end
            subscription.updated_at = datetime.now(UTC)
        else:
            subscription = Subscription(
                user_id=user.id,
                tier=tier,
                status="active",
                current_period_start=datetime.now(UTC),
                current_period_end=period_end,
            )
            self.session.add(subscription)

        # Link payment to subscription
        await self.session.flush()
        payment.subscription_id = subscription.id

        return subscription

    # =========================================================================
    # PAYMENT QUERIES
    # =========================================================================

    async def _get_user_payment(
        self,
        payment_id: UUID,
        user_id: UUID,
    ) -> Payment | None:
        """Get a payment by ID for a specific user."""
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id).where(Payment.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_payment(
        self,
        payment_id: UUID,
        user: User,
    ) -> PaymentInfo | None:
        """Get payment info for display."""
        payment = await self._get_user_payment(payment_id, user.id)
        if not payment:
            return None

        return PaymentInfo(
            id=str(payment.id),
            amount=payment.amount,
            status=payment.status,
            payment_type=payment.payment_type,
            created_at=payment.created_at,
            transaction_hash=payment.txid,
        )

    async def get_payment_history(
        self,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PaymentInfo]:
        """Get user's payment history."""
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        payments = result.scalars().all()

        return [
            PaymentInfo(
                id=str(p.id),
                amount=p.amount,
                status=p.status,
                payment_type=p.payment_type,
                created_at=p.created_at,
                transaction_hash=p.txid,
            )
            for p in payments
        ]

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_payment_metadata(self, payment: Payment) -> dict:
        """Extract metadata from payment record."""
        if hasattr(payment, "get_metadata") and callable(payment.get_metadata):
            metadata = payment.get_metadata()
            if metadata:
                return metadata

        if payment.metadata_json:
            try:
                return json.loads(payment.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {}

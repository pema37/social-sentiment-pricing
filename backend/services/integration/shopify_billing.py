"""
Shopify Billing Service

Handles all Shopify Billing API interactions via GraphQL Admin API.
Creates recurring subscriptions, processes billing callbacks,
handles plan upgrades/downgrades, and cancellations.

Flow:
  1. App calls create_subscription() → gets confirmationUrl
  2. Merchant is redirected to Shopify to approve charge
  3. Shopify redirects back to our returnUrl with charge_id
  4. We call verify_subscription() to confirm status is ACTIVE
  5. We update our local Subscription model

Ref: https://shopify.dev/docs/apps/launch/billing/subscription-billing
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from core.encryption import decrypt_token
from models.integration import EcommercePlatform, Integration, IntegrationStatus
from models.subscription import Subscription
from schemas.shopify_billing import (
    SHOPIFY_PLANS,
    ShopifyBillingStatusResponse,
    ShopifyCancelResponse,
    ShopifySubscribeResponse,
)
from services.integration.http_client import RetryableClient
from services.integration.retry import RetryConfig
from services.integration.shopify_service import ShopifyService

logger = logging.getLogger(__name__)


# =============================================================================
# GraphQL Mutations & Queries
# =============================================================================

CREATE_SUBSCRIPTION_MUTATION = """
mutation AppSubscriptionCreate(
  $name: String!,
  $lineItems: [AppSubscriptionLineItemInput!]!,
  $returnUrl: URL!,
  $test: Boolean,
  $trialDays: Int,
  $replacementBehavior: AppSubscriptionReplacementBehavior
) {
  appSubscriptionCreate(
    name: $name,
    returnUrl: $returnUrl,
    lineItems: $lineItems,
    test: $test,
    trialDays: $trialDays,
    replacementBehavior: $replacementBehavior
  ) {
    userErrors {
      field
      message
    }
    appSubscription {
      id
      name
      status
      trialDays
      test
      currentPeriodEnd
      createdAt
    }
    confirmationUrl
  }
}
"""

CANCEL_SUBSCRIPTION_MUTATION = """
mutation AppSubscriptionCancel($id: ID!, $prorate: Boolean) {
  appSubscriptionCancel(id: $id, prorate: $prorate) {
    userErrors {
      field
      message
    }
    appSubscription {
      id
      status
    }
  }
}
"""

CHECK_SUBSCRIPTION_QUERY = """
query CheckSubscription($id: ID!) {
  node(id: $id) {
    ... on AppSubscription {
      id
      name
      status
      createdAt
      currentPeriodEnd
      test
      trialDays
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppRecurringPricing {
              interval
              price { amount currencyCode }
            }
          }
        }
      }
    }
  }
}
"""

ACTIVE_SUBSCRIPTIONS_QUERY = """
query {
  currentAppInstallation {
    activeSubscriptions {
      id
      name
      status
      test
      trialDays
      currentPeriodEnd
      createdAt
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppRecurringPricing {
              interval
              price { amount currencyCode }
            }
          }
        }
      }
    }
  }
}
"""


class ShopifyBillingService:
    """
    Service for managing Shopify app subscriptions via the Billing API.

    Uses ShopifyService's _graphql() method for all GraphQL calls,
    maintaining consistent retry, rate limiting, and circuit breaker behavior.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.shopify = ShopifyService()
        self._is_test = settings.ENVIRONMENT != "production"

    # =========================================================================
    # HELPERS — Integration Lookup & Token Decryption
    # =========================================================================

    async def _get_shopify_integration(
        self, user_id: UUID | None = None, shop_domain: str | None = None
    ) -> Integration | None:
        """
        Find the active Shopify integration for a user or shop domain.
        Tries shop_domain first (for embedded/install flows), then user_id.
        """
        if shop_domain:
            stmt = select(Integration).where(
                Integration.platform == EcommercePlatform.SHOPIFY,
                Integration.store_url == shop_domain,
                Integration.status == IntegrationStatus.ACTIVE,
            )
            result = await self.session.execute(stmt)
            integration = result.scalars().first()
            if integration:
                return integration

        if user_id:
            stmt = select(Integration).where(
                Integration.user_id == user_id,
                Integration.platform == EcommercePlatform.SHOPIFY,
                Integration.status == IntegrationStatus.ACTIVE,
            )
            result = await self.session.execute(stmt)
            return result.scalars().first()

        return None

    def _get_access_token(self, integration: Integration) -> str:
        """Decrypt the stored access token."""
        return decrypt_token(integration.access_token_encrypted)

    def _get_shop_domain(self, integration: Integration) -> str:
        """Get clean shop domain from integration."""
        return self.shopify._get_shop_domain(integration.store_url)

    def _build_return_url(self, shop_domain: str) -> str:
        """Build the billing callback URL that Shopify redirects to after approval."""
        return f"{settings.BACKEND_URL}/api/v1/integrations/shopify/billing/callback?shop={shop_domain}"

    def _tier_from_plan_name(self, plan_name: str) -> str | None:
        """Extract our tier from the Shopify plan name."""
        for tier, plan in SHOPIFY_PLANS.items():
            if plan.name == plan_name:
                return tier
        # Fallback: check if tier name is in the plan name
        plan_lower = plan_name.lower()
        for tier in SHOPIFY_PLANS:
            if tier in plan_lower:
                return tier
        return None

    # =========================================================================
    # CREATE SUBSCRIPTION
    # =========================================================================

    async def create_subscription(
        self,
        tier: str,
        user_id: UUID | None = None,
        shop_domain: str | None = None,
    ) -> ShopifySubscribeResponse:
        """
        Create a Shopify recurring subscription for a merchant.

        1. Look up the Integration (access token + shop domain)
        2. Call appSubscriptionCreate GraphQL mutation
        3. Return the confirmationUrl for merchant approval
        4. Store the pending Shopify subscription ID locally

        Args:
            tier: Plan tier (starter, professional, enterprise)
            user_id: User ID (for authenticated flows)
            shop_domain: Shop domain (for embedded/install flows)

        Returns:
            ShopifySubscribeResponse with confirmationUrl
        """
        # Validate tier
        plan_config = SHOPIFY_PLANS.get(tier)
        if not plan_config:
            return ShopifySubscribeResponse(
                success=False,
                tier=tier,
                message=f"Invalid tier: {tier}. Must be one of: {list(SHOPIFY_PLANS.keys())}",
            )

        # Find integration
        integration = await self._get_shopify_integration(user_id, shop_domain)
        if not integration:
            return ShopifySubscribeResponse(
                success=False,
                tier=tier,
                message="No active Shopify integration found. Please install the app first.",
            )

        access_token = self._get_access_token(integration)
        shop = self._get_shop_domain(integration)
        return_url = self._build_return_url(shop)

        # Build GraphQL variables
        variables = {
            "name": plan_config.name,
            "returnUrl": return_url,
            "test": self._is_test,
            "trialDays": plan_config.trial_days,
            "replacementBehavior": "APPLY_IMMEDIATELY",
            "lineItems": [
                {
                    "plan": {
                        "appRecurringPricingDetails": {
                            "price": {
                                "amount": plan_config.price_amount,
                                "currencyCode": plan_config.currency_code,
                            },
                            "interval": plan_config.interval,
                        }
                    }
                }
            ],
        }

        try:
            async with RetryableClient(shop, "shopify", RetryConfig(max_retries=2), 15.0) as rc:
                data = await self.shopify._graphql(
                    rc,
                    shop,
                    access_token,
                    CREATE_SUBSCRIPTION_MUTATION,
                    variables,
                )

            result = data.get("appSubscriptionCreate", {})
            user_errors = result.get("userErrors", [])

            if user_errors:
                error_msgs = "; ".join(e.get("message", "") for e in user_errors)
                logger.error(f"Shopify billing error for {shop}: {error_msgs}")
                return ShopifySubscribeResponse(
                    success=False,
                    tier=tier,
                    message=f"Shopify billing error: {error_msgs}",
                )

            confirmation_url = result.get("confirmationUrl")
            subscription_data = result.get("appSubscription", {})
            shopify_sub_id = subscription_data.get("id")

            if not confirmation_url:
                return ShopifySubscribeResponse(
                    success=False,
                    tier=tier,
                    message="No confirmation URL returned from Shopify.",
                )

            # Store pending subscription info in integration settings
            integration.settings = {
                **(integration.settings or {}),
                "pending_shopify_subscription_id": shopify_sub_id,
                "pending_tier": tier,
            }
            integration.updated_at = datetime.now(UTC)
            self.session.add(integration)
            await self.session.commit()

            logger.info(
                f"Created Shopify subscription for {shop}: tier={tier}, sub_id={shopify_sub_id}, test={self._is_test}"
            )

            return ShopifySubscribeResponse(
                success=True,
                confirmation_url=confirmation_url,
                shopify_subscription_id=shopify_sub_id,
                tier=tier,
                message="Redirect merchant to confirmation URL to approve the charge.",
            )

        except Exception as e:
            logger.exception(f"Failed to create Shopify subscription for {shop}: {e}")
            return ShopifySubscribeResponse(
                success=False,
                tier=tier,
                message=f"Failed to create subscription: {e!s}",
            )

    # =========================================================================
    # VERIFY SUBSCRIPTION (after merchant approves)
    # =========================================================================

    async def verify_subscription(
        self,
        charge_id: str,
        shop_domain: str,
    ) -> tuple[bool, str | None, str | None]:
        """
        Verify a subscription after the merchant approves the charge.

        Called from the billing callback endpoint when Shopify redirects
        back with ?charge_id=xxx.

        Args:
            charge_id: Numeric charge ID from the callback URL
            shop_domain: Shop domain

        Returns:
            Tuple of (is_active, tier, shopify_subscription_gid)
        """
        integration = await self._get_shopify_integration(shop_domain=shop_domain)
        if not integration:
            logger.error(f"No integration found for {shop_domain} during billing callback")
            return False, None, None

        access_token = self._get_access_token(integration)
        shop = self._get_shop_domain(integration)
        gid = f"gid://shopify/AppSubscription/{charge_id}"

        try:
            async with RetryableClient(shop, "shopify", RetryConfig(max_retries=2), 15.0) as rc:
                data = await self.shopify._graphql(
                    rc,
                    shop,
                    access_token,
                    CHECK_SUBSCRIPTION_QUERY,
                    {"id": gid},
                )

            node = data.get("node", {})
            status = node.get("status", "").upper()
            plan_name = node.get("name", "")
            tier = self._tier_from_plan_name(plan_name)

            # Also check pending tier from integration settings
            if not tier:
                tier = (integration.settings or {}).get("pending_tier")

            logger.info(f"Subscription verification for {shop}: charge_id={charge_id}, status={status}, tier={tier}")

            if status == "ACTIVE":
                # Update local subscription
                await self._activate_local_subscription(
                    integration=integration,
                    tier=tier or "starter",
                    shopify_subscription_id=gid,
                    plan_name=plan_name,
                    is_test=node.get("test", False),
                    trial_days=node.get("trialDays"),
                    current_period_end=node.get("currentPeriodEnd"),
                )
                return True, tier, gid

            return False, tier, gid

        except Exception as e:
            logger.exception(f"Failed to verify subscription for {shop}: {e}")
            return False, None, None

    # =========================================================================
    # CHECK ACTIVE SUBSCRIPTION STATUS
    # =========================================================================

    async def get_subscription_status(
        self,
        user_id: UUID | None = None,
        shop_domain: str | None = None,
    ) -> ShopifyBillingStatusResponse:
        """
        Check the current active subscription status from Shopify.
        Uses currentAppInstallation query for authoritative status.
        """
        integration = await self._get_shopify_integration(user_id, shop_domain)
        if not integration:
            return ShopifyBillingStatusResponse(has_active_subscription=False)

        access_token = self._get_access_token(integration)
        shop = self._get_shop_domain(integration)

        try:
            async with RetryableClient(shop, "shopify", RetryConfig(max_retries=2), 15.0) as rc:
                data = await self.shopify._graphql(
                    rc,
                    shop,
                    access_token,
                    ACTIVE_SUBSCRIPTIONS_QUERY,
                )

            active_subs = data.get("currentAppInstallation", {}).get("activeSubscriptions", [])

            if not active_subs:
                return ShopifyBillingStatusResponse(has_active_subscription=False)

            # Take the first (should only be one per app)
            sub = active_subs[0]
            plan_name = sub.get("name", "")
            tier = self._tier_from_plan_name(plan_name)

            # Extract price from line items
            price = None
            currency = None
            line_items = sub.get("lineItems", [])
            if line_items:
                pricing = line_items[0].get("plan", {}).get("pricingDetails", {})
                if pricing.get("__typename") == "AppRecurringPricing":
                    price_info = pricing.get("price", {})
                    price = price_info.get("amount")
                    currency = price_info.get("currencyCode")

            return ShopifyBillingStatusResponse(
                has_active_subscription=True,
                tier=tier,
                plan_name=plan_name,
                status=sub.get("status", "").lower(),
                shopify_subscription_id=sub.get("id"),
                trial_days=sub.get("trialDays"),
                current_period_end=sub.get("currentPeriodEnd"),
                test=sub.get("test", False),
                price=price,
                currency=currency,
            )

        except Exception as e:
            logger.exception(f"Failed to check subscription status for {shop}: {e}")
            return ShopifyBillingStatusResponse(has_active_subscription=False)

    # =========================================================================
    # CANCEL SUBSCRIPTION
    # =========================================================================

    async def cancel_subscription(
        self,
        prorate: bool = True,
        user_id: UUID | None = None,
        shop_domain: str | None = None,
    ) -> ShopifyCancelResponse:
        """
        Cancel the active Shopify subscription.
        """
        # First get the current active subscription ID from Shopify
        status = await self.get_subscription_status(user_id, shop_domain)
        if not status.has_active_subscription or not status.shopify_subscription_id:
            return ShopifyCancelResponse(
                success=False,
                message="No active Shopify subscription to cancel.",
            )

        integration = await self._get_shopify_integration(user_id, shop_domain)
        if not integration:
            return ShopifyCancelResponse(
                success=False,
                message="No active Shopify integration found.",
            )

        access_token = self._get_access_token(integration)
        shop = self._get_shop_domain(integration)

        try:
            async with RetryableClient(shop, "shopify", RetryConfig(max_retries=2), 15.0) as rc:
                data = await self.shopify._graphql(
                    rc,
                    shop,
                    access_token,
                    CANCEL_SUBSCRIPTION_MUTATION,
                    {
                        "id": status.shopify_subscription_id,
                        "prorate": prorate,
                    },
                )

            result = data.get("appSubscriptionCancel", {})
            user_errors = result.get("userErrors", [])

            if user_errors:
                error_msgs = "; ".join(e.get("message", "") for e in user_errors)
                return ShopifyCancelResponse(
                    success=False,
                    message=f"Shopify error: {error_msgs}",
                )

            cancelled_status = result.get("appSubscription", {}).get("status", "").lower()

            # Downgrade local subscription to free
            await self._downgrade_local_subscription(integration)

            logger.info(f"Cancelled Shopify subscription for {shop}")

            return ShopifyCancelResponse(
                success=True,
                message="Subscription cancelled successfully.",
                status=cancelled_status,
            )

        except Exception as e:
            logger.exception(f"Failed to cancel subscription for {shop}: {e}")
            return ShopifyCancelResponse(
                success=False,
                message=f"Failed to cancel: {e!s}",
            )

    # =========================================================================
    # LOCAL SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def _activate_local_subscription(
        self,
        integration: Integration,
        tier: str,
        shopify_subscription_id: str,
        plan_name: str,
        is_test: bool = False,
        trial_days: int | None = None,
        current_period_end: str | None = None,
    ) -> Subscription | None:
        """
        Create or update the local Subscription record after Shopify approval.
        """
        user_id = integration.user_id
        if not user_id:
            logger.warning(f"Integration {integration.id} has no user_id — cannot create local subscription")
            return None

        plan_config = SHOPIFY_PLANS.get(tier)
        price = plan_config.price_amount if plan_config else "0.00"

        # Find or create subscription
        result = await self.session.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if subscription:
            subscription.tier = tier
            subscription.status = "active"
            subscription.monthly_price = price
            subscription.shopify_charge_id = shopify_subscription_id
            subscription.shopify_plan_name = plan_name
            subscription.current_period_start = now
            if current_period_end:
                try:
                    subscription.current_period_end = datetime.fromisoformat(current_period_end.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    subscription.current_period_end = None
            subscription.cancel_at_period_end = False
            subscription.cancelled_at = None
            subscription.updated_at = now
        else:
            subscription = Subscription(
                user_id=user_id,
                tier=tier,
                status="active",
                monthly_price=price,
                shopify_charge_id=shopify_subscription_id,
                shopify_plan_name=plan_name,
                current_period_start=now,
            )
            if current_period_end:
                try:
                    subscription.current_period_end = datetime.fromisoformat(current_period_end.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            self.session.add(subscription)

        # Clear pending info from integration settings
        if integration.settings:
            integration.settings.pop("pending_shopify_subscription_id", None)
            integration.settings.pop("pending_tier", None)
            integration.updated_at = now
            self.session.add(integration)

        await self.session.commit()

        logger.info(
            f"Activated local subscription for user {user_id}: tier={tier}, shopify_id={shopify_subscription_id}"
        )

        return subscription

    async def _downgrade_local_subscription(self, integration: Integration) -> None:
        """Downgrade local subscription to free after Shopify cancellation."""
        if not integration.user_id:
            return

        result = await self.session.execute(select(Subscription).where(Subscription.user_id == integration.user_id))
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.tier = "free"
            subscription.status = "active"
            subscription.monthly_price = "0.00"
            subscription.shopify_charge_id = None
            subscription.shopify_plan_name = None
            subscription.cancelled_at = datetime.now(UTC)
            subscription.updated_at = datetime.now(UTC)
            self.session.add(subscription)
            await self.session.commit()

            logger.info(f"Downgraded local subscription to free for user {integration.user_id}")

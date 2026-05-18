"""
Integration tests for the boss bug:
ApprovalService.auto_approve_and_apply() must be idempotent and must not
push to Shopify twice for the same logical decision.

These tests intentionally fail on the current (pre-repair) code to
reproduce the production bug deterministically. Once the repair is
in place, they go green and stay green forever.

Run with:
    cd backend
    pytest tests/integration/test_price_apply_idempotency.py -v

The tests use:
- in-memory SQLite for speed (the bugs reproduce equally well there)
- AsyncMock at the EcommerceService boundary (no live Shopify needed)
- real ApprovalService + real EcommercePushService (the code under test)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

# Bring all models into SQLModel.metadata so create_all() builds the schema.
# Order doesn't matter for in-memory SQLite. If any of these imports fail,
# you'll see it immediately at collection time — that's a different bug.
import models.user  # noqa: F401
import models.product  # noqa: F401
import models.price_recommendation  # noqa: F401
import models.price_history  # noqa: F401
import models.pricing_settings  # noqa: F401
import models.integration  # noqa: F401

from models.product import Product
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.user import User

from services.pricing.approval_service import ApprovalError, ApprovalService
from services.integration.schemas import PriceUpdateResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine():
    """Fresh in-memory SQLite per test. No persistence between tests."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    """One AsyncSession per test."""
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def fixture_user(db: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:8]}@example.com",
        username=f"test-{uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def fixture_product(db: AsyncSession, fixture_user: User) -> Product:
    """A product with a current_price ready to be updated."""
    p = Product(
        id=uuid4(),
        user_id=fixture_user.id,
        name="Test Serum 30ml",
        sku=f"SKU-{uuid4().hex[:8]}",
        current_price=Decimal("49.99"),
        cost=Decimal("15.00"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest_asyncio.fixture
async def pending_recommendation(
    db: AsyncSession, fixture_user: User, fixture_product: Product
) -> PriceRecommendation:
    """A PENDING recommendation ready to be approved + applied."""
    r = PriceRecommendation(
        id=uuid4(),
        user_id=fixture_user.id,
        product_id=fixture_product.id,
        current_price=fixture_product.current_price,
        recommended_price=Decimal("59.99"),
        change_percent=Decimal("20.00"),
        confidence_score=Decimal("0.95"),
        status=RecommendationStatus.PENDING,
        valid_until=datetime.now(UTC) + timedelta(days=1),
        created_at=datetime.now(UTC),
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


@pytest.fixture
def mock_shopify_success():
    """
    Patches EcommercePushService._push_to_platform to simulate a successful
    Shopify push WITHOUT calling the network. Returns the mock so the test
    can assert call counts.

    We patch _push_to_platform (the internal method that actually invokes
    ShopifyService) rather than push_price (the orchestrator) so that the
    DB metadata-update logic in push_price still runs. This is what real
    production calls do; mocking too high gives us a false-green.
    """
    async def fake_push(self, product, link):
        return {
            "platform": "shopify",
            "success": True,
            "external_id": "gid://shopify/Product/123",
            "external_variant_id": "gid://shopify/ProductVariant/456",
            "new_price": float(product.current_price),
            "old_price": 49.99,
        }

    with patch(
        "services.pricing.ecommerce_push_service.EcommercePushService._push_to_platform",
        new=AsyncMock(side_effect=fake_push, autospec=True),
    ) as m:
        yield m


# ---------------------------------------------------------------------------
# Helper: create an ACTIVE Shopify integration link so push_price has
# something to iterate over. Without a link, push_price returns
# NO_ACTIVE_INTEGRATION_LINK and the bug never reproduces.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def active_shopify_link(db: AsyncSession, fixture_user: User, fixture_product: Product):
    from models.integration import (
        EcommercePlatform,
        Integration,
        IntegrationStatus,
        ProductIntegrationLink,
    )

    integ = Integration(
        id=uuid4(),
        user_id=fixture_user.id,
        platform=EcommercePlatform.SHOPIFY,
        store_url="test-store.myshopify.com",
        status=IntegrationStatus.ACTIVE,
        access_token_encrypted=b"fake-encrypted-token",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(integ)
    await db.commit()
    await db.refresh(integ)

    link = ProductIntegrationLink(
        id=uuid4(),
        product_id=fixture_product.id,
        integration_id=integ.id,
        external_product_id="gid://shopify/Product/123",
        external_variant_id="gid://shopify/ProductVariant/456",
        sync_enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    # Decrypt is mocked so we don't need a real Fernet key in tests
    with patch(
        "services.pricing.ecommerce_push_service.decrypt_token",
        return_value="shpua_fake_token",
    ):
        yield link


# ---------------------------------------------------------------------------
# TEST 1 — Concurrent double-click
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_apply_pushes_to_shopify_only_once(
    db: AsyncSession,
    fixture_user: User,
    pending_recommendation: PriceRecommendation,
    active_shopify_link,
    mock_shopify_success,
):
    """
    THE BOSS BUG.

    Two concurrent calls to auto_approve_and_apply() for the same
    recommendation. Real production scenario: David double-clicks the
    Approve button, or the frontend's useMutation retries on a 503,
    or two Celery workers race after a Railway restart.

    Expected (post-repair):
      - Exactly ONE Shopify push.
      - One call returns the applied recommendation; the other raises
        an INVALID_STATUS or IN_PROGRESS error.
      - Recommendation ends in APPLIED.

    Pre-repair: Shopify mutation fires twice. Test fails with
        AssertionError: assert 2 == 1
    which is the deterministic reproduction of the boss bug.
    """
    service = ApprovalService(db)

    async def attempt():
        try:
            return await service.auto_approve_and_apply(
                pending_recommendation.id, fixture_user.id
            )
        except ApprovalError as e:
            return e

    # Fire both at the same time
    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)

    # CRITICAL ASSERTION: only one Shopify push fired
    assert mock_shopify_success.call_count == 1, (
        f"BOSS BUG: Shopify pushed {mock_shopify_success.call_count} times "
        f"for the same recommendation. Expected exactly 1."
    )

    # One should succeed, one should be a clear error (not silent)
    successes = [r for r in results if isinstance(r, PriceRecommendation)]
    errors = [r for r in results if isinstance(r, ApprovalError)]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"

    # Verify final state in the DB
    await db.refresh(pending_recommendation)
    assert pending_recommendation.status == RecommendationStatus.APPLIED


# ---------------------------------------------------------------------------
# TEST 2 — DB commit failure after successful Shopify push
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_commit_failure_after_shopify_push_does_not_double_push_on_retry(
    db: AsyncSession,
    fixture_user: User,
    pending_recommendation: PriceRecommendation,
    active_shopify_link,
    mock_shopify_success,
):
    """
    The two-phase-commit failure mode.

    Sequence:
      1. push_price() succeeds (Shopify has the new price).
      2. db.commit() fails (network blip to Neon, deadlock).
      3. The caller (or Celery) retries auto_approve_and_apply().

    Expected (post-repair):
      - Second attempt either returns the cached result without pushing,
        OR fails fast with a clear "already executed" error.
      - In neither case does Shopify get a second mutation.

    Pre-repair: The recommendation is still PENDING (commit failed),
    so the second attempt re-pushes. Shopify count = 2. Test fails.
    """
    service = ApprovalService(db)

    # First attempt: force the final commit to fail
    original_commit = db.commit
    commit_calls = {"count": 0}

    async def flaky_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 1:
            raise RuntimeError("simulated DB commit failure (network blip)")
        return await original_commit()

    with patch.object(db, "commit", side_effect=flaky_commit):
        with pytest.raises(Exception):
            await service.auto_approve_and_apply(
                pending_recommendation.id, fixture_user.id
            )

    # At this point: Shopify pushed once, DB commit failed.
    assert mock_shopify_success.call_count == 1

    # Second attempt — exactly the retry shape that produces the bug today
    try:
        await service.auto_approve_and_apply(
            pending_recommendation.id, fixture_user.id
        )
    except ApprovalError:
        pass  # acceptable: retry detected and refused to re-push

    # CRITICAL ASSERTION
    assert mock_shopify_success.call_count == 1, (
        f"BOSS BUG: retry after DB commit failure produced "
        f"{mock_shopify_success.call_count} Shopify pushes. Expected 1."
    )


# ---------------------------------------------------------------------------
# TEST 3 — Already-APPLIED recommendation cannot be re-applied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_already_applied_recommendation_cannot_push_again(
    db: AsyncSession,
    fixture_user: User,
    pending_recommendation: PriceRecommendation,
    active_shopify_link,
    mock_shopify_success,
):
    """
    Sanity test: once a recommendation is APPLIED, no further push
    is allowed. This already passes on current code (the status guard
    catches it), but we lock it in so a future refactor doesn't
    silently regress.
    """
    service = ApprovalService(db)

    # First apply succeeds
    await service.auto_approve_and_apply(pending_recommendation.id, fixture_user.id)
    assert mock_shopify_success.call_count == 1

    # Second apply must fail without pushing
    with pytest.raises(ApprovalError) as exc_info:
        await service.auto_approve_and_apply(
            pending_recommendation.id, fixture_user.id
        )

    assert exc_info.value.error_code == "INVALID_STATUS"
    assert mock_shopify_success.call_count == 1



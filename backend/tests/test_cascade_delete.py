"""
Tests for services/products/cascade_delete.py

cascade_delete_product — async cascade deletion with dry_run support.
get_deletion_preview — convenience wrapper.
"""

import sys
import types
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from uuid import uuid4

import pytest

# ── Import isolation ──────────────────────────────────────────────
import os as _os
_backend_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

_MOCKED = [
    "sqlalchemy",
    "sqlalchemy.dialects",
    "sqlalchemy.dialects.postgresql",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models",
    "models.user",
    "models.product",
    "models.recommendation_outcome",
    "models.price_recommendation",
    "models.pricing_rule",
    "models.alert",
    "models.price_history",
    "models.sentiment",
    "models.social_mention",
    "models.competitor_product",
    "models.integration",
    "schemas",
    "schemas.alert",
    "services.products",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Packages need __path__ for submodule resolution
_PACKAGES = {
    "sqlalchemy": [],
    "sqlalchemy.dialects": [],
    "sqlalchemy.ext": [],
    "models": [],
    "schemas": [],
    "services.products": [_os.path.join(_backend_dir, "services", "products")],
}

for _m in _MOCKED:
    if _m not in sys.modules:
        stub = types.ModuleType(_m)
        if _m in _PACKAGES:
            stub.__path__ = _PACKAGES[_m]
        sys.modules[_m] = stub

# Provide sqlalchemy.ext.asyncio.AsyncSession
sys.modules["sqlalchemy.ext.asyncio"].AsyncSession = MagicMock()

# Ensure sqlalchemy.delete is a callable mock
_sa = sys.modules["sqlalchemy"]
_sa.delete = MagicMock()
_sa.func = MagicMock()
_sa.select = MagicMock()

# Provide sqlalchemy.dialects.postgresql.UUID
sys.modules["sqlalchemy.dialects.postgresql"].UUID = MagicMock()

# Provide sqlmodel basics
sys.modules["sqlmodel"].SQLModel = MagicMock()
sys.modules["sqlmodel"].Field = MagicMock()

# Wire up models with __tablename__
_model_names = {
    "models.recommendation_outcome": ("RecommendationOutcome", "recommendation_outcomes"),
    "models.price_recommendation": ("PriceRecommendation", "price_recommendations"),
    "models.pricing_rule": ("PricingRule", "pricing_rules"),
    "models.alert": ("Alert", "alerts"),
    "models.price_history": ("PriceHistory", "price_history"),
    "models.sentiment": ("Sentiment", "sentiments"),
    "models.social_mention": ("SocialMention", "social_mentions"),
    "models.competitor_product": ("CompetitorProduct", "competitor_products"),
    "models.integration": ("ProductIntegrationLink", "product_integration_links"),
}

# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for mod_name, (cls_name, table_name) in _model_names.items():
    if mod_name in sys.modules:
        _saved_attrs[(mod_name, cls_name)] = getattr(sys.modules[mod_name], cls_name, _SENTINEL)
    mock_model = MagicMock()
    mock_model.__tablename__ = table_name
    mock_model.product_id = MagicMock()
    setattr(sys.modules[mod_name], cls_name, mock_model)

# Provide real enums on models.alert so Pydantic doesn't choke
from enum import Enum

class _AlertType(str, Enum):
    PRICE_CHANGE = "price_change"
    SENTIMENT_SHIFT = "sentiment_shift"

class _AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class _AlertChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"

class _AlertStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"

for _key, _attr in [
    ("models.alert", "AlertType"),
    ("models.alert", "AlertSeverity"),
    ("models.alert", "AlertChannel"),
    ("models.alert", "AlertStatus"),
    ("models.user", "User"),
    ("models.product", "Product"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)

_alert_mod = sys.modules["models.alert"]
_alert_mod.AlertType = _AlertType
_alert_mod.AlertSeverity = _AlertSeverity
_alert_mod.AlertChannel = _AlertChannel
_alert_mod.AlertStatus = _AlertStatus

# Stub models.user and models.product to prevent __init__.py imports
sys.modules["models.user"].User = MagicMock()
sys.modules["models.product"].Product = MagicMock()

from services.products.cascade_delete import (
    cascade_delete_product,
    get_deletion_preview,
    PRODUCT_DEPENDENCIES,
)

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

# Restore overwritten attributes on pre-existing modules
for (_mod_key, _attr_name), _orig_val in _saved_attrs.items():
    if _mod_key in sys.modules:
        if _orig_val is _SENTINEL:
            try:
                delattr(sys.modules[_mod_key], _attr_name)
            except AttributeError:
                pass
        else:
            setattr(sys.modules[_mod_key], _attr_name, _orig_val)

SVC_MOD = "services.products.cascade_delete"


# ── Helpers ───────────────────────────────────────────────────────

def _make_session(rowcount=0, scalar_value=0):
    """Create a mock AsyncSession."""
    session = AsyncMock()

    # For delete operations
    exec_result = MagicMock()
    exec_result.rowcount = rowcount

    # For count queries (dry_run)
    exec_result.scalar.return_value = scalar_value

    session.execute.return_value = exec_result
    return session


# ──────────────────────────────────────────────
# PRODUCT_DEPENDENCIES constant
# ──────────────────────────────────────────────
class TestProductDependencies:

    def test_is_list(self):
        assert isinstance(PRODUCT_DEPENDENCIES, list)

    def test_has_9_entries(self):
        assert len(PRODUCT_DEPENDENCIES) == 9

    def test_each_entry_is_tuple_of_3(self):
        for entry in PRODUCT_DEPENDENCIES:
            assert len(entry) == 3

    def test_all_fk_columns_are_product_id(self):
        for _, fk_col, _ in PRODUCT_DEPENDENCIES:
            assert fk_col == "product_id"

    def test_all_descriptions_are_strings(self):
        for _, _, desc in PRODUCT_DEPENDENCIES:
            assert isinstance(desc, str)
            assert len(desc) > 0


# ──────────────────────────────────────────────
# cascade_delete_product — delete mode
# ──────────────────────────────────────────────
class TestCascadeDeleteProduct:

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        session = _make_session(rowcount=0)
        result = await cascade_delete_product(session, uuid4())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_calls_execute_for_each_dependency(self):
        session = _make_session(rowcount=0)
        await cascade_delete_product(session, uuid4())
        assert session.execute.call_count == len(PRODUCT_DEPENDENCIES)

    @pytest.mark.asyncio
    async def test_returns_counts_per_table(self):
        session = _make_session(rowcount=5)
        result = await cascade_delete_product(session, uuid4())
        # Each table should have a count
        assert len(result) == len(PRODUCT_DEPENDENCIES)

    @pytest.mark.asyncio
    async def test_rowcount_reflected(self):
        session = _make_session(rowcount=3)
        result = await cascade_delete_product(session, uuid4())
        for count in result.values():
            assert count == 3

    @pytest.mark.asyncio
    async def test_zero_rowcount(self):
        session = _make_session(rowcount=0)
        result = await cascade_delete_product(session, uuid4())
        for count in result.values():
            assert count == 0

    @pytest.mark.asyncio
    async def test_exception_propagates(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await cascade_delete_product(session, uuid4())


# ──────────────────────────────────────────────
# cascade_delete_product — dry_run mode
# ──────────────────────────────────────────────
class TestCascadeDeleteDryRun:

    @pytest.mark.asyncio
    async def test_dry_run_returns_dict(self):
        session = _make_session(scalar_value=10)
        result = await cascade_delete_product(session, uuid4(), dry_run=True)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dry_run_uses_count(self):
        session = _make_session(scalar_value=7)
        result = await cascade_delete_product(session, uuid4(), dry_run=True)
        for count in result.values():
            assert count == 7

    @pytest.mark.asyncio
    async def test_dry_run_scalar_none_becomes_zero(self):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar.return_value = None
        session.execute.return_value = exec_result

        result = await cascade_delete_product(session, uuid4(), dry_run=True)
        for count in result.values():
            assert count == 0

    @pytest.mark.asyncio
    async def test_dry_run_calls_execute(self):
        session = _make_session(scalar_value=0)
        await cascade_delete_product(session, uuid4(), dry_run=True)
        assert session.execute.call_count == len(PRODUCT_DEPENDENCIES)


# ──────────────────────────────────────────────
# get_deletion_preview
# ──────────────────────────────────────────────
class TestGetDeletionPreview:

    @pytest.mark.asyncio
    async def test_returns_dict_structure(self):
        session = _make_session(scalar_value=5)
        pid = uuid4()
        result = await get_deletion_preview(session, pid)

        assert "product_id" in result
        assert "related_records" in result
        assert "total_records" in result

    @pytest.mark.asyncio
    async def test_product_id_is_string(self):
        session = _make_session(scalar_value=0)
        pid = uuid4()
        result = await get_deletion_preview(session, pid)
        assert result["product_id"] == str(pid)

    @pytest.mark.asyncio
    async def test_total_records_sum(self):
        session = _make_session(scalar_value=3)
        result = await get_deletion_preview(session, uuid4())
        expected_total = 3 * len(PRODUCT_DEPENDENCIES)
        assert result["total_records"] == expected_total

    @pytest.mark.asyncio
    async def test_related_records_is_dict(self):
        session = _make_session(scalar_value=0)
        result = await get_deletion_preview(session, uuid4())
        assert isinstance(result["related_records"], dict)

    @pytest.mark.asyncio
    async def test_calls_dry_run(self):
        with patch(f"{SVC_MOD}.cascade_delete_product", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = {"table_a": 5}
            pid = uuid4()
            session = AsyncMock()

            result = await get_deletion_preview(session, pid)

            mock_fn.assert_called_once_with(session, pid, dry_run=True)
            assert result["total_records"] == 5


            
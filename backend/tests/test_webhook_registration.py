"""
Tests for services/integration/webhook_registration.py — WebhookRegistrationService

Covers:
- __init__: session, services stored
- _get_callback_url: Shopify, WooCommerce, unsupported platform
- _get_service: Shopify, WooCommerce, unsupported
- register_webhooks: lookup, active check, registers, stores webhook IDs, commit,
  not found, inactive integration
- unregister_webhooks: unregisters, clears IDs, not found, no webhook IDs,
  decrypt failure
- verify_webhooks: returns status dict, not found
- Helper functions: register_webhooks_for_integration, unregister_webhooks_for_integration
"""

import sys
import os
from types import ModuleType
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "models.integration",
    "core.config", "core.encryption",
    "services.integration.schemas",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
    "sqlmodel",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Ensure db.session stub
for _m in ("db.session"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Compute real filesystem paths
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure parent packages with real paths
for _pkg, _subdir in [
    ("services", "services"),
    ("services.integration", "services/integration"),
    ("models", "models"),
    ("core", "core"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod


# --- Stub enums ---
class _FakeEcommercePlatform:
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"

    @property
    def value(self):
        return self


class _FakeIntegrationStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class _FakeIntegration:
    id = MagicMock()
    status = MagicMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_integration_mod = ModuleType("models.integration")
_integration_mod.Integration = _FakeIntegration
_integration_mod.IntegrationStatus = _FakeIntegrationStatus
_integration_mod.EcommercePlatform = _FakeEcommercePlatform
sys.modules["models.integration"] = _integration_mod

# --- Stub core.config ---
_config_stub = ModuleType("core.config")
_fake_settings = MagicMock()
_fake_settings.BACKEND_URL = "https://api.actualprice.com"
_config_stub.settings = _fake_settings
sys.modules["core.config"] = _config_stub

# --- Stub core.encryption ---
_encryption_stub = ModuleType("core.encryption")
_encryption_stub.decrypt_token = MagicMock(return_value="decrypted-token-123")
sys.modules["core.encryption"] = _encryption_stub

# --- Stub schemas ---
_schemas_stub = ModuleType("services.integration.schemas")


class _FakeWebhookRegistration:
    def __init__(self, **kw):
        self.success = kw.get("success", True)
        self.webhook_id = kw.get("webhook_id", None)
        self.topic = kw.get("topic", "products/update")
        self.error = kw.get("error", None)


_schemas_stub.WebhookRegistration = _FakeWebhookRegistration
sys.modules["services.integration.schemas"] = _schemas_stub

# --- Stub shopify/woo services ---
_shopify_stub = ModuleType("services.integration.shopify_service")
_fake_shopify = MagicMock()
_fake_shopify.register_webhooks = AsyncMock(return_value=[])
_fake_shopify.unregister_webhooks = AsyncMock(return_value=True)
_shopify_stub.ShopifyService = MagicMock(return_value=_fake_shopify)
sys.modules["services.integration.shopify_service"] = _shopify_stub

_woo_stub = ModuleType("services.integration.woocommerce_service")
_fake_woo = MagicMock()
_fake_woo.register_webhooks = AsyncMock(return_value=[])
_fake_woo.unregister_webhooks = AsyncMock(return_value=True)
_woo_stub.WooCommerceService = MagicMock(return_value=_fake_woo)
sys.modules["services.integration.woocommerce_service"] = _woo_stub

# --- Stub sqlmodel ---
_sqlmodel_stub = ModuleType("sqlmodel")
_sqlmodel_stub.select = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.integration.webhook_registration import (
    WebhookRegistrationService,
    register_webhooks_for_integration,
    unregister_webhooks_for_integration,
)

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================

def _make_session():
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


def _make_integration(**overrides):
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "platform": _FakeEcommercePlatform.SHOPIFY,
        "status": _FakeIntegrationStatus.ACTIVE,
        "store_url": "https://test-store.myshopify.com",
        "access_token_encrypted": "encrypted-token",
        "webhook_ids": ["wh_1", "wh_2"],
    }
    defaults.update(overrides)
    return _FakeIntegration(**defaults)


def _mock_db_returns_integration(session, integration):
    """Configure session.execute to return the integration via scalars().first()."""
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = integration
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)


def _mock_db_returns_none(session):
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)


# ===========================================================================
# Tests
# ===========================================================================

class TestWebhookRegistrationServiceInit:
    def test_stores_db(self):
        session = _make_session()
        svc = WebhookRegistrationService(session)
        assert svc.db is session

    def test_creates_platform_services(self):
        svc = WebhookRegistrationService(_make_session())
        assert svc._shopify is not None
        assert svc._woocommerce is not None


class TestGetCallbackUrl:
    def test_shopify_url(self):
        svc = WebhookRegistrationService(_make_session())
        iid = uuid4()
        with patch("services.integration.webhook_registration.settings", _fake_settings):
            url = svc._get_callback_url(_FakeEcommercePlatform.SHOPIFY, iid)
        assert f"/api/v1/webhooks/shopify/{iid}" in url
        assert url.startswith("https://api.actualprice.com")

    def test_woocommerce_url(self):
        svc = WebhookRegistrationService(_make_session())
        iid = uuid4()
        with patch("services.integration.webhook_registration.settings", _fake_settings):
            url = svc._get_callback_url(_FakeEcommercePlatform.WOOCOMMERCE, iid)
        assert f"/api/v1/webhooks/woocommerce/{iid}" in url

    def test_unsupported_platform_raises(self):
        svc = WebhookRegistrationService(_make_session())
        with patch("services.integration.webhook_registration.settings", _fake_settings):
            with pytest.raises(ValueError, match="Unsupported platform"):
                svc._get_callback_url("bigcommerce", uuid4())

    def test_strips_trailing_slash(self):
        svc = WebhookRegistrationService(_make_session())
        fake_s = MagicMock()
        fake_s.BACKEND_URL = "https://api.actualprice.com/"
        with patch("services.integration.webhook_registration.settings", fake_s):
            url = svc._get_callback_url(_FakeEcommercePlatform.SHOPIFY, uuid4())
        assert "//api" not in url.replace("https://", "")


class TestGetService:
    def test_shopify(self):
        svc = WebhookRegistrationService(_make_session())
        result = svc._get_service(_FakeEcommercePlatform.SHOPIFY)
        assert result is svc._shopify

    def test_woocommerce(self):
        svc = WebhookRegistrationService(_make_session())
        result = svc._get_service(_FakeEcommercePlatform.WOOCOMMERCE)
        assert result is svc._woocommerce

    def test_unsupported_raises(self):
        svc = WebhookRegistrationService(_make_session())
        with pytest.raises(ValueError, match="Unsupported platform"):
            svc._get_service("bigcommerce")


class TestRegisterWebhooks:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        session = _make_session()
        _mock_db_returns_none(session)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            with pytest.raises(ValueError, match="not found"):
                await svc.register_webhooks(uuid4())

    @pytest.mark.asyncio
    async def test_inactive_raises(self):
        session = _make_session()
        integration = _make_integration(status=_FakeIntegrationStatus.INACTIVE)
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            with pytest.raises(ValueError, match="not active"):
                await svc.register_webhooks(integration.id)

    @pytest.mark.asyncio
    async def test_registers_and_stores_webhook_ids(self):
        session = _make_session()
        integration = _make_integration()
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        webhook_results = [
            _FakeWebhookRegistration(success=True, webhook_id="wh_new_1", topic="products/update"),
            _FakeWebhookRegistration(success=True, webhook_id="wh_new_2", topic="orders/create"),
            _FakeWebhookRegistration(success=False, webhook_id=None, topic="products/delete", error="403"),
        ]

        svc._get_service = MagicMock(return_value=MagicMock(
            register_webhooks=AsyncMock(return_value=webhook_results)
        ))

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.decrypt_token", return_value="tok"):
                with patch("services.integration.webhook_registration.settings", _fake_settings):
                    results = await svc.register_webhooks(integration.id)

        assert len(results) == 3
        assert integration.webhook_ids == ["wh_new_1", "wh_new_2"]
        session.add.assert_called_with(integration)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_successful_webhooks_skips_commit(self):
        session = _make_session()
        integration = _make_integration()
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        webhook_results = [
            _FakeWebhookRegistration(success=False, webhook_id=None, topic="products/update", error="500"),
        ]

        svc._get_service = MagicMock(return_value=MagicMock(
            register_webhooks=AsyncMock(return_value=webhook_results)
        ))

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.decrypt_token", return_value="tok"):
                with patch("services.integration.webhook_registration.settings", _fake_settings):
                    results = await svc.register_webhooks(integration.id)

        assert len(results) == 1
        # No webhook IDs to store, so no commit
        session.commit.assert_not_awaited()


class TestUnregisterWebhooks:
    @pytest.mark.asyncio
    async def test_not_found_returns_false(self):
        session = _make_session()
        _mock_db_returns_none(session)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            result = await svc.unregister_webhooks(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_no_webhook_ids_returns_true(self):
        session = _make_session()
        integration = _make_integration(webhook_ids=[])
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            result = await svc.unregister_webhooks(integration.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_successful_unregister(self):
        session = _make_session()
        integration = _make_integration(webhook_ids=["wh_1", "wh_2"])
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        mock_service = MagicMock()
        mock_service.unregister_webhooks = AsyncMock(return_value=True)
        svc._get_service = MagicMock(return_value=mock_service)

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.decrypt_token", return_value="tok"):
                result = await svc.unregister_webhooks(integration.id)

        assert result is True
        assert integration.webhook_ids == []
        session.add.assert_called_with(integration)
        session.commit.assert_awaited_once()
        mock_service.unregister_webhooks.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_unregister_returns_false(self):
        session = _make_session()
        integration = _make_integration(webhook_ids=["wh_1"])
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        mock_service = MagicMock()
        mock_service.unregister_webhooks = AsyncMock(return_value=False)
        svc._get_service = MagicMock(return_value=mock_service)

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.decrypt_token", return_value="tok"):
                result = await svc.unregister_webhooks(integration.id)

        assert result is False
        # Should still clear webhook IDs and commit
        assert integration.webhook_ids == []
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_decrypt_failure_returns_false(self):
        session = _make_session()
        integration = _make_integration(webhook_ids=["wh_1"])
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.decrypt_token",
                        side_effect=Exception("decrypt failed")):
                result = await svc.unregister_webhooks(integration.id)

        assert result is False


class TestVerifyWebhooks:
    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_session()
        _mock_db_returns_none(session)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            result = await svc.verify_webhooks(uuid4())
        assert result["status"] == "error"
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_status_dict(self):
        session = _make_session()
        iid = uuid4()
        integration = _make_integration(
            id=iid,
            store_url="https://test.myshopify.com",
            webhook_ids=["wh_1", "wh_2"],
        )
        # Make platform have a .value attribute
        integration.platform = MagicMock()
        integration.platform.value = "shopify"
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.settings", _fake_settings):
                # Need _get_callback_url to work with the mock platform
                svc._get_callback_url = MagicMock(return_value="https://api.actualprice.com/api/v1/webhooks/shopify/" + str(iid))
                result = await svc.verify_webhooks(iid)

        assert result["status"] == "ok"
        assert result["integration_id"] == str(iid)
        assert result["store_url"] == "https://test.myshopify.com"
        assert result["webhook_count"] == 2
        assert result["webhook_ids"] == ["wh_1", "wh_2"]

    @pytest.mark.asyncio
    async def test_no_webhooks(self):
        session = _make_session()
        integration = _make_integration(webhook_ids=[])
        integration.platform = MagicMock()
        integration.platform.value = "shopify"
        _mock_db_returns_integration(session, integration)
        svc = WebhookRegistrationService(session)

        with patch("services.integration.webhook_registration.select"):
            with patch("services.integration.webhook_registration.settings", _fake_settings):
                svc._get_callback_url = MagicMock(return_value="https://example.com/hook")
                result = await svc.verify_webhooks(integration.id)

        assert result["webhook_count"] == 0


class TestHelperFunctions:
    @pytest.mark.asyncio
    async def test_register_webhooks_for_integration(self):
        session = _make_session()
        iid = uuid4()

        with patch(
            "services.integration.webhook_registration.WebhookRegistrationService"
        ) as MockSvc:
            mock_instance = AsyncMock()
            mock_instance.register_webhooks = AsyncMock(return_value=["result"])
            MockSvc.return_value = mock_instance

            results = await register_webhooks_for_integration(session, iid)

        MockSvc.assert_called_once_with(session)
        mock_instance.register_webhooks.assert_awaited_once_with(iid)
        assert results == ["result"]

    @pytest.mark.asyncio
    async def test_unregister_webhooks_for_integration(self):
        session = _make_session()
        iid = uuid4()

        with patch(
            "services.integration.webhook_registration.WebhookRegistrationService"
        ) as MockSvc:
            mock_instance = AsyncMock()
            mock_instance.unregister_webhooks = AsyncMock(return_value=True)
            MockSvc.return_value = mock_instance

            result = await unregister_webhooks_for_integration(session, iid)

        MockSvc.assert_called_once_with(session)
        mock_instance.unregister_webhooks.assert_awaited_once_with(iid)
        assert result is True



        
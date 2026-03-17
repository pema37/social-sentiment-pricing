#!/usr/bin/env python3
"""
Auto-apply save/restore patches to 5 test files that pollute sys.modules
via attribute overwrites without restoring originals.

Usage: cd backend && python patches/fix_attr_pollution.py

Files patched:
  tests/test_product_sync_handler.py
  tests/test_shopify_service.py
  tests/test_sync_service.py
  tests/test_webhook_handler.py
  tests/test_price_push_service.py

Already fixed (no changes):
  tests/test_http_client.py
  tests/test_webhook_registration.py
"""

import sys
from pathlib import Path

# The restore block appended after existing stub cleanup
RESTORE_BLOCK = """
# Restore overwritten attributes on pre-existing modules
for (_mod_key, _attr_name), _orig_val in _saved_attrs.items():
    if _mod_key in sys.modules:
        if _orig_val is _SENTINEL:
            try:
                delattr(sys.modules[_mod_key], _attr_name)
            except AttributeError:
                pass
        else:
            setattr(sys.modules[_mod_key], _attr_name, _orig_val)"""


def patch_file(filepath: str, save_block: str, save_anchor: str, restore_anchor: str) -> bool:
    """
    Apply a patch to a single file:
    1. Insert save_block BEFORE save_anchor line
    2. Insert RESTORE_BLOCK AFTER restore_anchor line
    """
    p = Path(filepath)
    if not p.exists():
        print(f"  SKIP: {filepath} not found")
        return False

    content = p.read_text()

    # Check if already patched
    if "_saved_attrs" in content:
        print(f"  SKIP: {filepath} already patched")
        return False

    # Insert save block before the anchor
    if save_anchor not in content:
        print(f"  ERROR: save anchor not found in {filepath}")
        print(f"         Looking for: {save_anchor[:80]}...")
        return False

    content = content.replace(save_anchor, save_block + "\n" + save_anchor)

    # Insert restore block after the restore anchor
    if restore_anchor not in content:
        print(f"  ERROR: restore anchor not found in {filepath}")
        print(f"         Looking for: {restore_anchor[:80]}...")
        return False

    content = content.replace(restore_anchor, restore_anchor + RESTORE_BLOCK)

    p.write_text(content)
    print(f"  DONE: {filepath}")
    return True


def main():
    # Verify we're in the backend directory
    if not Path("tests").is_dir():
        print("ERROR: Run from the backend/ directory")
        sys.exit(1)

    patched = 0

    # -----------------------------------------------------------------------
    # 1. test_product_sync_handler.py
    # -----------------------------------------------------------------------
    print("\n[1/5] test_product_sync_handler.py")
    patched += patch_file(
        "tests/test_product_sync_handler.py",
        save_block="""# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "EcommercePlatform"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "ExternalProduct"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.shopify_service", "ShopifyService"),
    ("services.integration.woocommerce_service", "WooCommerceService"),
    ("services.integration.repositories", "ProductRepository"),
    ("services.integration.repositories", "LinkRepository"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)
""",
        save_anchor='sys.modules["models.integration"].Integration = MagicMock',
        restore_anchor="""# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]""",
    )

    # -----------------------------------------------------------------------
    # 2. test_shopify_service.py
    # -----------------------------------------------------------------------
    print("\n[2/5] test_shopify_service.py")
    patched += patch_file(
        "tests/test_shopify_service.py",
        save_block="""# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("core.config", "settings"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.schemas", "OAuthResult"),
    ("services.integration.schemas", "ExternalProduct"),
    ("services.integration.schemas", "ExternalProductVariant"),
    ("services.integration.schemas", "ProductSyncResult"),
    ("services.integration.schemas", "PriceUpdateRequest"),
    ("services.integration.schemas", "PriceUpdateResponse"),
    ("services.integration.schemas", "PriceUpdateResult"),
    ("services.integration.schemas", "WebhookRegistration"),
    ("services.integration.schemas", "ConnectionStatus"),
    ("services.integration.retry", "RetryConfig"),
    ("services.integration.retry", "execute_with_retry"),
    ("services.integration.http_client", "RetryableClient"),
    ("services.integration.circuit_breaker", "CircuitOpenError"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)
""",
        save_anchor="""# Provide settings
_settings = MagicMock()""",
        restore_anchor="""# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]""",
    )

    # -----------------------------------------------------------------------
    # 3. test_sync_service.py
    # -----------------------------------------------------------------------
    print("\n[3/5] test_sync_service.py")
    patched += patch_file(
        "tests/test_sync_service.py",
        save_block="""# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "IntegrationSyncLog"),
    ("models.integration", "ProductIntegrationLink"),
    ("models.integration", "IntegrationStatus"),
    ("models.integration", "EcommercePlatform"),
    ("models.product", "Product"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "ExternalProduct"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.circuit_breaker", "CircuitOpenError"),
    ("services.integration.circuit_breaker", "circuit_breaker_registry"),
    ("services.integration.shopify_service", "ShopifyService"),
    ("services.integration.woocommerce_service", "WooCommerceService"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)
""",
        save_anchor='_integ_mod = sys.modules["models.integration"]',
        restore_anchor="""# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]""",
    )

    # -----------------------------------------------------------------------
    # 4. test_webhook_handler.py
    # -----------------------------------------------------------------------
    print("\n[4/5] test_webhook_handler.py")
    patched += patch_file(
        "tests/test_webhook_handler.py",
        save_block="""# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "IntegrationStatus"),
    ("models.integration", "EcommercePlatform"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.shopify_service", "ShopifyService"),
    ("services.integration.woocommerce_service", "WooCommerceService"),
    ("services.integration.sync_service", "SyncService"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)
""",
        save_anchor="""_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = MagicMock
_integ_mod.IntegrationStatus = _FakeIntegrationStatus
_integ_mod.EcommercePlatform = _FakeEcommercePlatform""",
        restore_anchor="""# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]""",
    )

    # -----------------------------------------------------------------------
    # 5. test_price_push_service.py
    # -----------------------------------------------------------------------
    print("\n[5/5] test_price_push_service.py")
    patched += patch_file(
        "tests/test_price_push_service.py",
        save_block="""# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "ProductIntegrationLink"),
    ("models.integration", "IntegrationStatus"),
    ("models.integration", "EcommercePlatform"),
    ("models.product", "Product"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "PriceUpdateRequest"),
    ("services.integration.models", "PriceUpdateResult"),
    ("services.integration.models", "PriceUpdateResponse"),
    ("services.integration.sync_service", "SyncService"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)
""",
        save_anchor="""_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = _FakeIntegrationModel""",
        restore_anchor="""# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]""",
    )

    # -----------------------------------------------------------------------
    print(f"\n{'=' * 50}")
    print(f"Patched {patched}/5 files")
    if patched == 5:
        print("All done! Run: pytest tests/ -x -q")
    elif patched > 0:
        print("Some files need manual attention (see errors above)")
    else:
        print("No files were patched (already done or errors)")


if __name__ == "__main__":
    main()

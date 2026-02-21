#!/usr/bin/env python3
"""
ActualPrice - Shopify OAuth Flow Verification Test (v2)
========================================================
Tests the complete OAuth flow that Shopify's automated Distribution checks verify.
"""

import httpx
import base64
import json
import time
import ssl
import socket
from urllib.parse import urlparse
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
BACKEND_URL = "https://social-sentiment-pricing-staging-2ecd.up.railway.app"
FRONTEND_URL = "https://ssp-staging.vercel.app"
CALLBACK_PATH = "/api/v1/integrations/oauth/callback"
TEST_SHOP = "demostore.myshopify.com"

results = []

def log_test(name, passed, details="", critical=False):
    status = "✅ PASS" if passed else ("❌ CRITICAL FAIL" if critical else "⚠️  FAIL")
    results.append({"name": name, "passed": passed, "details": details, "critical": critical})
    print(f"\n{status}: {name}")
    if details:
        print(f"   → {details}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# TEST 1: Backend Health
# ============================================================
def test_backend_health():
    section("1. BACKEND HEALTH & REACHABILITY")
    try:
        r = httpx.get(BACKEND_URL, follow_redirects=True, timeout=15)
        log_test("Backend root reachable", r.status_code < 500, f"Status: {r.status_code}")
    except Exception as e:
        log_test("Backend root reachable", False, str(e), critical=True)
        return False

    for path in ["/health", "/api/health", "/api/v1/health"]:
        try:
            r = httpx.get(f"{BACKEND_URL}{path}", timeout=10)
            if r.status_code == 200:
                log_test(f"Health endpoint at {path}", True, f"Response: {r.text[:200]}")
                break
        except:
            continue

    for path in ["/docs", "/api/docs"]:
        try:
            r = httpx.get(f"{BACKEND_URL}{path}", timeout=10)
            if r.status_code == 200:
                log_test(f"API docs at {path}", True)
                break
        except:
            continue
    return True

# ============================================================
# TEST 2: OAuth Initiation
# ============================================================
def test_oauth_initiation():
    section("2. OAUTH INITIATION")

    # Your init is POST /api/v1/integrations/oauth/init (requires auth)
    # This is fine for app-initiated flows.
    # For Shopify App Store installs, the frontend App URL handles it.
    
    try:
        r = httpx.post(
            f"{BACKEND_URL}/api/v1/integrations/oauth/init",
            json={"platform": "shopify", "store_url": TEST_SHOP},
            timeout=15
        )
        # Should get 401 (requires auth) — NOT 404
        log_test("OAuth init endpoint exists (POST /integrations/oauth/init)",
                 r.status_code in [200, 401, 403, 422],
                 f"Status: {r.status_code}" +
                 (" (properly requires auth)" if r.status_code == 401 else ""))
    except Exception as e:
        log_test("OAuth init endpoint", False, str(e), critical=True)

    # Frontend App URL test (what Shopify hits on install)
    print(f"\n  --- Frontend App URL (Shopify Install Entry) ---")
    try:
        r = httpx.get(
            FRONTEND_URL,
            params={"shop": TEST_SHOP, "host": base64.b64encode(TEST_SHOP.encode()).decode()},
            follow_redirects=False,
            timeout=15
        )
        log_test("Frontend App URL responds", r.status_code < 500, f"Status: {r.status_code}")
        if r.status_code in [301, 302, 307, 308]:
            location = r.headers.get("location", "")
            log_test("Frontend redirects on shop param",
                     True, f"Redirects to: {location[:150]}")
    except Exception as e:
        log_test("Frontend App URL", False, str(e))

# ============================================================
# TEST 3: OAuth Callback
# ============================================================
def test_oauth_callback():
    section("3. OAUTH CALLBACK ENDPOINT")
    callback_url = f"{BACKEND_URL}{CALLBACK_PATH}"

    # 3a. Exists?
    try:
        r = httpx.get(callback_url, timeout=15)
        log_test("Callback endpoint exists", r.status_code != 404,
                 f"Status: {r.status_code}", critical=r.status_code == 404)
    except Exception as e:
        log_test("Callback endpoint reachable", False, str(e), critical=True)
        return

    # 3b. Missing params = 422 (not 500)
    try:
        r = httpx.get(callback_url, timeout=15)
        log_test("Handles missing params gracefully",
                 r.status_code in [400, 401, 403, 422],
                 f"Status: {r.status_code}", critical=r.status_code == 500)
    except Exception as e:
        log_test("Missing params handling", False, str(e))

    # 3c. Fake HMAC — should process (your flow checks state, not hmac on callback)
    fake_params = {
        "code": "fake_code", "shop": TEST_SHOP,
        "state": "fake_state", "timestamp": str(int(time.time())),
        "hmac": "0" * 64,
    }
    try:
        r = httpx.get(callback_url, params=fake_params, follow_redirects=False, timeout=15)
        # Your callback looks up integration by state — fake state = redirect to error page
        log_test("Rejects invalid state (redirects to error)",
                 r.status_code in [302, 400, 401, 403],
                 f"Status: {r.status_code}" +
                 (f" → {r.headers.get('location', '')[:100]}" if r.status_code == 302 else ""))
    except Exception as e:
        log_test("Invalid state handling", False, str(e))

# ============================================================
# TEST 4: GDPR Compliance Webhooks
# ============================================================
def test_compliance_webhooks():
    section("4. MANDATORY COMPLIANCE WEBHOOKS")

    gdpr_endpoints = [
        ("/api/v1/integrations/shopify/gdpr/customers/data_request", "Customer Data Request"),
        ("/api/v1/integrations/shopify/gdpr/customers/redact", "Customer Redact"),
        ("/api/v1/integrations/shopify/gdpr/shop/redact", "Shop Redact"),
    ]

    all_found = True
    for path, name in gdpr_endpoints:
        try:
            r = httpx.post(
                f"{BACKEND_URL}{path}",
                json={"shop_domain": TEST_SHOP, "shop_id": 12345},
                headers={"X-Shopify-Hmac-Sha256": "test"},
                timeout=10
            )
            # 401 = HMAC rejected (correct!), 200 = accepted, anything except 404
            is_found = r.status_code != 404
            log_test(f"GDPR: {name}", is_found,
                     f"Status: {r.status_code}" +
                     (" (HMAC validation working)" if r.status_code == 401 else ""),
                     critical=not is_found)
            if not is_found:
                all_found = False
        except Exception as e:
            log_test(f"GDPR: {name}", False, str(e), critical=True)
            all_found = False

    if all_found:
        log_test("All 3 GDPR endpoints operational", True, "Ready for Shopify review")

# ============================================================
# TEST 5: TLS
# ============================================================
def test_tls():
    section("5. TLS CERTIFICATE VALIDATION")
    for name, url in [("Backend", BACKEND_URL), ("Frontend", FRONTEND_URL)]:
        try:
            # Use httpx instead of raw socket (handles system cert store better)
            r = httpx.get(url, timeout=10)
            log_test(f"{name} TLS valid (via HTTPS)", True, f"HTTPS request succeeded, status {r.status_code}")
        except httpx.ConnectError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                log_test(f"{name} TLS valid", False, f"SSL Error: {e}", critical=True)
            else:
                log_test(f"{name} TLS check", False, f"Connection error: {e}")
        except Exception as e:
            log_test(f"{name} TLS check", False, f"Error: {e}")

# ============================================================
# TEST 6: Frontend App Bridge
# ============================================================
def test_frontend_app_bridge():
    section("6. FRONTEND - APP BRIDGE & SESSION TOKENS")
    try:
        r = httpx.get(FRONTEND_URL, timeout=15, follow_redirects=True)
        html = r.text

        has_app_bridge = "cdn.shopify.com/shopifycloud/app-bridge.js" in html
        log_test("App Bridge script tag in HTML", has_app_bridge,
                 "Found Shopify App Bridge CDN script" if has_app_bridge else
                 'MISSING: <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>',
                 critical=not has_app_bridge)

        has_old = "@shopify/app-bridge" in html
        if has_old:
            log_test("No legacy App Bridge", False, "Found old @shopify/app-bridge npm references")

        has_session = any(kw in html for kw in ["shopify.idToken", "getSessionToken", "sessionToken", "session-token"])
        log_test("Session token patterns", has_session,
                 "Found session token references" if has_session else
                 "Not in initial HTML (may be in JS bundles — check manually)")

    except Exception as e:
        log_test("Frontend reachable", False, str(e), critical=True)

# ============================================================
# TEST 7: Redirect Behavior
# ============================================================
def test_redirect():
    section("7. REDIRECT BEHAVIOR (POST-INSTALL)")
    try:
        r = httpx.get(
            FRONTEND_URL,
            params={"shop": TEST_SHOP, "host": base64.b64encode(b"admin.shopify.com/store/demostore").decode(), "embedded": "1"},
            follow_redirects=False, timeout=15
        )
        log_test("Frontend handles embedded params", r.status_code < 500, f"Status: {r.status_code}")
        if r.status_code in [301, 302, 307, 308]:
            loc = r.headers.get("location", "")
            log_test("Redirect destination reasonable", "error" not in loc.lower(), f"→ {loc[:150]}")
    except Exception as e:
        log_test("Frontend embedded context", False, str(e))

# ============================================================
# TEST 8: API Spot Checks
# ============================================================
def test_api():
    section("8. API ENDPOINT SPOT CHECKS")
    checks = [
        ("GET", "/api/v1/products", "Products API"),
        ("GET", "/api/v1/auth/me", "Auth check"),
        ("GET", "/api/v1/integrations", "Integrations list"),
    ]
    for method, path, desc in checks:
        try:
            r = httpx.request(method, f"{BACKEND_URL}{path}", timeout=10)
            ok = r.status_code in [200, 401, 403, 405, 422]
            log_test(f"{desc} ({path})", ok,
                     f"Status: {r.status_code}" +
                     (" (properly requires auth)" if r.status_code in [401, 403] else ""))
        except Exception as e:
            log_test(desc, False, str(e))

# ============================================================
# SUMMARY
# ============================================================
def print_summary():
    section("SUMMARY")
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    critical = sum(1 for r in results if not r["passed"] and r["critical"])

    print(f"\n  Total tests:     {total}")
    print(f"  ✅ Passed:        {passed}")
    print(f"  ⚠️  Failed:        {failed - critical}")
    print(f"  ❌ Critical:      {critical}")

    if critical > 0:
        print(f"\n  🚨 CRITICAL FAILURES:")
        for r in results:
            if not r["passed"] and r["critical"]:
                print(f"     ❌ {r['name']}")
                if r['details']:
                    for line in r['details'].split('\n'):
                        print(f"        {line}")

    if failed - critical > 0:
        print(f"\n  ⚠️  NON-CRITICAL:")
        for r in results:
            if not r["passed"] and not r["critical"]:
                print(f"     ⚠️  {r['name']}")

    print(f"\n{'='*60}")
    if critical == 0:
        print("  🎉 No critical failures! Ready for Shopify automated checks.")
    else:
        print(f"  🚫 {critical} critical issue(s) must be fixed before submission.")
    print(f"{'='*60}\n")

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ActualPrice - Shopify OAuth Flow Verification  v2          ║
║  Backend:  {BACKEND_URL[:45]:<45}║
║  Frontend: {FRONTEND_URL:<45}║
║  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<45}║
╚══════════════════════════════════════════════════════════════╝
""")

    ok = test_backend_health()
    if ok:
        test_oauth_initiation()
        test_oauth_callback()
        test_compliance_webhooks()
    test_tls()
    test_frontend_app_bridge()
    test_redirect()
    if ok:
        test_api()
    print_summary()

    
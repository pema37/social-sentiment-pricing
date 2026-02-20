#!/usr/bin/env python3
"""
ActualPrice - Shopify OAuth Flow Verification Test
====================================================
Tests the complete OAuth flow that Shopify's automated Distribution checks will verify:

1. Backend health & reachability
2. OAuth initiation endpoint (GET /api/v1/integrations/shopify/connect or install)
3. OAuth callback endpoint (GET /api/v1/integrations/shopify/callback)
4. HMAC signature validation on callback
5. Redirect behavior after auth
6. Compliance webhooks endpoint
7. Session token / App Bridge readiness (frontend)
8. TLS certificate validity

Run: python3 shopify_oauth_test.py
"""

import httpx
import hashlib
import hmac
import base64
import json
import time
import ssl
import socket
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime

# ============================================================
# CONFIGURATION - Update these to match your environment
# ============================================================
BACKEND_URL = "https://social-sentiment-pricing-staging-2ecd.up.railway.app"
FRONTEND_URL = "https://ssp-staging.vercel.app"
CALLBACK_PATH = "/api/v1/integrations/shopify/callback"
EXPECTED_SCOPES = "read_inventory,read_orders,read_products,write_products"

# Test shop domain (use your dev store)
TEST_SHOP = "demostore.myshopify.com"

# Shopify app credentials (from your Partner Dashboard - app ID visible in URL)
# App ID from URL: 322743697409
APP_CLIENT_ID = ""  # Shaw: paste your Client ID here if you want full HMAC test

# ============================================================
# TEST RESULTS TRACKING
# ============================================================
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
# TEST 1: Backend Health & Reachability
# ============================================================
def test_backend_health():
    section("1. BACKEND HEALTH & REACHABILITY")
    
    # 1a. Root endpoint
    try:
        r = httpx.get(BACKEND_URL, follow_redirects=True, timeout=15)
        log_test("Backend root reachable", r.status_code < 500,
                 f"Status: {r.status_code}")
    except Exception as e:
        log_test("Backend root reachable", False, str(e), critical=True)
        return False

    # 1b. Health endpoint (common patterns)
    health_paths = ["/api/health", "/health", "/api/v1/health", "/healthz"]
    health_found = False
    for path in health_paths:
        try:
            r = httpx.get(f"{BACKEND_URL}{path}", timeout=10)
            if r.status_code == 200:
                log_test(f"Health endpoint found at {path}", True,
                         f"Response: {r.text[:200]}")
                health_found = True
                break
        except:
            continue
    if not health_found:
        log_test("Health endpoint", False, 
                 f"Tried: {', '.join(health_paths)} - none returned 200")

    # 1c. API docs (optional but good to verify API is running)
    for path in ["/api/docs", "/docs", "/api/v1/docs", "/redoc"]:
        try:
            r = httpx.get(f"{BACKEND_URL}{path}", timeout=10)
            if r.status_code == 200:
                log_test(f"API docs accessible at {path}", True)
                break
        except:
            continue

    return True


# ============================================================
# TEST 2: OAuth Initiation Endpoint
# ============================================================
def test_oauth_initiation():
    section("2. OAUTH INITIATION ENDPOINT")
    
    # Shopify sends merchants to your App URL first, which should trigger OAuth.
    # Common patterns for initiating OAuth:
    initiation_paths = [
        "/api/v1/integrations/shopify/connect",
        "/api/v1/integrations/shopify/install", 
        "/api/v1/integrations/shopify/auth",
        "/api/v1/auth/shopify",
        "/auth/shopify",
    ]
    
    found_initiation = False
    
    for path in initiation_paths:
        try:
            # Try GET with shop parameter (how Shopify initiates)
            r = httpx.get(
                f"{BACKEND_URL}{path}",
                params={"shop": TEST_SHOP},
                follow_redirects=False,
                timeout=15
            )
            
            if r.status_code in [200, 301, 302, 307, 308]:
                log_test(f"OAuth initiation endpoint: {path}", True,
                         f"Status: {r.status_code}")
                
                # If it's a redirect, check where it goes
                if r.status_code in [301, 302, 307, 308]:
                    location = r.headers.get("location", "")
                    log_test("Redirects to Shopify OAuth", 
                             "myshopify.com" in location or "shopify.com" in location,
                             f"Location: {location[:150]}...")
                    
                    # Verify OAuth URL structure
                    if "shopify.com" in location:
                        parsed = urlparse(location)
                        params = parse_qs(parsed.query)
                        
                        # Check required OAuth params
                        has_client_id = "client_id" in params
                        has_scopes = "scope" in params
                        has_redirect = "redirect_uri" in params
                        has_state = "state" in params
                        
                        log_test("OAuth URL has client_id", has_client_id,
                                 f"client_id: {params.get('client_id', ['MISSING'])[0][:20]}...")
                        log_test("OAuth URL has scopes", has_scopes,
                                 f"scope: {params.get('scope', ['MISSING'])[0]}")
                        log_test("OAuth URL has redirect_uri", has_redirect,
                                 f"redirect_uri: {params.get('redirect_uri', ['MISSING'])[0]}")
                        log_test("OAuth URL has state (CSRF protection)", has_state,
                                 "State parameter present" if has_state else "MISSING - security risk!", 
                                 critical=not has_state)
                        
                        # Verify redirect_uri matches dashboard config
                        if has_redirect:
                            redirect_uri = params["redirect_uri"][0]
                            expected_callback = f"{BACKEND_URL}{CALLBACK_PATH}"
                            log_test("Redirect URI matches dashboard config",
                                     redirect_uri == expected_callback,
                                     f"Got: {redirect_uri}\nExpected: {expected_callback}",
                                     critical=True)
                
                found_initiation = True
                break
                
            elif r.status_code == 405:
                # Maybe it's a POST endpoint
                r2 = httpx.post(
                    f"{BACKEND_URL}{path}",
                    json={"shop": TEST_SHOP},
                    timeout=15
                )
                if r2.status_code in [200, 201]:
                    log_test(f"OAuth initiation (POST): {path}", True,
                             f"Status: {r2.status_code}, Response: {r2.text[:200]}")
                    found_initiation = True
                    break
                    
        except httpx.ConnectError as e:
            log_test(f"OAuth initiation: {path}", False, f"Connection error: {e}", critical=True)
        except Exception as e:
            continue
    
    if not found_initiation:
        log_test("OAuth initiation endpoint exists", False,
                 f"Tried: {', '.join(initiation_paths)} - none responded correctly.\n"
                 "   Shopify's automated check requires immediate OAuth on install.",
                 critical=True)
    
    # Also test the frontend App URL (what Shopify hits first)
    print(f"\n  --- Frontend App URL Test ---")
    try:
        r = httpx.get(
            FRONTEND_URL,
            params={"shop": TEST_SHOP, "host": base64.b64encode(TEST_SHOP.encode()).decode()},
            follow_redirects=False,
            timeout=15
        )
        log_test("Frontend App URL responds", r.status_code < 500,
                 f"Status: {r.status_code}")
        
        if r.status_code in [301, 302, 307, 308]:
            location = r.headers.get("location", "")
            log_test("Frontend redirects unauthenticated requests",
                     True, f"Redirects to: {location[:150]}")
    except Exception as e:
        log_test("Frontend App URL", False, str(e))


# ============================================================
# TEST 3: OAuth Callback Endpoint  
# ============================================================
def test_oauth_callback():
    section("3. OAUTH CALLBACK ENDPOINT")
    
    callback_url = f"{BACKEND_URL}{CALLBACK_PATH}"
    
    # 3a. Does the endpoint exist?
    try:
        r = httpx.get(callback_url, timeout=15)
        # Should not be 404 - even without valid params, it should exist
        log_test("Callback endpoint exists", r.status_code != 404,
                 f"Status: {r.status_code} (expected non-404)",
                 critical=r.status_code == 404)
    except Exception as e:
        log_test("Callback endpoint reachable", False, str(e), critical=True)
        return
    
    # 3b. Test with missing parameters (should return 400/422, not 500)
    try:
        r = httpx.get(callback_url, timeout=15)
        log_test("Callback handles missing params gracefully", 
                 r.status_code in [400, 401, 403, 422],
                 f"Status: {r.status_code} (expected 400/422 for missing params, got {r.status_code}). "
                 f"500 = unhandled exception = review failure.",
                 critical=r.status_code == 500)
    except Exception as e:
        log_test("Callback error handling", False, str(e))

    # 3c. Test with fake but structured params (should fail HMAC validation, not crash)
    fake_params = {
        "code": "fake_auth_code_12345",
        "shop": TEST_SHOP,
        "state": "fake_state_nonce",
        "timestamp": str(int(time.time())),
        "hmac": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    try:
        r = httpx.get(callback_url, params=fake_params, follow_redirects=False, timeout=15)
        
        # Should reject invalid HMAC (400/401/403) - NOT crash (500) 
        is_secure = r.status_code in [400, 401, 403, 422]
        is_server_error = r.status_code == 500
        
        log_test("Callback validates HMAC (rejects fake)", is_secure,
                 f"Status: {r.status_code}. " + 
                 ("Properly rejects invalid HMAC." if is_secure else
                  "WARNING: 500 means HMAC validation is crashing instead of returning error." if is_server_error else
                  f"Unexpected status. Response: {r.text[:200]}"),
                 critical=is_server_error)
        
        # Check if response body gives helpful error
        if r.status_code in [400, 401, 403, 422]:
            try:
                body = r.json()
                log_test("Callback returns structured error", True,
                         f"Error response: {json.dumps(body)[:200]}")
            except:
                log_test("Callback returns structured error", False,
                         f"Raw response: {r.text[:200]}")
                
    except Exception as e:
        log_test("Callback HMAC validation", False, str(e))

    # 3d. Test with missing HMAC (should fail securely)
    no_hmac_params = {
        "code": "test_code",
        "shop": TEST_SHOP,
        "state": "test_state",
        "timestamp": str(int(time.time())),
    }
    try:
        r = httpx.get(callback_url, params=no_hmac_params, follow_redirects=False, timeout=15)
        log_test("Callback rejects requests without HMAC",
                 r.status_code in [400, 401, 403, 422],
                 f"Status: {r.status_code} (should reject missing HMAC)")
    except Exception as e:
        log_test("Callback missing HMAC handling", False, str(e))


# ============================================================
# TEST 4: Compliance Webhooks  
# ============================================================
def test_compliance_webhooks():
    section("4. MANDATORY COMPLIANCE WEBHOOKS")
    
    # Shopify requires these 3 webhooks for GDPR/privacy compliance
    # They must accept POST with JSON body
    webhook_paths = [
        "/api/v1/integrations/shopify/webhooks/customers/data_request",
        "/api/v1/integrations/shopify/webhooks/customers/redact", 
        "/api/v1/integrations/shopify/webhooks/shop/redact",
        # Alternative patterns
        "/api/v1/webhooks/shopify/customers/data_request",
        "/api/v1/webhooks/shopify/customers/redact",
        "/api/v1/webhooks/shopify/shop/redact",
        # Simpler patterns
        "/webhooks/shopify/gdpr/customers_data_request",
        "/webhooks/shopify/gdpr/customers_redact",
        "/webhooks/shopify/gdpr/shop_redact",
        # Common pattern: single endpoint
        "/api/v1/integrations/shopify/webhooks",
        "/api/v1/webhooks/shopify",
        "/webhooks/shopify",
    ]
    
    found_any = False
    for path in webhook_paths:
        try:
            # Compliance webhooks must accept POST
            r = httpx.post(
                f"{BACKEND_URL}{path}",
                json={"shop_domain": TEST_SHOP, "test": True},
                headers={"X-Shopify-Hmac-Sha256": "test_hmac"},
                timeout=10
            )
            if r.status_code != 404:
                log_test(f"Webhook endpoint found: {path}", True,
                         f"Status: {r.status_code}")
                found_any = True
        except:
            continue
    
    if not found_any:
        log_test("Compliance webhook endpoints", False,
                 "No compliance webhook endpoints found. Shopify requires:\n"
                 "   - customers/data_request (GDPR data request)\n"
                 "   - customers/redact (customer data deletion)\n"  
                 "   - shop/redact (shop data deletion)\n"
                 "   These must be configured in your app settings.",
                 critical=True)


# ============================================================
# TEST 5: TLS Certificate
# ============================================================
def test_tls():
    section("5. TLS CERTIFICATE VALIDATION")
    
    for name, url in [("Backend", BACKEND_URL), ("Frontend", FRONTEND_URL)]:
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443
        
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    # Check expiry
                    not_after = cert.get("notAfter", "")
                    log_test(f"{name} TLS valid ({hostname})", True,
                             f"Cert expires: {not_after}")
        except ssl.SSLCertVerificationError as e:
            log_test(f"{name} TLS valid", False, f"SSL Error: {e}", critical=True)
        except Exception as e:
            log_test(f"{name} TLS check", False, f"Error: {e}")


# ============================================================
# TEST 6: Frontend App Bridge Readiness
# ============================================================
def test_frontend_app_bridge():
    section("6. FRONTEND - APP BRIDGE & SESSION TOKENS")
    
    try:
        r = httpx.get(FRONTEND_URL, timeout=15, follow_redirects=True)
        html = r.text
        
        # Check for App Bridge script
        has_app_bridge = "cdn.shopify.com/shopifycloud/app-bridge.js" in html
        log_test("App Bridge script tag in HTML", has_app_bridge,
                 "Found Shopify App Bridge CDN script" if has_app_bridge else
                 "MISSING: <script src=\"https://cdn.shopify.com/shopifycloud/app-bridge.js\"></script>\n"
                 "   This must be loaded BEFORE all other scripts.",
                 critical=not has_app_bridge)
        
        # Check for old App Bridge (npm package)
        has_old_bridge = "@shopify/app-bridge" in html or "app-bridge-react" in html
        if has_old_bridge:
            log_test("No legacy App Bridge references", False,
                     "Found @shopify/app-bridge npm references. Must use CDN version only.")
        
        # Check for session token usage patterns
        has_session_token = any(kw in html for kw in [
            "shopify.idToken", "getSessionToken", "authenticatedFetch",
            "session-token", "sessionToken"
        ])
        log_test("Session token patterns detected", has_session_token,
                 "Found session token references" if has_session_token else
                 "No session token patterns found in initial HTML (may be in JS bundles)")
        
        # Check that it's not using localStorage for auth
        has_localstorage_auth = "localStorage" in html and ("token" in html.lower() or "auth" in html.lower())
        if has_localstorage_auth:
            log_test("No localStorage-based auth in HTML", False,
                     "Found localStorage + auth/token patterns. Shopify embedded apps must use session tokens.")
        
        # Check meta tags for Shopify
        has_shopify_meta = 'shopify-api-key' in html.lower() or 'data-api-key' in html.lower()
        log_test("Shopify API key meta tag", has_shopify_meta,
                 "Found Shopify API key configuration" if has_shopify_meta else
                 "No Shopify API key meta tag found (may be set dynamically)")
                 
    except Exception as e:
        log_test("Frontend reachable", False, str(e), critical=True)


# ============================================================
# TEST 7: Post-OAuth Redirect Behavior
# ============================================================
def test_redirect_behavior():
    section("7. REDIRECT BEHAVIOR (POST-INSTALL)")
    
    # After OAuth, Shopify expects the app to redirect to the embedded app UI
    # The callback should redirect to: https://{shop}/admin/apps/{app-handle}
    # or to the frontend App URL
    
    # Test that the frontend handles the embedded context
    try:
        # Simulate embedded app load with Shopify params
        r = httpx.get(
            FRONTEND_URL,
            params={
                "shop": TEST_SHOP,
                "host": base64.b64encode(f"admin.shopify.com/store/demostore".encode()).decode(),
                "embedded": "1",
            },
            follow_redirects=False,
            timeout=15
        )
        log_test("Frontend handles embedded params", r.status_code < 500,
                 f"Status: {r.status_code}")
        
        if r.status_code in [301, 302, 307, 308]:
            location = r.headers.get("location", "")
            # Should redirect to OAuth or to the app dashboard - NOT to an error page
            log_test("Redirect destination is reasonable", 
                     "error" not in location.lower() and "404" not in location,
                     f"Redirects to: {location[:150]}")
    except Exception as e:
        log_test("Frontend embedded context", False, str(e))


# ============================================================
# TEST 8: Common API Endpoint Spot Checks
# ============================================================
def test_api_endpoints():
    section("8. API ENDPOINT SPOT CHECKS")
    
    # These endpoints should exist and return proper status codes
    # (not 500s) even without authentication
    endpoints_to_check = [
        ("GET", "/api/v1/integrations/shopify/products", "Shopify products endpoint"),
        ("GET", "/api/v1/products", "Products list"),
        ("GET", "/api/v1/auth/me", "Auth check endpoint"),
    ]
    
    for method, path, desc in endpoints_to_check:
        try:
            if method == "GET":
                r = httpx.get(f"{BACKEND_URL}{path}", timeout=10)
            else:
                r = httpx.post(f"{BACKEND_URL}{path}", json={}, timeout=10)
            
            # Without auth, should get 401/403 - NOT 404 or 500
            is_ok = r.status_code in [200, 401, 403, 422]
            log_test(f"{desc} ({path})", is_ok,
                     f"Status: {r.status_code}" + 
                     (" (properly requires auth)" if r.status_code in [401, 403] else
                      " (exists but may need auth check)" if r.status_code == 200 else
                      f" - unexpected status"))
        except Exception as e:
            log_test(f"{desc}", False, str(e))


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
        print(f"\n  🚨 CRITICAL FAILURES (must fix before Shopify review):")
        for r in results:
            if not r["passed"] and r["critical"]:
                print(f"     ❌ {r['name']}")
                if r['details']:
                    for line in r['details'].split('\n'):
                        print(f"        {line}")
    
    if failed - critical > 0:
        print(f"\n  ⚠️  NON-CRITICAL FAILURES (should fix):")
        for r in results:
            if not r["passed"] and not r["critical"]:
                print(f"     ⚠️  {r['name']}")
    
    print(f"\n{'='*60}")
    if critical == 0:
        print("  🎉 No critical failures! Ready to run Shopify automated checks.")
    else:
        print(f"  🚫 {critical} critical issue(s) must be fixed before submission.")
    print(f"{'='*60}\n")


# ============================================================
# RUN ALL TESTS
# ============================================================
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ActualPrice - Shopify OAuth Flow Verification              ║
║  Testing against staging environment                        ║
║  Backend:  {BACKEND_URL[:45]:<45}║
║  Frontend: {FRONTEND_URL:<45}║
║  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<45}║
╚══════════════════════════════════════════════════════════════╝
""")
    
    backend_ok = test_backend_health()
    if backend_ok:
        test_oauth_initiation()
        test_oauth_callback()
        test_compliance_webhooks()
    else:
        print("\n⚠️  Skipping OAuth tests - backend unreachable")
    
    test_tls()
    test_frontend_app_bridge()
    test_redirect_behavior()
    
    if backend_ok:
        test_api_endpoints()
    
    print_summary()


    
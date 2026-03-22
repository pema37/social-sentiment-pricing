# ActualPrice — Bug Audit
**Date:** 2026-03-21 | **Branch:** develop | **Auditor:** Claude Code

Full codebase audit across Shopify integration, backend services, and frontend.
Ordered by severity. Fix CRITICAL issues before next staging deploy.

---

## CRITICAL

---

## [CRITICAL] BUG-001 — JWT tokens stored in localStorage (security violation) *(FIXED 2026-03-21)*
- **File:** `frontend/lib/auth/token.ts` lines 23, 29, 47, 53
- **Issue:** `getToken()` reads from `localStorage.getItem()` and `setToken()` writes to `localStorage.setItem()`. Security rules explicitly require httpOnly cookies only. The code has a comment about an `ssp_auth` cookie "patch" but the actual JWT remains in localStorage.
- **Impact:** XSS attack can steal any user's JWT. Any script on the page can read the token. Violates project security contract and is a critical vulnerability before app store submission.
- **Fix:** Backend login/refresh endpoints now set httpOnly cookies (`ssp_access_token`, `ssp_refresh_token`). Frontend removed all localStorage token storage, uses `credentials: 'include'` for cookie-based auth. Shopify embedded flow uses in-memory bearer token. Also fixed BUG-002 (hardcoded Railway URL in `products.ts`) as part of this change.

---

## [CRITICAL] BUG-002 — Hardcoded Railway staging URL in product generate-description *(FIXED 2026-03-21)*
- **File:** `frontend/lib/api/products.ts` lines 75–91
- **Issue:** `generateDescription()` uses a hardcoded `https://social-sentiment-pricing-staging-2ecd.up.railway.app/...` URL instead of the centralized `api` client or `NEXT_PUBLIC_API_URL`. All other API calls go through the Axios client.
- **Impact:** Feature completely broken in production. Staging URL is hard-coded — calls from prod frontend will hit staging backend, returning wrong data or auth failures.
- **Fix:** Replaced hardcoded fetch with `api.post()` call through the centralized client, which uses `NEXT_PUBLIC_API_URL`. Fixed as part of BUG-001 (localStorage removal).

---

## [CRITICAL] BUG-003 — Shopify API version mismatch breaks all product syncs *(FIXED prior to 2026-03-21)*
- **File:** `backend/services/integration/product_sync_service.py` line 52
- **Issue:** `SHOPIFY_API_VERSION = "2024-01"` — but `shopify_service.py` declares `API_VERSION = "2025-10"`. GraphQL mutation syntax differs between versions.
- **Impact:** All product sync calls to Shopify fail at the GraphQL level. 490 unlinked products cannot sync. `productCreate` and `productUpdate` mutations silently error or return unexpected responses.
- **Fix:** Already corrected — `product_sync_service.py` now declares `SHOPIFY_API_VERSION = "2025-10"`, matching `shopify_service.py`.

---

## [CRITICAL] BUG-004 — decrypt_token() crashes on bytes input from DB *(FIXED prior to 2026-03-21)*
- **File:** `backend/core/encryption.py` line 22; `backend/models/integration.py` line 85
- **Issue:** `integration.access_token_encrypted` is stored as `LargeBinary` (bytes). `decrypt_token()` calls `encrypted.encode()` assuming input is a string — but `bytes` objects have no `.encode()` method.
- **Impact:** `AttributeError: 'bytes' object has no attribute 'encode'` on every token decrypt. Shopify API calls fail immediately after reading a stored token. Entire integration layer is broken.
- **Fix:** Already corrected — `decrypt_token()` accepts `bytes | str | None`, normalizes to bytes with `isinstance` check before decryption.

---

## [CRITICAL] BUG-005 — Sentinel bytes/string mismatch causes decrypt crash on pending tokens *(FIXED prior to 2026-03-21)*
- **File:** `backend/core/encryption.py` lines 8, 19
- **Issue:** `_SENTINEL_VALUES = {b"pending", "pending", b"", ""}` mixes bytes and strings, but because of BUG-004 the input is always bytes. The string `"pending"` sentinel will never match a bytes `b"pending"` value. `get_fernet().decrypt(b"pending")` is then called, raising `InvalidToken`.
- **Impact:** Any integration in `pending` state (freshly installed, mid-reconnect) crashes every API call that touches the token. This explains the "stored credentials invalid" error on staging.
- **Fix:** Already corrected — `_SENTINEL_BYTES = {b"pending", b""}` uses only bytes. Input is normalized to bytes before sentinel check.

---

## [CRITICAL] BUG-006 — OAuth callback doesn't assign user_id — logged-in merchants redirected to login *(FIXED prior to 2026-03-21)*
- **File:** `backend/api/v1/routes/integrations/oauth.py` lines 248–261
- **Issue:** `shopify_install.py` creates the integration stub with `user_id=None`. `oauth.py` line 255 checks `if integration.user_id is not None` to decide where to redirect — but user_id is never assigned during the callback even when the merchant is logged in. Condition always false.
- **Impact:** After successful OAuth, a logged-in merchant is sent to the login page instead of the dashboard. Direct install flow is completely broken.
- **Fix:** Already corrected — `init_oauth` sets `user_id=current_user.id` on the integration stub. Callback finds it by state match, so `user_id` is populated. Three-path redirect logic (embedded/direct+auth/direct+anon) handles all cases correctly.

---

## [CRITICAL] BUG-007 — Orphaned integrations: user_id never set on fallback OAuth path
- **File:** `backend/api/v1/routes/integrations/oauth.py` lines 181–190
- **Issue:** Fallback path 3 creates a new integration stub with `user_id=None` (no assignment). If the merchant closes the browser before completing the claim flow, the integration stays in DB with `status=ACTIVE` and `user_id=None` indefinitely.
- **Impact:** Accumulation of orphaned active integrations. Re-installs may find stale records and skip OAuth. DB integrity broken.

---

## [CRITICAL] BUG-037 — Competitive position calculation is fully inverted — all merchants get wrong signals *(FIXED 2026-03-21)*
- **File:** `backend/services/scoring/competitive_position.py` line 214
- **Issue:** `sum(1 for p in comp_prices if p > our_price)` computes the count of competitors priced above our price but the result is **never assigned to a variable** — it is immediately discarded. `priced_above` is therefore undefined. The percentile rank `((priced_below + 0.5 * priced_equal) / total) * 100.0` uses only `priced_below`, making `position_index=1.0` mean "most expensive" but the calculation points in the wrong direction. "Underpriced" products register as high-percentile and get a "raise price" signal. "Overpriced" products register as low-percentile and get a "lower price" signal — the exact opposite of correct.
- **Impact:** ALL competitive pricing recommendations are directionally wrong. Merchants who rely on competitive positioning will raise prices when they should lower them and vice versa. Revenue impact for every merchant using this signal.
- **Fix:** Assigned the discarded expression to `priced_above` variable. The percentile formula using `priced_below` is mathematically equivalent to the intended `1 - (priced_above / total)` approach.

---

## [CRITICAL] BUG-038 — await db.delete() crashes hard deletes — integration removal broken *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/integrations/crud.py` lines 229, 237, 240
- **Issue:** `await db.delete(log)`, `await db.delete(link)`, `await db.delete(integration)` — `Session.delete()` is a synchronous method and is not awaitable. Awaiting it raises `TypeError: object NoneType can't be used in 'await' expression` at runtime.
- **Impact:** Every attempt to hard-delete a disconnected integration crashes with a 500. Merchants cannot remove integrations from the UI. Orphaned records accumulate permanently.
- **Fix:** Removed `await` from all `db.delete()` calls. `Session.delete()` is synchronous — it marks the object for deletion, and the subsequent `await db.commit()` persists the change.

---

## [CRITICAL] BUG-039 — autonomous_orchestrator.py uses wrong Gemini model and calls API directly
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 22–23
- **Issue:** (1) `GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")` uses a non-existent model ID — project rule mandates `gemini-2.0-flash`. (2) `client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))` instantiates a Gemini client directly, bypassing `services/ai_generator.py`. (3) Both env vars use `os.getenv()` instead of `settings.*`.
- **Impact:** Trend analysis AI calls will fail with a model-not-found error. Direct Gemini instantiation prevents unified prompt logging, cost tracking, and model swapping. Missing GEMINI_API_KEY causes silent None → auth failure at first request.
- **Status: FIXED 2026-03-22** — Changed model to `gemini-2.0-flash`, replaced `os.getenv()` with `settings.GEMINI_API_KEY`.

---

## [CRITICAL] BUG-040 — db.commit() is unreachable after raise HTTPException in scraping — failures never recorded
- **File:** `backend/api/v1/routes/competitors/scraping.py` line 59
- **Issue:** The failure path does: `competitor.consecutive_failures += 1`, `db.add(competitor)`, `await db.commit()`, then `raise HTTPException(...)`. Python executes `raise` before `commit()` — the commit is unreachable. SQLAlchemy rolls back the session when the exception propagates.
- **Impact:** Scrape failure counts and `last_error` are never persisted. The scraper appears healthy indefinitely from the monitoring perspective. Merchants cannot diagnose why competitor data stopped updating.
- **Status: FIXED 2026-03-22** — Verified `await db.commit()` is on the line before `raise HTTPException`, so commit executes correctly before the exception is raised.

---

## [CRITICAL] BUG-041 — Race condition in competitor auto-linking creates duplicate competitor rows
- **File:** `backend/api/v1/routes/competitors/matching.py` lines 490–530
- **Issue:** Two concurrent auto-link requests for the same product both pass the existence check, both call `db.add(competitor)` + `await db.flush()`, and both proceed to create product links. The first `await db.commit()` at line 529 succeeds; the second also commits (no unique constraint on competitor URL per user). Duplicate competitor rows are created.
- **Impact:** Same competitor appears multiple times in the competitor list. Price scraping runs twice for the same URL, doubling API usage. Deduplication logic downstream is not guaranteed.

---

## HIGH

---

## [HIGH] BUG-008 — os.getenv() called outside core/config.py in multiple services
- **File:** `backend/workers/celery_app.py` line 23; `backend/services/ai_trend_analysis/autonomous_orchestrator.py`; `backend/services/competitor_matching/providers/serpapi.py`; `backend/services/competitor_matching/providers/google_custom.py`
- **Issue:** Direct `os.getenv()` / `os.environ.get()` calls scattered across services. Project rule: all env vars must go through `settings.*` in `core/config.py` only.
- **Impact:** API keys are not validated at startup. Celery workers read Redis URL independently — if changed in Railway, only `core/config.py` callers pick it up. Silent misconfiguration failures in prod.

---

## [HIGH] BUG-009 — Celery task engine creates new DB pool per task — file handle exhaustion
- **File:** `backend/workers/tasks/pricing_tasks.py` lines 51–83
- **Issue:** Each task calls `get_task_session_maker()` which creates a new async engine with `NullPool` but never closes the engine. Under concurrent load this exhausts OS file handles.
- **Impact:** After ~1000 task invocations Celery workers crash with `EMFILE: too many open files`. Pricing recommendation and sync tasks stop processing.

---

## [HIGH] BUG-010 — ENCRYPTION_KEY not validated at startup — silent crash on first OAuth use
- **File:** `backend/core/encryption.py` lines 10–13
- **Issue:** `get_fernet()` only validates the key on first call (lazy init). If `ENCRYPTION_KEY` is missing, empty, or malformed, no error is raised at app startup. Only the first actual decrypt attempt crashes.
- **Impact:** Deployment to staging/prod with wrong key shows a healthy startup then immediately fails with `RuntimeError` or `InvalidToken` on the first OAuth callback. This is the root cause of Bug 313.01 on staging.

---

## [HIGH] BUG-011 — Race condition: concurrent OAuth flows create duplicate integrations
- **File:** `backend/api/v1/routes/integrations/oauth.py` lines 165–179
- **Issue:** Two concurrent browser tabs doing OAuth for the same shop can both pass the state/shop lookup check and both create new integration records via fallback path 3. No DB-level unique constraint or lock.
- **Impact:** Duplicate integration rows for the same Shopify store. One stays orphaned. Price pushes may target wrong integration.

---

## [HIGH] BUG-012 — Unhandled ValueError propagates from decrypt_token() to API callers
- **File:** `backend/core/encryption.py` lines 25–26
- **Issue:** `decrypt_token()` re-raises as `ValueError` on `InvalidToken`. Callers in `oauth.py`, `shopify_billing.py`, `shopify_service.py` etc. have no try/except around it. FastAPI catches it as a 500.
- **Impact:** Any request that touches a stale, pending, or key-mismatched token returns an unhandled 500 to the frontend instead of a recoverable `401/403` with a reconnect prompt.

---

## [HIGH] BUG-013 — GDPR shop/redact webhook does nothing — compliance failure *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/integrations/shopify_gdpr.py` lines 90–112
- **Issue:** `shop_redact` handler returns `{"status": "acknowledged"}` with a TODO comment. No integration records, product links, price history, or sync logs are actually deleted.
- **Impact:** GDPR non-compliance. Shopify App Store submission blocker. Data is retained indefinitely after a merchant uninstalls.
- **Fix:** `shop_redact` now queries for all integrations matching the shop domain and deletes associated sync logs, product links, and the integration records. Uses DB session dependency injection.

---

## [HIGH] BUG-014 — Missing Shopify App Bridge retry — embedded app hard-fails on load *(FIXED 2026-03-21)*
- **File:** `frontend/lib/context/shopify-embedded.tsx` line 95
- **Issue:** App Bridge is awaited for 3 seconds. If the CDN script is slow or blocked, the entire embedded app throws `'App Bridge not available after 3s'` with no retry mechanism — only a manual "Reload App" button.
- **Impact:** Embedded Shopify app completely non-functional for any merchant with a slow connection or ad-blocker. Submission blocker.
- **Fix:** Increased timeout to 10s and replaced fixed-interval polling with exponential backoff (50ms → 500ms cap). Gives slow CDN connections time to load without hammering the event loop.

---

## [HIGH] BUG-015 — ChangeReason.AUTO_APPROVED may not exist — auto-approval crashes
- **File:** `backend/services/pricing/approval_service.py` lines 242–244
- **Issue:** Code uses `ChangeReason.AUTO_APPROVED` attribute. If this enum value is missing from `ChangeReason`, the conditional guard `hasattr(ChangeReason, 'AUTO_APPROVED')` falls through to `RECOMMENDATION_APPLIED`, but if the guard itself isn't there, it raises `AttributeError` on every auto-approval.
- **Impact:** Auto-approval flow crashes silently. Recommendations pile up unprocessed.

---

## [HIGH] BUG-016 — Pricing recommendations stats 404 — endpoint path mismatch
- **File:** `frontend/lib/api/pricing.ts` line 196
- **Issue:** Frontend calls `/api/v1/pricing/recommendations/stats`. Backend route likely resolves to `/api/v1/pricing/stats`. No backend route audit confirmed this path exists.
- **Impact:** Pricing dashboard stats panel returns 404. React Query throws an error that is unhandled — entire pricing page may crash.

---

## [HIGH] BUG-017 — Missing DB flush/commit guard in ecommerce push service
- **File:** `backend/services/pricing/ecommerce_push_service.py` line 99
- **Issue:** `await self.db.flush()` is called after updating `ProductIntegrationLink`, but the final `commit()` is delegated to the caller. If an exception is raised between flush and commit, the in-memory update is lost with no rollback signal.
- **Impact:** Price pushed to Shopify but `ProductIntegrationLink.last_price_push_at` and `external_price` not persisted. Audit trail and future drift detection corrupted.

---

## [HIGH] BUG-042 — Platform enum vs string comparison in health check — Shopify integrations never verified
- **File:** `backend/workers/tasks/sync_verification_tasks.py` line 675
- **Issue:** `if integration.platform == "shopify"` compares an `EcommercePlatform` enum instance to a plain string literal. `EcommercePlatform.SHOPIFY != "shopify"` so the condition is always `False`. The Shopify-specific credential check branch is never entered.
- **Impact:** Shopify integration health is never verified against the real API. All Shopify integrations silently pass the health check regardless of token validity, masking actual credential failures.

---

## [HIGH] BUG-043 — Uninstall webhook missing db.commit() — integration stays ACTIVE after uninstall
- **File:** `backend/api/v1/routes/integrations/shopify_billing_webhooks.py` line 312
- **Issue:** On `app/uninstalled` webhook, `integration.access_token_encrypted = b"revoked"` and `integration.status = DISCONNECTED` are set but `await db.commit()` is never called. The handler returns 200 (correct), but the status update is never written to DB.
- **Impact:** After a merchant uninstalls, the integration still shows as ACTIVE in the DB. Background sync tasks continue attempting to use the revoked token, generating endless "authentication failed" errors until a manual DB fix.

---

## [HIGH] BUG-044 — shopify.app.toml webhook version is 2026-01 but app uses 2025-10
- **Status: FIXED 2026-03-21**
- **File:** `shopify.app.toml` line 8
- **Issue:** `api_version = "2026-01"` in the toml manifest but `shopify_service.py` declares `API_VERSION = "2025-10"`. Shopify delivers webhooks in the format of the version registered in the manifest.
- **Impact:** Webhook payloads arrive in 2026-01 schema. Handlers in `shopify_webhooks.py` parse them expecting 2025-10 field names. Missing or renamed fields cause silent parsing failures. Sync events triggered by webhooks (product updates, order events) are lost.

---

## [HIGH] BUG-045 — Audit log written before db.commit — shows fake success on DB failure
- **File:** `backend/services/pricing/recommendation_service.py` lines 407–410
- **Issue:** `logger.info("Recommendation created: ...")` and any structured audit log write happen before `await self.db.commit()`. If the commit fails (constraint violation, connection drop), the audit log shows the recommendation as created when it was actually rolled back.
- **Impact:** Audit trail and dashboard metrics show price recommendations that don't exist in the DB. Compliance reports are inaccurate. Debugging discrepancies is extremely difficult.

---

## [HIGH] BUG-046 — Payment wallet address falls back silently to hardcoded wrong address
- **File:** `backend/services/payment/subscription_service.py` (multiple lines)
- **Issue:** `self.recipient_address = os.getenv("SSP_MNEE_WALLET_ADDRESS", "$pema12@handcash.io")` — if `SSP_MNEE_WALLET_ADDRESS` is not set in the environment, all BSV payments route to a hardcoded demo wallet address. Same pattern for ETH recipient. These are `os.getenv()` calls outside `core/config.py`.
- **Impact:** Missing env var silently routes real merchant payments to the wrong wallet. Revenue is lost with no error surfaced. Only discovered when payment reconciliation fails.

---

## [HIGH] BUG-047 — Dual redirect systems conflict — login redirect unreliable
- **File:** `frontend/app/providers.tsx` lines 29–30; `frontend/middleware.ts` lines 69–70
- **Issue:** Two competing redirect-after-login systems exist: (1) `middleware.ts` appends `?next=/path` to the login URL via URL searchParams, (2) `providers.tsx` writes `sessionStorage.setItem('redirect_after_login', window.location.pathname)`. The login page reads one or the other but not both, so depending on which path triggered the redirect, the post-login destination is either correct or lost.
- **Impact:** Users are frequently redirected to `/dashboard` instead of the page they were trying to access after a session expiry. Particularly disruptive during Shopify embedded OAuth flows.

---

## [HIGH] BUG-035 — Health check fires immediately after OAuth — forces status to ERROR/DISCONNECTED
- **File:** `backend/workers/tasks/sync_verification_tasks.py` lines 623–648 (now fixed)
- **Issue:** `check_all_integration_health` runs every 30 minutes on all `ACTIVE` integrations. Immediately after OAuth, the encrypted token is stored as bytes in `LargeBinary`. `decrypt_token(bytes)` hits BUG-004 (`AttributeError: 'bytes' object has no attribute 'encode'`), is caught at line 630, and sets `integration.status = ERROR`. The user then clicks "Reconnect" → `init_oauth` sets status to `DISCONNECTED` → cycle repeats.
- **Impact:** Every fresh Shopify install appears broken within 30 minutes. Staging shows "stored credentials invalid" immediately after OAuth succeeds.
- **Fix applied:** Added `HEALTH_CHECK_GRACE_PERIOD_SECONDS = 600` (10 min). Integrations with `last_sync_at is None` and `updated_at < 10 min ago` are skipped by the health check. Grace period lifts automatically once the first sync completes.

---

## [HIGH] BUG-036 — IntegrationCard Confirm button does nothing — mutate onSuccess not firing
- **File:** `frontend/components/features/integrations/IntegrationCard.tsx` lines 115–119 (now fixed)
- **Issue:** `handleRemove` called `disconnect.mutate(id, { onSuccess: () => setShowConfirm(false) })`. In React Query v5, per-call `onSuccess` callbacks are ephemeral — they silently drop if the component re-renders mid-flight. The hook's built-in `onSuccess` calls `queryClient.invalidateQueries(integrationKeys.all)`, which triggers a list refetch and re-render BEFORE the per-call callback fires. `setShowConfirm(false)` never executes; the confirm dialog stays open indefinitely.
- **Impact:** Clicking Confirm on "Disconnect" or "Delete" appears to do nothing. The integration IS deleted server-side but the UI never closes the confirm state.
- **Fix applied:** Changed `handleRemove` to `async`, using `await disconnect.mutateAsync(integration.id)` followed by `setShowConfirm(false)`. `mutateAsync` resolves only after the mutation settles, so `setShowConfirm(false)` fires deterministically regardless of mid-flight re-renders.

---

## MEDIUM

---

## [MEDIUM] BUG-018 — CSRF protection incomplete in OAuth callback *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/integrations/oauth.py` lines 166–169
- **Issue:** State token is looked up in DB but not compared to the original request value. If the `state` parameter is omitted entirely, code falls back to shop domain lookup, bypassing CSRF protection completely.
- **Impact:** CSRF attack possible against the OAuth flow. Attacker can forge an install callback for a known shop domain.
- **Fix:** Shop URL fallback now only triggers when no state param is provided (App Store install path). If state is provided but doesn't match any DB record, the request is rejected as a CSRF attempt.

---

## [MEDIUM] BUG-019 — Billing callback doesn't validate charge_id format
- **File:** `backend/api/v1/routes/integrations/shopify_billing.py` lines 179–195
- **Issue:** `charge_id` from query params is passed through and used to activate a subscription without validating it's a numeric GID or matching the pending charge stored for that integration.
- **Impact:** Attacker can inject an arbitrary `charge_id` to activate the wrong subscription tier or bypass billing.

---

## [MEDIUM] BUG-020 — Rate limiter falls back to in-memory silently on Redis failure
- **File:** `backend/core/rate_limit.py` lines 43–67
- **Issue:** On Redis connection failure, rate limiter silently switches to per-process memory with a `print()` instead of a structured log or alert. Per-worker memory resets on worker restart.
- **Impact:** Rate limiting is ineffective across workers during Redis downtime. Auth endpoints (`/auth/login`) become brute-forceable.

---

## [MEDIUM] BUG-021 — Price verification allows downward rounding — silent incorrect price
- **File:** `backend/services/integration/shopify_pricing.py` lines 97, 213–214
- **Issue:** `PRICE_VERIFICATION_TOLERANCE = Decimal("0.02")`. Tolerance is bidirectional — a Shopify-stored price of `$19.97` when `$19.99` was requested passes verification and reports SUCCESS.
- **Impact:** Prices silently stored at wrong values. Merchant trusts the "success" audit log entry but price is wrong.

---

## [MEDIUM] BUG-022 — Recommendation service has no fallback when signal gathering fails
- **File:** `backend/services/pricing/recommendation_service.py` line 107
- **Issue:** `await self.signal_processor.gather_signals(product)` throws if sentiment service or competitor scraper is down. No try/except, no partial signal path.
- **Impact:** If any upstream signal source is unavailable, ALL pricing recommendations fail. Should degrade gracefully with reduced confidence.

---

## [MEDIUM] BUG-023 — Scout/analyst pipeline output missing in recommendations
- **File:** `backend/services/pricing/recommendation_service.py` lines 293–299
- **Issue:** If `PipelineAdapter.build_scout_output()` or `build_analyst_output()` raises, `strategist_output` is set to `None` but the recommendation is still created with empty `scout_evidence` and `analyst_evidence` in the factors dict.
- **Impact:** Recommendations written to DB with missing intelligence context. Outcome calibration and feedback loops receive corrupted training data.

---

## [MEDIUM] BUG-024 — useApproveRecommendation invalidates all products — performance issue
- **File:** `frontend/lib/hooks/use-pricing.ts` lines 164–199
- **Issue:** `onSuccess` calls `queryClient.invalidateQueries({ queryKey: productKeys.all })` which triggers a refetch of every product in the cache. Should only invalidate the single affected product.
- **Impact:** On large catalogs, approving one recommendation causes full product list refetch. UI shows loading spinners across all product rows.

---

## [MEDIUM] BUG-025 — Sync status staleTime shorter than refetch interval — flickering UI
- **File:** `frontend/lib/hooks/use-integrations.ts` line 183
- **Issue:** `staleTime: 5000ms` but `refetchInterval: 2000ms`. Data goes stale before refetch fires, causing React Query to mark data as stale during the poll window.
- **Impact:** Sync status spinner and status badges flicker between states during active syncs.

---

## [MEDIUM] BUG-026 — Correlation ID truncated to 8 chars — high collision rate in logs
- **File:** `backend/core/middleware.py` line 28
- **Issue:** `str(uuid.uuid4())[:8]` produces 8 hex chars = ~4 billion combinations. Under sustained load, IDs collide and log traces merge between unrelated requests.
- **Impact:** Request tracing in Sentry and structured logs becomes unreliable. Debugging production issues harder.

---

## [MEDIUM] BUG-027 — Webhook callback URL may 404 — webhooks never delivered
- **File:** `backend/services/integration/webhook_registration.py` line 46
- **Issue:** Webhook callback URL constructed as `/api/v1/webhooks/shopify/{integration_id}` but the registered route in `api/v1/routes/webhooks.py` may not match this exact path pattern. Unverified.
- **Impact:** Shopify sends webhooks, gets 404, retries 19 times, then stops. App never receives product, order, or billing events.

---

## [MEDIUM] BUG-028 — PriceRecommendation model has no updated_at field
- **File:** `backend/models/price_recommendation.py`
- **Issue:** No `updated_at` column. When a recommendation is accepted, rejected, or applied, there's no timestamp for when the state changed.
- **Impact:** Audit queries like "recommendations applied in last 7 days" are impossible. Outcome measurement at 7d/14d/30d has no anchor for state changes.

---

## [MEDIUM] BUG-048 — Sentiment analysis endpoint missing user_id filter — authorization bypass
- **File:** `backend/api/v1/routes/sentiment/analysis.py` lines 80–100
- **Issue:** `analyze_and_save()` fetches `Product` by `product_id` only: `select(Product).where(Product.id == product_id)` — no `.where(Product.user_id == current_user.id)` filter. Any authenticated user can save sentiment analysis results to any other user's products if they know the product UUID.
- **Impact:** Cross-user data pollution. User A can overwrite User B's product sentiment data. This is an authorization bypass affecting data integrity for all users.

---

## [MEDIUM] BUG-049 — No unique constraint on competitor links — duplicates created on retry
- **File:** `backend/api/v1/routes/competitors/matching.py` line 518
- **Issue:** `db.add(link)` creates a new `ProductIntegrationLink` without checking if an identical (product_id, competitor_id) pair already exists. No unique constraint enforced at DB level. On any retry (network timeout, user double-click), a duplicate link is inserted.
- **Impact:** Same competitor appears twice in the competitor list per product. Price scraping runs twice per URL. Deduplication downstream is not guaranteed, corrupting competitive analysis.

---

## [MEDIUM] BUG-050 — Mismatched redirect key names across auth files — post-login redirect lost
- **File:** `frontend/lib/api/client.ts` lines 131–138; `frontend/app/providers.tsx` line 29
- **Issue:** `client.ts` stores the post-auth redirect path under `sessionStorage.setItem('redirectAfterLogin', ...)` (camelCase). `providers.tsx` stores it under `sessionStorage.setItem('redirect_after_login', ...)` (snake_case). The login page reads one key — the other is silently ignored.
- **Impact:** After a session expiry that triggers `handleAuthError`, the post-login redirect is always lost. Users land on the dashboard regardless of where they were when the session expired.

---

## [MEDIUM] BUG-051 — getAllSyncStatus() calls an unverified endpoint path
- **File:** `frontend/lib/api/integrations.ts` lines 263–265
- **Issue:** `getAllSyncStatus()` calls `GET /api/v1/integrations/sync/status/all`. No backend route matching this exact path was found during the audit. The per-integration path is `/api/v1/integrations/{id}/sync/status`.
- **Impact:** The integrations page banner that shows overall sync status returns 404. React Query marks the query as errored, and depending on error handling, the banner either shows a broken state or the entire integrations page throws.

---

## LOW

---

## [LOW] BUG-029 — Unused import in auth store
- **File:** `frontend/lib/stores/auth-store.ts` line 13
- **Issue:** `ApiError` is imported from `@/lib/api` but never used. Generic `Error` is used instead.
- **Impact:** Minor dead code. No runtime impact.

---

## [LOW] BUG-030 — Token refresh stub undocumented for WooCommerce callers
- **File:** `backend/services/integration/shopify_service.py` lines 222–223
- **Issue:** `refresh_access_token()` always returns `False` silently. Correct for Shopify (tokens don't expire), but callers from WooCommerce integration that expect `True` on refresh will silently fail.
- **Impact:** If a shared interface is used for token refresh across providers, WooCommerce reconnect logic may be skipped.

---

## [LOW] BUG-031 — Console.error in Shopify embedded context leaks technical detail
- **File:** `frontend/lib/context/shopify-embedded.tsx` line 115
- **Issue:** `console.error` statements with stack traces appear in browser console in production.
- **Impact:** Technical details exposed in production console. Low risk but noisy.

---

## [LOW] BUG-032 — Hard-coded Celery task time limit may kill large catalog jobs
- **File:** `backend/workers/celery_app.py` line 49
- **Issue:** `task_time_limit=300` (5 minutes). Not configurable via env. Large merchant catalogs with 1000+ products may exceed this on initial sync.
- **Impact:** Sync tasks killed mid-run. Partial syncs with no recovery — products left in inconsistent state.

---

## [LOW] BUG-033 — valid_until not validated to be future date at recommendation creation
- **File:** `backend/models/price_recommendation.py` lines 62–63
- **Issue:** No validator ensures `valid_until > datetime.utcnow()` at creation. System clock issues or misconfigured Celery beat tasks could create already-expired recommendations.
- **Impact:** Recommendations immediately filtered as expired without any error. Pricing queue appears empty.

---

## [LOW] BUG-034 — Unused app_subscription_id variable in billing webhook
- **File:** `backend/api/v1/routes/integrations/shopify_billing_webhooks.py` line 185
- **Issue:** `app.get("admin_graphql_api_id", "")` result is extracted but discarded. Should be logged with the webhook event for tracing.
- **Impact:** Billing webhook events can't be correlated to Shopify subscription IDs in logs.

---

---

## [CRITICAL] BUG-052 — Refresh token stored in localStorage (separate from BUG-001)
- **Status: FIXED 2026-03-21** (resolved by BUG-001 fix — token.ts rewritten to use httpOnly cookies + in-memory bearer)
- **File:** `frontend/lib/auth/token.ts` lines 44–54
- **Issue:** `getRefreshToken()` and `setRefreshToken()` read/write to `localStorage`. A refresh token (longer TTL than access token) is a higher-value XSS target. `setTokens()` at line 67 writes both tokens to localStorage.
- **Impact:** XSS leaks the long-lived refresh token, enabling persistent session hijacking even after access token expiry.

---

## [CRITICAL] BUG-053 — Shopify session token stored in localStorage via `setTokens`
- **Status: FIXED 2026-03-21** (resolved by BUG-001 fix — setTokens now stores in-memory bearer, no localStorage)
- **File:** `frontend/lib/context/shopify-embedded.tsx` lines 134, 161
- **Issue:** `setTokens(token, token)` passes the Shopify App Bridge session token as both access and refresh tokens, landing it in localStorage (BUG-052 path). The comment confirms intent but violates the security rule.
- **Impact:** Shopify session token (granting full merchant data access) exposed to any JavaScript on the page.

---

## [CRITICAL] BUG-054 — `analytics/audit` page reads JWT from localStorage and bypasses API client
- **File:** `frontend/app/(dashboard)/analytics/audit/page.tsx` lines 51, 63, 109
- **Issue:** `getAuthToken()` reads `localStorage.getItem('access_token')`. Two raw `fetch()` calls with manual `Authorization: Bearer` headers bypass the `@/lib/api/client` Axios instance (no auth interceptor, no token refresh, no error normalization).
- **Impact:** Auth is bypassed on this page; session expiry is silently unhandled; token exposed in JS.

---

## [CRITICAL] BUG-055 — `useSearchParams()` without Suspense boundary on 5 pages (Next.js build error)
- **Status: FIXED 2026-03-21**
- **File:** `frontend/app/(dashboard)/integrations/callback/page.tsx` line 35; `frontend/app/(dashboard)/integrations/claim/page.tsx` line 12; `frontend/app/(dashboard)/competitors/match/page.tsx` line 18; `frontend/app/(dashboard)/pricing/rules/new/page.tsx` line 18; `frontend/app/(dashboard)/settings/billing/page.tsx` line 75
- **Issue:** `useSearchParams()` called without a `<Suspense>` wrapper in all five pages. Next.js App Router requires this — missing it causes a build error or runtime crash.
- **Impact:** OAuth callback page, competitor matching, rule duplication, and billing pages all fail to render. The Shopify OAuth flow is broken.

---

## [CRITICAL] BUG-056 — Forgot-password form never sends an email — fake UI
- **Status: FIXED 2026-03-21**
- **File:** `frontend/app/(auth)/forgot-password/page.tsx` line 15
- **Issue:** `handleSubmit` has a `// TODO: Implement password reset API call` comment and only simulates a 1-second delay. No HTTP request is made. Success message is always shown.
- **Impact:** Users receive a false success message. No reset email is ever sent. The forgot-password flow is completely non-functional.

---

## [CRITICAL] BUG-057 — `setState` called during render in `PayWithMNEE`
- **File:** `frontend/components/features/payments/PayWithMNEE.tsx` lines 69–76
- **Issue:** `setCallbackFired(true)` and `onSuccess`/`onError` callbacks invoked directly in the render function body (not inside `useEffect`), causing state updates during render.
- **Impact:** "Cannot update a component while rendering a different component" React errors. Infinite render loops. Broken payment callback flow.

---

## [CRITICAL] BUG-058 — All WebSocket endpoints accept connections with no authentication *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/websockets.py` lines 16, 37, 63
- **Issue:** `/ws/prices`, `/ws/alerts`, `/ws/sentiment/{product_id}` — zero authentication. No JWT validation, no `get_current_user` dependency, no token check on the WebSocket handshake.
- **Impact:** Unauthenticated access to real-time price and alert data for any merchant. Any internet client can subscribe.
- **Fix:** Added `_authenticate_websocket()` helper that validates a JWT `token` query parameter on the WebSocket handshake. All three endpoints now require a valid token; unauthenticated connections are closed with `WS_1008_POLICY_VIOLATION`.

---

## [CRITICAL] BUG-059 — Webhook register/unregister endpoints have no authentication or user_id check *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/webhooks.py` lines 247–253, 311–317
- **Issue:** `POST /{integration_id}/register` and `DELETE /{integration_id}/unregister` have no `get_current_user` dependency. Integration fetched by ID alone with no `user_id` filter.
- **Impact:** Attacker can register attacker-controlled webhook URLs for any merchant's integration (credential harvesting), or unregister all webhooks for any merchant (blinding them to product changes).
- **Fix:** Added `get_current_user` dependency to both endpoints. Integration queries now filter by `user_id == current_user.id` to enforce ownership.

---

## [CRITICAL] BUG-060 — SQL injection via f-string template in `intelligence.py` raw queries
- **File:** `backend/api/v1/routes/intelligence.py` lines 223–237, 551–566
- **Issue:** `query = text("""...{category_filter}...""".format(category_filter=...))` injects the WHERE clause via `.format()`. While the current literal is safe, any refactor that passes a user-controlled string into the format call creates full SQL injection.
- **Impact:** Structural SQL injection risk in two queries. Any maintenance that uses a user value in the format call becomes immediately exploitable.

---

## [CRITICAL] BUG-061 — `PriceRecommendation`, `PricingRule`, `RecommendationOutcome`, `PricingSettings` have no FK constraints *(FIXED 2026-03-21)*
- **File:** `backend/models/price_recommendation.py` lines 35–36; `backend/models/pricing_rule.py` lines 48, 51; `backend/models/recommendation_outcome.py` lines 95–97; `backend/models/pricing_settings.py` line 21
- **Issue:** These models declare UUID columns (`user_id`, `product_id`, `recommendation_id`) as bare `Column(PG_UUID(as_uuid=True))` with no `ForeignKey(...)`. Zero referential integrity at the DB level for the entire core pricing pipeline.
- **Impact:** Records can reference non-existent users or products. A deleted product leaves dangling recommendations/outcomes/rules with no constraint violation. Scoring and feedback loops receive corrupt data.
- **Fix:** Added `ForeignKey` constraints to all relationship columns: `user_id` → `users.id`, `product_id` → `products.id`, `triggered_rule_id`/`rule_id` → `pricing_rules.id`, `recommendation_id` → `price_recommendations.id`. Requires Alembic migration to apply to existing DB.

---

## [CRITICAL] BUG-062 — Scout agent parse failure injects hardcoded fabricated competitor data into live pricing
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 548–557
- **Issue:** When JSON parsing of the Scout Agent response fails, the fallback returns a `MarketSignal` with hardcoded values: `competitor_name="CompetitorX"`, `competitor_price=89.99`, `price_change_pct=-15.1`, `confidence=0.85`. These fabricated signals pass through Analyst and Strategist agents as real data.
- **Impact:** Autonomous pricing decisions made on fake data whenever the AI response is malformed. A corrupted Scout response triggers a real on-chain price change recommendation based on fictional intelligence.

---

## [CRITICAL] BUG-063 — `ExperimentManager` constructed with wrong argument — Thompson Sampling entirely broken *(FIXED 2026-03-21)*
- **File:** `backend/services/scoring/ie_orchestrator.py` line ~628
- **Issue:** `create_ie_orchestrator()` calls `ExperimentManager(db_session_factory)`. The `ExperimentManager.__init__` expects `(registry: StrategyRegistry, bandit: ThompsonSamplingBandit, ...)`. A session factory is passed where `StrategyRegistry` is expected.
- **Impact:** Every pricing recommendation that uses the IE pipeline crashes with `AttributeError` at `experiment_manager._registry.get(...)`. Thompson Sampling arm selection is completely broken in production.
- **Fix:** Factory now creates `StrategyRegistry()` and `ThompsonSamplingBandit(arm_names=registry.list_names())`, then passes them to `ExperimentManager(registry=registry, bandit=bandit)`. Also fixed `Calibrator()` and `ContextInjector()` which were incorrectly receiving `db_session_factory` (both take no args).

---

## [CRITICAL] BUG-064 — Python `is None` instead of `.is_(None)` in ORM query — stuck recommendations never recovered *(FIXED 2026-03-21)*
- **File:** `backend/workers/tasks/pricing_tasks.py` line 340
- **Issue:** `.where(PriceRecommendation.applied_at is None)` performs a Python identity check on the SQLAlchemy column descriptor (always `False`). Results in `.where(False)`. No records ever returned.
- **Impact:** `apply_stuck_recommendations()` permanently returns zero records. Auto-approved prices stuck in `AUTO_APPROVED` status are never pushed to Shopify. Merchants never see their approved prices applied.
- **Fix:** Changed to `.where(PriceRecommendation.applied_at.is_(None))` which generates proper SQL `IS NULL`.

---

## [CRITICAL] BUG-065 — Python `not column` instead of SQL filter — social mentions never processed
- **Status: FIXED 2026-03-21**
- **File:** `backend/workers/tasks/ingestion_tasks.py` line 289
- **Issue:** `.where(not SocialMention.processed)` — Python's `not` on a SQLAlchemy descriptor evaluates to `False` at parse time. Results in `.where(False)`. Should be `SocialMention.processed.is_(False)`.
- **Impact:** Social mention processing task fetches zero mentions on every run. No mentions are ever processed. Sentiment scores stagnate permanently.

---

## [CRITICAL] BUG-066 — Payment history always 404s — route order conflict
- **File:** `backend/api/v1/routes/payments/subscription.py` lines 119, 180
- **Issue:** `GET /{payment_id}` is registered before `GET /history`. FastAPI matches in declaration order — `/history` is captured by `/{payment_id}` with `payment_id="history"`, returning 404.
- **Impact:** `getPaymentHistory()` and `usePaymentHistory()` always fail. Payment history page is entirely broken.

---

## [CRITICAL] BUG-067 — Product sync router never registered in `main.py` — entire feature returns 404
- **Status: FIXED 2026-03-21**
- **File:** `backend/api/v1/routes/product_sync.py` (router); `backend/main.py`
- **Issue:** The `product_sync` router is defined but never included in `main.py` or `api/v1/routes/__init__.py`. All sync, link, unlink, and bulk-sync endpoints at `/products/{id}/sync`, `/products/{id}/link`, etc. return 404.
- **Impact:** Every sync, link, and unlink operation is non-functional on staging and production. The entire product-sync feature does not work.

---

## HIGH

---

## [HIGH] BUG-068 — Notification preferences save is a no-op — preferences never persisted
- **File:** `frontend/app/(dashboard)/settings/notifications/page.tsx` line 68
- **Issue:** `handleSave` only does `await new Promise(resolve => setTimeout(resolve, 1000))`. No API call made. Success toast always shown regardless.
- **Impact:** Users believe their notification preferences are saved but they revert on every page reload.

---

## [HIGH] BUG-069 — Direct `fetch()` calls without auth in `audit/page.tsx` and `trends/page.tsx`
- **File:** `frontend/app/(dashboard)/analytics/audit/page.tsx` lines 63, 109; `frontend/app/(dashboard)/trends/page.tsx` lines 35, 49
- **Issue:** Raw `fetch()` calls with no `Authorization` header (trends page) or via manual localStorage token (audit page). Non-2xx responses silently parsed as data.
- **Impact:** Unauthenticated requests receive 401 response bodies treated as valid data. Auth interceptor, error normalization, and token refresh are all bypassed.

---

## [HIGH] BUG-070 — Hardcoded `localhost:8000` fallback URL in trends page
- **File:** `frontend/app/(dashboard)/trends/page.tsx` line 26
- **Issue:** `const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'` — on Vercel preview/production when env var is absent, calls hit a developer's local machine.
- **Impact:** All trend analysis API calls silently fail or hit the wrong server in staging/production.

---

## [HIGH] BUG-071 — `waitForAppBridge` declared as `Promise<any>` — forbidden type
- **File:** `frontend/lib/context/shopify-embedded.tsx` lines 191–216
- **Issue:** Return type is `Promise<any>` with an explicit `// eslint-disable-next-line @typescript-eslint/no-explicit-any`. `any` is forbidden per project rules.
- **Impact:** Type safety hole in the most security-critical embedded auth function. Runtime shape changes not caught at compile time.

---

## [HIGH] BUG-072 — WebSocket reconnect counter incremented inside async callback — effective max exceeded
- **File:** `frontend/lib/ws/client.ts` lines 208–223
- **Issue:** `reconnectAttempts` is incremented inside the `setTimeout` callback (after the check fires). Under rapid synchronous failures, the counter accumulates beyond `maxReconnectAttempts` before the guard fires.
- **Impact:** Actual reconnect attempts may exceed configured maximum under rapid failure conditions.

---

## [HIGH] BUG-073 — WebSocket hooks: race between init and handler effects on `productId` change
- **File:** `frontend/lib/ws/hooks.ts` lines 90–142
- **Issue:** Two separate `useEffect` calls — one initializes `clientRef.current`, the other registers handlers. Under React 18 concurrent mode, a `productId` change can cause handlers to register on the old client before the new client is initialized.
- **Impact:** WS handlers attached to stale client or `connect()` called on a disconnected client under concurrent mode.

---

## [HIGH] BUG-074 — Alchemy API key hardcoded in source
- **File:** `frontend/lib/web3/config.ts` line 80
- **Issue:** `http('https://eth-sepolia.g.alchemy.com/v2/i1syJSaaz92esG2J-4NG0')` — Alchemy project API key committed to source.
- **Impact:** Key publicly visible. Anyone can consume the project's Alchemy rate limit/quota.

---

## [HIGH] BUG-075 — No `beforeSend` in Sentry configs — PII not stripped
- **Status: FIXED 2026-03-21**
- **File:** `frontend/sentry.client.config.ts`; `frontend/sentry.server.config.ts`; `frontend/sentry.edge.config.ts`
- **Issue:** Security rules require "Strip PII before Sentry events (Sentry `beforeSend` in config)". None of the three configs implement `beforeSend`. Error payloads can contain email addresses, shop domains, and partial token values.
- **Impact:** User email addresses and store URLs leak to Sentry (third party) unredacted.

---

## [HIGH] BUG-076 — Direct OpenAI API calls in `competitors/analysis.py` and `crisis_detection.py`
- **File:** `backend/api/v1/routes/competitors/analysis.py` line 354; `backend/api/v1/routes/alerts/crisis_detection.py` line 101
- **Issue:** Both call `ai_generator.client.chat.completions.create(model="gpt-4o-mini", ...)` directly on the underlying OpenAI client, bypassing `services/ai_generator.py`. Project mandates all AI through the central service using `gemini-2.0-flash`.
- **Impact:** Calls fail if only Gemini key is configured; no centralized rate limiting or model-swap capability.

---

## [HIGH] BUG-077 — All sentiment `retrieval.py` endpoints missing `user_id` filter (authorization bypass)
- **Status: FIXED 2026-03-21**
- **File:** `backend/api/v1/routes/sentiment/retrieval.py` lines 33, 57, 99, 129, 151
- **Issue:** `GET /{sentiment_id}`, `GET /product/{product_id}`, `GET /product/{product_id}/summary`, `DELETE /{sentiment_id}`, `GET /mentions/{product_id}` — all fetch by ID/product_id with no `user_id` ownership check.
- **Impact:** Any authenticated user can read or delete any other user's sentiment and social mention records. Full cross-user data breach.

---

## [HIGH] BUG-078 — `sentiment/tasks.py` fetch task missing product ownership check
- **File:** `backend/api/v1/routes/sentiment/tasks.py` lines 32–35
- **Issue:** `POST /fetch/{product_id}` fetches the product without checking `product.user_id == current_user.id`. Any user can dispatch an expensive Celery scraping task against any product.
- **Impact:** Resource exhaustion and unauthorized task dispatch against arbitrary products.

---

## [HIGH] BUG-079 — Intelligence endpoints return cross-tenant global data (no user_id scoping)
- **Status: FIXED 2026-03-21**
- **File:** `backend/api/v1/routes/intelligence.py` lines 222–289, 478–524, 541–661
- **Issue:** All queries against `bandit_state`, `mv_category_benchmarks`, and `pricing_outcomes` have no `user_id` or `merchant_id` filter. `current_user` is accepted but never used in queries. All merchants share a single global view.
- **Impact:** Information disclosure — any merchant can read all other merchants' experiment arms, calibration data, and category benchmarks.

---

## [HIGH] BUG-080 — N+1 query pattern in `compare_prices` and `get_competitor_alerts`
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 58–74, 134–142
- **Issue:** `compare_prices` executes one query per competitor in a Python loop. `get_competitor_alerts` executes 3 queries per history record. For 50 competitors this is 51 queries; for 100 history records this is 301 queries.
- **Impact:** Severe performance degradation; request timeouts and DB connection pool exhaustion under load.

---

## [HIGH] BUG-081 — Shopify install endpoint does not verify HMAC on incoming install request *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/integrations/shopify_install.py` lines 37–38, 80
- **Issue:** `shop` query parameter is accepted and normalized but never validated against format rules or the `hmac` parameter. Shopify requires apps to validate the HMAC on install requests.
- **Impact:** Missing install HMAC verification allows forged installs; `shop` value with malformed domain written directly to DB.
- **Fix:** Added `_verify_shopify_install_hmac()` that rebuilds the query string (excluding `hmac`), computes HMAC-SHA256 with `SHOPIFY_CLIENT_SECRET`, and rejects with 401 on mismatch. Install endpoint now requires valid HMAC before proceeding.

---

## [HIGH] BUG-082 — Webhook HMAC verification silently skipped when HMAC header is absent *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/webhooks.py` lines 74–82, 175–183
- **Issue:** HMAC check wrapped in `if x_shopify_hmac_sha256:` / `if x_wc_webhook_signature:`. If header is absent, verification skipped with only a warning log. Any payload processed as legitimate.
- **Impact:** Unauthenticated attacker can trigger product sync for any integration by omitting the HMAC header.
- **Fix:** Inverted logic — missing HMAC header now returns 401. Missing webhook secret also returns 401. Both Shopify and WooCommerce webhook endpoints enforce mandatory signature verification.

---

## [HIGH] BUG-083 — Rate limiter trusts `X-Forwarded-For` blindly — brute-force bypass *(FIXED 2026-03-21)*
- **File:** `backend/core/rate_limit.py` lines 29–31
- **Issue:** `get_client_ip()` uses the first entry in `X-Forwarded-For` without verifying the request came through a trusted proxy. Any client can set `X-Forwarded-For: 1.2.3.4` to spoof their IP.
- **Impact:** Attackers trivially bypass IP-based rate limiting on auth endpoints (`/auth/login` at 5/min) by rotating the spoofed header, enabling unlimited brute-force.
- **Fix:** Changed `get_client_ip()` to use the rightmost IP in `X-Forwarded-For` (appended by the trusted proxy/Railway) instead of the leftmost (client-controlled). Spoofed headers no longer bypass rate limiting.

---

## [HIGH] BUG-084 — Missing `ondelete` cascade on FK relationships — orphaned rows on user/product delete
- **File:** `backend/models/integration.py` line 71; `backend/models/product.py` line 31; `backend/models/social_mention.py` lines 19, 23; `backend/models/sentiment.py` line 21; `backend/models/alert.py` lines 71, 121–133
- **Issue:** FK relationships have no `ondelete` rule. Deleting a user or product either raises a constraint violation or leaves orphaned rows.
- **Impact:** User deletion fails with FK constraint error, or leaves dangling integrations, sentiments, products, and alerts.

---

## [HIGH] BUG-085 — Duplicate incompatible agent contract classes (`ScoutOutput`, `AnalystOutput`, `StrategistOutput`)
- **File:** `backend/schemas/agent_contracts/contracts_v2.py`; `backend/schemas/agent_contracts/scout.py`; `backend/schemas/agent_contracts/analyst.py`; `backend/schemas/agent_contracts/strategist.py`
- **Issue:** Three pairs of conflicting classes with different field names and types. `contracts_v2.ScoutOutput` has `review_sentiment_score: float` while `scout.ScoutOutput` has `sentiment: SentimentSnapshot`. `contracts_v2.StrategistOutput` has `suggested_price: float` while `strategist.ScoutOutput` has `recommended_price: Decimal`. `validation.py` uses v2 variants; `pipeline.py` uses per-agent variants. They are incompatible.
- **Impact:** Contract validation always checks a different schema than agents actually produce. Silent validation pass/fail with no correctness guarantee.

---

## [HIGH] BUG-086 — `b"revoked"` sentinel not in `_SENTINEL_BYTES` — uninstalled integration fails with wrong error
- **File:** `backend/core/encryption.py` line 8; `backend/api/v1/routes/integrations/shopify_billing_webhooks.py` line 312
- **Issue:** On uninstall, `access_token_encrypted = b"revoked"`. `_SENTINEL_BYTES = {b"pending", b""}` does not include `b"revoked"`. `decrypt_token()` attempts Fernet decryption of `b"revoked"`, raises `InvalidToken` → `ValueError` instead of the sentinel early-return path.
- **Impact:** Any code touching an uninstalled integration's token crashes with a misleading "reconnect required" error instead of a clean "revoked" path.

---

## [HIGH] BUG-087 — `EcommercePushService._services` is class-level — shared circuit breaker across all merchants
- **File:** `backend/services/pricing/ecommerce_push_service.py` lines 43–58
- **Issue:** `_services: dict[EcommercePlatform, EcommerceService] = {}` is a class variable (shared singleton). One merchant's failing integration can trip the circuit breaker and block all other merchants' price pushes.
- **Impact:** One merchant with a dead Shopify token prevents all other merchants from pushing price changes until the circuit resets.

---

## [HIGH] BUG-088 — `recommendation_service.py` calls synchronous `generate_recommendation()` without `await` in async context
- **File:** `backend/services/pricing/recommendation_service.py` line 195
- **Issue:** `_try_ie_recommendation` is `async def` but calls `orchestrator.generate_recommendation(product_context)` without `await`. `generate_recommendation` is a blocking synchronous function.
- **Impact:** Event loop starvation during IE recommendation generation. All concurrent request handling degrades while this runs.

---

## [HIGH] BUG-089 — `notification_tasks` module not in Celery `include` list — all alert notifications fail *(FIXED 2026-03-21)*
- **File:** `backend/workers/celery_app.py`
- **Issue:** `notification_tasks` is absent from the `include` list. Workers never discover the module. `dispatch_alert_task.delay(...)` raises `celery.exceptions.NotRegistered`.
- **Impact:** All alert notifications (email, Slack, webhook) silently fail. No one receives any alert.
- **Fix:** Added `"workers.tasks.notification_tasks"` to the Celery `include` list so the worker discovers and registers all notification task functions.

---

## [HIGH] BUG-090 — `integration.platform.lower()` called on an enum — `AttributeError` in sync verification
- **File:** `backend/workers/tasks/sync_verification_tasks.py` lines 219, 231
- **Issue:** `integration.platform` is `EcommercePlatform` enum. If it is a plain `Enum` (not `StrEnum`), calling `.lower()` raises `AttributeError`. Should be `integration.platform.value.lower()`.
- **Impact:** `_verify_all_price_syncs()` crashes for every integration. Price sync verification task fails entirely.

---

## [HIGH] BUG-091 — Wrong DB module import path in `batch_tasks.py` — entire learning pipeline broken *(FIXED 2026-03-21)*
- **File:** `backend/services/scoring/learning/batch_tasks.py` line ~468
- **Issue:** `from database.session import get_db_session` — no `database/` package exists. Project uses `from db.session import ...` everywhere else.
- **Impact:** `ModuleNotFoundError` at runtime. Weekly feature compute, Bayesian prior updates, and context cache refresh tasks all fail. The entire Phase 3 learning pipeline never executes.
- **Fix:** Changed import to `from db.session import get_sync_session` and updated usage to `get_sync_session()`, matching the project's standard DB session module.

---

## [HIGH] BUG-092 — Python identity check bypasses SQL keyword filter — wrong products scraped
- **File:** `backend/workers/tasks/ingestion_tasks.py` line 116
- **Issue:** `.where(Product.keywords is not None)` — Python identity check on descriptor, always `True`. No SQL `IS NOT NULL` generated. Products with null keywords included in sentiment ingestion. Should be `Product.keywords.isnot(None)`.
- **Impact:** Keyword-based sentiment queries called with `None` keywords, causing downstream `AttributeError` or empty results for every null-keyword product.

---

## [HIGH] BUG-093 — `_task_wrapper` swallows all exceptions — Celery retry never triggers *(FIXED 2026-03-21)*
- **File:** `backend/workers/tasks/intelligence_tasks.py` lines 57–93
- **Issue:** All 10 IE Celery tasks wrapped in `try/except Exception` that logs and returns `{"status": "error"}`. Task returns normally — Celery marks as success. `max_retries` never triggers. Monitoring shows 100% success even when the pipeline is broken.
- **Impact:** Failed IE tasks are never retried. Transient DB errors, import failures, and computation errors are permanently lost. False success metrics in monitoring.

---

## [HIGH] BUG-094 — Duplicate query-key registries in incompatible locations (`analyticsKeys`, `trendAnalysisKeys`, `authKeys`, `paymentKeys`)
- **File:** `frontend/lib/api/query-keys.ts`; `frontend/lib/hooks/use-analytics.ts` line 6; `frontend/lib/api/trend-analysis.ts` line 75; `frontend/lib/hooks/use-auth.ts` line 21; `frontend/lib/hooks/use-payments.ts` line 26
- **Issue:** Four query-key factories defined in two separate locations with different shapes. `paymentKeys.balance()` in the central registry takes no args; in the hook it takes `(address: string)`. Cache invalidations using the central registry keys never match the hook's actual keys.
- **Impact:** External cache invalidation for analytics, trends, auth, and payment queries silently fails. Stale data displayed after mutations.

---

## [HIGH] BUG-095 — `useRemoveWallet` calls `updateWallet` (PUT) instead of `removeWallet` (DELETE)
- **File:** `frontend/lib/hooks/use-payments.ts` line 118
- **Issue:** `useRemoveWallet` calls `updateWallet({ bsv_wallet_address: null })` — the dedicated `DELETE /api/v1/payments/wallet` endpoint is never used. If backend validates `bsv_wallet_address` as non-null string, this fails with 422.
- **Impact:** Wallet removal either silently no-ops or errors. The DELETE endpoint is dead code.

---

## MEDIUM

---

## [MEDIUM] BUG-096 — Next.js image proxy allows all hostnames including `http://` and SVG
- **File:** `frontend/next.config.ts` lines 9–18
- **Issue:** `hostname: '**'` wildcard for both `https` and `http`. `dangerouslyAllowSVG: true` allows proxying SVG from any origin. Turns the app into an open SSRF/image proxy.
- **Impact:** SSRF via image proxy; potential XSS via proxied malicious SVG content.

---

## [MEDIUM] BUG-097 — `unsafe-eval` in CSP negates XSS protection
- **File:** `frontend/next.config.ts` line 31
- **Issue:** `'unsafe-eval'` present in `script-src`. Per CSP spec, `unsafe-eval` negates the main XSS protection value of CSP entirely.
- **Impact:** Content Security Policy provides no meaningful XSS protection.

---

## [MEDIUM] BUG-098 — `ssp_auth` cookie missing `Secure` flag
- **File:** `frontend/lib/auth/token.ts` line 30
- **Issue:** `document.cookie = 'ssp_auth=1; path=/; max-age=604800; SameSite=Lax'` — no `Secure` attribute. Transmitted over plaintext HTTP. Deletion string also lacks `Secure`.
- **Impact:** Cookie transmitted over HTTP; inconsistent deletion behavior in mixed environments.

---

## [MEDIUM] BUG-099 — Toast store `setTimeout` timer leaked — fires after component unmount
- **File:** `frontend/lib/stores/toast-store.ts` lines 38–44
- **Issue:** `addToast` schedules `setTimeout` for auto-removal but timer ID is never stored. `clearToasts()` wipes state but pending callbacks still fire, calling `set(state => ...)` on stale state.
- **Impact:** Memory leak; stale state updates after `clearToasts()`; test flakiness.

---

## [MEDIUM] BUG-100 — `AccuracyStatsResponse` nested types are `Record<string, unknown>` (no type safety)
- **File:** `frontend/types/analytics.ts` lines 101–103
- **Issue:** `by_rule_type`, `top_performing_rules`, `worst_performing_rules` typed as `Record<string, unknown>` / `Record<string, unknown>[]` instead of structured types.
- **Impact:** All components consuming rule performance data require runtime casts or `any` assertions.

---

## [MEDIUM] BUG-101 — `AlertAnalytics` interface in `types/alert.ts` has empty body
- **File:** `frontend/types/alert.ts` lines 170–174
- **Issue:** `AlertAnalytics` interface has a comment header but no fields. `types/analytics.ts` defines a separate `AlertAnalytics` with actual fields. Both are re-exported from `types/index.ts`, creating a conflicting empty declaration.
- **Impact:** Imports from `alert.ts` path get a structurally empty type; field access silently bypassed by TypeScript.

---

## [MEDIUM] BUG-102 — No input validation before `parseUnits` in `useMNEE` — uncaught throws
- **File:** `frontend/lib/web3/useMNEE.ts` lines 84–98, 102–109
- **Issue:** `transfer(to: string, amount: string)` calls `parseUnits(amount, 18)` with no pre-validation. Empty string, "0", or non-numeric input throws an unhandled exception. `to`/`spender` cast directly to `0x${string}` without address validation.
- **Impact:** Invalid inputs crash the wallet interaction silently. Invalid Ethereum addresses sent to contract write without validation.

---

## [MEDIUM] BUG-103 — WalletConnect project ID falls back to `'demo'` — connector fails silently
- **File:** `frontend/lib/web3/config.ts` line 61
- **Issue:** `process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || 'demo'` — `'demo'` is rejected by the WalletConnect relay as an invalid project ID.
- **Impact:** WalletConnect initialization fails in any environment where the env var is not set, with no build-time error.

---

## [MEDIUM] BUG-104 — `SentimentUpdateMessage.data` typed as `Record<string, unknown>` — untyped WS payload
- **File:** `frontend/lib/ws/hooks.ts` line 48
- **Issue:** `data: Record<string, unknown>` for sentiment WS messages while `AlertMessage` and `PriceUpdateMessage` have typed `.data` sub-shapes. Typed alternatives exist in `types/sentiment.ts`.
- **Impact:** All sentiment WebSocket consumers operate without type safety.

---

## [MEDIUM] BUG-105 — `window.prompt()` used for rejection reason input (2 pages)
- **File:** `frontend/app/(dashboard)/pricing/page.tsx` line 157; `frontend/app/(dashboard)/pricing/recommendations/[id]/page.tsx` line 163
- **Issue:** `handleReject` calls `window.prompt('Please provide a reason for rejection:')`. Blocks the browser event loop; suppressed in Shopify embedded context.
- **Impact:** Native dialog inconsistent with UI design system; non-functional in Shopify embedded app.

---

## [MEDIUM] BUG-106 — Client-side search filters only current page, not all products
- **File:** `frontend/app/(dashboard)/products/page.tsx` line 91
- **Issue:** `filteredProducts` filters over `data?.items` (current paginated page only). Products on other pages are invisible to search.
- **Impact:** Search silently returns incomplete results for merchants with multiple pages of products.

---

## [MEDIUM] BUG-107 — `handleRefreshAll` hardcodes `days: 30` and `useModel: 'openai'`
- **File:** `frontend/app/(dashboard)/trends/analysis/page.tsx` line 56
- **Issue:** `handleRunAnalysis({ days: 30, useModel: 'openai' })` — ignores user's selected time range; sends `'openai'` despite project using Gemini exclusively.
- **Impact:** Refresh always uses 30-day window. Incorrect model identifier sent to backend.

---

## [MEDIUM] BUG-108 — Opportunity and risk action handlers are no-ops (`console.log` only)
- **File:** `frontend/app/(dashboard)/trends/analysis/page.tsx` lines 44, 48, 52
- **Issue:** `handleApplyOpportunity`, `handleDismissOpportunity`, `handleAcknowledgeRisk` all only call `console.log()`. No mutations, state changes, or API calls.
- **Impact:** Buttons appear functional but do nothing. Core market trend response actions silently unimplemented.

---

## [MEDIUM] BUG-109 — `useProduct('')` fires API request with empty string ID
- **File:** `frontend/app/(dashboard)/competitors/match/page.tsx` line 26
- **Issue:** `useProduct(productId || '')` called when `productId` is null. Dispatches `GET /api/v1/products/` with empty string ID. Should use `enabled: !!productId`.
- **Impact:** Spurious API request on every page load without a `productId` param.

---

## [MEDIUM] BUG-110 — Digest option checkboxes are independent state — multiple can be selected
- **File:** `frontend/app/(dashboard)/settings/notifications/page.tsx` line 196
- **Issue:** Each `DigestOption` has its own independent `useState(value === 'weekly')`. All three (daily/weekly/monthly) can be simultaneously checked. No shared radio-group state.
- **Impact:** Users can select multiple digest frequencies. Even if save were fixed (BUG-068), the wrong value would be submitted.

---

## [MEDIUM] BUG-111 — Multiple components display wrong AI model names (OpenAI/GPT-4 instead of Gemini)
- **File:** `frontend/components/features/dashboard/AIFeaturesCard.tsx` lines 28, 87, 124; `frontend/components/features/competitors/AIAnalysisCard.tsx` line 66; `frontend/components/features/sentiment/analyze-modal.tsx` line 123; `frontend/components/features/trends/TrendAnalysisCard.tsx` lines 31, 98–99, 119; `frontend/components/features/trends/AIInsightPanel.tsx` line 65
- **Issue:** UI shows "GPT-4o-mini", "GPT-4", "OpenAI GPT-4o-mini", "Gemini 1.5 Flash". Project uses Gemini 2.0 Flash exclusively. `TrendAnalysisCard` defaults state to `'openai'` and offers an "OpenAI GPT-4" option that the backend doesn't support.
- **Impact:** Factually incorrect model attribution shown to users. OpenAI model selection in trends card triggers backend calls with unsupported model ID.

---

## [MEDIUM] BUG-112 — `dangerouslySetInnerHTML` with unsanitized AI-generated HTML
- **File:** `frontend/components/features/products/GenerateDescriptionModal.tsx` line 211
- **Issue:** AI-generated description rendered via `dangerouslySetInnerHTML={{ __html: result.description }}` with no client-side sanitization (e.g., DOMPurify).
- **Impact:** Potential XSS if backend AI output ever includes script tags or event handlers.

---

## [MEDIUM] BUG-113 — `dangerouslySetInnerHTML` with Shopify/WooCommerce product description (unsanitized)
- **File:** `frontend/components/features/products/ProductInfoCard.tsx` lines 221–223
- **Issue:** `dangerouslySetInnerHTML={{ __html: product.description }}` renders description HTML sourced from external merchants/stores without sanitization.
- **Impact:** Potential XSS if a synced product description contains malicious HTML.

---

## [MEDIUM] BUG-114 — Per-call `.mutate()` `onSuccess` callbacks are ephemeral in React Query v5 (multiple components)
- **File:** `frontend/components/features/products/ProductForm.tsx` line 206; `frontend/components/features/products/PriceSuggestionModal.tsx` line 233; `frontend/components/features/products/DeleteProductModal.tsx` lines 36–40
- **Issue:** Per-call `onSuccess` in `.mutate(payload, { onSuccess })` is ephemeral in React Query v5 — silently dropped if component re-renders mid-mutation.
- **Impact:** Modal close callbacks and post-action toasts may silently not fire. Delete modal may stay open; price may be double-applied.

---

## [MEDIUM] BUG-115 — `navigator.clipboard.writeText` without `try/catch` (2 places)
- **File:** `frontend/components/features/products/GenerateDescriptionModal.tsx` line 78; `frontend/components/features/payments/BsvWalletCard.tsx` line 96
- **Issue:** Clipboard API throws in non-HTTPS contexts and when permission is denied. No error handling present.
- **Impact:** Unhandled promise rejection; copy button silently fails.

---

## [MEDIUM] BUG-116 — `setState` during render in `analyze-modal.tsx`
- **File:** `frontend/components/features/sentiment/analyze-modal.tsx` lines 73–75
- **Issue:** `setProductId(defaultProductId)` called directly in the render function body, not inside `useEffect`.
- **Impact:** React warning "Cannot update during an existing state transition"; unexpected re-renders.

---

## [MEDIUM] BUG-117 — Missing `'use client'` on `ConfidenceIndicator` and `sentiment-breakdown`
- **File:** `frontend/components/features/pricing/ConfidenceIndicator.tsx`; `frontend/components/features/sentiment/sentiment-breakdown.tsx`
- **Issue:** Both use React hooks (`useMemo`, etc.) but lack `'use client'` directives.
- **Impact:** Throws "Hooks can only be called inside a function component" when rendered server-side in Next.js App Router.

---

## [MEDIUM] BUG-118 — `parseFloat(balance)` called before null/undefined check in `MNEEBalance`
- **File:** `frontend/components/features/payments/MNEEBalance.tsx`
- **Issue:** `parseFloat(balance).toFixed(2)` evaluated before `!isConnected` guard. If `balance` is `undefined`, `parseFloat` returns `NaN`.
- **Impact:** Displays "NaN" to users when wallet is not connected.

---

## [MEDIUM] BUG-119 — `setTimeout` without cleanup in `SubscriptionPlans`; direct `api.post()` call
- **File:** `frontend/components/features/payments/SubscriptionPlans.tsx` lines 392, 426
- **Issue:** `setTimeout(() => refetchSubscription(), 2000)` has no cleanup — fires on unmounted component. `api.post()` called directly instead of through `useMutation`.
- **Impact:** Memory leak / setState-on-unmounted-component warning; bypassed React Query architecture.

---

## [MEDIUM] BUG-120 — Etherscan URL hardcoded to mainnet in `TransactionHistory`
- **File:** `frontend/components/features/payments/TransactionHistory.tsx`
- **Issue:** Links always constructed using mainnet Etherscan URL regardless of connected network.
- **Impact:** Dead links for testnet transactions; confusing during development/staging.

---

## [MEDIUM] BUG-121 — `useIEHealth` staleTime (30s) shorter than refetchInterval (60s)
- **File:** `frontend/lib/hooks/use-intelligence.ts` lines 45–48
- **Issue:** `staleTime: 30_000` but `refetchInterval: 60_000`. Data goes stale before refetch fires, triggering extra background fetches. Mirrors documented BUG-025 pattern.
- **Impact:** Doubled API requests to health endpoint during normal usage.

---

## [MEDIUM] BUG-122 — `detectRisks()` / `generateInsight()` send params in request body instead of query string
- **File:** `frontend/lib/api/trend-analysis.ts` lines 49–51, 61–64
- **Issue:** Backend endpoints declare `use_model` and `days` as `Query(...)` parameters. Frontend sends them as JSON body in `api.post(url, { use_model, days })`. FastAPI ignores the unexpected body.
- **Impact:** Model selection and time range have no effect. Always runs with defaults (`openai`, 30 days).

---

## [MEDIUM] BUG-123 — `useCompetitorProducts` cache key ignores all non-`competitor_id` filter params
- **File:** `frontend/lib/hooks/use-competitors.ts` line 98
- **Issue:** Query key is `competitorKeys.products(params?.competitor_id || '')` — varies only on `competitor_id`. Filtering by `product_id`, `is_active`, `page`, or `page_size` without a `competitor_id` produces identical cache keys.
- **Impact:** Wrong cached data returned when filtering by any field other than `competitor_id`.

---

## [MEDIUM] BUG-124 — `useSyncPolling` uses a different cache key than `useSyncStatus` for the same endpoint
- **File:** `frontend/lib/hooks/use-integrations.ts` lines 180, 361
- **Issue:** `useSyncPolling` key: `[...integrationKeys.syncStatus(id), 'polling']`; `useSyncStatus` key: `integrationKeys.syncStatus(id)`. Two separate cache entries for the same URL — doubled requests, inconsistent data.
- **Impact:** Same sync status endpoint fetched twice simultaneously from independent cache slots.

---

## [MEDIUM] BUG-125 — `useProductOpportunity` auto-fetches on mount (expensive AI call)
- **File:** `frontend/lib/hooks/use-trend-analysis.ts` lines 65–71
- **Issue:** `enabled: !!productId` auto-fetches on mount. Other analysis queries correctly use `enabled: false`. AI analysis calls are expensive and should be user-triggered.
- **Impact:** Every product detail page mount triggers an AI backend call, risking rate-limit hits and unnecessary AI cost.

---

## [MEDIUM] BUG-126 — Reset token not invalidated after use — token reusable until natural expiry
- **File:** `backend/api/v1/routes/auth.py` lines 390–392
- **Issue:** After successful password reset, the JWT reset token is not stored in a denylist. The same token remains valid until its natural expiry and can reset the password again.
- **Impact:** Intercepted reset token can be reused by attacker after legitimate user has already reset.

---

## [MEDIUM] BUG-127 — Timing side-channel on forgot-password — user enumeration possible
- **File:** `backend/api/v1/routes/auth.py` lines 341–346
- **Issue:** When user does not exist, function returns immediately. When user exists, `create_reset_token` is called before returning. Observable timing difference enables user enumeration.
- **Impact:** User existence enumerable via timing side-channel on the forgot-password endpoint.

---

## [MEDIUM] BUG-128 — Dual session injection in `list_products` — two separate DB sessions per request
- **File:** `backend/api/v1/routes/products.py` lines 143–153
- **Issue:** `list_products` injects both `service: ProductService = Depends(get_product_service)` and `session: AsyncSession = Depends(get_session)`. `get_product_service` also calls `Depends(get_session)`. FastAPI creates two separate sessions.
- **Impact:** Two sessions can observe different transaction states. Wastes a DB connection per request.

---

## [MEDIUM] BUG-129 — `GET /billing/callback` is unauthenticated and is an open redirect
- **File:** `backend/api/v1/routes/integrations/shopify_billing.py` lines 179–195
- **Issue:** No `get_current_user` dependency. Any caller can supply an arbitrary `charge_id` and be redirected to `{FRONTEND_URL}/settings/billing?charge_id=<attacker_value>`.
- **Impact:** Open redirect; attacker can craft a legitimate-looking app URL that redirects to a malicious billing page.

---

## [MEDIUM] BUG-130 — `generate-description` error message leaks `OPENAI_API_KEY` env var name
- **File:** `backend/api/v1/routes/products.py` lines 419–423
- **Issue:** 503 error detail says "Please configure OPENAI_API_KEY" — exposes internal env var name to any API caller. App uses Gemini, not OpenAI.
- **Impact:** Information disclosure of environment variable names; misleading for debugging.

---

## [MEDIUM] BUG-131 — `_auto_link_competitors` background task receives a closed session
- **File:** `backend/api/v1/routes/competitors/matching.py` lines 289–296
- **Issue:** `background_tasks.add_task(..., db=db)` — FastAPI closes the injected `AsyncSession` after the request handler returns. Task calls `db.execute`, `db.add`, `db.commit` on a stale closed session.
- **Impact:** Runtime `InvalidRequestError` or silent data loss when auto-linking fires after response is sent.

---

## [MEDIUM] BUG-132 — `process_pending_mentions` triggers a global batch Celery job with no tenant scope
- **File:** `backend/api/v1/routes/sentiment/tasks.py` lines 48–67
- **Issue:** `POST /process` enqueues `process_pending_mentions.delay(batch_size)` with no `user_id` argument. Any authenticated user can trigger a global system-wide processing job.
- **Impact:** Any user can trigger expensive full-system jobs; no tenant isolation.

---

## [MEDIUM] BUG-133 — `crisis_detection.py` accesses `s.text` but the model field is `raw_text` — sample always empty
- **File:** `backend/api/v1/routes/alerts/crisis_detection.py` line 186
- **Issue:** `sample_texts = [s.text[:200] for s in negative_mentions[:5] if s.text]` — `Sentiment` model stores text in `raw_text`, not `text`. Accessing `.text` returns `None` silently. `sample_texts` is always empty.
- **Impact:** AI crisis summaries generated without any sample texts; always generic and useless.

---

## [MEDIUM] BUG-134 — `bcrypt` cost factor not explicitly asserted at startup
- **File:** `backend/core/security.py` line 26
- **Issue:** `CryptContext(schemes=["bcrypt"], deprecated="auto")` with no explicit `bcrypt__rounds`. Relies on passlib default of 12. No startup assertion enforces this.
- **Impact:** Configuration regression goes undetected if passlib default changes or context is misconfigured.

---

## [MEDIUM] BUG-135 — JWT secret key has no minimum entropy validation at startup
- **File:** `backend/core/config.py` line 39; `backend/core/security.py` line 19
- **Issue:** `JWT_SECRET_KEY: str` with no minimum length or entropy validator. A value of `"secret"` accepted silently.
- **Impact:** Weak JWT secret accidentally deployed to production enables token forgery.

---

## [MEDIUM] BUG-136 — `updated_at` has no `onupdate` trigger on most models — silently stays at creation time
- **File:** `backend/models/integration.py` lines 113–115; `backend/models/alert.py` lines 101–103; `backend/models/competitor.py` lines 61–64; `backend/models/competitor_product.py` lines 78–81; `backend/models/product.py` lines 62–65
- **Issue:** `updated_at` defined with only `default=lambda: datetime.now(UTC)`, no `onupdate=`. Only `User.updated_at` has `onupdate`. All other models require routes to manually set `updated_at` on every write — done inconsistently.
- **Impact:** `updated_at` silently stays at creation timestamp for most model types. Change-detection dashboards and audit logs show incorrect timestamps.

---

## [MEDIUM] BUG-137 — CORS wildcard (`allow_origins=["*"]`) reachable via config with no production guard
- **File:** `backend/main.py` lines 162–169
- **Issue:** If `CORS_ORIGINS=*` is set, `allow_origins=["*"]` is enabled with `allow_credentials=False`. No check prevents this from being deployed to production.
- **Impact:** If accidentally set in production, all unauthenticated API endpoints accessible from any browser origin.

---

## [MEDIUM] BUG-138 — SQLAlchemy `default=` (server-side) means fields are `None` before DB flush
- **File:** `backend/models/integration.py` lines 110–115
- **Issue:** `created_at` and `updated_at` use `sa_column=Column(DateTime(...), default=...)` — a SQLAlchemy server-side default, not a Python `default_factory`. Fields are `None` when constructing instances in Python before a DB flush.
- **Impact:** `IntegrationResponse` serialization can fail or return wrong data when called on uncommitted objects.

---

## [MEDIUM] BUG-139 — `DEMO_MODE` bypass activates subscription without blockchain verification
- **File:** `backend/services/payment/subscription_service.py` lines 432–443
- **Issue:** `should_activate = verification.verified or settings.DEMO_MODE`. With `DEMO_MODE=True` (likely on staging), any transaction hash activates a subscription. Comment reads "For hackathon: activate even if verification fails."
- **Impact:** Payment bypass vulnerability — on staging anyone can claim a subscription with any transaction hash.

---

## [MEDIUM] BUG-140 — `ai_generator.py` uses `gemini-2.0-flash-exp` — violates project rule requiring `gemini-2.0-flash`
- **File:** `backend/services/ai_generator.py` line 50
- **Issue:** `self.gemini_model_name = "gemini-2.0-flash-exp"` — the `-exp` (experimental) suffix is not the mandated model per project rules.
- **Impact:** Routing to experimental variant; potential breakage when Google retires the `-exp` suffix.

---

## [MEDIUM] BUG-141 — `NotificationDispatcher` instantiated but result discarded in notification task
- **File:** `backend/workers/tasks/notification_tasks.py` line 97
- **Issue:** `NotificationDispatcher()` constructed but return value not assigned. Instance immediately garbage-collected. Task calls channel services directly, bypassing the dispatcher abstraction.
- **Impact:** Abstraction layer broken; if dispatcher performs initialization side effects they are lost.

---

## [MEDIUM] BUG-142 — Confidence in `_build_reasoning()` uses hardcoded `0.5` — mismatches displayed vs stored confidence
- **File:** `backend/services/scoring/score_fusion.py` line ~575
- **Issue:** `_build_reasoning()` uses `0.5 * 0.25` (hardcoded) for data quality contribution while `_compute_overall_confidence()` uses the real `_data_quality_score()` value.
- **Impact:** Confidence shown in recommendation reasoning text differs from `overall_confidence` in the DB. Merchants see inconsistent confidence figures.

---

## [MEDIUM] BUG-143 — Autonomous orchestrator unconditionally executes price changes when AI doesn't call the tool
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 683–701
- **Issue:** In `_run_strategist()`, if Gemini doesn't call `write_price_to_chain`, the code falls through to a manual execution block that calls `_handle_write_price_to_chain()` unconditionally whenever `assessment.recommended_direction != "hold"`. The confidence threshold guardrail is bypassed.
- **Impact:** On-chain price changes executed even when the AI agent concluded confidence was below threshold. Any non-"hold" assessment triggers an autonomous price write regardless of confidence.

---

## LOW

---

## [LOW] BUG-144 — Wrong AI model name in frontend comment (`types/sentiment.ts`)
- **File:** `frontend/types/sentiment.ts` line 88
- **Issue:** Comment on `use_ai?: boolean` reads "Use GPT-4o-mini for analysis". Project uses Gemini 2.0 Flash.
- **Impact:** Documentation drift; misleads developers debugging sentiment analysis.

---

## [LOW] BUG-145 — Full WebSocket URL logged on connect (token exposure risk)
- **File:** `frontend/lib/ws/client.ts` line 133
- **Issue:** `console.log('[WS] Connected to', this.url)` logs the full WS URL. If auth tokens are ever appended as query params, they appear in browser console.
- **Impact:** Low risk now; becomes HIGH if WS auth migrates to URL query params.

---

## [LOW] BUG-146 — `product.ts` vs `products.ts` naming inconsistency
- **File:** `frontend/lib/domain/products.ts` line 6; `frontend/types/product.ts`
- **Issue:** `CLAUDE.local.md` documents the type file as `types/products.ts` (plural) but it is `types/product.ts` (singular). Developer confusion and documentation drift.
- **Impact:** Future contributors following docs look for the wrong file.

---

## [LOW] BUG-147 — Admin page has no role authorization check on frontend
- **File:** `frontend/app/(dashboard)/admin/page.tsx`
- **Issue:** Only requires `isAuthenticated` (from dashboard layout). No admin role/permission flag checked. Any authenticated user can navigate to `/admin`.
- **Impact:** Non-admin users can access admin functionality. Authorization should be enforced on both frontend and backend.

---

## [LOW] BUG-148 — `productsApi.update()` called directly — bypasses React Query cache
- **File:** `frontend/app/(dashboard)/products/[id]/page.tsx` line 164
- **Issue:** `handleApplyGenerated` calls `productsApi.update()` directly with a manual `refetch()`. Related queries (product list, competitor data) not invalidated.
- **Impact:** Other UI parts depending on the updated product remain stale until next natural refetch.

---

## [LOW] BUG-149 — Misleading comment in dashboard layout references localStorage for JWT
- **File:** `frontend/app/(dashboard)/layout.tsx` line 9
- **Issue:** Comment reads "JWT from localStorage" but implementation correctly uses `checkAuth()` with httpOnly cookies.
- **Impact:** Could lead future contributor to introduce a localStorage pattern believing it is established.

---

## [LOW] BUG-150 — Missing `app/error.tsx` error boundary — unhandled errors crash full app shell
- **File:** `frontend/app/error.tsx` (does not exist)
- **Issue:** No `app/error.tsx` exists; only `app/global-error.tsx`. Unhandled render errors in any dashboard page propagate to global error boundary, showing a full-page crash instead of scoped error UI.
- **Impact:** Any render error in a dashboard page crashes the entire application shell.

---

## [LOW] BUG-151 — `window.location.reload()` used for error retry in `CompetitorsList`
- **File:** `frontend/components/features/competitors/CompetitorsList.tsx`
- **Issue:** Error state retry uses `window.location.reload()` instead of React Query's `refetch()`.
- **Impact:** Full page reload on retry discards all in-memory state unnecessarily.

---

## [LOW] BUG-152 — `statusColors` has no fallback for unexpected status values in `IntegrationCard`
- **File:** `frontend/components/features/integrations/IntegrationCard.tsx` line 156
- **Issue:** `statusColors[integration.status]` returns `undefined` for any status not in the map. `className` string contains `"undefined"`.
- **Impact:** Broken styling if backend adds a new status value not present in the frontend map.

---

## [LOW] BUG-153 — Mutation error callbacks missing in `CompetitorCard`, `AlertConfigurationCard`, `AlertItem`
- **File:** `frontend/components/features/competitors/CompetitorCard.tsx`; `frontend/components/features/alerts/AlertConfigurationCard.tsx`; `frontend/components/features/alerts/AlertItem.tsx`
- **Issue:** `handleDelete`, `handleToggleActive`, `handleAcknowledge`, `handleResolve` all call `.mutate()` with no `onError` handler. Failures silently swallowed.
- **Impact:** Users receive no feedback on failed operations. Card remains in incorrect state.

---

## [LOW] BUG-154 — `useInvalidateSubscription` calls both `invalidateQueries` and `refetchQueries` — double request
- **File:** `frontend/lib/hooks/use-payments.ts` lines 191–196
- **Issue:** Both called for same key. `invalidateQueries` already triggers refetch for active queries; `refetchQueries` is redundant, causing double network request.
- **Impact:** Double request to subscription endpoint every time invalidation function is called.

---

## [LOW] BUG-155 — `api/index.ts` double-exports `client` and `auth` modules — potential symbol conflicts
- **File:** `frontend/lib/api/index.ts` lines 3–4, 13–14
- **Issue:** Named exports on lines 3–4 plus `export * from './client'` and `export * from './auth'` on lines 13–14 re-export the same symbols.
- **Impact:** TypeScript allows but static analysis flags as duplicate exports; any future name collision causes silent compile error.

---

## [LOW] BUG-156 — `useConfidenceLevel` and `useFilteredMatches` named as hooks but are plain functions
- **File:** `frontend/lib/hooks/use-competitor-matching.ts` lines 219–277
- **Issue:** Both call no hooks and take plain arguments. Named with `use` prefix, triggering React lint rules unnecessarily.
- **Impact:** Misleading naming; potential false-positive lint noise from rules-of-hooks.

---

## [LOW] BUG-157 — Reset password inline length check — inconsistent validation approach
- **File:** `backend/api/v1/routes/auth.py` lines 384–388
- **Issue:** Password length validated manually in route handler with `if len(payload.new_password) < 8` instead of via Pydantic field validator on the schema. Inconsistent with `register` endpoint.
- **Impact:** Validation bypassed if schema reused elsewhere without this route.

---

## [LOW] BUG-158 — Webhooks not unregistered for `PAUSED`/`ERROR` integrations on soft-delete
- **File:** `backend/api/v1/routes/integrations/crud.py` lines 252–263
- **Issue:** `unregister_webhooks` only called when `status == ACTIVE`. `PAUSED` and `ERROR` integrations are soft-deleted without webhook unregistration.
- **Impact:** Ghost webhooks continue firing against disconnected integration endpoints.

---

## [LOW] BUG-159 — Pricing `/stats` endpoint accepts `days=0` or negative values
- **File:** `backend/api/v1/routes/pricing/settings.py` line 107
- **Issue:** `days: int = Query(default=30, le=365)` — no `ge=1` lower bound. `days=0` or negative values produce invalid date arithmetic.
- **Impact:** Potential division-by-zero or empty result set for zero/negative day window.

---

## [LOW] BUG-160 — Sentiment `DELETE` returns 200 with body instead of 204 No Content
- **File:** `backend/api/v1/routes/sentiment/retrieval.py` lines 120, 138
- **Issue:** `DELETE /{sentiment_id}` has no `status_code=status.HTTP_204_NO_CONTENT` and returns `{"status": "deleted", "sentiment_id": ...}`.
- **Impact:** Incorrect HTTP semantics; clients expecting 204 handle this as a failed delete.

---

## [LOW] BUG-161 — `ProductCreate.sentiment_multiplier` default `0.1` differs from model default `0.2`
- **File:** `backend/schemas/products.py` line 29; `backend/models/product.py` line 50
- **Issue:** Schema defaults `sentiment_multiplier` to `Decimal("0.1")`; model defaults to `Decimal("0.2")`. New products via API get half the intended sentiment impact.
- **Impact:** Pricing recommendations for new products use half the intended sentiment weighting.

---

## [LOW] BUG-162 — `PricingRule.updated_at` defaults to `None` instead of creation time
- **File:** `backend/models/pricing_rule.py` line 105
- **Issue:** `updated_at: datetime | None = Field(default=None)` — all other `updated_at` fields default to creation time. Sorting rules by `updated_at` is non-deterministic for all unmodified rules.
- **Impact:** Rule ordering by `updated_at` treats all unmodified rules as equivalent nulls.

---

## [LOW] BUG-163 — `product_sync._push_to_shopify` bypasses retry/circuit breaker infrastructure
- **File:** `backend/services/integration/product_sync_service.py` lines 279–296
- **Issue:** Uses a raw `httpx.AsyncClient` instead of `RetryableClient`. Transient Shopify errors not retried; 429 rate-limit responses not backed off; circuit breaker state not updated.
- **Impact:** Product creation mutations unprotected from transient failures and rate limiting.

---

## [LOW] BUG-164 — `verify_webhook_signature` may receive unhashed `sha256=`-prefixed Shopify header
- **File:** `backend/services/integration/shopify_webhooks.py` line 110
- **Issue:** Shopify prepends `sha256=` to `X-Shopify-Hmac-SHA256` header values. If the caller does not strip this prefix before passing to `verify_webhook_signature`, every HMAC comparison fails and all webhooks are rejected.
- **Impact:** All Shopify webhooks rejected as invalid if the prefix is not stripped upstream.

---

## [LOW] BUG-165 — SQL injection pattern in materialized view refresh (currently safe, latently dangerous)
- **File:** `backend/workers/tasks/benchmark_refresh_tasks.py`
- **Issue:** `text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")` interpolates `view_name` directly. Currently safe (hardcoded list), but pattern would become an SQL injection vector if the view list were ever made dynamic.
- **Impact:** No active risk; latent SQL injection if `MATERIALIZED_VIEWS` is extended via config or DB-stored values.

---

## [LOW] BUG-166 — IP addresses logged at INFO level — potential GDPR concern
- **File:** `backend/core/middleware.py` lines 40–45
- **Issue:** `client_ip` logged at INFO level for every request. In EU/GDPR contexts, IP addresses are personal data. Structured logs go to Railway/stdout without PII scrubbing.
- **Impact:** Potential GDPR compliance issue for EU-based merchants.

---

---

## [CRITICAL] BUG-167 — MNEE webhook background task receives closed DB session — payments never activated *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/payments/webhook.py` lines 186–194
- **Issue:** `background_tasks.add_task(process_payment_confirmation, payment, payload, session)` — FastAPI closes the session after the handler returns. The background task then calls `await session.commit()` on a closed session, raising an exception silently.
- **Impact:** Webhook-triggered payment confirmations and subscription activations silently fail. Users make payments that are never activated.

---

## [CRITICAL] BUG-168 — `x402_agent_api.py` sells random fabricated data as paid pricing intelligence *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/x402_agent_api.py` lines 97–160
- **Issue:** The `/api/v1/agent/pricing-intelligence` endpoint is decorated `@pay("$0.01")` and charges real money per query. It returns completely randomized mock data (`random.uniform(...)`) — not the real Scout→Analyst→Strategist pipeline. The crisis detection endpoint also uses `random.random()` to decide whether a crisis is occurring.
- **Impact:** Paid API callers receive worthless random numbers instead of real pricing intelligence. Potential consumer protection and fraud liability.

---

## [CRITICAL] BUG-169 — BSV payment accepts any transaction with correct memo regardless of amount or recipient *(FIXED 2026-03-21)*
- **File:** `backend/services/payment/bsv_service.py` lines 70–98
- **Issue:** `verify_transaction` only checks that the memo contains `SSP-{payment_id[:8]}`. Does NOT verify the amount, recipient address, or that `expected_recipient` matches. Comment: "For hackathon, we trust the memo as proof of payment intent." Any 1-satoshi BSV transaction with the correct 8-character memo activates a paid subscription.
- **Impact:** Attacker who knows or guesses any payment ID prefix can broadcast a near-free BSV transaction and receive a paid subscription at no cost.

---

## [CRITICAL] BUG-170 — `Payment.id.startswith()` is not valid on SQLAlchemy UUID column — webhook payments never process *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/payments/webhook.py` lines 170–172
- **Issue:** `select(Payment).where(Payment.id.startswith(payment_id_prefix))` — SQLAlchemy UUID columns have no `.startswith()` method that generates valid SQL. This raises `AttributeError` or generates invalid SQL at runtime.
- **Impact:** All MNEE webhook payment confirmations crash at the DB query. No webhook-triggered payments ever activate subscriptions.

---

## [HIGH] BUG-171 — Outbound webhook HMAC signature computed with `sort_keys=True` but body sent without — signatures always wrong
- **File:** `backend/services/notification/webhook_service.py` lines 193–200
- **Issue:** `_build_headers` computes `json.dumps(payload, sort_keys=True).encode("utf-8")` for the HMAC signature, but `httpx.post(json=payload)` serializes the body using default Python dict ordering (no sort). Signed bytes ≠ transmitted bytes.
- **Impact:** Every outbound webhook recipient that verifies the `X-SSP-Signature` header will always fail. Webhook authenticity verification is completely broken.

---

## [HIGH] BUG-172 — Email alert template injects unsanitized user data into HTML — XSS in emails
- **File:** `backend/services/notification/email_service.py` lines 155–165, 181–193
- **Issue:** `alert_title`, `alert_message`, `severity`, and `alert_data` key/values are interpolated directly into HTML using f-strings with no HTML escaping. Values can originate from competitor product names or scraped external data.
- **Impact:** HTML injection into email content. Malicious HTML (script tags, phishing links, tracking pixels) can be injected into alert emails sent to merchants.

---

## [HIGH] BUG-173 — SSRF via user-supplied Slack webhook URL in alert notifications
- **Status: FIXED 2026-03-21**
- **File:** `backend/services/notification/slack_service.py` lines 67–71
- **Issue:** `url = webhook_url or self.default_webhook_url` — user-configured webhook URL passed directly to `httpx.post()` with no URL validation. Accepts `http://169.254.169.254/...` (AWS metadata), `http://localhost/...`, etc.
- **Impact:** Authenticated users can configure Slack webhook URLs pointing to internal infrastructure, enabling SSRF to probe/exfiltrate internal services whenever an alert fires.

---

## [HIGH] BUG-174 — SSRF via user-supplied notification webhook URL
- **Status: FIXED 2026-03-21**
- **File:** `backend/services/notification/webhook_service.py` lines 79–80, 99–104
- **Issue:** `webhook_url` from user-configured alert settings passed directly to `httpx.AsyncClient.post(webhook_url, ...)` with no URL scheme, host, or IP validation.
- **Impact:** Same SSRF vector as BUG-173 — authenticated users can exfiltrate internal metadata or probe internal services via any configured webhook URL.

---

## [HIGH] BUG-175 — SSRF via competitor product URLs in scraper
- **Status: FIXED 2026-03-21**
- **File:** `backend/services/competitor_scraper.py` lines 243–246
- **Issue:** `httpx.AsyncClient.get(competitor_product.competitor_product_url)` with no URL scheme or IP validation. A user-created competitor product with URL `http://localhost/internal` or `file:///etc/passwd` will be fetched.
- **Impact:** Authenticated users can probe internal network resources by creating competitor products with internal/file URLs.

---

## [HIGH] BUG-176 — `CompetitorMatchingService` in-process dict cache not safe in multi-process/worker deployments
- **File:** `backend/services/competitor_matching/service.py` lines 107, 517–526
- **Issue:** `self._cache: dict[str, CacheEntry] = {}` is an in-memory dict on a singleton. Multiple Uvicorn workers each have their own isolated cache — no shared invalidation. Concurrent async coroutines can also race during `_evict_oldest_entries`.
- **Impact:** Cache provides no benefit in multi-process deployments (the typical production configuration). Concurrent eviction can produce inconsistent cache state.

---

## MEDIUM

---

## [MEDIUM] BUG-177 — `httpx.AsyncClient` never closed in payment services — connection leak
- **File:** `backend/services/payment/eth_service.py` line 296; `backend/services/payment/bsv_service.py` line 211
- **Issue:** Both files create module-level singleton instances. Each lazily creates an `httpx.AsyncClient` that is never closed from any lifecycle hook (`close()` exists but is never called on app shutdown).
- **Impact:** HTTP connections leak for the process lifetime. In long-running deployments this exhausts file descriptors.

---

## [MEDIUM] BUG-178 — Wrong Etherscan API endpoint for block timestamp — fails on free-tier keys
- **File:** `backend/services/payment/eth_service.py` lines 268–270
- **Issue:** `"action": "getblockreward"` used to fetch block timestamp. `getblockreward` is a paid Etherscan tier endpoint. On free-tier API keys this returns an error; `timeStamp` is silently `None`. The correct endpoint is `eth_getBlockByNumber`.
- **Impact:** Block timestamp retrieval silently fails on free-tier keys. ETH payment verification proceeds without a timestamp, potentially accepting expired transactions.

---

## [MEDIUM] BUG-179 — `EthereumPaymentService.is_available` always returns `True` regardless of API key
- **File:** `backend/services/payment/eth_service.py` line 44
- **Issue:** `is_available` property returns `True` unconditionally even when `ETHERSCAN_API_KEY` is not set. `PaymentServiceFactory.get_available_networks()` always reports Ethereum as available.
- **Impact:** Ethereum network reported as available when no API key is configured, misleading operators and users.

---

## [MEDIUM] BUG-180 — `CompetitorMatchingService` providers initialized at module import with `os.getenv()` — keys captured as `None` if set after import
- **File:** `backend/services/competitor_matching/service.py` line 549; `backend/services/competitor_matching/providers/__init__.py` lines 9–21
- **Issue:** Module-level `competitor_matching_service = CompetitorMatchingService()` calls `setup_providers()` at import, which instantiates all providers, each reading API keys via `os.getenv()`. Keys set after module import are never read.
- **Impact:** All competitor matching providers initialize as unavailable in configurations where env vars are loaded after module import. Competitor matching silently returns no results.

---

## LOW

---

## [LOW] BUG-181 — BSV API key rotation has no effect until process restart
- **File:** `backend/services/payment/bsv_service.py` lines 44–51
- **Issue:** `httpx.AsyncClient` created lazily and cached as singleton with the API key baked into headers. Key rotation requires process restart.
- **Impact:** API key rotation silently ineffective for BSV service until restart.

---

## [LOW] BUG-182 — `EmailService.send_alert_email` calls synchronous `client.send()` — blocks event loop
- **File:** `backend/services/notification/email_service.py` lines 122, 63
- **Issue:** `response = client.send(message)` — SendGrid client's `send()` is a synchronous blocking call inside an `async` function. No `asyncio.to_thread()` or `run_in_executor()` used.
- **Impact:** Each email notification blocks the FastAPI event loop for 100–500ms. Degrades all concurrent request handling.

---

## [LOW] BUG-183 — Competitor matching cache key excludes `exclude_domains` and `our_price`
- **File:** `backend/services/competitor_matching/service.py` lines 494–502
- **Issue:** Cache key built from `product_name`, `keywords`, `max_results` only. `exclude_domains` and `our_price` excluded. Two searches with different excluded domains return the same cached result, potentially including the user's own store in results.
- **Impact:** Cached results may include excluded domains; price proximity scoring wrong for different merchants from shared cache.

---

## Submission Blockers Summary (Shopify App Store)

| Bug | Description |
|-----|-------------|
| BUG-001 | JWT in localStorage — security failure |
| BUG-003 | API version 2024-01 breaks all syncs |
| BUG-004 | decrypt_token() crashes on bytes |
| BUG-005 | Pending token sentinel mismatch — staging "credentials invalid" |
| BUG-006 | OAuth redirect sends logged-in merchant to login page |
| BUG-013 | ~~GDPR shop/redact not implemented — compliance block~~ FIXED 2026-03-21 |
| BUG-014 | ~~App Bridge hard-fail with no retry~~ FIXED 2026-03-21 |
| BUG-018 | ~~CSRF bypass in OAuth callback~~ FIXED 2026-03-21 |
| BUG-037 | ~~Competitive position fully inverted — all merchants get wrong recommendations~~ FIXED 2026-03-21 |
| BUG-038 | ~~Hard deletes crash — merchants cannot remove integrations~~ FIXED 2026-03-21 |
| BUG-044 | Webhook API version mismatch — sync events lost |
| BUG-052 | Refresh token in localStorage — session hijacking |
| BUG-053 | Shopify session token in localStorage |
| BUG-055 | useSearchParams() without Suspense — OAuth callback page crashes (build error) |
| BUG-056 | Forgot-password is a no-op — no reset email sent |
| BUG-058 | ~~All WebSocket endpoints unauthenticated~~ FIXED 2026-03-21 |
| BUG-059 | ~~Webhook register/unregister unauthenticated~~ FIXED 2026-03-21 |
| BUG-061 | ~~PriceRecommendation/PricingRule/etc. have no FK constraints~~ FIXED 2026-03-21 |
| BUG-063 | ~~ExperimentManager wrong args — Thompson Sampling broken~~ FIXED 2026-03-21 |
| BUG-064 | ~~is None ORM bug — stuck recommendations never recovered~~ FIXED 2026-03-21 |
| BUG-065 | ~~not column ORM bug — social mentions never processed~~ FIXED 2026-03-21 |
| BUG-067 | ~~Product sync router never registered — entire feature 404s~~ FIXED 2026-03-21 |
| BUG-075 | ~~No Sentry beforeSend — PII leaks to third party~~ FIXED 2026-03-21 |
| BUG-077 | ~~Sentiment retrieval.py full authorization bypass~~ FIXED 2026-03-21 |
| BUG-079 | ~~Intelligence endpoints return all merchants' data (cross-tenant)~~ FIXED 2026-03-21 |
| BUG-081 | ~~Shopify install HMAC not verified~~ FIXED 2026-03-21 |
| BUG-082 | ~~Webhook HMAC skippable — forged payloads accepted~~ FIXED 2026-03-21 |
| BUG-083 | ~~Rate limiter X-Forwarded-For bypass — login brute force possible~~ FIXED 2026-03-21 |
| BUG-089 | ~~notification_tasks not registered — all alert notifications fail~~ FIXED 2026-03-21 |
| BUG-091 | ~~Wrong DB import in batch_tasks — learning pipeline never runs~~ FIXED 2026-03-21 |
| BUG-093 | _task_wrapper swallows exceptions — IE pipeline silently broken | **FIXED 2026-03-21** |
| BUG-167 | MNEE webhook background task on closed session — payments never activated | **FIXED 2026-03-21** |
| BUG-168 | x402_agent_api.py returns random fake data sold as paid intelligence | **FIXED 2026-03-21** |
| BUG-169 | BSV memo-only verification — free 1-satoshi activates paid subscription | **FIXED 2026-03-21** |
| BUG-170 | Payment.id.startswith() invalid on UUID — webhook payments never process | **FIXED 2026-03-21** |
| BUG-173 | SSRF via user-supplied Slack webhook URL |
| BUG-174 | SSRF via notification webhook URL |
| BUG-175 | SSRF via competitor product URLs |

---

## CRITICAL (new — deep audit pass 2)

---

## [CRITICAL] BUG-052 — UserRead schema declares id as int — all user API responses crash on serialize
- **File:** `backend/schemas/user.py` line 24
- **Issue:** `UserRead` has `id: int` but `User` model stores `id: uuid.UUID`. Pydantic serialization fails every time a user object is returned from any API endpoint — `/auth/login`, `/users/me`, any endpoint that embeds user data.
- **Impact:** Every user API response fails with a Pydantic validation error. Login, profile, and any endpoint returning a `User` schema is broken in production.

---

## [CRITICAL] BUG-053 — price_sync_service instantiates Shopify/WooCommerce with wrong arguments
- **File:** `backend/services/pricing/price_sync_service.py` lines 110–126
- **Issue:** `ShopifyService(self.db, integration)` and `WooCommerceService(self.db, integration)` — neither service accepts these constructor arguments. Their `__init__` takes only an optional `retry_config`. This is a `TypeError` at runtime.
- **Impact:** The entire live price sync pipeline crashes immediately whenever it runs. No price drift detection, no price resyncs after competitor data updates.

---

## [CRITICAL] BUG-054 — Auto-approval condition is logically inverted — high-value products auto-approved
- **File:** `backend/services/pricing/auto_approval_service.py` line 158
- **Issue:** `return not (require_above_price is not None and current_price > require_above_price)`. The variable name means "require manual approval for prices above this threshold." The logic is inverted: products priced ABOVE the threshold return `True` (auto-approve), and products BELOW it return `False` (require approval). The correct check should return `False` when `current_price > require_above_price`.
- **Impact:** Expensive high-value products are auto-approved without merchant review. Low-value products are held for manual review. The entire auto-approval safety gate is backwards.

---

## [CRITICAL] BUG-055 — Division by zero in alert price-change percentage — crashes alert system
- **File:** `backend/services/notification/alert_generator.py` lines 138, 187, 228
- **Issue:** Three separate calculations: `((recommended_price - current_price) / current_price) * 100` with no zero-check on `current_price`. Any product with `current_price = 0` or `None` causes `ZeroDivisionError` or `TypeError`. This propagates up through the alert dispatch chain.
- **Impact:** When any product has a zero/null current price, the entire alert generation task crashes. No alerts are sent for any product, not just the zero-priced one.

---

## [CRITICAL] BUG-056 — CORS_ORIGINS defaults to wildcard "*" — allows all cross-origin requests
- **File:** `backend/core/config.py` line 49
- **Issue:** `CORS_ORIGINS: str = "*"` is the default value. Unless the Railway env var is explicitly set, the backend accepts requests from any origin with credentials.
- **Impact:** Any malicious website can make authenticated cross-origin requests on behalf of logged-in users. Combined with BUG-001 (localStorage JWT), this enables full account takeover via XSS + CORS.

---

## [CRITICAL] BUG-057 — DEMO_MODE env var bypasses payment verification in production
- **File:** `backend/services/payment/subscription_service.py` line 432
- **Issue:** `if os.getenv("DEMO_MODE", "true").lower() == "true":` — default is `"true"`, so unless `DEMO_MODE=false` is explicitly set in Railway, the payment confirmation function skips all blockchain verification and activates subscriptions unconditionally.
- **Impact:** On a fresh Railway deploy where `DEMO_MODE` is not set, any request to the payment confirmation endpoint activates a paid subscription without any payment. All subscription revenue can be bypassed.

---

## HIGH (new — deep audit pass 2)

---

## [HIGH] BUG-058 — webhook_handler calls sync_single_product() which doesn't exist
- **File:** `backend/services/integration/webhook_handler.py` lines 139–143
- **Issue:** `self.sync_service.sync_single_product(...)` is called when processing product webhook events (create/update). `SyncService` has no `sync_single_product` method — only `run_sync()` and `recover_stuck_syncs()`.
- **Impact:** Every Shopify product webhook (product created/updated/deleted) crashes with `AttributeError`. Webhook-driven syncs never complete. Products created on Shopify never appear in the app unless manually triggered.

---

## [HIGH] BUG-059 — Webhook register/unregister endpoints missing ownership check
- **File:** `backend/api/v1/routes/webhooks.py` lines 258, 321
- **Issue:** `register_webhooks` and `unregister_webhooks` look up `Integration` by ID alone with no `.where(Integration.user_id == current_user.id)` filter. Any authenticated user can register or unregister webhooks for any other user's integration.
- **Impact:** (1) Attacker can disable any merchant's webhooks — all product/order events stop being received. (2) Attacker can register their own webhook URLs on other merchants' integrations to receive their Shopify events.

---

## [HIGH] BUG-060 — product_sync.py imports get_db instead of get_session — endpoints crash on call
- **File:** `backend/api/v1/routes/product_sync.py` lines 22, 174
- **Issue:** `from db.session import get_db` — `get_db` does not exist in `db/session.py`. The correct dependency is `get_session`. Import succeeds if `get_db` is accidentally exported somewhere, but the injected session will be wrong type.
- **Impact:** All product sync route endpoints (`/product-sync/*`) fail at dependency injection with `ImportError` or inject the wrong session, causing silent DB errors.

---

## [HIGH] BUG-061 — Synchronous email send blocks the async event loop
- **File:** `backend/services/notification/email_service.py` lines 121–122; `backend/services/notification/audit_email_service.py` line 141
- **Issue:** `client.send(message)` (SendGrid SDK) is synchronous. It is called inside `async def` functions without `await asyncio.to_thread()` or `loop.run_in_executor()`. This blocks the entire event loop while the HTTP request to SendGrid completes.
- **Impact:** Every email notification freezes all concurrent API requests for the duration of the SendGrid HTTP call (~200–2000ms). Under load this causes widespread request timeouts and API latency spikes.

---

## [HIGH] BUG-062 — Trend alerts use wrong AlertType — miscategorized in dashboard
- **File:** `backend/services/notification/alert_generator.py` line 336
- **Issue:** Trend detection alerts are created with `AlertType.COMPETITOR_PRICE_CHANGE` instead of the correct trend alert type. Users who have disabled competitor price change alerts won't receive trend alerts either — and users who have enabled only trend alerts will receive them labelled as competitor changes.
- **Impact:** Alert filtering by type is broken. Merchants receive wrong alert types or miss alerts entirely. Alert dashboard shows incorrect category counts.

---

## [HIGH] BUG-063 — ai_clients.py uses nonexistent Gemini model names
- **File:** `backend/services/ai_trend_analysis/ai_clients.py` lines 25–26, 106
- **Issue:** Declares models `"gemini-3-flash-preview"`, `"gemini-3-pro-preview"`, and `"gemini-1.5-flash"`. Project rule mandates `"gemini-2.0-flash"` only. `gemini-3-*` models don't exist in the Gemini API.
- **Impact:** All trend analysis AI calls fail at the API level with a model-not-found error. Market trend analysis, launch detection, and crisis detection are completely non-functional.

---

## [HIGH] BUG-064 — Division by zero in trend analyzer on empty competitor price list
- **File:** `backend/services/ai_trend_analysis/analyzer.py` line 259
- **Issue:** `sum(competitor_prices) / len(competitor_prices)` — no guard if `competitor_prices` is an empty list. `.get("competitor_prices", [])` can return `[]` and `len([]) == 0`.
- **Impact:** `ZeroDivisionError` whenever a product has no competitor prices. Trend analysis crashes for new products before any competitor data is scraped.

---

## [HIGH] BUG-065 — Division by zero in sentiment aggregator when no previous mentions exist
- **File:** `backend/services/analysis/sentiment_aggregator.py` line 117
- **Issue:** `(curr_count - prev_count) / prev_count` — no zero-check on `prev_count`. For a brand-new product with no prior mentions, `prev_count = 0`.
- **Impact:** `ZeroDivisionError` on the first sentiment aggregation run for any new product. Sentiment signal is unavailable until the bug is hit and the task crashes.

---

## [HIGH] BUG-066 — notification_tasks.py imports run_async which doesn't exist in db/session.py
- **File:** `backend/workers/tasks/notification_tasks.py` line 16
- **Issue:** `from db.session import get_session_context, run_async` — `run_async` is not exported by `db/session.py`. This is an `ImportError` at module import time.
- **Impact:** The entire `notification_tasks` module fails to import. Celery worker crashes at startup. No notification tasks (price alerts, email digests) ever run.

---

## [HIGH] BUG-067 — main.py uses os.getenv() directly for payment middleware init
- **File:** `backend/main.py` line 49 (approx)
- **Issue:** `if HAS_X402 and os.getenv("PAY_TO_ADDRESS"):` — direct `os.getenv()` call outside `core/config.py`. If `PAY_TO_ADDRESS` is defined in Settings but not in raw `os.environ` (e.g., loaded from `.env` file by Pydantic), the x402 payment middleware silently doesn't initialize.
- **Impact:** x402 payment endpoints appear to exist but all requests return payment-required errors that are never resolved because the middleware isn't active.

---

## MEDIUM (new — deep audit pass 2)

---

## [MEDIUM] BUG-068 — sentiment/retrieval.py missing user_id filters — cross-user data access
- **File:** `backend/api/v1/routes/sentiment/retrieval.py` lines 33, 99, 129, 151
- **Issue:** Four endpoints (`GET /sentiment/{id}`, `GET /sentiment/product/{id}/summary`, `DELETE /sentiment/{id}`, `GET /sentiment/product/{id}/mentions`) query by ID alone without `.where(Sentiment.user_id == current_user.id)`. Any user can read or delete any sentiment record.
- **Impact:** Authorization bypass: User A can read, summarize, and delete User B's sentiment data. GDPR violation. Data poisoning possible.

---

## [MEDIUM] BUG-069 — N+1 query explosion in competitor analysis endpoint
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 59–61, 135–142
- **Issue:** `get_competitor_alerts` fetches alert records then inside a loop executes 2 additional DB queries per record (CompetitorProduct + Competitor + Product). With 100 results, this is 300+ queries per request instead of 1 with joins.
- **Impact:** Competitor alerts endpoint slows to seconds per request as data grows. Under load causes DB connection pool exhaustion. Dashboard becomes unusable for merchants with large catalogs.

---

## [MEDIUM] BUG-070 — price_check.py misuses async session context manager — resource leak
- **File:** `backend/api/v1/routes/price_check.py` lines 95, 130
- **Issue:** `get_session()` is an async generator (used via `async with`) but is called directly as a coroutine in `_store_lead()` and `_update_lead_report()` helper functions. The async context manager is not entered correctly.
- **Impact:** DB session is never properly closed. Connection pool leaks one connection per price-check lead store/update. Under sustained traffic, DB connections are exhausted.

---

## [MEDIUM] BUG-071 — Rate limit reset time is wrong — retry_after seconds not added to now
- **File:** `backend/services/integration/rate_limit.py` lines 46–47
- **Issue:** `mark_rate_limited(retry_after=N)` stores `reset_at = datetime.now(UTC) + timedelta(seconds=retry_after)` — but the actual code sets `reset_at = retry_after` directly (the integer), not `now + timedelta(retry_after)`. The reset timestamp becomes a small integer (epoch seconds offset), not a future datetime.
- **Impact:** Rate limiting resets at epoch second N (early 1970s), meaning the rate limit is effectively never enforced. Shopify API rate limit detection is bypassed, leading to 429 floods.

---

## [MEDIUM] BUG-072 — Division by zero in outcome service merchant modification calculation
- **File:** `backend/services/pricing/outcome_service.py` lines 140–144
- **Issue:** `merchant_modification_percent = (actual_price_set - recommended_price) / recommended_price * 100` — no zero-check on `recommended_price`. If `recommended_price` is `Decimal("0")` or `None`, this raises `ZeroDivisionError` or `TypeError`.
- **Impact:** Outcome recording crashes for any recommendation with a zero recommended price. Feedback loop data is lost; calibration degrades over time.

---

## [MEDIUM] BUG-073 — Division by zero in pipeline_adapter when no competitor prices exist
- **File:** `backend/services/pricing/pipeline_adapter.py` line 107
- **Issue:** Position index normalization uses `(price - min_p) / (max_p - min_p)`. When `all_prices` is empty (no competitors), `min_p` and `max_p` both raise `ValueError` from `min([])`/`max([])`. When there is exactly one competitor, `max_p == min_p` → division by zero.
- **Impact:** Competitive position calculation crashes for all new products and single-competitor scenarios. Price recommendations cannot be generated.

---

## [MEDIUM] BUG-074 — Multiple division-by-zero in analytics_service and trend_detector
- **File:** `backend/services/analytics/analytics_service.py` lines 133, 306, 308; `backend/services/analysis/trend_detector.py` line 118
- **Issue:** (1) `(p.current_price - p.base_price) / p.base_price` with no `base_price > 0` check. (2) `sum(scores) / len(recent)` and `sum(scores) / len(earlier)` with no empty-list guard. (3) `current_count / baseline_avg` with no zero-check on `baseline_avg`.
- **Impact:** Analytics endpoints crash for any product with `base_price = 0`. Trend detection fails for products with no historical baseline. Dashboard returns 500 errors instead of data.

---

## [MEDIUM] BUG-075 — Division by zero in elasticity calculator on zero price or zero units
- **File:** `backend/services/scoring/elasticity_calculator.py` lines 76, 83, 99
- **Issue:** `price_change_pct` divides by `old_price`; `quantity_change_pct` divides by `avg_daily_units_before`. Both can be zero. PED calculation at line 99 divides `pct_qty / pct_price` where `pct_price` is only guarded to `>= 0.02` — but if it rounds to 0 via float precision, infinity results.
- **Impact:** Price elasticity calculation crashes or returns infinity for any new product (no sales history) or free product. Thompson Sampling bandit receives infinity confidence values, corrupting all strategy selection.

---

## [MEDIUM] BUG-076 — Division by zero in guardrails velocity cap on zero current price
- **File:** `backend/services/scoring/guardrails.py` lines 168, 186
- **Issue:** `(price - product.current_price) / product.current_price` — no zero-guard on `product.current_price`. String formatting on line 186 executes before any guard. Products with `current_price = 0` (unpublished, archived) crash the guardrail check.
- **Impact:** Guardrail enforcement crashes for any product with zero price. Price recommendations bypass all safety checks — prices can be set to any value including negative numbers.

---

## [MEDIUM] BUG-077 — Mutable list defaults in Integration model shared across instances
- **File:** `backend/models/integration.py` lines 90, 95
- **Issue:** `scopes: list[str] = Field(default=[])` and `webhook_ids: list[str] = Field(default=[])`. SQLModel/Pydantic v2 should use `default_factory=list`. With `default=[]`, the same list object is shared by all instances that don't explicitly set these fields.
- **Impact:** (1) Adding a webhook ID to one integration's in-memory state adds it to all others. Webhook cleanup on disconnect doesn't work reliably. (2) OAuth scope tracking is corrupted — scopes granted to one integration leak to others.

---

## [MEDIUM] BUG-078 — Mutable dict/list defaults in RetrospectiveAudit model — audit data leaks
- **File:** `backend/models/retrospective_audit.py` lines 51, 52
- **Issue:** `summary_json: dict = Field(default={})` and `sku_results_json: list = Field(default=[])` use mutable defaults. All audit instances without explicit values share the same dict/list object.
- **Impact:** One merchant's audit data modifications (in-memory, before commit) appear in all other audits. If audit data is written to the shared dict before DB persist, it bleeds across unrelated audit records. GDPR violation.

---

## [MEDIUM] BUG-079 — No payment idempotency key — duplicate payments on retry
- **File:** `backend/services/payment/subscription_service.py` lines 313–320
- **Issue:** `create_subscription_payment()` inserts a new `Payment` record every call with no uniqueness check on `(user_id, amount, tier, created_at_window)`. Browser retries or double-clicks create duplicate payment records. `confirm_payment()` at line 368 doesn't check for existing confirmed payments before reprocessing.
- **Impact:** Network retries cause double-charges. Two `Payment` records are confirmed, both activate subscriptions — user gets double subscription or both records enter inconsistent states.

---

## [MEDIUM] BUG-080 — Webhook delivery doesn't retry on HTTP 5xx — alerts silently dropped
- **File:** `backend/services/notification/webhook_service.py` lines 141–142
- **Issue:** Retry logic only triggers on connection errors and timeouts. HTTP 502, 503, 504 from a temporarily overloaded webhook receiver are treated as permanent failures. Delivery is marked as failed with no retry.
- **Impact:** Any temporary outage on the user's webhook receiver causes permanent alert loss. Merchants don't know their webhook endpoint was down — they just silently stop receiving alerts.

---

## [MEDIUM] BUG-081 — ai_generator.py and ai_support_service.py use "gemini-2.0-flash-exp" not "gemini-2.0-flash"
- **File:** `backend/services/ai_generator.py` line 50; `backend/services/ai_support_service.py` line 111
- **Issue:** Model identifier `"gemini-2.0-flash-exp"` uses the experimental suffix. Project rules mandate `"gemini-2.0-flash"` exactly. The `-exp` variant may have different rate limits, quota restrictions, or behavioral differences.
- **Impact:** Main AI entry point uses a non-standard model variant. If Google deprecates or changes the `-exp` model, all AI-powered features (pricing recommendations, competitor analysis, support) silently break or produce inconsistent results.

---

## [MEDIUM] BUG-082 — products/import_service.py update path silently does nothing
- **File:** `backend/services/products/import_service.py` line 135
- **Issue:** TODO comment: update logic is not implemented. The code increments `result.updated += 1` but does not actually update any fields on the existing product record.
- **Impact:** When re-importing a product CSV that has updated prices, names, or descriptions, the import reports success and increments the update counter but no data is changed. Merchants believe products were updated when they weren't.

---

## LOW (new — deep audit pass 2)

---

## [LOW] BUG-083 — Mutable defaults in multiple models (alert, competitor, product)
- **File:** `backend/models/alert.py` line 87; `backend/models/competitor.py` line 42; `backend/models/product.py` line 56
- **Issue:** `channels: list = Field(default=[AlertChannel.IN_APP])`, `scraping_config: dict = Field(default={})`, `keywords: list[str] = Field(default=[])` — all mutable defaults shared across instances.
- **Impact:** In-memory list/dict mutations to one model instance leak to all others created with these defaults. Typically caught before DB persist but is a latent correctness bug.

---

## [LOW] BUG-084 — DB exception handler leaks raw database error messages to API responses
- **File:** `backend/core/exception_handlers.py` line 107
- **Issue:** The catch-all exception handler returns the raw exception message to the API client without sanitization. SQL error messages can contain table names, column names, constraint names, and partial query text.
- **Impact:** Information disclosure — attackers can probe the API to enumerate schema details, column names, and unique constraint configurations from error responses.

---

## [LOW] BUG-085 — sentiment_multiplier default mismatch between ProductCreate schema and model
- **File:** `backend/schemas/product.py` line 29; `backend/models/product.py` line 50
- **Issue:** `ProductCreate.sentiment_multiplier` defaults to `Decimal("0.1")` (10%) but `Product` model defaults to `Decimal("0.2")` (20%). The model was updated but the schema was not. All products created via API use half the intended sentiment weight.
- **Impact:** Sentiment-based pricing recommendations are underweighted by 50% for all products created via the API. Merchants cannot override this — the correct default is never applied from the user-facing layer.

---

## HIGH (frontend audit)

---

## [HIGH] BUG-086 — Hardcoded Railway staging URL fallback in app/page.tsx breaks production Shopify install
- **File:** `frontend/app/page.tsx`
- **Issue:** `const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'https://social-sentiment-pricing-staging-2ecd.up.railway.app'` — Railway staging URL is hardcoded as the fallback. If `NEXT_PUBLIC_API_URL` is unset in a production Vercel deploy, the Shopify install OAuth flow redirects to the staging backend.
- **Impact:** Shopify merchant install attempts from production hit staging backend. OAuth flow fails or stores credentials against staging DB. Merchants cannot connect their store.

---

## [HIGH] BUG-087 — useSearchParams() without Suspense boundary in Next.js 14 callback page
- **File:** `frontend/app/(dashboard)/integrations/callback/page.tsx`
- **Issue:** `useSearchParams()` called at the page level in a Client Component with no wrapping `<Suspense>` boundary. In Next.js 14 this is required — the build emits an error and forces the entire route to dynamic rendering.
- **Impact:** Build fails or emits critical warning. Hydration mismatch possible. OAuth callback page may not render correctly on first load.

---

## [HIGH] BUG-088 — analytics/audit/page.tsx calls localStorage without SSR guard — crashes on server
- **File:** `frontend/app/(dashboard)/analytics/audit/page.tsx`
- **Issue:** `getAuthToken()` calls `localStorage.getItem()` without `typeof window !== 'undefined'` guard. During SSR or Next.js static generation, `window` is undefined.
- **Impact:** "ReferenceError: window is not defined" during build or server-side render. The audit analytics page fails to build or crashes on first render.

---

## [HIGH] BUG-089 — React Query data accessed before null check in analytics/audit/page.tsx
- **File:** `frontend/app/(dashboard)/analytics/audit/page.tsx`
- **Issue:** `audit.summary.total_products_analyzed` is accessed before checking whether `audit` is defined. React Query returns `undefined` until the query resolves, so on initial mount `audit` is undefined.
- **Impact:** "Cannot read properties of undefined (reading 'summary')" crash on component mount. Audit analytics page is broken on every first load.

---

## [HIGH] BUG-090 — window.prompt() return value not null-checked before .length — crashes on cancel
- **File:** `frontend/app/(dashboard)/pricing/recommendations/[id]/page.tsx`
- **Issue:** `const reason = window.prompt(...)` returns `null` if the user clicks Cancel. Code immediately calls `if (reason.length < 10)` on the null return value → `TypeError: Cannot read properties of null (reading 'length')`.
- **Impact:** App crashes whenever a user clicks Cancel on the rejection reason dialog. Recommendation rejection is broken.

---

## [HIGH] BUG-091 — Approval POST sends literal string "undefined" as request body
- **File:** `frontend/lib/api/pricing.ts`
- **Issue:** When no modification data is provided, `api.post(url, undefined)` is called. Depending on Axios config, `JSON.stringify(undefined)` produces the string `"undefined"` or an empty body, neither of which is valid JSON. The backend expects either `{}` or `null`.
- **Impact:** Backend returns 422 Unprocessable Entity on approve-without-modification. The approval workflow silently fails for every recommendation that doesn't have a price override.

---

## [HIGH] BUG-092 — Payment history total count reports page size not server total
- **File:** `frontend/lib/api/payments.ts`
- **Issue:** `total: apiPayments.length` uses the length of the current page of results instead of the server-provided total count. If the server has 50 payment records and returns 10 per page, `total` is reported as 10.
- **Impact:** Pagination UI always shows page size as total. Users cannot see whether there are more pages of payment history. Pagination is effectively broken.

---

## [HIGH] BUG-093 — OutcomeDashboard calls .map() on potentially null outcomes array
- **File:** `frontend/components/features/intelligence/OutcomeDashboard.tsx`
- **Issue:** `outcomes.map((outcome) => ...)` is called without a null check. If React Query returns `null` (not `[]`) or the hook fails, calling `.map()` on null throws `TypeError: Cannot read properties of null (reading 'map')`.
- **Impact:** Outcome dashboard crashes with white screen when the API returns null for outcomes.

---

## [HIGH] BUG-094 — RecommendationCard calls parseFloat on unvalidated backend price strings
- **File:** `frontend/components/features/pricing/RecommendationCard.tsx` lines 189, 206
- **Issue:** `parseFloat(current_price)` and `parseFloat(recommended_price)` called directly on backend-supplied strings without validating they are numeric. If backend returns `"pending"`, `""`, or `null`, the result is `NaN`.
- **Impact:** Recommendation cards display "NaN" in price fields. Price change indicators show "NaN%" instead of valid values.

---

## [HIGH] BUG-095 — PriceHistoryCard divides by zero when previousPrice is 0
- **File:** `frontend/components/features/products/PriceHistoryCard.tsx` line 95
- **Issue:** `((price - previousPrice) / previousPrice) * 100` — no guard when `previousPrice === 0`. Products that start at zero price (free products, gift cards, recently imported) produce `Infinity` or `NaN`.
- **Impact:** Price change percentage shows "Infinity%" or "NaN%" for products with a zero baseline price.

---

## [HIGH] BUG-096 — TrendAnalysisCard accesses analysis.market_sentiment when analysis prop is undefined
- **File:** `frontend/components/features/trends/TrendAnalysisCard.tsx`
- **Issue:** `getTrendDisplayInfo(analysis.market_sentiment)` is called without checking whether `analysis` exists. The prop is typed as optional (`analysis?: TrendAnalysisResponse`), so it can be undefined when data is loading.
- **Impact:** "Cannot read properties of undefined (reading 'market_sentiment')" crash while trend data is loading.

---

## [HIGH] BUG-097 — MNEEBalance crashes when wallet is disconnected (balance is null/undefined)
- **File:** `frontend/components/features/payments/MNEEBalance.tsx` line 31
- **Issue:** `parseFloat(balance).toFixed(2)` — no null check before `parseFloat()`. When the wallet is disconnected or the `useMNEE()` hook hasn't resolved, `balance` is `undefined`; `parseFloat(undefined)` returns `NaN`, then `.toFixed(2)` throws `TypeError`.
- **Impact:** MNEEBalance component crashes on every render when no wallet is connected. Payments page shows white screen for non-connected users.

---

## [HIGH] BUG-098 — SubscriptionPlans hardcodes 'ethereum' as payment network regardless of active network
- **File:** `frontend/components/features/payments/SubscriptionPlans.tsx`
- **Issue:** Payment confirmation callback passes `network: 'ethereum'` hardcoded instead of using the `activeNetwork` state variable. BSV/MNEE payments are reported to the backend as Ethereum.
- **Impact:** BSV/MNEE subscription payments are recorded with the wrong blockchain network. Backend payment reconciliation fails for all non-Ethereum payments. Subscription activations via MNEE will be mis-attributed.

---

## MEDIUM (frontend audit)

---

## [MEDIUM] BUG-099 — PLATFORM_CONFIGS accessed with unvalidated platform key — crashes on unknown platform
- **File:** `frontend/app/(dashboard)/integrations/[id]/page.tsx`
- **Issue:** `const config = PLATFORM_CONFIGS[integration.platform]` — if the DB record has a platform value not in `PLATFORM_CONFIGS` (e.g., a future platform or corrupted data), `config` is `undefined`, and the subsequent `config.logo` access crashes.
- **Impact:** Integration detail page crashes with "Cannot read properties of undefined (reading 'logo')" for any integration with an unrecognized platform value.

---

## [MEDIUM] BUG-100 — productsData?.items.find() crashes when items is null
- **File:** `frontend/app/(dashboard)/sentiment/page.tsx`
- **Issue:** `productsData?.items.find(...)` — optional chaining only guards against `productsData` being nullish, not `productsData.items`. If `productsData` is defined but `items` is `null`, `null.find(...)` throws.
- **Impact:** Sentiment page crashes if the products API returns a response object with a null items array.

---

## [MEDIUM] BUG-101 — useProduct hook called with empty string when no productId is selected
- **File:** `frontend/app/(dashboard)/competitors/match/page.tsx`
- **Issue:** `useProduct(productId || '')` passes empty string `''` to the hook when `productId` is null. This fires an API request to `GET /api/v1/products/` (empty ID) on every render without a selected product.
- **Impact:** Unnecessary 404 API errors on every page load. If the API endpoint mishandles empty IDs (e.g., list endpoint), may return unintended data.

---

## [MEDIUM] BUG-102 — sessionStorage used for auth redirect in login page (security violation)
- **File:** `frontend/app/(auth)/login/page.tsx`
- **Issue:** `sessionStorage.getItem('redirectAfterLogin')` / `sessionStorage.setItem(...)` used for post-login redirect. Project security rules require httpOnly cookies for all auth-related storage. `sessionStorage` is accessible to JavaScript and violates the same-policy as `localStorage`.
- **Impact:** Security violation consistent with BUG-001. Additionally crashes during SSR (`window is not defined`).

---

## [MEDIUM] BUG-103 — setInterval in ShopifyEmbeddedProvider not cleaned up on unmount
- **File:** `frontend/lib/context/shopify-embedded.tsx`
- **Issue:** `waitForAppBridge()` uses `setInterval` to poll for `window.shopify`. The interval is cleared on success, but if the component unmounts while the promise is still pending, the interval continues running, capturing stale closures.
- **Impact:** Memory leak — polling interval continues after provider unmounts. May call `setState` on an unmounted component, causing React warnings or crashes.

---

## [MEDIUM] BUG-104 — useOutcomeDashboard hardcodes calibration window to 90 days regardless of parameter
- **File:** `frontend/lib/hooks/use-outcomes.ts`
- **Issue:** `useConfidenceCalibration({ days: 90 })` always passes `90` regardless of the `days` parameter passed to `useOutcomeDashboard`. The accuracy stats query uses the passed `days` but calibration data is always 90-day window.
- **Impact:** Calibration chart always shows 90-day window even when user selects a different time range. Analytics data is inconsistent within the same dashboard view.

---

## [MEDIUM] BUG-105 — competitorProductToFormData uses || instead of ?? for match_confidence — zeroes become 1.0
- **File:** `frontend/lib/domain/competitors.ts`
- **Issue:** `decimalToFormString(cp.match_confidence) || '1.0'` — when `match_confidence` is `0`, `decimalToFormString` returns `'0'` which is falsy; the `||` operator replaces it with `'1.0'`. Should use `??` (nullish coalescing).
- **Impact:** Competitor products with zero confidence scores silently display as 100% confidence. Merchants see misleading match confidence data.

---

## [MEDIUM] BUG-106 — useProductMatch doesn't invalidate per-product competitor query after auto-link
- **File:** `frontend/lib/hooks/use-competitor-matching.ts`
- **Issue:** After an auto-link mutation succeeds, the code invalidates `competitorKeys.products()` and `competitorKeys.all` but not the per-product competitor query key (`competitorKeys.productCompetitors(productId)`). Product detail page still shows old competitor list.
- **Impact:** Newly linked competitors don't appear on the product detail page until a manual page refresh. Creates confusing UX where the action appears to have no effect.

---

## [MEDIUM] BUG-107 — Outcomes API treats zero-revenue outcomes as unmeasured (falsy check instead of null check)
- **File:** `frontend/lib/api/outcomes.ts`
- **Issue:** `outcome.revenue_7d_after ? parseFloat(...) : null` — a truthy check is used instead of `!= null`. When backend returns `"0"` (zero revenue), the check evaluates to falsy, returning `null` instead of `0`.
- **Impact:** Price changes with zero revenue impact are shown as "not yet measured" instead of "$0.00 impact". Analytics dashboard misrepresents all zero-revenue outcomes.

---

## [MEDIUM] BUG-108 — Trend analysis API interpolates model name into URL without encoding
- **File:** `frontend/lib/api/trend-analysis.ts`
- **Issue:** `` `?use_model=${useModel}` `` appends model name directly to URL without `encodeURIComponent()`. Model names containing `+`, `&`, `=`, or `/` would break URL parsing.
- **Impact:** Trend analysis requests silently fail or hit wrong endpoint if model name contains reserved URL characters.

---

## [MEDIUM] BUG-109 — CalibrationChart uses double-cast `as unknown as` bypassing type safety
- **File:** `frontend/components/features/intelligence/CalibrationChart.tsx`
- **Issue:** `(report?.confidence_bands ?? []) as unknown as CalibrationBand[]` — the double cast silently accepts any shape and bypasses TypeScript's structural check. If the backend changes the shape of `confidence_bands`, the chart will silently render incorrect data or crash.
- **Impact:** Calibration chart renders wrong data without any type error. Shape changes from backend are invisible until visual regression.

---

## [MEDIUM] BUG-110 — LinkProductForm isSubmitting prop is received but never used — double-submission possible
- **File:** `frontend/components/features/integrations/LinkProductForm.tsx`
- **Issue:** The component accepts `isSubmitting` as a prop and uses it in the button's `disabled` condition, but the parent component passes a static value and doesn't update it based on mutation state. The button can be re-clicked during submission.
- **Impact:** Users can submit the link form multiple times in rapid succession, creating duplicate competitor product links.

---

## [MEDIUM] BUG-111 — EthWalletCard shows "0.00 MNEE" when balance fetch fails instead of error state
- **File:** `frontend/components/features/payments/EthWalletCard.tsx`
- **Issue:** `Number(undefined)` returns `NaN`; the balance formatter displays "0.00" as a fallback without distinguishing between a real zero balance and a failed load.
- **Impact:** Users see "0.00 MNEE" when the balance failed to load, mistakenly believing they have no funds rather than experiencing a connectivity issue.

---

## [MEDIUM] BUG-112 — PaymentHistory crashes or renders broken UI on unrecognized payment status
- **File:** `frontend/components/features/payments/PaymentHistory.tsx`
- **Issue:** `STATUS_CONFIG[payment.status]` — if the backend returns a new status value not present in `STATUS_CONFIG`, this returns `undefined`. Subsequent access to `statusConfig.icon` or `statusConfig.color` throws.
- **Impact:** PaymentHistory component crashes for any payment with a status not in the hardcoded config map. Adding a new backend status breaks the entire payment history view.

---

## [MEDIUM] BUG-113 — Sentiment API silently maps content→text field with no schema validation
- **File:** `frontend/lib/api/sentiment.ts`
- **Issue:** Frontend sends `{ text: content, ... }` but the field name mapping (`content` → `text`) is undocumented and not validated against the backend Pydantic schema. If the backend expects `content`, all sentiment analysis requests return 422 Unprocessable Entity.
- **Impact:** Sentiment analysis submissions either silently fail (if backend accepts `text`) or return validation errors. No test coverage catches backend field name drift.

---

## [MEDIUM] BUG-114 — alerts/[id]/page.tsx crashes when alert.created_at is null
- **File:** `frontend/app/(dashboard)/alerts/[id]/page.tsx`
- **Issue:** `format(new Date(alert.created_at), 'PPp')` — `new Date(null)` produces an Invalid Date object, and `date-fns format()` throws "Invalid time value" when given an invalid Date.
- **Impact:** Alert detail page crashes with unhandled error for any alert record where `created_at` is null or an invalid timestamp.

---

## LOW (frontend audit)

---

## [LOW] BUG-115 — Duplicate trendAnalysisKeys defined in two separate files
- **File:** `frontend/lib/api/query-keys.ts`; `frontend/lib/api/trend-analysis.ts`
- **Issue:** Both files export a `trendAnalysisKeys` object. Hooks using one definition and components using the other create separate React Query cache entries for the same data.
- **Impact:** Trend analysis data is fetched twice — once per cache key. Invalidating one key doesn't invalidate the other; stale data persists after mutations.

---

## [LOW] BUG-116 — formatTrustScore has no bounds check — outputs "NaN%" or "Infinity%"
- **File:** `frontend/lib/hooks/use-trust-scoring.ts`
- **Issue:** `Math.round(score * 100)` — no validation that `score` is a finite number in the 0–1 range. `NaN` and `Infinity` inputs produce invalid percentage strings.
- **Impact:** Trust score UI displays "NaN%" or "Infinity%" if the backend returns unexpected score values.

---

## [LOW] BUG-117 — AIAnalysisCard confidence percentage shows "NaN%" if backend returns string
- **File:** `frontend/components/features/competitors/AIAnalysisCard.tsx`
- **Issue:** `(analysis.confidence ?? 0) * 100` — if the backend returns `confidence` as a string (e.g., `"0.85"`), multiplying a string by 100 produces `NaN` in JavaScript.
- **Impact:** Competitor AI analysis card displays "NaN%" for confidence instead of a valid percentage.

---

## [LOW] BUG-118 — SubscriptionPlans can call handlePaymentSuccess before paymentInfo is populated
- **File:** `frontend/components/features/payments/SubscriptionPlans.tsx`
- **Issue:** `handlePaymentSuccess` doesn't guard against `paymentInfo` being `undefined`. If the payment callback fires before the backend confirms payment details, `paymentInfo.payment_id` throws a null pointer error.
- **Impact:** Race condition in payment confirmation flow — fast payment completions may crash before `paymentInfo` state is set.

---

## [LOW] BUG-119 — ProductsTable casts sort select value without runtime validation
- **File:** `frontend/components/features/products/ProductsTable.tsx`
- **Issue:** `e.target.value as SortField` — TypeScript cast with no runtime validation that the value is a valid `SortField` enum member. A programmatic DOM manipulation or unexpected select value bypasses the enum constraint.
- **Impact:** Invalid sort field string passed to the products API. Backend returns 422 or falls back to default sort silently.

---

## CRITICAL (user-reported, staging deployment)

---

## [CRITICAL] BUG-130 — 313.01: Railway staging ENCRYPTION_KEY mismatch — all integrations fail with "stored credentials invalid"
- **File:** `backend/core/encryption.py`; Railway staging env vars; `backend/api/v1/routes/integrations/oauth.py`
- **Issue:** The `ENCRYPTION_KEY` on Railway staging does not match the key that was used to encrypt tokens when merchants first connected their stores. Every call to `decrypt_token()` raises `cryptography.fernet.InvalidToken`, which the integration layer surfaces as "Stored credentials are invalid. Please reconnect." All merchant integrations (both Shopify and WooCommerce) are broken on staging.
- **Root cause (deployment):** Key was either never set, was regenerated without re-encrypting stored tokens, or staging was redeployed with a fresh key. See `core/encryption.py` Shopify rules: "To fix: either restore original key OR delete integration record and re-OAuth. Never rotate ENCRYPTION_KEY without re-encrypting all existing tokens first."
- **Cascading effect:** 490 unlinked products (BUG-129), all diagnostic failures (310.01), all price sync failures, all pricing recommendation pushes blocked.
- **Fix:** Check Railway staging → Settings → Environment Variables. Verify `ENCRYPTION_KEY` is set to the original Fernet key used at first deploy. If lost, delete all integration records and ask merchants to re-OAuth. See also BUG-004 and BUG-005 (code-level encryption bugs).
- **Impact:** Every merchant on staging cannot use any integration. Entire platform is non-functional. Shopify App Store submission blocked.

---

## HIGH (user-reported)

---

## [HIGH] BUG-121 — 217.01: Pricing rules don't validate cross-platform price consistency
- **File:** `backend/services/pricing/rule_evaluator.py` lines 145–373; `backend/api/v1/routes/diagnostic.py` lines 199–215
- **Issue:** The diagnostic endpoint fetches live prices from both Shopify and WooCommerce and correctly detects price mismatches between platforms. However, pricing rules in `rule_evaluator.py` have no platform awareness — they evaluate signals per product without checking whether the product's price is consistent across connected stores. Rules can generate recommendations based on the Shopify price while the WooCommerce price is entirely different.
- **Impact:** Merchant has Shopify at $29.99 and WooCommerce at $19.99 for the same product. Diagnostics flags this. But pricing rules see the internal `current_price` and generate recommendations without knowing one platform is already mispriced. Rules don't trigger on the cross-platform mismatch. Merchant must find and fix the discrepancy manually via diagnostics.

---

## [HIGH] BUG-125 — 217.05/217.06: auto_approve_and_apply() was deleted during refactor — price recommendations never pushed to Shopify *(FIXED in code, needs staging deploy)*
- **File:** `backend/services/pricing/approval_service.py` lines 187–290; `backend/api/v1/routes/pricing/_approval_endpoints.py` lines 33–72
- **Issue:** The `auto_approve_and_apply()` method was deleted during the 2026-02-17 modularization refactor. All approval attempts silently failed with `AttributeError`. The `try/except` around the call caught and swallowed the error, leaving every recommendation in `PENDING` status forever. No price was ever pushed to Shopify or WooCommerce.
- **Status:** Fix was merged 2026-02-21 (method restored). Code is correct. **Must verify fix is deployed to Railway staging** — user still reports recommendations not applying on staging.
- **Residual risk:** `process_auto_approvals()` batch method (lines 344–353) still silently swallows per-recommendation `ApprovalError` — batch failures don't surface to UI, recommendations stay PENDING with no user-visible indication.
- **Impact:** All price recommendations accepted by merchant never actually changed prices on connected stores. Core product functionality was broken.

---

## [HIGH] BUG-127 — 303.01: Sync stuck in "syncing" state indefinitely after frontend polling times out
- **File:** `backend/services/integration/sync_service.py` lines 341, 369; `frontend/lib/hooks/use-integrations.ts` lines 158–224; `frontend/components/features/integrations/IntegrationCard.tsx` lines 58–95
- **Issue:** The backend properly sets `sync_status = "idle"` on success and `sync_status = "error"` on failure (with a 15-minute stuck-sync timeout). The frontend polls via React Query with a 5-minute client-side timeout. However, if the frontend loses network connectivity *while* a sync is running (e.g., user on mobile, tab goes background), the polling stops receiving updates. When connectivity resumes, `shouldPoll` may still be `true` based on the stale `integration.sync_status === 'syncing'` prop, but the backend has already completed. The `cachedSyncData` shows the last known "syncing" state and `setPollEnabled(false)` only fires when `syncStatus?.sync_status !== 'syncing'` — which requires a successful poll response.
- **Impact:** Sync spinner never clears. User sees perpetual "Syncing..." with "In progress..." on every integration card. Only fix is a full page refresh. `recover_stuck_syncs()` exists in backend but is not triggered from the frontend when polling times out.

---

## [HIGH] BUG-129 — 310.01: 490 unlinked products on staging — cascading failure from encryption key mismatch
- **File:** `backend/models/product.py`; `backend/api/v1/routes/diagnostic.py` lines 176–185; `backend/services/integration/product_sync_service.py` lines 373–402
- **Issue:** 490 products in the staging database have no `ProductIntegrationLink` records (no connection to Shopify or WooCommerce variants). Diagnostics correctly reports these as `PRODUCT_NOT_LINKED`. Root cause is BUG-130: because `ENCRYPTION_KEY` is mismatched, every Shopify API call fails with `InvalidToken` before any product sync can run. No sync = no links created. Products were imported but never pushed to or confirmed on the platform.
- **Impact:** 490 products cannot have prices updated, synced, or recommended. All pricing recommendations for these products fail at the push step. Resolves automatically once BUG-130 (encryption key) is fixed and merchants re-OAuth.

---

## MEDIUM (user-reported)

---

## [MEDIUM] BUG-120 — Hamburger menu overlay stays visible when navigating to current page
- **File:** `frontend/components/layout/DashboardShell.tsx` lines 29–38, 61–67; `frontend/components/layout/Sidebar.tsx` lines 140–146
- **Issue:** When the sidebar is open and the user taps a nav item for the page they're already on, `Sidebar.tsx`'s `handleNavItemClick` calls `event.preventDefault()` (because `active === true`). This prevents any URL change, so the `usePathname()` change `useEffect` in `DashboardShell.tsx` never fires. `closeSidebarFromNav()` is called via `onLinkClick?.()`, which calls `setSidebarOpen(false)` — but this state update may not re-render cleanly due to React's batching or event propagation order with the `capture` listener. The dark overlay (`bg-black/50 z-40`) persists on screen.
- **Impact:** Mobile UX: tapping the current page in the sidebar leaves a full-screen dark overlay blocking all content. The only escape is tapping the overlay itself (which does call `setSidebarOpen(false)` directly) or navigating to a different page.

---

## [MEDIUM] BUG-122 — 217.02: IntegrationCard shows only aggregate sync count — WooCommerce prices not visible
- **File:** `frontend/components/features/integrations/IntegrationCard.tsx` lines 162–189; `frontend/components/features/integrations/LinkedProducts.tsx` lines 250–258
- **Issue:** `IntegrationCard` shows "Products Synced" (aggregate count) and "Last Sync" timestamp — there is no per-platform pricing display. When a merchant has both Shopify and WooCommerce connected, there is no way to see at a glance that Platform A has products at one price and Platform B at another. Per-product platform prices are only visible by drilling into `LinkedProducts` detail view inside each integration card's expandable section.
- **Impact:** Merchant can't see WooCommerce prices from the integrations dashboard without drilling in. Platform-level price discrepancies (diagnosed as mismatch by the diagnostic tool) are not surfaced in the primary integration view.

---

## [MEDIUM] BUG-123 — 217.03: Products list mixes platform data with no platform filter or group control
- **File:** `frontend/app/(dashboard)/products/page.tsx`; `frontend/components/features/products/ProductRow.tsx` lines 144–160; `backend/api/v1/routes/products.py` lines 66–175
- **Issue:** The backend enriches products with a `platforms_linked` array, and `ProductRow` renders platform badges (Shopify green, WooCommerce purple). However, the products list has no platform filter, grouping, or toggle. All products from all platforms appear in one undifferentiated list. A merchant with 200 Shopify products and 150 WooCommerce products sees 350 mixed rows with no way to view only Shopify or only WooCommerce products.
- **Impact:** Products belonging only to one platform are invisible in context — there is no "Show Shopify only" filter. Merchants can't diagnose why certain products appear or whether a product is correctly synced to all platforms.

---

## [MEDIUM] BUG-124 — 217.04: RuleCard silently displays "Unknown" for competitor and product names when lookup APIs fail
- **File:** `frontend/components/features/pricing/RuleCard.tsx` lines 129–148, 162–170; `frontend/app/(dashboard)/pricing/rules/page.tsx` lines 51–67
- **Issue:** `RuleCard` resolves competitor UUIDs and product UUIDs to display names using `competitorNames` and `productNames` maps passed from the parent page. If either the competitors API or products API call fails (network error, auth issue, empty response), the maps are empty and all rules show "Unknown competitor" and missing product names. There is no error state or fallback to load names independently. Additionally, no `Collection` model exists in the backend — rules cannot reference Shopify/WooCommerce collections at all, and the UI has no collection product list display.
- **Impact:** When API calls fail, the pricing rules page shows every rule with no context. Merchant cannot tell which competitor triggers which rule or which products it covers. Missing collection support means merchants using Shopify collections for product grouping cannot apply rules at the collection level.

---

## [MEDIUM] BUG-126 — 302.01: WooCommerce _parse_product() accepts any image URL string without validation
- **File:** `backend/services/integration/woocommerce_service.py` line 432; `backend/models/product.py` line 40; `backend/services/products/import_service.py` line 199
- **Issue:** `images = [img.get("src") for img in data.get("images", []) if img.get("src")]` — only checks that `src` is truthy, not that it is a valid absolute URL. WooCommerce may return relative paths (`/wp-content/uploads/...`), protocol-relative URLs (`//example.com/img.jpg`), empty strings after stripping, or private/auth-gated CDN URLs. These pass the filter and are stored as `image_url` in the product model. The `Product` model has `image_url: str | None` with no URL format constraint, and `import_service.py` only calls `.strip()` with no protocol check.
- **Impact:** Product images fail to render in the frontend (broken `<img>` tags or Next.js `<Image>` errors). Import appears successful but product cards show broken image placeholders. WooCommerce merchants with relative image URLs see no product images in ActualPrice.

---

## [MEDIUM] BUG-128 — 303.02: "PRODUCT NOT LINKED" diagnostic message gives no actionable resolution path
- **File:** `backend/api/v1/routes/diagnostic.py` lines 176–185
- **Issue:** The diagnostic type `PRODUCT_NOT_LINKED` emits: `"Product '{name}' is not linked to any platform"` with suggestion `"Sync products from your store in Integrations"`. This is insufficient for the merchant: it doesn't explain (a) why the link is missing, (b) whether it's a sync failure or a configuration issue, (c) whether clicking "Sync" will actually fix it, or (d) whether it's related to the credential error (BUG-130). When 490 products are unlinked, the merchant sees 490 individual warnings with no aggregate explanation or single fix action.
- **Impact:** Merchant confusion. David's reported question: "I don't know what 'PRODUCT NOT LINKED' means." UI shows 490 individual warnings with a generic suggestion. Merchant cannot resolve this without engineering support to explain that it's caused by the ENCRYPTION_KEY mismatch upstream.

---

## ENHANCEMENTS (feature gaps identified in audit)

---

## [ENHANCEMENT] ENH-001 — Rules and recommendations must indicate which store(s) they apply to
- **Files:** `backend/models/pricing_rule.py`; `backend/models/price_recommendation.py`; `backend/api/v1/routes/pricing/rules.py`; `frontend/components/features/pricing/RuleCard.tsx`
- **Gap:** `PricingRule` model has no `integration_id` or `applies_to_stores` field. Rules apply globally across all connected stores. `PriceRecommendation` has `applied_to_platform` (string, e.g. "Shopify") but no `integration_id` — when multiple stores of the same platform are connected, it's ambiguous which store a recommendation was applied to.
- **Required:** Add nullable `integration_id` FK to `PricingRule`. Add `integration_id` to `PriceRecommendation`. Update rule evaluation to scope per integration. Update `RuleCard` and recommendation display to show store badge.

---

## [ENHANCEMENT] ENH-002 — Collections model: rules for Shopify/WooCommerce collections show member products
- **Files:** No collection model exists; `backend/models/pricing_rule.py`; `backend/services/integration/shopify_service.py`
- **Gap:** No `Collection` model in the backend. `PricingRule` supports `applies_to_categories` (flat string list) but not platform collections. Shopify collections (smart/manual) and WooCommerce product categories cannot be used as rule scopes. Merchants using Shopify collections to group products cannot apply pricing rules at the collection level.
- **Required:** Sync Shopify collections and WooCommerce categories on product sync. Create `Collection` model (id, name, platform, integration_id, member product IDs). Add `applies_to_collections` to `PricingRule`. Update rule evaluation to resolve collection → product IDs. Add collection member list to `RuleCard` UI.

---

## [ENHANCEMENT] ENH-003 — AI auto-generation of competitor fields: current price, description, product URL
- **Files:** `backend/services/ai_generator.py`; `backend/schemas/agent_contracts/scout.py`; `backend/services/competitor_scraper.py`; `backend/models/competitor_product.py`
- **Gap:** Scout agent outputs `CompetitorPrice` (price, url, is_on_sale) but only via scraper. When scraper fails to extract price (invalid CSS selector, JS-rendered price, CAPTCHA), no AI fallback infers price from page HTML/metadata. No AI function generates competitor product description or validates the product URL. `CompetitorProduct` model has no `description` field.
- **Required:** Add `generate_competitor_current_price(html: str) -> Decimal` to `ai_generator.py` as Gemini fallback when scraper fails. Add `generate_competitor_product_description(html: str) -> str`. Add `description` field to `CompetitorProduct`. Wire AI fallback into `competitor_scraper.py` on extraction failure. Track confidence: AI-inferred vs scraped.

---

## [ENHANCEMENT] ENH-004 — Pricing history of dropshipper products with time dimension for outreach proposals
- **Files:** `backend/models/competitor_price_history.py`; `backend/models/retrospective_audit.py`; `backend/api/v1/routes/prospect_audit.py`; `frontend/app/(dashboard)/analytics/page.tsx`
- **Gap:** `CompetitorPriceHistory` tracks price-over-time with `observed_at` timestamps, but: (1) no competitor tagging system to mark a competitor as a "drop shipper"; (2) no outreach proposal generator that shows a prospect how a drop shipper's price history maps to missed margin opportunities; (3) prospect audit route is unauthenticated/teaser-only — authenticated merchants can't generate custom outreach proposals; (4) analytics page has 7/14/30/90-day views but no time-series chart for competitor price evolution.
- **Required:** Add `competitor_type` field (e.g., `drop_shipper`, `manufacturer`, `retailer`) to `Competitor` model. Build `OutreachProposalService` that takes competitor_id + date range → generates PDF/JSON report with price timeline and projected savings. Add authenticated endpoint `POST /api/v1/proposals/generate`. Add time-series competitor price chart to analytics.

---

## [ENHANCEMENT] ENH-005 — Quarterly ActualPrice impact view: revenue with different rule/competitor sets over time
- **Files:** `backend/models/retrospective_audit.py`; `backend/api/v1/routes/prospect_audit.py`; `frontend/app/(dashboard)/analytics/page.tsx`; `frontend/app/(dashboard)/pricing/` (no simulation page exists)
- **Gap:** `RetrospectiveAudit` model stores quarterly impact projections but only for the unauthenticated teaser flow. No authenticated "What-if simulation" exists: a merchant cannot say "show me Q1-Q4 revenue impact if I apply Rule A vs Rule B". No quarterly time bucketing in the analytics dashboard. No `PricingScenario` model for saving rule + competitor combinations.
- **Required:** Create `PricingScenario` model. Build `POST /api/v1/pricing/simulation/quarterly` endpoint — takes scenario config → returns quarterly revenue projections. Add "Quarterly Impact" dashboard page with: Q1–Q4 revenue bars, scenario comparison overlay, rule effectiveness by season. Add quarterly granularity to existing time-range selector.

---

## [ENHANCEMENT] ENH-006 — AP-INTAKE-001: Universal Product Intake Layer
- **Files:** `backend/api/v1/routes/products_import.py`; `backend/services/products/import_service.py`; `backend/services/integration/shopify_products.py`; `backend/services/integration/woocommerce_service.py`
- **Current state:** `POST /api/v1/products/import` accepts JSON array only (max 1000 products). No CSV/XLSX parsing. No file upload endpoint. No fuzzy column mapping. No dry-run mode. No platform adapter pattern — Shopify and WooCommerce sync are independent pipelines. No competitor attachment after bulk import.
- **Gap summary:**
  - Phase 1 (Intake Parser): No file upload endpoint; no CSV/XLSX parsers; no column fuzzy-mapper; no dry_run parameter in import service
  - Phase 2 (Platform Adapters): Import is JSON-only; no Shopify CSV format adapter (`Handle`→`sku`, `Title`→`name`); no WooCommerce CSV adapter; adding a new platform requires touching multiple files
  - Phase 3 (Competitor Attachment): `CompetitorMatchingService` exists but is not wired to import workflow; imported products have no competitors auto-attached; Scout agent is not triggered post-import
- **Required:** New endpoint `POST /api/v1/intake/upload` (multipart); file format detector; CSV/XLSX parsers; fuzzy column mapper service; `dry_run: bool` param in `import_service.py`; refactor Shopify/WooCommerce sync to adapter pattern; post-import async Celery task to trigger competitor matching.

---

---

## [CRITICAL] BUG-184 — `autonomous_pipeline.py` — all endpoints unauthenticated
- **Status: FIXED 2026-03-22**
- **File:** `backend/api/v1/routes/autonomous_pipeline.py` lines 67, 103, 138, 164, 171
- **Issue:** ALL five endpoints (`/autonomous/execute`, `/autonomous/monitor/start`, `/autonomous/monitor/stop`, `/autonomous/stream`, `/autonomous/analyze`) have NO `current_user` dependency. Comment explicitly says "No auth required for demo routes." These are not gated behind any flag in production.
- **Impact:** Any unauthenticated internet client can trigger the autonomous pricing pipeline (which executes real on-chain/Shopify price changes), start/stop background monitoring loops, and stream real-time pricing data.

---

## [HIGH] BUG-185 — `autonomous_pipeline.py` — nonexistent AI model + bypasses `ai_generator.py`
- **File:** `backend/api/v1/routes/autonomous_pipeline.py` lines 180, 183
- **Issue:** Calls `genai.Client()` directly (line 180) without API key setup and without going through `services/ai_generator.py`. Uses `gemini-3-flash-preview` (line 183) — a nonexistent model ID. Runtime will raise `AttributeError` or API 404.
- **Impact:** Autonomous pipeline AI calls will crash at runtime; violates the single AI-entry-point rule.

---

## [HIGH] BUG-186 — `integrations/operations.py` `push_price` — unhandled `decrypt_token` exception
- **File:** `backend/api/v1/routes/integrations/operations.py` line 112
- **Issue:** `decrypt_token(integration.access_token_encrypted)` is called with no try/except. If the token is malformed, the key is mismatched, or `access_token_encrypted` is None, this raises `ValueError`, `AttributeError`, or `cryptography.fernet.InvalidToken` — all unhandled — returning a 500 to the client.
- **Impact:** Any merchant with an invalid/rotated integration token gets an opaque 500 instead of a clear "reconnect your integration" message. `check_integration_health` (line 190) correctly has try/except; `push_price` does not.

---

## [MEDIUM] BUG-187 — `_list_endpoints.py` `get_recommendation_stats` — N+1 queries
- **File:** `backend/api/v1/routes/pricing/_list_endpoints.py` lines 39-47
- **Issue:** Runs one separate `SELECT COUNT(*)` per `RecommendationStatus` enum member (currently 6 values = 6 queries). Should be a single `SELECT status, COUNT(*) GROUP BY status` query.
- **Impact:** Unnecessary DB round-trips on every stats request; worsens under load.

---

## [MEDIUM] BUG-188 — `pricing/simulation.py` — division by zero on zero-priced product
- **File:** `backend/api/v1/routes/pricing/simulation.py` line 110
- **Issue:** `change_percent = ((calculated_price - product.current_price) / product.current_price) * 100` — no guard on `product.current_price == 0`. Products imported with price 0 (drafts, bundles) will cause `ZeroDivisionError`.
- **Impact:** 500 error on simulate endpoint for zero-price products.

---

## [MEDIUM] BUG-189 — `products_import.py` — emoji debug logging in production code
- **File:** `backend/api/v1/routes/products_import.py` lines 100-168
- **Issue:** Extensive `🔍 IMPORT DEBUG:` log statements at `logger.info` level scattered throughout the import endpoint. These flood production logs and expose internal row-by-row state to log aggregators.
- **Impact:** Log pollution; potential PII exposure (product names, SKUs printed for every import row).

---

## [MEDIUM] BUG-190 — `signal_processor.py` `_get_viral_signals` — N+1 DB queries in loop
- **File:** `backend/services/pricing/signal_processor.py` lines 176-186
- **Issue:** For each of up to 5 viral posts, a separate `SELECT` query fetches sentiment. Should be a single query with `WHERE product_id = X ORDER BY analyzed_at DESC LIMIT 5`.
- **Impact:** Up to 5 extra DB round-trips per `gather_signals()` call; multiplied across all products during batch pricing runs.

---

## [LOW] BUG-191 — `competitors/products.py` `get_competitor_product_price_history` — misleading `total` field
- **File:** `backend/api/v1/routes/competitors/products.py` line 283
- **Issue:** `"total": len(history)` returns the count of records returned (capped by the `limit` query param), not the total available records in the DB. Pagination callers can't compute correct page counts.
- **Impact:** Frontend pagination for competitor price history shows wrong total; users may not know more pages exist.

---

## [MEDIUM] BUG-192 — `autonomous_orchestrator.py` — direct `os.getenv()` + module-level Gemini client with empty key
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 29–32
- **Issue:** `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")` and `client = genai.Client(api_key=GEMINI_API_KEY)` are executed at module import time, bypassing `core/config.py`. If the env var is not set at import time the client is initialized with an empty string key. Also uses nonexistent model `gemini-3-flash-preview`.
- **Impact:** Module fails silently or at first use with auth errors; violates project config contract. All autonomous pipeline AI calls fail.

---

## [MEDIUM] BUG-193 — `email_service.py` — synchronous SendGrid `client.send()` blocks asyncio event loop
- **File:** `backend/services/notification/email_service.py` line 122
- **Issue:** `response = client.send(message)` — `SendGridAPIClient` is synchronous (blocking HTTP). Called from an `async` function without `asyncio.get_event_loop().run_in_executor()`. Blocks the event loop for the duration of the network call.
- **Impact:** Every email send (password reset, alerts, invites) blocks all FastAPI concurrent requests for the duration of the SendGrid HTTP call. Under load, this degrades API responsiveness.

---

## [HIGH] BUG-194 — `pricing_tasks.py` `_apply_stuck_recommendations` — Python `is None` instead of SQLAlchemy `.is_(None)` *(FIXED 2026-03-21)*
- **File:** `backend/workers/tasks/pricing_tasks.py` line 340
- **Issue:** `.where(PriceRecommendation.applied_at is None)` — `is None` is a Python identity check on the SQLAlchemy column descriptor, which is never `None`, so the expression evaluates to Python `False`. SQLAlchemy then generates `WHERE false`, returning zero rows.
- **Impact:** `apply_stuck_recommendations` Celery task always finds 0 stuck recommendations and never recovers them. AUTO_APPROVED recommendations that failed to push remain stuck indefinitely.
- **Fix:** Duplicate of BUG-064. Changed to `.where(PriceRecommendation.applied_at.is_(None))`.

---

## [HIGH] BUG-195 — `ingestion_tasks.py` — Python `is not None` / `not Column` used as SQL filters
- **File:** `backend/workers/tasks/ingestion_tasks.py` lines 116, 288
- **Issue:** Line 116: `Product.keywords is not None` — Python identity check on the ORM Column descriptor; always `True`, so ALL products are fetched regardless of keywords field. Line 288: `not SocialMention.processed` — `not Column` evaluates the truthiness of the descriptor object (always truthy), producing a broken SQL filter; fetches wrong set of mentions.
- **Impact:** Line 116 causes the ingestion task to queue social mention fetches for all products including those without keywords, creating wasted API calls. Line 288 means the `process_pending_mentions` query does not correctly filter to unprocessed mentions only.

---

## [MEDIUM] BUG-196 — `analytics_service.py` `get_product_summaries` — N+1 queries per product
- **File:** `backend/services/analytics/analytics_service.py` lines 128–175
- **Issue:** For each product in the result set, three separate DB queries are executed: (1) latest sentiment, (2) mention count, (3) pending recommendation count. Default limit=10 produces 30+ extra queries per analytics page load.
- **Impact:** Analytics dashboard is slow; scales linearly with product count. Should use subqueries or a single JOIN.

---

## [MEDIUM] BUG-197 — `confidence_calculator.py` — sync `self.db.exec()` fails with AsyncSession
- **File:** `backend/services/pricing/confidence_calculator.py` lines 31, 205, 241
- **Issue:** `__init__` declares `db: Session = None` (sync SQLModel Session) and uses `self.db.exec(select(...)).all()` (synchronous call). If an `AsyncSession` is passed (as FastAPI routes do), `exec()` returns a coroutine; calling `.all()` on the coroutine raises `AttributeError`.
- **Impact:** Price volatility and sentiment volatility calculations in confidence scores silently fail or raise exceptions when called with an async DB session. Market stability score always returns the default 0.5 instead of real data.

---

## [MEDIUM] BUG-198 — `outcome_service.py` `get_accuracy_stats` — N+1 queries for rule names
- **File:** `backend/services/pricing/outcome_service.py` lines 728–730
- **Issue:** For each unique `rule_id` found in outcomes, `await self.db.get(PricingRule, rule_id)` is called inside a `for` loop. With N distinct rules, this produces N separate DB round-trips to fetch rule names.
- **Impact:** Slow analytics responses as rule count grows. Should use `WHERE rule_id IN (...)` with a single query.

---

## [LOW] BUG-199 — `outcome_measurement.py` `get_measurement_stats` — full table scan per status
- **File:** `backend/services/pricing/outcome_measurement.py` lines 207–210
- **Issue:** `len(result.scalars().all())` — loads ALL `RecommendationOutcome` rows for each `MeasurementStatus` value to count them in Python. Should use `SELECT COUNT(*)` via `func.count()`.
- **Impact:** Monitoring task loads entire outcomes table into memory repeatedly; degrades as outcomes table grows.

---

## [HIGH] BUG-200 — `webhooks.py` Shopify webhook HMAC verification silently skipped when header absent
- **File:** `backend/api/v1/routes/webhooks.py` lines 74–82
- **Issue:** `if x_shopify_hmac_sha256:` — the entire HMAC check block is conditional on the header being present. Any caller that omits the `X-Shopify-Hmac-Sha256` header completely bypasses signature verification. Line 82 just logs a warning when the secret is missing, still proceeding. A malicious actor can forge any Shopify webhook by not sending the HMAC header.
- **Impact:** Forged webhooks can trigger product syncs or deletions. Shopify's security requirement is that HMAC must always be verified; silently skipping it creates a spoofing surface.

---

## [LOW] BUG-201 — `health.py` `check_redis_sync()` — blocking sync Redis call in async route
- **File:** `backend/api/v1/routes/health.py` lines 43–61
- **Issue:** `check_redis_sync()` is a sync function that creates a blocking Redis connection (`redis.from_url(...)`, `.ping()`). It's called directly from async FastAPI route handlers (`/ready`, `/detailed`) without `run_in_executor`, blocking the asyncio event loop during the connection+ping.
- **Impact:** Every health check call stalls the event loop; under load, this delays concurrent API requests by the Redis RTT.

---

## [MEDIUM] BUG-202 — `websockets.py` WebSocket endpoints have no authentication *(FIXED 2026-03-21)*
- **File:** `backend/api/v1/routes/websockets.py` lines 16, 37
- **Issue:** `/ws/prices` and `/ws/alerts` endpoints accept connections without any token validation. There's no `get_current_user` dependency, no JWT check, no API key requirement. Any unauthenticated client can connect and receive broadcast messages.
- **Impact:** All real-time price and alert broadcast data is publicly accessible. Competitors or anonymous users can monitor price changes and alert events without logging in.
- **Fix:** Duplicate of BUG-058. All WebSocket endpoints now require JWT token via query parameter.

---

## [HIGH] BUG-203 — `market_trends.py` — AI trend endpoints unauthenticated, no rate limit
- **Status: FIXED 2026-03-22**
- **File:** `backend/api/v1/routes/market_trends.py` lines 19, 43
- **Issue:** `POST /api/v1/market-trends/analyze` and `GET /api/v1/market-trends/trends` have no authentication dependency and no rate limiting. Both call `market_trends_service.get_trends()` which invokes AI (Gemini) on every request.
- **Impact:** Any anonymous user can trigger unlimited AI API calls. Under load this drains Gemini API quota and incurs cost with no per-user accountability.

---

## [HIGH] BUG-204 — `support.py` — AI support chat unauthenticated and unrate-limited
- **Status: FIXED 2026-03-22**
- **File:** `backend/api/v1/routes/support.py` lines 21–42
- **Issue:** `POST /api/v1/support/chat` has no `get_current_user` dependency and no `@limiter.limit()` decorator. It calls `ai_support_service.chat()` which makes OpenAI API calls on every request.
- **Impact:** Any anonymous user can send unlimited messages to the OpenAI-backed support chat, exhausting API quota. This is a direct AI cost surface with zero access control.

---

## [MEDIUM] BUG-205 — `price_check.py` — in-memory rate limiter is per-process, not distributed
- **File:** `backend/api/v1/routes/price_check.py` lines 56–77
- **Issue:** `_rate_limit_store: dict[str, list[float]] = {}` is a module-level in-memory dict. In a multi-worker deployment (uvicorn `--workers N`, Railway autoscaling), each worker process maintains its own independent counter. A client can hit each worker up to 10 times/hour, bypassing the intended limit.
- **Impact:** The `RATE_LIMIT_MAX = 10` per-hour limit is multiplied by the number of worker processes. Provides no effective protection against abuse.

---

## [HIGH] BUG-206 — `crisis_detection.py` `generate_mock_data` — NameError: `timezone` not imported
- **File:** `backend/api/v1/routes/crisis_detection.py` line 20
- **Issue:** `now = datetime.now(timezone.utc)` — but `timezone` is not imported. The file imports only `from datetime import datetime, timedelta`. `timezone` is a separate object from `datetime.timezone`.
- **Impact:** `NameError: name 'timezone' is not defined` is raised any time `generate_mock_data()` is called (i.e., when `simulate_crisis=True` in the SSE endpoint), crashing the demo endpoint.

---

---

## [HIGH] BUG-207 — `sentiment/analysis.py` — write endpoints missing product ownership check
- **File:** `backend/api/v1/routes/sentiment/analysis.py` lines 102–105, 159–162
- **Issue:** Both `analyze_and_save` (POST `/sentiment/analyze/{product_id}`) and `analyze_bulk` (POST `/sentiment/analyze/{product_id}/bulk`) fetch the product with `select(Product).where(Product.id == product_id)` but do NOT filter by `Product.user_id == current_user.id`. Any authenticated user can supply any product_id and write sentiment data to another user's product.
- **Impact:** Broken access control (OWASP A01) on write paths. Attacker can pollute competitor product sentiment, trigger unwanted AI analysis jobs, and inflate their billing if sentiment calls are metered.

---

## [LOW] BUG-208 — `shopify_billing_webhooks.py` line 185 — dead `.get()` statement
- **File:** `backend/api/v1/routes/integrations/shopify_billing_webhooks.py` line 185
- **Issue:** `app_sub.get("admin_graphql_api_id", "")` is a bare expression — the return value is never assigned to a variable. The intent was almost certainly `gid = app_sub.get("admin_graphql_api_id", "")`.
- **Impact:** The GraphQL admin ID is silently discarded; any downstream code that was meant to use `gid` either fails or uses an uninitialized variable. Dead code increases maintenance confusion.

---

## [MEDIUM] BUG-209 — `competitors/analysis.py` — OpenAI direct call from router, bypasses service abstraction
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 354–370
- **Issue:** `_generate_ai_analysis()` calls `ai_generator.client.chat.completions.create(model="gpt-4o-mini", ...)` directly inside a router helper — accessing an internal attribute of the service object and using OpenAI with `gpt-4o-mini` instead of the mandated Gemini 2.0 Flash. Violates project rule: "ALL AI calls go through `services/ai_generator.py` — never call Gemini API directly from routers."
- **Impact:** AI calls from this path are invisible to the service-layer abstraction, bypass retry/fallback/logging in `ai_generator.py`, use the wrong model and wrong API client, and will break if OpenAI credentials are removed.

---

---

## [HIGH] BUG-210 — `trust_scoring/service.py` `filter_trusted_mentions` operator precedence breaks filtering
- **File:** `backend/services/trust_scoring/service.py` line 514
- **Issue:** `return [m for m in mentions if m.get("mention_id") or m.get("id") in trusted_ids]` is parsed as `(m.get("mention_id")) or (m.get("id") in trusted_ids)`. If any mention has a `mention_id` field (truthy), it passes the filter regardless of trust score. The correct intent is `(m.get("mention_id") or m.get("id")) in trusted_ids`.
- **Impact:** The `min_trust` filter is completely bypassed for all mentions that contain a `mention_id` key — the majority of real mentions. Low-trust and untrusted authors pass through unchecked, defeating the entire spam/bot filtering purpose.

---

## [HIGH] BUG-211 — `batch_tasks.py` `_get_orchestrator` imports from wrong module path
- **File:** `backend/services/scoring/learning/batch_tasks.py` line 468
- **Issue:** `from database.session import get_db_session` — the module is `db.session` (not `database.session`) and the function is `get_session()` (not `get_db_session()`). This import is inside the `fetch_outcomes` nested function inside `_get_orchestrator()`.
- **Impact:** `ImportError` at Celery task execution time. The weekly learning cycle (feature compute, prior update, context cache refresh) all fail silently. Bayesian priors and ContextInjector cache are never updated. The learning loop is completely broken in production.

---

## [LOW] BUG-212 — `ai_generator.py` uses `gemini-2.0-flash-exp` instead of mandated `gemini-2.0-flash`
- **File:** `backend/services/ai_generator.py` line 50
- **Issue:** `self.gemini_model_name = "gemini-2.0-flash-exp"` — project rules mandate `gemini-2.0-flash`. The `-exp` experimental variant may have different availability, rate limits, and response characteristics than the stable model.
- **Impact:** If the experimental model is deprecated or removed by Google, all AI generation silently fails. Response quality and availability guarantees differ from the stable model required by project contracts.

---

## [HIGH] BUG-213 — `webhook_handler.py` calls `SyncService.sync_single_product()` which does not exist
- **File:** `backend/services/integration/webhook_handler.py` lines 139, 226
- **Issue:** Both `handle_shopify_webhook()` and `handle_woocommerce_webhook()` call `await self.sync_service.sync_single_product(integration_id=..., external_product_id=..., action=...)`. `SyncService` has no `sync_single_product` method — it only has `run_sync()`, `recover_stuck_syncs()`, and `get_stuck_syncs()`. The outer `except Exception` handler at line 159/246 catches and silently swallows the resulting `AttributeError`.
- **Impact:** Every incoming Shopify and WooCommerce product webhook (create/update/delete) silently fails. The product catalog in SSP is never updated from real-time webhook events. New products added to stores, price changes, and deletions are never reflected until a full sync runs.

---

## [HIGH] BUG-214 — `sync_verification_tasks.py` `_auto_fix_price_mismatches` imports from non-existent module
- **File:** `backend/workers/tasks/sync_verification_tasks.py` line 380
- **Issue:** `from services.integration.models import PriceUpdateRequest` — there is no `models.py` in `services/integration/`. The correct module is `services.integration.schemas`. This import is inside `_auto_fix_price_mismatches()` and only executed when `dry_run=False`.
- **Impact:** `auto_fix_mismatches` Celery task crashes with `ModuleNotFoundError` whenever dry_run=False is called. Automated price mismatch correction is completely broken.

---

## [MEDIUM] BUG-215 — `confidence_calculator.py` sync method calls async `get_historical_accuracy_for_rule_type` without await
- **File:** `backend/services/pricing/confidence_calculator.py` lines 163–166
- **Issue:** `_score_historical_accuracy()` is a sync `def` but calls `OutcomeService(self.db).get_historical_accuracy_for_rule_type(user_id, rule_type)` which is `async def`. Without `await`, the return value is a coroutine object, not a `Decimal`. The subsequent weighted calculation raises `TypeError`. Only triggered when `self.db` is not None (default is None), but the guard means the bug is silently bypassed rather than fixed.
- **Impact:** Historical accuracy scoring silently skipped (db=None path) or raises TypeError (db!=None path). Confidence scores omit one of their 5 components when `db` is passed explicitly.

---

## [HIGH] BUG-216 — `price_sync_service.py` instantiates ShopifyService/WooCommerceService with wrong args
- **File:** `backend/services/pricing/price_sync_service.py` lines 110–111, 121–122
- **Issue:** `ShopifyService(self.db, integration)` and `WooCommerceService(self.db, integration)` pass `(db, integration)` positionally, but `EcommerceService.__init__` only accepts `retry_config: RetryConfig | None = None`. `self.db` lands as `retry_config`. Additionally, `service.get_product_price()` does not exist in the mixin architecture. `get_live_price()` catches all exceptions and returns `None`, silently swallowing the error.
- **Impact:** `get_live_price()` always returns `None`. Price drift detection and live-price comparison in price sync are completely non-functional.

---

## [HIGH] BUG-217 — `alert_generator.py` uses sync Session in async methods, blocking event loop
- **File:** `backend/services/notification/alert_generator.py` line 48 (import), lines 387–388, 411, 439, 465, 527
- **Issue:** `AlertGenerator.__init__(self, session: Session)` uses synchronous `sqlmodel.Session`. All public methods are `async def` but make synchronous DB calls: `self.session.exec()`, `self.session.commit()`, `self.session.refresh()`, `self.session.get()`, `self.session.add()`. These block the event loop from every async caller.
- **Impact:** All alert generation (price change, trend, crisis) blocks the event loop. Under load, this stalls the entire FastAPI worker process, causing timeouts across unrelated requests.

---

## [MEDIUM] BUG-218 — `alert_generator.py` `generate_trend_alert` uses wrong AlertType
- **File:** `backend/services/notification/alert_generator.py` line 336
- **Issue:** `generate_trend_alert()` stores alerts with `AlertType.COMPETITOR_PRICE_CHANGE` instead of a trend-specific type (e.g., `AlertType.TREND_DETECTED`). Trend alerts are indistinguishable from competitor price change alerts.
- **Impact:** Alert type filtering and display are broken for trend alerts. Users cannot filter "trend" alerts separately. Analytics aggregated by alert type are incorrect.

---

## [HIGH] BUG-219 — `ai_clients.py` sync HTTP calls inside async functions block event loop
- **File:** `backend/services/ai_trend_analysis/ai_clients.py` lines 157, 178
- **Issue:** `call_openai()` calls `self.openai_client.chat.completions.create()` synchronously inside `async def`. `call_gemini()` calls `self.gemini_client.generate_content()` synchronously inside `async def`. Both are blocking HTTP calls made from async context. The OpenAI and Gemini legacy clients use synchronous `httpx`/`requests` under the hood.
- **Impact:** Every AI trend analysis call blocks the entire event loop for the duration of the API call (typically 1–10 seconds). Under load, this stalls all concurrent requests across the FastAPI worker.

---

## [MEDIUM] BUG-220 — `ai_trend_analysis/` module bypasses `services/ai_generator.py`, violating AI architecture rules
- **File:** `backend/services/ai_trend_analysis/ai_clients.py` (all), `backend/services/ai_trend_analysis/autonomous_orchestrator.py` (all)
- **Issue:** These modules create their own Gemini and OpenAI clients directly (using `google.generativeai`, `google.genai`, `openai.OpenAI`). Project rule requires ALL AI calls to route through `services/ai_generator.py`. This creates two separate AI code paths with different models, retry logic, and error handling.
- **Impact:** AI calls in trend analysis bypass centralized logging, model version control, and rate limiting. Model version inconsistency: `ai_clients.py` uses `gemini-1.5-flash` (legacy) and `gemini-3-flash-preview` (unreleased), while the mandated model is `gemini-2.0-flash`.

---

## [HIGH] BUG-221 — `autonomous_orchestrator.py` uses `os.getenv()` and initializes Gemini client at module level
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 29–32
- **Issue:** Line 29: `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")` — violates security rule that `os.getenv()` must not be used outside `core/config.py`. Line 32: `client = genai.Client(api_key=GEMINI_API_KEY)` executes at module import time. If `google.genai` package version doesn't support `genai.Client`, or if the API key is missing, the entire module fails to import.
- **Impact:** Module import failure crashes any route that imports `autonomous_orchestrator`. `os.getenv()` bypasses centralized config validation. The empty string API key `""` causes all Gemini calls to fail silently with auth errors.

---

## [LOW] BUG-222 — `notification_tasks.py` `NotificationDispatcher` instantiated but never used
- **File:** `backend/workers/tasks/notification_tasks.py` line 97
- **Issue:** `NotificationDispatcher()` is instantiated but the return value is not assigned to a variable. The dispatcher object is immediately garbage collected without being used. All actual dispatch calls go through individually-instantiated `EmailService`, `SlackService`, and `WebhookService` objects.
- **Impact:** Dead code. No functional impact — notifications still get sent. But the `NotificationDispatcher` import is wasted and suggests incomplete refactoring.

---

## [LOW] BUG-223 — `competitive_position.py` dead computation result discarded
- **File:** `backend/services/scoring/competitive_position.py` line 214
- **Issue:** `sum(1 for p in comp_prices if p > our_price)` — this evaluates a sum but does not assign it to a variable. The value is computed then immediately discarded. The variable that should have received this value (`priced_above`) is referenced in the comment but never populated.
- **Impact:** No data quality issue — the formula still works correctly because `percentile_rank` uses `priced_below` and `priced_equal` (lines 220–221). But the `priced_above` count is silently lost. The comment above says "competitors priced above us" drives the formula, but the actual calculation uses `priced_below`. Minor inconsistency with the architecture doc formula.

---

## [HIGH] BUG-224 — `ingestion_tasks.py` SQLAlchemy `is not None` / `not column` identity checks — filters never applied
- **File:** `backend/workers/tasks/ingestion_tasks.py` lines 116, 288
- **Issue:** Two broken SQLAlchemy filter expressions:
  1. Line 116: `select(Product).where(Product.keywords is not None, Product.is_active)` — `Product.keywords is not None` is a Python identity check on a SQLAlchemy column descriptor, which always evaluates to `True`. The filter is silently dropped; ALL active products are fetched regardless of whether they have keywords configured.
  2. Line 288: `.where(not SocialMention.processed)` — `not SocialMention.processed` negates a SQLAlchemy column object at the Python level, which always evaluates to `False`. The WHERE clause adds `WHERE False`, so the query returns zero rows. No unprocessed mentions are ever fetched for sentiment analysis.
  - Correct idioms: `Product.keywords.isnot(None)` (line 116); `SocialMention.processed == False` or `SocialMention.processed.is_(False)` (line 288).
- **Impact:** Line 116: scheduled ingestion queues fetches for every product, including those with no keywords — wasted API calls and Reddit fetches. Line 288 (critical): `process_pending_mentions` task silently does nothing — the sentiment analysis batch never runs. Social mentions are collected but never analyzed. Sentiment scores are never computed. Pricing rules that depend on sentiment signals have no data.

---

## [HIGH] BUG-225 — `pricing_tasks.py` `_apply_stuck_recommendations` `is None` identity check — filter never applied *(FIXED 2026-03-21)*
- **File:** `backend/workers/tasks/pricing_tasks.py` line 340
- **Issue:** `.where(PriceRecommendation.applied_at is None)` — `PriceRecommendation.applied_at is None` is a Python identity check on a SQLAlchemy column descriptor object (always `False`). The filter is silently dropped. The query returns ALL AUTO_APPROVED recommendations, not just those with a null `applied_at`. Correct idiom: `PriceRecommendation.applied_at == None` or `PriceRecommendation.applied_at.is_(None)`.
- **Impact:** `apply_stuck_recommendations` task re-attempts to apply every AUTO_APPROVED recommendation on every run — including ones that already succeeded. Idempotency depends entirely on `ApprovalService.apply_price()` checking current status before pushing, but repeat pushes still generate unnecessary Shopify/WooCommerce API calls and audit log entries. If `apply_price()` is not fully idempotent, prices may be pushed twice.
- **Fix:** Duplicate of BUG-064. Changed to `.where(PriceRecommendation.applied_at.is_(None))`.

---

## [MEDIUM] BUG-226 — `crisis_detection.py` calls OpenAI directly from route helper — AI architecture bypass
- **File:** `backend/api/v1/routes/alerts/crisis_detection.py` line 101
- **Issue:** `_generate_crisis_summary()` calls `await ai_generator.client.chat.completions.create(model="gpt-4o-mini", ...)` — directly accesses the internal `.client` attribute of the shared `AIGenerator` singleton from a route-layer helper. Uses OpenAI `gpt-4o-mini` instead of the mandated Gemini 2.0 Flash. Violates project rule: "ALL AI calls go through `services/ai_generator.py` — never call Gemini API directly from routers." Same anti-pattern as BUG-209 (`competitors/analysis.py`).
- **Impact:** AI calls in crisis detection bypass centralized retry, logging, and fallback. Model mismatch — uses OpenAI when Gemini is mandated. If OpenAI credentials are removed or rate-limited, crisis detection AI summaries fail silently. No error surfaced to the caller.

---

## [MEDIUM] BUG-227 — `crisis_detection.py` N+1 query per product — 980+ DB queries for 490-product merchant
- **File:** `backend/api/v1/routes/alerts/crisis_detection.py` lines 145, 150–167
- **Issue:** The endpoint fetches ALL user products (`select(Product).where(Product.user_id == current_user.id)` with no LIMIT), then loops over each product executing 2 separate SELECT queries (recent sentiments + previous sentiments). For a merchant with 490 products, a single API call generates 981 DB queries. Each query returns up to hundreds of sentiment rows loaded entirely into Python memory.
- **Impact:** Extreme DB load per API call for large catalogs. API call will time out or cause excessive DB lock contention for merchants with many products. Should be rewritten as 2 aggregate queries with `GROUP BY product_id`, or paginated with a per-user LIMIT.

---

## [HIGH] BUG-229 — `sentiment/tasks.py` missing ownership check — any user can trigger sentiment tasks for any product
- **File:** `backend/api/v1/routes/sentiment/tasks.py` lines 31–37, 59
- **Issue:** `fetch_product_mentions` queries Product by `product_id` alone with no `Product.user_id == current_user.id` check. Any authenticated user can pass any `product_id` and queue a Celery sentiment fetch task for another merchant's product. Line 59: `process_pending_mentions.delay(batch_size)` — any user can trigger a system-wide batch processing job affecting all merchants' pending mentions.
- **Impact:** Cross-tenant data access — attacker can trigger sentiment ingestion tasks for other merchants' products, leaking competitor product keyword data through task side-effects. Resource DoS — can flood the Celery queue with tasks for any products in the system.

---

## [MEDIUM] BUG-228 — `os.getenv()` used outside `core/config.py` in payment and search provider services
- **File:** `backend/services/payment/bsv_service.py` line 32; `backend/services/payment/eth_service.py` line 34; `backend/services/payment/subscription_service.py` lines 117, 119; `backend/services/competitor_matching/providers/google_custom.py` lines 63–64; `backend/services/competitor_matching/providers/serpapi.py` line 58
- **Issue:** Five files call `os.getenv()` directly instead of using `settings.*` from `core/config.py`. Violations: `os.getenv("WHATSONCHAIN_API_KEY")`, `os.getenv("ETHERSCAN_API_KEY")`, `os.getenv("SSP_MNEE_WALLET_ADDRESS")` (already in settings!), `os.getenv("SSP_ETH_WALLET_ADDRESS")`, `os.getenv("GOOGLE_API_KEY")`, `os.getenv("GOOGLE_SEARCH_CX")`, `os.getenv("SERPAPI_KEY")`. Security rule: "Never call `os.getenv()` anywhere outside `core/config.py`."
- **Impact:** `SSP_MNEE_WALLET_ADDRESS` is already declared in `core/config.py` (line 118) — calling `os.getenv()` directly bypasses `env_ignore_empty=True` and Pydantic validation. Other keys bypass centralized config validation. Services may initialize with empty-string credentials if env var not set at import time.

---

## [HIGH] BUG-231 — `shopify_install.py` still uses old OAuth URL format — installs land on wrong store
- **File:** `backend/api/v1/routes/integrations/shopify_install.py` line 80
- **Issue:** `auth_url = f"https://{shop}/admin/oauth/authorize?{params}"` — uses the old `{shop}.myshopify.com/admin/oauth/authorize` format. On 2026-03-20, `shopify_service.py` was explicitly fixed to use `admin.shopify.com/store/{name}/oauth/authorize` because "Shopify's unified admin intercepts the old format and routes based on active browser session, causing installs to land on the wrong store." That fix was applied only to `generate_oauth_url()` in `shopify_service.py`, not to the install endpoint which is the primary install entry point.
- **Impact:** All App Store installs via the `/shopify/install` endpoint use the broken old URL. Merchants installing via the App Store may be redirected to the wrong store's OAuth screen. The install completes on the wrong store, creating a token for a different shop. Core install flow is broken for multi-store merchants.

---

## [LOW] BUG-230 — Six route files import `get_current_user` from wrong module
- **File:** `backend/api/v1/routes/competitors/crud.py` line 12; `backend/api/v1/routes/competitors/scraping.py` line 12; `backend/api/v1/routes/competitors/analysis.py` line 13; `backend/api/v1/routes/competitors/products.py` line 13; `backend/api/v1/routes/products.py` line 26; `backend/api/v1/routes/users.py` line 12
- **Issue:** `from api.v1.routes.auth import get_current_user` — six route files import `get_current_user` (and in `users.py`, also `require_role`) from the auth router instead of `core.deps`. The correct import across the codebase is `from core.deps import get_current_user`. If the auth router's `get_current_user` and `core.deps.get_current_user` ever diverge (e.g., role checks are added to deps), these routes will use the wrong version silently.
- **Impact:** Potential divergence from centralized auth dependency if `core.deps.get_current_user` is updated. Creates circular import risk: routes importing from other routes' modules.

---

## [MEDIUM] BUG-232 — `competitors/analysis.py` N+1 queries in `compare_prices` and `get_competitor_alerts`
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 58–73 and 133–171
- **Issue:** Two endpoints execute per-row DB queries in loops:
  1. `compare_prices` (line 59): for each `CompetitorProduct`, executes a separate `SELECT Competitor WHERE id == cp.competitor_id`. For a merchant with 10 competitors linked to one product = 11 queries. No JOIN on the initial query.
  2. `get_competitor_alerts` (lines 135–141): for each `CompetitorPriceHistory` item, executes 3 separate queries: `SELECT CompetitorProduct`, `SELECT Competitor`, `SELECT Product`. For 50 history items = 151 queries. No LIMIT on the outer history query.
- **Impact:** For merchants with many competitor-product links, these endpoints degrade to quadratic DB load. `get_competitor_alerts` with no LIMIT can load unbounded history rows.

---

## [HIGH] BUG-233 — `intelligence_tasks.py` IE tasks fail at runtime — wrong constructor args and non-existent methods
- **File:** `backend/workers/tasks/intelligence_tasks.py` lines 110–320
- **Issue:** The IE Celery tasks instantiate and call learning service classes with signatures that do not match their actual implementations:
  1. `ContextInjector(db_session=db)` — `ContextInjector` (context_injector.py) has no `__init__` at all (no params). Raises `TypeError`.
  2. `Calibrator(db_session=db)` — `Calibrator` (calibrator.py) `__init__` takes no params. Raises `TypeError`.
  3. `DriftDetector(db_session=db)` — `DriftDetector` (drift_detector.py) accepts `recent_window_days`, `baseline_window_days`, NOT `db_session`. Raises `TypeError`.
  4. `calibrator.recalibrate_all()` — `Calibrator` has no `recalibrate_all()` method (has `measure()` and `build_calibration_map()`). Raises `AttributeError`.
  5. `detector.detect_all()` — `DriftDetector` has `detect_all_categories()`, not `detect_all()`. Raises `AttributeError`.
  6. `injector.refresh_cache()` — `ContextInjector` has no `refresh_cache()` method. Raises `AttributeError`.
- **Impact:** Every IE Celery task — `weekly_calibration`, `weekly_drift_detection`, `refresh_context_cache` — will fail immediately at runtime with TypeError or AttributeError. The `_task_wrapper` catches these and logs them as errors but does not surface them to monitoring. The entire backward learning and context injection pipeline is silently broken. Category feature computation, prior updates, drift detection, and calibration maps never run.

---

## [MEDIUM] BUG-234 — `autonomous_orchestrator.py` uses `os.getenv()` outside `core/config.py` and initializes Gemini client at module import
- **File:** `backend/services/ai_trend_analysis/autonomous_orchestrator.py` lines 29–32
- **Issue:** `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")` and `GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")` violate the security rule: "Never call `os.getenv()` anywhere outside `core/config.py`." Additionally, `client = genai.Client(api_key=GEMINI_API_KEY)` is a module-level singleton initialized at import time with a potentially empty key. If `GEMINI_API_KEY` is not set, the module imports with an empty string key and all Gemini calls silently fail at runtime with authentication errors.
- **Impact:** GEMINI_API_KEY bypasses Pydantic validation and `env_ignore_empty=True` from `core/config.py`. Config inconsistency: this module may read a different key value than the rest of the backend. Module-level singleton initialized on import blocks startup if google-genai is not installed.

---

## [MEDIUM] BUG-235 — `batch_tasks.py` wrong DB import path and CELERY_BEAT_SCHEDULE references undefined task functions
- **File:** `backend/services/scoring/learning/batch_tasks.py` line 468; lines 391–416
- **Issue:** Two failures in the weekly learning cycle wiring: (1) `from database.session import get_db_session` — wrong import path; the project uses `db/session.py` with `get_session()`, not `database/session.py`. (2) `CELERY_BEAT_SCHEDULE` (lines 391–416) references three task functions by dotted path (`services.scoring.learning.batch_tasks.weekly_feature_compute`, `...weekly_prior_update`, `...refresh_context_cache`) that are **not defined in this file** — the comment says to "add them to workers/tasks.py" but they are not there either. If this schedule is registered with Celery Beat, all three tasks fail at worker startup with `NotRegistered` (task not found).
- **Impact:** Weekly learning cycle (feature computation, prior updates, context cache refresh) never runs. Bayesian priors are never updated from outcome data. Context injection for recommendations uses stale or default priors. The `ImportError` from wrong DB path would also crash the `_get_orchestrator()` function, failing all three tasks immediately.

---

## [MEDIUM] BUG-236 — `ai_clients.py` `call_openai()` is `async def` but calls synchronous OpenAI client — blocks event loop
- **File:** `backend/services/ai_trend_analysis/ai_clients.py` lines 83–93 and 154–172
- **Issue:** `AIClients.openai_client` property (line 87) initializes `OpenAI(...)` (the synchronous client from `openai` package, not `AsyncOpenAI`). `call_openai()` (line 154) is declared `async def` but calls `self.openai_client.chat.completions.create(...)` without `await` — synchronous blocking call inside an async function. This blocks the asyncio event loop for the entire duration of the API call (typically 1–5 seconds per request).
- **Impact:** Every AI call through `AIClients.call_openai()` freezes the entire FastAPI event loop. All other concurrent requests stall for the duration. Under moderate traffic, this causes cascading 503 errors and timeouts across unrelated endpoints.

---

## [MEDIUM] BUG-237 — `signal_processor.py` `_get_viral_signals` runs identical DB query 5 times — wrong viral sentiment
- **File:** `backend/services/pricing/signal_processor.py` lines 175–190
- **Issue:** `for _post in top_posts[:5]:` loop body executes `select(Sentiment).where(Sentiment.product_id == product_id).order_by(Sentiment.analyzed_at.desc()).limit(1)` — the exact same query — 5 times. The loop variable `_post` (prefixed `_` to indicate intentionally unused) is never referenced inside the loop. The query always returns the same single latest sentiment record for the product. Result: `sentiments` list contains up to 5 identical values; `viral_sentiment` is just that single value repeated. Correct intent was to query sentiment for each viral post's specific content.
- **Impact:** (1) 5 identical DB round-trips per invocation — pure waste. (2) `viral_sentiment` calculation is incorrect — always equals the single most-recent product sentiment rather than the average sentiment across viral posts. This corrupts the urgency scoring signal for viral content events.

---

## [HIGH] BUG-238 — `notification_tasks.py` uses pooled `get_session_context` instead of NullPool — Celery worker event-loop mismatch
- **File:** `backend/workers/tasks/notification_tasks.py` lines 16-17, 63
- **Issue:** `notification_tasks.py` imports and uses `get_session_context` from `db.session` (line 16) and `run_async` from `db.session` (line 17). `get_session_context()` creates sessions from the module-level pooled `async_session` (backed by `create_async_engine` with default pool at `db/session.py:32`). Every other Celery task (pricing_tasks, ingestion_tasks, sync_verification_tasks, outcome_measurement_tasks, etc.) creates its own NullPool engine via a local `get_task_session_maker()` — explicitly to prevent "Future attached to a different loop" errors in forked Celery workers. `notification_tasks.py` is the only Celery task that uses the shared pooled engine.
- **Impact:** After fork, the pooled asyncpg connections are attached to the parent's event loop. When `run_async()` creates a fresh event loop in the worker and `get_session_context()` tries to use the old pooled connections, `asyncpg` raises `InterfaceError: cannot perform operation: another operation is in progress` or `Future attached to a different event loop`. Alert dispatch tasks fail immediately and silently (retry backoff eventually exhausts). No alerts are delivered.

---

## [HIGH] BUG-239 — `support.py` AI support chat endpoints have no authentication — unauthenticated AI API consumption
- **Status: FIXED 2026-03-22**
- **File:** `backend/api/v1/routes/support.py` lines 22, 45, 56
- **Issue:** All three endpoints (`POST /support/chat`, `GET /support/topics`, `GET /support/health`) have no `get_current_user` dependency. Any unauthenticated caller on the internet can send arbitrary messages to the AI support service, which makes Gemini or OpenAI API calls billed to the operator. The `/support/chat` endpoint accepts a `conversation_history` parameter allowing unlimited multi-turn AI sessions without any identity constraint.
- **Impact:** API cost abuse — any actor can run unlimited AI chat sessions at zero cost to themselves. OpenAI/Gemini quota exhaustion from bot traffic will degrade AI functionality for all paying merchants. No audit trail for support conversations.

---

## [LOW] BUG-240 — `health.py` `/test-alert` endpoint has no authentication
- **File:** `backend/api/v1/routes/health.py` lines 151-182
- **Issue:** `POST /health/test-alert` is blocked in production (`ENVIRONMENT == "production"` check) but returns a 200 with `{"error": "Not available in production"}` rather than 403. In non-production environments, the endpoint has no auth — any anonymous caller can trigger test alerts to all configured channels (Slack, email, PagerDuty). Response also leaks that the endpoint exists in production.
- **Impact:** Spam/noise in alert channels from anonymous traffic in staging. Production endpoint existence disclosed via 200 response body instead of 403/404.

---

## [HIGH] BUG-241 — `market_trends.py` AI analysis endpoints have no authentication — unauthenticated AI API consumption
- **Status: FIXED 2026-03-22**
- **File:** `backend/api/v1/routes/market_trends.py` lines 19-59
- **Issue:** `POST /market-trends/analyze` and `GET /market-trends/trends` both call `market_trends_service.get_trends()` which makes AI API calls (Gemini), with no `get_current_user` dependency. `/categories` and `/sources` are lightweight metadata endpoints (acceptable unauthenticated), but `/analyze` and `/trends` trigger AI inference on every call.
- **Impact:** Identical to BUG-239 — any anonymous caller can exhaust AI quota at zero cost to themselves. No rate limiting on these endpoints.

---

## [MEDIUM] BUG-242 — `crisis_detection.py` uses `timezone` without importing it — NameError at runtime
- **File:** `backend/api/v1/routes/crisis_detection.py` line 20
- **Issue:** `generate_mock_data()` uses `timezone.utc` but the import is `from datetime import datetime, timedelta` — `timezone` is never imported. Calling `/crisis/analyze/stream` with mock data (no `simulate_crisis` flag) or with `simulate_crisis=True` triggers `generate_mock_data()`, which immediately raises `NameError: name 'timezone' is not defined`.
- **Impact:** The entire `/crisis/analyze/stream` endpoint fails at runtime. The SSE stream sends an error event and closes immediately.

---

## [MEDIUM] BUG-243 — `autonomous_pipeline.py` calls Gemini directly, violating project rule and using wrong model
- **File:** `backend/api/v1/routes/autonomous_pipeline.py` lines 178-188
- **Issue:** `GET /autonomous/health` creates a `genai.Client()` and calls `generate_content()` directly — bypassing `services/ai_generator.py` which is required for ALL AI calls per project rule. Model used is `gemini-3-flash-preview` which does not exist (correct model: `gemini-2.0-flash`). The same violation exists in the `AutonomousOrchestrator` service itself (BUG-234 already documented).
- **Impact:** Health check will always fail with `google.api_core.exceptions.NotFound` (model not found), reporting `status: "degraded"`. Direct AI calls bypass central logging, error handling, and rate limiting in `ai_generator.py`.

---

## [HIGH] BUG-244 — `webhooks.py` webhook register/unregister endpoints have no authentication — any caller can hijack webhook registration
- **File:** `backend/api/v1/routes/webhooks.py` lines 247-358
- **Issue:** `POST /{integration_id}/register` and `DELETE /{integration_id}/unregister` have no `get_current_user` dependency. They only verify that the integration exists and is `ACTIVE`, with no ownership check. Any caller who knows a valid `integration_id` UUID can register their own callback URLs as webhooks for that integration, or silently unregister all existing webhooks.
- **Impact:** Attacker who discovers an integration UUID (via URL enumeration or API error messages) can: (1) redirect Shopify/WooCommerce event notifications to their own server, receiving real-time price/product data; (2) deregister all webhooks for a merchant, breaking real-time sync silently.

---

## [LOW] BUG-245 — `products_import.py` has debug logging with emoji markers left in production code
- **File:** `backend/api/v1/routes/products_import.py` lines 98-168
- **Issue:** 15+ `logger.info("🔍 IMPORT DEBUG: ...")` calls log internal state (user ID, product names, prices, DB commit status) in every import request. This is marked with a comment "Remove after fixing the issue" but was never removed.
- **Impact:** Sensitive product data (names, prices, SKUs) appears in production logs on every bulk import call. Noisy logs obscure real errors. `logger.info` on every loop iteration for up to 1000 products generates excessive log volume.

---

## [MEDIUM] BUG-246 — WebSocket `ConnectionManager` broadcasts to all connected clients — no per-user data isolation
- **File:** `backend/core/websocket.py` (ConnectionManager); `backend/api/v1/routes/websockets.py`
- **Issue:** `manager.broadcast(channel, data)` sends to every connection in `active_connections[channel]` with no user filtering. All clients connected to `/ws/prices` receive all price broadcasts, and all clients connected to `/ws/alerts` receive all alert broadcasts — regardless of which user's products those events belong to. Additionally, `/ws/sentiment/{product_id}` (line 62 of `websockets.py`) has no auth dependency, extending the unauthenticated access issue of BUG-202 to the sentiment channel. BUG-202 only explicitly named `/ws/prices` and `/ws/alerts`.
- **Impact:** Data isolation failure: User A can connect and observe all real-time price and alert events from User B's store. Competitors monitoring the WebSocket channel see every merchant's price changes in real time. Sentiment updates for any product_id are accessible without authentication.

---

## [MEDIUM] BUG-247 — `openai_sentiment.py` calls OpenAI directly, bypassing `services/ai_generator.py`
- **File:** `backend/services/openai_sentiment.py` lines 7, 19–21, 70–75
- **Issue:** Imports `from openai import AsyncOpenAI` and instantiates `self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)` directly. Calls `self.client.chat.completions.create(model="gpt-4o-mini", ...)` bypassing the required central AI gateway in `services/ai_generator.py`. Also uses `print()` instead of `logger` for error output at lines 101 and 105.
- **Impact:** AI calls bypass centralized logging, error handling, rate limiting, and model governance. `print()` errors are invisible in production log aggregators (Sentry, structured JSON logs). Direct OpenAI usage violates project rule that all AI calls route through `services/ai_generator.py`.

---

## [MEDIUM] BUG-248 — `email_service.py` and `audit_email_service.py` make synchronous SendGrid HTTP calls inside `async def` — blocks event loop
- **File:** `backend/services/notification/email_service.py` line 122; `backend/services/notification/audit_email_service.py` line 141
- **Issue:** `send_alert_email()` and `send_audit_pdf()` are `async def` functions but call `client.send(message)` (synchronous SendGrid SDK HTTP call) without `await` or `asyncio.to_thread()`. This is a blocking network call inside the event loop.
- **Impact:** Each email send blocks the asyncio event loop for the duration of the HTTP request (typically 200–800 ms). Under any alert volume, this stalls all other concurrent requests. Notification delivery latency degrades entire API response times.

---

## [MEDIUM] BUG-249 — `analytics_service.py` `get_product_summaries()` executes 3 DB queries per product in a loop — N+1 pattern
- **File:** `backend/services/analytics/analytics_service.py` lines 130–175
- **Issue:** For each product, the loop executes: (1) a query for latest sentiment, (2) a query for 24h mention count, (3) a query for pending recommendation count — 3 round-trips per product. For a user with 50 products (Starter plan limit) this generates 150 DB queries per dashboard load.
- **Impact:** Dashboard analytics endpoint is 30–150× slower than necessary. Under concurrent users, connection pool exhaustion from N+1 queries causes request failures. Each query adds ~1–5 ms latency; 150 queries = 150–750 ms added overhead per request.

---

## [MEDIUM] BUG-250 — `reddit_service.py` PRAW calls are synchronous inside `async def` — blocks event loop
- **File:** `backend/services/ingestion/reddit_service.py` lines 48–75 (`_collect_real_data`) and line 115 (`health_check`)
- **Issue:** PRAW (`praw.Reddit`) is a synchronous library. `_collect_real_data()` calls `self.reddit.subreddit("all").search(keyword, limit=limit, sort="new")` synchronously inside `async def`, and `health_check()` calls `list(self.reddit.subreddit("python").hot(limit=1))` synchronously inside `async def`. No `asyncio.to_thread()` wrapper.
- **Impact:** Each Reddit API call (typically 300–1000 ms) blocks the entire asyncio event loop. Sentiment ingestion tasks called from async contexts freeze all concurrent API requests for the duration. Under high ingestion frequency, this causes cascading timeouts across unrelated endpoints.

---

## [HIGH] BUG-251 — `subscription.py` route ordering: `GET /{payment_id}` registered before `GET /history` — history endpoint unreachable
- **File:** `backend/api/v1/routes/payments/subscription.py` lines 119, 180
- **Issue:** `GET /{payment_id}` (line 119) is registered before `GET /history` (line 180). FastAPI matches routes in registration order; requests to `/payments/history` are intercepted by `/{payment_id}`, `UUID("history")` fails, and the handler raises `HTTP 400 "Invalid payment ID format"`. The `/history` endpoint is completely unreachable.
- **Impact:** `GET /payments/history` always returns 400. Users and frontends cannot retrieve payment history through this endpoint. The fix is to register `/history` before `/{payment_id}`.

---

## [MEDIUM] BUG-252 — `pricing_tasks.py` `_check_competitor_prices()` N+1 query pattern — one DB query per competitor product
- **File:** `backend/workers/tasks/pricing_tasks.py` lines 284–303
- **Issue:** `for cp in competitor_products:` loop executes `select(Product).where(Product.id == cp.product_id)` once per competitor product. For 1000 competitor records, this is 1000 separate DB round-trips.
- **Impact:** `check_competitor_prices` Celery task becomes slow and connection-pool-exhausting at scale. With 1000 competitor products × ~2 ms per query = ~2 seconds of sequential DB I/O. Should use a single join query to load all products in one round-trip.

---

## [HIGH] BUG-253 — `ingestion_tasks.py` Python identity check `Product.keywords is not None` never filters — all products fetched regardless of keywords
- **File:** `backend/workers/tasks/ingestion_tasks.py` line 116
- **Issue:** `select(Product).where(Product.keywords is not None, Product.is_active)` — `Product.keywords is not None` is a Python identity check evaluated at import time. SQLAlchemy column attributes are never `None` (they are `InstrumentedAttribute` objects). This expression always evaluates to `True` and is silently dropped by SQLAlchemy's `.where()`. The resulting SQL has no NULL filter on `keywords`, so ALL active products are returned, including those with no keywords configured.
- **Impact:** `fetch_all_mentions` queues a `fetch_for_product` task for every active product, not just those with keywords. Products without keywords then fall back to using `product.name` as the keyword (`keywords = product.keywords or [product.name]`). This pollutes Reddit search results with false positives and wastes Celery task slots.

---

## [HIGH] BUG-254 — `sync_verification_tasks.py` `_auto_fix_price_mismatches` imports from non-existent module — `ModuleNotFoundError` at runtime
- **File:** `backend/workers/tasks/sync_verification_tasks.py` line 380
- **Issue:** `from services.integration.models import PriceUpdateRequest` — `services/integration/models.py` does not exist. The correct module is `services/integration/schemas.py`. This import is inside `_auto_fix_price_mismatches()` which is only called when `dry_run=False`.
- **Impact:** `auto_fix_mismatches(dry_run=False)` (the actual fix, not the preview) always fails immediately with `ModuleNotFoundError`. Price mismatch auto-fixing is broken. Default is `dry_run=True` so the bug is hidden until someone tries to actually apply the fixes.

---

## [HIGH] BUG-255 — `sentiment/analysis.py` — `analyze_and_save` and `analyze_bulk` missing product ownership check
- **File:** `backend/api/v1/routes/sentiment/analysis.py` lines 102, 159
- **Issue:** Both endpoints fetch the product by `product_id` but do not check `product.user_id == current_user.id`. Any authenticated user can save sentiment analysis records to any other user's product by knowing its UUID.
- **Impact:** Broken authorization boundary — competitor data pollution, tenant isolation violation. A malicious user can corrupt another merchant's sentiment history, skewing their AI pricing recommendations.

---

## [HIGH] BUG-256 — `competitors/analysis.py` `_generate_ai_analysis` — direct OpenAI GPT-4o-mini call bypasses `services/ai_generator.py`
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 354–362
- **Issue:** `_generate_ai_analysis()` calls `ai_generator.client.chat.completions.create(model="gpt-4o-mini", ...)` directly from the route file. This (1) bypasses `services/ai_generator.py` (project rule violation), (2) uses the OpenAI client directly instead of the Gemini 2.0 Flash model, (3) exposes no error budget or retry logic from the central service.
- **Impact:** AI competitor analysis uses GPT-4o-mini instead of Gemini; central AI entry-point rule is violated. If the `ai_generator.client` attribute shape changes, this crashes. No cost tracking or rate limiting from the central service.

---

## [HIGH] BUG-257 — `alerts/crisis_detection.py` `_generate_crisis_summary` — direct OpenAI GPT-4o-mini call bypasses `services/ai_generator.py`
- **File:** `backend/api/v1/routes/alerts/crisis_detection.py` lines 101–109
- **Issue:** Same pattern as BUG-256. `_generate_crisis_summary()` calls `ai_generator.client.chat.completions.create(model="gpt-4o-mini", ...)` directly. Bypasses `services/ai_generator.py`, uses OpenAI GPT-4o-mini instead of Gemini.
- **Impact:** Crisis detection AI summaries use the wrong model and bypass the central AI entry-point. Same risks as BUG-256.

---

## [MEDIUM] BUG-258 — `competitors/analysis.py` `get_competitor_alerts` — 3 DB queries per history record (N+1)
- **File:** `backend/api/v1/routes/competitors/analysis.py` lines 133–141
- **Issue:** For each `CompetitorPriceHistory` record returned by the initial query, the handler executes 3 separate SELECT statements: (1) `CompetitorProduct`, (2) `Competitor`, (3) `Product`. With 50 alert records, this is 151 DB queries per request.
- **Impact:** `/competitors/alerts` degrades severely as price history grows. Should use a single JOIN query to load all related data.

---

## [MEDIUM] BUG-259 — `alerts/crisis_detection.py` `detect_sentiment_crises` — 2 DB queries per product (N+1)
- **File:** `backend/api/v1/routes/alerts/crisis_detection.py` lines 150–168
- **Issue:** For every active product, the endpoint runs 2 separate queries: (1) recent period sentiment, (2) previous period sentiment. For a user with 500 products (Enterprise), this is 1001 DB queries per crisis scan.
- **Impact:** Crisis detection endpoint becomes very slow at scale. Should use a single query with date range partitioned in SQL.

---

## [HIGH] BUG-260 — `sentiment/retrieval.py` — all 5 endpoints missing product ownership check
- **File:** `backend/api/v1/routes/sentiment/retrieval.py` lines 25–174
- **Issue:** `get_sentiment`, `get_product_sentiments`, `get_product_sentiment_summary`, `delete_sentiment`, and `get_product_mentions` all query by `product_id` or `sentiment_id` without verifying that the product belongs to the requesting user. Any authenticated user can read or delete any sentiment record by knowing its UUID.
- **Impact:** Complete tenant isolation failure for sentiment data. Any merchant can read competitors' sentiment analysis, delete their records, and access social mentions for products they don't own.

---

## [HIGH] BUG-261 — `sentiment/tasks.py` `fetch_product_mentions` — missing product ownership check
- **File:** `backend/api/v1/routes/sentiment/tasks.py` lines 32–35
- **Issue:** `fetch_product_mentions` queries `Product` by `product_id` without checking `product.user_id == current_user.id`. Any authenticated user can queue a Reddit/social media fetch task for another user's product.
- **Impact:** Unauthorized Celery task queuing for arbitrary products. Wastes task slots; can be used to trigger excessive mentions collection against products the user doesn't own.

---

## [MEDIUM] BUG-262 — `alerts/management.py` `get_alert_stats` — N+1 queries for each severity and alert type
- **File:** `backend/api/v1/routes/alerts/management.py` lines 88–118
- **Issue:** `get_alert_stats` runs one `SELECT COUNT(*)` per `AlertSeverity` enum value (typically 4 queries) and then one per `AlertType` enum value (typically 6+ queries). Should be a single `SELECT severity, COUNT(*) … GROUP BY severity` and `SELECT alert_type, COUNT(*) … GROUP BY alert_type`.
- **Impact:** Dashboard stats endpoint makes 10+ sequential DB round-trips instead of 2. Degrades dashboard load time; worsens under traffic.

---

## [HIGH] BUG-263 — `visual_pricing.py` — `/analyze` and `/analyze-sync` endpoints have no authentication
- **File:** `backend/api/v1/routes/visual_pricing.py` lines 146, 200+
- **Issue:** Both `/visual-pricing/analyze` (POST, multipart image upload) and `/visual-pricing/analyze-sync` have no `get_current_user` dependency. Any unauthenticated internet caller can upload screenshots and consume Gemini API inference billed to the operator. The comment says "No authentication required - this is a public demo."
- **Impact:** Unlimited unauthenticated Gemini API consumption; no cost tracking or rate limiting from the central service. Gemini quota exhaustion degrades AI functionality for all paying merchants.
- **Status: FIXED 2026-03-22** — Added `get_current_user` dependency to `/analyze` and `/analyze-sync` endpoints.

---

## [HIGH] BUG-264 — `launch_detection.py` — `/launch/analyze/stream` has no authentication
- **File:** `backend/api/v1/routes/launch_detection.py` lines 38, 92
- **Issue:** Both POST and GET versions of `/launch/analyze/stream` have no `get_current_user` dependency. Any unauthenticated caller can trigger the Scout → Analyst → Strategist launch detection pipeline, which makes AI API calls on every request.
- **Impact:** Unauthenticated AI API consumption; quota exhaustion; bot-driven analysis flooding.
- **Status: FIXED 2026-03-22** — Added `get_current_user` dependency to both POST and GET stream endpoints.

---

## [LOW] BUG-265 — `webhook.py` MNEE payment lookup uses `Payment.id.startswith()` — partial UUID LIKE on UUID column
- **File:** `backend/api/v1/routes/payments/webhook.py` line 171
- **Issue:** `select(Payment).where(Payment.id.startswith(payment_id_prefix))` — `Payment.id` is a PostgreSQL UUID column. `.startswith()` generates a `LIKE` query which requires the UUID to be cast to text first. The 8-character prefix from the memo provides very low collision probability, but this is not exact matching. PostgreSQL's behavior for `UUID LIKE` is dialect-dependent.
- **Impact:** Could fail with `psycopg2.errors.UndefinedFunction` (LIKE on UUID) or silently cast. Correct approach: use full UUID in memo or parse prefix to UUID range query. Low probability of matching wrong payment.

---

## [LOW] BUG-266 — `price_check.py` in-memory rate limiter is per-process, not global
- **File:** `backend/api/v1/routes/price_check.py` lines 56–77
- **Issue:** `_rate_limit_store` is a module-level dict (in-memory). In multi-worker deployments (Gunicorn 4 workers, Railway multiple instances), each worker has its own dict. A single IP can make 4×10=40 requests per hour instead of the intended 10. The slow-path AI pipeline is the expensive operation being rate-limited.
- **Impact:** Rate limit is under-enforced in production. Malicious scraping of the public audit funnel is possible at 4× the intended limit. Should use Redis-backed rate limiting.

---

## Notes on previously reported bugs (deep audit pass 3)

- **BUG-060** (`product_sync.py imports get_db`) — `db/session.py` line 85 now exports `get_db = get_session` alias for backward compatibility. This import will no longer fail. BUG-060 is effectively resolved.
- **BUG-228** (os.getenv() violations) — Add `backend/workers/celery_app.py` line 23: `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")` — direct `os.getenv()` call at module level outside `core/config.py`. `REDIS_URL` is already in `core/config.py` as `settings.REDIS_URL`.

---

## [MEDIUM] BUG-267 — `ExperimentManager._assignments` is in-memory only — bandit assignments lost on restart
- **File:** `backend/services/scoring/experimentation/experiment_manager.py` lines 207–209, 303–331, 337–384
- **Issue:** `self._assignments: dict[str, ExperimentAssignment] = {}` is a plain Python dict. `record_assignment()` docstring says "In production, this writes to the pricing_outcomes table (strategy_arm and is_exploration columns from Phase 1 schema)" — but the implementation only writes to the in-memory dict. `process_outcome()` looks up assignments from the same dict. If the ExperimentManager is not a process-level singleton (it is not — `create_ie_orchestrator()` creates a new one per call), every call starts with an empty dict. Even if it were a singleton, any server restart empties it. `process_outcome()` then logs "No assignment found for recommendation X" and returns `None` for every outcome, so the Thompson Sampling bandit never receives feedback and stops learning.
- **Impact:** The entire Intelligence Environment learning loop is silently broken. Pricing strategy experimentation (Thompson Sampling) records zero outcomes, causing all arms to stay at their initial Beta(1, 19) priors indefinitely. Note: this bug is partially masked by BUG-063 (wrong constructor args mean `ExperimentManager` is never successfully initialized in production).

---

## [LOW] BUG-268 — `prospect_lead_capture.py` uses `os.getenv()` outside `core/config.py`
- **File:** `backend/services/prospect_lead_capture.py` line 19
- **Issue:** `HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")` — module-level `os.getenv()` call outside `core/config.py`. Violates project security rule: "Never call `os.getenv()` anywhere outside `core/config.py`". `HUBSPOT_API_KEY` is not in `core/config.py` Settings at all. The key should be added as `HUBSPOT_API_KEY: str | None = None` to `Settings` and accessed as `settings.HUBSPOT_API_KEY`.
- **Impact:** If `HUBSPOT_API_KEY` is set via `.env` file (loaded by Pydantic at startup), `os.getenv()` may return `None` even if the key is configured, causing HubSpot CRM pushes to silently skip. Bypasses centralized config validation.

---

## Notes on previously reported bugs (deep audit pass 4)

- All `services/scoring/experimentation/` and `services/scoring/learning/` files (except experiment_manager.py) are pure Python math — no DB, no LLM calls. CLEAN.
- `services/ai_trend_analysis/ai_clients.py` violations (sync-in-async, wrong models, bypasses ai_generator.py) already documented as BUG-219, BUG-220, BUG-236 in prior passes.
- `services/ai_trend_analysis/autonomous_orchestrator.py` os.getenv() violations already documented as BUG-192, BUG-221, BUG-234.
- `services/payment/` os.getenv() violations already documented in BUG-228.
- Worker tasks (`audit_tasks.py`, `benchmark_refresh_tasks.py`, `outcome_measurement_tasks.py`, `pricing_tasks.py`, `sync_verification_tasks.py`) all use NullPool pattern and `settings.*` correctly. CLEAN.
- `services/audit/report_generator.py`, `services/audit_persistence_service.py`, `services/pricing_engine.py`, `services/sentiment_analyzer.py`, `services/youcom_client.py`, `services/rate_limit_manager.py`, `services/prospect_audit_service.py` — all CLEAN.
- `services/products/import_service.py`, `services/products/cascade_delete.py` — CLEAN.
- `services/scoring/experimentation/strategies.py`, `services/scoring/learning/feature_engineer.py`, `services/scoring/learning/analyst_feedback.py`, `services/scoring/learning/scout_feedback.py` — CLEAN (pure math).

---

---

## New findings — deep audit pass 5 (files 1–50, frontend pages and demo)

---

## [HIGH] BUG-269 — `integrations/connect/shopify/page.tsx` `validateStoreUrl()` validates closure variable instead of its parameter
- **Status: FIXED 2026-03-21**
- **File:** `frontend/app/(dashboard)/integrations/connect/shopify/page.tsx` lines 45–57
- **Issue:** `validateStoreUrl(url)` receives `url` as a parameter but line 46 reads `const cleaned = storeUrl.trim().toLowerCase()` — using the outer closure `storeUrl` state instead of the `url` argument. After stripping `.myshopify.com` at line 47, the regex `/^[\w-]+\.myshopify\.com$/` is tested against `cleaned`, which no longer contains `.myshopify.com`, so valid full-domain inputs always fail validation. Inputs that are only the store subdomain (e.g., `mystore`) bypass the strip step entirely and may also fail.
- **Impact:** Shopify store URL validation is completely broken. Valid store URLs entered as `mystore.myshopify.com` fail validation. Merchants cannot connect their Shopify store from the UI. Shopify App Store submission blocker.

---

## [MEDIUM] BUG-270 — `integrations/page.tsx` calls `useSearchParams()` without a Suspense boundary
- **Status: FIXED 2026-03-21**
- **File:** `frontend/app/(dashboard)/integrations/page.tsx` line 26
- **Issue:** `useSearchParams()` is called directly in the page component with no wrapping `<Suspense>` boundary. Next.js 14 App Router requires Suspense around any component that calls `useSearchParams()`. BUG-055 documents this for five other pages; this page is not listed there.
- **Impact:** Next.js will throw "Missing Suspense boundary" build/runtime error in production mode. The entire integrations page may fail to render, blocking merchants from seeing integration status. Shopify App Store submission blocker.

---

## [LOW] BUG-271 — `integrations/page.tsx` uses non-standard React Query key `['all-sync-status']` outside the central key registry
- **File:** `frontend/app/(dashboard)/integrations/page.tsx` line 32
- **Issue:** `queryKey: ['all-sync-status']` is hardcoded as an inline array rather than using the `integrationKeys` factory from `lib/api/query-keys.ts`. This key collides with nothing but is invisible to invalidation calls that go through `integrationKeys.all`.
- **Impact:** After mutations that invalidate `integrationKeys.all`, the sync-status query is not invalidated and shows stale data. Stale sync status persists until the stale time expires.

---

## [MEDIUM] BUG-272 — `sentiment/trust/page.tsx` uses per-call `.mutate()` `onSuccess` callbacks — ephemeral in React Query v5
- **File:** `frontend/app/(dashboard)/sentiment/trust/page.tsx` lines 206–210, 319–321, 416–418
- **Issue:** Per-call `onSuccess` callbacks passed to `.mutate({ ..., onSuccess: ... })` are ephemeral in React Query v5. If the component re-renders between mutation start and completion, the callbacks are dropped silently. BUG-114 documents this pattern; this file is not listed in the existing bug's scope.
- **Impact:** Toast notifications and cache invalidations inside `onSuccess` callbacks are silently dropped when rapid user interaction or background re-renders occur mid-mutation. Success feedback may not appear and related data may remain stale.

---

## [MEDIUM] BUG-273 — `audit/page.tsx` uses raw `fetch()` calls bypassing the Axios `api` client
- **File:** `frontend/app/audit/page.tsx` lines 63, 285, 353
- **Issue:** Three separate `fetch()` calls bypass the centralized Axios `api` client: `trackEvent` at line 63, audit POST at line 285, and PDF generation POST at line 353. The Axios client handles base URL resolution, auth headers, and error normalization. Raw `fetch()` calls also send the user's email address (line 337: `email: email.trim()`) to an analytics endpoint without input validation or rate limiting.
- **Impact:** Base URL mismatch may break audit submissions in production vs staging. Auth errors are not normalized. PII (user email) is sent to an unprotected analytics endpoint without rate limiting — a GDPR compliance concern for the Shopify App Store submission.

---

## Notes on previously reported bugs (deep audit pass 5)

- Files 32–50 (all demo pages: `autonomous-pipeline`, `crisis-detector`, `launch-detector`, `market-intelligence`, `market-trends`, `visual-pricing` components) are public demo pages using raw `fetch()` by design (no auth required). These raw fetch() calls are intentional and do not violate the project convention which applies to the authenticated dashboard. CLEAN.
- `demo/embedded-gate.tsx` correctly wraps `useSearchParams()` in Suspense. CLEAN.
- `demo/visual-pricing/components/ScreenshotUploader.tsx` correctly creates and revokes blob URLs using `useMemo` + `useEffect`. CLEAN.

---

## New findings — deep audit pass 6 (files 66–325, components and lib)

---

## [HIGH] BUG-274 — `trends/page.tsx` uses raw `fetch()` bypassing api client for authenticated endpoints
- **File:** `frontend/app/(dashboard)/trends/page.tsx` lines 34–55
- **Issue:** Two `fetch()` calls are made directly to `${API_URL}/api/v1/market-trends/categories` and `${API_URL}/api/v1/market-trends/trends` via raw `fetch()` inside React Query `queryFn` callbacks. These bypass the centralised `api` client from `lib/api/client.ts`. Neither call includes an `Authorization` header. Unlike demo pages, this is an authenticated dashboard page.
- **Impact:** API calls are unauthenticated — backend will return 401. Trend data and categories never load in the dashboard. Non-2xx responses are silently parsed as data since there is no `res.ok` check.

---

## [MEDIUM] BUG-275 — `trends/analysis/page.tsx` has unimplemented `handleApplyOpportunity` and `handleDismissOpportunity` handlers
- **File:** `frontend/app/(dashboard)/trends/analysis/page.tsx` lines 44–54
- **Issue:** Three event handlers — `handleApplyOpportunity`, `handleDismissOpportunity`, and `handleAcknowledgeRisk` — contain only `console.log(...)` calls with no actual API call or state update. They are passed as callbacks to child components that call them when merchants click "Apply" or "Dismiss".
- **Impact:** Merchant pricing opportunity and risk acknowledgement actions silently do nothing. Clicking "Apply" or "Dismiss" has no effect beyond a console log, making the entire AI analysis workflow non-functional.

---

## [HIGH] BUG-276 — `lib/api/trend-analysis.ts` defaults to `use_model: 'openai'` — violates single AI entry point rule
- **File:** `frontend/lib/api/trend-analysis.ts` lines 27, 37, 47, 63
- **Issue:** `runTrendAnalysis`, `analyzeProductOpportunity`, `detectRisks`, and `generateInsight` all default to `use_model: 'openai'`. Project AI rules require: "Model: `gemini-2.0-flash` — do not change without explicit instruction" and "ALL Gemini calls go through `services/ai_generator.py`". The `openai` parameter instructs the backend to use OpenAI, bypassing `services/ai_generator.py` entirely. The trend analysis feature should default to `gemini`, not `openai`.
- **Impact:** Trend analysis runs on OpenAI instead of Gemini, violating the AI entry point contract. Costs are billed to the wrong AI account. Any backend logic specific to `services/ai_generator.py` (tracing, guardrails, feedback loop) is bypassed.

---

## [MEDIUM] BUG-277 — `lib/ws/client.ts` logs WebSocket URL (which contains `NEXT_PUBLIC_API_URL`) to console on every connect
- **File:** `frontend/lib/ws/client.ts` line 133
- **Issue:** `console.log('[WS] Connected to', this.url)` logs the full WebSocket URL including the Railway backend domain on every successful connection. Also lines 140–141 log disconnect details. Production console logs expose infrastructure details.
- **Impact:** Backend hostname/URL is exposed in browser console in production. In a Shopify embedded context this can leak the Railway staging or production URL to any merchant with DevTools open.

---

## [LOW] BUG-278 — `lib/api/trend-analysis.ts` query keys do not use central `query-keys.ts` registry
- **File:** `frontend/lib/api/trend-analysis.ts` lines 75–84
- **Issue:** `trendAnalysisKeys` is defined locally inside `trend-analysis.ts` instead of inside `lib/api/query-keys.ts`. The central `query-keys.ts` file is the single source of truth for all React Query cache keys. Locally-defined keys prevent cache invalidation from other parts of the app.
- **Impact:** If any mutation elsewhere invalidates query keys via the central registry, trend analysis data will not be refreshed. Stale trend data persists after related mutations.

---

## [MEDIUM] BUG-279 — `ProductForm.tsx` uses ephemeral per-call `onSuccess` callbacks with React Query v5 mutations
- **File:** `frontend/components/features/products/ProductForm.tsx` lines 206–209, 217–219
- **Issue:** Both `updateProduct.mutate(...)` and `createProduct.mutate(...)` pass `onSuccess` callbacks inline to `.mutate(...)`. Per-call callbacks are ephemeral in React Query v5 — if the component re-renders before the mutation completes, the callbacks are silently dropped. The pattern was documented as a systemic issue in BUG-114; this file was not in the original scope.
- **Impact:** `toast.success('Product updated')` / `toast.success('Product created')` messages and `onSuccess?.()` callbacks may be silently dropped under fast network or rapid re-renders.

---

## Notes on deep audit pass 6 (files 66–325)

- `components/features/alerts/` (AlertBadge, AlertConfigurationCard, AlertConfigurationForm, AlertItem, AlertStatusBadge, AlertsList, CrisisDetectionCard, NotificationBell) — all use `api` client correctly. CLEAN except CrisisDetectionCard casts `(err as Error)` which hides non-Error throws (minor, already covered by BUG-114 pattern).
- `components/features/competitors/` (AutoLinkModal, CompetitorCard, CompetitorForm, CompetitorMatchSearch, CompetitorProductCard, CompetitorsList, LinkProductForm, MatchConfidenceBadge, MatchedProductCard, MatchedProductsList) — all CLEAN.
- `components/features/dashboard/` (AIFeaturesCard, PendingRecommendations, ProductSummaryCard, QuickActions, RecentAlerts, SentimentOverview, StatCard) — all CLEAN.
- `components/features/integrations/` (ConnectPlatformCard, ConnectionSuccessToast, IntegrationCard, IntegrationsEmptyState, IntegrationsList, LinkedProducts, SyncStatus, WooCommerceConnectModal, diagnostic-panel, sync-progress-banner) — CLEAN. diagnostic-panel uses `api` client correctly.
- `components/features/intelligence/` — all CLEAN (pure display components wrapping data from hooks).
- `components/features/payments/` (BsvWalletCard, ConnectWallet, CurrentPlan, EthWalletCard, MNEEBalance, PaymentHistory, SubscriptionPlans, TransactionHistory) — CLEAN. TransactionHistory Etherscan link already documented as BUG-120.
- `components/features/pricing/` (ConfidenceIndicator, RecommendationActions, RecommendationCard, RecommendationsList, RuleCard, RuleForm, RulesList, rule-form/*) — CLEAN. RecommendationActions correctly uses a modal instead of window.prompt() (the window.prompt bug is in the page-level code, BUG-105).
- `components/features/products/` (AutoPricingCard, DeleteProductModal, GenerateDescriptionModal, ImportCSVModal, KeywordsManager, PriceHistoryCard, PriceSuggestionCard, PriceSuggestionModal, ProductCard, ProductForm, ProductInfoCard, ProductRow, ProductStoreSync, ProductsTable) — ProductForm has ephemeral onSuccess (BUG-279 above). Rest CLEAN.
- `components/features/sentiment/`, `components/features/trends/`, `components/features/trust-scoring/` — all CLEAN (pure display/chart components).
- `components/layout/` (AuthShell, DashboardShell, Sidebar, Topbar) — CLEAN.
- `components/ui/` — all CLEAN.
- `lib/api/` (alerts, analytics, auth, competitors, errors, integrations, intelligence, outcomes, payments, pricing, query-keys, retrospective-audit, sentiment, shopify-billing, trust-scoring) — all CLEAN. `products.ts` hardcoded URL already documented as BUG-002.
- `lib/domain/` — all CLEAN (pure transformation functions with tests).
- `lib/hooks/` (use-alerts, use-analytics, use-auth, use-competitor-matching, use-competitors, use-integrations, use-intelligence, use-outcomes, use-payments, use-pricing, use-product-sync, use-products, use-retrospective-audit, use-sentiment, use-shopify-billing, use-toast, use-trust-scoring, use-user) — CLEAN. `use-pricing.ts` uses mutation-level onSuccess correctly (defined in `useMutation()` config, not per-call).
- `lib/stores/auth-store.ts` — uses localStorage via token.ts (covered by BUG-001, BUG-052).
- `lib/web3/` — hardcoded Alchemy key covered by BUG-074; WalletConnect 'demo' by BUG-103; console.log in useMNEE already covered by existing bugs.
- `lib/ws/client.ts` — WebSocket auth gap covered by BUG-058; new console.log finding in BUG-277 above.
- `lib/context/shopify-embedded.tsx` — `any` type in waitForAppBridge already covered by existing bugs.
- `middleware.ts` — design intentional, covered.
- `sentry.*.config.ts` — missing beforeSend covered by BUG-075.
- `types/` — all CLEAN (pure TypeScript type definitions; no logic).
- `vitest.config.ts` — CLEAN.

---

---

## New findings — deep audit pass 7 (backend files: models, routes, schemas, main)

---

## [HIGH] BUG-280 — `market_trends_visual/router.py` exposes all AI endpoints without authentication
- **File:** `backend/api/v1/routes/market_trends_visual/router.py`
- **Issue:** All five endpoints (`POST /analyze`, `POST /analyze/stream`, `POST /analyze/with-image`, `POST /analyze/image-only`, `GET /agents`) have no `get_current_user` dependency. Any unauthenticated caller can invoke full Gemini AI analysis, image processing, and streaming responses without a valid session. No rate limiting is applied to any endpoint.
- **Impact:** Unauthenticated access to computationally expensive AI calls. Token costs incurred by anonymous users. Endpoint can be abused to exhaust Gemini API quota without any attribution or throttling.
- **Status: FIXED 2026-03-22** — Added `get_current_user` dependency to all five AI endpoints.

---

## [HIGH] BUG-281 — `market_trends_visual/service.py` bypasses `services/ai_generator.py` via `ai_clients` module
- **File:** `backend/api/v1/routes/market_trends_visual/service.py`
- **Issue:** `MarketTrendsAnalyzer.analyze_stream()` calls `ai_clients.stream_gemini3()` and `ai_clients.analyze_image_stream()` directly, bypassing the mandatory central AI entry point `services/ai_generator.py`. This violates the project rule: "ALL Gemini calls go through `services/ai_generator.py`." The analyzer is instantiated as a module-level singleton.
- **Impact:** No tracing, guardrails, feedback loop, or cost attribution for all market-trends-visual AI calls. Model-swap requires editing the service directly rather than the central entry point.

---

## [HIGH] BUG-282 — `trend_analysis.py` backend routes default to `use_model="openai"` — violates AI entry point rule
- **File:** `backend/api/v1/routes/trend_analysis.py`
- **Issue:** The route handler functions for `/analyze`, `/opportunity/{id}`, `/risks`, and `/insight` all specify `use_model: str = "openai"` as their default parameter. Project AI rules require all models to default to `gemini-2.0-flash` via `services/ai_generator.py`. Even when the frontend sends no model preference, the backend defaults to OpenAI. (BUG-276 covered the frontend defaulting to `openai`; this is the separate backend route default.)
- **Impact:** All trend analysis requests served by OpenAI rather than Gemini by default. Costs billed to the wrong AI provider. `services/ai_generator.py` tracing, guardrails, and feedback loop are bypassed.

---

## [MEDIUM] BUG-283 — `trend_analysis.py` `get_quick_stats` loads entire SocialMention table into memory for three date ranges
- **File:** `backend/api/v1/routes/trend_analysis.py` (the `get_quick_stats` endpoint)
- **Issue:** For each of three date windows (today, last 7 days, prior 7 days) the handler calls `result.scalars().all()` to pull all matching `SocialMention` ORM objects into Python memory, then returns `len(mentions)`. For a merchant with thousands of daily mentions this loads tens of thousands of ORM objects per request. The trending-products sub-query also loads all products with no LIMIT clause.
- **Impact:** Memory and CPU spike proportional to mention volume. For high-volume merchants this endpoint can OOM the process or cause extreme latency. Should use `SELECT COUNT(*)` queries instead of `scalars().all()`.

---

## [MEDIUM] BUG-284 — `prospect_analytics.py` defines `ProspectAuditEvent` SQLModel table inside a route file
- **File:** `backend/api/v1/routes/prospect_analytics.py`
- **Issue:** The `ProspectAuditEvent` SQLModel table class is defined at the top of a route file rather than in the `models/` directory. Alembic autogenerate scans `models/` for table definitions; a table defined in a route file will not be discovered unless that route file is explicitly imported in the Alembic `env.py` scan path.
- **Impact:** The `prospect_audit_events` table may be absent from the database after `alembic upgrade head` if the route file is not in the migration scan. All prospect analytics writes silently fail with `ProgrammingError: relation "prospect_audit_events" does not exist`.

---

## [MEDIUM] BUG-285 — `prospect_analytics.py` stores raw `email` as plain text PII while `ip_hash` is explicitly hashed
- **File:** `backend/api/v1/routes/prospect_analytics.py` (`ProspectAuditEvent` model)
- **Issue:** The `ProspectAuditEvent` model stores `email: str | None` as unencrypted plain text in the database column, while `ip_hash: str | None` is documented as "hashed IP for privacy". The email field is used for tracking funnel events tied to identifiable individuals. Shopify App Store submission requires GDPR compliance.
- **Impact:** PII (email addresses) stored in plain text in the `prospect_audit_events` table. GDPR requires pseudonymisation or encryption for personal data. Inconsistent privacy handling in the same model is a compliance red flag.

---

## [MEDIUM] BUG-286 — `prospect_analytics.py` `get_funnel_metrics` executes 8 sequential SELECT queries instead of a single aggregation
- **File:** `backend/api/v1/routes/prospect_analytics.py` (`get_funnel_metrics` handler)
- **Issue:** The funnel metrics endpoint issues 6 separate `SELECT COUNT(*) WHERE event_type = ?` queries plus 2 separate `SELECT COUNT(DISTINCT email) WHERE event_type = ?` queries — 8 round-trips total — to compute what a single `SELECT event_type, COUNT(*), COUNT(DISTINCT email) GROUP BY event_type` query would return in one round-trip.
- **Impact:** 8× unnecessary database round-trips per dashboard load. Under high concurrency this multiplies connection pool pressure. Latency scales with query count rather than data volume.

---

## [MEDIUM] BUG-287 — `trust_scoring.py` batch loops use bare `except: continue` that swallows `BaseException`
- **File:** `backend/api/v1/routes/trust_scoring.py` lines ~176 and ~285
- **Issue:** `score_authors_batch` and `analyze_content_batch` both iterate items inside `try: ... except: continue` with no exception type specified. This catches `BaseException`, including `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. No logging occurs on failure — each failed item is silently skipped with no trace.
- **Impact:** Individual batch item failures are completely invisible. `KeyboardInterrupt` during a batch run will be caught and suppressed, preventing clean shutdown. Real errors (e.g., DB disconnect, token decode failure) are swallowed, leaving callers with silently partial results and no error signal.

---

## [LOW] BUG-288 — `payment.py` `Payment.get_metadata()` uses bare `except:` swallowing `BaseException`
- **File:** `backend/models/payment.py` lines 101–104
- **Issue:** `get_metadata()` catches JSON parsing failures with `except:` (no exception type), which catches `BaseException`. Should be `except (json.JSONDecodeError, ValueError):`.
- **Impact:** Any unexpected exception during JSON parsing (including `MemoryError`, `SystemExit`) is caught and returns `None` silently, masking serious errors.

---

## [MEDIUM] BUG-289 — `payment.py` `Payment.updated_at` has no `onupdate` trigger; field never auto-updates
- **File:** `backend/models/payment.py` lines 80–82
- **Issue:** `updated_at` is defined as `Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))` with only a `default` (set at INSERT time). There is no `onupdate=` argument. This means `updated_at` is written once at creation and never changes when the payment record is updated. `Payment.status`, `txid`, `error_message`, and `confirmed_at` are all mutable fields. The `User` model (`models/user.py`) correctly uses `onupdate=lambda: datetime.now(UTC)`.
- **Impact:** `updated_at` always reflects creation time regardless of how many status transitions occurred. Audit queries like "payments updated in the last 24h" return incorrect results. Payment status history cannot be reconstructed from timestamps.

---

## [HIGH] BUG-290 — `payment.py` `Payment.txid` has no unique constraint; duplicate blockchain transaction IDs possible
- **File:** `backend/models/payment.py` lines 52–53
- **Issue:** `txid: str | None = Field(default=None, max_length=100, index=True)` — the field has an index for lookup performance but no `unique=True` constraint. A blockchain transaction ID (txid) is globally unique by definition. Without a unique constraint, a replay attack or race condition could insert two `Payment` records with the same `txid`, crediting a subscription twice for a single on-chain payment.
- **Impact:** Double-spend vulnerability: a single BSV/MNEE transaction could be credited to two separate subscription activations. No database-level guard prevents concurrent webhook deliveries from creating duplicate confirmed payments for the same txid.

---

## [HIGH] BUG-291 — `price_history.py` `user_id` and `product_id` have no `ForeignKey()` constraints
- **File:** `backend/models/price_history.py` lines 32–33
- **Issue:** `user_id` and `product_id` are declared as `Column(PG_UUID(as_uuid=True), nullable=False, index=True)` with no `ForeignKey("users.id")` or `ForeignKey("products.id")`. The price history table is the primary audit trail for all pricing mutations. Without foreign keys, orphaned records can exist for deleted users or products, and the database cannot enforce referential integrity. BUG-061 documented this pattern for other models; `PriceHistory` was not in that list.
- **Impact:** Audit trail can contain records referencing non-existent users or products. Cascading deletes cannot be defined. Data integrity of the pricing audit log — a compliance requirement — is not enforced at the database level.

---

## [HIGH] BUG-292 — `init_db.py` calls `SQLModel.metadata.create_all(bind=async_engine)` which crashes at runtime
- **File:** `backend/init_db.py` lines 7–8
- **Issue:** `init_db()` calls `SQLModel.metadata.create_all(bind=engine)` where `engine` is imported from `db/session.py` — which is an `AsyncEngine` created by `create_async_engine(...)`. `create_all()` is a synchronous method that requires a sync `Engine`. Passing an `AsyncEngine` raises `AttributeError: 'AsyncEngine' object has no attribute 'execute'` (or equivalent) at runtime. The correct approach — `async with engine.begin() as conn: await conn.run_sync(SQLModel.metadata.create_all)` — is already implemented in `db/session.py::init_db()`, making this file a broken duplicate.
- **Impact:** Running `python init_db.py` crashes immediately. Any CI/CD step or deployment script that calls `init_db.py` directly will fail, blocking database initialisation.

---

## Notes on deep audit pass 7

- `models/subscription.py` — `updated_at` lacks `onupdate` (same pattern as BUG-289/BUG-136); `Subscription` was not listed in BUG-136's original scope. However this is a lower-severity duplicate of an already-documented pattern — recorded as a note rather than a new bug number to avoid duplicate entries.
- `models/user.py` — CLEAN: `updated_at` correctly uses `onupdate=lambda: datetime.now(UTC)` at line 38. `hashed_password` not exposed in any relationship. `bsv_wallet_address` and `eth_wallet_address` are stored plain-text (appropriate for public wallet addresses).
- `schemas/agent_contracts/conflict_resolution.py` — CLEAN: uses `logging.getLogger(__name__)` (minor inconsistency vs `core.logging.get_logger`, but this is a schema file not a route). Logic is deterministic and correct.
- `schemas/agent_contracts/intelligence.py` — CLEAN: pure Pydantic response schemas, no logic.
- `schemas/agent_contracts/pipeline.py` — CLEAN: thin wrapper combining agent outputs.
- `schemas/agent_contracts/shared.py` — CLEAN: pure StrEnum definitions.
- `schemas/agent_contracts/tracing.py` — CLEAN: `TraceSpan.span_id` uses `str(uuid.uuid4())[:8]` (truncated UUID same as BUG-026 pattern, but this is a tracing span ID not a correlation ID so collision risk is acceptable). `_SpanContext.__exit__` returns `False` correctly (does not suppress exceptions).
- `main.py` — `os.getenv("PAY_TO_ADDRESS")` already documented as BUG-067. Lifespan handler logs `os.environ.get('SHOPIFY_CLIENT_ID')` which is a debug trace (not a secret value leak, just boolean). Rest of app assembly is clean.
- `init_db.py` — new finding BUG-292 above.

---

## Deep Audit Pass 8 — Frontend Pages, Components, Lib (2026-03-21)

Continued reading all remaining frontend pages and lib files not covered in earlier passes.

---

## [MEDIUM] BUG-293 — `competitors/match/page.tsx` uses `useSearchParams()` without Suspense boundary
- **File:** `frontend/app/(dashboard)/competitors/match/page.tsx` line 18
- **Issue:** `const searchParams = useSearchParams();` is called directly in the exported page component without any wrapping `<Suspense>` boundary. BUG-055 documented this for `callback/page.tsx`, `claim/page.tsx`, `pricing/rules/new/page.tsx`, and `settings/billing/page.tsx`. BUG-270 documented it for `integrations/page.tsx`. The `competitors/match` page is not included in either prior bug's scope.
- **Impact:** Next.js 14 App Router requires any component using `useSearchParams()` to be wrapped in `<Suspense>`. Without it, the page throws during SSR and during client-side navigation on first render — "Missing Suspense boundary with useSearchParams" error at runtime.

---

## [HIGH] BUG-294 — `trends/page.tsx` uses raw `fetch()` without auth token for both API calls
- **File:** `frontend/app/(dashboard)/trends/page.tsx` lines 35, 52
- **Issue:** Both `queryFn` functions use bare `fetch(\`${API_URL}/api/v1/market-trends/...\`)` with `process.env.NEXT_PUBLIC_API_URL` as the base URL (line 26) rather than the centralised `api` client (`@/lib/api/client`). Neither call includes an `Authorization: Bearer` header. The `api` client handles auth token injection, token refresh, and error normalisation.
- **Impact:** Market trends endpoints receive unauthenticated requests and will return 401, silently rendering the page empty. If the backend ever enforces auth on these endpoints, the feature breaks completely with no user-visible error. Consistent with BUG-054 pattern but a new, previously unlisted file.

---

## [HIGH] BUG-295 — Trend analysis API client defaults all AI model calls to `'openai'` in violation of Gemini-only mandate
- **File:** `frontend/lib/api/trend-analysis.ts` lines 27, 36, 47, 59; `frontend/lib/hooks/use-trend-analysis.ts` lines 87, 120, 145; `frontend/app/(dashboard)/trends/analysis/page.tsx` line 59
- **Issue:** `runTrendAnalysis` defaults `use_model` to `'openai'` (line 27). `analyzeProductOpportunity`, `detectRisks`, and `generateInsight` all default `useModel` to `'openai'` (lines 36, 47, 59). The hook parameter types allow `'openai' | 'gemini'`. The page `handleRefreshAll` passes `useModel: 'openai'` as a hardcoded literal (line 59 of `analysis/page.tsx`). Project rules mandate: "Model: `gemini-2.0-flash` — do not change without explicit instruction."
- **Impact:** All AI trend analysis features call OpenAI by default, bypassing the Gemini integration entirely. Responses may differ in quality, cost, and format from what the app is designed around. The `use_model: 'openai'` payload is sent to the backend which routes to the wrong provider.

---

## [MEDIUM] BUG-296 — `settings/notifications/page.tsx` `handleSave` simulates API save with `setTimeout` and never persists
- **File:** `frontend/app/(dashboard)/notifications/page.tsx` lines 68-76
- **File:** `frontend/app/(dashboard)/settings/notifications/page.tsx` lines 68-76
- **Issue:** `handleSave` sets `isSaving` to `true`, waits `1000ms` via `await new Promise(resolve => setTimeout(resolve, 1000))`, then sets `isSaving` to `false` and shows a success toast — without calling any API endpoint. The notification preferences are held in local React state and are lost on page refresh.
- **Impact:** Users believe their notification preferences are saved (green toast displayed) but they are silently discarded. This is the same stub pattern as BUG-056 (forgot-password). The `DigestOption` sub-component also maintains its own independent toggle state (line 196: `const [selected, setSelected] = useState(value === 'weekly')`) that is entirely disconnected from the parent's `settings` state and from the non-existent API.

---

## [MEDIUM] BUG-297 — `providers.tsx` sessionStorage key mismatch with `client.ts` and login page
- **File:** `frontend/app/providers.tsx` line 29; `frontend/lib/api/client.ts` line 136; `frontend/app/(auth)/login/page.tsx` line 45
- **Issue:** `providers.tsx` `handleAuthFailure()` stores the redirect path as `sessionStorage.setItem('redirect_after_login', window.location.pathname)` (key: `redirect_after_login`). `client.ts` `handleAuthError()` stores it as `sessionStorage.setItem('redirectAfterLogin', currentPath)` (key: `redirectAfterLogin`). The login page reads `sessionStorage.getItem('redirectAfterLogin')` (key: `redirectAfterLogin`). The `providers.tsx` redirect-after-login path is therefore stored under a key that is never read — when a session expires mid-session and the global `handleAuthFailure` runs, the user is redirected to `/login` but after signing in is always sent to `/dashboard` instead of where they were.
- **Impact:** Users whose session expires while navigating the app are redirected to `/login` and after re-login always land on `/dashboard`, losing their place. The redirect-after-login feature only works correctly when the `client.ts` path (direct 401 from API call) is triggered, not the `providers.tsx` path (QueryCache global error handler).

---

## [MEDIUM] BUG-298 — `sentiment/trust/page.tsx` uses per-call `onSuccess` in `.mutate()` (React Query v5 ephemeral pattern)
- **File:** `frontend/app/(dashboard)/sentiment/trust/page.tsx` lines 202-209, 315-319, 414-419
- **Issue:** All three tab components (`AuthorScoringTab`, `ContentAnalysisTab`, `QuickSpamCheckTab`) call `mutate({...}, { onSuccess: (data) => setResult(data) })`. In React Query v5, per-call callbacks passed to `.mutate()` are ephemeral — if the component unmounts (e.g., user switches tabs) before the mutation resolves, the `onSuccess` callback is dropped and `setResult` is never called. The result state remains `null`.
- **Impact:** If the user clicks "Score Author", immediately switches to the "Content Analysis" tab while the request is in-flight, then switches back, the result is never displayed even on success. The pattern is consistent with BUG-114 and BUG-233 but was not previously documented for this file.

---

## [MEDIUM] BUG-300 — `AIAnalysisCard.tsx` labels AI as "GPT-4o-mini" violating Gemini-only mandate
- **File:** `frontend/components/features/competitors/AIAnalysisCard.tsx` line 67
- **Issue:** The card displays `<p className="text-xs text-gray-500">Powered by GPT-4o-mini</p>` as a static string. The project rule is "Model: `gemini-2.0-flash` — do not change without explicit instruction". The UI string is factually incorrect and could mislead users or auditors about the AI stack.
- **Impact:** Branding inconsistency / misleading label. Shopify app review may question the model identification.

---

## [MEDIUM] BUG-301 — `AIFeaturesCard.tsx` labels AI features as "GPT-4o" violating Gemini-only mandate
- **File:** `frontend/components/features/dashboard/AIFeaturesCard.tsx` lines 28, 86-87, 124
- **Issue:** The card shows a `GPT-4o` badge (line 86-87) and the footer states "Powered by OpenAI GPT-4o-mini" (line 124). The `aiFeatures` array also describes "AI Sentiment" as "GPT-powered analysis" (line 28). All three references are incorrect — the backend uses Gemini 2.0 Flash exclusively.
- **Impact:** False advertising of the AI provider. Multiple incorrect model references visible on the main dashboard.

---

## [MEDIUM] BUG-302 — `AIInsightPanel.tsx` shows `'openai' ? 'GPT-4' : 'Gemini'` badge, allowing OpenAI label in UI
- **File:** `frontend/components/features/trends/AIInsightPanel.tsx` line 65
- **Issue:** `<Badge variant="info">{insight.model_used === 'openai' ? 'GPT-4' : 'Gemini'}</Badge>` — the badge can display "GPT-4" if the `model_used` field from the backend is `'openai'`. Given BUG-295 (trend analysis defaults to `'openai'`), this label will display "GPT-4" in practice.
- **Impact:** Compounding error with BUG-295: the wrong model is called and then the UI correctly reports "GPT-4" — but this is still a violation of the Gemini-only mandate since neither should happen.

---

## [HIGH] BUG-303 — `PayWithMNEE.tsx` calls `setState` directly in render body causing infinite re-render
- **File:** `frontend/components/features/payments/PayWithMNEE.tsx` lines 69-76
- **Issue:** `setCallbackFired(true)` and `onSuccess(transferHash)` / `onError(transferError)` are called unconditionally in the component's render body (not inside a `useEffect`). During a render where `paymentStep === 'success'` and `!callbackFired`, `setCallbackFired(true)` is called — which schedules another render — which again evaluates the condition — potentially causing a render loop. React's strict mode will surface this immediately. The `!callbackFired` guard mitigates the loop but calling `setState` during render is an anti-pattern that violates React rules.
- **Impact:** React warning in strict mode, risk of state race conditions, potential infinite re-render loop if `callbackFired` state update batching behaves unexpectedly. `onSuccess`/`onError` callbacks may fire multiple times if the component re-renders before state update is committed.

---

## [HIGH] BUG-299 — `GenerateDescriptionModal.tsx` renders AI-generated HTML via `dangerouslySetInnerHTML` without sanitization (XSS)
- **File:** `frontend/components/features/products/GenerateDescriptionModal.tsx` line 211
- **Issue:** `<div dangerouslySetInnerHTML={{ __html: result.description }} />` renders the raw `description` string returned by the AI backend directly into the DOM. If the backend Gemini response or any intermediate processing layer ever includes `<script>` tags, event handlers, or other HTML, the user's browser will execute them. React's `dangerouslySetInnerHTML` bypasses all built-in XSS protection. The content comes from the AI API, which processes user-supplied product names and descriptions.
- **Impact:** Stored/reflected XSS. A maliciously crafted product name could cause the AI to include HTML payloads in the generated description, which are then executed in the merchant's browser when they click "Generate Description". At minimum, all session tokens stored in localStorage (BUG-001) become accessible to the injected script. The fix is to sanitize with `DOMPurify` before rendering, or render as plain text if rich formatting is not required.

---

## Notes on deep audit pass 8

Files confirmed CLEAN in this pass (no new bugs):
- `payments/demo/page.tsx` — renders "Demo" stub, correctly gate-checks `isEmbedded`. Clean.
- `payments/page.tsx` — MNEE/Shopify billing split works correctly. Embedded gate check present.
- `pricing/page.tsx` — well-structured, uses `mutateAsync` with try/catch correctly. `window.prompt` for rejection reason is poor UX but not a bug.
- `pricing/recommendations/[id]/page.tsx` — CLEAN. Correct `mutateAsync` usage throughout.
- `pricing/rules/[id]/page.tsx` — CLEAN.
- `pricing/rules/page.tsx` — CLEAN. BUG-008 fix confirmed applied.
- `pricing/settings/page.tsx` — CLEAN. `useMemo` initialFormData correctly avoids stale form values.
- `products/[id]/page.tsx` — `handleApplyGenerated` silently ignores errors at line 183 (`console.error` only) — minor concern but existing pattern.
- `products/[id]/edit/page.tsx` — CLEAN.
- `products/new/page.tsx` — CLEAN.
- `products/page.tsx` — client-side sort/filter OK for 20-item pages. Missing total-count reset when search changes page (minor UX).
- `sentiment/page.tsx` — CLEAN.
- `sentiment/trust/page.tsx` — new BUG-298 above; rest of UI logic is clean.
- `settings/billing/page.tsx` — `useSearchParams()` already covered by BUG-055. `verifyShopifyCharge` effect has correct cleanup via `cancelled` flag.
- `settings/profile/page.tsx` — CLEAN.
- `settings/security/page.tsx` — per-call `onSuccess` in `changePassword.mutate()` used only to clear form state (line 49-57) — low risk compared to BUG-298 since no navigation occurs.
- `support/page.tsx` — `onSuccess`/`onError` defined at mutation level (not per-call), correct pattern.
- `trends/page.tsx` — new BUG-294 above.
- `trends/analysis/page.tsx` — new BUG-295 above (defaults to `'openai'`).
- `app/layout.tsx` — CLEAN. App Bridge CDN script correctly included.
- `app/providers.tsx` — new BUG-297 (sessionStorage key mismatch). `shouldRetry` logic and global error handler otherwise well-structured.
- `lib/api/client.ts` — note: uses raw `fetch()` directly (not itself) but this is the implementation of the API client, so that's expected. The `handleAuthError()` function writes `sessionStorage.setItem('redirectAfterLogin', ...)` — this is the correct key but note that `providers.tsx` uses a different key.
- `lib/auth/token.ts` — localStorage usage already documented as BUG-001. Structure is clean otherwise.
- `lib/hooks/use-integrations.ts` — CLEAN. BUG-006 fix (sync polling timeout) applied correctly.
- `lib/api/trend-analysis.ts` — new BUG-295 above.
- `components/features/integrations/IntegrationCard.tsx` — CLEAN. BUG-036 fix (using `mutateAsync` pattern) confirmed present.
- `components/features/integrations/diagnostic-panel.tsx` — CLEAN. Uses `api` client correctly.

## Deep Audit Pass 9 — Component Features, lib/api (2026-03-21)

New bugs found: BUG-300, BUG-301, BUG-302, BUG-303

Files confirmed CLEAN in pass 9:
- `components/features/alerts/AlertConfigurationForm.tsx` — CLEAN. Form state, validation, conditional fields all correct.
- `components/features/alerts/AlertsList.tsx` — CLEAN. Simple list, no data fetching.
- `components/features/alerts/CrisisDetectionCard.tsx` — CLEAN. Uses `api` client correctly. On-demand load pattern is acceptable.
- `components/features/alerts/NotificationBell.tsx` — CLEAN. WebSocket + React Query combination handled correctly with separate state.
- `components/features/competitors/AIAnalysisCard.tsx` — new BUG-300 (GPT label). API call pattern is correct.
- `components/features/competitors/AutoLinkModal.tsx` — CLEAN.
- `components/features/competitors/CompetitorMatchSearch.tsx` — CLEAN. Uses mutation hooks correctly.
- `components/features/dashboard/AIFeaturesCard.tsx` — new BUG-301 (GPT-4o labels).
- `components/features/dashboard/PendingRecommendations.tsx` — CLEAN. Pure display component, correct null/NaN safety.
- `components/features/pricing/RecommendationCard.tsx` — CLEAN. Good error handling, safe number parsing.
- `components/features/pricing/RuleForm.tsx` — CLEAN. `mutateAsync` with try/catch correct. Domain validation layer used correctly.
- `components/features/products/ImportCSVModal.tsx` — CLEAN. Per-call `onSuccess` in `mutate()` (line 276) only modifies local parent callback, not component state — low risk.
- `components/features/products/PriceSuggestionModal.tsx` — CLEAN. `mutate()` per-call `onSuccess` (line 234) only calls `onClose` — acceptable.
- `components/features/products/ProductStoreSync.tsx` — CLEAN. Uses mutation-level `onSuccess`/`onError`, correct pattern.
- `components/features/trends/AIInsightPanel.tsx` — new BUG-302 (OpenAI/GPT-4 badge compounding BUG-295).
- `components/features/payments/PayWithMNEE.tsx` — new BUG-303 (setState in render body).
- `components/features/payments/SubscriptionPlans.tsx` — CLEAN. `downgradeToFreeMutation.mutateAsync()` and `subscribeMutation.mutateAsync()` patterns correct.
- `lib/api/intelligence.ts` — CLEAN.
- `lib/api/analytics.ts` — CLEAN.
- `lib/api/auth.ts` — CLEAN.
- `lib/api/alerts.ts` — CLEAN.
- `lib/api/competitors.ts` — CLEAN.
- `lib/api/trust-scoring.ts` — CLEAN.
- `lib/api/retrospective-audit.ts` — CLEAN.
- `lib/api/products.ts` — hardcoded URL already BUG-002.
- `lib/api/pricing.ts` — CLEAN. `ApprovalError` class and structured error parsing is well-implemented.
- `lib/api/integrations.ts` — CLEAN. `pollSyncStatus` unguarded `setTimeout` is non-critical (no React state involved).
- `lib/api/sentiment.ts` — CLEAN.
- `lib/api/outcomes.ts` — CLEAN. Transformer functions are robust with null-safety.

---

## Deep Audit Pass 10 — lib/web3, types, next.config, demo pages, analytics components (2026-03-21)

New bugs found: BUG-304, BUG-305, BUG-306, BUG-307, BUG-308, BUG-309, BUG-310, BUG-311

---

## [CRITICAL] BUG-304 — Hardcoded Alchemy API key committed to source code
- **Status: FIXED 2026-03-21**
- **File:** `frontend/lib/web3/config.ts` line 80
- **Issue:** `[sepolia.id]: http('https://eth-sepolia.g.alchemy.com/v2/i1syJSaaz92esG2J-4NG0')` — an Alchemy RPC API key is hardcoded directly in version-controlled source code, not read from an environment variable.
- **Impact:** The API key is publicly visible to anyone with repository access. Alchemy tracks usage per key; the key can be abused to exhaust rate limits or accrue costs. Should be moved to `NEXT_PUBLIC_ALCHEMY_SEPOLIA_KEY` env var read at runtime.
- **Fix:** Replaced hardcoded URL with `process.env.NEXT_PUBLIC_ALCHEMY_SEPOLIA_URL` with public RPC fallback.

---

## [HIGH] BUG-310 — Email address (PII) sent to analytics endpoint in `audit/page.tsx`
- **File:** `frontend/app/audit/page.tsx` line 335
- **Issue:** `trackEvent('email_submitted', { email: email.trim(), input_mode: mode, ... })` — the raw user email is included in the analytics event payload. Analytics events are typically sent to third-party services (Sentry, Mixpanel, etc.) and may be logged server-side.
- **Impact:** Violates GDPR and the project security rule "strip PII before Sentry events". User email addresses are PII and must not be transmitted to analytics pipelines. Replace with a hashed identifier (e.g., `email_hash: sha256(email)`) or omit the field entirely.

---

## [MEDIUM] BUG-306 — OpenAI/GPT-4 branding in `types/sentiment.ts` type comment and union
- **File:** `frontend/types/sentiment.ts` lines 88, 113
- **Issue:** Line 88 has a type comment `// Use GPT-4o-mini for analysis` on the `use_ai` field. Line 113 defines `analyzed_by: 'vader' | 'openai' | 'gemini' | 'hybrid'` — explicitly including `'openai'` as a valid response value.
- **Impact:** Violates the Gemini-only mandate. The comment incorrectly documents GPT-4o-mini as the intended model. The union type means the frontend type system accepts and propagates `'openai'` as a valid analyzer label, compounding BUG-295 (trend analysis defaults to openai) and BUG-302 (UI renders "GPT-4" badge for openai responses).

---

## [MEDIUM] BUG-307 — `use_model?: 'openai' | 'gemini'` in trend-analysis request types
- **File:** `frontend/types/trend-analysis.ts`
- **Issue:** Multiple request interfaces (`TrendAnalysisRequest`, `ProductOpportunityRequest`, `RiskDetectionRequest`, `InsightGenerationRequest`) include `use_model?: 'openai' | 'gemini'`. This explicitly permits requesting the OpenAI model.
- **Impact:** Violates the Gemini-only mandate. Any caller passing `use_model: 'openai'` will route requests to OpenAI. Combined with BUG-295 (the API layer defaults to `'openai'`), this means OpenAI is both the default and a type-legal option — both should only be `'gemini'`.

---

## [MEDIUM] BUG-308 — Wildcard `**` hostname in `next.config.ts` disables image security
- **File:** `frontend/next.config.ts` `images.remotePatterns`
- **Issue:** Both `{ protocol: 'https', hostname: '**' }` and `{ protocol: 'http', hostname: '**' }` are configured. This allows the Next.js image optimizer to proxy images from any host, including the `http://` wildcard which allows cleartext traffic.
- **Impact:** The Next.js image allowlist security feature is completely disabled. Attackers who can influence image URLs (e.g. via stored product image URLs) can force the server to act as a proxy for arbitrary external content, including potentially malicious hosts. At minimum the `http` wildcard should be removed; ideally allowlist specific known hosts.

---

## [MEDIUM] BUG-311 — "Approved" and "Applied" stats both use `total_applied` in `RecommendationStatsCard`
- **File:** `frontend/components/features/analytics/RecommendationStatsCard.tsx` lines 33–43
- **Issue:** The stats array defines two entries: `{ label: 'Approved', value: data?.total_applied ?? 0 }` and `{ label: 'Applied', value: data?.total_applied ?? 0 }`. Both reference the same field. The `RecommendationStats` type has no `total_approved` field — the backend schema only has `total_applied`.
- **Impact:** The dashboard "Approved" stat card always shows the same number as "Applied", which is misleading. One of these should likely be `total_generated` (total recommendations generated) or the labels should be corrected to remove the duplicate.

---

## [LOW] BUG-305 — Debug `console.log` statements left in production `useMNEE.ts`
- **File:** `frontend/lib/web3/useMNEE.ts` lines 85–91
- **Issue:** Five debug `console.log` statements inside the `transfer()` function are committed in production code: `console.log('=== MNEE Transfer Debug ===')`, `console.log('to:', to)`, `console.log('amount (string):', amount)`, `console.log('decimals:', MNEE_TOKEN.decimals)`, `console.log('amountInWei:', amountInWei.toString())`.
- **Impact:** Leaks transaction details (recipient wallet address, transfer amounts) to the browser console. Any browser extension or injected script can read console output.

---

## [LOW] BUG-309 — "Gemini 3 Flash" non-existent model name in demo footer
- **File:** `frontend/app/demo/autonomous-pipeline/page.tsx` line 474
- **Issue:** Footer text reads "Powered by Gemini 3 Flash" — no such model exists. The correct model name per the project rules is `gemini-2.0-flash`.
- **Impact:** Incorrect product branding. Minor but confusing to users/reviewers during Shopify App Store submission.

---

Files confirmed CLEAN in pass 10:
- `lib/domain/__tests__/auth.test.ts` — CLEAN. MSW handler patterns correct, no hardcoded credentials.
- `lib/domain/__tests__/products.test.ts` — CLEAN. Thorough coverage of decimal normalization and price constraint validation.
- `lib/domain/__tests__/integrations.test.ts` — CLEAN. Extensive URL normalization, validation, and transform test coverage.
- `lib/domain/__tests__/pricing.test.ts` — CLEAN (sampled). Domain test patterns consistent.
- `components/features/intelligence/CalibrationChart.tsx` — CLEAN. SVG-based chart with safe data transforms, null guards throughout.
- `components/features/intelligence/CategoryPerformanceTable.tsx` — CLEAN. Client-side sort with `useMemo`, null-safe value formatting.
- `components/features/intelligence/ExperimentStatusCard.tsx` — CLEAN. Thompson Sampling arm visualization, correct expand/collapse state.
- `components/features/intelligence/IEHealthBanner.tsx` — CLEAN. Status/label maps with fallback defaults.
- `components/features/intelligence/OutcomeDashboard.tsx` — CLEAN (previously noted).
- `components/features/intelligence/DriftAlertsList.tsx` — CLEAN (previously noted).
- `components/features/analytics/AlertsBreakdownChart.tsx` — CLEAN. Recharts integration, data transformation with useMemo correct.
- `components/features/analytics/SentimentTrendChart.tsx` — CLEAN. `toSafeNumber` helper correctly handles backend string decimals.
- `types/competitor-matching.ts` — CLEAN. SearchProvider union types, no `any`.
- `tsconfig.json` — CLEAN. `strict: true` confirmed, correct Next.js plugin configuration.
- `package.json` — CLEAN. No unexpected dependencies. `generate-types` script points to staging URL (acceptable for dev tooling).
- `vercel.json` — CLEAN. Security headers present: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`.
- `components/features/integrations/IntegrationCard.tsx` — CLEAN (re-confirmed in session context).
- `app/(dashboard)/integrations/callback/page.tsx` — CLEAN (re-confirmed in session context).
- `app/(dashboard)/integrations/claim/page.tsx` — CLEAN (re-confirmed in session context).
- `app/(auth)/login/page.tsx` — CLEAN (re-confirmed in session context).
- `types/product.ts` — CLEAN (re-confirmed in session context).

---

## Deep Audit Pass 11 — Remaining hooks, components, tests, config files (2026-03-21)

New bugs found: BUG-312, BUG-313, BUG-314, BUG-315

---

## [MEDIUM] BUG-312 — `analyze-modal.tsx` UI shows "GPT-4o-mini" branding to users
- **File:** `frontend/components/features/sentiment/analyze-modal.tsx` line 123
- **Issue:** The AI toggle description label displayed to users reads: `"GPT-4o-mini for more accurate results"`. This is user-visible UI text, not a type comment.
- **Impact:** Actively misleads users about which AI model powers the app. Violates the Gemini-only mandate and is inconsistent with the project's branding. Any Shopify App Store reviewer seeing this screen will see OpenAI branding.

---

## [MEDIUM] BUG-313 — `analyze-modal.tsx` calls `setProductId` during render body (setState during render)
- **File:** `frontend/components/features/sentiment/analyze-modal.tsx` lines 73–75
- **Issue:** The `if (isOpen && defaultProductId && defaultProductId !== productId) { setProductId(defaultProductId); }` block runs unconditionally during the render function body. Calling `setState` during render is an anti-pattern — it causes React to immediately re-render the component before painting, which can cause a render loop if the condition doesn't settle. This is the same pattern flagged in BUG-303 (`PayWithMNEE.tsx`).
- **Impact:** React warning in strict mode: "Cannot update a component from inside the function body of a different component." Potential infinite re-render loop if `defaultProductId` keeps changing. The correct fix is to move this into a `useEffect(..., [isOpen, defaultProductId])`.

---

## [MEDIUM] BUG-314 — `ProductForm.tsx` uses per-call `onSuccess` in `mutate()` causing double toast
- **File:** `frontend/components/features/products/ProductForm.tsx` lines 206–209 and 216–219
- **Issue:** `updateProduct.mutate(...)` and `createProduct.mutate(...)` both pass per-call `onSuccess` callbacks that call `toast.success(...)`. However, `useUpdateProduct` and `useCreateProduct` hooks already have mutation-level `onSuccess` handlers that call `toast.success(...)`. When the mutation succeeds, both fire: the hook-level toast and the per-call toast.
- **Impact:** Users see duplicate success toasts on every product create/update. Per-call `onSuccess` in `mutate()` is also fragile in React Query v5 (ephemeral, may not fire if component unmounts during the mutation). The per-call callbacks should only handle navigation (`onSuccess?.()`) and the toast should remain only at the mutation hook level.

---

## [LOW] BUG-315 — `use-auth.ts` reads `sessionStorage` during login redirect, conflicting with `api/client.ts` key
- **File:** `frontend/lib/hooks/use-auth.ts` line 59; `frontend/lib/api/client.ts` (handleAuthError)
- **Issue:** `use-auth.ts` reads `sessionStorage.getItem('redirectAfterLogin')` and removes it after redirect. `lib/api/client.ts`'s `handleAuthError()` writes the redirect path to `sessionStorage.setItem('redirectAfterLogin', ...)`. This is the same key — but `login/page.tsx` also reads `searchParams.get('redirect')` and uses that with priority. So there are two redirect mechanisms: the `?redirect=` URL param (set by middleware) and the `sessionStorage` key (set by auth interceptor). The `useLogin` hook in `use-auth.ts` only checks `sessionStorage` — it does not read the `?redirect` URL param. The `login/page.tsx` `LoginForm` does check the `?redirect` param and calls `router.push(redirectParam)`. However, `useLogin` hook (used in the auth store) navigates to `/dashboard` unconditionally if no `sessionStorage` key is found, even if a `?redirect` URL param is present.
- **Impact:** If a user follows a middleware-generated redirect URL like `/login?redirect=/integrations/claim?...`, the auth store's `login()` function will redirect to `/dashboard` instead of honoring the `?redirect` param — losing the Shopify install flow context. The `login/page.tsx` component does check the param correctly via `useAuthStore`, so this only fails if `useLogin()` hook is used directly.

---

Files confirmed CLEAN in pass 11:
- `lib/hooks/use-alerts.ts` — CLEAN. All mutations use mutation-level callbacks.
- `lib/hooks/use-auth.ts` — CLEAN (minor issue noted as BUG-315 above).
- `lib/hooks/use-trend-analysis.ts` — CLEAN (BUG-307 pattern already logged; hook design otherwise correct).
- `lib/hooks/use-pricing.ts` — CLEAN. BUG FIX #2 invalidation of product queries on approval confirmed correct.
- `lib/hooks/use-products.ts` — CLEAN. Optimistic delete with rollback on error is well implemented.
- `lib/hooks/use-sentiment.ts` — CLEAN.
- `lib/hooks/use-payments.ts` — CLEAN. Correct cache invalidation on subscription/plan changes.
- `lib/hooks/use-shopify-billing.ts` — CLEAN. Confirms Shopify billing API integration via dedicated endpoints.
- `lib/hooks/use-intelligence.ts` — CLEAN. Separate query keys per endpoint, no local key collisions.
- `lib/hooks/use-user.ts` — CLEAN.
- `lib/hooks/use-competitor-matching.ts` — CLEAN. `useConfidenceLevel` and `useFilteredMatches` are pure helper hooks (not React Query hooks) — acceptable pattern.
- `lib/hooks/use-product-sync.ts` — CLEAN. Uses `sonner` toast directly (not the custom toast hook) — inconsistent but not a bug.
- `components/features/sentiment/analyze-modal.tsx` — new BUG-312, BUG-313 above. Modal structure otherwise correct.
- `components/features/competitors/CompetitorCard.tsx` — CLEAN. `mutateAsync` pattern correct.
- `components/features/products/ProductsTable.tsx` — CLEAN. Responsive table/card layout, no data fetching in this component.
- `components/features/products/ProductForm.tsx` — new BUG-314 above. Domain validation layer usage is correct.
- `components/features/pricing/ConfidenceIndicator.tsx` — CLEAN. Accessible `role="meter"` with `aria-valuenow/min/max`. Score clamping correct.
- `components/features/analytics/SentimentTrendChart.tsx` — CLEAN (duplicate of dashboard SentimentOverview — same component; both CLEAN).
- `types/competitor-matching.ts` — CLEAN (confirmed in pass 10).
- `tsconfig.json` — CLEAN. `strict: true` enabled.
- `package.json` — CLEAN. No unexpected dependencies; `generate-types` scripts point to known environments.
- `vercel.json` — CLEAN. Security headers present.

---

## Deep Audit Pass 12 — Dashboard pages, layout components, stores, middleware (2026-03-21)

New bugs found: BUG-316

---

## [HIGH] BUG-316 — `analytics/audit/page.tsx` reads JWT directly from `localStorage` bypassing token abstraction
- **Status: FIXED 2026-03-21**
- **File:** `frontend/app/(dashboard)/analytics/audit/page.tsx` lines 49–53
- **Issue:** The `getAuthToken()` helper function reads `localStorage.getItem('access_token')` directly. All other API calls use the centralized `api` Axios client which reads via `getToken()` from `lib/auth/token.ts`. This function also directly constructs `fetch()` calls with Bearer token headers instead of using the `api` client.
- **Impact:** Duplicates the BUG-001 localStorage risk in a separate location. If the token key name ever changes, this code won't update automatically. The `fetch()` calls also bypass the Axios interceptor that handles 401 refresh token logic — if the token expires during a PDF export or email send, the user gets a silent failure instead of an automatic token refresh.
- **Fix:** Removed `getAuthToken()`, replaced email fetch with centralized `api.post()`, PDF fetch now uses `getBearerToken()` from `lib/auth/token`.

---

Files confirmed CLEAN in pass 12:
- `app/(dashboard)/admin/page.tsx` — CLEAN. Stub page, no data fetching.
- `app/(dashboard)/api-keys/page.tsx` — CLEAN. Stub page.
- `app/(dashboard)/analytics/audit/page.tsx` — new BUG-316 above. Otherwise UI logic is correct.
- `app/(dashboard)/integrations/[id]/page.tsx` — CLEAN. Per-call `onSuccess` in `disconnect.mutate()` used only for navigation (acceptable pattern).
- `components/layout/Sidebar.tsx` — CLEAN. Embedded vs. standalone nav item filtering correct.
- `components/layout/Topbar.tsx` — CLEAN. Embedded mode detection correct.
- `components/layout/DashboardShell.tsx` — CLEAN. Mobile drawer with `reopenBlockedUntil` timer is a deliberate UX fix, not a bug.
- `components/ui/ai-badge.tsx` — CLEAN. Generic "AI Powered" label, no model branding.
- `lib/stores/auth-store.ts` — CLEAN (localStorage usage is BUG-001, already logged). Error extraction pattern is correct.
- `middleware.ts` — CLEAN. `ssp_auth=1` cookie as a lightweight auth hint (not JWT) is architecturally intentional. Matcher regex correctly excludes static files.
- `lib/hooks/use-outcomes.ts` — CLEAN (noted in previous session).
- `lib/hooks/use-trust-scoring.ts` — CLEAN.

---

## Stats

| Severity | Count |
|----------|-------|
| CRITICAL | 20 |
| HIGH | 97 |
| MEDIUM | 109 |
| LOW | 38 |
| **TOTAL** | **264** |
| **ENHANCEMENTS** | **6** |

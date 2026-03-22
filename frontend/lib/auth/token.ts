// frontend/lib/auth/token.ts

/**
 * Token Management Utilities
 *
 * FIXED (2026-03-21): BUG-001 — Removed localStorage JWT storage.
 * JWTs are now stored in httpOnly cookies set by the backend.
 * JavaScript cannot read the actual tokens (that's the point — XSS-safe).
 *
 * This module manages:
 *  - The `ssp_auth` hint cookie (non-httpOnly) so Next.js middleware can
 *    detect auth state server-side and prevent flash of unauthorized content.
 *  - An in-memory bearer token for the Shopify embedded flow, where App
 *    Bridge session tokens must be sent as Authorization headers.
 *
 * Regular browser auth: httpOnly cookies (credentials: 'include').
 * Shopify embedded auth: in-memory bearer token (Authorization header).
 */

// ─────────────────────────────────────────────────────────────────────────────
// In-memory token for Shopify embedded flow
// ─────────────────────────────────────────────────────────────────────────────

let _bearerToken: string | null = null;

/**
 * Returns the in-memory bearer token if one has been set (Shopify embedded),
 * or null if the regular httpOnly cookie flow is in use.
 */
export function getBearerToken(): string | null {
  return _bearerToken;
}

// ─────────────────────────────────────────────────────────────────────────────
// Hint cookie helpers
// ─────────────────────────────────────────────────────────────────────────────

function hasHintCookie(): boolean {
  if (typeof document === 'undefined') return false;
  return document.cookie.split(';').some(c => c.trim().startsWith('ssp_auth=1'));
}

function setHintCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = 'ssp_auth=1; path=/; max-age=604800; SameSite=Lax; Secure';
}

function clearHintCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = 'ssp_auth=; path=/; max-age=0; SameSite=Lax; Secure';
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API — signatures preserved for callers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Check whether the user has an active auth session.
 * Returns the in-memory bearer token (Shopify embedded) or a truthy hint
 * string when httpOnly cookies are in use. Returns null if not authenticated.
 */
export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return _bearerToken ?? (hasHintCookie() ? 'httponly' : null);
}

/**
 * Store a token. For regular login the actual JWT lives in an httpOnly cookie
 * set by the backend — this just sets the hint cookie. For Shopify embedded
 * flow, the App Bridge session token is held in memory so the API client can
 * send it as a Bearer header.
 */
export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  _bearerToken = token === 'httponly' ? null : token;
  setHintCookie();
}

/** Clear the auth hint cookie and in-memory token. */
export function removeToken(): void {
  if (typeof window === 'undefined') return;
  _bearerToken = null;
  clearHintCookie();
}

/**
 * Refresh tokens are now stored in httpOnly cookies by the backend.
 * These functions are kept for API compatibility but are no-ops.
 */
export function getRefreshToken(): string | null {
  return hasHintCookie() ? 'httponly' : null;
}

export function setRefreshToken(_token: string): void {
  // No-op: backend sets the httpOnly cookie directly
}

export function removeRefreshToken(): void {
  // No-op: cleared by backend /auth/logout or cookie expiry
}

// ─────────────────────────────────────────────────────────────────────────────
// Combined Operations
// ─────────────────────────────────────────────────────────────────────────────

/** Store tokens after login. Sets hint cookie and optional in-memory bearer. */
export function setTokens(accessToken: string, _refreshToken?: string): void {
  setToken(accessToken);
}

/** Clear all auth state. */
export function removeAllTokens(): void {
  _bearerToken = null;
  clearHintCookie();
}

/** Check if user is authenticated (in-memory token or hint cookie present). */
export function isAuthenticated(): boolean {
  return _bearerToken !== null || hasHintCookie();
}

/** Check if we can attempt a refresh (hint cookie present). */
export function canRefresh(): boolean {
  return hasHintCookie();
}

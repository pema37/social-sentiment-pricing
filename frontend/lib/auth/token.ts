// frontend/lib/auth/token.ts

/**
 * Token Management Utilities
 * Handles storing/retrieving JWT tokens from browser localStorage
 * 
 * PATCHED (2025-01-07): Added refresh token support to prevent session timeouts.
 * PATCHED (2026-02-23): Added ssp_auth cookie flag so middleware.ts can detect
 *   auth state server-side. The cookie is just a boolean hint (no sensitive data).
 *   Actual JWT validation still happens client-side in the Zustand auth store.
 */

const ACCESS_TOKEN_KEY = 'ssp_access_token';
const REFRESH_TOKEN_KEY = 'ssp_refresh_token';

// ─────────────────────────────────────────────────────────────────────────────
// Access Token
// ─────────────────────────────────────────────────────────────────────────────

/** Get the access token from localStorage */
export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/** Save the access token to localStorage */
export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  document.cookie = 'ssp_auth=1; path=/; max-age=604800; SameSite=Lax';
}

/** Remove the access token from localStorage */
export function removeToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  document.cookie = 'ssp_auth=; path=/; max-age=0';
}

// ─────────────────────────────────────────────────────────────────────────────
// Refresh Token
// ─────────────────────────────────────────────────────────────────────────────

/** Get the refresh token from localStorage */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** Save the refresh token to localStorage */
export function setRefreshToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

/** Remove the refresh token from localStorage */
export function removeRefreshToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// ─────────────────────────────────────────────────────────────────────────────
// Combined Operations
// ─────────────────────────────────────────────────────────────────────────────

/** Save both tokens at once (after login) */
export function setTokens(accessToken: string, refreshToken?: string): void {
  setToken(accessToken);
  if (refreshToken) {
    setRefreshToken(refreshToken);
  }
}

/** Remove all tokens (logout) */
export function removeAllTokens(): void {
  removeToken();
  removeRefreshToken();
}

/** Check if user is authenticated (has an access token) */
export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Check if we can attempt a refresh (has a refresh token) */
export function canRefresh(): boolean {
  return !!getRefreshToken();
}



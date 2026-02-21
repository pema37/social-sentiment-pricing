// frontend/lib/context/shopify-embedded.tsx

/**
 * Shopify Embedded Context
 *
 * Detects when ActualPrice is running inside Shopify Admin iframe
 * and provides App Bridge session token auth to all dashboard components.
 *
 * Usage in any component:
 *   const { isEmbedded, shopDomain } = useShopifyEmbedded();
 *
 * What this solves:
 * - Detects ?shop=xxx&host=xxx&embedded=1 URL params
 * - Acquires session tokens from Shopify App Bridge (window.shopify.idToken())
 * - Exposes isEmbedded flag so billing, payments, auth pages can conditionally render
 * - Keeps standalone (non-Shopify) auth flow untouched
 */

'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import { useSearchParams } from 'next/navigation';
import { setTokens } from '@/lib/auth/token';
import { useAuthStore } from '@/lib/stores/auth-store';

// ─── Types ───────────────────────────────────────────────────────────

interface ShopifyEmbeddedState {
  /** True when running inside Shopify Admin iframe */
  isEmbedded: boolean;
  /** The merchant's myshopify.com domain (e.g., "cool-store.myshopify.com") */
  shopDomain: string | null;
  /** The base64-encoded host param Shopify passes for App Bridge */
  hostParam: string | null;
  /** Whether session token auth has completed */
  isSessionReady: boolean;
  /** Any error during session token acquisition */
  sessionError: string | null;
  /** Force refresh the session token (e.g., before an important API call) */
  refreshSessionToken: () => Promise<string | null>;
}

const defaultState: ShopifyEmbeddedState = {
  isEmbedded: false,
  shopDomain: null,
  hostParam: null,
  isSessionReady: false,
  sessionError: null,
  refreshSessionToken: async () => null,
};

// ─── Context ─────────────────────────────────────────────────────────

const ShopifyEmbeddedContext = createContext<ShopifyEmbeddedState>(defaultState);

export function useShopifyEmbedded(): ShopifyEmbeddedState {
  return useContext(ShopifyEmbeddedContext);
}

// ─── Provider ────────────────────────────────────────────────────────

interface Props {
  children: ReactNode;
}

export function ShopifyEmbeddedProvider({ children }: Props) {
  const searchParams = useSearchParams();
  const { checkAuth } = useAuthStore();

  // Detect embedded context from URL params
  const shopParam = searchParams.get('shop');
  const hostParam = searchParams.get('host');
  const embeddedParam = searchParams.get('embedded');
  const isEmbedded = embeddedParam === '1' && !!shopParam && !!hostParam;

  const [isSessionReady, setIsSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const initAttempted = useRef(false);

  // ── Get session token from App Bridge ──────────────────────────────

  const acquireSessionToken = useCallback(async (): Promise<string | null> => {
    // Not in embedded context — nothing to do
    if (!isEmbedded) return null;

    try {
      const appBridge = await waitForAppBridge(3000) as { idToken?: () => Promise<string> } | null;

      if (!appBridge) {
        throw new Error('App Bridge not available after 3s');
      }

      if (typeof appBridge.idToken !== 'function') {
        throw new Error('App Bridge missing idToken method');
      }

      // Get fresh session token
      const token = await appBridge.idToken();

      if (!token) {
        throw new Error('App Bridge returned empty session token');
      }

      return token;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Session token acquisition failed';
      console.error('[ShopifyEmbedded] Token error:', message);
      setSessionError(message);
      return null;
    }
  }, [isEmbedded]);

  // ── Initialize embedded auth on mount ──────────────────────────────

  useEffect(() => {
    // Only run once, only in embedded context
    if (!isEmbedded || initAttempted.current) return;
    initAttempted.current = true;

    async function initEmbeddedAuth() {
      const token = await acquireSessionToken();

      if (token) {
        // Store the session token so the API client sends it as Bearer token.
        // We pass it as both access and refresh since App Bridge handles refresh.
        setTokens(token, token);

        // Now verify the token with our backend (calls GET /auth/me)
        await checkAuth();
        setIsSessionReady(true);
      } else {
        setSessionError('Could not acquire Shopify session token');
        setIsSessionReady(true); // Mark ready so UI doesn't hang
      }
    }

    initEmbeddedAuth();
  }, [isEmbedded, acquireSessionToken, checkAuth]);

  // ── If not embedded, immediately mark ready ────────────────────────

  useEffect(() => {
    if (!isEmbedded) {
      setIsSessionReady(true);
    }
  }, [isEmbedded]);

  // ── Expose refresh function for child components ───────────────────

  const refreshSessionToken = useCallback(async (): Promise<string | null> => {
    const token = await acquireSessionToken();
    if (token) {
      setTokens(token, token);
    }
    return token;
  }, [acquireSessionToken]);

  // ── Context value ──────────────────────────────────────────────────

  const value: ShopifyEmbeddedState = {
    isEmbedded,
    shopDomain: shopParam,
    hostParam,
    isSessionReady,
    sessionError,
    refreshSessionToken,
  };

  return (
    <ShopifyEmbeddedContext.Provider value={value}>
      {children}
    </ShopifyEmbeddedContext.Provider>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────

/**
 * Polls for window.shopify (App Bridge global) with timeout.
 * App Bridge CDN script loads async, so it may not be available immediately.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function waitForAppBridge(timeoutMs: number): Promise<any> {
  return new Promise((resolve) => {
    if (typeof window !== 'undefined' && window.shopify) {
      resolve(window.shopify);
      return;
    }

    const interval = 50;
    let elapsed = 0;

    const timer = setInterval(() => {
      elapsed += interval;

      if (typeof window !== 'undefined' && window.shopify) {
        clearInterval(timer);
        resolve(window.shopify);
        return;
      }

      if (elapsed >= timeoutMs) {
        clearInterval(timer);
        resolve(null);
      }
    }, interval);
  });
}


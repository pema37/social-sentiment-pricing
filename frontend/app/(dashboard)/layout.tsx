// frontend/app/(dashboard)/layout.tsx

/**
 * Dashboard Layout
 * Wraps all dashboard pages with auth protection + shell.
 *
 * Two auth paths:
 * 1. Embedded (Shopify Admin iframe) → App Bridge session token, no login redirect
 * 2. Standalone (direct browser)     → JWT from httpOnly cookie, redirect to /login if missing
 *
 * Updated Feb 21, 2026 — Shopify App Store compliance
 */

'use client';

import { Suspense, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';
import {
  ShopifyEmbeddedProvider,
  useShopifyEmbedded,
} from '@/lib/context/shopify-embedded';
import { DashboardShell } from '@/components/layout';
import { ErrorBoundary } from '@/components/ui';

// ─── Outer wrapper: provides Shopify context + Suspense boundary ─────

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <ShopifyEmbeddedProvider>
        <DashboardAuthGate>{children}</DashboardAuthGate>
      </ShopifyEmbeddedProvider>
    </Suspense>
  );
}

// ─── Inner gate: handles auth for both embedded & standalone ─────────

function DashboardAuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const { isEmbedded, isSessionReady, sessionError } = useShopifyEmbedded();

  // Standalone path: check existing JWT on mount
  // (Embedded path: ShopifyEmbeddedProvider calls checkAuth after token acquisition)
  useEffect(() => {
    if (!isEmbedded) {
      checkAuth();
    }
  }, [isEmbedded, checkAuth]);

  // Standalone path: redirect to login if not authenticated
  useEffect(() => {
    if (!isEmbedded && !isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isEmbedded, isLoading, isAuthenticated, router]);

  // ── Loading states ──────────────────────────────────────────────────

  // Embedded: wait for App Bridge session token
  if (isEmbedded && !isSessionReady) {
    return <LoadingScreen message="Connecting to Shopify..." />;
  }

  // Embedded: session token failed — show error, don't redirect to login
  if (isEmbedded && isSessionReady && !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Connection Error
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            {sessionError || 'Unable to authenticate with Shopify. Please try reloading the app from your Shopify Admin.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Reload App
          </button>
        </div>
      </div>
    );
  }

  // Standalone: still checking auth
  if (!isEmbedded && isLoading) {
    return <LoadingScreen />;
  }

  // Standalone: not authenticated (will redirect via useEffect above)
  if (!isEmbedded && !isAuthenticated) {
    return null;
  }

  // ── Authenticated — render dashboard ────────────────────────────────

  return (
    <DashboardShell>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </DashboardShell>
  );
}

// ─── Shared loading component ────────────────────────────────────────

function LoadingScreen({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-sm text-gray-500">{message}</p>
      </div>
    </div>
  );
}



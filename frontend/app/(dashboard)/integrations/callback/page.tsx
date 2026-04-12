export const dynamic = 'force-dynamic';
'use client';

/**
 * OAuth Callback Handler
 *
 * Handles the redirect from Shopify after user authorizes the app.
 * Captures OAuth params (code, state, shop) and sends to backend
 * to exchange for access token.
 *
 * URL: /integrations/callback?code=xxx&state=xxx&shop=xxx
 */

import { Suspense, useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';

// ==================== Types ====================

interface CallbackState {
  status: 'loading' | 'success' | 'error';
  message: string;
  platform?: string;
}

interface OAuthCallbackResponse {
  integration_id: string;
  platform: string;
  store_url: string;
  message: string;
}

// ==================== Component ====================

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center"><LoadingSpinner /></div>}>
      <OAuthCallbackContent />
    </Suspense>
  );
}

function OAuthCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [state, setState] = useState<CallbackState>({
    status: 'loading',
    message: 'Completing connection...',
  });

  /**
   * Process the OAuth callback
   * Extracts params and sends to backend for token exchange,
   * then triggers an initial full product sync.
   */
  const processCallback = useCallback(async () => {
    const code = searchParams.get('code');
    const oauthState = searchParams.get('state');
    const shop = searchParams.get('shop');
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');

    // 1. Handle OAuth error from provider FIRST
    if (error) {
      setState({
        status: 'error',
        message: errorDescription || `Authorization failed: ${error}`,
      });
      return;
    }

    // 2. Validate required params
    if (!code || !oauthState) {
      setState({
        status: 'error',
        message: 'Missing authorization parameters. Please try again.',
      });
      return;
    }

    try {
      setState({ status: 'loading', message: 'Exchanging authorization code...' });

      // 3. Exchange code for access token
      const response = await api.post<OAuthCallbackResponse>(
        '/api/v1/integrations/oauth/callback',
        { code, state: oauthState, shop }
      );

      // 4. Trigger initial full product sync (non-fatal if it fails)
      setState({ status: 'loading', message: 'Syncing products from your store...' });
      try {
        await api.post(`/api/v1/integrations/${response.integration_id}/sync`, {
          sync_type: 'full',
        });
      } catch (syncErr) {
        // Non-fatal: integration is connected, sync can be retried manually
        console.error('Initial sync failed:', syncErr);
      }

      // 5. Show success and redirect
      setState({
        status: 'success',
        message: `Successfully connected ${response.store_url}!`,
        platform: response.platform,
      });

      setTimeout(() => {
        router.push(
          `/integrations?connected=true&platform=${response.platform}&message=${encodeURIComponent(response.message)}`
        );
      }, 1500);

    } catch (err) {
      console.error('OAuth callback error:', err);
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to complete connection. Please try again.',
      });
    }
  }, [searchParams, router]);

  // Process callback on mount
  useEffect(() => {
    const runCallback = async () => {
      await processCallback();
    };
    runCallback();
  }, [processCallback]);

  // Handle retry
  const handleRetry = () => {
    router.push('/integrations');
  };

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        {/* Loading State */}
        {state.status === 'loading' && (
          <div className="text-center">
            <LoadingSpinner />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Connecting your store
            </h2>
            <p className="mt-2 text-sm text-gray-500">{state.message}</p>
          </div>
        )}

        {/* Success State */}
        {state.status === 'success' && (
          <div className="text-center">
            <SuccessIcon />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Connection successful!
            </h2>
            <p className="mt-2 text-sm text-gray-500">{state.message}</p>
            <p className="mt-4 text-xs text-gray-400">
              Redirecting to integrations...
            </p>
          </div>
        )}

        {/* Error State */}
        {state.status === 'error' && (
          <div className="text-center">
            <ErrorIcon />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Connection failed
            </h2>
            <p className="mt-2 text-sm text-red-600">{state.message}</p>
            <button
              onClick={handleRetry}
              className="mt-6 inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Back to Integrations
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Sub-components ====================

function LoadingSpinner() {
  return (
    <div className="mx-auto h-12 w-12">
      <svg
        className="animate-spin text-indigo-600"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  );
}

function SuccessIcon() {
  return (
    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
      <svg
        className="h-6 w-6 text-green-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    </div>
  );
}

function ErrorIcon() {
  return (
    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
      <svg
        className="h-6 w-6 text-red-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    </div>
  );
}





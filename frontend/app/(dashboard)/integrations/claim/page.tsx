export const dynamic = 'force-dynamic';
// frontend/app/(dashboard)/integrations/claim/page.tsx
'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api/client';

type ClaimStatus = 'claiming' | 'success' | 'error';

export default function ClaimIntegrationPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center"><Spinner /></div>}>
      <ClaimIntegrationContent />
    </Suspense>
  );
}

function ClaimIntegrationContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<ClaimStatus>('claiming');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const integrationId = searchParams.get('integration_id');
    const platform = searchParams.get('platform') ?? 'shopify';

    async function claim() {
      if (!integrationId) {
        setStatus('error');
        setErrorMessage('Missing integration ID. Please try connecting your store again.');
        return;
      }

      try {
        await api.post(`/api/v1/integrations/${integrationId}/claim`, {});
        setStatus('success');
        await new Promise(resolve => setTimeout(resolve, 1500));
        router.push(
          `/integrations?connected=true&integration_id=${integrationId}&platform=${platform}`
        );
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'Failed to link your store. Please try again.';
        setStatus('error');
        setErrorMessage(message);
      }
    }

    claim();
  }, [searchParams, router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white p-8 shadow-sm text-center">

        {status === 'claiming' && (
          <>
            <Spinner />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Linking your store
            </h2>
            <p className="mt-2 text-sm text-gray-500">
              Just a moment while we connect your Shopify store to your account...
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <SuccessIcon />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Store connected!
            </h2>
            <p className="mt-2 text-sm text-gray-500">
              Your Shopify store has been linked to your account.
            </p>
            <p className="mt-4 text-xs text-gray-400">
              Redirecting to integrations...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <ErrorIcon />
            <h2 className="mt-4 text-lg font-medium text-gray-900">
              Connection failed
            </h2>
            <p className="mt-2 text-sm text-red-600">{errorMessage}</p>
            <button
              onClick={() => router.push('/integrations')}
              className="mt-6 inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Go to Integrations
            </button>
          </>
        )}

      </div>
    </div>
  );
}

function Spinner() {
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



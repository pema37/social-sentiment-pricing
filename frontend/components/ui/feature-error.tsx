'use client';

// frontend/components/ui/feature-error.tsx

/**
 * Shared error fallback for per-feature error boundaries.
 *
 * Next.js App Router uses error.tsx files as automatic React Error Boundaries
 * for each route segment. Each error.tsx receives { error, reset } props.
 * This component provides a consistent, branded error UI that:
 *
 * 1. Shows what went wrong (feature name + error message)
 * 2. Offers a "Try again" button (calls reset() to re-render the route)
 * 3. Offers a "Go back" link to a safe parent page
 * 4. Reports the error to Sentry (if configured)
 *
 * Usage in any error.tsx:
 *   'use client';
 *   import { FeatureError } from '@/components/ui/feature-error';
 *   export default function ProductsError({ error, reset }: { error: Error; reset: () => void }) {
 *     return <FeatureError error={error} reset={reset} feature="Products" backHref="/dashboard" />;
 *   }
 */

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, RefreshCw, ArrowLeft } from 'lucide-react';
import * as Sentry from '@sentry/nextjs';

interface FeatureErrorProps {
  /** The error thrown by the route segment */
  error: Error & { digest?: string };
  /** Next.js reset function — re-renders the route segment */
  reset: () => void;
  /** Human-readable feature name shown in the UI (e.g., "Products", "Sentiment Analysis") */
  feature: string;
  /** Safe page to navigate back to if retry doesn't work */
  backHref?: string;
  /** Label for the back link (defaults to "Back to Dashboard") */
  backLabel?: string;
}

export function FeatureError({
  error,
  reset,
  feature,
  backHref = '/dashboard',
  backLabel = 'Back to Dashboard',
}: FeatureErrorProps) {
  useEffect(() => {
    Sentry.captureException(error, {
      tags: { feature: feature.toLowerCase().replace(/\s+/g, '_') },
    });
    console.error(`[${feature}] Error boundary caught:`, error);
  }, [error, feature]);

  return (
    <div className="flex items-center justify-center min-h-100 p-6">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-6 h-6 text-red-600" />
        </div>

        {/* Heading */}
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          {feature} couldn&apos;t load
        </h2>

        {/* Error message — only in development, not in production */}
        <p className="text-sm text-gray-600 mb-1">
          Something went wrong loading this section.
        </p>
        {process.env.NODE_ENV === 'development' && error.message && (
          <p className="text-xs text-red-500 font-mono bg-red-50 rounded-md px-3 py-2 mb-4 break-all">
            {error.message}
          </p>
        )}
        {process.env.NODE_ENV !== 'development' && (
          <p className="text-xs text-gray-400 mb-4">
            This has been reported automatically.
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try again
          </button>
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
          >
            <ArrowLeft className="w-4 h-4" />
            {backLabel}
          </Link>
        </div>
      </div>
    </div>
  );
}



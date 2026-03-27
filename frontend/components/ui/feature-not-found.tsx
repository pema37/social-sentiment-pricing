// frontend/components/ui/feature-not-found.tsx

/**
 * Shared 404 fallback for dynamic [id] routes.
 *
 * Next.js App Router renders the nearest not-found.tsx when a page calls
 * notFound() from 'next/navigation'. Without per-route not-found files,
 * users see a generic Next.js 404 page with no context.
 *
 * This component shows a friendly message with the resource type
 * and a link back to the parent list page.
 *
 * Usage in any not-found.tsx:
 *   import { FeatureNotFound } from '@/components/ui/feature-not-found';
 *   export default function ProductNotFound() {
 *     return <FeatureNotFound resource="Product" listHref="/products" listLabel="Back to Products" />;
 *   }
 */

import Link from 'next/link';
import { SearchX, ArrowLeft } from 'lucide-react';

interface FeatureNotFoundProps {
  /** What the user was looking for (e.g., "Product", "Pricing Rule") */
  resource: string;
  /** URL of the parent list page */
  listHref: string;
  /** Label for the back link (e.g., "Back to Products") */
  listLabel: string;
}

export function FeatureNotFound({
  resource,
  listHref,
  listLabel,
}: FeatureNotFoundProps) {
  return (
    <div className="flex items-center justify-center min-h-100 p-6">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <SearchX className="w-6 h-6 text-gray-400" />
        </div>

        {/* Heading */}
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          {resource} not found
        </h2>

        {/* Description */}
        <p className="text-sm text-gray-600 mb-6">
          This {resource.toLowerCase()} may have been deleted or the link may be
          incorrect. Check the URL and try again.
        </p>

        {/* Back link */}
        <Link
          href={listHref}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          <ArrowLeft className="w-4 h-4" />
          {listLabel}
        </Link>
      </div>
    </div>
  );
}




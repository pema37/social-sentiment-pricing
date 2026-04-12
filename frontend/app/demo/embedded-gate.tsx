export const dynamic = 'force-dynamic';
'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

function Gate({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const isEmbedded = searchParams.get('embedded') === '1';

  if (isEmbedded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Demo Not Available
          </h2>
          <p className="text-sm text-gray-500">
            Demo pages are not available inside the Shopify app. 
            Access your pricing tools from the dashboard.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function DemoEmbeddedGate({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen" />}>
      <Gate>{children}</Gate>
    </Suspense>
  );
}


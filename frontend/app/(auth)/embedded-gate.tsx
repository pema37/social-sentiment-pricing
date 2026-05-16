'use client';

export const dynamic = 'force-dynamic';

import { useSearchParams, useRouter } from 'next/navigation';
import { Suspense, useEffect } from 'react';

function Gate({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const isEmbedded = searchParams.get('embedded') === '1';

  // Inside Shopify → merchants never see login/register
  // App Bridge session tokens handle auth automatically
  useEffect(() => {
    if (isEmbedded) {
      router.replace('/dashboard');
    }
  }, [isEmbedded, router]);

  if (isEmbedded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-gray-500">Redirecting to dashboard...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function AuthEmbeddedGate({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen" />}>
      <Gate>{children}</Gate>
    </Suspense>
  );
}


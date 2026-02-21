'use client';

import { useShopifyEmbedded } from '@/lib/context/shopify-embedded';

export default function PaymentsDemoPage() {
  const { isEmbedded } = useShopifyEmbedded();

  // Hide demo payment page entirely inside Shopify
  if (isEmbedded) {
    return (
      <div className="p-8 text-center text-sm text-gray-500">
        This page is not available in the Shopify app.
      </div>
    );
  }

  return <div>Demo</div>;
}


// Root Page
// Detects Shopify install params, otherwise redirects to login

import { redirect } from 'next/navigation';

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ shop?: string; host?: string; embedded?: string }>;
}) {
  const params = await searchParams;
  
  // Shopify install flow: redirect to backend install endpoint
  if (params.shop) {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'https://social-sentiment-pricing-staging-2ecd.up.railway.app';
    redirect(`${backendUrl}/api/v1/integrations/shopify/install?shop=${params.shop}`);
  }

  // Normal flow: go to login
  redirect('/login');
}


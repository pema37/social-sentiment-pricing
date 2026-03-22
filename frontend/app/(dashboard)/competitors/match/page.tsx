// frontend/app/(dashboard)/competitors/match/page.tsx

'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Sparkles, HelpCircle, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { CompetitorMatchSearch } from '@/components/features/competitors';
import { useCreateCompetitor, useCreateCompetitorProduct } from '@/lib/hooks/use-competitors';
import { useProduct } from '@/lib/hooks/use-products';
import { useToast } from '@/lib/hooks/use-toast';
import type { MatchedProduct } from '@/types';

export default function CompetitorMatchPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center"><div className="animate-spin h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full" /></div>}>
      <CompetitorMatchContent />
    </Suspense>
  );
}

function CompetitorMatchContent() {
  const searchParams = useSearchParams();
  const productId = searchParams.get('productId');
  
  const toast = useToast();
  const createCompetitor = useCreateCompetitor();
  const createCompetitorProduct = useCreateCompetitorProduct();
  
  // Fetch the product if productId is provided
  const { data: product } = useProduct(productId);
  
  // Track linked URLs to show checkmarks
  const [linkedUrls, setLinkedUrls] = useState<string[]>([]);

  // Handle linking a single matched product
  const handleLinkProduct = async (matchedProduct: MatchedProduct) => {
    if (!productId) {
      toast.error('No product selected. Please go back and try again.');
      return;
    }

    try {
      // Step 1: Create or find the competitor (merchant)
      const competitor = await createCompetitor.mutateAsync({
        name: matchedProduct.merchant,
        website: matchedProduct.url ? new URL(matchedProduct.url).origin : undefined,
        description: 'Auto-created from competitor matching',
      });

      // Step 2: Create the competitor product link
      await createCompetitorProduct.mutateAsync({
        competitor_id: competitor.id,
        product_id: productId,
        competitor_product_name: matchedProduct.title,
        competitor_product_url: matchedProduct.url,
        current_price: matchedProduct.price?.toString(),
        currency: matchedProduct.currency || 'USD',
      });

      // Track as linked
      setLinkedUrls((prev) => [...prev, matchedProduct.url]);

      toast.success(`Now tracking ${matchedProduct.title} from ${matchedProduct.merchant}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to link competitor');
      throw error;
    }
  };

  // Show warning if no product selected
  if (!productId) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/products">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Products
            </Button>
          </Link>
        </div>
        
        <Card className="p-6 bg-yellow-50 border-yellow-200">
          <div className="flex gap-3">
            <AlertTriangle className="w-6 h-6 text-yellow-600 shrink-0" />
            <div>
              <h2 className="font-semibold text-yellow-800">No Product Selected</h2>
              <p className="text-yellow-700 mt-1">
                To find competitors, please go to a product page and click the Find Competitors button.
              </p>
              <Link href="/products">
                <Button className="mt-4">
                  Go to Products
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/products/${productId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Product
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-blue-600" />
              Find Competitor Products
            </h1>
            {product && (
              <p className="text-gray-500 mt-1">
                Finding competitors for: <span className="font-medium text-gray-700">{product.name}</span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Main Search Component - pre-filled with product info */}
      <CompetitorMatchSearch
        initialProductName={product?.name || ''}
        initialPrice={product?.current_price || product?.base_price}
        initialKeywords={product?.keywords || []}
        onProductLink={handleLinkProduct}
        linkedUrls={linkedUrls}
      />

      {/* Help Card */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex gap-3">
          <HelpCircle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">How it works:</p>
            <ol className="list-decimal list-inside space-y-1 text-blue-700">
              <li>We pre-filled the search with your product name</li>
              <li>Click Find Competitors to search major retailers</li>
              <li>Click Link on matching products to track their prices</li>
              <li>Linked prices appear on your product dashboard</li>
            </ol>
          </div>
        </div>
      </Card>
    </div>
  );
}



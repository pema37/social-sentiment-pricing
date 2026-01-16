// frontend/app/(dashboard)/competitors/match/page.tsx

'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { ArrowLeft, Sparkles, Zap, HelpCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { 
  CompetitorMatchSearch,
  AutoLinkModal,
} from '@/components/features/competitors';
import { 
  useCreateCompetitor,
  useCreateCompetitorProduct,
} from '@/lib/hooks/use-competitors';
import { useCompetitorSearch } from '@/lib/hooks/use-competitor-matching';
import { useToast } from '@/lib/hooks/use-toast';
import type { MatchedProduct, CreateCompetitorRequest, CreateCompetitorProductRequest } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface LinkingState {
  productId?: string;
  productName?: string;
  ourPrice?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function CompetitorMatchPage() {
  const toast = useToast();
  
  // Track linked URLs to show check marks
  const [linkedUrls, setLinkedUrls] = useState<string[]>([]);
  
  // Create mutations
  const createCompetitor = useCreateCompetitor();
  const createCompetitorProduct = useCreateCompetitorProduct();

  // Handle linking a single matched product
  const handleLinkProduct = useCallback(async (product: MatchedProduct) => {
    try {
      // First, find or create the competitor based on merchant domain
      let competitorId: string;

      // Create competitor for this merchant
      const competitorData: CreateCompetitorRequest = {
        name: product.merchant,
        website: `https://${product.merchant_domain}`,
        description: `Auto-created from competitor matching`,
        is_active: true,
      };

      try {
        const competitor = await createCompetitor.mutateAsync(competitorData);
        competitorId = competitor.id;
      } catch (error: any) {
        // If competitor already exists, try to extract ID from error or search
        // For now, we'll show an error - in production, you'd search existing competitors
        toast.error({
          title: 'Competitor exists',
          message: `${product.merchant} already exists. Please link manually from the competitor page.`,
        });
        return;
      }

      // Create the competitor product link
      // Note: This requires a product_id from YOUR catalog
      // For standalone matching, we'll just create the competitor
      toast.success({
        title: 'Competitor Created',
        message: `${product.merchant} has been added. Link it to your products from the competitor page.`,
      });

      // Mark as linked
      setLinkedUrls((prev) => [...prev, product.url]);

    } catch (error: any) {
      toast.error({
        title: 'Link Failed',
        message: error.message || 'Failed to link competitor product',
      });
    }
  }, [createCompetitor, createCompetitorProduct, toast]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/competitors"
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Competitors
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900">
                Find Competitor Products
              </h1>
            </div>
            <p className="text-gray-600 mt-1">
              Automatically discover competitor listings across major retailers
            </p>
          </div>
        </div>
      </div>

      {/* How it works */}
      <Card className="p-4 mb-6 bg-linear-to-r from-blue-50 to-indigo-50 border-blue-200">
        <div className="flex items-start gap-3">
          <HelpCircle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-900">How it works</h3>
            <ul className="mt-1 text-sm text-blue-800 space-y-1">
              <li>1. Enter a product name (e.g., "iPhone 15 Pro 256GB")</li>
              <li>2. Optionally add keywords to improve accuracy</li>
              <li>3. We search Google Shopping, Google, and DuckDuckGo</li>
              <li>4. Results show confidence scores and price comparisons</li>
              <li>5. Link high-confidence matches to track their prices</li>
            </ul>
          </div>
        </div>
      </Card>

      {/* Search Component */}
      <CompetitorMatchSearch
        onProductLink={handleLinkProduct}
        linkedUrls={linkedUrls}
      />

      {/* Tips */}
      <Card className="mt-6 p-4 bg-gray-50">
        <h3 className="font-medium text-gray-900 mb-2">💡 Tips for better results</h3>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• Include brand name and model number for exact matches</li>
          <li>• Add specific attributes like color, size, or storage capacity</li>
          <li>• Use your product's price to see how competitors compare</li>
          <li>• High-confidence matches (80%+) are most likely to be the same product</li>
        </ul>
      </Card>
    </div>
  );
}



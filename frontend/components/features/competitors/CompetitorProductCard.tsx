// Competitor product card component
'use client';

import { useState } from 'react';
import { ExternalLink, Trash2, RefreshCw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { 
  useDeleteCompetitorProduct, 
  useScrapeCompetitorPrice 
} from '@/lib/hooks/use-competitors';
import type { CompetitorProduct } from '@/types';

interface CompetitorProductCardProps {
  competitorProduct: CompetitorProduct;
  competitorName?: string;
  yourProductName?: string;
  yourPrice?: string;
}

export function CompetitorProductCard({
  competitorProduct,
  competitorName,
  yourProductName,
  yourPrice,
}: CompetitorProductCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const deleteProduct = useDeleteCompetitorProduct();
  const scrapePrice = useScrapeCompetitorPrice();

  const handleDelete = async () => {
    if (!confirm('Remove this competitor product link?')) return;

    setIsDeleting(true);
    try {
      await deleteProduct.mutateAsync(competitorProduct.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleScrape = () => {
    scrapePrice.mutate(competitorProduct.id);
  };

  // Calculate price difference if we have both prices
  const priceDiff = yourPrice && competitorProduct.current_price
    ? parseFloat(yourPrice) - parseFloat(competitorProduct.current_price)
    : null;

  const priceDiffPercent = priceDiff !== null && competitorProduct.current_price
    ? (priceDiff / parseFloat(competitorProduct.current_price)) * 100
    : null;

  return (
    <div className={`bg-white rounded-lg border p-4 ${
      competitorProduct.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-gray-900 truncate">
              {competitorProduct.competitor_product_name}
            </span>
            {!competitorProduct.is_active && (
              <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">
                Inactive
              </span>
            )}
          </div>

          {/* Competitor & Your Product */}
          <div className="text-sm text-gray-500 mb-2">
            {competitorName && <span>{competitorName}</span>}
            {competitorName && yourProductName && <span> · </span>}
            {yourProductName && <span>vs. {yourProductName}</span>}
          </div>

          {/* URL */}
          {competitorProduct.competitor_product_url && (
            <a
              href={competitorProduct.competitor_product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mb-2"
            >
              View on competitor site
              <ExternalLink className="w-3 h-3" />
            </a>
          )}

          {/* Price Comparison */}
          <div className="flex items-center gap-4 mt-2">
            <div>
              <p className="text-xs text-gray-500">Competitor Price</p>
              <p className="font-semibold text-gray-900">
                {competitorProduct.current_price
                  ? `${competitorProduct.currency} ${(parseFloat(competitorProduct.current_price) || 0).toFixed(2)}`
                  : 'No price'}
              </p>
            </div>

            {yourPrice && (
              <div>
                <p className="text-xs text-gray-500">Your Price</p>
                <p className="font-semibold text-gray-900">
                  ${(parseFloat(yourPrice) || 0).toFixed(2)}
                </p>
              </div>
            )}

            {priceDiff !== null && (
              <div>
                <p className="text-xs text-gray-500">Difference</p>
                <p className={`font-semibold ${
                  priceDiff > 0 ? 'text-red-600' : priceDiff < 0 ? 'text-green-600' : 'text-gray-600'
                }`}>
                  {priceDiff > 0 ? '+' : ''}{(priceDiff ?? 0).toFixed(2)}
                  {priceDiffPercent !== null && (
                    <span className="text-xs ml-1">
                      ({priceDiffPercent > 0 ? '+' : ''}{(priceDiffPercent ?? 0).toFixed(1)}%)
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>

          {/* Last Updated */}
          {competitorProduct.last_price_update && (
            <p className="text-xs text-gray-400 mt-2">
              Price updated {formatDistanceToNow(new Date(competitorProduct.last_price_update), { addSuffix: true })}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleScrape}
            disabled={scrapePrice.isPending || !competitorProduct.competitor_product_url}
            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded disabled:opacity-50"
            title="Refresh price"
          >
            <RefreshCw className={`w-4 h-4 ${scrapePrice.isPending ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
            title="Remove link"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}


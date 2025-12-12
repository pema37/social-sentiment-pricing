// Link product to competitor form
'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { useProducts } from '@/lib/hooks/use-products';
import { useCompetitors } from '@/lib/hooks/use-competitors';
import type { CreateCompetitorProductRequest } from '@/types';

interface LinkProductFormProps {
  preselectedCompetitorId?: string;
  preselectedProductId?: string;
  onSubmit: (data: CreateCompetitorProductRequest) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function LinkProductForm({
  preselectedCompetitorId,
  preselectedProductId,
  onSubmit,
  onCancel,
  isSubmitting,
}: LinkProductFormProps) {
  const [competitorId, setCompetitorId] = useState(preselectedCompetitorId ?? '');
  const [productId, setProductId] = useState(preselectedProductId ?? '');
  const [competitorProductName, setCompetitorProductName] = useState('');
  const [competitorProductUrl, setCompetitorProductUrl] = useState('');
  const [currentPrice, setCurrentPrice] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [notes, setNotes] = useState('');

  const { data: productsData, isLoading: productsLoading } = useProducts();
  const { data: competitorsData, isLoading: competitorsLoading } = useCompetitors();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!competitorId || !productId || !competitorProductName.trim()) return;

    onSubmit({
      competitor_id: competitorId,
      product_id: productId,
      competitor_product_name: competitorProductName.trim(),
      competitor_product_url: competitorProductUrl.trim() || undefined,
      current_price: currentPrice ? currentPrice : undefined,
      currency,
      notes: notes.trim() || undefined,
    });
  };

  const isLoading = productsLoading || competitorsLoading;
  const products = productsData?.items ?? [];
  const competitors = competitorsData?.items ?? [];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Link Competitor Product
          </h2>
          <button
            onClick={onCancel}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Your Product */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Your Product *
            </label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              disabled={!!preselectedProductId || isLoading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
              required
            >
              <option value="">Select a product</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} - ${parseFloat(product.current_price).toFixed(2)}
                </option>
              ))}
            </select>
          </div>

          {/* Competitor */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Competitor *
            </label>
            <select
              value={competitorId}
              onChange={(e) => setCompetitorId(e.target.value)}
              disabled={!!preselectedCompetitorId || isLoading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
              required
            >
              <option value="">Select a competitor</option>
              {competitors.map((competitor) => (
                <option key={competitor.id} value={competitor.id}>
                  {competitor.name}
                </option>
              ))}
            </select>
            {competitors.length === 0 && !isLoading && (
              <p className="text-xs text-amber-600 mt-1">
                No competitors yet. Add a competitor first.
              </p>
            )}
          </div>

          <div className="border-t border-gray-200 pt-4">
            <p className="text-sm font-medium text-gray-700 mb-3">
              Competitor Product Details
            </p>

            {/* Competitor Product Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product Name at Competitor *
              </label>
              <input
                type="text"
                value={competitorProductName}
                onChange={(e) => setCompetitorProductName(e.target.value)}
                placeholder="e.g., Premium Widget XL"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            {/* Competitor Product URL */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product URL
              </label>
              <input
                type="url"
                value={competitorProductUrl}
                onChange={(e) => setCompetitorProductUrl(e.target.value)}
                placeholder="https://competitor.com/product/123"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Used for automatic price scraping
              </p>
            </div>

            {/* Price and Currency */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Current Price
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={currentPrice}
                  onChange={(e) => setCurrentPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Currency
                </label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                  <option value="CAD">CAD</option>
                  <option value="AUD">AUD</option>
                </select>
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes about this product match..."
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !competitorId || !productId || !competitorProductName.trim()}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Linking...' : 'Link Product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

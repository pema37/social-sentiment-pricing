'use client';

// frontend/components/features/competitors/CompetitorMatchSearch.tsx

import { useState, useCallback } from 'react';
import {
  Search,
  Sparkles,
  DollarSign,
  Store,
  X,
  Info,
  Zap,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { useCompetitorSearch, useSearchProviders } from '@/lib/hooks/use-competitor-matching';
import { MatchedProductsList } from './MatchedProductsList';
import type { MatchedProduct, CompetitorSearchRequest } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface CompetitorMatchSearchProps {
  initialProductName?: string;
  initialPrice?: string | number;
  initialKeywords?: string[];
  onProductLink?: (product: MatchedProduct) => void;
  linkedUrls?: string[];
  compact?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function KeywordInput({
  keywords,
  onAdd,
  onRemove,
}: {
  keywords: string[];
  onAdd: (keyword: string) => void;
  onRemove: (keyword: string) => void;
}) {
  const [input, setInput] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      if (!keywords.includes(input.trim().toLowerCase())) {
        onAdd(input.trim().toLowerCase());
      }
      setInput('');
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Keywords (optional)
      </label>
      <div className="flex flex-wrap gap-2 mb-2">
        {keywords.map((keyword) => (
          <Badge key={keyword} variant="info" className="flex items-center gap-1">
            {keyword}
            <button
              type="button"
              onClick={() => onRemove(keyword)}
              className="ml-1 hover:text-red-600"
            >
              <X className="w-3 h-3" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        type="text"
        placeholder="Type keyword and press Enter..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <p className="mt-1 text-xs text-gray-500">
        Add brand, model, or specific terms to improve search accuracy
      </p>
    </div>
  );
}

function PreferredMerchantsInput({
  merchants,
  onToggle,
}: {
  merchants: string[];
  onToggle: (merchant: string) => void;
}) {
  const popularMerchants = [
    'Amazon',
    'Walmart',
    'Best Buy',
    'Target',
    'eBay',
    'Newegg',
  ];

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Preferred Merchants
      </label>
      <div className="flex flex-wrap gap-2">
        {popularMerchants.map((merchant) => {
          const isSelected = merchants.includes(merchant);
          return (
            <button
              key={merchant}
              type="button"
              onClick={() => onToggle(merchant)}
              className={`
                px-3 py-1.5 text-sm rounded-full border transition-colors
                ${
                  isSelected
                    ? 'bg-blue-100 border-blue-300 text-blue-700'
                    : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                }
              `}
            >
              <Store className="w-3 h-3 inline mr-1" />
              {merchant}
            </button>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Results from these merchants will appear first
      </p>
    </div>
  );
}

function ProvidersInfo() {
  const { data: providers, isLoading } = useSearchProviders();

  if (isLoading || !providers) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <Info className="w-4 h-4" />
      <span>
        {providers.available_count} of {providers.total_count} search providers available
      </span>
      {providers.providers
        .filter((p) => p.available)
        .map((p) => (
          <Badge key={p.name} variant="default" className="text-xs">
            {p.name.replace(/_/g, ' ')}
          </Badge>
        ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function CompetitorMatchSearch({
  initialProductName = '',
  initialPrice,
  initialKeywords = [],
  onProductLink,
  linkedUrls = [],
  compact = false,
}: CompetitorMatchSearchProps) {
  // Form state
  const [productName, setProductName] = useState(initialProductName);
  const [ourPrice, setOurPrice] = useState(initialPrice?.toString() || '');
  const [keywords, setKeywords] = useState<string[]>(initialKeywords);
  const [preferredMerchants, setPreferredMerchants] = useState<string[]>([]);
  const [maxResults, setMaxResults] = useState(10);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Linking state
  const [linkingUrl, setLinkingUrl] = useState<string | null>(null);

  // Search mutation
  const {
    mutate: search,
    data: searchResponse,
    isPending: isSearching,
    reset: resetSearch,
  } = useCompetitorSearch();

  // Handle search
  const handleSearch = useCallback(() => {
    if (!productName.trim()) return;

    const request: CompetitorSearchRequest = {
      product_name: productName.trim(),
      max_results: maxResults,
    };

    if (keywords.length > 0) {
      request.keywords = keywords;
    }

    if (ourPrice) {
      request.our_price = ourPrice;
    }

    if (preferredMerchants.length > 0) {
      request.preferred_merchants = preferredMerchants;
    }

    search(request);
  }, [productName, keywords, ourPrice, preferredMerchants, maxResults, search]);

  // Handle keyword management
  const addKeyword = (keyword: string) => {
    setKeywords((prev) => [...prev, keyword]);
  };

  const removeKeyword = (keyword: string) => {
    setKeywords((prev) => prev.filter((k) => k !== keyword));
  };

  // Handle merchant toggle
  const toggleMerchant = (merchant: string) => {
    setPreferredMerchants((prev) =>
      prev.includes(merchant)
        ? prev.filter((m) => m !== merchant)
        : [...prev, merchant]
    );
  };

  // Handle product link
  const handleLink = async (product: MatchedProduct) => {
    if (!onProductLink) return;
    
    setLinkingUrl(product.url);
    try {
      await onProductLink(product);
    } finally {
      setLinkingUrl(null);
    }
  };

  // Clear search
  const handleClear = () => {
    setProductName('');
    setOurPrice('');
    setKeywords([]);
    setPreferredMerchants([]);
    resetSearch();
  };

  return (
    <div className="space-y-6">
      {/* Search Form */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900">
            Find Competitor Products
          </h2>
        </div>

        <div className="space-y-4">
          {/* Product Name - Required */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Product Name <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="e.g., iPhone 15 Pro 256GB"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="pl-10"
              />
            </div>
          </div>

          {/* Two-column layout for compact mode */}
          <div className={compact ? 'grid grid-cols-2 gap-4' : 'space-y-4'}>
            {/* Your Price */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Your Price (optional)
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="999.99"
                  value={ourPrice}
                  onChange={(e) => setOurPrice(e.target.value)}
                  className="pl-10"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Used to calculate price differences
              </p>
            </div>

            {/* Max Results (only in advanced) */}
            {!compact && showAdvanced && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Results
                </label>
                <Input
                  type="number"
                  min="1"
                  max="50"
                  value={maxResults}
                  onChange={(e) => setMaxResults(parseInt(e.target.value) || 10)}
                />
              </div>
            )}
          </div>

          {/* Keywords */}
          {(!compact || showAdvanced) && (
            <KeywordInput
              keywords={keywords}
              onAdd={addKeyword}
              onRemove={removeKeyword}
            />
          )}

          {/* Advanced toggle */}
          {!compact && (
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              {showAdvanced ? '− Hide advanced options' : '+ Show advanced options'}
            </button>
          )}

          {/* Advanced Options */}
          {showAdvanced && (
            <div className="pt-4 border-t border-gray-200 space-y-4">
              <PreferredMerchantsInput
                merchants={preferredMerchants}
                onToggle={toggleMerchant}
              />
            </div>
          )}

          {/* Provider Info */}
          <ProvidersInfo />

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={handleSearch}
              disabled={!productName.trim() || isSearching}
              className="flex-1 sm:flex-none"
            >
              {isSearching ? (
                <>
                  <div className="w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Find Competitors
                </>
              )}
            </Button>

            {(searchResponse || productName || keywords.length > 0) && (
              <Button variant="secondary" onClick={handleClear}>
                Clear
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Results */}
      <MatchedProductsList
        response={searchResponse || null}
        isLoading={isSearching}
        ourPrice={ourPrice || undefined}
        onLinkProduct={onProductLink ? handleLink : undefined}
        linkingProductUrl={linkingUrl}
        linkedUrls={linkedUrls}
      />
    </div>
  );
}

export default CompetitorMatchSearch;



'use client';

// components/features/products/KeywordsManager.tsx
import { useState, useCallback, KeyboardEvent } from 'react';
import { Tag, X, Plus, Loader2, Sparkles } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '@/lib/api';
import { productKeys } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface KeywordsManagerProps {
  productId: string;
  keywords: string[];
  onUpdate?: (keywords: string[]) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function normalizeKeyword(keyword: string): string {
  return keyword.trim().toLowerCase();
}

function isValidKeyword(keyword: string): boolean {
  const normalized = normalizeKeyword(keyword);
  return normalized.length >= 2 && normalized.length <= 50;
}

// ─────────────────────────────────────────────────────────────────────────────
// Keyword Badge (removable)
// ─────────────────────────────────────────────────────────────────────────────

interface KeywordBadgeProps {
  keyword: string;
  onRemove: () => void;
  disabled?: boolean;
}

function KeywordBadge({ keyword, onRemove, disabled }: KeywordBadgeProps) {
  return (
    <span className="group inline-flex items-center gap-1 px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm font-medium border border-blue-200 transition-all hover:bg-blue-100">
      {keyword}
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        className="ml-1 p-0.5 rounded-full hover:bg-blue-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label={`Remove ${keyword}`}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty State
// ─────────────────────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="text-center py-4 px-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
      <Tag className="h-8 w-8 text-gray-300 mx-auto mb-2" />
      <p className="text-sm text-gray-500">
        No keywords yet. Add keywords to enable sentiment tracking.
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function KeywordsManager({ productId, keywords: initialKeywords, onUpdate }: KeywordsManagerProps) {
  const [keywords, setKeywords] = useState<string[]>(initialKeywords || []);
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  
  // Silent mutation - no toast on every keyword change
  const updateKeywords = useMutation({
    mutationFn: (newKeywords: string[]) =>
      productsApi.update(productId, { keywords: newKeywords }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });

  const isLoading = updateKeywords.isPending;

  // ─────────────────────────────────────────────────────────────────────────
  // Save to backend
  // ─────────────────────────────────────────────────────────────────────────

  const saveKeywords = useCallback(async (newKeywords: string[]) => {
    try {
      await updateKeywords.mutateAsync(newKeywords);
      onUpdate?.(newKeywords);
      setError(null);
    } catch {
      setError('Failed to save keywords. Please try again.');
      setKeywords(initialKeywords || []);
    }
  }, [updateKeywords, onUpdate, initialKeywords]);

  // ─────────────────────────────────────────────────────────────────────────
  // Add keyword
  // ─────────────────────────────────────────────────────────────────────────

  const addKeyword = useCallback(() => {
    const normalized = normalizeKeyword(inputValue);

    if (!normalized) {
      return;
    }

    if (!isValidKeyword(normalized)) {
      setError('Keyword must be 2-50 characters');
      return;
    }

    if (keywords.includes(normalized)) {
      setError('Keyword already exists');
      return;
    }

    const newKeywords = [...keywords, normalized];
    setKeywords(newKeywords);
    setInputValue('');
    setError(null);
    saveKeywords(newKeywords);
  }, [inputValue, keywords, saveKeywords]);

  // ─────────────────────────────────────────────────────────────────────────
  // Remove keyword
  // ─────────────────────────────────────────────────────────────────────────

  const removeKeyword = useCallback((keywordToRemove: string) => {
    const newKeywords = keywords.filter(k => k !== keywordToRemove);
    setKeywords(newKeywords);
    saveKeywords(newKeywords);
  }, [keywords, saveKeywords]);

  // ─────────────────────────────────────────────────────────────────────────
  // Handle Enter key
  // ─────────────────────────────────────────────────────────────────────────

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addKeyword();
    }
    // Clear error on new input
    if (error) {
      setError(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Tag className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Sentiment Keywords</h3>
            <p className="text-sm text-gray-500">
              Track social mentions matching these keywords
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 bg-purple-50 rounded-full">
          <Sparkles className="h-3.5 w-3.5 text-purple-500" />
          <span className="text-xs font-medium text-purple-600">AI Powered</span>
        </div>
      </div>

      {/* Input */}
      <div className="flex gap-2 mb-4">
        <div className="flex-1 relative">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add keyword (e.g., product name, brand, hashtag)"
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-sm"
            disabled={isLoading}
            maxLength={50}
          />
          {isLoading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
            </div>
          )}
        </div>
        <Button
          type="button"
          onClick={addKeyword}
          disabled={isLoading || !inputValue.trim()}
          className="px-4"
        >
          <Plus className="h-4 w-4 mr-1" />
          Add
        </Button>
      </div>

      {/* Error */}
      {error && (
        <p className="text-sm text-red-600 mb-3">{error}</p>
      )}

      {/* Keywords List */}
      {keywords.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-wrap gap-2">
          {keywords.map((keyword) => (
            <KeywordBadge
              key={keyword}
              keyword={keyword}
              onRemove={() => removeKeyword(keyword)}
              disabled={isLoading}
            />
          ))}
        </div>
      )}

      {/* Info text */}
      <p className="mt-4 text-xs text-gray-400">
        Keywords are used to search social media for mentions. Add product names, 
        brand terms, and relevant hashtags for best results.
      </p>
    </Card>
  );
}

export default KeywordsManager;


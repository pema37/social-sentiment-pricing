'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Card } from '@/components/ui';
import { useAnalyzeSentiment } from '@/lib/hooks';
import { useProducts } from '@/lib/hooks';
import { cn } from '@/lib/utils';
import type { SentimentSource } from '@/types';

interface AnalyzeModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultProductId?: string | null;
}

const SOURCES: { value: SentimentSource; label: string }[] = [
  { value: 'manual', label: 'Manual Entry' },
  { value: 'twitter', label: 'Twitter/X' },
  { value: 'reddit', label: 'Reddit' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'news', label: 'News Article' },
];

export function AnalyzeModal({ isOpen, onClose, defaultProductId }: AnalyzeModalProps) {
  const [productId, setProductId] = useState(defaultProductId || '');
  const [content, setContent] = useState('');
  const [source, setSource] = useState<SentimentSource>('manual');
  const [author, setAuthor] = useState('');
  const [url, setUrl] = useState('');

  const { data: productsData, isLoading: productsLoading } = useProducts({ page: 1, page_size: 100 });
  const analyzeMutation = useAnalyzeSentiment();

  const resetForm = useCallback(() => {
    setContent('');
    setAuthor('');
    setUrl('');
    analyzeMutation.reset();
  }, [analyzeMutation]);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!productId || !content.trim()) return;

    try {
      await analyzeMutation.mutateAsync({
        product_id: productId,
        content: content.trim(),
        source,
        author: author.trim() || undefined,
        url: url.trim() || undefined,
      });

      resetForm();
      onClose();
    } catch (error) {
      // Error is handled by mutation state
      console.error('Analysis failed:', error);
    }
  };

  // Sync productId when defaultProductId changes and modal opens
  if (isOpen && defaultProductId && defaultProductId !== productId) {
    setProductId(defaultProductId);
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="analyze-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <Card className="relative z-10 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 id="analyze-modal-title" className="text-lg font-semibold">
                Analyze Sentiment
              </h2>
              <button
                type="button"
                onClick={handleClose}
                className="p-1 text-gray-400 hover:text-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Close modal"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              {/* Product selector */}
              <div>
                <label htmlFor="analyze-product" className="block text-sm font-medium text-gray-700 mb-1">
                  Product <span className="text-red-500">*</span>
                </label>
                <select
                  id="analyze-product"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                  disabled={productsLoading}
                >
                  <option value="">Select a product</option>
                  {productsData?.items.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Source selector */}
              <div>
                <label htmlFor="analyze-source" className="block text-sm font-medium text-gray-700 mb-1">
                  Source
                </label>
                <select
                  id="analyze-source"
                  value={source}
                  onChange={(e) => setSource(e.target.value as SentimentSource)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {SOURCES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Content textarea */}
              <div>
                <label htmlFor="analyze-content" className="block text-sm font-medium text-gray-700 mb-1">
                  Content <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="analyze-content"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Enter the text you want to analyze for sentiment..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={4}
                  required
                  maxLength={5000}
                />
                <p className="mt-1 text-xs text-gray-500">
                  {content.length}/5000 characters
                </p>
              </div>

              {/* Optional fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="analyze-author" className="block text-sm font-medium text-gray-700 mb-1">
                    Author <span className="text-gray-400">(optional)</span>
                  </label>
                  <Input
                    id="analyze-author"
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    placeholder="@username"
                  />
                </div>
                <div>
                  <label htmlFor="analyze-url" className="block text-sm font-medium text-gray-700 mb-1">
                    URL <span className="text-gray-400">(optional)</span>
                  </label>
                  <Input
                    id="analyze-url"
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://..."
                  />
                </div>
              </div>

              {/* Error message */}
              {analyzeMutation.isError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md" role="alert">
                  <p className="text-sm text-red-700">
                    {analyzeMutation.error instanceof Error
                      ? analyzeMutation.error.message
                      : 'Failed to analyze sentiment. Please try again.'}
                  </p>
                </div>
              )}

              {/* Success result preview */}
              {analyzeMutation.isSuccess && analyzeMutation.data && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-md">
                  <p className="text-sm font-medium text-green-800 mb-2">Analysis Complete!</p>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span className="text-gray-600">Score:</span>
                      <span
                        className={cn(
                          'ml-1 font-medium',
                          analyzeMutation.data.sentiment_score >= 0.05
                            ? 'text-green-600'
                            : analyzeMutation.data.sentiment_score <= -0.05
                            ? 'text-red-600'
                            : 'text-gray-600'
                        )}
                      >
                        {(analyzeMutation.data.sentiment_score * 100).toFixed(0)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Label:</span>
                      <span className="ml-1 font-medium capitalize">
                        {analyzeMutation.data.sentiment_label.replace('_', ' ')}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Confidence:</span>
                      <span className="ml-1 font-medium">
                        {(analyzeMutation.data.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3 rounded-b-lg">
            <Button type="button" variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!productId || !content.trim() || analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? 'Analyzing...' : 'Analyze'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

// components/features/products/GenerateDescriptionModal.tsx
'use client';

import { useState } from 'react';
import { Button, Card } from '@/components/ui';
import { AIBadge } from '@/components/ui/ai-badge';
import { cn } from '@/lib/utils';
import { productsApi } from '@/lib/api';
import { Sparkles, Copy, Check } from 'lucide-react';

interface GenerateDescriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  productId: string;
  productName: string;
  onApply: (description: string) => void;
}

interface GeneratedContent {
  description: string;
  seo_title: string;
  meta_description: string;
  suggested_keywords: string[];
}

const TONES = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'luxury', label: 'Luxury' },
  { value: 'technical', label: 'Technical' },
];

const LENGTHS = [
  { value: 'short', label: 'Short (~50 words)' },
  { value: 'medium', label: 'Medium (~100 words)' },
  { value: 'long', label: 'Long (~200 words)' },
];

export function GenerateDescriptionModal({
  isOpen,
  onClose,
  productId,
  productName,
  onApply,
}: GenerateDescriptionModalProps) {
  const [tone, setTone] = useState('professional');
  const [length, setLength] = useState('medium');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GeneratedContent | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const handleGenerate = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await productsApi.generateDescription(productId, { tone, length });
      setResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error 
                ? err.message 
                : 'Failed to generate description';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleApply = () => {
    if (result) {
      onApply(result.description);
      onClose();
    }
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={handleClose} />

      <Card className="relative z-10 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-600" />
              <h2 className="text-lg font-semibold">Generate Description</h2>
              <AIBadge />
            </div>
            <button
              onClick={handleClose}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <p className="text-sm text-gray-600 mb-6">
            Generate an SEO-optimized description for <strong>{productName}</strong>
          </p>

          {/* Options */}
          {!result && (
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
                <div className="flex flex-wrap gap-2">
                  {TONES.map((t) => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => setTone(t.value)}
                      className={cn(
                        'px-3 py-1.5 text-sm rounded-lg border transition-colors',
                        tone === t.value
                          ? 'border-purple-500 bg-purple-50 text-purple-700'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Length</label>
                <div className="flex flex-wrap gap-2">
                  {LENGTHS.map((l) => (
                    <button
                      key={l.value}
                      type="button"
                      onClick={() => setLength(l.value)}
                      className={cn(
                        'px-3 py-1.5 text-sm rounded-lg border transition-colors',
                        length === l.value
                          ? 'border-purple-500 bg-purple-50 text-purple-700'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 mb-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-4 mb-6">
              {/* Description */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-gray-700">Description</label>
                  <button
                    onClick={() => handleCopy(result.description, 'description')}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    {copied === 'description' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied === 'description' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div
                  className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: result.description }}
                />
              </div>

              {/* SEO Title */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-gray-700">SEO Title</label>
                  <button
                    onClick={() => handleCopy(result.seo_title, 'seo_title')}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    {copied === 'seo_title' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied === 'seo_title' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="p-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                  {result.seo_title}
                </div>
              </div>

              {/* Meta Description */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-gray-700">Meta Description</label>
                  <button
                    onClick={() => handleCopy(result.meta_description, 'meta')}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    {copied === 'meta' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied === 'meta' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="p-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                  {result.meta_description}
                </div>
              </div>

              {/* Keywords */}
              {result.suggested_keywords.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">
                    Suggested Keywords
                  </label>
                  <div className="flex flex-wrap gap-1">
                    {result.suggested_keywords.map((kw, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end gap-3">
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          {result ? (
            <>
              <Button variant="secondary" onClick={() => setResult(null)}>
                Regenerate
              </Button>
              <Button onClick={handleApply}>
                Apply Description
              </Button>
            </>
          ) : (
            <Button onClick={handleGenerate} disabled={isLoading}>
              {isLoading ? (
                <>
                  <span className="animate-spin mr-2">⚡</span>
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate
                </>
              )}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}


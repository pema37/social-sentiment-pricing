// components/features/products/GenerateDescriptionModal.tsx
'use client';

import { useState } from 'react';
import { Button, Card } from '@/components/ui';
import { AIBadge } from '@/components/ui/ai-badge';
import { cn } from '@/lib/utils';
import { productsApi } from '@/lib/api';
import { Sparkles, Copy, Check, CheckCircle } from 'lucide-react';
import DOMPurify from 'dompurify';

interface GenerateDescriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  productId: string;
  productName: string;
  onApply: (fields: {
    description?: string;
    seo_title?: string;
    meta_description?: string;
    keywords?: string[];
  }) => void;
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
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set());

  const handleGenerate = async () => {
    setIsLoading(true);
    setError(null);
    setAppliedFields(new Set());

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

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(field);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setError('Failed to copy to clipboard');
    }
  };

  // Apply individual field
  const handleApplyField = (field: 'description' | 'seo_title' | 'meta_description' | 'keywords') => {
    if (!result) return;
    
    if (field === 'keywords') {
      onApply({ keywords: result.suggested_keywords });
    } else {
      onApply({ [field]: result[field] });
    }
    
    setAppliedFields(prev => new Set([...prev, field]));
  };

  // Apply all fields
  const handleApplyAll = () => {
    if (!result) return;
    onApply({
      description: result.description,
      seo_title: result.seo_title,
      meta_description: result.meta_description,
      keywords: result.suggested_keywords,
    });
    setAppliedFields(new Set(['description', 'seo_title', 'meta_description', 'keywords']));
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    setAppliedFields(new Set());
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
              <FieldResult
                label="Description"
                isApplied={appliedFields.has('description')}
                isCopied={copied === 'description'}
                onApply={() => handleApplyField('description')}
                onCopy={() => handleCopy(result.description, 'description')}
              >
                <div
                  className="p-3 bg-white border border-gray-200 rounded-lg text-sm prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(result.description) }}
                />
              </FieldResult>

              {/* SEO Title */}
              <FieldResult
                label="SEO Title"
                isApplied={appliedFields.has('seo_title')}
                isCopied={copied === 'seo_title'}
                onApply={() => handleApplyField('seo_title')}
                onCopy={() => handleCopy(result.seo_title, 'seo_title')}
              >
                <div className="p-2 bg-white border border-gray-200 rounded-lg text-sm">
                  {result.seo_title}
                </div>
              </FieldResult>

              {/* Meta Description */}
              <FieldResult
                label="Meta Description"
                isApplied={appliedFields.has('meta_description')}
                isCopied={copied === 'meta_description'}
                onApply={() => handleApplyField('meta_description')}
                onCopy={() => handleCopy(result.meta_description, 'meta_description')}
              >
                <div className="p-2 bg-white border border-gray-200 rounded-lg text-sm">
                  {result.meta_description}
                </div>
              </FieldResult>

              {/* Keywords */}
              {result.suggested_keywords.length > 0 && (
                <FieldResult
                  label="Suggested Keywords"
                  isApplied={appliedFields.has('keywords')}
                  isCopied={copied === 'keywords'}
                  onApply={() => handleApplyField('keywords')}
                  onCopy={() => handleCopy(result.suggested_keywords.join(', '), 'keywords')}
                >
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
                  <p className="text-xs text-gray-400 mt-1">
                    Click Copy for comma-separated format
                  </p>
                </FieldResult>
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
              <Button variant="secondary" onClick={() => { setResult(null); setAppliedFields(new Set()); }}>
                Regenerate
              </Button>
              <Button 
                onClick={handleApplyAll}
                disabled={appliedFields.size === 4}
                className="bg-purple-600 hover:bg-purple-700"
              >
                {appliedFields.size === 4 ? 'All Applied' : 'Apply All'}
              </Button>
            </>
          ) : (
            <Button onClick={handleGenerate} disabled={isLoading} className="bg-purple-600 hover:bg-purple-700">
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

// Sub-component for each field result with individual Apply button
interface FieldResultProps {
  label: string;
  isApplied: boolean;
  isCopied: boolean;
  onApply: () => void;
  onCopy: () => void;
  children: React.ReactNode;
}

function FieldResult({ label, isApplied, isCopied, onApply, onCopy, children }: FieldResultProps) {
  return (
    <div className={cn(
      "border rounded-lg p-3 transition-colors",
      isApplied ? "border-green-300 bg-green-50" : "border-gray-200 bg-gray-50"
    )}>
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
          {label}
          {isApplied && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <CheckCircle className="w-3 h-3" />
              Applied
            </span>
          )}
        </label>
        <div className="flex items-center gap-2">
          <button
            onClick={onCopy}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-white"
          >
            {isCopied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
            {isCopied ? 'Copied!' : 'Copy'}
          </button>
          <Button
            variant={isApplied ? "secondary" : "primary"}
            size="sm"
            onClick={onApply}
            disabled={isApplied}
            className={cn(
              "text-xs h-7",
              !isApplied && "bg-purple-600 hover:bg-purple-700"
            )}
          >
            {isApplied ? 'Applied' : 'Apply'}
          </Button>
        </div>
      </div>
      {children}
    </div>
  );
}


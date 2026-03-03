'use client';

/**
 * Free Pricing Audit — Public Lead Magnet Page
 *
 * Route: /audit (outside the (dashboard) layout — no auth required)
 *
 * Flow:
 * 1. Prospect enters Shopify URL or pastes products
 * 2. We show teaser results (top 5 + headline numbers) — free
 * 3. "Get Full Report" requires email → downloads PDF
 */

import { useState, useEffect } from 'react';

// ── Types ────────────────────────────────────────────────────

interface ProspectProduct {
  name: string;
  price: number;
  sku?: string;
}

interface ProductResult {
  name: string;
  sku: string | null;
  your_price: string;
  market_avg_price: string | null;
  gap_percent: string | null;
  gap_type: 'overpriced' | 'underpriced' | 'aligned' | 'no_data';
  competitor_count: number;
}

interface AuditTeaser {
  store_name: string | null;
  total_products_found: number;
  products_with_market_data: number;
  estimated_monthly_impact: string;
  products_overpriced: number;
  products_underpriced: number;
  avg_gap_percent: string | null;
  top_products: ProductResult[];
  remaining_products_count: number;
  cta_message: string;
}

// ── Helpers ──────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// ── Analytics Tracker ────────────────────────────────────────

function trackEvent(
  eventType: string,
  data?: {
    store_url?: string;
    email?: string;
    input_mode?: string;
    products_found?: number;
    estimated_impact?: string;
  }
) {
  fetch(`${API_BASE}/api/v1/prospect/analytics/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_type: eventType, ...data }),
  }).catch(() => {}); // Fire and forget — never block UI
}

function fmtCurrency(val: string | number): string {
  const num = typeof val === 'string' ? parseFloat(val) : val;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num);
}

function fmtPct(val: string | number | null): string {
  if (!val) return '—';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  return `${num >= 0 ? '+' : ''}${num.toFixed(1)}%`;
}

type InputMode = 'url' | 'csv';


// ── Loading Progress Steps ───────────────────────────────────

function AnalysisProgress({ mode }: { mode: InputMode }) {
  const [step, setStep] = useState(0);

  const steps = mode === 'url'
    ? [
        'Connecting to store...',
        'Fetching product catalog...',
        'Analyzing pricing gaps...',
        'Calculating revenue impact...',
        'Building your report...',
      ]
    : [
        'Processing your products...',
        'Analyzing pricing gaps...',
        'Calculating revenue impact...',
        'Building your report...',
      ];

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => Math.min(s + 1, steps.length - 1));
    }, 1500);
    return () => clearInterval(interval);
  }, [steps.length]);

  return (
    <div className="max-w-md mx-auto mt-12 px-6">
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center shadow-sm">
        {/* Spinner */}
        <div className="w-16 h-16 mx-auto mb-6 relative">
          <div className="absolute inset-0 border-4 border-blue-100 rounded-full" />
          <div className="absolute inset-0 border-4 border-blue-600 rounded-full border-t-transparent animate-spin" />
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {steps.map((label, i) => (
            <div
              key={label}
              className={`flex items-center gap-3 transition-all duration-300 ${
                i < step ? 'opacity-50' : i === step ? 'opacity-100' : 'opacity-30'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                  i < step
                    ? 'bg-green-500'
                    : i === step
                    ? 'bg-blue-600'
                    : 'bg-gray-200'
                }`}
              >
                {i < step ? (
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : i === step ? (
                  <div className="w-2 h-2 bg-white rounded-full" />
                ) : null}
              </div>
              <p className={`text-sm ${i === step ? 'font-medium text-gray-900' : 'text-gray-500'}`}>
                {label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Error State ──────────────────────────────────────────────

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const isStoreError = message.toLowerCase().includes('store') || message.toLowerCase().includes('fetch');

  return (
    <div className="max-w-md mx-auto mt-12 px-6">
      <div className="bg-white rounded-2xl border border-red-200 p-8 text-center">
        <div className="w-14 h-14 mx-auto mb-4 bg-red-50 rounded-full flex items-center justify-center">
          <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>

        <h3 className="text-lg font-semibold text-gray-900">Couldn&apos;t complete the analysis</h3>
        <p className="text-sm text-gray-500 mt-2">{message}</p>

        {isStoreError && (
          <div className="mt-4 text-left bg-gray-50 rounded-lg p-4">
            <p className="text-xs font-medium text-gray-700 mb-2">Common fixes:</p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li>• Make sure the URL is a Shopify store (ends in .myshopify.com or a custom domain)</li>
              <li>• The store must be publicly accessible (not password-protected)</li>
              <li>• Check for typos in the URL</li>
            </ul>
          </div>
        )}

        <button
          onClick={onRetry}
          className="mt-6 px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}

// ── Empty Results State ──────────────────────────────────────

function EmptyResultsState({ storeName }: { storeName?: string | null }) {
  return (
    <div className="max-w-md mx-auto mt-12 px-6">
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
        <div className="w-14 h-14 mx-auto mb-4 bg-blue-50 rounded-full flex items-center justify-center">
          <svg className="w-7 h-7 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <h3 className="text-lg font-semibold text-gray-900">
          {storeName ? `${storeName} looks great!` : 'No pricing data found'}
        </h3>
        <p className="text-sm text-gray-500 mt-2">
          {storeName
            ? "We couldn't find significant pricing gaps in your catalog. Your pricing seems well-positioned."
            : "We couldn't find enough products to analyze. Try a different store URL or paste your products manually."}
        </p>

        <a
          href="https://cal.com/actualprice/demo"
          onClick={() => trackEvent('demo_clicked')}
          className="inline-block mt-6 px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition"
        >
          Still curious? Book a deeper analysis
        </a>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────

export default function FreeAuditPage() {
  const [mode, setMode] = useState<InputMode>('url');
  const [storeUrl, setStoreUrl] = useState('');
  const [csvText, setCsvText] = useState('');
  const [loading, setLoading] = useState(false);
  const [teaser, setTeaser] = useState<AuditTeaser | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Email gate
  const [email, setEmail] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfDone, setPdfDone] = useState(false);

  // Track page view on mount
  useEffect(() => {
    trackEvent('page_view');
  }, []);

  // ── Submit Audit ─────────────────────────────────────────

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    setError(null);
    setTeaser(null);
    setLoading(true);
    setPdfDone(false);

    try {
      let body: Record<string, unknown> = {};

      if (mode === 'url') {
        if (!storeUrl.trim()) {
          setError('Please enter a store URL.');
          setLoading(false);
          return;
        }
        body = { store_url: storeUrl.trim() };
      } else {
        const products = parseCsv(csvText);
        if (products.length === 0) {
          setError('Please paste at least one product (name, price per line).');
          setLoading(false);
          return;
        }
        body = { products };
      }

      const resp = await fetch(`${API_BASE}/api/v1/prospect/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      trackEvent('audit_started', {
        input_mode: mode,
        store_url: mode === 'url' ? storeUrl.trim() : undefined,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (resp.status === 429) {
          throw new Error('Too many requests. Please wait a minute and try again.');
        }
        throw new Error(data.detail || `Something went wrong (error ${resp.status}).`);
      }

      const data: AuditTeaser = await resp.json();
      setTeaser(data);

      trackEvent('audit_completed', {
        input_mode: mode,
        store_url: mode === 'url' ? storeUrl.trim() : undefined,
        products_found: data.total_products_found,
        estimated_impact: data.estimated_monthly_impact,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  // ── Retry ────────────────────────────────────────────────

  function handleRetry() {
    setError(null);
    setTeaser(null);
  }

  // ── Request PDF ──────────────────────────────────────────

  async function handlePdfRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;

    setPdfLoading(true);

    trackEvent('email_submitted', {
      email: email.trim(),
      input_mode: mode,
      store_url: mode === 'url' ? storeUrl.trim() : undefined,
    });

    try {
      const body: Record<string, unknown> = {
        email: email.trim(),
        company_name: companyName.trim() || undefined,
      };

      if (mode === 'url') {
        body.store_url = storeUrl.trim();
      } else {
        body.products = parseCsv(csvText);
      }

      const resp = await fetch(`${API_BASE}/api/v1/prospect/audit/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        if (resp.status === 429) {
          throw new Error('Too many requests. Please wait a minute and try again.');
        }
        throw new Error('Failed to generate PDF');
      }

      // Download the PDF
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'pricing-audit.pdf';
      a.click();
      URL.revokeObjectURL(url);

      trackEvent('pdf_downloaded', {
        email: email.trim(),
        input_mode: mode,
        store_url: mode === 'url' ? storeUrl.trim() : undefined,
      });

      setPdfDone(true);
    } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to generate PDF. Please try again.');
    } finally {
      setPdfLoading(false);
    }
  }

  // ── CSV Parser ───────────────────────────────────────────

  function parseCsv(text: string): ProspectProduct[] {
    const lines = text.trim().split('\n').filter(Boolean);
    const products: ProspectProduct[] = [];

    for (const line of lines) {
      const parts = line.split(/[,\t]+/).map((s) => s.trim());
      if (parts.length < 2) continue;

      const name = parts[0];
      const price = parseFloat(parts[1]);
      if (!name || isNaN(price) || price <= 0) continue;

      products.push({ name, price, sku: parts[2] || undefined });
    }
    return products;
  }

  // ── Render ───────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-linear-to-br from-blue-700 to-blue-900 text-white">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <div className="inline-flex items-center gap-2 bg-blue-600/50 rounded-full px-4 py-1.5 text-sm mb-6">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            Free — No signup required
          </div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight">
            How much money is your pricing leaving on the table?
          </h1>
          <p className="text-lg text-blue-200 mt-4 max-w-2xl mx-auto">
            Enter your Shopify store URL or paste your product list.
            We&apos;ll analyze your pricing in under 30 seconds.
          </p>
        </div>
      </div>

      {/* Input Section — only show when not loading and no results */}
      {!loading && !teaser && !error && (
        <div className="max-w-2xl mx-auto px-6 -mt-8">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-6">
            {/* Mode Toggle */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setMode('url')}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition ${
                  mode === 'url'
                    ? 'bg-blue-600 text-white shadow'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Shopify Store URL
              </button>
              <button
                onClick={() => setMode('csv')}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition ${
                  mode === 'csv'
                    ? 'bg-blue-600 text-white shadow'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Paste Products
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              {mode === 'url' ? (
                <input
                  type="text"
                  value={storeUrl}
                  onChange={(e) => setStoreUrl(e.target.value)}
                  placeholder="https://your-store.myshopify.com"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              ) : (
                <div>
                  <textarea
                    value={csvText}
                    onChange={(e) => setCsvText(e.target.value)}
                    placeholder={"Product Name, Price\nClassic T-Shirt, 29.99\nRunning Shoes, 89.00\nWireless Earbuds, 49.95"}
                    rows={6}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">One product per line: Name, Price (optional: , SKU)</p>
                </div>
              )}

              <button
                type="submit"
                className="w-full mt-4 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition"
              >
                Run Free Pricing Audit
              </button>
            </form>

            {/* Trust signals */}
            <div className="flex items-center justify-center gap-6 mt-5 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                No data stored
              </span>
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                30 second analysis
              </span>
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                100% free
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && <AnalysisProgress mode={mode} />}

      {/* Error State */}
      {!loading && error && !teaser && (
        <ErrorState message={error} onRetry={handleRetry} />
      )}

      {/* Empty Results */}
      {!loading && teaser && teaser.total_products_found === 0 && (
        <EmptyResultsState storeName={teaser.store_name} />
      )}

      {/* Results */}
      {!loading && teaser && teaser.total_products_found > 0 && (
        <div className="max-w-3xl mx-auto px-6 mt-10 space-y-6 pb-16">
          {/* Headline Card */}
          <div className="bg-linear-to-br from-red-50 to-orange-50 border border-red-200 rounded-2xl p-8 text-center">
            {teaser.store_name && (
              <p className="text-sm text-gray-500 mb-1">{teaser.store_name}</p>
            )}
            <p className="text-sm font-medium text-red-600 uppercase tracking-wider">
              Estimated Monthly Pricing Gap
            </p>
            <p className="text-5xl font-black text-red-700 mt-2">
              {fmtCurrency(teaser.estimated_monthly_impact)}
              <span className="text-xl font-normal text-red-500">/mo</span>
            </p>
            <p className="text-gray-600 mt-3">
              {teaser.total_products_found} products analyzed ·{' '}
              {teaser.products_overpriced} overpriced ·{' '}
              {teaser.products_underpriced} underpriced
              {teaser.avg_gap_percent && (
                <> · Avg gap: {fmtPct(teaser.avg_gap_percent)}</>
              )}
            </p>
          </div>

          {/* Top Products Table */}
          {teaser.top_products.length > 0 && (
            <div className="bg-white rounded-2xl shadow border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h3 className="font-bold text-gray-900">Top Pricing Gaps</h3>
                <p className="text-sm text-gray-500">Your 5 biggest pricing opportunities</p>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                    <th className="px-6 py-3 text-left">Product</th>
                    <th className="px-6 py-3 text-right">Your Price</th>
                    <th className="px-6 py-3 text-right">Market Avg</th>
                    <th className="px-6 py-3 text-right">Gap</th>
                  </tr>
                </thead>
                <tbody>
                  {teaser.top_products.map((p, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="px-6 py-3">
                        <p className="font-medium text-gray-900 text-sm">{p.name}</p>
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-sm">
                        {fmtCurrency(p.your_price)}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-sm text-gray-500">
                        {p.market_avg_price ? fmtCurrency(p.market_avg_price) : '—'}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                            p.gap_type === 'overpriced'
                              ? 'bg-red-100 text-red-700'
                              : p.gap_type === 'underpriced'
                              ? 'bg-orange-100 text-orange-700'
                              : 'bg-green-100 text-green-700'
                          }`}
                        >
                          {fmtPct(p.gap_percent)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {teaser.remaining_products_count > 0 && (
                <div className="px-6 py-4 bg-gray-50 text-center">
                  <p className="text-sm text-gray-600">
                    + <strong>{teaser.remaining_products_count} more products</strong> in the full report
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Email Gate → PDF Download */}
          <div className="bg-white rounded-2xl shadow border border-gray-200 p-8">
            <h3 className="text-xl font-bold text-gray-900 text-center">
              Get the Full Report
            </h3>
            <p className="text-gray-500 text-center mt-1 text-sm">
              {teaser.cta_message}
            </p>

            {pdfDone ? (
              <div className="mt-6 text-center">
                <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-3 rounded-lg">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="font-medium">PDF downloaded! Check your downloads folder.</span>
                </div>
                <p className="text-sm text-gray-500 mt-3">
                  Want to automatically track these prices 24/7?{' '}
                  <a href="https://cal.com/actualprice/demo" onClick={() => trackEvent('demo_clicked')} className="text-blue-600 font-medium hover:underline">
                    Book a demo →
                  </a>
                </p>
              </div>
            ) : (
              <form onSubmit={handlePdfRequest} className="mt-6 space-y-3">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Company name (optional)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />

                {error && (
                  <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={pdfLoading}
                  className="w-full py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50 transition"
                >
                  {pdfLoading ? 'Generating PDF...' : 'Download Full PDF Report'}
                </button>
                <p className="text-xs text-gray-400 text-center">No spam. We&apos;ll send you the report and follow up once.</p>
              </form>
            )}
          </div>

          {/* Final CTA */}
          <div className="text-center py-8">
            <p className="text-gray-500 text-sm">
              ActualPrice monitors your competitors 24/7 and shows you exactly when to adjust prices.
            </p>
            <a
              href="https://cal.com/actualprice/demo"
              onClick={() => trackEvent('demo_clicked')}
              className="inline-block mt-3 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition"
            >
              Book a Demo
            </a>
          </div>

          {/* Run another audit */}
          <div className="text-center">
            <button
              onClick={handleRetry}
              className="text-sm text-gray-400 hover:text-gray-600 underline transition"
            >
              Run another audit
            </button>
          </div>
        </div>
      )}
    </div>
  );
}




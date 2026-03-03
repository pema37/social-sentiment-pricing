'use client';

/**
 * Retrospective Loss Audit Page
 *
 * The "Free Pricing Audit" dashboard — shows merchants (and prospects)
 * exactly how much money they left on the table over the last 90 days.
 *
 * Route: (dashboard)/analytics/audit/page.tsx
 */

import { useState } from 'react';
import { useLatestAudit } from '@/lib/hooks/use-retrospective-audit';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { SectionHeader } from '@/components/ui/SectionHeader';
import { Download, Loader2, Mail, X, Send, CheckCircle } from 'lucide-react';
import type { SKUAuditResult } from '@/types/retrospective-audit';

// ── Helpers ──────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function formatCurrency(value: string | number): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}

function formatPercent(value: string | number | null): string {
  if (value === null || value === undefined) return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return `${num >= 0 ? '+' : ''}${num.toFixed(1)}%`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function getAuthToken(): string {
  return typeof window !== 'undefined'
    ? localStorage.getItem('access_token') || ''
    : '';
}

// ── PDF Export Hook ──────────────────────────────────────────

function useExportPdf() {
  const [loading, setLoading] = useState(false);

  async function exportPdf(lookbackDays: number) {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/audit/retrospective/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({ lookback_days: lookbackDays }),
      });

      if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pricing-audit-${lookbackDays}d.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setLoading(false);
    }
  }

  return { exportPdf, loading };
}

// ── Email Audit Hook ─────────────────────────────────────────

function useEmailAudit() {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendEmail(payload: {
    to_email: string;
    lookback_days: number;
    store_name?: string;
    personal_note?: string;
  }) {
    setLoading(true);
    setError(null);
    setSent(false);

    try {
      const resp = await fetch(`${API_BASE}/api/v1/audit/retrospective/email`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Failed: ${resp.status}`);
      }

      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to send email');
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setSent(false);
    setError(null);
  }

  return { sendEmail, loading, sent, error, reset };
}

// ── Email Modal ──────────────────────────────────────────────

function EmailAuditModal({
  lookbackDays,
  onClose,
}: {
  lookbackDays: number;
  onClose: () => void;
}) {
  const [toEmail, setToEmail] = useState('');
  const [storeName, setStoreName] = useState('');
  const [personalNote, setPersonalNote] = useState('');
  const { sendEmail, loading, sent, error, reset } = useEmailAudit();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!toEmail.trim()) return;
    sendEmail({
      to_email: toEmail.trim(),
      lookback_days: lookbackDays,
      store_name: storeName.trim() || undefined,
      personal_note: personalNote.trim() || undefined,
    });
  }

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={handleClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Mail className="w-5 h-5 text-blue-600" />
            <h3 className="font-bold text-gray-900">Email Audit Report</h3>
          </div>
          <button onClick={handleClose} className="p-1 hover:bg-gray-100 rounded-lg transition">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {sent ? (
            <div className="text-center py-6">
              <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <p className="text-lg font-semibold text-gray-900">Email sent!</p>
              <p className="text-sm text-gray-500 mt-1">
                The audit PDF was sent to <strong>{toEmail}</strong>
              </p>
              <Button variant="primary" size="sm" className="mt-4" onClick={handleClose}>
                Done
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Recipient email *
                </label>
                <input
                  type="email"
                  value={toEmail}
                  onChange={(e) => setToEmail(e.target.value)}
                  placeholder="prospect@store.com"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Store name
                </label>
                <input
                  type="text"
                  value={storeName}
                  onChange={(e) => setStoreName(e.target.value)}
                  placeholder="Their Store Name (shown in subject line)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Personal note
                </label>
                <textarea
                  value={personalNote}
                  onChange={(e) => setPersonalNote(e.target.value)}
                  placeholder="Optional message included above the CTA button..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-none"
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
              )}

              <Button
                type="submit"
                variant="primary"
                disabled={loading || !toEmail.trim()}
                className="w-full"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                {loading ? 'Sending...' : 'Send Audit PDF'}
              </Button>

              <p className="text-xs text-gray-400 text-center">
                Sends a branded email with the PDF attached and your cal.com booking link
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Headline Card ────────────────────────────────────────────

function HeadlineCard({
  totalImpact,
  lostRevenue,
  missedMargin,
  monthlyLoss,
  annualLoss,
  productsAnalyzed,
  lookbackDays,
}: {
  totalImpact: string;
  lostRevenue: string;
  missedMargin: string;
  monthlyLoss: string;
  annualLoss: string;
  productsAnalyzed: number;
  lookbackDays: number;
}) {
  return (
    <Card className="bg-linear-to-br from-red-50 to-orange-50 border-red-200">
      <div className="p-6">
        <p className="text-sm font-medium text-red-600 uppercase tracking-wider">
          Estimated Money Left on the Table
        </p>
        <p className="text-4xl font-black text-red-700 mt-2">
          {formatCurrency(totalImpact)}
        </p>
        <p className="text-sm text-gray-600 mt-1">
          Over the last {lookbackDays} days across {productsAnalyzed} products
        </p>

        <div className="grid grid-cols-2 gap-4 mt-6">
          <div>
            <p className="text-xs text-gray-500 uppercase">Lost Revenue (Overpriced)</p>
            <p className="text-lg font-bold text-red-600">{formatCurrency(lostRevenue)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">Missed Margin (Underpriced)</p>
            <p className="text-lg font-bold text-orange-600">{formatCurrency(missedMargin)}</p>
          </div>
        </div>

        <div className="border-t border-red-200 mt-4 pt-4 flex gap-6">
          <div>
            <p className="text-xs text-gray-500">Monthly projection</p>
            <p className="text-sm font-semibold text-red-700">{formatCurrency(monthlyLoss)}/mo</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Annual projection</p>
            <p className="text-sm font-semibold text-red-700">{formatCurrency(annualLoss)}/yr</p>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ── SKU Row ──────────────────────────────────────────────────

function SKURow({
  sku,
  onSelect,
}: {
  sku: SKUAuditResult;
  onSelect: (sku: SKUAuditResult) => void;
}) {
  const impact = parseFloat(sku.total_estimated_impact);
  const isSignificant = impact > 100;

  return (
    <tr
      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
      onClick={() => onSelect(sku)}
    >
      <td className="px-4 py-3">
        <div>
          <p className="font-medium text-gray-900">{sku.product_name}</p>
          {sku.sku && <p className="text-xs text-gray-500">{sku.sku}</p>}
        </div>
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {formatCurrency(sku.current_price)}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {sku.current_competitor_avg ? formatCurrency(sku.current_competitor_avg) : '—'}
      </td>
      <td className="px-4 py-3 text-right">
        {sku.current_gap_percent !== null ? (
          <Badge
            variant={parseFloat(sku.current_gap_percent) > 2 ? 'danger' : parseFloat(sku.current_gap_percent) < -2 ? 'warning' : 'success'}
          >
            {formatPercent(sku.current_gap_percent)}
          </Badge>
        ) : (
          '—'
        )}
      </td>
      <td className="px-4 py-3 text-center text-sm">
        <span className="text-red-600 font-medium">{sku.days_overpriced}d</span>
        {' / '}
        <span className="text-orange-500 font-medium">{sku.days_underpriced}d</span>
        {' / '}
        <span className="text-green-600">{sku.days_aligned}d</span>
      </td>
      <td className={`px-4 py-3 text-right font-mono text-sm font-bold ${isSignificant ? 'text-red-700' : 'text-gray-600'}`}>
        {formatCurrency(sku.total_estimated_impact)}
      </td>
    </tr>
  );
}

// ── SKU Detail Panel ─────────────────────────────────────────

function SKUDetailPanel({
  sku,
  onClose,
}: {
  sku: SKUAuditResult;
  onClose: () => void;
}) {
  return (
    <Card className="mt-4">
      <div className="p-6">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-bold">{sku.product_name}</h3>
            <p className="text-sm text-gray-500">{sku.sku} · {sku.competitor_count} competitors ({sku.competitor_names.join(', ')})</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-4">
          <div className="p-3 bg-red-50 rounded-lg">
            <p className="text-xs text-red-600 uppercase">Lost Revenue</p>
            <p className="text-xl font-bold text-red-700">{formatCurrency(sku.estimated_lost_revenue)}</p>
            <p className="text-xs text-gray-500">{sku.days_overpriced} days overpriced (avg {formatPercent(sku.avg_overpriced_gap_percent)})</p>
          </div>
          <div className="p-3 bg-orange-50 rounded-lg">
            <p className="text-xs text-orange-600 uppercase">Missed Margin</p>
            <p className="text-xl font-bold text-orange-700">{formatCurrency(sku.estimated_missed_margin)}</p>
            <p className="text-xs text-gray-500">{sku.days_underpriced} days underpriced (avg {formatPercent(sku.avg_underpriced_gap_percent)})</p>
          </div>
          <div className="p-3 bg-green-50 rounded-lg">
            <p className="text-xs text-green-600 uppercase">Aligned Days</p>
            <p className="text-xl font-bold text-green-700">{sku.days_aligned}</p>
            <p className="text-xs text-gray-500">Within ±2% of optimal</p>
          </div>
        </div>

        {/* Mini gap timeline */}
        {sku.daily_gaps.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Pricing Gap Timeline</p>
            <div className="flex gap-px overflow-x-auto">
              {sku.daily_gaps.map((gap, i) => (
                <div
                  key={i}
                  className={`w-2 rounded-sm ${
                    gap.gap_type === 'overpriced'
                      ? 'bg-red-400'
                      : gap.gap_type === 'underpriced'
                      ? 'bg-orange-400'
                      : 'bg-green-400'
                  }`}
                  style={{ height: `${Math.min(40, Math.max(4, Math.abs(parseFloat(gap.gap_percent)) * 3))}px` }}
                  title={`${formatDate(gap.date)}: ${formatPercent(gap.gap_percent)} (${gap.gap_type})`}
                />
              ))}
            </div>
            <div className="flex gap-4 mt-1 text-xs text-gray-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded-sm" /> Overpriced</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-orange-400 rounded-sm" /> Underpriced</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-400 rounded-sm" /> Aligned</span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

// ── Main Page ────────────────────────────────────────────────

export default function RetrospectiveAuditPage() {
  const [lookbackDays, setLookbackDays] = useState(90);
  const [selectedSku, setSelectedSku] = useState<SKUAuditResult | null>(null);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const { exportPdf, loading: pdfLoading } = useExportPdf();

  const { data: audit, isLoading, error } = useLatestAudit(lookbackDays);

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <SectionHeader title="Pricing Audit" description="Analyzing your pricing history..." />
        <div className="animate-pulse space-y-4">
          <div className="h-48 bg-gray-100 rounded-xl" />
          <div className="h-64 bg-gray-100 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <SectionHeader title="Pricing Audit" />
        <Card className="p-6 mt-4">
          <p className="text-red-600">Failed to generate audit. Make sure you have products with competitor data linked.</p>
        </Card>
      </div>
    );
  }

  if (!audit || audit.summary.total_products_analyzed === 0) {
    return (
      <div className="p-6">
        <SectionHeader
          title="Pricing Audit"
          description="See how much money you're leaving on the table"
        />
        <Card className="p-8 mt-4 text-center">
          <p className="text-gray-600 text-lg">No products with competitor data found.</p>
          <p className="text-gray-500 mt-2">
            Link competitor products to your SKUs first, then come back here to see your retrospective loss analysis.
          </p>
        </Card>
      </div>
    );
  }

  const { summary, sku_results, methodology } = audit;

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-start">
        <SectionHeader
          title="Retrospective Pricing Audit"
          description={`${formatDate(summary.analysis_period_start)} — ${formatDate(summary.analysis_period_end)}`}
        />
        <div className="flex items-center gap-3">
          {/* Lookback toggles */}
          <div className="flex gap-1">
            {[30, 60, 90, 180].map((d) => (
              <Button
                key={d}
                variant={lookbackDays === d ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => {
                  setLookbackDays(d);
                  setSelectedSku(null);
                }}
              >
                {d}d
              </Button>
            ))}
          </div>

          {/* Share via Email */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowEmailModal(true)}
          >
            <Mail className="w-4 h-4 mr-2" />
            Email
          </Button>

          {/* Export PDF */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => exportPdf(lookbackDays)}
            disabled={pdfLoading}
          >
            {pdfLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Download className="w-4 h-4 mr-2" />
            )}
            {pdfLoading ? 'Generating...' : 'Export PDF'}
          </Button>
        </div>
      </div>

      {/* Headline card */}
      <HeadlineCard
        totalImpact={summary.total_estimated_impact}
        lostRevenue={summary.total_lost_revenue}
        missedMargin={summary.total_missed_margin}
        monthlyLoss={summary.monthly_projected_loss}
        annualLoss={summary.annual_projected_loss}
        productsAnalyzed={summary.total_products_analyzed}
        lookbackDays={summary.lookback_days}
      />

      {/* Top loss products callout */}
      {summary.top_loss_products.length > 0 && (
        <Card className="p-4 bg-amber-50 border-amber-200">
          <p className="text-sm font-medium text-amber-800">
            Top impact products: {summary.top_loss_products.join(', ')}
          </p>
          <p className="text-xs text-amber-600 mt-1">
            On average, your products were overpriced for {summary.avg_days_overpriced} days
            {summary.avg_overpriced_gap_percent && (
              <> by {formatPercent(summary.avg_overpriced_gap_percent)}</>
            )}
          </p>
        </Card>
      )}

      {/* SKU table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3 text-right">Your Price</th>
                <th className="px-4 py-3 text-right">Competitor Avg</th>
                <th className="px-4 py-3 text-right">Gap</th>
                <th className="px-4 py-3 text-center">Over / Under / Aligned</th>
                <th className="px-4 py-3 text-right">Est. Impact</th>
              </tr>
            </thead>
            <tbody>
              {sku_results
                .sort((a, b) => parseFloat(b.total_estimated_impact) - parseFloat(a.total_estimated_impact))
                .map((sku) => (
                  <SKURow key={sku.product_id} sku={sku} onSelect={setSelectedSku} />
                ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Detail panel */}
      {selectedSku && (
        <SKUDetailPanel sku={selectedSku} onClose={() => setSelectedSku(null)} />
      )}

      {/* Methodology footer */}
      <p className="text-xs text-gray-400 leading-relaxed">{methodology}</p>

      {/* Email Modal */}
      {showEmailModal && (
        <EmailAuditModal
          lookbackDays={lookbackDays}
          onClose={() => setShowEmailModal(false)}
        />
      )}
    </div>
  );
}




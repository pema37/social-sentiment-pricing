/**
 * Retrospective Loss Audit Types
 *
 * Matches backend schemas/retrospective_audit.py
 */

// ════════════════════════════════════════════════
// REQUEST
// ════════════════════════════════════════════════

export interface AuditRequest {
  lookback_days?: number; // default 90
  product_ids?: string[];
  estimated_daily_units?: number;
  include_sentiment?: boolean;
}

// ════════════════════════════════════════════════
// PER-SKU DETAIL
// ════════════════════════════════════════════════

export interface PricingGapDay {
  date: string;
  your_price: string; // Decimal as string
  competitor_avg_price: string;
  optimal_price: string;
  gap_amount: string;
  gap_percent: string;
  gap_type: 'overpriced' | 'underpriced' | 'aligned';
}

export interface SKUAuditResult {
  product_id: string;
  product_name: string;
  sku: string | null;
  category: string | null;

  current_price: string;
  current_competitor_avg: string | null;
  current_gap_percent: string | null;

  competitor_count: number;
  competitor_names: string[];

  days_overpriced: number;
  avg_overpriced_gap_percent: string | null;
  estimated_lost_revenue: string;

  days_underpriced: number;
  avg_underpriced_gap_percent: string | null;
  estimated_missed_margin: string;

  days_aligned: number;
  total_estimated_impact: string;

  daily_gaps: PricingGapDay[];
}

// ════════════════════════════════════════════════
// SUMMARY
// ════════════════════════════════════════════════

export interface AuditSummary {
  total_products_analyzed: number;
  lookback_days: number;
  analysis_period_start: string;
  analysis_period_end: string;

  total_estimated_impact: string;
  total_lost_revenue: string;
  total_missed_margin: string;

  avg_days_overpriced: string;
  avg_days_underpriced: string;
  avg_overpriced_gap_percent: string | null;

  top_loss_products: string[];

  monthly_projected_loss: string;
  annual_projected_loss: string;
}

// ════════════════════════════════════════════════
// FULL RESPONSE
// ════════════════════════════════════════════════

export interface RetrospectiveAuditResponse {
  id: string;
  user_id: string;
  created_at: string;
  summary: AuditSummary;
  sku_results: SKUAuditResult[];
  methodology: string;
}

// ════════════════════════════════════════════════
// LIST
// ════════════════════════════════════════════════

export interface AuditListItem {
  id: string;
  created_at: string;
  lookback_days: number;
  total_products_analyzed: number;
  total_estimated_impact: string;
  monthly_projected_loss: string;
}

export interface AuditListResponse {
  items: AuditListItem[];
  total: number;
}




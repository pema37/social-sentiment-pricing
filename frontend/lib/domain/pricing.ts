// frontend/lib/domain/pricing.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type {
  PricingRule,
  CreatePricingRuleRequest,
  RuleType,
  RuleAction,
  PriceRecommendation,
  PricingSettings,
  RecommendationStatus,
} from '@/types';

// Import centralized error handling for API responses
export { parseApiError, getErrorMessage, isAuthError } from '@/lib/api/errors';

// ============================================
// ZOD SCHEMAS
// ============================================

/** Valid rule types */
const ruleTypes = [
  'sentiment_threshold',
  'competitor_relative',
  'time_based',
  'volume_surge',
  'viral_detection',
] as const;

/** Valid rule actions */
const ruleActions = [
  'increase_percent',
  'decrease_percent',
  'set_absolute',
  'match_competitor',
  'undercut_competitor',
] as const;

/** Actions that don't require a value input */
const ACTIONS_WITHOUT_VALUE: RuleAction[] = ['match_competitor'];

/**
 * Zod schema for validating a decimal string is valid
 */
const validDecimalString = z.string().refine((val) => {
  if (val === '') return true;
  let cleaned = val.trim().replace(/%/g, '');
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return true;
  return !isNaN(parseFloat(cleaned));
}, { message: 'Must be a valid number' });

/**
 * Form data schema - validates the raw form input
 */
export const ruleFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string(),
  rule_type: z.enum(ruleTypes),
  is_active: z.boolean(),
  priority: z.number().int().min(0).max(100),
  scope_type: z.enum(['single', 'multiple', 'categories', 'all']),
  product_id: z.string(),
  applies_to_products: z.array(z.string()),
  applies_to_categories: z.array(z.string()),
  sentiment_threshold: validDecimalString,
  sentiment_direction: z.string(),
  competitor_id: z.string(),
  price_position: z.string(),
  time_days: z.string(),
  volume_threshold: z.string(),
  viral_threshold_reach: z.string(),
  action: z.enum(ruleActions),
  action_value: z.string(),
  max_change_percent: validDecimalString,
  min_price: validDecimalString,
  max_price: validDecimalString,
  cooldown_hours: z.string(),
}).superRefine((data, ctx) => {
  if (data.scope_type === 'single' && !data.product_id) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Select a product', path: ['product_id'] });
  }
  if (data.scope_type === 'multiple' && data.applies_to_products.length === 0) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Select at least one product', path: ['applies_to_products'] });
  }
  if (data.scope_type === 'categories' && data.applies_to_categories.length === 0) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Select at least one category', path: ['applies_to_categories'] });
  }
  if (data.rule_type === 'sentiment_threshold' && !data.sentiment_threshold) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required', path: ['sentiment_threshold'] });
  }
  if (data.rule_type === 'time_based' && !data.time_days) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required', path: ['time_days'] });
  }
  if (data.rule_type === 'volume_surge' && !data.volume_threshold) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required', path: ['volume_threshold'] });
  }
  if (data.rule_type === 'viral_detection' && !data.viral_threshold_reach) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Required', path: ['viral_threshold_reach'] });
  }
  if (!ACTIONS_WITHOUT_VALUE.includes(data.action) && !data.action_value.trim()) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Action value is required', path: ['action_value'] });
  }
});

// ============================================
// TYPES
// ============================================

export type ScopeType = 'single' | 'multiple' | 'categories' | 'all';

export type RuleFormData = z.input<typeof ruleFormSchema>;

export type RuleFormErrors = Partial<Record<keyof RuleFormData, string>>;

// ============================================
// DECIMAL HANDLING UTILITIES
// ============================================

export function normalizeDecimal(value: string | number | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  if (typeof value === 'number') {
    if (isNaN(value)) return undefined;
    return value.toString();
  }
  let cleaned = value.toString().trim().replace(/%/g, '');
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return undefined;
  const num = parseFloat(cleaned);
  return isNaN(num) ? undefined : cleaned;
}

export function isValidDecimal(value: string | number | undefined | null): boolean {
  return normalizeDecimal(value) !== undefined;
}

export function parseInteger(value: string | number | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  if (typeof value === 'number') return isNaN(value) ? undefined : Math.floor(value);
  const num = parseInt(value.toString().trim(), 10);
  return isNaN(num) ? undefined : num;
}

export function decimalToFormString(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  return value.toString();
}

// ============================================
// TRANSFORMATIONS: API → Form
// ============================================

export const DEFAULT_FORM_DATA: RuleFormData = {
  name: '',
  description: '',
  rule_type: 'sentiment_threshold',
  is_active: true,
  priority: 10,
  scope_type: 'single',
  product_id: '',
  applies_to_products: [],
  applies_to_categories: [],
  sentiment_threshold: '',
  sentiment_direction: 'above',
  competitor_id: '',
  price_position: 'below',
  time_days: '',
  volume_threshold: '',
  viral_threshold_reach: '',
  action: 'increase_percent',
  action_value: '',
  max_change_percent: '',
  min_price: '',
  max_price: '',
  cooldown_hours: '24',
};

export function ruleToFormData(rule: Partial<PricingRule>): RuleFormData {
  const scopeType: ScopeType = rule.applies_to_all_products
    ? 'all'
    : rule.applies_to_categories?.length
      ? 'categories'
      : rule.applies_to_products?.length
        ? 'multiple'
        : 'single';

  return {
    name: rule.name ?? '',
    description: rule.description ?? '',
    rule_type: rule.rule_type ?? 'sentiment_threshold',
    is_active: rule.is_active ?? true,
    priority: rule.priority ?? 10,
    scope_type: scopeType,
    product_id: rule.product_id ?? '',
    applies_to_products: rule.applies_to_products ?? [],
    applies_to_categories: rule.applies_to_categories ?? [],
    sentiment_threshold: decimalToFormString(rule.sentiment_threshold),
    sentiment_direction: rule.sentiment_direction ?? 'above',
    competitor_id: rule.competitor_id ?? '',
    price_position: rule.price_position ?? 'below',
    time_days: rule.time_days ?? '',
    volume_threshold: decimalToFormString(rule.volume_threshold),
    viral_threshold_reach: decimalToFormString(rule.viral_threshold_reach),
    action: rule.action ?? 'increase_percent',
    action_value: decimalToFormString(rule.action_value),
    max_change_percent: decimalToFormString(rule.max_change_percent),
    min_price: decimalToFormString(rule.min_price),
    max_price: decimalToFormString(rule.max_price),
    cooldown_hours: rule.cooldown_hours?.toString() ?? '24',
  };
}

// ============================================
// TRANSFORMATIONS: Form → API
// ============================================

export function formDataToRequest(form: RuleFormData): CreatePricingRuleRequest {
  const actionValue = ACTIONS_WITHOUT_VALUE.includes(form.action)
    ? '0'
    : (normalizeDecimal(form.action_value) ?? '0');

  const payload: CreatePricingRuleRequest = {
    name: form.name.trim(),
    description: form.description.trim() || undefined,
    rule_type: form.rule_type,
    is_active: form.is_active,
    priority: form.priority,
    action: form.action,
    action_value: actionValue,
    cooldown_hours: parseInteger(form.cooldown_hours) ?? 24,
  };

  switch (form.scope_type) {
    case 'single':
      payload.product_id = form.product_id || undefined;
      payload.applies_to_all_products = false;
      break;
    case 'multiple':
      payload.applies_to_products = form.applies_to_products;
      payload.applies_to_all_products = false;
      break;
    case 'categories':
      payload.applies_to_categories = form.applies_to_categories;
      payload.applies_to_all_products = false;
      break;
    case 'all':
      payload.applies_to_all_products = true;
      break;
  }

  switch (form.rule_type) {
    case 'sentiment_threshold': {
      const threshold = normalizeDecimal(form.sentiment_threshold);
      payload.sentiment_threshold = threshold ? parseFloat(threshold) : undefined;
      payload.sentiment_direction = form.sentiment_direction || undefined;
      break;
    }
    case 'competitor_relative':
      payload.competitor_id = form.competitor_id || undefined;
      payload.price_position = form.price_position || undefined;
      break;
    case 'time_based':
      payload.time_days = form.time_days || undefined;
      break;
    case 'volume_surge':
      payload.volume_threshold = parseInteger(form.volume_threshold);
      break;
    case 'viral_detection':
      payload.viral_threshold_reach = parseInteger(form.viral_threshold_reach);
      break;
  }

  const maxChangePercent = normalizeDecimal(form.max_change_percent);
  const minPrice = normalizeDecimal(form.min_price);
  const maxPrice = normalizeDecimal(form.max_price);

  if (maxChangePercent !== undefined) payload.max_change_percent = maxChangePercent;
  if (minPrice !== undefined) payload.min_price = minPrice;
  if (maxPrice !== undefined) payload.max_price = maxPrice;

  return payload;
}

// ============================================
// VALIDATION
// ============================================

export function validateRuleForm(form: RuleFormData): RuleFormErrors {
  const result = ruleFormSchema.safeParse(form);
  if (result.success) return {};

  const errors: RuleFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof RuleFormData;
    if (path && !errors[path]) {
      errors[path] = issue.message;
    }
  }
  return errors;
}

export function isFormValid(form: RuleFormData): boolean {
  return ruleFormSchema.safeParse(form).success;
}

export function validateAndTransform(form: RuleFormData):
  | { success: true; data: CreatePricingRuleRequest }
  | { success: false; errors: RuleFormErrors } {
  const validation = ruleFormSchema.safeParse(form);
  if (!validation.success) {
    const errors: RuleFormErrors = {};
    for (const issue of validation.error.issues) {
      const path = issue.path[0] as keyof RuleFormData;
      if (path && !errors[path]) {
        errors[path] = issue.message;
      }
    }
    return { success: false, errors };
  }
  return { success: true, data: formDataToRequest(form) };
}

// ============================================
// LABEL MAPS — single source for all UI labels
// ============================================

export const RULE_TYPE_LABELS: Record<RuleType, string> = {
  sentiment_threshold: 'Sentiment Threshold',
  competitor_relative: 'Competitor Relative',
  time_based: 'Time-Based',
  volume_surge: 'Volume Surge',
  viral_detection: 'Viral Detection',
};

export const RULE_ACTION_LABELS: Record<RuleAction, string> = {
  increase_percent: 'Increase %',
  decrease_percent: 'Decrease %',
  set_absolute: 'Set Price',
  match_competitor: 'Match Competitor',
  undercut_competitor: 'Undercut Competitor',
};

export const RECOMMENDATION_STATUS_LABELS: Record<RecommendationStatus, string> = {
  pending: 'Pending Review',
  auto_approved: 'Auto-Approved',
  approved: 'Approved',
  rejected: 'Rejected',
  applied: 'Applied',
  expired: 'Expired',
};

// ============================================
// DISPLAY TYPES — what list/card components consume
// ============================================

export interface RuleDisplay {
  id: string;
  name: string;
  description: string;
  ruleType: RuleType;
  ruleTypeLabel: string;
  isActive: boolean;
  priority: number;
  action: RuleAction;
  actionLabel: string;
  actionValue: string;
  summary: string;
  constraintsSummary: string;
  scopeSummary: string;
  cooldownHours: number;
  createdAt: Date;
  updatedAt: Date;
  _raw: PricingRule;
}

export interface RecommendationDisplay {
  id: string;
  productId: string;
  ruleId: string | null;
  currentPrice: number;
  recommendedPrice: number;
  changePercent: number;
  changeDirection: 'up' | 'down' | 'flat';
  isAggressive: boolean;
  confidenceScore: number;
  confidenceLabel: 'low' | 'medium' | 'high';
  reasoning: string;
  factors: Record<string, unknown>;
  status: RecommendationStatus;
  statusLabel: string;
  requiresApproval: boolean;
  expiresAt: Date;
  createdAt: Date;
  _raw: PriceRecommendation;
}

// ============================================
// DISPLAY TRANSFORMS: API → Card/List props
// ============================================

export function toRuleDisplay(rule: PricingRule): RuleDisplay {
  return {
    id: rule.id,
    name: rule.name,
    description: rule.description ?? '',
    ruleType: rule.rule_type,
    ruleTypeLabel: RULE_TYPE_LABELS[rule.rule_type] ?? rule.rule_type,
    isActive: rule.is_active,
    priority: rule.priority,
    action: rule.action,
    actionLabel: RULE_ACTION_LABELS[rule.action] ?? rule.action,
    actionValue: rule.action_value,
    summary: buildRuleSummary(rule),
    constraintsSummary: buildConstraintsSummary(rule),
    scopeSummary: buildScopeSummary(rule),
    cooldownHours: rule.cooldown_hours,
    createdAt: new Date(rule.created_at),
    updatedAt: new Date(rule.updated_at),
    _raw: rule,
  };
}

export function toRecommendationDisplay(rec: PriceRecommendation): RecommendationDisplay {
  const current = parseFloat(rec.current_price);
  const recommended = parseFloat(rec.recommended_price);
  const pct = rec.change_percent;

  return {
    id: rec.id,
    productId: rec.product_id,
    ruleId: rec.rule_id,
    currentPrice: current,
    recommendedPrice: recommended,
    changePercent: pct,
    changeDirection: pct > 0.1 ? 'up' : pct < -0.1 ? 'down' : 'flat',
    isAggressive: Math.abs(pct) > 10,
    confidenceScore: rec.confidence_score,
    confidenceLabel:
      rec.confidence_score >= 0.8 ? 'high' :
      rec.confidence_score >= 0.5 ? 'medium' : 'low',
    reasoning: rec.reasoning,
    factors: rec.factors,
    status: rec.status,
    statusLabel: RECOMMENDATION_STATUS_LABELS[rec.status] ?? rec.status,
    requiresApproval: rec.requires_approval,
    expiresAt: new Date(rec.expires_at),
    createdAt: new Date(rec.created_at),
    _raw: rec,
  };
}

// ============================================
// SETTINGS TRANSFORMS
// Matches actual PricingSettings type from types/pricing.ts
// ============================================

export interface SettingsFormValues {
  autoApproveEnabled: boolean;
  autoApproveMaxIncrease: number;
  autoApproveMaxDecrease: number;
  autoApproveMinConfidence: number;
  minMarginPercent: number;
  maxAutoChangesPerDay: number;
  globalCooldownHours: number;
  blackoutHoursStart: number | null;
  blackoutHoursEnd: number | null;
  requireApprovalAbovePrice: number | null;
  recommendationValidHours: number;
  notifyOnAutoApply: boolean;
  notifyOnPending: boolean;
  notificationEmail: string;
  notificationSlackWebhook: string;
}

export function settingsToForm(s: PricingSettings): SettingsFormValues {
  return {
    autoApproveEnabled: s.auto_approve_enabled,
    autoApproveMaxIncrease: s.auto_approve_max_increase,
    autoApproveMaxDecrease: s.auto_approve_max_decrease,
    autoApproveMinConfidence: s.auto_approve_min_confidence,
    minMarginPercent: s.min_margin_percent,
    maxAutoChangesPerDay: s.max_auto_changes_per_day,
    globalCooldownHours: s.global_cooldown_hours,
    blackoutHoursStart: s.blackout_hours_start,
    blackoutHoursEnd: s.blackout_hours_end,
    requireApprovalAbovePrice: s.require_approval_above_price,
    recommendationValidHours: s.recommendation_valid_hours,
    notifyOnAutoApply: s.notify_on_auto_apply,
    notifyOnPending: s.notify_on_pending,
    notificationEmail: s.notification_email ?? '',
    notificationSlackWebhook: s.notification_slack_webhook ?? '',
  };
}

export function formToSettingsPayload(form: SettingsFormValues) {
  return {
    auto_approve_enabled: form.autoApproveEnabled,
    auto_approve_max_increase: form.autoApproveMaxIncrease,
    auto_approve_max_decrease: form.autoApproveMaxDecrease,
    auto_approve_min_confidence: form.autoApproveMinConfidence,
    min_margin_percent: form.minMarginPercent,
    max_auto_changes_per_day: form.maxAutoChangesPerDay,
    global_cooldown_hours: form.globalCooldownHours,
    blackout_hours_start: form.blackoutHoursStart,
    blackout_hours_end: form.blackoutHoursEnd,
    require_approval_above_price: form.requireApprovalAbovePrice,
    recommendation_valid_hours: form.recommendationValidHours,
    notify_on_auto_apply: form.notifyOnAutoApply,
    notify_on_pending: form.notifyOnPending,
    notification_email: form.notificationEmail || null,
    notification_slack_webhook: form.notificationSlackWebhook || null,
  };
}

// ============================================
// PRIVATE HELPERS
// ============================================

function buildRuleSummary(rule: PricingRule): string {
  const action = RULE_ACTION_LABELS[rule.action] ?? rule.action;
  const val = rule.action_value;

  switch (rule.rule_type) {
    case 'sentiment_threshold':
      return `${action} ${val}% when sentiment ${rule.sentiment_direction ?? '>'} ${rule.sentiment_threshold ?? '0'}`;
    case 'competitor_relative':
      return `${action} ${val}% based on competitor pricing`;
    case 'time_based':
      return `${action} ${val}% after ${rule.time_days ?? 0} days`;
    case 'volume_surge':
      return `${action} ${val}% when volume exceeds ${rule.volume_threshold ?? 0}`;
    case 'viral_detection':
      return `${action} ${val}% when reach exceeds ${rule.viral_threshold_reach ?? 0}`;
    default:
      return `${action} ${val}%`;
  }
}

function buildConstraintsSummary(rule: PricingRule): string {
  const parts: string[] = [];
  if (rule.max_change_percent) parts.push(`Max ±${rule.max_change_percent}%`);
  if (rule.min_price) parts.push(`Floor $${rule.min_price}`);
  if (rule.max_price) parts.push(`Ceiling $${rule.max_price}`);
  if (rule.cooldown_hours > 0) parts.push(`${rule.cooldown_hours}h cooldown`);
  return parts.length > 0 ? parts.join(' · ') : 'No constraints';
}

function buildScopeSummary(rule: PricingRule): string {
  if (rule.applies_to_all_products) return 'All products';

  const products = rule.applies_to_products?.length ?? 0;
  const categories = rule.applies_to_categories?.length ?? 0;

  if (products === 0 && categories === 0) {
    return rule.product_id ? '1 product' : 'All products';
  }

  const parts: string[] = [];
  if (products > 0) parts.push(`${products} product${products > 1 ? 's' : ''}`);
  if (categories > 0) parts.push(`${categories} categor${categories > 1 ? 'ies' : 'y'}`);
  return parts.join(', ');
}


import { describe, it, expect } from 'vitest';
import {
  ruleToFormData,
  formDataToRequest,
  validateAndTransform,
  validateRuleForm,
  isFormValid,
  DEFAULT_FORM_DATA,
  normalizeDecimal,
  parseInteger,
  decimalToFormString,
  isValidDecimal,
  toRuleDisplay,
  toRecommendationDisplay,
  RULE_TYPE_LABELS,
  RULE_ACTION_LABELS,
  RECOMMENDATION_STATUS_LABELS,
} from '@/lib/domain/pricing';

import type { PricingRule, PriceRecommendation } from '@/types';

// ─── FIXTURES ───

const mockRule: PricingRule = {
  id: 'rule-1',
  user_id: 'user-1',
  name: 'Sentiment Boost',
  description: 'Increase when sentiment is high',
  rule_type: 'sentiment_threshold',
  is_active: true,
  priority: 50,
  product_id: '',
  applies_to_all_products: false,
  applies_to_products: ['prod-1', 'prod-2'],
  applies_to_categories: [],
  sentiment_threshold: '0.7',
  sentiment_direction: 'above',
  competitor_id: null,
  competitor_margin_percent: null,
  price_position: null,
  time_days: null,
  time_start: null,
  time_end: null,
  volume_threshold: null,
  volume_window_hours: null,
  viral_threshold_reach: null,
  viral_threshold_engagement: null,
  viral_sentiment_min: null,
  action: 'increase_percent',
  action_value: '5',
  max_change_percent: '10',
  min_price: '5.00',
  max_price: '100.00',
  cooldown_hours: 24,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-16T12:00:00Z',
};

const mockRecommendation: PriceRecommendation = {
  id: 'rec-1',
  user_id: 'user-1',
  product_id: 'prod-1',
  rule_id: 'rule-1',
  current_price: '29.99',
  recommended_price: '31.49',
  change_percent: 5.0,
  confidence_score: 0.85,
  reasoning: 'Positive sentiment detected',
  factors: { sentiment: 0.8 },
  status: 'pending',
  requires_approval: true,
  reviewed_by: null,
  reviewed_at: null,
  rejection_reason: null,
  applied_at: null,
  applied_to_platform: null,
  expires_at: '2026-01-20T10:00:00Z',
  created_at: '2026-01-15T10:00:00Z',
};

// ════════════════════════════════════════
// DECIMAL UTILITIES
// ════════════════════════════════════════

describe('normalizeDecimal', () => {
  it('handles normal numbers', () => {
    expect(normalizeDecimal('5.5')).toBe('5.5');
    expect(normalizeDecimal('100')).toBe('100');
    expect(normalizeDecimal('-3.14')).toBe('-3.14');
  });

  it('handles edge cases', () => {
    expect(normalizeDecimal('.5')).toBe('0.5');
    expect(normalizeDecimal('-.5')).toBe('-0.5');
    expect(normalizeDecimal('5%')).toBe('5');
    expect(normalizeDecimal(' 10.5 ')).toBe('10.5');
  });

  it('returns undefined for empty/invalid', () => {
    expect(normalizeDecimal('')).toBeUndefined();
    expect(normalizeDecimal(undefined)).toBeUndefined();
    expect(normalizeDecimal(null)).toBeUndefined();
    expect(normalizeDecimal('abc')).toBeUndefined();
    expect(normalizeDecimal('-')).toBeUndefined();
  });

  it('handles numeric input', () => {
    expect(normalizeDecimal(42)).toBe('42');
    expect(normalizeDecimal(0)).toBe('0');
    expect(normalizeDecimal(NaN)).toBeUndefined();
  });
});

describe('parseInteger', () => {
  it('parses valid integers', () => {
    expect(parseInteger('24')).toBe(24);
    expect(parseInteger('0')).toBe(0);
    expect(parseInteger(10)).toBe(10);
  });

  it('floors decimals', () => {
    expect(parseInteger(10.7)).toBe(10);
  });

  it('returns undefined for invalid', () => {
    expect(parseInteger('')).toBeUndefined();
    expect(parseInteger(undefined)).toBeUndefined();
    expect(parseInteger('abc')).toBeUndefined();
  });
});

describe('decimalToFormString', () => {
  it('converts values to form strings', () => {
    expect(decimalToFormString('5.00')).toBe('5.00');
    expect(decimalToFormString(10)).toBe('10');
    expect(decimalToFormString(null)).toBe('');
    expect(decimalToFormString(undefined)).toBe('');
  });
});

describe('isValidDecimal', () => {
  it('validates correctly', () => {
    expect(isValidDecimal('5.5')).toBe(true);
    expect(isValidDecimal('.5')).toBe(true);
    expect(isValidDecimal('abc')).toBe(false);
    expect(isValidDecimal(undefined)).toBe(false);
  });
});

// ════════════════════════════════════════
// ruleToFormData — API → Form
// ════════════════════════════════════════

describe('ruleToFormData', () => {
  it('transforms API rule to form data', () => {
    const form = ruleToFormData(mockRule);

    expect(form.name).toBe('Sentiment Boost');
    expect(form.rule_type).toBe('sentiment_threshold');
    expect(form.is_active).toBe(true);
    expect(form.priority).toBe(50);
    expect(form.action).toBe('increase_percent');
    expect(form.action_value).toBe('5');
    expect(form.cooldown_hours).toBe('24');
  });

  it('detects scope_type from applies_to fields', () => {
    expect(ruleToFormData(mockRule).scope_type).toBe('multiple');

    expect(ruleToFormData({ ...mockRule, applies_to_all_products: true }).scope_type).toBe('all');

    expect(ruleToFormData({
      ...mockRule,
      applies_to_products: [],
      applies_to_categories: ['electronics'],
    }).scope_type).toBe('categories');

    expect(ruleToFormData({
      ...mockRule,
      applies_to_products: [],
      applies_to_categories: [],
    }).scope_type).toBe('single');
  });

  it('converts null API values to empty form strings', () => {
    const form = ruleToFormData({
      ...mockRule,
      sentiment_threshold: null,
      max_change_percent: null,
      min_price: null,
    } as unknown as PricingRule);

    expect(form.sentiment_threshold).toBe('');
    expect(form.max_change_percent).toBe('');
    expect(form.min_price).toBe('');
  });

  it('handles partial input for create mode', () => {
    const form = ruleToFormData({});
    expect(form.name).toBe('');
    expect(form.rule_type).toBe('sentiment_threshold');
    expect(form.is_active).toBe(true);
    expect(form.cooldown_hours).toBe('24');
  });
});

// ════════════════════════════════════════
// formDataToRequest — Form → API
// ════════════════════════════════════════

describe('formDataToRequest', () => {
  it('converts form data to API payload', () => {
    const form = ruleToFormData(mockRule);
    const payload = formDataToRequest(form);

    expect(payload.name).toBe('Sentiment Boost');
    expect(payload.rule_type).toBe('sentiment_threshold');
    expect(payload.action).toBe('increase_percent');
    expect(payload.action_value).toBe('5');
    expect(payload.cooldown_hours).toBe(24);
  });

  it('strips empty optional fields', () => {
    const payload = formDataToRequest(DEFAULT_FORM_DATA);

    expect(payload.description).toBeUndefined();
    expect(payload.competitor_id).toBeUndefined();
    expect(payload.max_change_percent).toBeUndefined();
  });

  it('handles scope_type → applies_to mapping', () => {
    const allPayload = formDataToRequest({ ...DEFAULT_FORM_DATA, scope_type: 'all' });
    expect(allPayload.applies_to_all_products).toBe(true);

    const singlePayload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      scope_type: 'single',
      product_id: 'prod-1',
    });
    expect(singlePayload.product_id).toBe('prod-1');
    expect(singlePayload.applies_to_all_products).toBe(false);

    const multiPayload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      scope_type: 'multiple',
      applies_to_products: ['prod-1', 'prod-2'],
    });
    expect(multiPayload.applies_to_products).toEqual(['prod-1', 'prod-2']);

    const catPayload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      scope_type: 'categories',
      applies_to_categories: ['electronics'],
    });
    expect(catPayload.applies_to_categories).toEqual(['electronics']);
  });

  it('handles rule-type-specific fields', () => {
    const sentimentPayload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      rule_type: 'sentiment_threshold',
      sentiment_threshold: '0.7',
      sentiment_direction: 'above',
    });
    expect(sentimentPayload.sentiment_threshold).toBe(0.7);
    expect(sentimentPayload.sentiment_direction).toBe('above');

    const volumePayload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      rule_type: 'volume_surge',
      volume_threshold: '500',
    });
    expect(volumePayload.volume_threshold).toBe(500);
  });

  it('sets action_value to "0" for match_competitor', () => {
    const payload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      action: 'match_competitor',
      action_value: '',
    });
    expect(payload.action_value).toBe('0');
  });

  it('includes constraints when present', () => {
    const payload = formDataToRequest({
      ...DEFAULT_FORM_DATA,
      max_change_percent: '10',
      min_price: '5.00',
      max_price: '99.99',
    });
    expect(payload.max_change_percent).toBe('10');
    expect(payload.min_price).toBe('5.00');
    expect(payload.max_price).toBe('99.99');
  });
});

// ════════════════════════════════════════
// VALIDATION
// ════════════════════════════════════════

describe('validateRuleForm', () => {
  it('returns empty errors for valid form', () => {
    const validForm = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      sentiment_threshold: '0.7',
      action_value: '5',
      scope_type: 'all' as const,
    };
    expect(validateRuleForm(validForm)).toEqual({});
  });

  it('returns error for missing name', () => {
    const errors = validateRuleForm({ ...DEFAULT_FORM_DATA, name: '' });
    expect(errors.name).toBeDefined();
  });

  it('validates conditional fields per rule_type', () => {
    const errors = validateRuleForm({
      ...DEFAULT_FORM_DATA,
      name: 'Test',
      rule_type: 'sentiment_threshold',
      sentiment_threshold: '',
      action_value: '5',
    });
    expect(errors.sentiment_threshold).toBeDefined();
  });

  it('requires action_value for non-match actions', () => {
    const errors = validateRuleForm({
      ...DEFAULT_FORM_DATA,
      name: 'Test',
      action: 'increase_percent',
      action_value: '',
    });
    expect(errors.action_value).toBeDefined();
  });

  it('does not require action_value for match_competitor', () => {
    const errors = validateRuleForm({
      ...DEFAULT_FORM_DATA,
      name: 'Test',
      sentiment_threshold: '0.5',
      action: 'match_competitor',
      action_value: '',
    });
    expect(errors.action_value).toBeUndefined();
  });
});

describe('validateAndTransform', () => {
  it('returns success with API payload for valid form', () => {
    const result = validateAndTransform({
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      sentiment_threshold: '0.7',
      action_value: '5',
      scope_type: 'all' as const,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Test Rule');
      expect(result.data.action_value).toBe('5');
    }
  });

  it('returns failure with errors for invalid form', () => {
    const result = validateAndTransform({
      ...DEFAULT_FORM_DATA,
      name: '',
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.name).toBeDefined();
    }
  });
});

describe('isFormValid', () => {
  it('returns true for valid form', () => {
    expect(isFormValid({
      ...DEFAULT_FORM_DATA,
      name: 'Test',
      sentiment_threshold: '0.7',
      action_value: '5',
      scope_type: 'all' as const,
    })).toBe(true);
  });

  it('returns false for invalid form', () => {
    expect(isFormValid({ ...DEFAULT_FORM_DATA, name: '' })).toBe(false);
  });
});

// ════════════════════════════════════════
// DISPLAY TRANSFORMS
// ════════════════════════════════════════

describe('toRuleDisplay', () => {
  it('transforms rule to display shape', () => {
    const display = toRuleDisplay(mockRule);

    expect(display.id).toBe('rule-1');
    expect(display.ruleTypeLabel).toBe('Sentiment Threshold');
    expect(display.actionLabel).toBe('Increase %');
    expect(display.isActive).toBe(true);
    expect(display.createdAt).toBeInstanceOf(Date);
  });

  it('generates human-readable summary', () => {
    const display = toRuleDisplay(mockRule);
    expect(display.summary).toContain('Increase');
    expect(display.summary).toContain('5%');
    expect(display.summary).toContain('sentiment');
  });

  it('generates constraints summary', () => {
    const display = toRuleDisplay(mockRule);
    expect(display.constraintsSummary).toContain('Max ±10%');
    expect(display.constraintsSummary).toContain('Floor $5.00');
    expect(display.constraintsSummary).toContain('Ceiling $100.00');
    expect(display.constraintsSummary).toContain('24h cooldown');
  });

  it('generates scope summary', () => {
    expect(toRuleDisplay(mockRule).scopeSummary).toBe('2 products');

    const allProducts = { ...mockRule, applies_to_all_products: true };
    expect(toRuleDisplay(allProducts).scopeSummary).toBe('All products');

    const withCategories = {
      ...mockRule,
      applies_to_products: [],
      applies_to_categories: ['electronics', 'clothing'],
    };
    expect(toRuleDisplay(withCategories).scopeSummary).toBe('2 categories');
  });

  it('handles null description', () => {
    const noDesc = { ...mockRule, description: null } as unknown as PricingRule;
    expect(toRuleDisplay(noDesc).description).toBe('');
  });

  it('preserves raw rule via _raw', () => {
    expect(toRuleDisplay(mockRule)._raw).toBe(mockRule);
  });
});

describe('toRecommendationDisplay', () => {
  it('transforms recommendation to display shape', () => {
    const display = toRecommendationDisplay(mockRecommendation);

    expect(display.currentPrice).toBe(29.99);
    expect(display.recommendedPrice).toBe(31.49);
    expect(display.changeDirection).toBe('up');
    expect(display.isAggressive).toBe(false);
    expect(display.confidenceLabel).toBe('high');
    expect(display.statusLabel).toBe('Pending Review');
  });

  it('flags aggressive changes > 10%', () => {
    const aggressive = { ...mockRecommendation, change_percent: 15.0 };
    expect(toRecommendationDisplay(aggressive).isAggressive).toBe(true);
  });

  it('categorizes confidence levels', () => {
    expect(toRecommendationDisplay({ ...mockRecommendation, confidence_score: 0.9 }).confidenceLabel).toBe('high');
    expect(toRecommendationDisplay({ ...mockRecommendation, confidence_score: 0.6 }).confidenceLabel).toBe('medium');
    expect(toRecommendationDisplay({ ...mockRecommendation, confidence_score: 0.3 }).confidenceLabel).toBe('low');
  });

  it('detects change direction', () => {
    expect(toRecommendationDisplay({ ...mockRecommendation, change_percent: 5 }).changeDirection).toBe('up');
    expect(toRecommendationDisplay({ ...mockRecommendation, change_percent: -5 }).changeDirection).toBe('down');
    expect(toRecommendationDisplay({ ...mockRecommendation, change_percent: 0 }).changeDirection).toBe('flat');
  });
});

// ════════════════════════════════════════
// LABEL MAPS
// ════════════════════════════════════════

describe('Label maps', () => {
  it('covers all rule types', () => {
    expect(Object.keys(RULE_TYPE_LABELS)).toHaveLength(5);
    expect(RULE_TYPE_LABELS.sentiment_threshold).toBe('Sentiment Threshold');
  });

  it('covers all rule actions', () => {
    expect(Object.keys(RULE_ACTION_LABELS)).toHaveLength(5);
    expect(RULE_ACTION_LABELS.match_competitor).toBe('Match Competitor');
  });

  it('covers all recommendation statuses', () => {
    expect(Object.keys(RECOMMENDATION_STATUS_LABELS)).toHaveLength(6);
    expect(RECOMMENDATION_STATUS_LABELS.pending).toBe('Pending Review');
  });
});



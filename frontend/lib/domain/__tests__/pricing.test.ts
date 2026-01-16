import { describe, it, expect } from 'vitest';
import {
  normalizeDecimal,
  decimalToFormString,
  parseInteger,
  ruleToFormData,
  formDataToRequest,
  validateRuleForm,
  DEFAULT_FORM_DATA,
} from '../pricing';

describe('normalizeDecimal', () => {
  it('handles empty values', () => {
    expect(normalizeDecimal('')).toBeUndefined();
    expect(normalizeDecimal(null)).toBeUndefined();
    expect(normalizeDecimal(undefined)).toBeUndefined();
  });

  it('normalizes leading decimal point', () => {
    expect(normalizeDecimal('.5')).toBe('0.5');
    expect(normalizeDecimal('.00')).toBe('0.00');
    expect(normalizeDecimal('.123')).toBe('0.123');
  });

  it('normalizes negative leading decimal', () => {
    expect(normalizeDecimal('-.5')).toBe('-0.5');
  });

  it('strips percentage signs', () => {
    expect(normalizeDecimal('5%')).toBe('5');
    expect(normalizeDecimal('10.5%')).toBe('10.5');
  });

  it('handles numbers', () => {
    expect(normalizeDecimal(5)).toBe('5');
    expect(normalizeDecimal(0)).toBe('0');
    expect(normalizeDecimal(10.5)).toBe('10.5');
  });

  it('handles valid strings', () => {
    expect(normalizeDecimal('5')).toBe('5');
    expect(normalizeDecimal('10.00')).toBe('10.00');
    expect(normalizeDecimal('  5.5  ')).toBe('5.5');
  });

  it('returns undefined for invalid input', () => {
    expect(normalizeDecimal('abc')).toBeUndefined();
    expect(normalizeDecimal('-')).toBeUndefined();
    expect(normalizeDecimal(NaN)).toBeUndefined();
  });
});

describe('decimalToFormString', () => {
  it('converts null/undefined to empty string', () => {
    expect(decimalToFormString(null)).toBe('');
    expect(decimalToFormString(undefined)).toBe('');
  });

  it('converts values to strings', () => {
    expect(decimalToFormString('5.00')).toBe('5.00');
    expect(decimalToFormString(10)).toBe('10');
    expect(decimalToFormString(0)).toBe('0');
  });
});

describe('parseInteger', () => {
  it('handles empty values', () => {
    expect(parseInteger('')).toBeUndefined();
    expect(parseInteger(null)).toBeUndefined();
    expect(parseInteger(undefined)).toBeUndefined();
  });

  it('parses valid integers', () => {
    expect(parseInteger('10')).toBe(10);
    expect(parseInteger('0')).toBe(0);
    expect(parseInteger(5)).toBe(5);
  });

  it('floors decimal numbers', () => {
    expect(parseInteger(5.9)).toBe(5);
    expect(parseInteger('5.9')).toBe(5);
  });

  it('returns undefined for invalid input', () => {
    expect(parseInteger('abc')).toBeUndefined();
    expect(parseInteger(NaN)).toBeUndefined();
  });
});

describe('validateRuleForm', () => {
  it('requires name', () => {
    const form = { ...DEFAULT_FORM_DATA, name: '' };
    const errors = validateRuleForm(form);
    expect(errors.name).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      action_value: '5',
    };
    const errors = validateRuleForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('requires product_id for single scope', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      scope_type: 'single' as const,
      product_id: '',
      action_value: '5',
    };
    const errors = validateRuleForm(form);
    expect(errors.product_id).toBeDefined();
  });

  it('requires action_value for most actions', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      action: 'increase_percent' as const,
      action_value: '',
    };
    const errors = validateRuleForm(form);
    expect(errors.action_value).toBeDefined();
  });
});

describe('formDataToRequest', () => {
  it('normalizes decimal fields', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      action_value: '.5',
      max_change_percent: '10%',
    };
    const request = formDataToRequest(form);
    expect(request.action_value).toBe('0.5');
    expect(request.max_change_percent).toBe('10');
  });

  it('sets applies_to_all_products for all scope', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      scope_type: 'all' as const,
      action_value: '5',
    };
    const request = formDataToRequest(form);
    expect(request.applies_to_all_products).toBe(true);
  });

  it('includes product_id for single scope', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      scope_type: 'single' as const,
      product_id: 'prod-123',
      action_value: '5',
    };
    const request = formDataToRequest(form);
    expect(request.product_id).toBe('prod-123');
    expect(request.applies_to_all_products).toBe(false);
  });

  it('parses cooldown_hours as integer', () => {
    const form = {
      ...DEFAULT_FORM_DATA,
      name: 'Test Rule',
      action_value: '5',
      cooldown_hours: '48',
    };
    const request = formDataToRequest(form);
    expect(request.cooldown_hours).toBe(48);
  });
});

describe('ruleToFormData', () => {
  it('handles empty/partial rule', () => {
    const form = ruleToFormData({});
    expect(form.name).toBe('');
    expect(form.is_active).toBe(true);
    expect(form.priority).toBe(10);
  });

  it('determines scope_type from rule fields', () => {
    expect(ruleToFormData({ applies_to_all_products: true }).scope_type).toBe('all');
    expect(ruleToFormData({ applies_to_categories: ['cat-1'] }).scope_type).toBe('categories');
    expect(ruleToFormData({ applies_to_products: ['prod-1', 'prod-2'] }).scope_type).toBe('multiple');
    expect(ruleToFormData({ product_id: 'prod-1' }).scope_type).toBe('single');
  });

  it('converts decimal fields to strings', () => {
    const form = ruleToFormData({
      sentiment_threshold: '0.5',
      max_change_percent: '10.00',
    });
    expect(form.sentiment_threshold).toBe('0.5');
    expect(form.max_change_percent).toBe('10.00');
  });
});



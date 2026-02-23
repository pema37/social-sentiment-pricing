// frontend/lib/domain/__tests__/pricing-transformers.test.ts

import { describe, it, expect } from 'vitest';
import {
  ruleToFormData,
  validateAndTransform,
  DEFAULT_FORM_DATA,
  type RuleFormData,
} from '@/lib/domain/pricing';
import type { RuleType } from '@/types';

describe('Pricing Domain Transformers', () => {
  describe('ruleToFormData', () => {
    it('converts API rule to form data', () => {
      const apiRule = {
        id: 'rule-001',
        name: 'Test Rule',
        rule_type: 'sentiment_threshold',
        action: 'increase_percent',
        action_value: '5.0',
        is_active: true,
        priority: 0,
        sentiment_threshold: '0.5',
        sentiment_direction: 'above',
        max_change_percent: '10.0',
        min_price: null,
        max_price: null,
        cooldown_hours: 24,
        applies_to_products: [],
        applies_to_categories: [],
      };

      const result = ruleToFormData(apiRule as Partial<import('@/types').PricingRule>);

      expect(result.name).toBe('Test Rule');
      expect(result.rule_type).toBe('sentiment_threshold');
      expect(result.action).toBe('increase_percent');
      expect(result.is_active).toBe(true);
    });

    it('handles null and missing fields gracefully', () => {
      const minimal = {
        name: 'Minimal',
        rule_type: 'competitor_relative' as RuleType,
        action: 'match_competitor' as const,
      };

      const result = ruleToFormData(minimal as Partial<import('@/types').PricingRule>);
      
      expect(result.name).toBe('Minimal');
      expect(result.rule_type).toBe('competitor_relative');
    });

    it('handles empty object without crashing', () => {
      const result = ruleToFormData({});
      expect(result).toBeDefined();
    });
  });

  describe('DEFAULT_FORM_DATA', () => {
    it('has all required fields', () => {
      expect(DEFAULT_FORM_DATA).toHaveProperty('name');
      expect(DEFAULT_FORM_DATA).toHaveProperty('rule_type');
      expect(DEFAULT_FORM_DATA).toHaveProperty('action');
      expect(DEFAULT_FORM_DATA).toHaveProperty('is_active');
      expect(DEFAULT_FORM_DATA).toHaveProperty('cooldown_hours');
    });

    it('defaults are sensible', () => {
      expect(DEFAULT_FORM_DATA.is_active).toBe(true);
      expect(DEFAULT_FORM_DATA.cooldown_hours).toBeTruthy();
      expect(DEFAULT_FORM_DATA.name).toBe('');
    });
  });

  describe('validateAndTransform', () => {
    it('accepts valid form data', () => {
      const valid: RuleFormData = {
        ...DEFAULT_FORM_DATA,
        name: 'Valid Rule',
        rule_type: 'sentiment_threshold',
        action: 'increase_percent',
        action_value: '5.0',
        scope_type: 'all',
        sentiment_threshold: '0.5',
        sentiment_direction: 'above',
      };

      const result = validateAndTransform(valid);
      expect(result.success).toBe(true);
    });

    it('rejects empty name', () => {
      const invalid: RuleFormData = {
        ...DEFAULT_FORM_DATA,
        name: '',
        rule_type: 'sentiment_threshold',
        action: 'increase_percent',
        action_value: '5.0',
      };

      const result = validateAndTransform(invalid);
      expect(result.success).toBe(false);
    });
  });
});



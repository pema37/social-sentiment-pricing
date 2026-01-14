// frontend/lib/domain/pricing.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import type { PricingRule, CreatePricingRuleRequest, RuleType, RuleAction } from '@/types';

// ============================================
// FORM DATA TYPES (UI layer)
// ============================================

export type ScopeType = 'single' | 'multiple' | 'categories' | 'all';

/** What the form works with - all strings for input fields */
export interface RuleFormData {
  name: string;
  description: string;
  rule_type: RuleType;
  is_active: boolean;
  priority: number;
  scope_type: ScopeType;
  product_id: string;
  applies_to_products: string[];
  applies_to_categories: string[];
  sentiment_threshold: string;
  sentiment_direction: string;
  competitor_id: string;
  price_position: string;
  time_days: string;
  volume_threshold: string;
  viral_threshold_reach: string;
  action: RuleAction;
  action_value: string;
  max_change_percent: string;
  min_price: string;
  max_price: string;
  cooldown_hours: string;
}

export type RuleFormErrors = Partial<Record<keyof RuleFormData, string>>;

// ============================================
// DECIMAL HANDLING
// Backend uses Pydantic Decimal, returns strings
// Frontend forms use strings, API accepts number | string
// ============================================

/**
 * Normalize a string to a valid decimal string for the API
 * - Handles empty strings → undefined
 * - Handles ".5" → "0.5" (Pydantic requires leading zero)
 * - Handles "5%" → "5" (strips % sign)
 * - Returns undefined for invalid values
 */
export function normalizeDecimal(value: string | number | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  // If already a number, convert to string
  if (typeof value === 'number') {
    if (isNaN(value)) return undefined;
    return value.toString();
  }

  // Remove % sign if present (user might type "5%")
  let cleaned = value.toString().trim().replace(/%/g, '');

  // Handle ".5" → "0.5" (required by Pydantic Decimal)
  if (cleaned.startsWith('.')) {
    cleaned = '0' + cleaned;
  }

  // Handle "-.5" → "-0.5"
  if (cleaned.startsWith('-.')) {
    cleaned = '-0' + cleaned.substring(1);
  }

  // Handle empty after cleanup
  if (cleaned === '' || cleaned === '-') {
    return undefined;
  }

  // Validate it's a valid number
  const num = parseFloat(cleaned);
  if (isNaN(num)) {
    return undefined;
  }

  return cleaned;
}

/**
 * Check if a value represents a valid decimal
 */
export function isValidDecimal(value: string | number | undefined | null): boolean {
  return normalizeDecimal(value) !== undefined;
}

/**
 * Parse string to integer, handling edge cases
 */
export function parseInteger(value: string | number | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  if (typeof value === 'number') {
    return isNaN(value) ? undefined : Math.floor(value);
  }

  const num = parseInt(value.toString().trim(), 10);
  return isNaN(num) ? undefined : num;
}

/**
 * Convert API decimal (string | null) to form string
 */
export function decimalToFormString(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  return value.toString();
}

// ============================================
// TRANSFORMATIONS: API → Form
// ============================================

/** Default form data for new rules */
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

/**
 * Transform API PricingRule response to form data
 * Use when editing an existing rule
 */
export function ruleToFormData(rule: Partial<PricingRule>): RuleFormData {
  // Determine scope type from API data
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

/** Actions that don't require a value input */
const ACTIONS_WITHOUT_VALUE: RuleAction[] = ['match_competitor'];

/**
 * Transform form data to API request payload
 * Use when creating or updating a rule
 */
export function formDataToRequest(form: RuleFormData): CreatePricingRuleRequest {
  // Handle action value - some actions don't need it
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

  // Scoping
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

  // Rule type-specific fields
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

  // Constraints - only include if provided
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

/**
 * Validate form data and return errors
 * Returns empty object if valid
 */
export function validateRuleForm(form: RuleFormData): RuleFormErrors {
  const errors: RuleFormErrors = {};

  // Required fields
  if (!form.name.trim()) {
    errors.name = 'Name is required';
  }

  // Action value - required for most actions
  if (!ACTIONS_WITHOUT_VALUE.includes(form.action)) {
    if (!form.action_value.trim()) {
      errors.action_value = 'Action value is required';
    } else if (!isValidDecimal(form.action_value)) {
      errors.action_value = 'Must be a valid number';
    }
  }

  // Decimal field validation
  if (form.max_change_percent && !isValidDecimal(form.max_change_percent)) {
    errors.max_change_percent = 'Must be a valid number (e.g., 5 or 5.5)';
  }
  if (form.min_price && !isValidDecimal(form.min_price)) {
    errors.min_price = 'Must be a valid price (e.g., 0.00 or 10.99)';
  }
  if (form.max_price && !isValidDecimal(form.max_price)) {
    errors.max_price = 'Must be a valid price (e.g., 99.99)';
  }

  // Scope validation
  switch (form.scope_type) {
    case 'single':
      if (!form.product_id) errors.product_id = 'Select a product';
      break;
    case 'multiple':
      if (!form.applies_to_products.length) errors.applies_to_products = 'Select at least one product';
      break;
    case 'categories':
      if (!form.applies_to_categories.length) errors.applies_to_categories = 'Select at least one category';
      break;
  }

  // Rule type-specific validation
  switch (form.rule_type) {
    case 'sentiment_threshold':
      if (!form.sentiment_threshold) errors.sentiment_threshold = 'Required';
      break;
    case 'time_based':
      if (!form.time_days) errors.time_days = 'Required';
      break;
    case 'volume_surge':
      if (!form.volume_threshold) errors.volume_threshold = 'Required';
      break;
    case 'viral_detection':
      if (!form.viral_threshold_reach) errors.viral_threshold_reach = 'Required';
      break;
  }

  return errors;
}

/**
 * Check if form has validation errors
 */
export function isFormValid(form: RuleFormData): boolean {
  return Object.keys(validateRuleForm(form)).length === 0;
}



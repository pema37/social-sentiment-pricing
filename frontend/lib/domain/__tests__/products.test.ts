import { describe, it, expect } from 'vitest';
import {
  normalizeDecimal,
  decimalToFormString,
  productToFormData,
  formDataToCreateRequest,
  formDataToUpdateRequest,
  validateProductForm,
  validateAndCreate,
  DEFAULT_PRODUCT_FORM,
} from '../products';

describe('normalizeDecimal', () => {
  it('handles empty values', () => {
    expect(normalizeDecimal('')).toBeUndefined();
    expect(normalizeDecimal(null)).toBeUndefined();
    expect(normalizeDecimal(undefined)).toBeUndefined();
  });

  it('normalizes leading decimal point', () => {
    expect(normalizeDecimal('.5')).toBe('0.5');
    expect(normalizeDecimal('.99')).toBe('0.99');
  });

  it('handles numbers', () => {
    expect(normalizeDecimal(19.99)).toBe('19.99');
    expect(normalizeDecimal(0)).toBe('0');
  });

  it('trims whitespace', () => {
    expect(normalizeDecimal('  10.00  ')).toBe('10.00');
  });

  it('returns undefined for invalid input', () => {
    expect(normalizeDecimal('abc')).toBeUndefined();
    expect(normalizeDecimal(NaN)).toBeUndefined();
  });
});

describe('decimalToFormString', () => {
  it('converts null/undefined to empty string', () => {
    expect(decimalToFormString(null)).toBe('');
    expect(decimalToFormString(undefined)).toBe('');
  });

  it('converts values to strings', () => {
    expect(decimalToFormString('19.99')).toBe('19.99');
    expect(decimalToFormString(10)).toBe('10');
  });
});

describe('validateProductForm', () => {
  it('requires name', () => {
    const form = { ...DEFAULT_PRODUCT_FORM, name: '' };
    const errors = validateProductForm(form);
    expect(errors.name).toBeDefined();
  });

  it('requires base_price', () => {
    const form = { ...DEFAULT_PRODUCT_FORM, name: 'Test', base_price: '' };
    const errors = validateProductForm(form);
    expect(errors.base_price).toBeDefined();
  });

  it('requires positive base_price', () => {
    const form = { ...DEFAULT_PRODUCT_FORM, name: 'Test', base_price: '0' };
    const errors = validateProductForm(form);
    expect(errors.base_price).toBeDefined();
  });

  it('validates min_price < max_price', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '50',
      min_price: '100',
      max_price: '50',
    };
    const errors = validateProductForm(form);
    expect(errors.min_price).toBeDefined();
  });

  it('validates base_price >= min_price', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '10',
      min_price: '20',
    };
    const errors = validateProductForm(form);
    expect(errors.base_price).toBeDefined();
  });

  it('validates base_price <= max_price', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '100',
      max_price: '50',
    };
    const errors = validateProductForm(form);
    expect(errors.base_price).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test Product',
      base_price: '19.99',
    };
    const errors = validateProductForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('passes with valid price constraints', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test Product',
      base_price: '50',
      min_price: '40',
      max_price: '60',
    };
    const errors = validateProductForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });
});

describe('formDataToCreateRequest', () => {
  it('normalizes decimal fields', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '.99',
      cost: '5',
    };
    const request = formDataToCreateRequest(form);
    expect(request.base_price).toBe('0.99');
    expect(request.cost).toBe('5');
  });

  it('includes required fields', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test Product',
      base_price: '19.99',
    };
    const request = formDataToCreateRequest(form);
    expect(request.name).toBe('Test Product');
    expect(request.base_price).toBe('19.99');
  });

  it('omits empty optional fields', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '10',
      sku: '',
      description: '',
    };
    const request = formDataToCreateRequest(form);
    expect(request.sku).toBeUndefined();
    expect(request.description).toBeUndefined();
  });

  it('includes optional fields when provided', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '10',
      sku: 'SKU-123',
      category: 'electronics',
    };
    const request = formDataToCreateRequest(form);
    expect(request.sku).toBe('SKU-123');
    expect(request.category).toBe('electronics');
  });

  it('handles keywords array', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '10',
      keywords: ['phone', 'mobile', 'tech'],
    };
    const request = formDataToCreateRequest(form);
    expect(request.keywords).toEqual(['phone', 'mobile', 'tech']);
  });

  it('handles auto_pricing_enabled', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '10',
      auto_pricing_enabled: true,
    };
    const request = formDataToCreateRequest(form);
    expect(request.auto_pricing_enabled).toBe(true);
  });
});

describe('formDataToUpdateRequest', () => {
  it('returns null for empty optional strings', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: '',
      base_price: '10',
      sku: '',
    };
    const request = formDataToUpdateRequest(form);
    expect(request.name).toBeNull();
    expect(request.sku).toBeNull();
  });

  it('normalizes decimal fields', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test',
      base_price: '.5',
      min_price: '10',
    };
    const request = formDataToUpdateRequest(form);
    expect(request.base_price).toBe('0.5');
    expect(request.min_price).toBe('10');
  });
});

describe('productToFormData', () => {
  it('handles empty/partial product', () => {
    const form = productToFormData({});
    expect(form.name).toBe('');
    expect(form.is_active).toBe(true);
    expect(form.auto_pricing_enabled).toBe(false);
    expect(form.keywords).toEqual([]);
  });

  it('maps all fields correctly', () => {
    const product = {
      name: 'iPhone 15',
      sku: 'IP15-128',
      base_price: 999.00,
      current_price: 899.00,
      min_price: 799.00,
      max_price: 1099.00,
      is_active: true,
      auto_pricing_enabled: true,
      keywords: ['apple', 'phone'],
    };
    const form = productToFormData(product);
    expect(form.name).toBe('iPhone 15');
    expect(form.sku).toBe('IP15-128');
    expect(form.base_price).toBe('999');
    expect(form.min_price).toBe('799');
    expect(form.max_price).toBe('1099');
    expect(form.keywords).toEqual(['apple', 'phone']);
  });

  it('converts undefined values to empty strings', () => {
    const product = {
      name: 'Test',
      sku: undefined,
      description: undefined,
    };
    const form = productToFormData(product);
    expect(form.sku).toBe('');
    expect(form.description).toBe('');
  });

  it('uses default sentiment_multiplier', () => {
    const form = productToFormData({ name: 'Test' });
    expect(form.sentiment_multiplier).toBe('0.1');
  });
});

describe('validateAndCreate', () => {
  it('returns success with valid data', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: 'Test Product',
      base_price: '19.99',
    };
    const result = validateAndCreate(form);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Test Product');
    }
  });

  it('returns errors with invalid data', () => {
    const form = {
      ...DEFAULT_PRODUCT_FORM,
      name: '',
      base_price: '',
    };
    const result = validateAndCreate(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.name).toBeDefined();
      expect(result.errors.base_price).toBeDefined();
    }
  });
});



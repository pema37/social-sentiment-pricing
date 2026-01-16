import { describe, it, expect } from 'vitest';
import {
  competitorFormSchema,
  competitorProductFormSchema,
  competitorToFormData,
  formDataToCreateCompetitor,
  formDataToUpdateCompetitor,
  competitorProductToFormData,
  formDataToCreateCompetitorProduct,
  formDataToUpdateCompetitorProduct,
  validateCompetitorForm,
  validateCompetitorProductForm,
  validateAndCreateCompetitor,
  DEFAULT_COMPETITOR_FORM,
  DEFAULT_COMPETITOR_PRODUCT_FORM,
} from '../competitors';

describe('validateCompetitorForm', () => {
  it('requires name', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: '' };
    const errors = validateCompetitorForm(form);
    expect(errors.name).toBeDefined();
  });

  it('passes with valid name only', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Amazon' };
    const errors = validateCompetitorForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('validates website URL format', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: 'not-a-url' };
    const errors = validateCompetitorForm(form);
    expect(errors.website).toBeDefined();
  });

  it('accepts valid website URLs', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: 'amazon.com' };
    const errors = validateCompetitorForm(form);
    expect(errors.website).toBeUndefined();
  });

  it('accepts website with https', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: 'https://amazon.com' };
    const errors = validateCompetitorForm(form);
    expect(errors.website).toBeUndefined();
  });

  it('allows empty website', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: '' };
    const errors = validateCompetitorForm(form);
    expect(errors.website).toBeUndefined();
  });

  it('validates scrape_frequency_minutes minimum', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', scrape_frequency_minutes: '1' };
    const errors = validateCompetitorForm(form);
    expect(errors.scrape_frequency_minutes).toBeDefined();
  });

  it('accepts valid scrape_frequency_minutes', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', scrape_frequency_minutes: '30' };
    const errors = validateCompetitorForm(form);
    expect(errors.scrape_frequency_minutes).toBeUndefined();
  });
});

describe('formDataToCreateCompetitor', () => {
  it('includes required fields', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Amazon' };
    const request = formDataToCreateCompetitor(form);
    expect(request.name).toBe('Amazon');
    expect(request.is_active).toBe(true);
  });

  it('adds https to website if missing', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Amazon', website: 'amazon.com' };
    const request = formDataToCreateCompetitor(form);
    expect(request.website).toBe('https://amazon.com');
  });

  it('keeps https if already present', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Amazon', website: 'https://amazon.com' };
    const request = formDataToCreateCompetitor(form);
    expect(request.website).toBe('https://amazon.com');
  });

  it('omits empty optional fields', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: '', description: '' };
    const request = formDataToCreateCompetitor(form);
    expect(request.website).toBeUndefined();
    expect(request.description).toBeUndefined();
  });

  it('trims whitespace from name', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: '  Amazon  ' };
    const request = formDataToCreateCompetitor(form);
    expect(request.name).toBe('Amazon');
  });

  it('parses scrape_frequency_minutes as integer', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', scrape_frequency_minutes: '30' };
    const request = formDataToCreateCompetitor(form);
    expect(request.scrape_frequency_minutes).toBe(30);
  });
});

describe('formDataToUpdateCompetitor', () => {
  it('returns null for empty strings', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: '', description: '' };
    const request = formDataToUpdateCompetitor(form);
    expect(request.name).toBeNull();
    expect(request.description).toBeNull();
  });

  it('adds https to website', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: 'test.com' };
    const request = formDataToUpdateCompetitor(form);
    expect(request.website).toBe('https://test.com');
  });

  it('returns null for empty website', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Test', website: '' };
    const request = formDataToUpdateCompetitor(form);
    expect(request.website).toBeNull();
  });
});

describe('competitorToFormData', () => {
  it('handles empty/partial competitor', () => {
    const form = competitorToFormData({});
    expect(form.name).toBe('');
    expect(form.is_active).toBe(true);
    expect(form.scrape_frequency_minutes).toBe('60');
  });

  it('maps all fields correctly', () => {
    const competitor = {
      name: 'Amazon',
      website: 'https://amazon.com',
      description: 'E-commerce giant',
      is_active: false,
      scrape_frequency_minutes: 30,
    };
    const form = competitorToFormData(competitor);
    expect(form.name).toBe('Amazon');
    expect(form.website).toBe('https://amazon.com');
    expect(form.description).toBe('E-commerce giant');
    expect(form.is_active).toBe(false);
    expect(form.scrape_frequency_minutes).toBe('30');
  });

  it('handles null values', () => {
    const competitor = {
      name: 'Test',
      website: null,
      description: null,
    };
    const form = competitorToFormData(competitor);
    expect(form.website).toBe('');
    expect(form.description).toBe('');
  });
});

describe('validateAndCreateCompetitor', () => {
  it('returns success with valid data', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: 'Amazon' };
    const result = validateAndCreateCompetitor(form);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Amazon');
    }
  });

  it('returns errors with invalid data', () => {
    const form = { ...DEFAULT_COMPETITOR_FORM, name: '' };
    const result = validateAndCreateCompetitor(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.name).toBeDefined();
    }
  });
});

describe('validateCompetitorProductForm', () => {
  it('requires product_id', () => {
    const form = { ...DEFAULT_COMPETITOR_PRODUCT_FORM, product_id: '' };
    const errors = validateCompetitorProductForm(form);
    expect(errors.product_id).toBeDefined();
  });

  it('requires competitor_id', () => {
    const form = { ...DEFAULT_COMPETITOR_PRODUCT_FORM, competitor_id: '' };
    const errors = validateCompetitorProductForm(form);
    expect(errors.competitor_id).toBeDefined();
  });

  it('requires competitor_product_name', () => {
    const form = { ...DEFAULT_COMPETITOR_PRODUCT_FORM, competitor_product_name: '' };
    const errors = validateCompetitorProductForm(form);
    expect(errors.competitor_product_name).toBeDefined();
  });

  it('validates current_price as positive decimal', () => {
    const form = { 
      ...DEFAULT_COMPETITOR_PRODUCT_FORM, 
      product_id: 'p1',
      competitor_id: 'c1',
      competitor_product_name: 'Test',
      current_price: '-10' 
    };
    const errors = validateCompetitorProductForm(form);
    expect(errors.current_price).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = {
      ...DEFAULT_COMPETITOR_PRODUCT_FORM,
      product_id: 'prod-123',
      competitor_id: 'comp-456',
      competitor_product_name: 'iPhone 15',
      current_price: '999.00',
    };
    const errors = validateCompetitorProductForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });
});

describe('formDataToCreateCompetitorProduct', () => {
  it('includes required fields', () => {
    const form = {
      ...DEFAULT_COMPETITOR_PRODUCT_FORM,
      product_id: 'prod-123',
      competitor_id: 'comp-456',
      competitor_product_name: 'iPhone 15',
    };
    const request = formDataToCreateCompetitorProduct(form);
    expect(request.product_id).toBe('prod-123');
    expect(request.competitor_id).toBe('comp-456');
    expect(request.competitor_product_name).toBe('iPhone 15');
  });

  it('normalizes current_price', () => {
    const form = {
      ...DEFAULT_COMPETITOR_PRODUCT_FORM,
      product_id: 'p1',
      competitor_id: 'c1',
      competitor_product_name: 'Test',
      current_price: '.99',
    };
    const request = formDataToCreateCompetitorProduct(form);
    expect(request.current_price).toBe('0.99');
  });

  it('adds https to competitor_product_url', () => {
    const form = {
      ...DEFAULT_COMPETITOR_PRODUCT_FORM,
      product_id: 'p1',
      competitor_id: 'c1',
      competitor_product_name: 'Test',
      competitor_product_url: 'amazon.com/product/123',
    };
    const request = formDataToCreateCompetitorProduct(form);
    expect(request.competitor_product_url).toBe('https://amazon.com/product/123');
  });
});

describe('competitorProductToFormData', () => {
  it('handles empty/partial data', () => {
    const form = competitorProductToFormData({});
    expect(form.product_id).toBe('');
    expect(form.currency).toBe('USD');
    expect(form.match_confidence).toBe('1.0');
    expect(form.is_active).toBe(true);
  });

  it('maps all fields correctly', () => {
    const cp = {
      product_id: 'p1',
      competitor_id: 'c1',
      competitor_product_name: 'iPhone',
      current_price: '999.00',
      currency: 'EUR',
      match_confidence: '0.95',
    };
    const form = competitorProductToFormData(cp);
    expect(form.product_id).toBe('p1');
    expect(form.competitor_product_name).toBe('iPhone');
    expect(form.current_price).toBe('999.00');
    expect(form.currency).toBe('EUR');
    expect(form.match_confidence).toBe('0.95');
  });
});



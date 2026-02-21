import { describe, it, expect } from 'vitest';
import {
  wooCommerceConnectSchema,
  shopifyConnectSchema,
  productLinkSchema,
  normalizeStoreUrl,
  getStoreDomain,
  formDataToWooCommerceRequest,
  formDataToOAuthRequest,
  integrationToUpdateFormData,
  formDataToIntegrationUpdate,
  formDataToProductLinkCreate,
  validateWooCommerceForm,
  validateShopifyForm,
  validateProductLinkForm,
  validateAndConnectWooCommerce,
  validateAndConnectShopify,
  validateAndCreateProductLink,
  getStatusLabel,
  getStatusColor,
  getSyncStatusLabel,
  DEFAULT_WOOCOMMERCE_FORM,
  DEFAULT_SHOPIFY_FORM,
  DEFAULT_PRODUCT_LINK_FORM,
  DEFAULT_INTEGRATION_UPDATE_FORM,
} from '../integrations';

describe('normalizeStoreUrl', () => {
  it('adds https if missing', () => {
    expect(normalizeStoreUrl('example.com')).toBe('https://example.com');
    expect(normalizeStoreUrl('mystore.com')).toBe('https://mystore.com');
  });

  it('keeps https if already present', () => {
    expect(normalizeStoreUrl('https://example.com')).toBe('https://example.com');
  });

  it('converts http to https', () => {
    expect(normalizeStoreUrl('http://example.com')).toBe('https://example.com');
  });

  it('removes trailing slashes', () => {
    expect(normalizeStoreUrl('example.com/')).toBe('https://example.com');
    expect(normalizeStoreUrl('example.com///')).toBe('https://example.com');
  });

  it('lowercases the URL', () => {
    expect(normalizeStoreUrl('EXAMPLE.COM')).toBe('https://example.com');
    expect(normalizeStoreUrl('MyStore.Com')).toBe('https://mystore.com');
  });

  it('trims whitespace', () => {
    expect(normalizeStoreUrl('  example.com  ')).toBe('https://example.com');
  });

  it('handles full URLs with paths', () => {
    expect(normalizeStoreUrl('https://example.com/shop')).toBe('https://example.com/shop');
  });
});

describe('getStoreDomain', () => {
  it('extracts domain from URL', () => {
    expect(getStoreDomain('https://mystore.com')).toBe('mystore.com');
    expect(getStoreDomain('https://shop.example.com/products')).toBe('shop.example.com');
  });

  it('handles URLs without protocol', () => {
    expect(getStoreDomain('mystore.com')).toBe('mystore.com');
  });

  it('returns input for invalid URLs', () => {
    expect(getStoreDomain('not-a-url')).toBe('not-a-url');
  });
});

describe('validateWooCommerceForm', () => {
  it('requires store_url', () => {
    const form = { ...DEFAULT_WOOCOMMERCE_FORM, store_url: '' };
    const errors = validateWooCommerceForm(form);
    expect(errors.store_url).toBeDefined();
  });

  it('requires consumer_key', () => {
    const form = { ...DEFAULT_WOOCOMMERCE_FORM, store_url: 'example.com', consumer_key: '' };
    const errors = validateWooCommerceForm(form);
    expect(errors.consumer_key).toBeDefined();
  });

  it('requires consumer_secret', () => {
    const form = { 
      ...DEFAULT_WOOCOMMERCE_FORM, 
      store_url: 'example.com', 
      consumer_key: 'ck_xxx',
      consumer_secret: '' 
    };
    const errors = validateWooCommerceForm(form);
    expect(errors.consumer_secret).toBeDefined();
  });

  it('validates store_url format', () => {
    const form = { 
      ...DEFAULT_WOOCOMMERCE_FORM, 
      store_url: 'not a valid url',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const errors = validateWooCommerceForm(form);
    expect(errors.store_url).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'mystore.com',
      consumer_key: 'ck_xxxxxxxxxxxxx',
      consumer_secret: 'cs_xxxxxxxxxxxxx',
    };
    const errors = validateWooCommerceForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('allows optional store_name', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'mystore.com',
      store_name: '',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const errors = validateWooCommerceForm(form);
    expect(errors.store_name).toBeUndefined();
  });
});

describe('validateShopifyForm', () => {
  it('requires store_url', () => {
    const form = { ...DEFAULT_SHOPIFY_FORM, store_url: '' };
    const errors = validateShopifyForm(form);
    expect(errors.store_url).toBeDefined();
  });

  it('validates store_url format', () => {
    const form = { store_url: 'not valid' };
    const errors = validateShopifyForm(form);
    expect(errors.store_url).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = { store_url: 'mystore.myshopify.com' };
    const errors = validateShopifyForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });
});

describe('validateProductLinkForm', () => {
  it('requires product_id', () => {
    const form = { ...DEFAULT_PRODUCT_LINK_FORM, product_id: '' };
    const errors = validateProductLinkForm(form);
    expect(errors.product_id).toBeDefined();
  });

  it('requires external_product_id', () => {
    const form = { ...DEFAULT_PRODUCT_LINK_FORM, product_id: 'p1', external_product_id: '' };
    const errors = validateProductLinkForm(form);
    expect(errors.external_product_id).toBeDefined();
  });

  it('passes with valid data', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'prod-123',
      external_product_id: 'ext-456',
    };
    const errors = validateProductLinkForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('allows optional external_variant_id', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'p1',
      external_product_id: 'ext-1',
      external_variant_id: '',
    };
    const errors = validateProductLinkForm(form);
    expect(errors.external_variant_id).toBeUndefined();
  });
});

describe('formDataToWooCommerceRequest', () => {
  it('normalizes store_url', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'MyStore.com/',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const request = formDataToWooCommerceRequest(form);
    expect(request.store_url).toBe('https://mystore.com');
  });

  it('trims credentials', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'example.com',
      consumer_key: '  ck_xxx  ',
      consumer_secret: '  cs_xxx  ',
    };
    const request = formDataToWooCommerceRequest(form);
    expect(request.consumer_key).toBe('ck_xxx');
    expect(request.consumer_secret).toBe('cs_xxx');
  });

  it('sets store_name to null if empty', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'example.com',
      store_name: '',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const request = formDataToWooCommerceRequest(form);
    expect(request.store_name).toBeNull();
  });

  it('includes store_name when provided', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'example.com',
      store_name: 'My Awesome Store',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const request = formDataToWooCommerceRequest(form);
    expect(request.store_name).toBe('My Awesome Store');
  });
});

describe('formDataToOAuthRequest', () => {
  it('normalizes store_url', () => {
    const form = { store_url: 'MyStore.myshopify.com/' };
    const request = formDataToOAuthRequest(form, 'shopify');
    expect(request.store_url).toBe('https://mystore.myshopify.com');
  });

  it('includes platform', () => {
    const form = { store_url: 'example.com' };
    const request = formDataToOAuthRequest(form, 'shopify');
    expect(request.platform).toBe('shopify');
  });
});

describe('integrationToUpdateFormData', () => {
  it('handles empty/partial integration', () => {
    const form = integrationToUpdateFormData({});
    expect(form.store_name).toBe('');
    expect(form.is_paused).toBe(false);
  });

  it('maps store_name', () => {
    const form = integrationToUpdateFormData({ store_name: 'My Store' });
    expect(form.store_name).toBe('My Store');
  });

  it('sets is_paused based on status', () => {
    expect(integrationToUpdateFormData({ status: 'paused' }).is_paused).toBe(true);
    expect(integrationToUpdateFormData({ status: 'active' }).is_paused).toBe(false);
    expect(integrationToUpdateFormData({ status: 'error' }).is_paused).toBe(false);
  });

  it('handles null store_name', () => {
    const form = integrationToUpdateFormData({ store_name: null });
    expect(form.store_name).toBe('');
  });
});

describe('formDataToIntegrationUpdate', () => {
  it('sets status based on is_paused', () => {
    expect(formDataToIntegrationUpdate({ store_name: '', is_paused: true }).status).toBe('paused');
    expect(formDataToIntegrationUpdate({ store_name: '', is_paused: false }).status).toBe('active');
  });

  it('sets store_name to null if empty', () => {
    const request = formDataToIntegrationUpdate({ store_name: '', is_paused: false });
    expect(request.store_name).toBeNull();
  });

  it('trims store_name', () => {
    const request = formDataToIntegrationUpdate({ store_name: '  My Store  ', is_paused: false });
    expect(request.store_name).toBe('My Store');
  });
});

describe('formDataToProductLinkCreate', () => {
  it('includes required fields', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'prod-123',
      external_product_id: 'ext-456',
    };
    const request = formDataToProductLinkCreate(form);
    expect(request.product_id).toBe('prod-123');
    expect(request.external_product_id).toBe('ext-456');
  });

  it('trims external_product_id', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'p1',
      external_product_id: '  ext-123  ',
    };
    const request = formDataToProductLinkCreate(form);
    expect(request.external_product_id).toBe('ext-123');
  });

  it('sets external_variant_id to null if empty', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'p1',
      external_product_id: 'ext-1',
      external_variant_id: '',
    };
    const request = formDataToProductLinkCreate(form);
    expect(request.external_variant_id).toBeNull();
  });

  it('includes external_variant_id when provided', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'p1',
      external_product_id: 'ext-1',
      external_variant_id: 'var-123',
    };
    const request = formDataToProductLinkCreate(form);
    expect(request.external_variant_id).toBe('var-123');
  });
});

describe('validateAndConnectWooCommerce', () => {
  it('returns success with valid data', () => {
    const form = {
      ...DEFAULT_WOOCOMMERCE_FORM,
      store_url: 'mystore.com',
      consumer_key: 'ck_xxx',
      consumer_secret: 'cs_xxx',
    };
    const result = validateAndConnectWooCommerce(form);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.store_url).toBe('https://mystore.com');
    }
  });

  it('returns errors with invalid data', () => {
    const form = { ...DEFAULT_WOOCOMMERCE_FORM };
    const result = validateAndConnectWooCommerce(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.store_url).toBeDefined();
      expect(result.errors.consumer_key).toBeDefined();
      expect(result.errors.consumer_secret).toBeDefined();
    }
  });
});

describe('validateAndConnectShopify', () => {
  it('returns success with valid data', () => {
    const form = { store_url: 'mystore.myshopify.com' };
    const result = validateAndConnectShopify(form);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.platform).toBe('shopify');
    }
  });

  it('returns errors with invalid data', () => {
    const form = { store_url: '' };
    const result = validateAndConnectShopify(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.store_url).toBeDefined();
    }
  });
});

describe('validateAndCreateProductLink', () => {
  it('returns success with valid data', () => {
    const form = {
      ...DEFAULT_PRODUCT_LINK_FORM,
      product_id: 'p1',
      external_product_id: 'ext-1',
    };
    const result = validateAndCreateProductLink(form);
    expect(result.success).toBe(true);
  });

  it('returns errors with invalid data', () => {
    const form = { ...DEFAULT_PRODUCT_LINK_FORM };
    const result = validateAndCreateProductLink(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.product_id).toBeDefined();
      expect(result.errors.external_product_id).toBeDefined();
    }
  });
});

describe('display helpers', () => {
  describe('getStatusLabel', () => {
    it('returns correct labels', () => {
      expect(getStatusLabel('active')).toBe('Active');
      expect(getStatusLabel('error')).toBe('Error');
      expect(getStatusLabel('paused')).toBe('Paused');
      expect(getStatusLabel('disconnected')).toBe('Disconnected');
    });

    it('returns status as-is for unknown', () => {
      expect(getStatusLabel('unknown')).toBe('unknown');
    });
  });

  describe('getStatusColor', () => {
    it('returns correct colors', () => {
      expect(getStatusColor('active')).toBe('green');
      expect(getStatusColor('error')).toBe('red');
      expect(getStatusColor('paused')).toBe('yellow');
      expect(getStatusColor('disconnected')).toBe('gray');
    });

    it('defaults to gray for unknown', () => {
      expect(getStatusColor('unknown')).toBe('gray');
    });
  });

  describe('getSyncStatusLabel', () => {
    it('returns correct labels', () => {
      expect(getSyncStatusLabel('idle')).toBe('Ready');
      expect(getSyncStatusLabel('syncing')).toBe('Syncing...');
      expect(getSyncStatusLabel('error')).toBe('Sync Failed');
    });

    it('returns status as-is for unknown', () => {
      expect(getSyncStatusLabel('unknown')).toBe('unknown');
    });
  });
});

describe('default forms', () => {
  it('DEFAULT_WOOCOMMERCE_FORM has empty values', () => {
    expect(DEFAULT_WOOCOMMERCE_FORM.store_url).toBe('');
    expect(DEFAULT_WOOCOMMERCE_FORM.store_name).toBe('');
    expect(DEFAULT_WOOCOMMERCE_FORM.consumer_key).toBe('');
    expect(DEFAULT_WOOCOMMERCE_FORM.consumer_secret).toBe('');
  });

  it('DEFAULT_SHOPIFY_FORM has empty values', () => {
    expect(DEFAULT_SHOPIFY_FORM.store_url).toBe('');
  });

  it('DEFAULT_PRODUCT_LINK_FORM has empty values', () => {
    expect(DEFAULT_PRODUCT_LINK_FORM.product_id).toBe('');
    expect(DEFAULT_PRODUCT_LINK_FORM.external_product_id).toBe('');
    expect(DEFAULT_PRODUCT_LINK_FORM.external_variant_id).toBe('');
  });

  it('DEFAULT_INTEGRATION_UPDATE_FORM has defaults', () => {
    expect(DEFAULT_INTEGRATION_UPDATE_FORM.store_name).toBe('');
    expect(DEFAULT_INTEGRATION_UPDATE_FORM.is_paused).toBe(false);
  });
});



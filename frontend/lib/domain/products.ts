// frontend/lib/domain/products.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type { Product, CreateProductRequest, UpdateProductRequest } from '@/types/product';


// ============================================
// ZOD SCHEMAS
// ============================================

/**
 * Validates a string is a valid decimal (or empty)
 */
const validDecimalString = z.string().refine((val) => {
  if (val === '') return true;
  let cleaned = val.trim();
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return true;
  return !isNaN(parseFloat(cleaned));
}, { message: 'Must be a valid number' });

/**
 * Required positive decimal
 */
const requiredPositiveDecimal = z.string()
  .min(1, 'Required')
  .refine((val) => {
    let cleaned = val.trim();
    if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
    const num = parseFloat(cleaned);
    return !isNaN(num) && num > 0;
  }, { message: 'Must be a positive number' });

/**
 * Optional positive decimal (empty allowed, but if provided must be positive)
 */
const optionalPositiveDecimal = z.string().refine((val) => {
  if (val === '') return true;
  let cleaned = val.trim();
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  const num = parseFloat(cleaned);
  return !isNaN(num) && num >= 0;
}, { message: 'Must be a positive number' });

/**
 * Form data schema - validates the raw form input
 */
export const productFormSchema = z.object({
  name: z.string().min(1, 'Product name is required'),
  sku: z.string(),
  description: z.string(),
  category: z.string(),
  image_url: z.string(),
  is_active: z.boolean(),
  base_price: requiredPositiveDecimal,
  cost: optionalPositiveDecimal,
  min_price: optionalPositiveDecimal,
  max_price: optionalPositiveDecimal,
  sentiment_multiplier: validDecimalString,
  auto_pricing_enabled: z.boolean(),
  keywords: z.array(z.string()),
}).superRefine((data, ctx) => {
  // Validate min_price < max_price if both provided
  if (data.min_price && data.max_price) {
    const min = parseFloat(data.min_price);
    const max = parseFloat(data.max_price);
    if (!isNaN(min) && !isNaN(max) && min >= max) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Min price must be less than max price',
        path: ['min_price'],
      });
    }
  }
  
  // Validate base_price is within min/max range
  if (data.base_price) {
    const base = parseFloat(data.base_price);
    if (data.min_price) {
      const min = parseFloat(data.min_price);
      if (!isNaN(base) && !isNaN(min) && base < min) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Base price cannot be below min price',
          path: ['base_price'],
        });
      }
    }
    if (data.max_price) {
      const max = parseFloat(data.max_price);
      if (!isNaN(base) && !isNaN(max) && base > max) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Base price cannot exceed max price',
          path: ['base_price'],
        });
      }
    }
  }
});

// ============================================
// TYPES
// ============================================

/** Infer form data type from schema */
export type ProductFormData = z.input<typeof productFormSchema>;

export type ProductFormErrors = Partial<Record<keyof ProductFormData, string>>;

// ============================================
// DECIMAL HANDLING UTILITIES
// ============================================

/**
 * Normalize a string to a valid decimal string for the API
 */
export function normalizeDecimal(value: string | number | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  if (typeof value === 'number') {
    if (isNaN(value)) return undefined;
    return value.toString();
  }

  let cleaned = value.toString().trim();
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return undefined;

  const num = parseFloat(cleaned);
  return isNaN(num) ? undefined : cleaned;
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

/** Default form data for new products */
export const DEFAULT_PRODUCT_FORM: ProductFormData = {
  name: '',
  sku: '',
  description: '',
  category: '',
  image_url: '',
  is_active: true,
  base_price: '',
  cost: '',
  min_price: '',
  max_price: '',
  sentiment_multiplier: '0.1',
  auto_pricing_enabled: false,
  keywords: [],
};

/**
 * Transform API Product response to form data
 */
export function productToFormData(product: Partial<Product>): ProductFormData {
  return {
    name: product.name ?? '',
    sku: product.sku ?? '',
    description: product.description ?? '',
    category: product.category ?? '',
    image_url: product.image_url ?? '',
    is_active: product.is_active ?? true,
    base_price: decimalToFormString(product.base_price),
    cost: decimalToFormString(product.cost),
    min_price: decimalToFormString(product.min_price),
    max_price: decimalToFormString(product.max_price),
    sentiment_multiplier: decimalToFormString(product.sentiment_multiplier) || '0.1',
    auto_pricing_enabled: product.auto_pricing_enabled ?? false,
    keywords: product.keywords ?? [],
  };
}

// ============================================
// TRANSFORMATIONS: Form → API
// ============================================

/**
 * Transform form data to CreateProductRequest
 */
export function formDataToCreateRequest(form: ProductFormData): CreateProductRequest {
  const payload: CreateProductRequest = {
    name: form.name.trim(),
    base_price: normalizeDecimal(form.base_price) ?? '0',
    is_active: form.is_active,
    auto_pricing_enabled: form.auto_pricing_enabled,
    keywords: form.keywords,
  };

  // Optional fields - only include if provided
  if (form.sku.trim()) payload.sku = form.sku.trim();
  if (form.description.trim()) payload.description = form.description.trim();
  if (form.category.trim()) payload.category = form.category.trim();
  if (form.image_url.trim()) payload.image_url = form.image_url.trim();
  
  const cost = normalizeDecimal(form.cost);
  if (cost !== undefined) payload.cost = cost;
  
  const minPrice = normalizeDecimal(form.min_price);
  if (minPrice !== undefined) payload.min_price = minPrice;
  
  const maxPrice = normalizeDecimal(form.max_price);
  if (maxPrice !== undefined) payload.max_price = maxPrice;
  
  const multiplier = normalizeDecimal(form.sentiment_multiplier);
  if (multiplier !== undefined) payload.sentiment_multiplier = multiplier;

  return payload;
}

/**
 * Transform form data to UpdateProductRequest
 */
export function formDataToUpdateRequest(form: ProductFormData): UpdateProductRequest {
  return {
    name: form.name.trim() || null,
    sku: form.sku.trim() || null,
    description: form.description.trim() || null,
    category: form.category.trim() || null,
    image_url: form.image_url.trim() || null,
    is_active: form.is_active,
    base_price: normalizeDecimal(form.base_price) ?? null,
    cost: normalizeDecimal(form.cost) ?? null,
    min_price: normalizeDecimal(form.min_price) ?? null,
    max_price: normalizeDecimal(form.max_price) ?? null,
    sentiment_multiplier: normalizeDecimal(form.sentiment_multiplier) ?? null,
    auto_pricing_enabled: form.auto_pricing_enabled,
    keywords: form.keywords,
  };
}

// ============================================
// VALIDATION
// ============================================

/**
 * Validate form data using Zod schema
 * Returns errors object compatible with form state
 */
export function validateProductForm(form: ProductFormData): ProductFormErrors {
  const result = productFormSchema.safeParse(form);
  
  if (result.success) {
    return {};
  }

  const errors: ProductFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof ProductFormData;
    if (path && !errors[path]) {
      errors[path] = issue.message;
    }
  }
  
  return errors;
}

/**
 * Validate and transform for create - one step
 */
export function validateAndCreate(form: ProductFormData): 
  | { success: true; data: CreateProductRequest }
  | { success: false; errors: ProductFormErrors } {
  
  const validation = productFormSchema.safeParse(form);
  
  if (!validation.success) {
    const errors: ProductFormErrors = {};
    for (const issue of validation.error.issues) {
      const path = issue.path[0] as keyof ProductFormData;
      if (path && !errors[path]) {
        errors[path] = issue.message;
      }
    }
    return { success: false, errors };
  }
  
  return { success: true, data: formDataToCreateRequest(form) };
}

/**
 * Validate and transform for update - one step
 */
export function validateAndUpdate(form: ProductFormData): 
  | { success: true; data: UpdateProductRequest }
  | { success: false; errors: ProductFormErrors } {
  
  const validation = productFormSchema.safeParse(form);
  
  if (!validation.success) {
    const errors: ProductFormErrors = {};
    for (const issue of validation.error.issues) {
      const path = issue.path[0] as keyof ProductFormData;
      if (path && !errors[path]) {
        errors[path] = issue.message;
      }
    }
    return { success: false, errors };
  }
  
  return { success: true, data: formDataToUpdateRequest(form) };
}





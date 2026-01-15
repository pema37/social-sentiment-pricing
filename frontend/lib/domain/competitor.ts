// frontend/lib/domain/competitors.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type { 
  Competitor, 
  CreateCompetitorRequest, 
  UpdateCompetitorRequest,
  CompetitorProduct,
  CreateCompetitorProductRequest,
  UpdateCompetitorProductRequest,
} from '@/types/competitor';

// ============================================
// ZOD SCHEMAS - COMPETITOR
// ============================================

/**
 * URL validation (optional but must be valid if provided)
 */
const optionalUrl = z.string().refine((val) => {
  if (val === '') return true;
  try {
    new URL(val.startsWith('http') ? val : `https://${val}`);
    return true;
  } catch {
    return false;
  }
}, { message: 'Must be a valid URL' });

/**
 * Competitor form schema
 */
export const competitorFormSchema = z.object({
  name: z.string().min(1, 'Competitor name is required'),
  website: optionalUrl,
  description: z.string(),
  is_active: z.boolean(),
  scrape_frequency_minutes: z.string().refine((val) => {
    if (val === '') return true;
    const num = parseInt(val, 10);
    return !isNaN(num) && num >= 5;
  }, { message: 'Must be at least 5 minutes' }),
});

// ============================================
// ZOD SCHEMAS - COMPETITOR PRODUCT
// ============================================

const validDecimalString = z.string().refine((val) => {
  if (val === '') return true;
  let cleaned = val.trim();
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  const num = parseFloat(cleaned);
  return !isNaN(num) && num >= 0;
}, { message: 'Must be a valid positive number' });

/**
 * Competitor product form schema
 */
export const competitorProductFormSchema = z.object({
  product_id: z.string().min(1, 'Select your product'),
  competitor_id: z.string().min(1, 'Select a competitor'),
  competitor_product_name: z.string().min(1, 'Product name is required'),
  competitor_product_url: optionalUrl,
  competitor_sku: z.string(),
  currency: z.string(),
  match_confidence: validDecimalString,
  notes: z.string(),
  is_active: z.boolean(),
  current_price: validDecimalString,
});

// ============================================
// TYPES
// ============================================

export type CompetitorFormData = z.input<typeof competitorFormSchema>;
export type CompetitorFormErrors = Partial<Record<keyof CompetitorFormData, string>>;

export type CompetitorProductFormData = z.input<typeof competitorProductFormSchema>;
export type CompetitorProductFormErrors = Partial<Record<keyof CompetitorProductFormData, string>>;

// ============================================
// UTILITIES
// ============================================

function normalizeDecimal(value: string | number | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  if (typeof value === 'number') return isNaN(value) ? undefined : value.toString();
  let cleaned = value.toString().trim();
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned === '' || cleaned === '-') return undefined;
  const num = parseFloat(cleaned);
  return isNaN(num) ? undefined : cleaned;
}

function decimalToFormString(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  return value.toString();
}

// ============================================
// COMPETITOR: API → Form
// ============================================

export const DEFAULT_COMPETITOR_FORM: CompetitorFormData = {
  name: '',
  website: '',
  description: '',
  is_active: true,
  scrape_frequency_minutes: '60',
};

export function competitorToFormData(competitor: Partial<Competitor>): CompetitorFormData {
  return {
    name: competitor.name ?? '',
    website: competitor.website ?? '',
    description: competitor.description ?? '',
    is_active: competitor.is_active ?? true,
    scrape_frequency_minutes: competitor.scrape_frequency_minutes?.toString() ?? '60',
  };
}

// ============================================
// COMPETITOR: Form → API
// ============================================

export function formDataToCreateCompetitor(form: CompetitorFormData): CreateCompetitorRequest {
  const payload: CreateCompetitorRequest = {
    name: form.name.trim(),
    is_active: form.is_active,
  };

  if (form.website.trim()) {
    let url = form.website.trim();
    if (!url.startsWith('http')) url = 'https://' + url;
    payload.website = url;
  }
  if (form.description.trim()) payload.description = form.description.trim();
  
  const freq = parseInt(form.scrape_frequency_minutes, 10);
  if (!isNaN(freq) && freq >= 5) payload.scrape_frequency_minutes = freq;

  return payload;
}

export function formDataToUpdateCompetitor(form: CompetitorFormData): UpdateCompetitorRequest {
  let website: string | null = null;
  if (form.website.trim()) {
    website = form.website.trim();
    if (!website.startsWith('http')) website = 'https://' + website;
  }

  return {
    name: form.name.trim() || null,
    website,
    description: form.description.trim() || null,
    is_active: form.is_active,
    scrape_frequency_minutes: parseInt(form.scrape_frequency_minutes, 10) || null,
  };
}

// ============================================
// COMPETITOR PRODUCT: API → Form
// ============================================

export const DEFAULT_COMPETITOR_PRODUCT_FORM: CompetitorProductFormData = {
  product_id: '',
  competitor_id: '',
  competitor_product_name: '',
  competitor_product_url: '',
  competitor_sku: '',
  currency: 'USD',
  match_confidence: '1.0',
  notes: '',
  is_active: true,
  current_price: '',
};

export function competitorProductToFormData(cp: Partial<CompetitorProduct>): CompetitorProductFormData {
  return {
    product_id: cp.product_id ?? '',
    competitor_id: cp.competitor_id ?? '',
    competitor_product_name: cp.competitor_product_name ?? '',
    competitor_product_url: cp.competitor_product_url ?? '',
    competitor_sku: cp.competitor_sku ?? '',
    currency: cp.currency ?? 'USD',
    match_confidence: decimalToFormString(cp.match_confidence) || '1.0',
    notes: cp.notes ?? '',
    is_active: cp.is_active ?? true,
    current_price: decimalToFormString(cp.current_price),
  };
}

// ============================================
// COMPETITOR PRODUCT: Form → API
// ============================================

export function formDataToCreateCompetitorProduct(form: CompetitorProductFormData): CreateCompetitorProductRequest {
  const payload: CreateCompetitorProductRequest = {
    product_id: form.product_id,
    competitor_id: form.competitor_id,
    competitor_product_name: form.competitor_product_name.trim(),
    is_active: form.is_active,
  };

  if (form.competitor_product_url.trim()) {
    let url = form.competitor_product_url.trim();
    if (!url.startsWith('http')) url = 'https://' + url;
    payload.competitor_product_url = url;
  }
  if (form.competitor_sku.trim()) payload.competitor_sku = form.competitor_sku.trim();
  if (form.currency.trim()) payload.currency = form.currency.trim();
  if (form.notes.trim()) payload.notes = form.notes.trim();
  
  const confidence = normalizeDecimal(form.match_confidence);
  if (confidence !== undefined) payload.match_confidence = confidence;
  
  const price = normalizeDecimal(form.current_price);
  if (price !== undefined) payload.current_price = price;

  return payload;
}

export function formDataToUpdateCompetitorProduct(form: CompetitorProductFormData): UpdateCompetitorProductRequest {
  let url: string | null = null;
  if (form.competitor_product_url.trim()) {
    url = form.competitor_product_url.trim();
    if (!url.startsWith('http')) url = 'https://' + url;
  }

  return {
    competitor_product_name: form.competitor_product_name.trim() || null,
    competitor_product_url: url,
    competitor_sku: form.competitor_sku.trim() || null,
    currency: form.currency.trim() || null,
    match_confidence: normalizeDecimal(form.match_confidence) ?? null,
    notes: form.notes.trim() || null,
    is_active: form.is_active,
    current_price: normalizeDecimal(form.current_price) ?? null,
  };
}

// ============================================
// VALIDATION
// ============================================

export function validateCompetitorForm(form: CompetitorFormData): CompetitorFormErrors {
  const result = competitorFormSchema.safeParse(form);
  if (result.success) return {};

  const errors: CompetitorFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof CompetitorFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

export function validateCompetitorProductForm(form: CompetitorProductFormData): CompetitorProductFormErrors {
  const result = competitorProductFormSchema.safeParse(form);
  if (result.success) return {};

  const errors: CompetitorProductFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof CompetitorProductFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

/**
 * Validate and transform competitor for create
 */
export function validateAndCreateCompetitor(form: CompetitorFormData): 
  | { success: true; data: CreateCompetitorRequest }
  | { success: false; errors: CompetitorFormErrors } {
  
  const errors = validateCompetitorForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToCreateCompetitor(form) };
}

/**
 * Validate and transform competitor for update
 */
export function validateAndUpdateCompetitor(form: CompetitorFormData): 
  | { success: true; data: UpdateCompetitorRequest }
  | { success: false; errors: CompetitorFormErrors } {
  
  const errors = validateCompetitorForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToUpdateCompetitor(form) };
}

/**
 * Validate and transform competitor product for create
 */
export function validateAndCreateCompetitorProduct(form: CompetitorProductFormData): 
  | { success: true; data: CreateCompetitorProductRequest }
  | { success: false; errors: CompetitorProductFormErrors } {
  
  const errors = validateCompetitorProductForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToCreateCompetitorProduct(form) };
}

/**
 * Validate and transform competitor product for update
 */
export function validateAndUpdateCompetitorProduct(form: CompetitorProductFormData): 
  | { success: true; data: UpdateCompetitorProductRequest }
  | { success: false; errors: CompetitorProductFormErrors } {
  
  const errors = validateCompetitorProductForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToUpdateCompetitorProduct(form) };
}



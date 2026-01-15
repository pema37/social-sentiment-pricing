// frontend/lib/domain/index.ts
// Re-export domain modules with explicit naming to avoid collisions

// Pricing - export everything (it was first, so it "owns" shared utility names)
export * from './pricing';

// Products - rename colliding exports
export {
  // Types
  type ProductFormData,
  type ProductFormErrors,
  // Schema
  productFormSchema,
  // Constants
  DEFAULT_PRODUCT_FORM,
  // Transforms
  productToFormData,
  formDataToCreateRequest as formDataToCreateProduct,
  formDataToUpdateRequest as formDataToUpdateProduct,
  // Validation
  validateProductForm,
  validateAndCreate as validateAndCreateProduct,
  validateAndUpdate as validateAndUpdateProduct,
  // Utilities (renamed to avoid collision)
  normalizeDecimal as normalizeProductDecimal,
  decimalToFormString as productDecimalToFormString,
} from './products';

// Competitors - no collisions with pricing
export * from './competitors';

// Integrations - no collisions with pricing
export * from './integrations';

// Alerts - no collisions with pricing
export * from './alerts';


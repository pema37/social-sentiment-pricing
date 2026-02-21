// frontend/lib/api/errors.ts
// Centralized API error handling
// Components should NEVER parse errors themselves - use these utilities
//
// FIX (2026-01-28) Priority 3: Added support for structured backend errors:
// { detail: { message: "...", error_code: "..." } }
// and new recommendation-specific error codes.

export const ErrorCodes = {
  // Original error codes
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR: 'AUTHORIZATION_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  RATE_LIMIT: 'RATE_LIMIT',
  INTEGRATION_ERROR: 'INTEGRATION_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  
  // NEW: Recommendation-specific error codes (Priority 3 fix)
  RECOMMENDATION_NOT_FOUND: 'RECOMMENDATION_NOT_FOUND',
  RECOMMENDATION_EXPIRED: 'RECOMMENDATION_EXPIRED',
  RECOMMENDATION_ALREADY_PROCESSED: 'RECOMMENDATION_ALREADY_PROCESSED',
  PRODUCT_NOT_FOUND: 'PRODUCT_NOT_FOUND',
  PRODUCT_NOT_LINKED: 'PRODUCT_NOT_LINKED',
  INTEGRATION_NOT_FOUND: 'INTEGRATION_NOT_FOUND',
  INTEGRATION_NOT_ACTIVE: 'INTEGRATION_NOT_ACTIVE',
  PRICE_PUSH_FAILED: 'PRICE_PUSH_FAILED',
  UNAUTHORIZED: 'UNAUTHORIZED',
} as const;

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];

export interface ParsedApiError {
  code: ErrorCode;
  message: string;
  suggestion?: string;
  fieldErrors?: Record<string, string[]>;
  status?: number;
}

interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

// NEW: Structured error from backend (Priority 3 fix)
interface StructuredErrorDetail {
  message: string;
  error_code: string;
}

interface ApiErrorResponse {
  detail?: string | ValidationErrorDetail[] | StructuredErrorDetail;
}

/**
 * Parse any API error into a consistent format
 */
export function parseApiError(error: unknown): ParsedApiError {
  // Network errors (fetch failed)
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      code: ErrorCodes.NETWORK_ERROR,
      message: 'Unable to connect to the server',
      suggestion: 'Please check your internet connection and try again',
    };
  }

  // Response errors with status codes
  if (error && typeof error === 'object' && 'status' in error) {
    const responseError = error as { status: number; data?: ApiErrorResponse };
    return parseResponseError(responseError.status, responseError.data);
  }

  // Error objects with response property (from axios-like clients)
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { status: number; data?: ApiErrorResponse } };
    if (axiosError.response) {
      return parseResponseError(axiosError.response.status, axiosError.response.data);
    }
  }

  // Plain error objects with message
  if (error instanceof Error) {
    return {
      code: ErrorCodes.UNKNOWN_ERROR,
      message: error.message || 'An unexpected error occurred',
    };
  }

  // Fallback
  return {
    code: ErrorCodes.UNKNOWN_ERROR,
    message: 'An unexpected error occurred',
  };
}

/**
 * Check if detail is a structured error object (Priority 3 fix)
 */
function isStructuredError(detail: unknown): detail is StructuredErrorDetail {
  return (
    detail !== null &&
    typeof detail === 'object' &&
    !Array.isArray(detail) &&
    'message' in detail &&
    typeof (detail as StructuredErrorDetail).message === 'string'
  );
}

/**
 * Map backend error_code to our ErrorCode enum (Priority 3 fix)
 */
function mapBackendErrorCode(backendCode: string, status: number): ErrorCode {
  // Direct mapping for known backend codes
  const codeMap: Record<string, ErrorCode> = {
    'RECOMMENDATION_NOT_FOUND': ErrorCodes.RECOMMENDATION_NOT_FOUND,
    'RECOMMENDATION_EXPIRED': ErrorCodes.RECOMMENDATION_EXPIRED,
    'RECOMMENDATION_ALREADY_PROCESSED': ErrorCodes.RECOMMENDATION_ALREADY_PROCESSED,
    'PRODUCT_NOT_FOUND': ErrorCodes.PRODUCT_NOT_FOUND,
    'PRODUCT_NOT_LINKED': ErrorCodes.PRODUCT_NOT_LINKED,
    'INTEGRATION_NOT_FOUND': ErrorCodes.INTEGRATION_NOT_FOUND,
    'INTEGRATION_NOT_ACTIVE': ErrorCodes.INTEGRATION_NOT_ACTIVE,
    'PRICE_PUSH_FAILED': ErrorCodes.PRICE_PUSH_FAILED,
    'UNAUTHORIZED': ErrorCodes.UNAUTHORIZED,
    'VALIDATION_ERROR': ErrorCodes.VALIDATION_ERROR,
  };
  
  if (backendCode in codeMap) {
    return codeMap[backendCode];
  }
  
  // Fallback based on status code
  switch (status) {
    case 401: return ErrorCodes.AUTHENTICATION_ERROR;
    case 403: return ErrorCodes.AUTHORIZATION_ERROR;
    case 404: return ErrorCodes.NOT_FOUND;
    case 409: return ErrorCodes.VALIDATION_ERROR;
    case 410: return ErrorCodes.RECOMMENDATION_EXPIRED;
    case 422: return ErrorCodes.VALIDATION_ERROR;
    case 429: return ErrorCodes.RATE_LIMIT;
    case 502: return ErrorCodes.PRICE_PUSH_FAILED;
    default: return ErrorCodes.UNKNOWN_ERROR;
  }
}

function parseResponseError(status: number, data?: ApiErrorResponse): ParsedApiError {
  const detail = data?.detail;

  // ═══════════════════════════════════════════════════════════════════════════
  // Priority 3 FIX: Handle structured error responses from backend
  // Format: { detail: { message: "...", error_code: "..." } }
  // ═══════════════════════════════════════════════════════════════════════════
  if (isStructuredError(detail)) {
    const errorCode = mapBackendErrorCode(detail.error_code || '', status);
    return {
      code: errorCode,
      message: detail.message,
      suggestion: getSuggestionForErrorCode(errorCode),
      status,
    };
  }
  // ═══════════════════════════════════════════════════════════════════════════

  switch (status) {
    case 400:
      return {
        code: ErrorCodes.VALIDATION_ERROR,
        message: typeof detail === 'string' ? detail : 'Invalid request',
        status,
      };

    case 401:
      return {
        code: ErrorCodes.AUTHENTICATION_ERROR,
        message: 'Please log in to continue',
        suggestion: 'Your session may have expired',
        status,
      };

    case 403:
      return {
        code: ErrorCodes.AUTHORIZATION_ERROR,
        message: typeof detail === 'string' ? detail : 'You do not have permission to perform this action',
        status,
      };

    case 404:
      return {
        code: ErrorCodes.NOT_FOUND,
        message: typeof detail === 'string' ? detail : 'The requested resource was not found',
        status,
      };

    // NEW: Handle 409 Conflict (already processed)
    case 409:
      return {
        code: ErrorCodes.RECOMMENDATION_ALREADY_PROCESSED,
        message: typeof detail === 'string' ? detail : 'This action has already been completed',
        status,
      };

    // NEW: Handle 410 Gone (expired)
    case 410:
      return {
        code: ErrorCodes.RECOMMENDATION_EXPIRED,
        message: typeof detail === 'string' ? detail : 'This item has expired',
        suggestion: 'Please generate a new recommendation',
        status,
      };

    case 422:
      return parseValidationError(detail);

    case 429:
      return {
        code: ErrorCodes.RATE_LIMIT,
        message: 'Too many requests',
        suggestion: 'Please wait a moment before trying again',
        status,
      };

    // NEW: Handle 502 Bad Gateway (store push failed)
    case 502:
      return {
        code: ErrorCodes.PRICE_PUSH_FAILED,
        message: typeof detail === 'string' ? detail : 'Failed to update your store',
        suggestion: 'Please check your store connection in Settings → Integrations',
        status,
      };

    case 500:
    case 503:
    case 504:
      return {
        code: ErrorCodes.SERVER_ERROR,
        message: 'Server error. Please try again later.',
        suggestion: 'If the problem persists, please contact support',
        status,
      };

    default:
      return {
        code: ErrorCodes.UNKNOWN_ERROR,
        message: typeof detail === 'string' ? detail : 'An unexpected error occurred',
        status,
      };
  }
}

function parseValidationError(detail: string | ValidationErrorDetail[] | StructuredErrorDetail | undefined): ParsedApiError {
  if (!detail || typeof detail === 'string') {
    return {
      code: ErrorCodes.VALIDATION_ERROR,
      message: detail || 'Validation failed',
    };
  }

  // Handle structured error that slipped through
  if (isStructuredError(detail)) {
    return {
      code: ErrorCodes.VALIDATION_ERROR,
      message: detail.message,
    };
  }

  // Parse FastAPI validation errors into field-specific errors
  const fieldErrors: Record<string, string[]> = {};

  for (const err of detail as ValidationErrorDetail[]) {
    const field = err.loc[err.loc.length - 1]?.toString() || 'unknown';
    if (!fieldErrors[field]) {
      fieldErrors[field] = [];
    }
    fieldErrors[field].push(err.msg);
  }

  return {
    code: ErrorCodes.VALIDATION_ERROR,
    message: 'Please check your input',
    fieldErrors,
  };
}

/**
 * Get helpful suggestion based on error code (Priority 3 fix)
 */
function getSuggestionForErrorCode(code: ErrorCode): string | undefined {
  const suggestions: Partial<Record<ErrorCode, string>> = {
    [ErrorCodes.RECOMMENDATION_EXPIRED]: 'Please generate a new price recommendation',
    [ErrorCodes.RECOMMENDATION_ALREADY_PROCESSED]: 'Refresh the page to see the latest status',
    [ErrorCodes.INTEGRATION_NOT_FOUND]: 'Go to Settings → Integrations to connect your store',
    [ErrorCodes.INTEGRATION_NOT_ACTIVE]: 'Go to Settings → Integrations to reconnect your store',
    [ErrorCodes.PRODUCT_NOT_LINKED]: 'Go to Products → Edit → Link to Store',
    [ErrorCodes.PRICE_PUSH_FAILED]: 'Check your store connection in Settings → Integrations',
    [ErrorCodes.AUTHENTICATION_ERROR]: 'Your session may have expired',
    [ErrorCodes.RATE_LIMIT]: 'Please wait a moment before trying again',
  };
  return suggestions[code];
}

/**
 * Check if error is an integration-related error (WooCommerce, Shopify)
 */
export function isIntegrationError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return (
    parsed.code === ErrorCodes.INTEGRATION_ERROR ||
    parsed.code === ErrorCodes.INTEGRATION_NOT_FOUND ||
    parsed.code === ErrorCodes.INTEGRATION_NOT_ACTIVE ||
    parsed.code === ErrorCodes.PRODUCT_NOT_LINKED ||
    parsed.code === ErrorCodes.PRICE_PUSH_FAILED ||
    parsed.message.toLowerCase().includes('integration') ||
    parsed.message.toLowerCase().includes('woocommerce') ||
    parsed.message.toLowerCase().includes('shopify')
  );
}

/**
 * Check if error requires re-authentication
 */
export function isAuthError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return parsed.code === ErrorCodes.AUTHENTICATION_ERROR;
}

/**
 * Check if error is due to expired recommendation (Priority 3 fix)
 */
export function isExpiredError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return parsed.code === ErrorCodes.RECOMMENDATION_EXPIRED || parsed.status === 410;
}

/**
 * Check if error is due to already-processed recommendation (Priority 3 fix)
 */
export function isAlreadyProcessedError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return parsed.code === ErrorCodes.RECOMMENDATION_ALREADY_PROCESSED || parsed.status === 409;
}

/**
 * Check if error is due to store push failure (Priority 3 fix)
 */
export function isPricePushError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return parsed.code === ErrorCodes.PRICE_PUSH_FAILED || parsed.status === 502;
}

/**
 * Check if error might resolve with a retry (Priority 3 fix)
 */
export function isRetryableError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return (
    parsed.code === ErrorCodes.RATE_LIMIT ||
    parsed.code === ErrorCodes.SERVER_ERROR ||
    parsed.code === ErrorCodes.NETWORK_ERROR ||
    parsed.status === 429 ||
    parsed.status === 503 ||
    parsed.status === 504
  );
}

/**
 * Get user-friendly error message for display
 */
export function getErrorMessage(error: unknown): string {
  return parseApiError(error).message;
}

/**
 * Get both message and suggestion for toast display (Priority 3 fix)
 */
export function getErrorDetails(error: unknown): { message: string; suggestion?: string } {
  const parsed = parseApiError(error);
  return {
    message: parsed.message,
    suggestion: parsed.suggestion,
  };
}





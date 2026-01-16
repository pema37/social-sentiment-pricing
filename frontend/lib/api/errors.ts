// Centralized API error handling
// Components should NEVER parse errors themselves - use these utilities

export const ErrorCodes = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR: 'AUTHORIZATION_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  RATE_LIMIT: 'RATE_LIMIT',
  INTEGRATION_ERROR: 'INTEGRATION_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
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

interface ApiErrorResponse {
  detail?: string | ValidationErrorDetail[];
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

function parseResponseError(status: number, data?: ApiErrorResponse): ParsedApiError {
  const detail = data?.detail;

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
        message: 'You do not have permission to perform this action',
        status,
      };

    case 404:
      return {
        code: ErrorCodes.NOT_FOUND,
        message: typeof detail === 'string' ? detail : 'The requested resource was not found',
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

    case 500:
    case 502:
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

function parseValidationError(detail: string | ValidationErrorDetail[] | undefined): ParsedApiError {
  if (!detail || typeof detail === 'string') {
    return {
      code: ErrorCodes.VALIDATION_ERROR,
      message: detail || 'Validation failed',
    };
  }

  // Parse FastAPI validation errors into field-specific errors
  const fieldErrors: Record<string, string[]> = {};

  for (const err of detail) {
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
 * Check if error is an integration-related error (WooCommerce, Shopify)
 */
export function isIntegrationError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return (
    parsed.code === ErrorCodes.INTEGRATION_ERROR ||
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
 * Get user-friendly error message for display
 */
export function getErrorMessage(error: unknown): string {
  return parseApiError(error).message;
}




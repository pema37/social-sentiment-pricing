// User domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["UserResponse"], RegisterRequest, etc.

// ============================================
// USER TYPES
// ============================================

/**
 * User response from /auth/me and other endpoints
 * Matches: components["schemas"]["UserResponse"]
 */
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string | null;
}

// ============================================
// AUTH REQUEST TYPES
// ============================================

/**
 * Login request payload
 * Matches: components["schemas"]["LoginRequest"]
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Register request payload
 * Matches: components["schemas"]["RegisterRequest"]
 */
export interface RegisterCredentials {
  email: string;
  password: string;
  full_name?: string | null;
}

/**
 * Forgot password request
 * Matches: components["schemas"]["ForgotPasswordRequest"]
 */
export interface ForgotPasswordRequest {
  email: string;
}

/**
 * Reset password request
 * Matches: components["schemas"]["ResetPasswordRequest"]
 */
export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

/**
 * Refresh token request
 * Matches: components["schemas"]["RefreshRequest"]
 */
export interface RefreshRequest {
  refresh_token: string;
}

// ============================================
// AUTH RESPONSE TYPES
// ============================================

/**
 * Token response from login/refresh
 * Matches: components["schemas"]["TokenResponse"]
 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ============================================
// PROFILE UPDATE TYPES
// ============================================

/**
 * Update profile request
 */
export interface UpdateProfileRequest {
  full_name?: string | null;
  email?: string | null;
}

/**
 * Change password request
 */
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

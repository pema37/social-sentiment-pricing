// User type - represents a user from the backend database
export interface User {
  id: string;           // Unique identifier (UUID from your backend)
  email: string;        // User's email address
  full_name: string;    // User's display name
  is_active: boolean;   // Is the account active?
  is_superuser: boolean; // Is this an admin?
  created_at: string;   // When account was created (ISO date string)
  updated_at: string;   // When account was last modified
}

// What the login form sends to the backend
export interface LoginCredentials {
  email: string;        // User's email
  password: string;     // User's password
}

// What the register form sends to the backend
export interface RegisterCredentials {
  email: string;        // User's email
  password: string;     // User's password
  full_name: string;    // Extra field needed for registration
}

// What the backend returns after successful login
export interface AuthTokens {
  access_token: string; // The JWT token from your backend
  token_type: string;   // Usually "bearer"
}

// Update profile request
export interface UpdateProfileRequest {
  full_name?: string;
  email?: string;
}

// Change password request
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

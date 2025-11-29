// Token Management Utilities
// Handles storing/retrieving JWT tokens from browser localStorage

const TOKEN_KEY = 'ssp_access_token'; // Key used in localStorage

// Get the token from localStorage
export function getToken(): string | null {
  // Check if we're in the browser (not server-side rendering)
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

// Save the token to localStorage
export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

// Remove the token from localStorage (logout)
export function removeToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

// Check if user is authenticated (has a token)
export function isAuthenticated(): boolean {
  return !!getToken(); // Returns true if token exists
}

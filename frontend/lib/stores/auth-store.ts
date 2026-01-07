// frontend/lib/stores/auth-store.ts

/**
 * Auth Store - Global authentication state using Zustand
 * 
 * PATCHED (2025-01-07): Added refresh token support.
 * - Saves refresh_token on login
 * - Clears both tokens on logout
 */

import { create } from 'zustand';
import { getToken, setTokens, removeAllTokens } from '@/lib/auth/token';
import { authApi, ApiError } from '@/lib/api';
import type { User } from '@/types';

// Define the shape of our auth state
interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string, fullName: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

// Helper to extract error message
function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String((error as { message: unknown }).message);
  }
  return fallback;
}

// Create the store
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  
  login: async (email, password) => {
    try {
      // Call the login API
      const response = await authApi.login(email, password);
      
      // Save BOTH tokens to localStorage
      setTokens(response.access_token, response.refresh_token);
      
      // Fetch the user's profile data
      const user = await authApi.me();
      
      // Update state with user data
      set({ user, isAuthenticated: true });
      
      return { success: true };
    } catch (error: unknown) {
      const message = getErrorMessage(error, 'Login failed. Please try again.');
      return { success: false, error: message };
    }
  },
  
  register: async (email, password, fullName) => {
    try {
      await authApi.register(email, password, fullName);
      return { success: true };
    } catch (error: unknown) {
      const message = getErrorMessage(error, 'Registration failed. Please try again.');
      return { success: false, error: message };
    }
  },
  
  logout: () => {
    // Remove ALL tokens from localStorage
    removeAllTokens();
    // Clear user from state
    set({ user: null, isAuthenticated: false });
  },
  
  checkAuth: async () => {
    const token = getToken();
    
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    
    try {
      // Token exists - verify it's still valid
      // Note: If token is expired, the API client will auto-refresh it
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      // Token is invalid and refresh failed - clear everything
      removeAllTokens();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));


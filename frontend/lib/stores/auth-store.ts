// Auth Store - Global authentication state using Zustand
// This store keeps track of the logged-in user across the entire app

import { create } from 'zustand';
import { getToken, setToken, removeToken } from '@/lib/auth/token';
import { authApi, ApiError } from '@/lib/api';
import type { User } from '@/types';

// Define the shape of our auth state
interface AuthState {
  user: User | null;        // Current logged-in user (null if not logged in)
  isLoading: boolean;       // Are we checking auth status?
  isAuthenticated: boolean; // Is user logged in?
  
  // Actions - functions to modify state
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string, fullName: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

// Helper to extract error message from various error types
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
  // Initial state
  user: null,
  isLoading: true,          // Start as loading until we check auth
  isAuthenticated: false,
  
  // Login action
  login: async (email, password) => {
    try {
      // Call the login API
      const response = await authApi.login(email, password);
      
      // Save the token to localStorage
      setToken(response.access_token);
      
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
  
  // Register action
  register: async (email, password, fullName) => {
    try {
      // Call the register API
      await authApi.register(email, password, fullName);
      
      // Registration successful (user still needs to login)
      return { success: true };
    } catch (error: unknown) {
      const message = getErrorMessage(error, 'Registration failed. Please try again.');
      return { success: false, error: message };
    }
  },
  
  // Logout action
  logout: () => {
    // Remove token from localStorage
    removeToken();
    // Clear user from state
    set({ user: null, isAuthenticated: false });
  },
  
  // Check if user is already logged in (called on app startup)
  checkAuth: async () => {
    // Check if we have a token
    const token = getToken();
    
    // No token = not logged in
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    
    try {
      // We have a token - verify it's still valid by fetching user
      const user = await authApi.me();
      
      // Token is valid - user is logged in
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      // Token is invalid - clear it
      removeToken();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));



// Auth Store - Global authentication state using Zustand
// This store keeps track of the logged-in user across the entire app

import { create } from 'zustand';
import { getToken, setToken, removeToken } from '@/lib/auth/token';
import { authApi } from '@/lib/api/client';
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

// Create the store
export const useAuthStore = create<AuthState>((set) => ({
  // Initial state
  user: null,
  isLoading: true,          // Start as loading until we check auth
  isAuthenticated: false,
  
  // Login action
  login: async (email, password) => {
    // Call the login API
    const response = await authApi.login(email, password);
    
    // Handle login failure
    if (response.error || !response.data) {
      return { success: false, error: response.error || 'Login failed' };
    }
    
    // Save the token to localStorage
    setToken(response.data.access_token);
    
    // Fetch the user's profile data
    const userResponse = await authApi.me();
    if (userResponse.data) {
      // Update state with user data
      set({ user: userResponse.data as User, isAuthenticated: true });
    }
    
    return { success: true };
  },
  
  // Register action
  register: async (email, password, fullName) => {
    // Call the register API
    const response = await authApi.register(email, password, fullName);
    
    // Handle registration failure
    if (response.error) {
      return { success: false, error: response.error };
    }
    
    // Registration successful (user still needs to login)
    return { success: true };
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
    
    // We have a token - verify it's still valid by fetching user
    const response = await authApi.me();
    
    if (response.data) {
      // Token is valid - user is logged in
      set({ user: response.data as User, isAuthenticated: true, isLoading: false });
    } else {
      // Token is invalid - clear it
      removeToken();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));

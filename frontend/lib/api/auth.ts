// frontend/lib/api/auth.ts

/**
 * Auth API functions.
 * 
 * PATCHED (2025-01-07): Updated LoginResponse to include refresh_token.
 */

import { api } from './client';
import type { User, UpdateProfileRequest, ChangePasswordRequest } from '@/types';

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;  // NEW: Refresh token from backend
  token_type: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
}

export const authApi = {
  // Authentication
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/api/v1/auth/login', { email, password }),

  register: (email: string, password: string, fullName: string) =>
    api.post<RegisterResponse>('/api/v1/auth/register', {
      email,
      password,
      full_name: fullName,
    }),

  me: () => api.get<User>('/api/v1/auth/me'),

  // NEW: Refresh tokens
  refresh: (refreshToken: string) =>
    api.post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),

  // Profile management
  updateProfile: (data: UpdateProfileRequest) =>
    api.put<User>('/api/v1/users/me', data),

  changePassword: (data: ChangePasswordRequest) =>
    api.post<{ message: string }>('/api/v1/users/me/change-password', data),
};



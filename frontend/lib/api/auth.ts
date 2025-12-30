// Auth API
import { api } from './client';
import type { User, UpdateProfileRequest, ChangePasswordRequest } from '@/types';

export interface LoginResponse {
  access_token: string;
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

  // Profile management
  updateProfile: (data: UpdateProfileRequest) =>
    api.put<User>('/api/v1/users/me', data),

  changePassword: (data: ChangePasswordRequest) =>
    api.post<{ message: string }>('/api/v1/users/me/change-password', data),
};

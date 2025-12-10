// Auth API
import { api } from './client';

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/api/v1/auth/login', { email, password }),

  register: (email: string, password: string, fullName: string) =>
    api.post<RegisterResponse>('/api/v1/auth/register', {
      email,
      password,
      full_name: fullName,
    }),

  me: () => api.get<User>('/api/v1/auth/me'),
};

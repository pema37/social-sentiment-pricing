// frontend/lib/domain/__tests__/auth.test.ts

import { describe, it, expect } from 'vitest';
import { server } from '@/lib/testing';
import { http, HttpResponse } from 'msw';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const api = (path: string) => `${API}/api/v1${path}`;

describe('Auth API Contract', () => {
  describe('POST /auth/login', () => {
    it('returns access_token and token_type on success', async () => {
      const res = await fetch(api('/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.com', password: 'Test1234!' }),
      });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('access_token');
      expect(data).toHaveProperty('token_type', 'bearer');
    });

    it('returns 401 on invalid credentials', async () => {
      server.use(
        http.post(api('/auth/login'), () =>
          HttpResponse.json(
            { detail: 'Invalid email or password' },
            { status: 401 }
          )
        )
      );

      const res = await fetch(api('/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'wrong@example.com', password: 'bad' }),
      });

      expect(res.status).toBe(401);
    });
  });

  describe('POST /auth/register', () => {
    it('returns user object on success', async () => {
      const res = await fetch(api('/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'new@example.com',
          password: 'Test1234!',
          full_name: 'New User',
        }),
      });

      expect(res.status).toBe(201);
      const data = await res.json();
      expect(data).toHaveProperty('id');
      expect(data).toHaveProperty('email');
      expect(data).toHaveProperty('is_active', true);
    });

    it('returns 409 on duplicate email', async () => {
      server.use(
        http.post(api('/auth/register'), () =>
          HttpResponse.json(
            { detail: 'Email already registered' },
            { status: 409 }
          )
        )
      );

      const res = await fetch(api('/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'existing@example.com',
          password: 'Test1234!',
          full_name: 'Duplicate',
        }),
      });

      expect(res.status).toBe(409);
    });
  });

  describe('GET /auth/me', () => {
    it('returns current user profile', async () => {
      const res = await fetch(api('/auth/me'), {
        headers: { Authorization: 'Bearer fake-jwt-token' },
      });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('id');
      expect(data).toHaveProperty('email');
      expect(data).toHaveProperty('full_name');
      expect(data).toHaveProperty('role');
    });

    it('returns 401 without token', async () => {
      server.use(
        http.get(api('/auth/me'), () =>
          HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
        )
      );

      const res = await fetch(api('/auth/me'));
      expect(res.status).toBe(401);
    });
  });
});



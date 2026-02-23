// frontend/lib/domain/__tests__/pricing-contracts.test.ts

import { describe, it, expect } from 'vitest';
import { server } from '@/lib/testing';
import { http, HttpResponse } from 'msw';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const api = (path: string) => `${API}/api/v1${path}`;
const authHeader = { Authorization: 'Bearer fake-jwt-token' };

describe('Pricing API Contract', () => {
  describe('GET /pricing/rules', () => {
    it('returns array of pricing rules', async () => {
      const res = await fetch(api('/pricing/rules'), { headers: authHeader });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(Array.isArray(data)).toBe(true);
    });

    it('each rule has required fields', async () => {
      const res = await fetch(api('/pricing/rules'), { headers: authHeader });
      const data = await res.json();
      const rule = data[0];

      expect(rule).toHaveProperty('id');
      expect(rule).toHaveProperty('name');
      expect(rule).toHaveProperty('rule_type');
      expect(rule).toHaveProperty('action');
      expect(rule).toHaveProperty('action_value');
      expect(rule).toHaveProperty('is_active');
      expect(rule).toHaveProperty('priority');
      expect(rule).toHaveProperty('cooldown_hours');
    });

    it('returns empty array when no rules', async () => {
      server.use(
        http.get(api('/pricing/rules'), () => HttpResponse.json([]))
      );

      const res = await fetch(api('/pricing/rules'), { headers: authHeader });
      const data = await res.json();
      expect(data).toHaveLength(0);
    });
  });

  describe('POST /pricing/rules', () => {
    it('creates a rule and returns it with id', async () => {
      const newRule = {
        name: 'New Rule',
        rule_type: 'sentiment_threshold',
        action: 'increase_percent',
        action_value: '5.0',
        is_active: true,
        priority: 0,
        cooldown_hours: 24,
      };

      const res = await fetch(api('/pricing/rules'), {
        method: 'POST',
        headers: { ...authHeader, 'Content-Type': 'application/json' },
        body: JSON.stringify(newRule),
      });

      expect(res.status).toBe(201);
      const data = await res.json();
      expect(data).toHaveProperty('id');
      expect(data.name).toBe('New Rule');
      expect(data.rule_type).toBe('sentiment_threshold');
    });

    it('returns 422 on invalid payload', async () => {
      server.use(
        http.post(api('/pricing/rules'), () =>
          HttpResponse.json(
            { detail: [{ loc: ['body', 'name'], msg: 'field required' }] },
            { status: 422 }
          )
        )
      );

      const res = await fetch(api('/pricing/rules'), {
        method: 'POST',
        headers: { ...authHeader, 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      expect(res.status).toBe(422);
    });
  });

  describe('GET /pricing/recommendations', () => {
    it('returns paginated recommendations', async () => {
      const res = await fetch(api('/pricing/recommendations'), { headers: authHeader });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('items');
      expect(data).toHaveProperty('total');
      expect(data).toHaveProperty('page');
    });
  });

  describe('GET /pricing/settings', () => {
    it('returns pricing settings with required fields', async () => {
      const res = await fetch(api('/pricing/settings'), { headers: authHeader });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('auto_pricing_enabled');
      expect(data).toHaveProperty('max_auto_changes_per_day');
      expect(data).toHaveProperty('global_min_margin_percent');
    });
  });
});



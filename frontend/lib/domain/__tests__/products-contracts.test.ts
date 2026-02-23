// frontend/lib/domain/__tests__/products-contracts.test.ts

import { describe, it, expect } from 'vitest';
import { server } from '@/lib/testing';
import { http, HttpResponse } from 'msw';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const api = (path: string) => `${API}/api/v1${path}`;
const authHeader = { Authorization: 'Bearer fake-jwt-token' };

describe('Products API Contract', () => {
  describe('GET /products/', () => {
    it('returns paginated product list', async () => {
      const res = await fetch(api('/products/'), { headers: authHeader });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data).toHaveProperty('items');
      expect(data).toHaveProperty('total');
      expect(data).toHaveProperty('page');
      expect(data).toHaveProperty('per_page');
      expect(data).toHaveProperty('pages');
      expect(Array.isArray(data.items)).toBe(true);
    });

    it('each product has required fields', async () => {
      const res = await fetch(api('/products/'), { headers: authHeader });
      const data = await res.json();
      const product = data.items[0];

      expect(product).toHaveProperty('id');
      expect(product).toHaveProperty('name');
      expect(product).toHaveProperty('sku');
      expect(product).toHaveProperty('current_price');
      expect(product).toHaveProperty('is_active');
      expect(product).toHaveProperty('created_at');
    });

    it('returns empty list when no products', async () => {
      server.use(
        http.get(api('/products/'), () =>
          HttpResponse.json({
            items: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0,
          })
        )
      );

      const res = await fetch(api('/products/'), { headers: authHeader });
      const data = await res.json();
      expect(data.items).toHaveLength(0);
      expect(data.total).toBe(0);
    });
  });

  describe('GET /products/:id', () => {
    it('returns single product by id', async () => {
      const res = await fetch(api('/products/prod-001'), { headers: authHeader });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data.id).toBe('prod-001');
      expect(data).toHaveProperty('name');
      expect(data).toHaveProperty('current_price');
    });

    it('returns 404 for unknown product', async () => {
      server.use(
        http.get(api('/products/:id'), () =>
          HttpResponse.json(
            { detail: 'Product not found' },
            { status: 404 }
          )
        )
      );

      const res = await fetch(api('/products/nonexistent'), { headers: authHeader });
      expect(res.status).toBe(404);
    });
  });
});



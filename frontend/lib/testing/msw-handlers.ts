// frontend/lib/testing/msw-handlers.ts

import { http, HttpResponse } from 'msw';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const api = (path: string) => `${API}/api/v1${path}`;

// ── Factories ──────────────────────────────────────────────
export const fakeUser = (overrides = {}) => ({
  id: 'user-001',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'USER',
  is_active: true,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  ...overrides,
});

export const fakeProduct = (overrides = {}) => ({
  id: 'prod-001',
  user_id: 'user-001',
  name: 'Test Product',
  sku: 'TEST-001',
  current_price: 29.99,
  base_price: 29.99,
  cost: 12.0,
  category: 'Electronics',
  is_active: true,
  auto_pricing_enabled: false,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  ...overrides,
});

export const fakePricingRule = (overrides = {}) => ({
  id: 'rule-001',
  user_id: 'user-001',
  name: 'Test Rule',
  rule_type: 'sentiment_threshold',
  action: 'increase_percent',
  action_value: '5.0',
  is_active: true,
  priority: 0,
  sentiment_threshold: '0.5',
  sentiment_direction: 'above',
  max_change_percent: '10.0',
  min_price: null,
  max_price: null,
  cooldown_hours: 24,
  applies_to_products: [],
  applies_to_categories: [],
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  ...overrides,
});

// ── Handlers ───────────────────────────────────────────────
export const handlers = [
  // Auth
  http.post(api('/auth/login'), () =>
    HttpResponse.json({
      access_token: 'fake-jwt-token',
      token_type: 'bearer',
    })
  ),

  http.post(api('/auth/register'), () =>
    HttpResponse.json(fakeUser(), { status: 201 })
  ),

  http.get(api('/auth/me'), () =>
    HttpResponse.json(fakeUser())
  ),

  // Products
  http.get(api('/products/'), ({ request }) => {
    const url = new URL(request.url);
    const page = Number(url.searchParams.get('page') ?? 1);
    return HttpResponse.json({
      items: [fakeProduct(), fakeProduct({ id: 'prod-002', name: 'Product 2', sku: 'TEST-002' })],
      total: 2,
      page,
      per_page: 20,
      pages: 1,
    });
  }),

  http.get(api('/products/:id'), ({ params }) =>
    HttpResponse.json(fakeProduct({ id: params.id }))
  ),

  // Pricing Rules
  http.get(api('/pricing/rules'), () =>
    HttpResponse.json([fakePricingRule()])
  ),


  http.post(api('/pricing/rules'), async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      fakePricingRule({ ...(body ?? {}), id: 'rule-new' }),
      { status: 201 }
    );
  }),

  http.get(api('/pricing/recommendations'), () =>
    HttpResponse.json({ items: [], total: 0, page: 1, per_page: 20, pages: 0 })
  ),

  // Pricing Settings
  http.get(api('/pricing/settings'), () =>
    HttpResponse.json({
      id: 'settings-001',
      user_id: 'user-001',
      auto_pricing_enabled: false,
      max_auto_changes_per_day: 5,
      global_min_margin_percent: 10.0,
    })
  ),
];



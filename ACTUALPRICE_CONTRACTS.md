# ActualPrice (SSP) Contracts

> **Purpose:** Single source of truth for all API contracts, types, and patterns.
> **Rule:** Update this file BEFORE writing code. Load into every Claude conversation.
> **Last Updated:** January 13, 2026

---

## 📋 Project Overview

**Name:** ActualPrice (Social Sentiment Pricing / SSP)
**Description:** AI-powered dynamic pricing based on social sentiment analysis for e-commerce merchants
**Stack:** FastAPI + Next.js + PostgreSQL + Redis + Celery
**Platforms:** Shopify, WooCommerce

---

## 🔗 API Endpoints

### Auth (`/api/v1/auth`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | /register | `{ email, password, full_name }` | `{ user, access_token, refresh_token }` | |
| POST | /login | `{ email, password }` | `{ user, access_token, refresh_token }` | |
| POST | /logout | - | `{ success }` | |
| POST | /refresh | `{ refresh_token }` | `{ access_token }` | |
| GET | /me | - | `User` | Requires auth |
| POST | /forgot-password | `{ email }` | `{ message }` | |
| POST | /reset-password | `{ token, new_password }` | `{ success }` | |

### Products (`/api/v1/products`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | `?page, page_size, search` | `PaginatedResponse<Product>` | |
| POST | / | `ProductCreate` | `Product` | |
| GET | /{id} | - | `Product` | |
| PUT | /{id} | `ProductUpdate` | `Product` | |
| DELETE | /{id} | - | `{ success }` | Cascades to links, history |
| GET | /{id}/sentiment | - | `SentimentData` | |
| GET | /{id}/price-history | - | `PriceHistory[]` | |
| GET | /{id}/price-suggestion | - | `PriceSuggestion` | AI-generated |
| POST | /{id}/apply-price | `{ price }` | `Product` | |
| POST | /{id}/keywords | `{ keywords: string[] }` | `Product` | |
| POST | /import | `{ products: ProductCreate[] }` | `{ created, failed }` | Bulk import |

### Sentiment (`/api/v1/sentiment`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /mentions | `?product_id, page, page_size` | `PaginatedResponse<SocialMention>` | |
| GET | /aggregate | `?product_id, period` | `AggregatedSentiment` | |
| GET | /trends | `?product_id` | `TrendData` | |
| POST | /analyze | `{ text }` | `SentimentResult` | Single text analysis |
| GET | /product/{id} | - | `SentimentHistory` | |
| GET | /product/{id}/stats | - | `SentimentStats` | |

### Pricing Rules (`/api/v1/pricing/rules`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | `?page, page_size` | `PaginatedResponse<PricingRule>` | |
| POST | / | `PricingRuleCreate` | `PricingRule` | product_id optional based on scope |
| GET | /{id} | - | `PricingRule` | |
| PUT | /{id} | `PricingRuleUpdate` | `PricingRule` | |
| DELETE | /{id} | - | `{ success }` | |
| POST | /{id}/test | - | `TestResult` | Test rule against data |

### Pricing Recommendations (`/api/v1/pricing/recommendations`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | `?status, page, page_size` | `PaginatedResponse<Recommendation>` | |
| GET | /{id} | - | `Recommendation` | |
| POST | /{id}/approve | - | `Recommendation` | |
| POST | /{id}/reject | `{ reason? }` | `Recommendation` | |
| POST | /{id}/apply | - | `Recommendation` | Push to store |

### Pricing Settings (`/api/v1/pricing/settings`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | - | `PricingSettings` | |
| PUT | / | `PricingSettingsUpdate` | `PricingSettings` | |

### Alerts (`/api/v1/alerts`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | `?status, severity, page` | `PaginatedResponse<Alert>` | Static route |
| GET | /stats | - | `AlertStats` | Static route - BEFORE /{id} |
| POST | /crisis-detection | `{ product_id? }` | `CrisisReport` | Static route - BEFORE /{id} |
| GET | /{id} | - | `Alert` | Dynamic route - LAST |
| POST | /{id}/acknowledge | - | `Alert` | |
| POST | /{id}/resolve | `{ resolution_notes? }` | `Alert` | |

### Alert Configurations (`/api/v1/alerts/configurations`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | - | `AlertConfiguration[]` | |
| POST | / | `AlertConfigCreate` | `AlertConfiguration` | |
| GET | /{id} | - | `AlertConfiguration` | |
| PUT | /{id} | `AlertConfigUpdate` | `AlertConfiguration` | |
| DELETE | /{id} | - | `{ success }` | |

### Competitors (`/api/v1/competitors`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | `?page, page_size` | `PaginatedResponse<Competitor>` | |
| POST | / | `CompetitorCreate` | `Competitor` | |
| GET | /{id} | - | `Competitor` | |
| PUT | /{id} | `CompetitorUpdate` | `Competitor` | |
| DELETE | /{id} | - | `{ success }` | |
| GET | /{id}/products | - | `CompetitorProduct[]` | |
| GET | /{id}/price-history | - | `CompetitorPriceHistory[]` | |
| POST | /{id}/scrape | - | `ScrapeResult` | Trigger manual scrape |
| POST | /{id}/ai-analysis | - | `AIAnalysis` | AI competitor analysis |

### Integrations (`/api/v1/integrations`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | - | `Integration[]` | |
| GET | /{id} | - | `Integration` | |
| DELETE | /{id} | - | `{ success }` | Disconnect |
| POST | /{id}/sync | `{ sync_type }` | `SyncStatusResponse` | Trigger sync (PULL) |
| POST | /{id}/push-prices | - | `PushResult` | Push prices (PUSH) |
| GET | /{id}/sync/status | - | `SyncStatusResponse` | |
| GET | /{id}/sync/logs | `?page, page_size` | `PaginatedResponse<SyncLog>` | |
| GET | /{id}/links | - | `ProductIntegrationLink[]` | |

### Integration OAuth (`/api/v1/integrations`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /shopify/auth-url | `{ shop }` | `{ auth_url }` | |
| GET | /shopify/callback | `?code, shop, state` | Redirect | |
| POST | /woocommerce/connect | `{ store_url, consumer_key, consumer_secret }` | `Integration` | Direct credentials |

### Analytics (`/api/v1/analytics`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /dashboard | - | `DashboardMetrics` | |
| GET | /revenue-impact | `?period` | `RevenueImpact` | |
| GET | /price-performance | `?period` | `PricePerformance` | |
| GET | /sentiment-correlation | - | `CorrelationData` | |

### Market Trends (`/api/v1/market-trends`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /analysis | `?product_id` | `MarketTrends` | AI analysis |

### Support (`/api/v1/support`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | /chat | `{ message, context? }` | `AIResponse` | AI support chat |

### Health (`/api/v1/health`)
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | / | - | `{ status, version }` | |
| GET | /detailed | - | `{ db, redis, services }` | |

---

## 📦 Types / Schemas


## 🔄 Type Generation

**Command:**
```bash
cd frontend && npm run generate-api-types
```

**How it works:**
- Backend Pydantic schemas → FastAPI auto-generates `/openapi.json` → `openapi-typescript` converts to TypeScript
- Generated file: `frontend/types/api-generated.ts`
- Run whenever backend schemas change

**Usage:**
```typescript
import type { components } from '@/types/api-generated';
type Product = components['schemas']['ProductRead'];
```


### Shared Types
```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface BaseEntity {
  id: string;           // UUID
  created_at: string;   // ISO datetime
  updated_at: string;   // ISO datetime
}
```

### User
```typescript
interface User extends BaseEntity {
  email: string;
  full_name: string;
  is_active: boolean;
  eth_wallet_address?: string;
}
```

### Product
```typescript
interface Product extends BaseEntity {
  user_id: string;
  name: string;
  sku: string;
  description?: string;
  category?: string;
  base_price: number;
  current_price: number;
  cost?: number;
  margin_floor?: number;
  keywords?: string[];
  image_url?: string;
  is_active: boolean;
}

interface ProductCreate {
  name: string;
  sku: string;
  description?: string;
  category?: string;
  base_price: number;
  current_price?: number;  // Defaults to base_price
  cost?: number;
  margin_floor?: number;
  keywords?: string[];
}
```

### Pricing Rule
```typescript
type RuleType = 'sentiment_threshold' | 'competitor_relative' | 'time_based' | 'volume_surge';
type ScopeType = 'single' | 'category' | 'all';

interface PricingRule extends BaseEntity {
  user_id: string;
  name: string;
  rule_type: RuleType;
  scope_type: ScopeType;
  product_id?: string;        // Required only if scope_type === 'single'
  category?: string;          // Used if scope_type === 'category'
  conditions: RuleCondition[];
  adjustment_percent: number;
  min_price?: number;
  max_price?: number;
  is_active: boolean;
  priority: number;
}

interface PricingRuleCreate {
  name: string;
  rule_type: RuleType;
  scope_type?: ScopeType;     // Defaults to 'single'
  product_id?: string;        // OPTIONAL - only needed for scope_type 'single'
  category?: string;
  conditions: RuleCondition[];
  adjustment_percent: number;
  min_price?: number;
  max_price?: number;
  is_active?: boolean;
  priority?: number;
}
```

### Recommendation
```typescript
type RecommendationStatus = 'pending' | 'approved' | 'rejected' | 'applied' | 'auto_approved';

interface PriceRecommendation extends BaseEntity {
  product_id: string;
  rule_id?: string;
  current_price: number;
  recommended_price: number;
  change_percent: number;
  confidence_score: number;
  reasoning: string;
  status: RecommendationStatus;
  applied_at?: string;
}
```

### Alert
```typescript
type AlertType = 'sentiment_drop' | 'sentiment_spike' | 'volume_surge' | 'viral_mention' | 
                 'competitor_price_change' | 'price_recommendation' | 'trend_detected';
type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
type AlertStatus = 'active' | 'acknowledged' | 'resolved';

interface Alert extends BaseEntity {
  user_id: string;
  product_id?: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  message: string;
  data?: Record<string, any>;
  acknowledged_at?: string;
  resolved_at?: string;
}
```

### Integration
```typescript
type EcommercePlatform = 'shopify' | 'woocommerce';
type IntegrationStatus = 'active' | 'error' | 'paused' | 'disconnected';
type SyncStatus = 'idle' | 'syncing' | 'error';

interface Integration extends BaseEntity {
  user_id: string;
  platform: EcommercePlatform;
  store_url: string;
  store_name?: string;
  status: IntegrationStatus;
  sync_status: SyncStatus;
  last_sync_at?: string;
  products_synced: number;
  error_message?: string;
}

interface ProductIntegrationLink extends BaseEntity {
  product_id: string;
  integration_id: string;
  external_product_id: string;
  external_variant_id?: string;
  external_price?: number;
  sync_enabled: boolean;
  last_price_push_at?: string;
  last_price_pull_at?: string;
}
```

### Sentiment
```typescript
type SentimentLabel = 'positive' | 'negative' | 'neutral';
type Platform = 'twitter' | 'reddit' | 'instagram' | 'facebook' | 'news';

interface SocialMention extends BaseEntity {
  product_id: string;
  platform: Platform;
  content: string;
  author?: string;
  url?: string;
  sentiment_score: number;    // -1.0 to 1.0
  sentiment_label: SentimentLabel;
  engagement_count: number;
  posted_at: string;
}

interface SentimentStats {
  average_score: number;
  total_mentions: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  trend_direction: 'up' | 'down' | 'stable';
}
```

### Competitor
```typescript
interface Competitor extends BaseEntity {
  user_id: string;
  name: string;
  website_url: string;
  description?: string;
  is_active: boolean;
}

interface CompetitorProduct extends BaseEntity {
  competitor_id: string;
  product_id?: string;        // Linked SSP product
  name: string;
  url: string;
  current_price: number;
  last_scraped_at?: string;
}
```
### Payment Schemas (updated)
- `network` field added: `"ethereum" | "bsv"` (default: "bsv")
- `full_name` added to user response schemas

---

## 🛣️ Route Ordering Rules

**CRITICAL: Static paths BEFORE dynamic paths. Always.**

```python
# ✅ CORRECT - alerts/__init__.py
router.include_router(configurations_router)  # /configurations/*
router.include_router(crisis_router)          # /crisis-detection (STATIC)
router.include_router(management_router)      # /{alert_id} (DYNAMIC LAST)

# ❌ WRONG
router.include_router(management_router)      # /{alert_id} catches everything!
router.include_router(crisis_router)          # Never reached
```

**Current SSP Route Structure:**
```
backend/api/v1/routes/
├── alerts/
│   ├── __init__.py           # Combines routers in correct order
│   ├── configurations.py     # /configurations/* (included first)
│   ├── crisis_detection.py   # /crisis-detection (static, before management)
│   └── management.py         # /{alert_id} (dynamic, LAST)
├── integrations/
│   ├── __init__.py
│   ├── oauth.py              # /shopify/*, /woocommerce/*
│   ├── crud.py               # /, /{id}
│   ├── sync.py               # /{id}/sync, /{id}/push-prices
│   ├── links.py              # /{id}/links
│   └── operations.py         # /{id}/push-price (singular)
├── pricing/
│   ├── __init__.py
│   ├── rules.py
│   ├── recommendations.py
│   └── settings.py
└── ...
```

---

## ⚠️ Known Gotchas

### Backend
| Issue | Solution |
|-------|----------|
| Route ordering | Static before dynamic. Split files if needed. |
| `product_id` in rules | Optional - only required when `scope_type === 'single'` |
| Sync vs Push | `SyncService` = PULL from platform. `PricePushService` = PUSH to platform. |
| Sync timeout | 300 seconds max. Uses `asyncio.wait_for()`. |
| WooCommerce creds | Format: `consumer_key` and `consumer_secret` (not combined) |
| UUID validation | FastAPI auto-validates. Returns 422 if invalid format. |
| Price comparison | Use $0.01 tolerance for float comparison |

### Frontend
| Issue | Solution |
|-------|----------|
| Type mismatches | Frontend types in `frontend/types/` must match backend schemas |
| Optional fields | Handle `null` and `undefined` separately |
| Cache invalidation | Invalidate React Query cache after mutations |
| Auth token | Stored in memory via Zustand, refresh via httpOnly cookie |

### Integration Services
| Issue | Solution |
|-------|----------|
| Shopify OAuth | Requires app credentials in env vars |
| WooCommerce | Direct API key connection, no OAuth |
| Webhook verification | Shopify uses HMAC, WooCommerce uses secret header |
| Rate limiting | Platform-specific. Circuit breaker prevents cascade failures. |

---

## 🔄 Request/Response Patterns

### Success Response
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

### Validation Error (422)
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Paginated Response
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

### Sync Status Response
```json
{
  "integration_id": "uuid",
  "sync_status": "syncing",
  "last_sync_at": "2025-01-01T00:00:00Z",
  "products_synced": 42
}
```

### Push Prices Response
```json
{
  "total": 10,
  "pushed": 8,
  "failed": 1,
  "skipped": 1,
  "errors": [{ "product_id": "uuid", "error": "..." }]
}
```

---

## 📁 File Structure

```
social-sentiment-pricing/
├── backend/
│   ├── api/v1/routes/
│   │   ├── alerts/           # Split: configurations, crisis_detection, management
│   │   ├── integrations/     # Split: oauth, crud, sync, links, operations
│   │   ├── pricing/          # Split: rules, recommendations, settings
│   │   ├── competitors/
│   │   ├── sentiment/
│   │   └── *.py              # Other routes
│   ├── models/               # SQLModel database models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/
│   │   ├── integration/      # SyncService (PULL), PricePushService (PUSH)
│   │   ├── pricing/          # Recommendation, approval, rules
│   │   ├── notification/     # Alerts, email, slack
│   │   └── *.py
│   ├── core/                 # Config, deps, security, middleware
│   ├── workers/              # Celery tasks
│   └── main.py
├── frontend/
│   ├── app/                  # Next.js App Router pages
│   │   ├── (auth)/           # Login, register, forgot-password
│   │   └── (dashboard)/      # All authenticated pages
│   ├── components/
│   │   ├── features/         # Feature-specific components
│   │   ├── layout/           # Shell, sidebar, topbar
│   │   └── ui/               # Reusable UI components
│   ├── lib/
│   │   ├── api/              # API client functions
│   │   └── hooks/            # React Query hooks
│   └── types/                # TypeScript type definitions
└── CONTRACTS.md              # This file
```

---

## ✅ Workflow Checklist

### Before coding a new feature:
- [ ] Define endpoint(s) in this file
- [ ] Define types/schemas in this file
- [ ] Check for route ordering issues
- [ ] Note any gotchas

### Before editing existing code:
- [ ] Paste current file contents to Claude
- [ ] State assumptions, get confirmation
- [ ] Make ONE change at a time
- [ ] Test before moving on

### After completing a feature:
- [ ] Update this file with any new gotchas
- [ ] Verify types match frontend ↔ backend
- [ ] Test happy path AND edge cases
- [ ] Have David try to break it

---

## 📝 Change Log

| Date | Change | Files Affected |
|------|--------|----------------|
| 2026-01-03 | Initial contracts document | All |
| 2026-01-03 | Fixed pricing rules (optional product_id) | rules.py |
| 2026-01-03 | Split alerts routes (route ordering fix) | alerts/*.py |
| 2026-01-03 | Split sync/push services | sync_service.py, price_push_service.py |
| 2026-01-03 | Added sync timeout (300s) | sync_service.py |
| 2026-01-13 | Set up openapi-typescript type generation | frontend/package.json, types/api-generated.ts |
| 2026-01-13 | Regenerated types from staging (network, full_name fields) | types/api-generated.ts |

---

## 🚀 Quick Reference

**Start the backend:**
```bash
cd backend && uvicorn main:app --reload
```

**Start the frontend:**
```bash
cd frontend && npm run dev
```

**Run migrations:**
```bash
cd backend && alembic upgrade head
```

**API docs:**
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Staging URLs:**
- Frontend: https://ssp-staging.vercel.app
- Backend: https://social-sentiment-pricing-staging-2ecd.up.railway.app
- OpenAPI: https://social-sentiment-pricing-staging-2ecd.up.railway.app/openapi.json

**Production URLs:**
- Frontend: https://actualprice.com (or your domain)
- Backend: ⚠️ NEEDS FIX - ssp-api-production serving wrong app


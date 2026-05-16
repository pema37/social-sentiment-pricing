# Contributing to ActualPrice (Social Sentiment Pricing)

Welcome to ActualPrice — an AI-driven Social Sentiment Pricing platform for e-commerce.
This document explains how we work. Read the whole thing before writing any code.

---

## Branch Workflow

We use two branches:

- **`main`** — Production. Deploys to `social-sentiment-pricing.vercel.app` (frontend) and production Railway service (backend). Never push directly to main.
- **`develop`** — Staging. Deploys to `ssp-staging.vercel.app` (frontend) and `ssp-staging` Railway service (backend). All work merges here first.

**How to work:**

1. Pull the latest `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   ```
2. Create a feature branch off `develop`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Do your work. Commit with clear messages (see conventions below).
4. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```
5. Open a Pull Request targeting `develop` on GitHub.
6. Wait for review. All PRs are reviewed within 24 hours.
7. After approval and merge, verify on staging (`ssp-staging.vercel.app`).

The project lead merges `develop` → `main` weekly when staging is stable. No one else merges to main.

---

## Branch Naming

Branch names follow this pattern:

```
feature/short-description     — New functionality
fix/short-description         — Bug fixes
test/short-description        — Adding or updating tests
refactor/short-description    — Code restructuring (no behavior change)
docs/short-description        — Documentation only
```

Examples from our history:
- `feature/sentiment-edge-cases`
- `fix/shopify-nullable-userid`
- `test/pricing-pipeline-coverage`
- `docs/update-api-reference`

---

## Commit Messages

We use conventional commits. Every commit message starts with a type prefix:

```
feat: add Shopify install flow detection
fix: make user_id nullable + handle Shopify install without state
test: add 128-test backend suite covering trust scoring
refactor: extract pricing form transformations to domain layer
docs: update privacy policy with crypto payment data section
```

Rules:
- Prefix is **lowercase**
- Message describes **what changed**, not how
- Keep it under 72 characters
- One logical change per commit

---

## Pull Request Requirements

Every PR must include:

1. **Title** following commit convention (e.g., `feat: add competitor price comparison endpoint`)
2. **Description** — What changed and why. 2-3 sentences minimum.
3. **Tests pass locally** — Run `pytest` from the backend directory. All 4,900+ tests must pass.
4. **No lint errors** — Backend and frontend should have zero errors.
5. **Screenshot** — Required for any frontend/UI changes.

PRs that break existing tests will not be merged.

---

## Project Structure

```
social-sentiment-pricing/
├── backend/                    # FastAPI + Python
│   ├── main.py                 # App entrypoint
│   ├── core/
│   │   ├── config.py           # Settings, env vars, constants
│   │   └── security.py         # JWT, password hashing, auth
│   ├── db/
│   │   └── session.py          # Database engine + session dependency
│   ├── models/                 # SQLModel database tables (21 models)
│   ├── schemas/                # Pydantic request/response DTOs (22 files)
│   ├── api/v1/routes/          # HTTP endpoints (32 route files + 8 sub-packages, ~150 endpoints)
│   ├── services/               # Business logic layer (100+ files across ~15 domain folders)
│   ├── integrations/           # Shopify, WooCommerce, MNEE
│   ├── workers/                # Celery background tasks
│   └── alembic/                # Database migrations
├── frontend/                   # Next.js 16 + TypeScript
│   ├── app/
│   │   ├── (auth)/             # Login, register, forgot password
│   │   └── (dashboard)/        # All protected pages
│   ├── components/
│   │   ├── layout/             # Sidebar, Topbar, Shells
│   │   ├── ui/                 # Button, Card, Input (shadcn/ui)
│   │   └── features/           # Domain components (products/, sentiment/)
│   ├── lib/
│   │   ├── api/                # API client + React Query hooks
│   │   ├── auth/               # Token management
│   │   └── stores/             # Zustand state stores
│   └── types/                  # TypeScript type definitions
├── CONTRIBUTING.md             # This file
├── DEVELOPER_SETUP.md          # Local environment setup guide
├── ACTUALPRICE_CONTRACTS.md    # API contracts and semantic definitions
└── README.md                   # Project overview
```

---

## Hard Rules

These are non-negotiable. Breaking them means your PR will be rejected.

### Backend Rules

1. **No new top-level folders** without explicit approval from the project lead.
   Use only: `core/`, `db/`, `models/`, `schemas/`, `api/`, `services/`, `integrations/`, `workers/`, `alembic/`.

2. **No `os.getenv()` or `.env` loading outside of `core/config.py`.**
   All environment variables are read once in config.py. Everything else imports `settings` from there.

3. **No direct database connections.**
   No `psycopg2.connect()`, no raw drivers. Always use `Session(engine)` via `Depends(get_session)` from `db/session.py`.

4. **No experimental scripts in the repo.**
   No `test_scratch.py`, no debug modules, no notebooks. Experiments stay local.

5. **Protected files — do not modify without explicit approval:**
   - `backend/main.py`
   - `backend/core/config.py`
   - `backend/core/security.py`
   - `backend/db/session.py`
   - `alembic/env.py`

6. **One router file per domain.**
   All endpoints go in `backend/api/v1/routes/`. Example: all product endpoints live in `products.py`, all sentiment endpoints in `sentiment.py`.

7. **Routers talk schemas at the edges, models internally.**
   Pydantic schemas handle request/response. SQLModel models handle database operations. Don't expose internal fields like `password_hash` through the API.

8. **Schema changes follow the migration flow:**
   - Update SQLModel model
   - Generate migration: `alembic revision --autogenerate -m "description"`
   - Review the generated migration
   - Apply: `alembic upgrade head`

### Frontend Rules

1. **Max 150 lines per file.** Break into smaller components if you exceed this.

2. **No custom styling in page files.** Pages import and arrange shared components. Styling lives in components.

3. **Use design tokens from `lib/theme.ts`.** No hardcoded colors or font sizes.

4. **Use `<Link>`, not `<a>`.** For all internal navigation (Next.js client-side routing).

5. **Never store secrets in localStorage.** Use httpOnly cookies or secure headers for auth tokens.

6. **Never log sensitive data.** No passwords, tokens, or PII in console logs.

### General Rules

1. **Use type hints everywhere** (Python) and **TypeScript strict mode** (frontend).
2. **No `console.log` left in committed code** — use proper logging.
3. **No commented-out code in PRs.** Delete it or don't commit it.

---

## Request Flow (How the Backend Works)

Understanding this flow is required before building any feature:

```
1. Frontend makes API call → e.g., POST /api/v1/auth/login
2. main.py routes to the correct router → auth.py
3. Router:
   - Validates input using Pydantic schema (schemas/auth.py)
   - Gets DB session via Depends(get_session)
   - Queries data using SQLModel (models/user.py)
   - Calls security helpers if needed (core/security.py)
   - Returns response shaped by Pydantic schema
4. Frontend receives JSON response
```

The API URL mapping between frontend and backend is intentionally 1:1:

| Frontend Page              | Backend API              |
|----------------------------|--------------------------|
| `/auth/login`              | `/api/v1/auth/login`     |
| `/dashboard/products`      | `/api/v1/products`       |
| `/dashboard/competitors`   | `/api/v1/competitors`    |
| `/dashboard/sentiment`     | `/api/v1/sentiment`      |
| `/dashboard/suggestions`   | `/api/v1/suggestions`    |

---

## Testing

Before opening a PR, run the full test suite:

```bash
# From the project root, with your virtual environment activated
cd backend
pytest
```

All 4,900+ tests must pass. If your changes break existing tests, fix them before opening the PR.

To run a specific test file:
```bash
pytest tests/test_sentiment.py -v
```

To run tests matching a keyword:
```bash
pytest -k "test_pricing" -v
```

---

## Code Review Expectations

When your PR is reviewed, the reviewer is checking for:

1. **Does it follow the patterns?** Look at existing code in the same domain and match the style.
2. **Are there tests?** New endpoints need tests. New components need at minimum a smoke test.
3. **Is it scoped?** One PR = one logical change. Don't mix a bug fix with a new feature.
4. **Does it break anything?** Full test suite must pass.
5. **Is it readable?** Clear variable names, no magic numbers, comments where logic is non-obvious.

---

## Staging & Deployment

Deployments are automatic via CI/CD:

| Branch    | Frontend Deployment         | Backend Deployment      |
|-----------|-----------------------------|-------------------------|
| `develop` | ssp-staging.vercel.app      | ssp-staging (Railway)   |
| `main`    | social-sentiment-pricing.vercel.app | production (Railway) |

When your PR merges to `develop`, staging updates automatically within ~2 minutes.
Check staging after merge to verify your changes work in the deployed environment.

You do **not** need access to Railway or Vercel dashboards. If something breaks on staging, notify the project lead.

---

## Getting Help

- **Stuck on setup?** See `DEVELOPER_SETUP.md` for complete local environment instructions.
- **Unsure about architecture?** Read the request flow section above, then look at an existing feature in the same domain as your task.
- **Need a credential or API key?** See the Environment Variables section in `DEVELOPER_SETUP.md`. Never use production credentials locally.
- **Found a bug unrelated to your task?** Open a GitHub Issue, don't fix it in your current PR.

---

## First Task Checklist

Before your first PR, confirm:

- [ ] You can run the backend locally (`uvicorn backend.main:app --reload`)
- [ ] You can run the frontend locally (`npm run dev` from `frontend/`)
- [ ] You can run the test suite and all 4,900+ tests pass
- [ ] You've read this entire document
- [ ] You've read `DEVELOPER_SETUP.md`
- [ ] You understand the branch workflow (feature branch → PR → develop)


# Developer Setup Guide

Everything you need to go from `git clone` to a running local environment.
Follow each step in order. If you get stuck, check the Troubleshooting section at the bottom before asking the team.

---

## Prerequisites

Install these before anything else:

| Tool | Version | How to check | How to install |
|------|---------|--------------|----------------|
| Python | 3.11+ | `python3 --version` | [python.org](https://python.org) or `brew install python` |
| Node.js | 18+ | `node --version` | [nodejs.org](https://nodejs.org) or `brew install node` |
| PostgreSQL | 14+ | `psql --version` | [postgresql.org](https://postgresql.org) or `brew install postgresql` |
| Git | 2.x | `git --version` | [git-scm.com](https://git-scm.com) |

**Optional but recommended:**
- Docker (if you prefer running PostgreSQL in a container)
- VS Code with Python and ESLint extensions

---

## 1. Clone the Repo

```bash
git clone https://github.com/pema37/social-sentiment-pricing.git
cd social-sentiment-pricing
git checkout develop
```

All work happens on `develop` or feature branches off develop. Never work directly on `main`.

---

## 2. Backend Setup

### 2.1 Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# On Windows: .venv\Scripts\activate
```

You should see `(.venv)` in your terminal prompt. Always activate this before working on the backend.

### 2.2 Install Dependencies

```bash
pip install -r requirements.txt
```

If you get errors about `psycopg2`, install the prerequisites:
```bash
# macOS
brew install libpq
pip install psycopg2-binary

# Ubuntu/Debian
sudo apt-get install libpq-dev
pip install psycopg2-binary
```

### 2.3 Set Up Environment Variables

Copy the example env file:
```bash
cp .env.example .env
```

Then edit `.env` with your own values. See the **Environment Variables Reference** section below for what each variable does and how to get your own keys.

**IMPORTANT:** The `.env` file is in `.gitignore` and must NEVER be committed. If git tries to track it, something is wrong.

### 2.4 Set Up Your Local Database

**Option A: Local PostgreSQL (recommended)**

```bash
# Create a development database
createdb ssp_dev

# Your DATABASE_URL in .env should be:
# DATABASE_URL=postgresql://your_username:your_password@localhost:5432/ssp_dev
```

**Option B: Docker**

```bash
docker run --name ssp-postgres -e POSTGRES_DB=ssp_dev -e POSTGRES_PASSWORD=devpassword -p 5432:5432 -d postgres:14

# Your DATABASE_URL in .env should be:
# DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/ssp_dev
```

### 2.5 Run Database Migrations

```bash
alembic upgrade head
```

This creates all the tables in your local database. If you get a connection error, check your DATABASE_URL in `.env`.

### 2.6 Start the Backend

```bash
uvicorn backend.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
```

Verify it works:
- Open http://localhost:8000 → should return `{"message": "SSP backend is running"}`
- Open http://localhost:8000/docs → interactive API documentation (Swagger UI)
- Open http://localhost:8000/api/v1/health → health check response

---

## 3. Frontend Setup

Open a **new terminal tab** (keep the backend running in the first one).

### 3.1 Install Dependencies

```bash
cd frontend
npm install
```

### 3.2 Set Up Frontend Environment

Create a `.env.local` file in the `frontend/` directory:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

This tells the frontend where to find the backend API when running locally.

**IMPORTANT:** Never prefix secrets with `NEXT_PUBLIC_` — that exposes them to the client browser. Only the API URL should be public.

### 3.3 Start the Frontend

```bash
npm run dev
```

You should see:
```
▲ Next.js 14.x
- Local: http://localhost:3000
```

Open http://localhost:3000 in your browser. The frontend should load and connect to your local backend.

---

## 4. Running Tests

### Backend Tests

From the project root, with your virtual environment activated:

```bash
cd backend
pytest
```

This runs the full test suite (4,268+ tests). All tests must pass before you open a PR.

Useful test commands:

```bash
# Run a specific test file
pytest tests/test_sentiment.py -v

# Run tests matching a keyword
pytest -k "test_pricing" -v

# Run tests with output shown
pytest -s

# Run tests and stop on first failure
pytest -x
```

### Frontend Tests (if applicable)

```bash
cd frontend
npm run lint          # Check for lint errors
npm run type-check    # TypeScript type checking (if configured)
```

---

## 5. Environment Variables Reference

Below is every environment variable the app uses. Create your `.env` file based on this.

### .env.example

```bash
# =============================================================
# ActualPrice / Social Sentiment Pricing - Environment Variables
# =============================================================
# Copy this file to .env and fill in your own values.
# NEVER commit .env to git. NEVER use production credentials locally.
# =============================================================

# --- Database ---
# Use your LOCAL database, not production.
# Option A: Local PostgreSQL
DATABASE_URL=postgresql://your_username:your_password@localhost:5432/ssp_dev
# Option B: Docker
# DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/ssp_dev

# --- Authentication ---
# Generate your own: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=generate-your-own-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- Google Gemini AI ---
# Get your own key: https://aistudio.google.com/apikey (free tier available)
GOOGLE_GEMINI_API_KEY=your-gemini-api-key-here

# --- Shopify (only needed if working on Shopify integration) ---
# Create a dev store: https://partners.shopify.com → Development stores
# Then create a custom app in that store to get these values
SHOPIFY_API_KEY=your-dev-shopify-api-key
SHOPIFY_API_SECRET=your-dev-shopify-api-secret
SHOPIFY_APP_URL=http://localhost:3000

# --- Social APIs (only needed if working on sentiment features) ---
# Twitter: https://developer.twitter.com (apply for API access)
TWITTER_API_KEY=your-twitter-api-key
TWITTER_API_SECRET=your-twitter-api-secret
TWITTER_BEARER_TOKEN=your-twitter-bearer-token

# Reddit: https://www.reddit.com/prefs/apps (create a "script" app)
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret

# NewsAPI: https://newsapi.org (free tier: 100 requests/day)
NEWS_API_KEY=your-newsapi-key

# --- Redis (only needed if working on background jobs) ---
# Install Redis locally or use Docker: docker run -p 6379:6379 -d redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# --- App Settings ---
APP_ENV=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

### What You Need Right Away vs. Later

**Need immediately (to run the app locally):**
- `DATABASE_URL` — Set up a local PostgreSQL database
- `JWT_SECRET_KEY` — Generate one with the command shown above

**Need for AI features:**
- `GOOGLE_GEMINI_API_KEY` — Get your own free key from [Google AI Studio](https://aistudio.google.com/apikey)

**Need only if assigned Shopify tasks:**
- `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET` — Ask the project lead to help create a dev store

**Need only if assigned sentiment pipeline tasks:**
- `TWITTER_API_KEY`, `REDDIT_CLIENT_ID`, `NEWS_API_KEY` — Get your own free-tier keys

**You do NOT need:**
- Railway dashboard access
- Vercel dashboard access
- Production database credentials
- Production API keys of any kind

---

## 6. How to Get Your Own API Keys

### Google Gemini API Key (free)
1. Go to https://aistudio.google.com/apikey
2. Sign in with any Google account
3. Click "Create API Key"
4. Copy the key into your `.env` as `GOOGLE_GEMINI_API_KEY`

### Local PostgreSQL Database
```bash
# macOS (with Homebrew)
brew install postgresql
brew services start postgresql
createdb ssp_dev

# Your DATABASE_URL: postgresql://your_mac_username@localhost:5432/ssp_dev
# (no password needed for local connections on macOS by default)
```

### JWT Secret Key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output into your .env as JWT_SECRET_KEY
```

---

## 7. Daily Workflow

Once everything is set up, your daily routine looks like this:

```bash
# 1. Navigate to project
cd social-sentiment-pricing

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Pull latest develop
git checkout develop
git pull origin develop

# 4. Create your feature branch
git checkout -b feature/your-task-name

# 5. Start backend (terminal 1)
uvicorn backend.main:app --reload

# 6. Start frontend (terminal 2)
cd frontend && npm run dev

# 7. Code your changes...

# 8. Run tests before committing
cd backend && pytest

# 9. Commit and push
git add .
git commit -m "feat: your clear commit message"
git push origin feature/your-task-name

# 10. Open PR on GitHub targeting develop
```

---

## 8. Troubleshooting

### "ModuleNotFoundError: No module named 'backend'"
You're probably running from the wrong directory. Make sure you're in the project root (`social-sentiment-pricing/`) not inside `backend/`.

### "psycopg2 - Error: pg_config not found"
Install PostgreSQL development headers:
```bash
# macOS
brew install libpq
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
pip install psycopg2-binary

# Ubuntu
sudo apt-get install libpq-dev
pip install psycopg2-binary
```

### "Connection refused" when running backend
Your local PostgreSQL isn't running. Start it:
```bash
# macOS
brew services start postgresql

# Ubuntu
sudo systemctl start postgresql

# Docker
docker start ssp-postgres
```

### "alembic upgrade head" fails
Check that your `DATABASE_URL` in `.env` is correct and the database exists:
```bash
psql -l  # Lists all databases. Make sure ssp_dev is there.
```

### Frontend shows blank page or API errors
Make sure:
1. Backend is running on port 8000
2. `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. No CORS errors in the browser console

### Tests fail with import errors
Make sure your virtual environment is activated (`(.venv)` in your prompt) and all dependencies are installed:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 9. What NOT to Do

- **Never use production credentials locally.** You have your own keys.
- **Never push `.env` files to git.** They contain secrets.
- **Never push directly to `main` or `develop`.** Use feature branches + PRs.
- **Never modify protected files** (`main.py`, `config.py`, `security.py`, `session.py`) without explicit approval from the project lead.
- **Never run untested code against any shared database.**

---

## Questions?

If something in this guide is wrong or unclear, open a GitHub Issue and it will be updated.
Read `CONTRIBUTING.md` for the workflow and code rules.



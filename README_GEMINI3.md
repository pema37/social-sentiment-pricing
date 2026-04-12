# ActualPrice (SSP)

**AI-Powered Dynamic Pricing Based on Social Sentiment Analysis**

*Built with Google Gemini 3 Flash for the Gemini 3 Hackathon 2026*

---

## 🎯 What is ActualPrice?

ActualPrice is a SaaS platform that helps e-commerce merchants optimize their pricing in real-time using AI-powered social sentiment analysis. Instead of guessing what price customers will pay, ActualPrice monitors what people are saying about your products across social media and recommends the right price at the right time — so merchants sell more products.

**The Problem:** Merchants set prices based on gut feeling or outdated spreadsheets. They have no idea what the market temperature is right now — what competitors are charging, what customers are saying, or what's trending. They leave money on the table every day.

**Our Solution:** ActualPrice connects to your store (Shopify/WooCommerce), reads the market in real time using Gemini 3 multi-agent AI, and either recommends or automatically applies optimal price changes.

---

## 🤖 Powered by Google Gemini 3

ActualPrice uses **Gemini 3 Flash** (`gemini-2.0-flash`) as the primary AI engine across all features:

| Feature | Gemini 3 Capability | Description |
|---------|---------------------|-------------|
| **Visual Pricing Intelligence** | Vision + Streaming + Thinking Levels | Multi-agent system analyzes competitor product images in real-time |
| **Crisis Detection** | Language + Streaming + Thought Signatures | Detects PR crises from sentiment data with severity assessment |
| **Launch Detection** | Vision + Multimodal + Thinking Levels | Identifies competitor product launches from screenshots |
| **Market Trends** | Language + Streaming + Thought Signatures | AI monitors trending topics, seasonal patterns, and demand shifts |
| **Sentiment Analysis** | Language | Hybrid analysis with Gemini 3 primary, VADER baseline |
| **AI Market Analysis** | Language | Generates insights about market trends and pricing opportunities |
| **AI Support Chat** | Language | Contextual merchant assistance |

### Gemini 3 Features Used

- **Native Thinking Levels** — Configurable reasoning depth (`minimal` / `low` / `high`) via `ThinkingConfig`, letting agents trade speed for deeper analysis
- **Thought Signatures** — Extracts native `part.thought` flags from Gemini 3 responses, displayed as real-time "agent thinking" in the UI
- **Multimodal Vision** — Visual Pricing and Launch Detector accept product screenshots for Gemini image analysis
- **1M Token Context** — Crisis Detector feeds comprehensive sentiment history for full-context analysis

### Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Gemini 3 Flash                           │
│               (gemini-2.0-flash)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Vision    │  │  Language   │  │  Streaming  │         │
│  │  Analysis   │  │  Analysis   │  │  + Thinking │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Multi-Agent Orchestration                 │   │
│  │  • Scout → Analyst → Strategist (Visual Pricing)     │   │
│  │  • Monitor → Analyzer → Response (Crisis)            │   │
│  │  • Scanner → Validator → Assessor (Launch Detection) │   │
│  │  • Collector → Analyzer → Forecaster (Market Trends) │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 🧠 AI-Powered Sentiment Analysis
- **Hybrid Analysis Engine** — Gemini 3 Flash (primary) + VADER (fast baseline) for robust sentiment scoring
- **Real-time Monitoring** — Tracks mentions across Reddit, Twitter, and news sources
- **Sarcasm Detection** — AI identifies sarcastic posts that would fool basic sentiment tools

### 💰 Dynamic Pricing Engine
- **Smart Pricing Rules** — Create rules based on sentiment thresholds, competitor prices, time-based triggers, or volume surges
- **Auto-Apply Mode** — Let AI automatically apply price changes within your defined guardrails
- **Margin Protection** — Set floor prices and margin minimums to ensure profitability

### 🔗 E-commerce Integration
- **Shopify** — One-click OAuth connection
- **WooCommerce** — Secure API credential connection
- **Two-way Sync** — Pull products from your store, push price updates back

### 📊 Analytics & Insights
- **Sentiment Dashboard** — Visualize sentiment trends over time
- **Price History** — Track how price changes affected sales
- **Competitor Monitoring** — Track competitor prices and market position
- **AI Market Analysis** — Get Gemini 3-generated insights about market trends

### 🚨 Smart Alerts
- **Crisis Detection** — Get notified when sentiment drops suddenly
- **Viral Detection** — Know when a product is trending
- **Price Recommendations** — Never miss an optimization opportunity

### 💳 Crypto Payments
- **MNEE Integration** — Accept cryptocurrency payments for subscriptions
- **BSV & ETH Support** — Multiple blockchain payment options

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, React Query |
| Backend | FastAPI, Python 3.11, SQLModel, Pydantic |
| Database | PostgreSQL (Neon), Redis |
| **AI/ML** | **Google Gemini 3 Flash (primary)**, VADER Sentiment |
| Background Jobs | Celery, Redis |
| Integrations | Shopify API, WooCommerce REST API |
| Payments | MNEE, MetaMask (ETH) |
| Deployment | Railway (backend), Vercel (frontend) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis
- **Google Gemini API Key**

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials (especially GEMINI_API_KEY)

# Run database migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your API URL

# Generate TypeScript types from backend (run when backend schemas change)
npm run generate-api-types

# Start development server
npm run dev
```

### Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# AI Provider (Primary)
GEMINI_API_KEY=your-gemini-api-key

# Integrations
SHOPIFY_API_KEY=...
SHOPIFY_API_SECRET=...
```

**Frontend (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 📖 API Documentation

Once the backend is running:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

See `ACTUALPRICE_CONTRACTS.md` for detailed API contracts and type definitions.

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│     Backend     │────▶│    Database     │
│   (Next.js)     │     │    (FastAPI)    │     │  (PostgreSQL)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  Celery  │ │  Redis   │ │ External │
              │ Workers  │ │  Cache   │ │   APIs   │
              └──────────┘ └──────────┘ └──────────┘
                                             │
                         ┌───────────────────┼───────────────────┐
                         ▼                   ▼                   ▼
                   ┌──────────┐        ┌──────────┐        ┌──────────┐
                   │  Reddit  │        │ Gemini 3 │        │ Shopify/ │
                   │   API    │        │  Flash   │        │   WC     │
                   └──────────┘        └──────────┘        └──────────┘
```

### Background Tasks (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_all_mentions` | Every 30 min | Fetches social mentions for products |
| `process_pending_mentions` | Every 5 min | Analyzes sentiment (VADER + Gemini 3) |
| `generate_recommendations` | Every hour | Creates pricing recommendations |
| `fetch_competitor_prices` | Every 30 min | Updates competitor price data |

---

## 📁 Project Structure

```
social-sentiment-pricing/
├── backend/
│   ├── api/v1/routes/      # API endpoints
│   ├── models/             # Database models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   │   ├── pricing/        # Pricing engine
│   │   ├── integration/    # Shopify/WooCommerce
│   │   ├── ai_trend_analysis/  # Gemini 3 multi-agent systems
│   │   └── analysis/       # Sentiment analysis
│   ├── workers/            # Celery tasks
│   └── main.py
├── frontend/
│   ├── app/                # Next.js pages
│   │   └── demo/           # Gemini 3 demo features
│   ├── components/         # React components
│   ├── lib/                # API clients, hooks
│   └── types/              # TypeScript types
├── ACTUALPRICE_CONTRACTS.md
├── PRIVACY.md
└── README.md
```

---

## 🎬 Demo

**Live Demo:** [ssp-staging.vercel.app/demo](https://ssp-staging.vercel.app/demo)

### Gemini 3-Powered Demo Features

| Demo | URL | Description |
|------|-----|-------------|
| **Visual Pricing** | [`/demo/visual-pricing`](https://ssp-staging.vercel.app/demo/visual-pricing) | Upload competitor image → Watch 3 AI agents collaborate in real-time |
| **Crisis Detection** | [`/demo/crisis-detector`](https://ssp-staging.vercel.app/demo/crisis-detector) | Paste social content → Get severity analysis and recommended actions |
| **Launch Detection** | [`/demo/launch-detector`](https://ssp-staging.vercel.app/demo/launch-detector) | Upload competitor announcement → See threat assessment |
| **Market Trends** | [`/demo/market-trends`](https://ssp-staging.vercel.app/demo/market-trends) | Analyze market signals → Get trend insights and pricing opportunities |

### Staging URLs
- **Demo Hub:** https://ssp-staging.vercel.app/demo
- **Frontend:** https://ssp-staging.vercel.app
- **Backend API:** https://social-sentiment-pricing-staging-2ecd.up.railway.app
- **API Docs:** https://social-sentiment-pricing-staging-2ecd.up.railway.app/docs

---

## 🗺️ Roadmap

### MVP (Current - Hackathon)
- [x] User authentication
- [x] Product management
- [x] Shopify/WooCommerce integration
- [x] Social sentiment analysis (Reddit)
- [x] **Gemini 3-powered pricing rules**
- [x] **Multi-agent visual analysis with thinking levels**
- [x] **Crisis detection with thought signatures**
- [x] **Launch detection with multimodal vision**
- [x] **Market trends with streaming analysis**
- [x] Auto-apply pricing
- [x] MNEE crypto payments

### Post-Hackathon
- [ ] Twitter/X integration
- [ ] Amazon integration
- [ ] Advanced competitor intelligence
- [ ] Mobile app
- [ ] Multi-currency support
- [ ] Team collaboration features

---

## 📄 License

This project is open source under the **MIT License**.

---

## 👥 Contributors

| Contributor | Role |
|-------------|------|
| @pema37 | Lead Developer |
| @Celestin-Pet | Frontend |
| @IbnNur | Backend |

---

Built with **Google Gemini 3 Flash** for the **Gemini 3 Hackathon 2026** 🚀

🔗 [Live Demo](https://ssp-staging.vercel.app/demo) | 📖 [API Docs](https://social-sentiment-pricing-staging-2ecd.up.railway.app/docs)


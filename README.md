# ActualPrice (SSP)

**AI-Powered Dynamic Pricing Based on Social Sentiment Analysis**

*Built with Google Gemini 2.0 Flash for the Gemini API Developer Competition 2025*

---

## 🎯 What is ActualPrice?

ActualPrice is a SaaS platform that helps e-commerce merchants optimize their pricing in real-time using AI-powered social sentiment analysis. Instead of guessing what price customers will pay, ActualPrice monitors what people are saying about your products across social media and automatically adjusts prices based on demand signals.

**The Problem:** E-commerce merchants lose revenue by not adjusting prices to match real-time market sentiment. A product going viral on Reddit? Price should go up. Negative reviews trending? Time to discount.

**Our Solution:** ActualPrice connects to your store (Shopify/WooCommerce), monitors social media sentiment, and either recommends or automatically applies optimal price changes.

---

## 🤖 Powered by Google Gemini

ActualPrice uses **Gemini 2.0 Flash** as the primary AI engine across all features:

| Feature | Gemini Capability | Description |
|---------|-------------------|-------------|
| **Visual Pricing Intelligence** | Vision + Streaming | Multi-agent system analyzes competitor product images in real-time |
| **Crisis Detection** | Language + Streaming | Detects PR crises from sentiment data with severity assessment |
| **Launch Detection** | Vision + Multimodal | Identifies competitor product launches from screenshots |
| **Sentiment Analysis** | Language | Hybrid analysis with Gemini primary, VADER baseline |
| **AI Market Analysis** | Language | Generates insights about market trends and pricing opportunities |
| **AI Support Chat** | Language | Contextual merchant assistance |

### Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Gemini 2.0 Flash                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Vision    │  │  Language   │  │  Streaming  │         │
│  │  Analysis   │  │  Analysis   │  │  Responses  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Multi-Agent Orchestration                 │   │
│  │  • Scout → Analyst → Strategist (Visual Pricing)     │   │
│  │  • Monitor → Investigator → Response (Crisis)        │   │
│  │  • Scanner → Validator → Assessor (Launch Detection) │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 🧠 AI-Powered Sentiment Analysis
- **Hybrid Analysis Engine** — Gemini 2.0 Flash (primary) + VADER (fast baseline) for robust sentiment scoring
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
- **AI Market Analysis** — Get Gemini-generated insights about market trends

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
| **AI/ML** | **Google Gemini 2.0 Flash (primary)**, VADER Sentiment |
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
                   │  Reddit  │        │  Gemini  │        │ Shopify/ │
                   │   API    │        │   2.0    │        │   WC     │
                   └──────────┘        └──────────┘        └──────────┘
```

### Background Tasks (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_all_mentions` | Every 30 min | Fetches social mentions for products |
| `process_pending_mentions` | Every 5 min | Analyzes sentiment (VADER + Gemini) |
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
│   │   ├── ai_trend_analysis/  # Gemini multi-agent systems
│   │   └── analysis/       # Sentiment analysis
│   ├── workers/            # Celery tasks
│   └── main.py
├── frontend/
│   ├── app/                # Next.js pages
│   │   └── demo/           # Gemini demo features
│   ├── components/         # React components
│   ├── lib/                # API clients, hooks
│   └── types/              # TypeScript types
├── ACTUALPRICE_CONTRACTS.md
├── PRIVACY.md
└── README.md
```

---

## 🎬 Demo

**Live Demo:** [ssp-staging.vercel.app](https://ssp-staging.vercel.app)

### Gemini-Powered Demo Features

| Demo | URL | Description |
|------|-----|-------------|
| **Visual Pricing** | `/demo/visual-pricing` | Upload competitor image → Watch 3 AI agents collaborate in real-time |
| **Crisis Detection** | `/demo/crisis-detector` | Paste social content → Get severity analysis and recommended actions |
| **Launch Detection** | `/demo/launch-detector` | Upload competitor announcement → See threat assessment |

### Staging URLs
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
- [x] **Gemini-powered pricing rules**
- [x] **Multi-agent visual analysis**
- [x] **Crisis detection system**
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

Built with **Google Gemini 2.0 Flash** for the **Gemini API Developer Competition 2025** 🚀

🔗 [Live Demo](https://ssp-staging.vercel.app) | 📖 [API Docs](https://social-sentiment-pricing-staging-2ecd.up.railway.app/docs)

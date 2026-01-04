# ActualPrice (SSP)

**AI-Powered Dynamic Pricing Based on Social Sentiment Analysis**


## 🎯 What is ActualPrice?

ActualPrice is a SaaS platform that helps e-commerce merchants optimize their pricing in real-time using AI-powered social sentiment analysis. Instead of guessing what price customers will pay, ActualPrice monitors what people are saying about your products across social media and automatically adjusts prices based on demand signals.

**The Problem:** E-commerce merchants lose revenue by not adjusting prices to match real-time market sentiment. A product going viral on Reddit? Price should go up. Negative reviews trending? Time to discount.

**Our Solution:** ActualPrice connects to your store (Shopify/WooCommerce), monitors social media sentiment, and either recommends or automatically applies optimal price changes.

---

## ✨ Key Features

### 🧠 AI-Powered Sentiment Analysis
- **Hybrid Analysis Engine** — Combines VADER (fast), OpenAI GPT-4 (accurate), and Google Gemini (fallback) for robust sentiment scoring
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
- **AI Market Analysis** — Get AI-generated insights about market trends

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
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, React Query |
| **Backend** | FastAPI, Python 3.11, SQLModel, Pydantic |
| **Database** | PostgreSQL (Neon), Redis |
| **AI/ML** | OpenAI GPT-4o-mini, Google Gemini, VADER Sentiment |
| **Background Jobs** | Celery, Redis |
| **Integrations** | Shopify API, WooCommerce REST API |
| **Payments** | MNEE, MetaMask (ETH) |
| **Deployment** | Railway (backend), Vercel (frontend) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

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
# Edit .env with your credentials

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

# Start development server
npm run dev
```

### Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
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

See [ACTUALPRICE_CONTRACTS.md](./ACTUALPRICE_CONTRACTS.md) for detailed API contracts and type definitions.

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
                   │  Reddit  │        │  OpenAI  │        │ Shopify/ │
                   │   API    │        │  Gemini  │        │   WC     │
                   └──────────┘        └──────────┘        └──────────┘
```

### Background Tasks (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_all_mentions` | Every 30 min | Fetches social mentions for products |
| `process_pending_mentions` | Every 5 min | Analyzes sentiment (VADER + OpenAI + Gemini) |
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
│   │   └── analysis/       # Sentiment analysis
│   ├── workers/            # Celery tasks
│   └── main.py
├── frontend/
│   ├── app/                # Next.js pages
│   ├── components/         # React components
│   ├── lib/                # API clients, hooks
│   └── types/              # TypeScript types
├── ACTUALPRICE_CONTRACTS.md
├── PRIVACY.md
└── README.md
```

---

## 🎬 Demo

**Live Demo:** [https://actualprice.vercel.app](https://actualprice.vercel.app)

**Demo Video:** [Watch on YouTube](#) *(coming soon)*


```

---

## 🗺️ Roadmap

### MVP (Current - Hackathon)
- [x] User authentication
- [x] Product management
- [x] Shopify/WooCommerce integration
- [x] Social sentiment analysis (Reddit)
- [x] AI-powered pricing rules
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

---

*Built with ❤️ for the MNEE Hackathon 2026*
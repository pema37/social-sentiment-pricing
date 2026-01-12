# ActualPrice

**AI-driven Social Sentiment Pricing for E-commerce**

> A Stanley cup goes viral on TikTok. Within hours, resellers have tripled their prices while most merchants are still selling at cost. By the time sellers realize what's happening, the trend has peaked and they've left thousands in revenue on the table.

ActualPrice answers one question: **What should this product cost _right now_, based on what the market actually looks like?**

And then: what if the price could adjust automatically, with payments settling instantly through MNEE instead of waiting 2-3 days for traditional processors?

## Features

### 🎯 Sentiment Engine
Continuously monitors Twitter and Reddit for product mentions, brand sentiment, and viral moments. When buzz spikes, you know immediately.

### 📊 Competitor Tracking
Track competitor prices automatically. When they move, you see it in your dashboard alongside the context—are they responding to the same trend you're seeing?

### 🤖 AI Pricing Recommendations
Our engine synthesizes sentiment data, competitor movements, and your pricing rules to recommend optimal prices. Each recommendation includes a confidence score and plain-English reasoning.

### ⚡ Auto-Reprice
Connect your Shopify or WooCommerce store and let ActualPrice push price updates directly. Set guardrails (min/max price, maximum daily changes) and choose between auto-apply or approval-based workflows.

### 💰 MNEE Payments
Accept MNEE stablecoin at checkout. Payments settle instantly with automatic revenue splits—80% merchant, 15% affiliate, 5% platform—executed by smart contract.

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Task Queue:** Celery with Redis
- **Database:** PostgreSQL (Neon)
- **AI/ML:** VADER + OpenAI GPT-4o-mini + Google Gemini

### Frontend
- **Framework:** Next.js 14 with TypeScript
- **Styling:** Tailwind CSS
- **State:** React Query

### Integrations
- Shopify Admin API
- WooCommerce REST API
- Twitter API v2
- Reddit API (PRAW)

### Payments
- Ethers.js + WalletConnect
- Solidity smart contracts for automated payment splits

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL (or Neon account)
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

#### Backend (.env)
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# AI Providers
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Social APIs
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
TWITTER_BEARER_TOKEN=...

# E-commerce
SHOPIFY_API_KEY=...
SHOPIFY_API_SECRET=...
WOOCOMMERCE_URL=...
WOOCOMMERCE_KEY=...
WOOCOMMERCE_SECRET=...
```

#### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=...
```

### Docker (Alternative)

```bash
docker-compose up -d
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Next.js UI    │────▶│   FastAPI       │────▶│   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Celery Workers │
                        │  - Sentiment    │
                        │  - Price Sync   │
                        │  - Competitors  │
                        └─────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌───────────┐    ┌───────────┐    ┌───────────┐
       │  Twitter  │    │  Reddit   │    │  Shopify/ │
       │  API      │    │  API      │    │  WooComm  │
       └───────────┘    └───────────┘    └───────────┘
```

## Business Impact

| Metric | Impact |
|--------|--------|
| Revenue Increase | 15-25% through optimized pricing |
| Payment Fees | 2-3% savings vs traditional processors |
| Settlement Time | Instant vs 2-3 day delays |
| Affiliate Payouts | Automated via smart contract |

## Why MNEE?

Traditional payment processors charge 2.5-3% and hold funds for days. For a merchant doing $100K/month, that's $3K in fees and constant cash flow pressure.

MNEE changes the economics: near-zero fees, instant settlement, and programmable money that can automatically split revenue the moment a transaction confirms.

## Demo

🔗 **Live Demo:** [ssp-staging.vercel.app](https://ssp-staging.vercel.app)

## Third-Party APIs & SDKs

- [OpenAI API](https://openai.com/) - GPT-4o-mini for sentiment analysis
- [Google Gemini](https://ai.google.dev/) - Fallback AI provider
- [VADER Sentiment](https://github.com/cjhutto/vaderSentiment) - Fast sentiment scoring
- [Reddit API (PRAW)](https://praw.readthedocs.io/) - Social monitoring
- [Twitter API v2](https://developer.twitter.com/) - Social monitoring
- [Shopify Admin API](https://shopify.dev/api/admin) - Store integration
- [WooCommerce REST API](https://woocommerce.github.io/woocommerce-rest-api-docs/) - Store integration
- [Ethers.js](https://ethers.org/) - Blockchain interaction
- [WalletConnect](https://walletconnect.com/) - Wallet connectivity

## License

This project is open source under the [MIT License](LICENSE).

## Team

Built for the MNEE Hackathon 2026.

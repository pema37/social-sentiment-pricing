# ActualPrice

**AI-driven Social Sentiment Pricing for E-commerce**

*Powered by Google Gemini 2.0 Flash*

---

A Stanley cup goes viral on TikTok. Within hours, resellers have tripled their prices while most merchants are still selling at cost. By the time sellers realize what's happening, the trend has peaked and they've left thousands in revenue on the table.

**ActualPrice** answers one question: *What should this product cost right now, based on what the market actually looks like?*

And then: what if the price could adjust automatically, with payments settling instantly through MNEE instead of waiting 2-3 days for traditional processors?

---

## Powered by Google Gemini

ActualPrice uses **Gemini 2.0 Flash** for all AI-powered features:

| Feature | Gemini Capability | Description |
|---------|-------------------|-------------|
| **Visual Pricing Intelligence** | Gemini Vision + Streaming | Multi-agent system (Scout → Analyst → Strategist) analyzes competitor product images and recommends optimal pricing in real-time |
| **Crisis Detection** | Gemini Language + Streaming | Monitor → Investigator → Response agents detect PR crises from sentiment data with severity assessment |
| **Launch Detection** | Gemini Vision + Multimodal | Scanner → Validator → Assessor agents identify competitor product launches from screenshots and social signals |
| **Sentiment Analysis** | Gemini Language | Real-time analysis of social media mentions with emotion detection, sarcasm detection, and topic extraction |
| **AI Support Chat** | Gemini Language | Contextual merchant assistance with conversation history |

All features use **streaming responses** for real-time thinking visualization.

---

## Features

### Sentiment Engine
Continuously monitors Twitter and Reddit for product mentions, brand sentiment, and viral moments. When buzz spikes, you know immediately.

### Competitor Tracking
Track competitor prices automatically. When they move, you see it in your dashboard alongside the context—are they responding to the same trend you're seeing?

### AI Pricing Recommendations
Our Gemini-powered engine synthesizes sentiment data, competitor movements, and your pricing rules to recommend optimal prices. Each recommendation includes a confidence score and plain-English reasoning.

### Auto-Reprice
Connect your Shopify or WooCommerce store and let ActualPrice push price updates directly. Set guardrails (min/max price, maximum daily changes) and choose between auto-apply or approval-based workflows.

### MNEE Payments
Accept MNEE stablecoin at checkout. Payments settle instantly with automatic revenue splits—80% merchant, 15% affiliate, 5% platform—executed by smart contract.

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Task Queue:** Celery with Redis
- **Database:** PostgreSQL (Neon)
- **AI/ML:** Google Gemini 2.0 Flash (primary) + VADER (baseline)

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

---

## Demo

🔗 **Live Demo:** [ssp-staging.vercel.app](https://ssp-staging.vercel.app)

### Demo Features
- `/demo/visual-pricing` - Upload a competitor product image → Watch 3 AI agents collaborate in real-time
- `/demo/crisis-detector` - Paste social media content → Get severity analysis and recommended actions
- `/demo/launch-detector` - Upload competitor announcement → See threat assessment and strategic response

---

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL (or Neon account)
- Redis
- Google Gemini API Key

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

---

## Environment Variables

### Backend (.env)

```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# AI Provider (Primary)
GEMINI_API_KEY=your-gemini-api-key

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

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=...
```

### Docker (Alternative)

```bash
docker-compose up -d
```

---

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

### Gemini Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Gemini 2.0 Flash                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Vision    │  │  Language   │  │  Streaming  │         │
│  │  Analysis   │  │  Analysis   │  │  Responses  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         ▼                ▼                ▼                 │
│  ┌─────────────────────────────────────────────┐           │
│  │           Multi-Agent Orchestration          │           │
│  │  Scout → Analyst → Strategist (Pricing)      │           │
│  │  Monitor → Investigator → Response (Crisis)  │           │
│  │  Scanner → Validator → Assessor (Launch)     │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Business Impact

| Metric | Impact |
|--------|--------|
| Revenue Increase | 15-25% through optimized pricing |
| Payment Fees | 2-3% savings vs traditional processors |
| Settlement Time | Instant vs 2-3 day delays |
| Affiliate Payouts | Automated via smart contract |

---

## Why MNEE?

Traditional payment processors charge 2.5-3% and hold funds for days. For a merchant doing $100K/month, that's $3K in fees and constant cash flow pressure.

MNEE changes the economics: near-zero fees, instant settlement, and programmable money that can automatically split revenue the moment a transaction confirms.

---

## Third-Party APIs & SDKs

| Service | Purpose |
|---------|---------|
| **Google Gemini 2.0 Flash** | Primary AI for all features (vision, sentiment, multi-agent systems) |
| **VADER Sentiment** | Fast baseline sentiment scoring |
| **Reddit API (PRAW)** | Social monitoring |
| **Twitter API v2** | Social monitoring |
| **Shopify Admin API** | Store integration |
| **WooCommerce REST API** | Store integration |
| **Ethers.js** | Blockchain interaction |
| **WalletConnect** | Wallet connectivity |

---

## License

This project is open source under the **MIT License**.

---

## Team

Built with **Google Gemini 2.0 Flash** for the **Gemini API Developer Competition 2025**.

🔗 [Live Demo](https://ssp-staging.vercel.app) | 📧 team@getactualprice.com

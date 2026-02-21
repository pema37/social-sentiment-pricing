<<<<<<< HEAD
# ActualPrice — Autonomous Pricing Pipeline

**VETROX AGENTIC 3.0 Hackathon Submission | Track 3: The Hand (Tool Use & Web3)**

An autonomous multi-agent system that monitors competitor prices, analyzes market sentiment, calculates optimal pricing, and executes price updates on-chain — without human intervention.

```
Market Signal → Scout → Analyst → Strategist → BNB Chain
                 ↓         ↓           ↓
              observe    reason       execute
```

## Live Demo

- **Frontend:** [ssp-staging.vercel.app/demo/autonomous-pipeline](https://ssp-staging.vercel.app/demo/autonomous-pipeline)
- **Backend API:** `POST /api/v1/autonomous/trigger`
- **SSE Stream:** `GET /api/v1/autonomous/stream/{product_id}`
- **Health Check:** `GET /api/v1/autonomous/health`

## What It Does

A merchant connects their store. From that point forward, ActualPrice runs autonomously:

1. **Scout Agent** detects a competitor price drop via Gemini 3 function calling — fetching live competitor data, analyzing price changes, and scoring sentiment across social platforms.
2. **Analyst Agent** receives the Scout's signal, calculates demand elasticity, assesses risk factors, and determines whether to raise, lower, or hold pricing.
3. **Strategist Agent** computes the exact optimal price, respects the merchant's margin floor, and if the confidence threshold is met — writes the new price to a BNB Chain smart contract for transparent, auditable execution.

The entire pipeline streams in real-time via SSE so the merchant can watch the agents think.

## Philosophy of Design

### Why three agents instead of one prompt?

A single monolithic prompt would be simpler. We rejected it for the same reason you wouldn't ask one person to be a field reporter, financial analyst, and portfolio manager simultaneously — the quality of each task degrades when you force a single context to hold competing objectives.

By decomposing the pipeline into Scout → Analyst → Strategist, each agent operates with a focused system prompt, dedicated tools, and a narrow output schema. The Scout doesn't need to know about margin floors. The Strategist doesn't need to parse Reddit threads. This separation means each agent can be tested, replaced, or upgraded independently.

This mirrors how autonomous systems work in practice: perception is separated from reasoning, which is separated from actuation.

### Why Gemini function calling instead of prompt-and-parse?

Early prototypes used Gemini to generate JSON directly. It worked 90% of the time. The other 10% produced malformed output that silently corrupted downstream decisions.

We switched to Gemini 3's native function calling — `fetch_competitor_price`, `analyze_sentiment`, `calculate_elasticity`, `assess_risk`, `calculate_optimal_price`, `write_price_to_chain`, `detect_price_change` — because the model selects and invokes tools with structured arguments. The tool handlers return typed data. No parsing. No regex. No "please format your response as JSON."

This isn't a stylistic choice. It's the difference between an agent that works in a demo and an agent that works at 3 AM when no one is watching.

### Why on-chain execution?

Pricing decisions are high-stakes. A merchant who trusts an AI to change their prices needs to verify what happened and when. Writing the final price decision to BNB Chain creates an immutable audit trail: the recommended price, the confidence score, and the timestamp are all recorded in a smart contract that neither the AI nor the platform operator can retroactively alter.

This isn't blockchain for its own sake. It's the minimum credible commitment an autonomous system can make to earn trust.

### What assumptions did we question?

**"AI pricing tools need a human approval step."** We questioned this. Our system includes a margin floor — a hard constraint the merchant sets once — below which the agent will never price. With that guardrail in place, requiring a human to click "approve" on every recommendation defeats the purpose of autonomy. The agent acts. The merchant audits after.

**"Multi-agent systems need complex orchestration frameworks."** We questioned this too. Our orchestrator is a single Python file (~500 lines) that runs three agents in sequence, handles fallbacks, and streams events. No LangChain. No CrewAI. No framework overhead. The complexity is in the Gemini tool definitions and the Pydantic schemas — where it belongs.

**"Tests slow you down during a hackathon."** We wrote 119 tests across four layers (schemas → tool handlers → orchestrator → API) and they caught a real bug: the on-chain transaction hash was being generated at 62 characters instead of the 66 required by Ethereum standards. That bug would have failed silently in production. The tests run in 5 seconds.

### Where is the elegance?

In what the merchant doesn't see. They see a price change. They don't see the Scout parsing a competitor signal, the Analyst running elasticity calculations, the Strategist respecting their margin floor, or the smart contract recording the decision. The architecture is invisible. That's the point.
=======
# ActualPrice

**AI-driven Social Sentiment Pricing for E-commerce**

*Powered by Google Gemini 2.0 Flash*

---

A Stanley cup goes viral on TikTok. Within hours, resellers have tripled their prices while most merchants are still selling at cost. By the time sellers realize what's happening, the trend has peaked and they've left thousands in revenue on the table.

**ActualPrice** answers one question: *What should this product cost right now, based on what the market actually looks like?*

And then: what if the price could adjust automatically, with payments settling instantly through MNEE instead of waiting 2-3 days for traditional processors?

---

## 🤖 Powered by Google Gemini

ActualPrice uses **Gemini 2.0 Flash** for all AI-powered features:

| Feature | Gemini Capability | Description |
|---------|-------------------|-------------|
| **Visual Pricing Intelligence** | Gemini Vision + Streaming | Multi-agent system (Scout → Analyst → Strategist) analyzes competitor product images and recommends optimal pricing in real-time |
| **Crisis Detection** | Gemini Language + Streaming | Monitor → Investigator → Response agents detect PR crises from sentiment data with severity assessment |
| **Launch Detection** | Gemini Vision + Multimodal | Scanner → Validator → Assessor agents identify competitor product launches from screenshots and social signals |
| **Market Trends** | Gemini Language + Streaming | AI monitors trending topics, seasonal patterns, and demand shifts to inform pricing strategy |
| **Sentiment Analysis** | Gemini Language | Real-time analysis of social media mentions with emotion detection, sarcasm detection, and topic extraction |
| **AI Support Chat** | Gemini Language | Contextual merchant assistance with conversation history |

All features use **streaming responses** for real-time thinking visualization.

---

## ✨ Features

### 🎯 Sentiment Engine
Continuously monitors Twitter and Reddit for product mentions, brand sentiment, and viral moments. When buzz spikes, you know immediately.

### 📊 Competitor Tracking
Track competitor prices automatically. When they move, you see it in your dashboard alongside the context—are they responding to the same trend you're seeing?

### 🤖 AI Pricing Recommendations
Our Gemini-powered engine synthesizes sentiment data, competitor movements, and your pricing rules to recommend optimal prices. Each recommendation includes a confidence score and plain-English reasoning.

### ⚡ Auto-Reprice
Connect your Shopify or WooCommerce store and let ActualPrice push price updates directly. Set guardrails (min/max price, maximum daily changes) and choose between auto-apply or approval-based workflows.

### 💰 MNEE Payments
Accept MNEE stablecoin at checkout. Payments settle instantly with automatic revenue splits—80% merchant, 15% affiliate, 5% platform—executed by smart contract.

---

## 🛠 Tech Stack

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

## 🎬 Demo

🔗 **Live Demo:** [ssp-staging.vercel.app/demo](https://ssp-staging.vercel.app/demo)

### Demo Features

| Feature | URL | Description |
|---------|-----|-------------|
| **Visual Pricing** | [`/demo/visual-pricing`](https://ssp-staging.vercel.app/demo/visual-pricing) | Upload a competitor product image → Watch 3 AI agents collaborate in real-time |
| **Crisis Detector** | [`/demo/crisis-detector`](https://ssp-staging.vercel.app/demo/crisis-detector) | Paste social media content → Get severity analysis and recommended actions |
| **Launch Detector** | [`/demo/launch-detector`](https://ssp-staging.vercel.app/demo/launch-detector) | Upload competitor announcement → See threat assessment and strategic response |
| **Market Trends** | [`/demo/market-trends`](https://ssp-staging.vercel.app/demo/market-trends) | Analyze market signals → Get trend insights and pricing opportunities |

---

## 🚀 Getting Started

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

## ⚙️ Environment Variables

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
>>>>>>> origin/main

---

## 🏗 Architecture

```
<<<<<<< HEAD
┌─────────────────────────────────────────────────────┐
│                    Next.js Frontend                   │
│              SSE event stream rendering               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                     │
│                                                      │
│  autonomous_pipeline.py  ←  API routes (trigger,     │
│                              stream, monitor, health) │
│                                                      │
│  autonomous_orchestrator.py  ←  Pipeline engine      │
│    ├── Scout Agent    (Gemini 3 + 3 tools)           │
│    ├── Analyst Agent  (Gemini 3 + 3 tools)           │
│    └── Strategist Agent (Gemini 3 + 1 tool)          │
│                                                      │
│  7 Gemini Function Tools:                            │
│    fetch_competitor_price, detect_price_change,       │
│    analyze_sentiment, calculate_elasticity,           │
│    assess_risk, calculate_optimal_price,              │
│    write_price_to_chain                              │
└──────────────────────┬──────────────────────────────┘
                       │ Web3 / JSON-RPC
┌──────────────────────▼──────────────────────────────┐
│              BNB Chain (Smart Contract)               │
│         Immutable pricing decision audit trail        │
│   Contract: 0x... (deployed on BNB Chain mainnet)    │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Engine | Google Gemini 3 Flash (function calling + structured output) |
| Backend | FastAPI, Python 3.13, Pydantic v2 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Database | PostgreSQL (Neon) |
| Blockchain | BNB Chain, Solidity smart contracts |
| Streaming | Server-Sent Events (SSE) |
| Deploy | Railway (backend) + Vercel (frontend) |
| Testing | pytest + pytest-asyncio (119 tests, 5s runtime) |

## Running the Tests

```bash
# Install dependencies
pip install pytest pytest-asyncio httpx google-genai pydantic

# Run the autonomous pipeline test suite (no API key needed)
python3 -m pytest backend/tests/test_autonomous_schemas.py \
                   backend/tests/test_autonomous_tool_handlers.py \
                   backend/tests/test_autonomous_orchestrator.py \
                   backend/tests/test_autonomous_api.py -v

# Expected: 119 passed in ~5s
```

### Test Coverage

| Layer | Tests | What's Covered |
|-------|-------|---------------|
| Schemas | 25 | Pydantic validation, bounds checking, serialization |
| Tool Handlers | 35 | All 7 Gemini function tools, edge cases, return structures |
| Orchestrator | 23 | Scout→Analyst→Strategist pipeline, SSE streaming, fallbacks |
| API Endpoints | 36 | HTTP status codes, request validation, response headers, SSE format |

## Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
export GEMINI_API_KEY=your-key
export GEMINI_MODEL=gemini-3-flash-preview
export DATABASE_URL=postgresql+asyncpg://...
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
yarn install
yarn dev
```

## API Endpoints

```
POST /api/v1/autonomous/trigger          One-shot pipeline execution
GET  /api/v1/autonomous/stream/{id}      SSE streaming pipeline
POST /api/v1/autonomous/monitor/start    Start continuous monitoring
POST /api/v1/autonomous/monitor/stop     Stop monitoring
GET  /api/v1/autonomous/health           Gemini connectivity check
```

### Example: Trigger Pipeline

```bash
curl -X POST https://your-api/api/v1/autonomous/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "SKU-001",
    "current_price": 99.99,
    "product_category": "electronics",
    "cost_basis": 45.00,
    "margin_floor_pct": 20.0
  }'
```

### Response

```json
{
  "success": true,
  "decision": {
    "action": "execute",
    "current_price": 99.99,
    "recommended_price": 87.49,
    "change_pct": -12.5,
    "confidence_score": 0.82,
    "reasoning": "Competitor dropped 15%. Sentiment bearish. Elasticity supports matching.",
    "tx_hash": "0xa1b2c3..."
  },
  "agents_executed": ["Scout", "Analyst", "Strategist"],
  "pipeline_duration_ms": 3400
}
```

## Smart Contract

Deployed on BNB Chain mainnet. Records every autonomous pricing decision with:
- Product ID
- Previous price → New price
- Confidence score
- Timestamp

Contract details in [ACTUALPRICE_CONTRACTS.md](./ACTUALPRICE_CONTRACTS.md).

## Team

**Massa Sakou** — Founder & Lead Engineer ([ActualPrice](https://ssp-staging.vercel.app))

## License

MIT

=======
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
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Multi-Agent Orchestration                  │   │
│  │  Scout → Analyst → Strategist (Visual Pricing)       │   │
│  │  Monitor → Investigator → Response (Crisis)          │   │
│  │  Scanner → Validator → Assessor (Launch Detection)   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 Business Impact

| Metric | Impact |
|--------|--------|
| Revenue Increase | 15-25% through optimized pricing |
| Payment Fees | 2-3% savings vs traditional processors |
| Settlement Time | Instant vs 2-3 day delays |
| Affiliate Payouts | Automated via smart contract |

---

## 💳 Why MNEE?

Traditional payment processors charge 2.5-3% and hold funds for days. For a merchant doing $100K/month, that's $3K in fees and constant cash flow pressure.

MNEE changes the economics: near-zero fees, instant settlement, and programmable money that can automatically split revenue the moment a transaction confirms.

---

## 🔌 Third-Party APIs & SDKs

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

## 📄 License

This project is open source under the **MIT License**.

---

<<<<<<< HEAD
## 👥 Team

Built with **Google Gemini 2.0 Flash** for the **Gemini 3 Hackathon 2026** 🚀

🔗 [Live Demo](https://ssp-staging.vercel.app/demo) | 📖 [GitHub](https://github.com/pema37/social-sentiment-pricing)
=======
Built for the MNEE Hackathon 2026.
>>>>>>> origin/main
>>>>>>> develop

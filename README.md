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

## Architecture

```
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


# Agora — Competitive Intelligence at $0.05

> AI agents hire, pay, and audit each other on Arc.  
> Full competitive intelligence report in 60 seconds.  
> Every micro-payment settles on-chain via Circle Nanopayments.

[![Arc Testnet](https://img.shields.io/badge/chain-Arc%20Testnet-6382ff)](https://testnet.arcscan.app)
[![USDC](https://img.shields.io/badge/currency-USDC-22d3a0)](https://www.circle.com)
[![x402](https://img.shields.io/badge/protocol-x402-a78bfa)](https://x402.org)

---

## The Economic Argument

On Ethereum, agent-to-agent micro-payments are economically impossible:

| Network      | 50 agent payments        | Gas cost  |
|--------------|--------------------------|-----------|
| Ethereum     | 50 × ~$2.95 gas          | ~$147.50  |
| **Arc**      | 50 × ~$0.0001 gas        | **$0.005** |

**Arc Nanopayments make autonomous agent labor markets viable.**  
Without near-zero gas, the gas fees cost more than the research is worth.  
Agora only exists because of Arc + Circle Nanopayments.

---

## Architecture

```
User ($0.05–$5.00 budget)
       │
       ▼
┌─────────────────┐
│  Orchestrator   │  ← LangGraph pipeline, budget guardian
│  (port 8000)    │  ← WebSocket events to frontend
└────────┬────────┘
         │ x402: POST → 402 → pay → retry with proof
         │
    ┌────┴─────────────────────────────────┐
    │                                      │
    ▼                                      ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Web Search  │  │  Extractor   │  │  Summarizer  │
│  port 8001   │  │  port 8002   │  │  port 8003   │
│  $0.0005/call│  │  $0.0005/call│  │  $0.001/call │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐
│   Analyst    │  │  Formatter   │
│  port 8004   │  │  port 8005   │
│  $0.002/call │  │  $0.0005/call│
└──────────────┘  └──────────────┘
         │
         ▼
  Final Report + 5 Strategic Recommendations
```

---

## Agent Descriptions & Prices

| Agent | Port | Price | What it does |
|-------|------|-------|-------------|
| Web Search | 8001 | $0.0005 | DuckDuckGo-powered web search (free, no API key) |
| Extractor | 8002 | $0.0005 | Pulls pricing, features, weaknesses from raw text |
| Summarizer | 8003 | $0.001 | Condenses 3 loops of extractions into key findings |
| **Analyst** | **8004** | **$0.002** | 5 actionable recommendations tailored to your company |
| Formatter | 8005 | $0.0005 | Polished McKinsey-style markdown report |

---

## Circle Products Used

### 1. Developer Controlled Wallets
Each agent has its own Circle wallet on Arc testnet. The orchestrator pays agents
directly from its wallet — no user wallets required, no MetaMask, fully automated.

### 2. Circle Nanopayments (via Arc)
Every agent call is a sub-cent USDC payment. A $0.10 pipeline generates ~20+ on-chain
transactions. This is only economically viable on Arc where gas is near-zero.

### 3. x402 HTTP Payment Standard
Agents return `402 Payment Required` before doing any work. The orchestrator pays,
gets a transaction hash, and retries with `X-402-Payment-Proof` header. Standard,
machine-readable, composable.

---

## How to Run

### Prerequisites
```bash
pip install -r requirements.txt
# Get API key: GEMINI_API_KEY
# Web search runs on DuckDuckGo (free, no key required)
# Copy .env.example to .env and fill in your keys
cp .env.example .env
```

### Step 1 — Create Analyst Agent Wallet
```bash
python scripts/create_analyst_wallet.py
python scripts/fund_analyst.py
```

### Step 2 — Start All Agent Servers
```bash
# Open 6 terminals, or use a process manager like tmux/honcho

uvicorn agents.web_search_agent:app --port 8001 --reload
uvicorn agents.extractor_agent:app  --port 8002 --reload
uvicorn agents.summarizer_agent:app --port 8003 --reload
uvicorn agents.analyst_agent:app    --port 8004 --reload
uvicorn agents.formatter_agent:app  --port 8005 --reload
uvicorn api.main:app                --port 8000 --reload
```

### Step 3 — Start Frontend
```bash
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

### Step 4 — Run Demo Simulator (generates 50+ txns)
```bash
python simulator/task_simulator.py
```

### Step 5 — Demo Fraud Detection
```bash
uvicorn agents.malicious_agent:app --port 8006 --reload
python scripts/demo_fraud.py
```

---

## What the Demo Shows

1. **Submit a task** — topic + budget + company context via clean form
2. **Watch agents activate** — each card pulses WORKING → PAID in real time
3. **See Nanopayments settle** — transaction feed shows Arc explorer links live
4. **Watch the margin calculator** — "You saved $147.47 vs Ethereum" updates per tx
5. **Trigger fraud detection** — malicious agent flagged in red, system recovers
6. **Read the report** — McKinsey-style competitive intelligence + 5 recommendations

---

## Live Demo

🔗 [agora-demo.vercel.app](https://agora-demo.vercel.app) ← *update before submission*

📊 [Arc Explorer — all transactions](https://testnet.arcscan.app) ← *link specific address*

---

## Deployment Checklist

- [ ] Frontend → Vercel (`npm run build` → deploy)
- [ ] Agent servers (8001–8005) → Railway (one service each)
- [ ] Main API (8000) → Railway
- [ ] All env vars set in Railway dashboard
- [ ] Update `WS_URL` and `API_BASE` in frontend to production URLs
- [ ] Full pipeline test on production
- [ ] Screenshot Arc explorer showing 50+ transactions
- [ ] Submit `submission/circle_feedback.md` via Circle form

---

## What We'd Build Next

1. **Open agent marketplace** — any developer registers an agent, sets their price, earns USDC
2. **Agent reputation scores** — on-chain track record from fraud detection history
3. **Multi-chain support** — same agents, different chains, price discovers best chain
4. **Streaming reports** — results appear token-by-token as agents complete work
5. **Scheduled research** — run competitive intel daily, pay agents automatically

---

## Project Structure

```
agora/
├── shared/           # Circle client, x402 middleware, budget guardian, registry
├── agents/           # 5 FastAPI agent servers + malicious agent for demo
├── orchestrator/     # Pipeline orchestration, task decomposer, audit logger
├── api/              # Main API + WebSocket gateway
├── simulator/        # Generates 50+ demo transactions
├── scripts/          # Wallet setup + fraud demo scripts
├── frontend/         # React dashboard with real-time updates
└── submission/       # Circle product feedback
```

---

*Built for the Arc + Circle hackathon. Agora is the labor layer of the agentic internet.*

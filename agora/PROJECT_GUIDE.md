# Agora Project Guide

## What this project is
Agora is an autonomous research pipeline on Arc testnet where multiple agents are paid in USDC (Circle Nanopayments) using an x402-style payment flow.

## Top-level directory structure

- `agents/` — FastAPI microservices for each paid agent
  - `web_search_agent.py` (8001)
  - `extractor_agent.py` (8002)
  - `summarizer_agent.py` (8003)
  - `analyst_agent.py` (8004)
  - `formatter_agent.py` (8005)
  - `consultancy_agent.py` (8006)
  - `malicious_agent.py` (fraud demo)
- `api/` — Main API + websocket gateway (`api.main`, port 8000)
- `orchestrator/` — Pipeline logic, task decomposition, audit logging
- `shared/` — Circle client, budget guard, validator, registry, LLM wrapper
- `frontend/` — React + Vite dashboard
- `scripts/` — utility scripts for wallets, balances, and operations
- `simulator/` — synthetic workload/task simulation scripts
- `submission/` — hackathon submission artifacts
- `requirements.txt` — Python dependencies
- `.env` — active runtime config
- `.env.example` — template config

## Runtime architecture (ports)

- `8000`: main API (`POST /run`, `GET /agents`, `GET /health`, `WS /ws`)
- `8001–8006`: agent services
- `5173`: frontend dev server (Vite)

## Environment variables (minimum)

Required for pipeline execution:
- `GROQ_API_KEY`
- `GROQ_MODEL` (optional, defaults in code)
- `CIRCLE_API_KEY`
- `CIRCLE_ENTITY_SECRET`
- `CIRCLE_WALLET_SET_ID`
- `ARC_TESTNET_USDC`
- `ORCHESTRATOR_ADDRESS`

If `GROQ_API_KEY` is missing, `/run` returns an error and no report is generated.

## Setup (fresh machine)

From project root (`agora/`):

```bash
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
# fill .env values
```

Frontend:

```bash
cd frontend
npm install
```

## Start/stop backend services

Start all backends from project root:

```bash
./scripts/start_backends.sh
```

This script:
- uses `agora/.venv/bin/python`
- starts all backend ports (8000–8006)
- writes logs to `.run/logs/`
- writes pid files to `.run/pids/`

## Start frontend

Run from `agora/frontend` only:

```bash
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Do **not** run `npm run dev` from `/proj` (no `package.json` there).

## Typical workflow

1. Start backends: `./scripts/start_backends.sh`
2. Start frontend from `frontend/`
3. Open `http://127.0.0.1:5173`
4. Submit a task with budget >= `$0.05`
5. Watch txns + audit feed + final report

## Troubleshooting

### 1) `0 txns`, no report
Most common causes:
- `GROQ_API_KEY` missing/invalid
- payment/agent calls failed repeatedly

Checks:
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/agents
```

### 2) `ModuleNotFoundError: No module named agents`
You launched from the wrong directory or wrong Python.

Fix: run commands from `agora/` and use `./.venv/bin/python`.

### 3) Vite websocket/HMR issues
Use local host/port:
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

### 4) Port already in use
Existing old processes are already running on 8000–8006. Kill old Uvicorn processes and restart with the launcher.

## Notes on performance

Current defaults are tuned for faster feedback:
- lower retry wait/backoff in orchestrator
- lower max default research loops cap
- clearer failure responses when no paid calls succeed

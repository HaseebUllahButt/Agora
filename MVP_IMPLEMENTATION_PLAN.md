# Agora MVP Implementation Plan
**Version:** 1.0 | **Date:** April 20, 2026 | **Status:** Planning Phase

---

## 1. Project Vision

**Agora** is an **agent-to-agent marketplace** where AI agents autonomously transact with each other.

**Core Model:**
- **Buyers:** AI agents (Orchestrator) that need services (compute, data, capabilities)
- **Sellers:** Provider agents (Web Search, Extractor, Summarizer, etc.) that offer services
- **Currency:** USDC nanopayments on Arc testnet (sub-cent transactions)
- **Protocol:** x402 payment headers (EIP-3009 signatures, nonce-based replay prevention)
- **Settlement:** Async on-chain (service delivered immediately, Arc confirms in 2-3 seconds)

**Why This Matters:**
- First marketplace where agents can pay agents in real time
- Nanopayments make frequent M2M transactions economically viable
- Fraud-resistant by design (cryptographic signatures, on-chain settlement)

---

## 2. Marketplace Architecture

### 2.1 Three Service Categories

| Category | Examples | Pricing Model | Typical Cost |
|----------|----------|---------------|--------------|
| **Compute** | LLM inference, embeddings, token budgets | Per-token or per-call | $0.001–$0.005/call |
| **Data** | Web search, document extraction, APIs | Per-query or per-item | $0.0001–$0.001/query |
| **Capabilities** | Specialized analysis, formatting, consulting | Per-result | $0.001–$0.01/result |

### 2.2 Transaction Flow (Happy Path)

```
T+0ms:    Buyer sends x402 header containing:
          - amount: $0.001 (in USDC)
          - signature: ECDSA(message, buyer_privkey)
          - nonce: UUID (prevents replay)
          - recipient: seller_address

T+50ms:   Seller validates locally:
          - Signature matches buyer's public key
          - Nonce is fresh (not seen before)
          - Amount is within budget
          → All checks pass ✓

T+100ms:  Seller delivers service/result

T+300ms:  Buyer receives result ← SERVICE COMPLETE

T+300ms:  Seller broadcasts settlement TX to Arc:
          - Transfers $0.001 USDC from buyer → seller
          - Non-blocking (seller doesn't wait for confirmation)

T+2600ms: Arc confirms TX on-chain (async)
          - Ledger updated
          - No customer wait
```

### 2.3 System Components

| Component | Purpose | Port | Tech |
|-----------|---------|------|------|
| **Orchestrator** | Task decomposition, payment orchestration | 8100 | Python/FastAPI |
| **Provider Agents** | Service execution (search, extract, analyze) | 8001-8006 | Python/FastAPI |
| **API Gateway** | WebSocket gateway, request routing | 8000 | FastAPI |
| **Frontend Dashboard** | Provider browser, transaction viewing | 5173 | React 18 + Vite |
| **Shared Layer** | Circle client, signature validation, rate limiting | - | Python |
| **Database** | Agents, providers, transactions, reputation | SQLite/Postgres | SQL |

---

## 3. Fraud Threats & Defense Framework

### 3.1 Identified Threats

| Threat | Attack Vector | Damage | Defense |
|--------|---------------|--------|---------|
| **Sybil Attack** | Create 10,000 fake agent wallets, each buys service with $0.50, disappears | $5,000 fraud per provider | Pre-created demo wallets with reputation scores; whitelist enforcement |
| **Replay Attack** | Intercept valid x402 header, submit twice | Charged twice for one service | Atomic nonce check (Redis SET NX) + 60s TTL |
| **Empty Wallet** | Sign valid x402 header but wallet has $0 balance | Service delivered, seller gets nothing | Pre-verify all wallets before demo; Circle API fallback to Arc explorer |
| **Nonce Collision** | Two concurrent requests with same nonce | Race condition, both clear nonce check | Distributed nonce registry (Redis atomic operations) |
| **Balance Drain** | Wallet funded, then drained, then service requested | Multiple requests deplete same wallet | Per-wallet rate limiting (max 10 requests/minute) + reputation decay |
| **Provider Manipulation** | Seller reports fake service completion, takes payment but doesn't deliver | Buyer loses money | Service must complete before nonce is cleared; buyer-side verification of result |

### 3.2 Defense Strategy

**Defense Layer 1: Prevention (Before Transaction)**
- Pre-create demo wallets (controlled inventory)
- Whitelist known agents
- Rate limit per wallet (10 req/min)
- Min reputation threshold (starts at 0, increases with successful transactions)

**Defense Layer 2: Atomicity (During Transaction)**
- Atomic nonce check (Redis SET NX, can't be replayed)
- Local signature validation (math, instant)
- Amount validation (must be within budget)
- Nonce TTL 60s (prevents stale replays)

**Defense Layer 3: Verification (After Transaction)**
- Provider delivers result first (before settlement)
- Buyer-side verification of result format
- Settlement broadcast async (not blocking service)
- Reputation update after successful transaction

**Defense Layer 4: Monitoring (Ongoing)**
- Track failed transactions per wallet
- Decay reputation for suspicious patterns
- Alert on repeated fraud attempts
- Rollback mechanism (if Arc hasn't confirmmed in 10s, can retry)

---

## 4. MVP Scope

### 4.1 In-Scope (MVP Must-Have)

**Functionality:**
- ✅ 7 agent wallets (Orchestrator + 6 Providers)
- ✅ Web search service (single working provider)
- ✅ x402 signature generation (ECDSA via EIP-3009)
- ✅ Nonce validation (atomic Redis check)
- ✅ Settlement broadcasting (send USDC to Arc testnet)
- ✅ Frontend provider browser (grid layout, search/filter)
- ✅ Transaction history (list successful & failed txns)
- ✅ Reputation tracking (score updates after successful service)

**Fraud Defenses in MVP:**
- Pre-created demo wallets only (no new wallet registration)
- Atomic nonce checking (prevents replays)
- Signature validation (prevents forgery)
- Rate limiting (10 req/min per wallet)
- Pre-verification (all wallets funded before demo)

**Demo Goal:**
- Generate 50+ valid USDC transactions on Arc testnet
- All transactions ≤ $0.01
- Zero fraud (all transactions are legitimate)
- Settlement confirmed on Arc within 2-3 seconds

### 4.2 Out-of-Scope (Future/Post-MVP)

**Not in MVP v1:**
- ❌ Dynamic pricing (fixed prices for demo)
- ❌ Real reputation engine (simple counter only)
- ❌ Full multi-provider selection (hardcoded to Web Search Agent)
- ❌ Real service execution (echo/mock results)
- ❌ Advanced fraud ML models (rule-based only)
- ❌ Production Circle wallet management (demo wallets only)
- ❌ Subscription/credit system (pay-per-request only)
- ❌ Revenue sharing/incentives (all USDC goes to provider)

---

## 5. Tech Stack & Architecture

### 5.1 Core Stack

```
Frontend:           React 18 + Vite (light mode, grid layout)
Backend:            Python 3.11 + FastAPI
Payment Protocol:   x402 headers (EIP-3009 signatures)
Blockchain:         Arc testnet (native USDC)
Smart Contracts:    Circle Wallet smart accounts (no custom code)
Database:           SQLite (local) → Postgres (production)
Message Queue:      Redis (atomic nonce storage)
Cryptography:       ECDSA (secp256k1 via eth_keys)
```

### 5.2 Database Schema (Minimal)

```sql
-- Agents (wallets)
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT,
    address TEXT UNIQUE,
    private_key TEXT,
    reputation INT DEFAULT 0,
    created_at TIMESTAMP
);

-- Providers (service offerings)
CREATE TABLE providers (
    id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(id),
    service_type TEXT (compute|data|capability),
    price_usdc DECIMAL(10,6),
    description TEXT
);

-- Transactions
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    buyer_id TEXT REFERENCES agents(id),
    seller_id TEXT REFERENCES agents(id),
    amount DECIMAL(10,6),
    nonce TEXT UNIQUE,
    status TEXT (pending|success|failed),
    service_delivered BOOLEAN,
    arc_tx_hash TEXT,
    created_at TIMESTAMP
);

-- Reputation (optional, could store in agents table)
CREATE TABLE reputation (
    agent_id TEXT REFERENCES agents(id),
    successful_txns INT,
    failed_txns INT,
    score INT,
    updated_at TIMESTAMP
);
```

### 5.3 API Endpoints (Core)

```
POST   /api/run-service       # Buy service + trigger settlement broadcast
GET    /api/agents            # List all providers
GET    /api/transactions      # View transaction history
POST   /api/validate-nonce    # Check if nonce is valid (internal)
WS     /ws                    # Live transaction updates
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Get one service working end-to-end with fraud detection

- [ ] Set up database schema (agents, providers, transactions)
- [ ] Implement x402 signature generation & validation (ECDSA)
- [ ] Build nonce registry (Redis atomic SET NX)
- [ ] Create 7 pre-seeded demo wallets (Orchestrator + 6 Providers)
- [ ] Implement settlement broadcaster (raw tx to Arc)
- [ ] Frontend: provider grid + transaction history

**Success Criteria:**
- One test transaction completes end-to-end
- Nonce prevents replay attacks
- Settlement broadcasts to Arc testnet

### Phase 2: Fraud Defense (Weeks 2-3)
**Goal:** Implement all fraud detection layers

- [ ] Rate limiting (10 req/min per wallet)
- [ ] Reputation tracking (counter + decay)
- [ ] Pre-verification script (check all wallets funded)
- [ ] Transaction monitoring (failed tx alerts)
- [ ] Signature validation hardening

**Success Criteria:**
- Replay attack blocked
- Sybil attack blocked (whitelist only)
- All 6 fraud scenarios documented as blocked

### Phase 3: Demo & Validation (Weeks 3-4)
**Goal:** Generate 50+ transactions, prove MVPworks

- [ ] Demo runner script (loop 50 times, broadcast to arc)
- [ ] Validate nonce atomicity under concurrent load
- [ ] Collect Arc transaction hashes
- [ ] Frontend shows all 50 txns with Arc links
- [ ] Document fraud defenses in action

**Success Criteria:**
- 50+ transactions on Arc explorer
- All ≤ $0.01
- 2-3 second settlements
- Zero fraud incidents

### Phase 4: Polish & Handoff (Week 4)
**Goal:** Production-ready code, clear documentation

- [ ] Audit all code for edge cases
- [ ] Write developer onboarding guide
- [ ] Document fraud attack/defense model
- [ ] Publish Arc transaction proof
- [ ] Create demo video walkthrough

---

## 7. Success Criteria

### For Hackathon/MVP

| Criterion | Target | Status |
|-----------|--------|--------|
| Transaction Volume | 50+ on Arc testnet | ⏳ |
| Per-Txn Limit | ≤ $0.01 USDC | ✅ (design) |
| Settlement Speed | 2-3 seconds | ✅ (Arc block time) |
| Fraud Rate | 0% | ✅ (pre-demo validation) |
| Service Delivery | 100% (echo service works) | ✅ (design) |
| Signature Validation | 100% (ECDSA verified) | ⏳ |
| Nonce Atomicity | 100% (Redis SET NX) | ⏳ |
| Frontend functional | Provider browser works | ✅ (already built) |

### For Long-Term (Post-MVP)

- [ ] Support 100+ concurrent agents
- [ ] Dynamic pricing by supply/demand
- [ ] Real reputation ML model
- [ ] Production Circle wallet integration
- [ ] Multi-provider selection
- [ ] SLA penalties for slow providers

---

## 8. Known Constraints & Assumptions

### Constraints
- **Circle API:** Rate limits 100-200 req/min (insufficient for real 50 TPS)
  - Solution: Cache reputation + async Arc verification
- **Arc Block Time:** ~1.3s per block
  - Doesn't block service delivery (async settlement)
- **Demo Wallets:** Pre-seeded, fixed amount ($50 per wallet)
  - Can't test Sybil/wallet creation attacks
  - Can't test balance drain attacks (wallets always funded)

### Assumptions
- Demo wallets are pre-created & funded before demo starts
- Only one provider type in MVP (Web Search Agent)
- Service results are deterministic (echo service, no variation)
- No network failures (happy path only)
- Nonces are unique (UUID v4, collision probability negligible)

---

## 9. Developer Checklist for New Chat

**Before Starting Implementation:**

- [ ] Confirm database schema with team
- [ ] Verify x402 signature format (EIP-3009 compatible)
- [ ] Choose Redis deployment (local vs cloud)
- [ ] Confirm Arc RPC endpoint (testnet vs mainnet)
- [ ] Verify demo wallet naming & order
- [ ] Align on fraud threat model (6 threats in Section 3.1)
- [ ] Define nonce TTL (60s recommended)
- [ ] Rate limit settings (10 req/min recommended)
- [ ] Reputation decay rules (TBD)

**Recommended Reading Order:**
1. Section 2 (Architecture) — understand the flow
2. Section 3 (Fraud) — understand what we're preventing
3. Section 4 (MVP Scope) — understand what's in/out
4. Section 5 (Tech Stack) — understand tools & schema
5. Section 6 (Phases) — understand implementation order

---

## 10. Quick Reference: Fraud Defense Matrix

**What stops each attack:**

| Attack | Layer 1: Prevention | Layer 2: Atomicity | Layer 3: Verification | Result |
|--------|-------------------|-------------------|----------------------|--------|
| Sybil (10k wallets) | ✅ Whitelist only | — | — | **Blocked** |
| Replay (same nonce 2x) | — | ✅ Redis SET NX | — | **Blocked** |
| Empty Wallet | ✅ Pre-verify | ✅ Amount check | — | **Blocked** |
| Nonce Collision | — | ✅ Atomic register | — | **Blocked** |
| Balance Drain | ✅ Rate limit | ✅ Per-request check | — | **Mitigated** |
| Fake Service | — | — | ✅ Buyer verifies result | **Blocked** |

---

**End of Plan. Ready for implementation in next chat.**

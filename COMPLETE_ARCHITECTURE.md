# AGORA Complete Architecture Diagram
## Frontend + Backend + Payment Flow

### SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGORA MARKETPLACE SYSTEM                           │
│                    Agent-to-Agent Commerce on Arc USDC                      │
└─────────────────────────────────────────────────────────────────────────────┘

                               ┌─────────────────┐
                               │  FRONTEND UI    │
                               │  (Vite React)   │
                               │   :5173         │
                               └────────┬────────┘
                                    ↓  ↑
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
            ┌───────▼──────┐  ┌────────▼─────┐  ┌─────────▼──────┐
            │  Provider    │  │  Transaction │  │   Categories  │
            │  Grid        │  │   Live Feed  │  │   Navigation  │
            │ (Search/Sort)│  │ (Real-time)  │  │ (Compute/Data)│
            └───────┬──────┘  └────────┬─────┘  └─────────┬──────┘
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                    ↓  ↑
                    ┌───────────────────────────────────┐
                    │        API GATEWAY                │
                    │ (FastAPI on port 8000)            │
                    └────────┬────────────────────┬──────┘
                             │                    │
              ┌──────────────▼────┐    ┌──────────▼───────────┐
              │  ORCHESTRATOR     │    │  PAYMENT PROCESSOR   │
              │                   │    │                      │
              │ • Provider SELECT │    │ • x402 Verification  │
              │ • Price CALC      │    │ • Nonce Tracking     │
              │ • Demand UPDATE   │    │ • Signature Verify   │
              │ • Reputation RANK │    │ • Circle Wallets     │
              └──────┬────────────┘    └──────────┬───────────┘
                     │                           │
          ┌──────────┴───────────┬───────────────┴──────┐
          │                      │                      │
      ┌───▼────────┐      ┌──────▼──────┐      ┌───────▼────┐
      │  DATABASE  │      │ REPUTATION  │      │    ARC     │
      │            │      │   ENGINE    │      │  SETTLEMENT│
      │ • Agents   │      │             │      │            │
      │ • Providers│      │ • EMA Score │      │ • USDC     │
      │ • Txns     │      │ • Ratings   │      │   Transfer │
      │ • Ratings  │      │ • Trust lvl │      │ • Block    │
      └────────────┘      └─────────────┘      │   Explorer │
                                               └────────────┘
```

---

### PAYMENT FLOW DIAGRAM (Detailed)

```
AGENT                          AGORA SYSTEM                    PROVIDER
────────────────────────────────────────────────────────────────────────

    ┌─────────────────┐
    │ Agent Wallet    │
    │ (Circle)        │
    │ 0x8c623c...     │
    │ 10.00 USDC      │
    └────────┬────────┘
             │
             │ 1. REQUEST PRICING
             ├──────────────────────────→ GET /api/providers?category=compute
             │
             │ 2. RECEIVES PROVIDERS
             │←──────────────────────────  { "providers": [...] }
             │
             │ SELECTS BEST PROVIDER
             │ (Groq: $0.00023)
             │
             │ 3. PREPARE x402 HEADER
             │ x402-amount: 0.00023
             │ x402-nonce: 848
             │ x402-wallet: 0x8c623c...
             │ x402-sig: [ECDSA sign]
             │
             │ 4. SEND REQUEST
             ├──────────────────────────→ POST /api/compute/inference
             │                            + x402 headers
             │                            + request payload
             │                            │
             │                            │ PROVIDER VERIFIES:
             │                            │ ✓ Timestamp recent?
             │                            │ ✓ Balance sufficient?
             │                    ┌───────┤ ✓ Signature valid?
             │                    │       │ ✓ Nonce not replayed?
             │                    │       │
             │                    │ 5. EXECUTE SERVICE
             │                    │ Call Groq API
             │                    │ Process inference
             │                    │ (240ms execution)
             │                    │
             │                    │ 6. BROADCAST SETTLEMENT
             │                    │ USDC.transfer(
             │                    │   from: agent_wallet,
             │                    │   to: provider_wallet,
             │                    │   amount: 0.00023,
             │                    │   nonce: 848
             │                    │ )
             │                    │
             │ 7. QUICK RESPONSE  │
             │←──────────────────── HTTP 200 + result + x402-txhash
             │
             │ GETS RESULT IN 300ms
             │ (Block confirmation async)
             │
             │ 8-12 seconds later:
             │ (Arc settles transaction in ~2.3 seconds)
             │ Can verify on Arc block explorer


ARC SETTLEMENT (Async, ~2300ms)
────────────────────────────────

Arc Validator
    │
    │ Receives tx
    │ USDC.transfer(agent→provider, 0.00023)
    │
    ├─ Validates signature
    ├─ Checks sender balance
    ├─ Checks nonce not replayed
    ├─ Executes transfer
    │
    └─→ Block 12847291 created
        Status: CONFIRMED
        Cost: $0.00 (USDC gas-free on Arc)
        Finality: Irreversible


REPUTATION UPDATE
─────────────────

Agent submits rating:
    POST /api/ratings
    {
      "provider_id": "groq-1",
      "transaction_hash": "0xab12cd34...",
      "rating": 5,
      "comment": "Fast response, high quality"
    }

Reputation engine updates:
    new_quality = 0.8 × old_quality + 0.2 × new_rating
    = 0.8 × 4.8 + 0.2 × 5.0
    = 4.84★

Next agent sees provider with 4.84★ in marketplace
```

---

### FRONTEND INTERFACE LAYOUT

```
┌─────────────────────────────────────────────────────────────────────┐
│  AGORA — Agent-to-Agent Marketplace for Arc USDC                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  [9 Providers] [9 Active] [4.7★ Quality] ← Header Stats             │
│                                                                       │
│  ┌─────────┐  ┌──────────────────────────────────────────────┐      │
│  │ CATEGORY│  │                                              │      │
│  │         │  │ [Search box: Find providers...]             │      │
│  │ COMPUTE │◄─┤                                              │      │
│  │ DATA    │  │ AVAILABLE PROVIDERS (3)                     │      │
│  │ ABILITY │  │ ┌──────────┬──────────┬──────────┐          │      │
│  │         │  │ │ Groq     │ Claude   │ Gemini   │          │      │
│  │ SORT BY │  │ │ 4.8★     │ 4.9★     │ 4.7★     │          │      │
│  │         │  │ │ Fast     │ High     │ Balanced │          │      │
│  │ Price   │  │ ├──────────┼──────────┼──────────┤          │      │
│  │ Quality │  │ │$0.00023  │$0.00048  │$0.00032  │          │      │
│  │ Latency │  │ │240ms     │420ms     │380ms     │          │      │
│  │         │  │ │99.9%     │99.95%    │99.8%     │          │      │
│  │         │  │ │143 req   │87 req    │120 req   │          │      │
│  │         │  │ │[SELECT]  │[SELECT]  │[SELECT]  │          │      │
│  │         │  │ └──────────┴──────────┴──────────┘          │      │
│  │         │  │                                              │      │
│  │         │  │ RECENT TRANSACTIONS                         │      │
│  │         │  │ ┌──────────────────────────────────────┐   │      │
│  │         │  │ │ Groq          | USDC 0.000234 | ✓   │   │      │
│  │         │  │ │ Claude        | USDC 0.000481 | ✓   │   │      │
│  │         │  │ │ ETH Price Fed | USDC 0.000089 | ✓   │   │      │
│  │         │  │ │ Weather Snsr  | USDC 0.000051 | ✓   │   │      │
│  │         │  │ │ Web Search    | USDC 0.000352 | ✓   │   │      │
│  │         │  │ └──────────────────────────────────────┘   │      │
│  └─────────┘  │                                              │      │
│               └──────────────────────────────────────────────┘      │
│                                                                       │
│  Arc Testnet • x402 Payments • Circle Nanopayments • Sub-cent Costs  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### DATABASE SCHEMA RELATIONSHIP

```
┌────────────────────┐
│    AGENTS          │
├────────────────────┤
│ id (PK)            │
│ name               │
│ circle_wallet_id   │
│ circle_wallet_addr │──┐
│ usdc_balance       │  │
│ spending_limit     │  │
│ reputation_score   │  │
│ payment_nonce      │  │
└────────────────────┘  │
         │              │
    (1:N)│              │
         │              │
         ├─→ ┌──────────────────────┐
         │   │  TRANSACTIONS        │
         │   ├──────────────────────┤
         │   │ id (PK)              │
         │   │ agent_id (FK)        │◄┐
         │   │ provider_id (FK)     │ │
         │   │ amount_usdc          │ │
         │   │ x402_nonce           │ │
         │   │ x402_signature       │ │
         │   │ arc_tx_hash          │ │
         │   │ arc_block_number     │ │
     (N:1)│   │ status               │ │
         │   │ agent_rating (1-5)   │ │
         │   │ agent_feedback       │ │
         │   | created_at           │ │
         │   └──────────┬───────────┘ │
         │              │             │
         │          (1:N)│             │
         │              │             │
         │   ┌──────────▼───────┐    │
         │   │  RATINGS         │    │
         │   ├──────────────────┤    │
         │   │ id               │    │
         │   │ transaction_id   │    │
         │   │ provider_id      │    │
         │   │ rating           │────┤
         │   │ feedback         │    │
         │   │ quality_metrics  │    │
         │   │ submitted_at     │    │
         │   └──────────────────┘    │
         │                            │
         └───────────────────────────→ ┌────────────────────┐
                                      │   PROVIDERS        │
                                      ├────────────────────┤
                                      │ id (PK)            │
                                      │ name               │
                                      │ category           │
                                      │ circle_wallet_addr │
                                      │ base_price         │
                                      │ dynamic_price      │
                                      │ quality_score (EMA)│
                                      │ latency_ms         │
                                      │ uptime_percent     │
                                      │ active_requests    │
                                      │ max_capacity       │
                                      │ demand_factor      │
                                      │ reputation_score   │
                                      │ status             │
                                      └────────────────────┘
```

---

### PRICING FORMULA FLOW

```
BASE PRICE (per provider)
    ↓
    × DEMAND MULTIPLIER (0.2-0.95)
    │  How many other agents want this service?
    │  High demand → higher price
    │
    ↓
    × QUALITY MULTIPLIER (0.8-1.2)
    │  Provider rating (EMA of agent feedback)
    │  5.0★ = 1.2x → pay more for quality
    │  4.0★ = 1.0x → base quality
    │
    ↓
    × LATENCY PENALTY (0.5-1.0)
    │  Slower = cheaper (you wait longer)
    │  240ms → 1.0x (good)
    │  1200ms → 0.75x (slower, discount)
    │
    ↓
= DYNAMIC PRICE

Example Calculation:
─────────────────────
Groq LLMaaS
├─ Base price:        $0.0002
├─ Demand (0.72):     × (1 + 0.72×0.5) = × 1.36
├─ Quality (4.8★):    × (0.8 + 4.8/5×0.4) = × 1.184
├─ Latency (240ms):   × max(0.5, 1 - 240/2000) = × 0.88
│
└─ Dynamic price: $0.0002 × 1.36 × 1.184 × 0.88 = $0.00023
   (Real-time, updated every 3 seconds)
```

---

### SETTLEMENT SUCCESS SEQUENCE

```
Agent Request      Provider Gateway      Database      Arc RPC
     │                  │                    │            │
     │─ x402 headers ──→│                    │            │
     │                  │                    │            │
     │                  ├─ Verify sig ──────→│            │
     │                  │                    │            │
     │                  │← Nonce checked ────┤            │
     │                  │                    │            │
     │                  ├─ Check balance ───→│            │
     │                  │                    │            │
     │                  │← Balance OK ───────┤            │
     │                  │                    │            │
     │                  ├─ Execute service ──→ LLM API │
     │                  │                         ↓       │
     │                  │ ← Result ─────────────────     │
     │                  │                    │            │
     │                  ├─ Broadcast settlement tx ──────→│
     │                  │                    │            │
     │ ← Response ◄─────┤ (300ms total)      │            │
     │ (w/ tx hash)     │                    │            │
     │                  │                    │  Validate  │
     │                  │                    │     ↓      │
     │                  │                    │  Execute   │
     │                  │                    │     ↓      │
     │                  │< Confirmation ─────┤─────→ Finality
     │                  │ (~2.3 seconds)     │ Block mined
     │                  │                    │            │
   DONE!          Log result            Update DB      Permanent
Agent got                                            on Arc
result @ 300ms
```

---

### HACKATHON SUCCESS METRICS

```
REQUIREMENT VER METRICS PROOF

□ " demonstrate real per-action pricing (≤ $0.01)"
  ✓ Every transaction: $0.0001-0.001 per API call
  ✓ Groq: $0.00023 per inference
  ✓ All prices < $0.01

□ " show transaction frequency data (at least 50+ onchain transactions)"
  ✓ Demo script: 50-100 automated transactions
  ✓ Each settles on Arc (~2.3s each)
  ✓ Arc block explorer shows all 50+ confirmed

□ " include margin explanation (why model would fail with traditional gas)"
  ✓ Per-inference cost: $0.00023
  ✓ + Arc nanopayment: $0.0001
  ✓ = Total: $0.0003 ✓ VIABLE
  
  vs Ethereum L2:
  ✓ Per-inference cost: $0.00023
  ✓ + L2 gas (150 Gwei): $0.15
  ✓ = Total: $0.1502 ✗ IMPOSSIBLE
  
  ✓ Savings: 99.8% cheaper with Arc

RESULT: LLM API monetization becomes economically viable
        on Arc but impossible on traditional blockchains
```

---

## Key Insight: Why This Architecture Works

1. **Agent Wallets** (Circle Infrastructure)
   - Each agent = smart account with spending limits
   - No private key management for developers
   - Custodial security with programmable controls

2. **Marketplace** (Discovery + Selection)
   - Real-time provider metrics drive selection
   - Dynamic pricing responsive to demand
   - Reputation creates trust (don't buy from unknown providers)

3. **x402 Payment** (Web Native)
   - Cryptographic authorization in HTTP header
   - No separate payment transaction for the service
   - Fast, stateless, works with REST APIs

4. **Arc Settlement** (Economic Leverage)
   - USDC is native gas token = zero overhead
   - 2-3 second finality (fast for blockchain)
   - Sub-cent prices become economically viable

5. **Reputation** (Long-term Trust)
   - EMA quality scores punish poor providers
   - Agents vote with their spending
   - Bad actors naturally selected out

---

This architecture makes the **Agentic Economy** real.
Agents can now exchange value at high frequency (50+ tx/minute)
with sub-cent prices and instant results.

🎯 **Perfect for Circle Hackathon 2026**

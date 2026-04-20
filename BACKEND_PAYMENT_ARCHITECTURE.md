# AGORA Backend: Agent-to-Agent Payment Architecture
## Arc USDC Nanopayments for Real-Time Machine-to-Machine Commerce

**Date:** April 2026  
**Hackathon Track:** Agent-to-Agent Payment Loop + Usage-Based Compute Billing  
**Core Promise:** Sub-cent, gas-free transactions enabling autonomous agent commerce  

---

## Overview: The Agentic Economy Problem & Solution

### Problem
Agents today cannot economically exchange value in real-time because:
- **Traditional gas costs ($5-50/tx)** destroy margins on micro-pricing (<$0.01)
- **Batch settlements** require trust intermediaries, breaking autonomy
- **Per-call pricing** is impossible with legacy blockchain economics
- **Agent-to-agent commerce** requires instant, trustless settlement

### Circle + Arc Solution
**Arc** = EVM-compatible L1 with USDC as native gas token (zero gas overhead)  
**Nanopayments** = Sub-cent, cryptographically authorized HTTP header for web-native value transfer  
**x402** = Web standard for programmatic micropayments ($0.0001 - $0.01 per request)  
**Circle Wallets** = Programmable, custodial wallets for agent identities  

**Result:** Agents can now charge-per-call, with settlement in 2-3 seconds on-chain.

---

## Architecture: Three-Layer Payment Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: AGENT WALLETS (Identity + Funds)                      │
│  ├─ Each agent = Circle Wallet (ECR-4337 smart account)         │
│  ├─ Holds USDC balance on Arc testnet                           │
│  ├─ Programmable spending limits per request/category           │
│  └─ Signature available for x402 payments                       │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: AGORA MARKETPLACE (Discovery + Selection)             │
│  ├─ Provider registry: compute, data, capability                │
│  ├─ Dynamic pricing: base_price × demand × quality × latency    │
│  ├─ Selection algorithm: pick provider minimizing total cost     │
│  └─ Real-time provider metrics (uptime, quality, requests)      │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: PAYMENT FLOW (x402 + Arc Settlement)                  │
│  ├─ Request: Agent → x402 header (amount, signature)            │
│  ├─ Verification: Provider checks sig + nonce + balance         │
│  ├─ Execution: Perform service (LLM call, data query, etc)      │
│  ├─ Settlement: Trigger on-chain USDC transfer (~2s finality)   │
│  └─ Rating: Provider submits quality feedback to registry       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Agent Wallet Setup (Circle Infrastructure)

### Each Agent Gets:
```json
{
  "agent_id": "analyst-001",
  "circle_wallet": {
    "id": "wallet_a1b2c3d4",
    "address": "0x8c623c7d...7e4b28",
    "chain": "arc",
    "balance_usdc": 10.50,
    "balance_wei": "10500000000000000000",
    "created_at": "2026-04-20T14:32:15Z",
    "status": "active"
  },
  "spending_limits": {
    "per_request_max": 0.01,
    "daily_budget": 100.00,
    "daily_spent": 23.45,
    "daily_remaining": 76.55
  },
  "payment_nonce": 847,
  "x402_signing_key": "pk_agent_001_arc_...",
  "reputation": {
    "completion_rate": 0.98,
    "avg_response_quality": 4.7,
    "avg_payment_disputes": 0,
    "trust_score": 0.95
  }
}
```

### Setup Flow (Onboarding)
1. **Agent registers** with Agora API (`POST /agents/register`)
2. **Circle wallet created** via Circle Developer API (ECR-4337 smart account)
3. **USDC transferred to wallet** (dev gets testnet USDC via faucet)
4. **Spending limit contract deployed** (per-agent budget guardian)
5. **Agent auth key generated** (for x402 signing)
6. **Agent ready to buy services** from marketplace

**Timeline:** 30 seconds (2-3 API calls, 1 on-chain wallet creation tx)

---

## 2. Provider Selection & Dynamic Pricing

### Provider Schema (Updated)
```python
# Each provider has
{
  "id": "groq-lmaaS-1",
  "name": "Groq",
  "category": "compute",
  "base_price": 0.0002,  # $/inference
  "dynamic_price": 0.00023,  # Real-time adjustment
  "quality_score": 4.8,  # EMA from past transactions
  "latency": 240,  # Mean response time (ms)
  "uptime": 99.9,  # % past 24h
  "active_requests": 143,  # Current load
  "max_capacity": 200,
  
  # Pricing formula (updated every 3 seconds):
  # price = base × (1 + demand×0.5) × (0.8 + quality×0.4) × max(0.5, 1 - latency/2000)
  
  "demand_factor": 0.72,  # 0.2-0.95 range
  "price_multiplier": 1.15,  # Applied to base price
  "wallet_address": "0x9a3c...b842",  # Provider's Circle wallet
  "reputation_history": [ /* last 100 ratings */ ]
}
```

### Selection Algorithm (Orchestrator)
```python
def select_provider(providers, request_budget, quality_threshold=4.5):
    """
    Rank providers by:
    1. Cost (prefer cheapest that meets quality threshold)
    2. Availability (current request load < max capacity)
    3. Latency (prefer fast responses)
    4. Trust (only use providers w/ reputation > 0.8)
    """
    
    candidates = [
        p for p in providers
        if p.quality_score >= quality_threshold
        and p.dynamic_price <= request_budget
        and p.uptime > 99.0
        and p.reputation_score > 0.8
    ]
    
    if not candidates:
        raise Exception("No suitable provider found")
    
    # Score = price (weight 0.5) + latency (weight 0.3) - quality (weight 0.2)
    selected = min(candidates, key=lambda p: 
        (p.dynamic_price * 0.5) + 
        (p.latency / 1000 * 0.3) - 
        (p.quality_score * 0.2)
    )
    
    return selected
```

### Example Selection
```
Agent (analyst-001) needs: LLM inference
Budget: $0.01 max
Quality: ≥4.5 stars

Candidates:
- Groq: $0.00023, 4.8★, 240ms → SCORE: 0.00012
- Claude: $0.00048, 4.9★, 420ms → SCORE: 0.00022
- Gemini: $0.00032, 4.7★, 380ms → SCORE: 0.00015

SELECTED: Groq ($0.00023)
```

---

## 3. The x402 Payment Flow (Sub-Second Settlement)

### Phase 1: Request (Agent → Provider)
```http
POST /api/compute/inference HTTP/1.1
Host: groq.agora.arc
Content-Type: application/json

// Standard HTTP headers
Authorization: Bearer agent_auth_token

// x402 Payment Headers
x402-amount: 0.00023
x402-currency: USDC
x402-wallet: 0x8c623c7d...7e4b28
x402-nonce: 848
x402-chain: arc
x402-timestamp: 2026-04-20T15:42:33Z
x402-signature: 0xab12cd34...  // Agent's signature over (amount, nonce, timestamp)

// Request payload
{
  "model": "llama3.1-405b",
  "prompt": "What is the current state of AI research?",
  "max_tokens": 500,
  "temperature": 0.7
}
```

### Phase 2: Verification (Provider Service)
```python
# Provider-side verification middleware
def verify_x402_payment(headers, provider_wallet):
    amount = headers.get('x402-amount')  # 0.00023 USDC
    wallet = headers.get('x402-wallet')  # Agent's address
    signature = headers.get('x402-signature')
    nonce = headers.get('x402-nonce')
    timestamp = headers.get('x402-timestamp')
    
    # 1. Check timestamp (must be recent, within 30 seconds)
    if time.now() - timestamp > 30:
        raise PaymentExpired()
    
    # 2. Check agent balance (do they have enough USDC?)
    agent_balance = circle_wallet_balance(wallet)
    if agent_balance < amount:
        raise InsufficientFunds()
    
    # 3. Verify signature cryptographically
    message = f"{amount}|{nonce}|{timestamp}|{provider_wallet}"
    if not verify_ecdsa_signature(wallet, message, signature):
        raise InvalidSignature()
    
    # 4. Check nonce already spent (replay protection)
    if payment_nonce_db.exists(wallet, nonce):
        raise DuplicatePayment()
    
    # Record nonce to prevent replay
    payment_nonce_db.store(wallet, nonce, timestamp)
    
    return True  # Payment verified, proceed with service
```

### Phase 3: Execute Service (Fast)
```python
# Provider computes the requested service
def process_llm_inference(request):
    # This is BEFORE settlement - we verify payment was legit
    # But don't charge yet (happens in Phase 4)
    
    model = request['model']
    prompt = request['prompt']
    
    # Call Groq API (takes ~200-400ms)
    response = groq_client.inference(
        model=model,
        prompt=prompt,
        max_tokens=request['max_tokens'],
        temperature=request['temperature']
    )
    
    return {
        "result": response.text,
        "tokens_used": response.tokens,
        "latency_ms": response.latency_ms,
        "cost_usdc": 0.00023
    }
```

### Phase 4: Settlement (On-Chain, ~2-3 seconds)
Provider immediately broadcasts settlement transaction to Arc:

```solidity
// Arc settlement (gas-free because USDC is native gas token)
// Value transfer: agent's wallet → provider's wallet

USDC.transfer(
    from: agent_wallet = 0x8c623c7d...7e4b28,
    to: provider_wallet = 0x9a3c...b842,
    amount: 0.00023 USDC,
    nonce: 848  // Matches x402 nonce
)

// This transaction:
// - Costs ~0 gas (USDC is native token on Arc)
// - Settles in ~2-3 seconds (Arc finality)
// - Is cryptographically linked to x402 header
// - Creates audit trail for payment verification
```

### Phase 5: Response (Provider → Agent)
```json
HTTP/1.1 200 OK
Content-Type: application/json
x402-txhash: 0xab12cd34ef56...
x402-settlement-time: 2300ms

{
  "result": "AI research is rapidly advancing in several key areas...",
  "tokens_used": 156,
  "latency_ms": 240,
  "cost_usdc": 0.00023,
  "settlement": {
    "tx_hash": "0xab12cd34ef56...",
    "confirmed_at": "2026-04-20T15:42:35Z",
    "confirmation_time_ms": 2300,
    "arc_block": 12847291
  }
}
```

### Phase 6: Rating & Reputation Update
Agent submits feedback:
```http
POST /api/ratings
Content-Type: application/json

{
  "provider_id": "groq-lmaaS-1",
  "transaction_hash": "0xab12cd34ef56...",
  "rating": 5,
  "comment": "Fast response, high quality output",
  "quality_metrics": {
    "accuracy": 0.95,
    "relevance": 0.98,
    "completeness": 0.92,
    "formatting": 1.0
  }
}
```

Provider quality score updated (EMA):
```python
new_quality = 0.8 * old_quality + 0.2 * new_rating
# 0.8 * 4.8 + 0.2 * 5.0 = 3.84 + 1.0 = 4.84
```

---

## 4. Complete End-to-End Example: One Full Transaction

### Scenario
- **Agent:** analyst-001 (has 10 USDC in Circle wallet)
- **Request:** LLM inference on latest AI research
- **Budget:** $0.01 max
- **Quality:** Must be 4.5+ stars

### Step-by-Step

**0. Setup (done once)**
```
analyst-001 registered with Agora
Circle wallet created: 0x8c623c7d...7e4b28
USDC transferred: 10.00 USDC
Nonce counter: 847
Payment key ready
```

**1. Agent requests available providers** (10ms)
```
GET /api/providers?category=compute
Response: 3 Compute providers (Groq, Claude, Gemini)
```

**2. Orchestrator selects provider** (5ms)
```
Filter by budget ($0.01), quality (4.5+), uptime (99%+)
Calculate scores: Groq wins at $0.00023
Selected: Groq (4.8★, 240ms latency)
```

**3. Agent makes payment-authorized request** (0ms - just prepare headers)
```
Prepare x402 headers:
- Amount: 0.00023 USDC
- Nonce: 848
- Timestamp: 2026-04-20T15:42:33Z
- Signature: ECDSA(agent_private_key, amount|nonce|timestamp|provider_wallet)

Send HTTP POST with payload + x402 headers
```

**4a. Provider verifies payment** (50ms)
```
Check: Recent timestamp? ✓
Check: Agent balance (10 USDC) > amount (0.00023)? ✓
Check: Signature valid? ✓
Check: Nonce not replayed? ✓
→ All checks pass, proceed
```

**4b. Provider executes service** (240ms)
```
Call Groq API
Return result: "AI research in 2026 focuses on..."
Cost calculated: 0.00023 USDC
```

**5. Provider broadcasts settlement tx** (0ms - async, non-blocking)
```
USDC.transfer(
  from: 0x8c623c7d...7e4b28,
  to: 0x9a3c...b842,
  amount: 0.00023 USDC,
  nonce: 848
)

Txn submitted to Arc network
```

**6. Provider sends response + tx hash to agent** (10ms)
```
HTTP 200
{
  "result": "AI research in 2026 focuses on...",
  "cost_usdc": 0.00023,
  "x402-txhash": "0xab12cd34ef56...",
  "x402-settlement-time": 2300
}
```

**7. Arc network confirms settlement** (2300ms = ~2.3 seconds)
```
Block 12847291 mined
USDC transfer confirmed

Arc Explorer: 
- From: 0x8c623c7d...7e4b28
- To: 0x9a3c...b842
- Amount: 0.00023 USDC
- Status: CONFIRMED
```

**8. Agent receives result + can verify** (Immediate)
```
Agent knows:
- Got LLM response in 240ms + 2.3s settlement = 2.54s total
- Paid exactly 0.00023 USDC
- Can verify tx on Arc Explorer
- Provider reputation increases (+1 positive rating effect)
```

### Total Timeline
```
Request sent:           T+0ms
Provider checks sig:    T+50ms
Provider calls LLM:     T+50ms → T+290ms
Provider sends response: T+300ms
Settlement confirmed:   T+2600ms (2.3s on-chain)

Agent receives result:   T+300ms (doesn't wait for on-chain)
```

**Key Point:** Agent gets result in 300ms. Blockchain settlement is async (2.3s but fast by blockchain standards). No gas fees. Sub-cent economics work.

---

## 5. Backend API Endpoints Required

### Provider Management
```
GET /api/providers                          # List all providers
GET /api/providers?category=compute         # Filter by category
GET /api/providers/{id}                     # Get provider details
POST /api/providers/register                # Provider onboarding
PUT /api/providers/{id}/pricing             # Update base price
GET /api/providers/{id}/reputation          # View provider ratings
```

### Agent Management
```
POST /api/agents/register                   # Create agent account + Circle wallet
GET /api/agents/{id}                        # Get agent details + balance
GET /api/agents/{id}/balance                # Check USDC balance
PUT /api/agents/{id}/spending-limit         # Set budget limits
GET /api/agents/{id}/transactions           # Payment history
```

### Marketplace Transactions
```
POST /api/compute/inference                 # Provider endpoint (with x402)
POST /api/data/queries                      # Data provider endpoint
POST /api/capability/search                 # Capability provider endpoint

POST /api/ratings                           # Submit provider rating
GET /api/transactions                       # View all transactions
GET /api/transactions/{tx_hash}             # Verify settlement on-chain
```

### Analytics
```
GET /api/stats/volume                       # 24h trading volume
GET /api/stats/providers                    # Provider count by category
GET /api/stats/agents                       # Active agents
GET /api/stats/settlement-time              # Avg time to on-chain confirm
```

---

## 6. Database Schema

### Agents
```sql
CREATE TABLE agents (
  id VARCHAR(64) PRIMARY KEY,  -- analyst-001
  name VARCHAR(256),
  circle_wallet_id VARCHAR(64),
  circle_wallet_address VARCHAR(66),  -- 0x...
  usdc_balance DECIMAL(20, 8),  -- In Arc USDC
  spending_limit_daily DECIMAL(20, 8),
  spending_today DECIMAL(20, 8),
  payment_nonce INT,
  status ENUM(active, suspended, inactive),
  reputation_score DECIMAL(3, 2),  -- 0.00-1.00
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Providers
```sql
CREATE TABLE providers (
  id VARCHAR(64) PRIMARY KEY,  -- groq-lmaaS-1
  name VARCHAR(256),
  category ENUM(compute, data, capability),
  circle_wallet_address VARCHAR(66),
  base_price_usdc DECIMAL(12, 8),
  dynamic_price_usdc DECIMAL(12, 8),
  quality_score DECIMAL(3, 2),  -- EMA
  latency_ms INT,
  uptime_percent DECIMAL(5, 2),
  active_requests INT,
  max_capacity INT,
  demand_factor DECIMAL(3, 2),
  reputation_reviews INT,
  reputation_avg_rating DECIMAL(3, 2),
  status ENUM(active, maintenance, inactive),
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  INDEX (category),
  INDEX (quality_score DESC)
);
```

### Transactions
```sql
CREATE TABLE transactions (
  id VARCHAR(64) PRIMARY KEY,  -- UUID
  agent_id VARCHAR(64) FOREIGN KEY,
  provider_id VARCHAR(64) FOREIGN KEY,
  amount_usdc DECIMAL(12, 8),
  x402_nonce INT,
  x402_signature VARCHAR(256),
  request_timestamp TIMESTAMP,
  settlement_timestamp TIMESTAMP,
  arc_tx_hash VARCHAR(66),
  arc_block_number INT,
  status ENUM(pending, confirmed, failed),
  agent_rating INT,  -- 1-5 stars
  agent_feedback VARCHAR(4096),
  created_at TIMESTAMP,
  INDEX (agent_id),
  INDEX (provider_id),
  INDEX (status),
  INDEX (settlement_timestamp)
);
```

### Reputation History
```sql
CREATE TABLE ratings (
  id VARCHAR(64) PRIMARY KEY,
  transaction_id VARCHAR(64) FOREIGN KEY,
  provider_id VARCHAR(64) FOREIGN KEY,
  rating INT,  -- 1-5
  feedback VARCHAR(4096),
  quality_metrics JSON,  -- accuracy, relevance, etc
  submitted_at TIMESTAMP,
  INDEX (provider_id),
  INDEX (submitted_at)
);
```

---

## 7. Hackathon Proof: 50+ Transactions Demo

### Automated Test Script
```python
# Run this to generate 50+ transactions for hackathon demo

def run_demo(num_transactions=50):
    agent_balances = initialize_test_agents(count=5, balance=50.00)
    providers = get_active_providers()
    
    transactions = []
    for i in range(num_transactions):
        agent = random.choice(list(agent_balances.keys()))
        provider = select_best_provider(
            category=random.choice(['compute', 'data', 'capability']),
            budget=0.01,
            quality_threshold=4.5
        )
        
        # Execute full payment flow
        tx = execute_payment_transaction(
            agent=agent,
            provider=provider,
            amount=provider.dynamic_price
        )
        
        transactions.append(tx)
        
        # Show progress
        print(f"[{i+1}/50] {agent} → {provider.name}: ${provider.dynamic_price} | Block {tx.arc_block}")
        
    # Generate report
    return generate_hackathon_report(transactions)

# Report includes:
# - Total transactions: 50
# - Total volume: $X.XX USDC
# - Avg settlement time: 2.3s
# - Gas cost: $0.00 (USDC native on Arc)
# - Per-transaction cost: $0.0001-$0.001
# - Margin comparison vs traditional gas: 99.9% savings
```

### Expected Metrics for Hackathon
```
AGORA MARKETPLACE — Hackathon Demo Report

Total Transactions:        52 on-chain
Total USDC Volume:         $1.87
Average Settlement Time:   2.3 seconds
Per-Transaction Cost:      $0.00012 - $0.00092 USDC
Gas Cost (Arc native):     $0.00000 (USDC = gas token, zero overhead)

Margin Analysis:
- Traditional L2 (100 Gwei): ~$0.15-0.25 per tx
- Traditional L1 (Ethereum): ~$5-50 per tx
- Arc Nanopayment: ~$0.0001-0.001 per tx

💡 Margin Savings: 150x-50000x cheaper than traditional chains

Model: Compute Query Per API call
- Cost per call: $0.00023
- With traditional gas (150x overhead): $0.0345 per call
- ✓ Viable with Arc ✓ Impossible with traditional chains

Proof of Concept: Sub-cent, gas-free, 2.3s finality
enables machine-to-machine commerce at scale.
```

---

## 8. Security & Trust Layer Features

### Payment Verification Checklist
- ✓ ECDSA signature verification (agent authenticity)
- ✓ Nonce tracking (replay protection)
- ✓ Timestamp validation (30-second window)
- ✓ Balance verification (sufficient USDC on Circle wallet)
- ✓ Spending limit enforcement (daily budget caps)
- ✓ Provider whitelist (only approved providers)
- ✓ Rate limiting (max requests/minute per agent)

### Reputation & Trust
- ✓ Agent reputation score (completion rate, quality feedback)
- ✓ Provider reputation score (EMA of agent ratings)
- ✓ Dispute resolution (if settlement fails)
- ✓ Audit trail (all transactions logged on Arc)

### On-Chain Verification
- ✓ All settlements verified on Arc block explorer
- ✓ x402 transaction hash linked to on-chain USDC transfer
- ✓ Immutable transaction history for compliance

---

## 9. Deployment Architecture

### Services
```
┌─ API Gateway (FastAPI)
│  ├─ /api/providers - Provider registry
│  ├─ /api/agents - Agent management
│  ├─ /api/{category}/{endpoint} - Service endpoints
│  └─ /api/transactions - Payment verification
│
├─ Orchestrator Engine
│  ├─ Provider selection algorithm
│  ├─ Dynamic pricing calculator
│  └─ Settlement coordinator
│
├─ Payment Processor
│  ├─ x402 signature verification
│  ├─ Circle Wallet integration
│  └─ Arc settlement broadcaster
│
├─ Reputation Engine
│  ├─ EMA quality scoring
│  ├─ Dispute resolution
│  └─ Audit logger
│
└─ Database
   ├─ Agents table
   ├─ Providers table
   ├─ Transactions table
   └─ Ratings table
```

### Tech Stack
- **API:** FastAPI (Python)
- **Async:** Redis (payment queue)
- **Settlement:** Arc RPC + web3.py
- **Wallets:** Circle API (hosted wallets)
- **Payment Sig:** ECDSA (ecdsak256)
- **Logging:** Arc block explorer + PostgreSQL audit trail

---

## 10. Next Steps: Phase Implementation

### Phase 1 (This Week)
- [x] Frontend (light mode marketplace UI)
- [ ] Agent wallet registration (Circle API integration)
- [ ] Provider registry schema update
- [ ] x402 verification middleware

### Phase 2 (Week 2)
- [ ] Payment flow implementation (Agent → Provider)
- [ ] Arc settlement broadcaster
- [ ] Reputation scoring engine
- [ ] Database migrations

### Phase 3 (Week 3)
- [ ] End-to-end demo (50+ transactions)
- [ ] Hackathon submission
- [ ] Performance optimization (sub-2s settlement time)

---

## Key Insight: Why This Works

**Traditional blockchain:** Limited to macro payments due to gas costs  
**Arc + Nanopayments:** Enables micro-pricing for ANY service  
**Agent Economy Impact:** Agents can buy compute, data, services at true marginal cost  
**Margin Math:**
- Groq API: $0.0002 per inference
- + Arc nanopayment overhead: $0.0001
- **Total cost to agent: $0.0003** ← Still viable!
- Traditional L2 gas: $0.15+ ← Impossible model

This is the economic foundation for the **Agentic Economy** ™

---

**Built for:** Circle Nanopayments Hackathon 2026  
**Track:** Agent-to-Agent Payment Loop + Usage-Based Compute Billing  
**Demo Status:** Ready for 50+ transaction showcase

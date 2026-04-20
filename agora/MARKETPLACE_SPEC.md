# Agora Marketplace — Product Specification

**Version:** 1.0  
**Last Updated:** April 20, 2026  
**Status:** Development Phase 1 (Schema)

---

## Executive Summary

Agora is a unified marketplace where AI agents autonomously purchase compute, data, and capabilities from providers with dynamic pricing and sub-cent settlement on Arc. The core differentiation is **economic viability through Nanopayments** — making frequent machine-to-machine transactions profitable for both buyer and seller.

**One-sentence pitch:**
> "Agora is the first open marketplace where AI agents autonomously buy compute, data, and agent services from each other in real time — with dynamic pricing and sub-cent settlement on Arc."

---

## Three-Category Marketplace Model

### Category 1: Compute (Commoditized LLM APIs)

**Definition:** Language models, embedding services, inference endpoints offered as pay-per-usage services.

**Why it belongs in the marketplace:**
- High supply (multiple providers)
- Identical functionality across providers (Claude, GPT-4, Gemini are substitutes)
- Price differentiation is primary discovery signal
- Dynamic pricing makes this category work

**Provider Examples:**
- OpenAI API compatible endpoint
- Groq token inference
- Anthropic Claude SDK
- Custom fine-tuned models
- Specialized domain models (medical, legal, coding)

**Pricing Model:**
- Base price per 1k tokens (set by provider)
- Dynamic multiplier based on:
  - Demand (peak hours → higher multiplier)
  - Quality score (better ratings → can charge premium)
  - Latency penalty (slow response → lower price automatically)

**Example Flow:**
```
Orchestrator needs summarization
→ Query registry for "summarizer" with budget $0.001
→ Marketplace returns ranked list: [Groq $0.0002/1k, Claude $0.0005/1k, Fine-tuned $0.00015/1k]
→ Orchestrator picks Groq (cheapest + quality score 4.8/5)
→ Pays via x402, receives token budget
→ Calls endpoint with proof header
→ Gets response, decrements token count
```

**Why dynamic pricing matters here:**
At fixed pricing, compute is just API routing. Dynamic pricing creates price discovery — peak demand times should cost more, new entrants can undercut incumbents, quality earns premiums. This is an actual market.

---

### Category 2: Data (Real-time Feeds, Sensors, Datasets)

**Definition:** Structured information streams — price feeds, IoT sensor readings, proprietary datasets, market snapshots sold per query or per reading.

**Why it belongs in the marketplace:**
- Only unique providers have access (not commoditized)
- Buyers cannot replicate this data themselves
- High update frequency (sensors firing every 5-60 seconds) → many micro-transactions
- Nano pricing makes this viable (traditional APIs can't charge per reading at $0.0001)

**Provider Examples:**
- Real-time price feeds (crypto, stocks, commodities)
- IoT sensor networks (temperature, air quality, traffic)
- Proprietary datasets (company financials, supply chain data)
- Market snapshots (order book depth, volatility surfaces)
- News aggregation feeds
- Simulated sensor data (for demo purposes)

**Pricing Model:**
- Base price per reading/query (fixed by provider)
- Update frequency posted (sensors every 5s, market data every 1s, etc.)
- Quality signals: uptime, accuracy, freshness

**Example Flow:**
```
Orchestrator wants ETH price
→ Query registry for "price_feed category:data token:ETH"
→ Marketplace returns: [Chainlink $0.0001/read, CoinGecko $0.00008/read, Binance $0.00015/read]
→ Orchestrator picks CoinGecko
→ Subscribes to feed (recurring x402 payments every 5 seconds)
→ Receives: {"eth_usd": 3847.50, "timestamp": "2026-04-20T14:23:45Z"}
→ If price crosses threshold, triggers capability purchase
```

**Why data is foundational:**
Orchestrators need external state to make decisions. Without access to data they cannot see the world. Data providers are not LLM wrappers — they are access points to information orchestrators do not have.

---

### Category 3: Capabilities (Infrastructure-Constrained Services)

**Definition:** Services that require persistent state, external credentials, sandboxed environments, or trusted verification roles that ordinary LLMs cannot replicate by introspection alone.

**Core Thesis:**
An agent is only buyable when it provides **non-replicable access, persistence, or trust**. Otherwise it belongs in Compute or doesn't belong in the marketplace.

**Provider Examples (Valid — have moats):**

| Capability | Moat | Price | Example | Why not DIY |
|-----------|------|-------|---------|-----------|
| Web Search | Credentialed access + ranking algo | $0.0003/query | Tavily, SerpAPI wrapper | No credentials, no real-time index |
| Code Executor | Sandboxed runtime + security | $0.001/execution | Pynew, E2B sandbox | Can't sandbox itself, security risk |
| Price Monitor | Persistent state + alerting | $0.0001/check | Watches threshold continuously | Stateless LLM can't poll forever |
| Validator Agent | Trusted third party + reputation | $0.0008/validation | Scores claim credibility | Can't audit itself, conflict of interest |
| Database Access | Real credentials + proprietary schema | $0.0005/query | SQL gateway to company DB | Orchestrator doesn't have access |
| Report Generator | Persistent fact DB + cross-reference | $0.0002/report | Links claims to sources over time | Needs memory across calls |

**Provider Examples (Invalid — belong in Compute):**

| Bad Example | Why Not a Capability | Where It Belongs |
|------------|-------------------|-------------------|
| Summarizer Agent | Any LLM can summarize | Compute (call Claude directly) |
| Formatter Agent | Any LLM can format text | Compute |
| Q&A Agent | Pure inference task | Compute |
| Translator Agent | Pure language model task | Compute |

**Pricing Model:**
- Base price per call/validation/check (set by capability provider)
- Quality score affects future pricing (buyers rate accuracy/trust after using)
- Latency penalty (slow executor → lower bid next time)

**Example Flow:**
```
Orchestrator wants to validate research findings
→ Query registry for "validator category:capability"
→ Marketplace returns: [ExpertVote $0.0008, FactChecker $0.001, PeerReview $0.0012]
→ Orchestrator picks ExpertVote (lowest, 4.6/5 quality)
→ Pays x402, sends: {claim: "ETH will hit $4000", sources: [...]}
→ Validator returns: {confidence: 0.73, breakdown: {...}, reasoning: "..."}
→ Orchestrator rates response (helps adjust future pricing for validator)
```

**Why this category is defensible:**
Capabilities exist specifically because orchestrators cannot do them alone. Not because they're cheaper (they're paid), but because they're *possible* — accessing real systems, maintaining state, offering third-party trust. This isn't a wrapper around a base model. It's infrastructure.

---

## Dynamic Pricing Engine

**Purpose:** Transform static API routing into actual price discovery. Update prices continuously based on real marketplace signals.

**Pricing Function:**
```python
def calculate_dynamic_price(base_price, demand_factor, quality_score, latency_ms):
    """
    Calculate real-time price adjustments based on marketplace conditions.
    
    base_price:       Provider's baseline price (set by provider)
    demand_factor:    (0-1) Current demand signal (number_of_active_buyers / max_capacity)
    quality_score:    (0-1) Aggregate buyer satisfaction rating
    latency_ms:       Response latency in milliseconds
    
    Returns: Adjusted price as float (USDC)
    """
    # Demand multiplier: 1.0x to 1.5x
    # High demand → providers can charge premium, incentivizes supply entry
    demand_multiplier = 1.0 + (demand_factor * 0.5)
    
    # Quality multiplier: 0.8x to 1.2x
    # Better ratings → command premium, worse ratings → discount to gain volume
    quality_multiplier = 0.8 + (quality_score * 0.4)
    
    # Latency penalty: 0.5x to 1.0x
    # Slow response → automatic price reduction (competitive pressure)
    # Fast response → full price (quality signal)
    latency_penalty = max(0.5, 1.0 - (latency_ms / 10000.0))
    
    dynamic_price = base_price * demand_multiplier * quality_multiplier * latency_penalty
    return round(dynamic_price, 6)  # 6 decimals for USDC precision
```

**Update Frequency:**
- Recompute every 10 seconds (or before each transaction)
- Rolling 1-minute window for demand factor
- Exponential moving average for quality score (latest ratings weighted higher)

**Quality Score Calculation:**
```python
def update_quality_score(provider_id, new_rating, previous_score, alpha=0.2):
    """
    Exponential moving average of buyer ratings.
    Lower alpha = slower drift, higher alpha = responsive to recent ratings.
    """
    return (alpha * new_rating) + ((1 - alpha) * previous_score)
```

**Demand Factor:**
```python
def calculate_demand_factor(active_requests, max_concurrent, window_seconds=60):
    """
    Ratio of concurrent requests to provider's stated capacity.
    Normalized to (0-1) range.
    """
    return min(1.0, active_requests / max_concurrent)
```

**Why This Matters:**
- Without dynamic pricing: Agora is just a directory
- With dynamic pricing: Agora is a working marketplace with price discovery
- This is what no prior team built

---

## Payment & Settlement (Unchanged from Current)

**Infrastructure:**
- x402 HTTP payment standard for all transactions
- Circle Developer Controlled Wallets for all parties (orchestrator, providers, marketplace treasury)
- Arc testnet USDC for all settlement
- Nanopayments (sub-cent precision) enable high-frequency transactions

**Flow (existing, no changes):**
1. Buyer requests capability
2. Provider returns `402 Payment Required`
3. Buyer obtains payment proof from provider's wallet
4. Buyer resends request with `X-402-Payment-Proof` header
5. Provider executes, buyer receives response
6. Settlement happens on Arc (record-keeping in marketplace ledger)

**Marketplace Treasury (new):**
- Marketplace takes 2% fee on all transactions
- Feeds quality scoring infrastructure
- Accumulated in separate wallet, visible in analytics

---

## Registry & Discovery

### Provider Registration Schema

Each provider (whether Compute, Data, or Capability) registers with:

```python
{
    "provider_id": "uuid",
    "provider_name": "string",
    "category": "compute|data|capability",
    "capability_type": "string",  # e.g., "web_search", "price_feed", "code_executor"
    
    # Pricing
    "base_price": "float (USDC)",
    "pricing_currency": "USDC",  # Hardcoded for now
    "update_frequency": "string",  # e.g., "per_call", "per_5s", "per_1m"
    
    # Wallet & Payment
    "wallet_address": "0x...",
    "wallet_id": "circle_wallet_id",
    "accepts_x402": true,
    
    # Quality & Performance
    "current_quality_score": "float (0-1)",
    "current_dynamic_price": "float (USDC)",
    "average_latency_ms": "int",
    "uptime_percent": "float (0-100)",
    
    # Capacity
    "max_concurrent_requests": "int",
    "active_requests": "int",
    
    # Metadata
    "description": "string",
    "metadata": {
        "compute": {
            "model_name": "string",
            "input_tokens_limit": "int"
        },
        "data": {
            "data_type": "string",
            "update_frequency_seconds": "int",
            "historical_depth": "string"
        },
        "capability": {
            "requires_credentials": "bool",
            "supported_languages": ["string"],
            "execution_timeout_seconds": "int"
        }
    }
}
```

### Discovery Queries

```
# By category
GET /marketplace/providers?category=compute

# By capability type (for capabilities)
GET /marketplace/providers?category=capability&capability_type=web_search

# By price range
GET /marketplace/providers?category=data&price_min=0.00001&price_max=0.001

# By quality
GET /marketplace/providers?category=compute&min_quality=4.5&sort=quality_desc

# By latency
GET /marketplace/providers?sort=latency_asc&limit=10

# Combined filters
GET /marketplace/providers?category=capability&capability_type=validator&max_latency=500&quality_min=4.0
```

---

## Reputation Loop

**Why it matters:**
- Orchestrators need to trust capability providers (you can't see inside the sandbox)
- Quality must be measurable and affect price
- Creates virtuous cycle: good providers get lower operational costs (higher volume), bad providers get cheaper until they improve or exit

**Flow:**

```
1. Orchestrator uses capability (validator, executor, etc.)
2. Receives result + confidence/metadata
3. Optionally rates: 1.0 - 5.0 stars
4. Rating submitted to marketplace with transaction ID
5. Marketplace updates provider's quality_score (EMA)
6. Next x402 request uses updated score in dynamic_price calculation
7. Over time, high-quality providers accumulate premium pricing power
8. Low-quality providers lose volume or reduce price to stay competitive
```

**Rating Submission:**
```python
POST /marketplace/ratings
{
    "provider_id": "uuid",
    "transaction_id": "x402_tx_hash",
    "rating": 4.5,
    "comment": "fast and accurate",
    "timestamp": "2026-04-20T14:23:45Z"
}
```

**Quality Score Public:**
- Visible in provider registry
- Used in marketplace ranking
- Affects dynamic pricing automatically
- Transparent to all orchestrators

---

## Simplified Execution Plan (5 Phases)

### Phase 1: Schema & Registry Refactor
**Goal:** Restructure registry and orchestrator to think in terms of categories and pricing.  
**Tasks:**
- Generalize `agent_registry.py` → `provider_registry.py`
- Add category, capability_type, base_price, quality_score to schema
- Replace hardcoded agent names with dynamic provider lookups
- No behavior change yet, just data structure

**Deliverable:** Registry responds correctly to `GET /providers?category=X`

### Phase 2: Mock Providers (One per Category)
**Goal:** Populate marketplace with minimal providers to prove discovery.  
**Tasks:**
- Compute: Mock LLM wrapper (Groq endpoint) with price per token
- Data: Mock sensor trio (temp, price, traffic) updating every 5s
- Capability: Mock validator + web_search agents

**Deliverable:** `GET /providers` returns 5 live providers across all categories

### Phase 3: Dynamic Pricing Engine
**Goal:** Make prices update based on demand, quality, latency.  
**Tasks:**
- Implement pricing function
- Run every 10s, update registry
- Display current dynamic price in orchestrator UI
- Log why price changed (demand factor 0.8x, quality 0.9x, latency 1.0x)

**Deliverable:** Prices visibly fluctuate in UI; explain math in UI tooltip

### Phase 4: Market Selection Algorithm
**Goal:** Orchestrator picks best provider for each task (not just first).  
**Tasks:**
- Implement ranking by: price, quality, latency, budget constraints
- Log selection reasoning
- Audit log shows "selected Groq over Claude because 60% cheaper + 4.8/5 quality"

**Deliverable:** Orchestrator calls 3+ different providers in one task (shows selection happening)

### Phase 5: End-to-End Demo Narrative
**Goal:** Single task that touches all three categories naturally.  
**Tasks:**
- Task: "Monitor ETH price, trigger research when it moves, produce decision brief"
- Sub-tasks:
  - Buy Data: Poll price feed (category:data) every 5 seconds → $0.0005
  - When triggered, buy Capability: Web research (category:capability) → $0.0003
  - Then buy Compute: Summarize findings (category:compute) → $0.0002
- Total ~$0.0010 per incident, settles instantly on Arc
- Frontend shows all three category types being used in one flow

**Deliverable:** Video of market selection and settlement for three-category workflow

---

## MVP Scope (What's in, what's out)

### IN (Must Have):
- Multi-category registry with discovery
- Dynamic pricing engine
- Three working mock providers (one per category)
- x402 payment flow (existing)
- Orchestrator that selects best provider per task
- Simple quality rating UI
- Audit log showing selections made

### OUT (Post-MVP):
- Real LLM integrations (mock only)
- Persistent provider reputation database (use in-memory for demo)
- Actual IoT hardware (simulate sensors)
- Advanced matching algorithms (simple ranking OK)
- Provider onboarding UI (hardcoded providers only)
- Revenue dashboard for providers

---

## Codebase Changes Map

### New Files:
- `agora/shared/dynamic_pricing.py` — Pricing function, demand tracking
- `agora/shared/marketplace_registry.py` — Provider discovery, ranking
- `agora/shared/reputation.py` — Quality score updates (in-memory for MVP)

### Modified Files:
- `agora/shared/agent_registry.py` → Refactor to use provider schema
- `agora/orchestrator/orchestrator.py` → Use marketplace discovery + ranking
- `agora/api/main.py` → Add marketplace endpoints (`GET /providers`, `POST /ratings`, etc.)
- `agora/frontend/src/App.jsx` → Add category tabs, show dynamic prices, log selections

### Removed Files (Phase 0 Cleanup):
- `agora/agents/malicious_agent.py` (demo only)
- `agora/simulator/task_simulator.py` (demo only)
- `agora/scripts/demo_fraud.py` (demo only)
- `agora/submission/` (hackathon submission, not needed for pivot)
- `agora/.run/pids/`, `agora/.run/logs/` (runtime artifacts)
- `dev-controlled-projects/` (one-time setup, keep reference only)

---

## Key Metrics to Track

1. **Market Health:**
   - Number of active providers per category
   - Average price per category
   - Price variance (competition signal)

2. **Transaction Volume:**
   - Txns per minute by category
   - Total gas cost on Arc
   - Total USDC transferred

3. **Provider Performance:**
   - Requests per provider per minute
   - Average quality score per provider
   - Provider uptime %

4. **Orchestrator Behavior:**
   - How often do they switch providers (loyalty)?
   - Do they pick cheapest or highest quality?
   - Multi-category requests (% of tasks touching 2+ categories)?

---

## Demo Script (What Judges Will See)

**Setup Time:** 2 minutes  
**Demo Runtime:** 3 minutes

```
1. DISCOVERY (30 sec)
   "Here's the marketplace — three categories: Compute, Data, Capabilities"
   Show registry UI with 15 providers, show dynamic prices real-time

2. SELECTION (30 sec)
   Submit task: "Monitor ETH, alert on move, research why, produce brief"
   Watch orchestrator selection:
     - Data category: picks price feed (lowest price, quality 4.8)
     - Capability category: picks web_search (balanced price/quality)
     - Compute category: picks summarizer (cheapest with rating > 4.5)

3. EXECUTION (60 sec)
   Real-time feed shows:
     - Payments being made via x402
     - Arc transactions settling
     - Fees automatically calculated per transaction
     - Final report assembled from all three provider outputs

4. RESULTS (60 sec)
   Show output:
     - ETH price: $3847 (from data provider)
     - Research summary: "Recent Fed comments, tech sector weakness" (from capability + compute)
     - Total cost: $0.0010
     - On Ethereum, this would exceed $1 in gas
     - On Arc: sub-cent precision, instant settlement, economically viable
```

---

## Success Criteria

- ✅ Registry supports discovery across three categories
- ✅ Dynamic pricing updates every 10 seconds based on signals
- ✅ Orchestrator selects providers using ranking algorithm (not just first available)
- ✅ One end-to-end task uses all three categories
- ✅ All payments settle on Arc with x402
- ✅ Judges understand why three categories matter (not just three APIs)

---

## Open Questions for Team

1. **Data category:** Should data providers offer subscriptions (recurring) or only per-query? MVP: per-query only, subscription streaming as Phase 2 upgrade.

2. **Capability providers:** Should we start with just web_search and validator, or add code executor too? MVP: two capabilities, executor is risky (security), defer.

3. **Quality scoring:** Should ratings be public by orchestrator ID or anonymous? MVP: anonymous (privacy).

4. **Marketplace fee:** Is 2% sustainable, or should we try fee-less for MVP? MVP: 2% covers operational costs, signals sustainable model.

5. **Provider onboarding:** Hardcoded for demo or should we build a registration UI? MVP: hardcoded five providers, onboarding UI is post-MVP.

---

**Next Step:** Proceed with Phase 1 (Schema Refactor). This spec is your north star; all code changes should map back to a specific section here.

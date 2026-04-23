# Agora Project Guide: Architecture & Agentic Workflows

This document serves as the deep-dive technical reference for human developers and **AI Agent Coders** integrating with the Agora ecosystem.

## 1. System Architecture

Agora consists of a **Stateless API** (`api/v1.py`) and a **Local-First Agent SDK** (`sdk/`). 

### The Guiding Philosophy: Privacy by Design
Never send `CIRCLE_API_KEY`, `CIRCLE_ENTITY_SECRET`, or private secp256k1 keys over the wire. The Marketplace only receives metadata (`capabilities`, `address`, `price`) and cryptographic proofs (`x402_headers`, `proof_of_service_hash`). All sensitive state is kept in `~/.agora/agent_config.json`.

### Database Schema (Decentralized State Tracker)
The `agora_local.db` tracks public states and verification:
- `agents`: Tracks `address` and `reputation_score` (No keys).
- `providers`: Tracks active services offered by agents.
- `transactions`: Central log of x402 activity, including Escrow tracking, and the `proof_of_service_hash`.
- `reputation_events`: An ERC-8004 aligned immutable log.

## 2. Core Operational Workflows

### A. Nonce Registry (Replay Attack Prevention)
The system uses strict atomic Redis locking (`SET NX`) to prevent transaction replays.
**File:** `shared/nonce_registry.py`
**For AI Agents:** Do *not* mock the `redis_client`. You must ensure `redis-server` is running locally on port 6379, or the application will proactively "fail closed".

### B. The Merchant Sweep Policy (Autonomous Banking)
Agents should manage their own capital. 
**File:** `sdk/agent.py`
When initiating an `Agent`, you can pass `auto_sweep_threshold=10.0` and a `main_wallet_address`. The SDK's `check_and_sweep()` hook (triggered during `get_status()`) will autonomously wire the USDC from the agent's active hot wallet to the main wallet without human intervention.

### C. Escrow-Style Purchasing & Cryptographic Settlement
Transactions are rarely synchronous in untrusted environments.
**File:** `api/v1.py` & `sdk/consumer.py`
1. The Buyer's SDK internally creates an **x402 payment header** (cryptographic proof of authorized funds) targeted at the Seller's `arc_address`.
2. The API verifies this header, puts the transaction in an `escrow_settled` state, and executes the payload.
3. The API then computes the **SHA-256 hash** of the returned payload (the "Proof of Service").
4. Reputation points are calculated and explicitly tied to that proof hash in the `reputation_events` ledger mapping.

## 3. Developer / Agent Implementation Patterns

### Hooking up your own AI (LLM) to the Buyer SDK
If you are developing a Buyer Agent (e.g. an agent trying to research stocks), your LLM can use the vector search tool to find providers natively:

```python
from sdk.consumer import create_agora_client

# 1. Initialize SDK
client = create_agora_client("my_research_agent", budget_usdc=1.50)

# 2. Semantic Search
# This uses TF-IDF and Cosine Similarity, so you don't need exact keywords.
results = client.search("I need someone who can read PDF proxy statements")

# 3. Autonomous Purchase
# Generates the x402 header locally, signs it, and settles the escrow.
tx_data = client.purchase_service(
    seller_id=results[0]["agent"],
    service_name=results[0]["name"],
    params={"url": "https://example.com/sec_filing.pdf"}
)

# 4. Result
print(tx_data["result"])
```

### Implementing The Agora Guide
We supply a built-in Orchestrator agent affectionately termed "The Agora Guide" (`scripts/register_guide.py`). If a user inputs a natural language prompt that requires chaining multiple agent services (e.g., Search Web -> Summarize Text -> Save to DB), the Guide uses its own local LLM context to plan the execution graph and securely handles the x402 orchestration for the full flow.

## 4. Troubleshooting for AI Assistants
- **Missing Redis**: If `api/v1.py` throws `ConnectionRefused` on `/purchase`, ensure Redis is running. Nonce checking is *mandatory*.
- **Insufficient Funds**: Circle wallets are created perfectly via the SDK, but they start with $0 USDC. Use the Arc testnet faucet to fund the specific `arc_address` generated in `~/.agora/agent_config.json`.
- **x402 Verification Failure**: Did you alter the `ecdsa_signing.py` payload? The `amount_usdc`, `sender`, `recipient`, `nonce`, and `expiry` must perfectly match the signature byte-for-byte.

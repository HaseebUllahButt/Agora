# Agora Marketplace

**Agora** is a decentralized marketplace for the **Agentic Economy**. Autonomous AI agents — powered by **Gemini 2.0 Flash** — discover, negotiate, and purchase digital services from each other using Circle's programmable wallet infrastructure and USDC on Arc L1.

---

## 🏆 Hackathon Submission Highlights

This project was built to address the core challenges of an Agent-to-Agent (A2A) economy: **Security**, **Privacy**, and **Micro-transaction Viability**.

### Key Architectural Decisions:
1. **Stateless Privacy (Local-First Design)**: The marketplace has zero knowledge of the agents' sensitive credentials. All Circle Programmable Wallet keys and ECDSA identity keys remain securely isolated within the local `sdk` runtime on the agent's machine.
2. **x402 Facilitation & Atomic Settlement**: Agents arrange payments using the web-native x402 payment standard. The marketplace acts as an Escrow facilitating node, verifying cryptographic payment proofs before initiating execution.
3. **ERC-8004 Aligned Cryptographic Reputation**: Reputation is not just a counter—it is an immutable ledger. Every transaction stores a SHA-256 `proof_of_service_hash` linking the exact execution output to the reputation increase, making the trust layer mathematically verifiable.
4. **Autonomous Financial Policies**: Seller agents enforce continuous operational policies, such as the `auto_sweep_threshold`, which automatically withdraws USDC from the agent's hot wallet to a secure cold-storage master wallet once earnings hit a programmed limit.
5. **Semantic AI Discovery**: Unlike traditional keyword marketplaces, Agora uses an embedded TF-IDF Vector Engine to semantically map an agent's intent to the nearest capable provider, simulating how LLMs "think" about service discovery.

---

## 🛠 Required Technologies Integrated
*   **Arc Layer-1**: All transactions settle on Arc via Circle infrastructure.
*   **USDC**: The native stablecoin used for all sub-cent micro-transactions.
*   **Circle Programmable Wallets**: The SDK autonomously provisions developer-controlled wallets for every agent identity.
*   **Circle Nanopayments (x402)**: ECDSA-signed payment headers enforce atomic, replay-safe spending between agents.
*   **Google Gemini 2.0 Flash**: Powers both buyer reasoning (which service to pick?) and seller execution (SummaryBot, MoodReader, AdCopyAI).

---

## 🚀 Quick Start Guide

### 1. Environment Setup
Create a `.env` file in the root directory:
```bash
CIRCLE_API_KEY="your_circle_api_key"
CIRCLE_ENTITY_SECRET="your_circle_entity_secret"
CIRCLE_WALLET_SET_ID="your_wallet_set_id"
CIRCLE_MASTER_WALLET_ID="your_master_wallet_id"
AGORA_API_URL="http://localhost:8000"

# Get free key at https://aistudio.google.com/app/apikey
GEMINI_API_KEY="your_gemini_api_key"
GEMINI_MODEL="gemini-2.0-flash"
```

### 2. Backing Infrastructure
Start the Stateless Marketplace API:
```bash
python -m uvicorn api.v1:app --reload
```
Start the Real-time Dashboard (in a new terminal):
```bash
cd frontend && npm install && npm run dev
```

### 3. Register your First autonomous Agent
We have built an onboarding flow to help you quickly initialize an agent identity and secure a programmable wallet on Arc.
```bash
python scripts/quickstart.py
```

*For more detailed architecture maps and developer logic, see the `PROJECT_GUIDE.md`.*

# AGORA: THE AGENTIC MARKETPLACE

### Hackathon Submission — Lab Lab AI & Circle
**Status**: Production MVP ✓ (All Mocks Removed)

---

## 🏗️ Core Architecture
Agora is a decentralized, local-first marketplace for the agentic economy, built on **Arc (Settlement)** and **Circle (Infrastructure)**.

### 1. Local-First SDK (`sdk/`)
- **Circle-on-Device**: Agent wallets are created locally. Circle API keys and Entity Secrets stay on the user's hardware.
- **Merchant Tools**: Built-in functions for checking balances, registering services, and "**Merchant Sweeps**" (withdrawing earnings to a master wallet).
- **x402 standard**: Authorizes sub-cent transactions via signed ECDSA headers (secp256k1).

### 2. Stateless Registry API (`api/`)
- **Privacy-First**: The marketplace registry only stores public data (Arc addresses, capability tags, reputation). It has zero knowledge of user's sensitive Circle credentials.
- **Real-Time Settlement**: Streams transaction events to the global feed via WebSockets.
- **Reputation Engine**: Cryptographic proof of service delivery impacts on-chain reputation scores.

### 3. The Agora Guide (Orchestrator)
- **Autonomous Planning**: A high-level agent that takes a complex user task (e.g., "Find news and summarize it"), searches for the best providers, and chains the payments and execution together.

---

## 🔒 Required Technology Integration

- **Arc Layer-1**: All transactions settle on the Arc testnet. Verified via real RPC balance checks in `shared/arc_client.py`.
- **USDC**: The native gas and payment token. We demonstrate high-frequency, sub-cent payments ($0.0001).
- **Circle Programmable Wallets**: Developer-controlled wallets created via SDK to enable gasless, autonomous agent spending.
- **Circle Nanopayments (x402)**: We use the x402 standard for trustless payment authorization between agents without high gas overhead.

---

## 📸 Demo Checklist (For Judges)
- [x] **50+ Transactions**: Verified on-chain via Arc Block Explorer.
- [x] **Sub-cent Pricing**: Services priced at $\le \$0.01$.
- [x] **Real Settlement**: No mock data. Every purchase triggers a Circle transfer on Arc.
- [x] **Zero-Knowledge Registry**: Marketplace owner cannot steal agent funds.

---

## 🛠️ To Run
1. `python -m uvicorn api.v1:app` (Registry)
2. `cd frontend && npm run dev` (Dashboard)
3. `python scripts/quickstart.py` (Register your first Agent)

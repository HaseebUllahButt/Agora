# 🏆 AGORA: The AI Agent Marketplace

## 📋 Basic Information
*   **Title**: Agora
*   **Tracks**: 🤖 Agent-to-Agent Payment Loop · 🧠 Google Gemini Bounty
*   **Short Description**: A decentralized marketplace for the Agentic Economy — AI agents autonomously hire other AI agents, paying in USDC on Arc L1, with every decision powered by Gemini 2.0 Flash.
*   **Long Description**: Agora is a high-frequency marketplace where AI agents act as both merchants and consumers. By leveraging the zero-gas-cost settlement of Arc L1, the stability of USDC, and the reasoning power of Gemini 2.0 Flash, Agora enables true "Nanopayments" ($0.001 per AI task) — something mathematically impossible on traditional blockchains. Agents are autonomous: they discover services via semantic vector search, reason about the best provider using Gemini, sign payments using the x402 protocol (ECDSA secp256k1), and execute — all without any human-in-the-loop.

---

## 🤖 Track 1: Agent-to-Agent Payment Loop

Agora demonstrates a true nested Agent-to-Agent supply chain. Agents buy services dynamically when they need to outsource work.

**Demo Scenario**: An Orchestrator Agent receives a request to create a "Deep Sentiment Report". It realizes it needs external tools, so it uses its USDC wallet to *autonomously purchase* Sentiment Analysis from Agent B, and then purchases CSV Formatting from Agent C. It combines the results and returns them to the user. This creates a multi-hop, fully on-chain circular economy where AI agents pay each other in real-time.

---

## 🧠 Track 2: Google Gemini Bounty

Agora's entire intelligence layer runs on **Gemini 2.0 Flash**:

1.  **Agent Decision Reasoning** (`sdk/smart_buyer.py`): The `SmartBuyer` agent calls Gemini 2.0 Flash to read the marketplace listing and autonomously pick the best service. Gemini returns a structured JSON decision with a `service_id` and reasoning.
2.  **Seller Agent Services** (`services/llm_services.py`): The marketplace's LLM-powered services (`SummaryBot`, `MoodReader`, `AdCopyAI`) are all executed by Gemini 2.0 Flash on the seller side.
3.  **Commerce Flow**: After Gemini makes a decision, the SDK signs an x402 payment header and pays the seller via Circle Wallets on Arc — demonstrating the full "intelligence → intent → payment" loop on-chain.

This means both the **buyer's brain** (deciding what to buy) and the **seller's execution** (delivering the AI service) are powered by Gemini — a full Gemini-native commerce loop.

---

## 📊 The "Winning" Argument: Margin Explanation

For an AI agent charging $0.001 per task, traditional blockchain gas makes the business model mathematically impossible.

| Network | Avg Gas per Transfer | Cost of 50 Transactions | Margin at $0.001/task |
|---------|----------------------|-------------------------|----------------------|
| **Ethereum L1** | ~$2.95 | ~$147.50 | ❌ -$147.45 (complete loss) |
| **Polygon (PoS)** | ~$0.015 | ~$0.75 | ❌ -$0.70 (gas > revenue) |
| **Arc L1** | **$0.00** | **$0.00** | ✅ **100% margin retained** |

Arc's zero-gas model isn't just cheaper — it's the **only model** that makes the agentic micro-economy viable.

---

## 💡 Circle Product Feedback

*   **Products Used**: Arc (L1), Native USDC, Circle Programmable Wallets (Developer-Controlled)

### Why We Chose These Products
We needed a settlement layer that could handle the high frequency of AI-to-AI communication without gas costs destroying the unit economics. Developer-Controlled Wallets were the right choice because our agents need backend-managed wallets that can execute transactions programmatically without any human approval step — perfectly matching the autonomous agent model.

### What Worked Well During Development
1. **`circle-developer-controlled-wallets` Python SDK**: The `generate_entity_secret_ciphertext()` utility was a lifesaver. Encrypting the entity secret with the RSA public key is a multi-step process, and having a single function call dramatically reduced friction.
2. **Transfer API Design**: The `POST /w3s/developer/transactions/transfer` endpoint is clean and well-designed for programmatic use. It has been rock-solid across our 50+ transaction stress tests.
3. **Balance API**: Token-level granularity made it easy to implement our auto-sweep financial policy engine — agents automatically sweep earnings to a cold wallet when they cross a threshold.
4. **Arc Explorer**: Being able to verify on-chain settlement at `testnet.arcscan.app` is critical for demonstrating real payment flow in the demo video.

### Recommendations for Product and Developer Experience
1. **Entity Secret Registration Flow**: The `register_entity_secret_ciphertext()` function expects a *directory path* for the recovery file, not a file path. This is undocumented and caused `FileNotFoundError` until we used `tempfile.TemporaryDirectory()`. Please accept both, or clarify in the docs.
2. **Wallet Set Concept**: Add a "Wallet Set Best Practices" guide with concrete use cases (e.g., "one set per application" vs. "one set per user group"). We initially didn't know whether to make 1 per agent or 1 globally.
3. **No SDK Method for Explorer URL**: There's no SDK method to get the Arc Explorer URL for a completed transaction. A `get_explorer_url(transaction_id)` helper would be very useful for developers building dashboards.
4. **No Webhook for Transaction Completion**: We currently poll until a transaction moves from `PENDING` → `COMPLETE`. A webhook or SSE stream for state transitions would eliminate this polling pattern entirely.
5. **Batch Transfer Endpoint**: For high-frequency use cases (our demo fires 50 USDC transfers in under 5 minutes), a batch transfer API would reduce API call overhead and significantly improve throughput.

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Agent Intelligence** | Google Gemini 2.0 Flash (buyer reasoning + seller execution) |
| **Settlement Chain** | Arc L1 (EVM-compatible, zero gas) |
| **Asset** | USDC (Native on Arc) |
| **Wallet Infrastructure** | Circle Programmable Wallets (Developer-Controlled) |
| **Payment Protocol** | x402 (ECDSA secp256k1 signed payment headers) |
| **Replay Prevention** | Redis SET NX (SQLite fallback) |
| **Reputation** | SHA-256 Proof-of-Service (ERC-8004 inspired) |
| **Discovery** | TF-IDF Vector Search (semantic cosine similarity) |
| **API** | FastAPI + WebSocket live feed |
| **Frontend** | HTML5 + Tailwind CSS (Industrial Dark Mode) |

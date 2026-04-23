# Agora Project Guide: Architecture & Technical Workflows

This document serves as the primary technical reference for Agora, merging the core architectural philosophy with the operational logic for human and AI autonomous developers.

---

## 1. Architectural Philosophy

Agora is built as a **Stateless Discovery and Settlement Layer**. Unlike traditional marketplaces that hold user funds, Agora never touches a private key.

### The Network Topography (Verbal Description)
The system is divided into three distinct operational zones:

1.  **The Client Edge (Agent SDK)**: This is where the real "intelligence" and "wealth" live. Every agent runs a local SDK instance that manages its own Circle Programmable Wallets and Identity Keys.
2.  **The Facilitation Hub (Stateless API)**: This acts as the "Marketplace Operator." It facilitates three things: **Discovery** (Semantic Search), **Validation** (Agora Guard Nonce Checking), and **Settlement Triggering** (Circle Bridge).
3.  **The Global Ledger (Arc & Circle)**: This is the source of truth for value. USDC moves directly between agent wallets on the Arc layer-1, while the Agora API logs the transactions and cryptographic reputation proofs for public audit.

---

## 2. Core Functional Pillars

### A. The x402 Facilitation Layer (Atomic Payments)
Instead of a simple "Send Money" command, Agora uses the **x402 protocol**. 
- A Buyer agent signs a cryptographic header specifying the exact amount and recipient address.
- The Marketplace API verifies this signature against the buyer's public key.
- This ensures that payments are **pre-authorized** and **non-repudiable** before any code is executed.

### B. Agora Guard (Anti-Fraud & Security)
To ensure the marketplace remains robust under high frequency:
1.  **Atomic Nonces**: We use a strict Redis-backed nonce registry. Every payment header has a unique UUID that is burned instantly upon use. An attacker cannot "replay" a payment to double-spend or spoof execution.
2.  **ERC-8004 Proof of Service**: Reputation isn't a social score; it's a verifiable audit trail. We calculate a SHA-256 hash of every service output. This `proof_of_service_hash` is permanently linked to the agent's reputation increase in the database. If an agent has 1,000 reputation points, there are 1,000 unique cryptographic proofs in the ledger to back it up.

### C. Semantic Vector Engine (Discovery)
Agora leverages a **TF-IDF Vector Engine** to transform natural language queries into mathematical vectors. We then perform a **Cosine Similarity** comparison against the indexed capabilities of all registered providers. This allows an AI agent to find a service based on *intent* (e.g., "I need to clean some messy data") rather than just matching keywords.

---

## 3. Autonomous Treasury Management

### The Merchant Sweep Policy
Agora enables agents to be financially autonomous. Using the `auto_sweep_threshold` policy, a seller agent can manage its own hot vs. cold wallet strategy.
- The SDK monitors the "Hot" Circle wallet balance.
- Once the threshold is crossed, the agent autonomously initiates a transfer to the "Cold" master wallet address.
- This prevents the agent from becoming a "honey pot" of high USDC balances in a single active wallet.

---

## 4. Integration for AI Agents

If you are an AI assistant or autonomous agent coding within this repo, prioritize these patterns:
- **Privacy First**: Do not send circle keys to any API endpoint.
- **Fail Closed**: If the Nonce check fails, the transaction must be rejected immediately to protect the ecosystem.
- **Verifiable Reputation**: Always call `record_service_result` with the `proof_hash` to ensure the global trust scores remain accurate.

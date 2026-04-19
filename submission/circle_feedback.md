# Circle Product Feedback — Agora Team

*This document is submitted as part of our hackathon project feedback.*  
*Written during active development — raw, honest notes as things happened.*

---

## Developer Controlled Wallets SDK

### What worked well
- The wallet creation API is straightforward — create wallets in bulk, get addresses immediately
- Polling for transaction state is reliable; COMPLETE state arrives within 10-20 seconds on Arc
- The `walletSetId` concept is elegant — lets you group related wallets (all Agora agents) cleanly
- Entity secret + API key auth pattern is simple to set up

### What was confusing
- The `amounts` field in `createTransaction` vs `amount` — inconsistency in docs vs SDK
- `getTransaction` returns the transaction nested under `data.transaction` not `data` — not obvious
- The SDK error messages when the entity secret is wrong are not descriptive

### Missing features we wanted
- Batch transaction creation — we call agents in loops and would benefit from batching 5 payments at once
- Webhook support for transaction state changes — polling works but websockets/webhooks would be cleaner
- Transaction labels/memos — would help with bookkeeping across 50+ agent payments

### Docs gaps
- The Arc testnet USDC contract address is not in the main docs — had to find it separately
- No example of creating a wallet and immediately funding it in one code snippet
- The error response schema is not documented — had to log and reverse-engineer

---

## x402 Standard + Facilitator

### What worked well
- The 402 → pay → retry pattern maps cleanly onto agent-to-agent calls
- The standard gives agents a machine-readable way to quote their price
- Works with standard HTTP clients — no special SDK required on the payer side

### What was confusing
- The facilitator package compatibility with Arc testnet is not clearly documented
- Header casing: `x-402-payment-proof` vs `X-402-Payment-Proof` — needed to test both
- No standard way to specify token address in the 402 response body — we added it ourselves

### Suggested improvements
- Official Arc testnet facilitator endpoint would help
- A standard `x402.json` discovery endpoint per agent (like `robots.txt`) would be useful
- Clear spec for the payment proof header name and format

---

## Arc Testnet

### What worked well
- Transaction finality is fast — 10-20 seconds is viable for real-time agent payments
- Arc explorer API works well for polling transaction state
- USDC contract is pre-deployed — no deployment needed

### Friction points
- The token transfer endpoint `api/v2/transactions/{hash}/token-transfers` requires knowing the exact schema
- Rate limits on the explorer API hit us during high-frequency polling (25+ transactions in a minute)
- No official faucet documentation — harder to onboard new devs to Arc testnet

---

## Nanopayments Pattern

### Use case fit
This is genuinely the killer use case for Arc Nanopayments. The economics are stark:
- Ethereum: 50 agent payments = $147.50 in gas
- Arc: 50 agent payments = $0.005 in gas

Without Arc's near-zero gas, this entire system is not viable. The Nanopayments pattern
enables a new category of application: autonomous economic agents that pay each other
for micro-tasks in real time.

### Suggested improvements
- Official Nanopayments SDK/library with rate limiting, batching, and retry built in
- A Nanopayments dashboard in the Circle console — filter transactions by `<$0.01`
- Case studies or reference architectures for agent-to-agent payment patterns

---

## Overall Developer Experience Score

| Product | Score | Notes |
|---------|-------|-------|
| Developer Controlled Wallets | 7/10 | Good core API, needs better error messages |
| x402 Standard | 7/10 | Great concept, needs Arc-specific docs |
| Arc Testnet | 8/10 | Fast and reliable, needs better explorer API docs |
| Nanopayments on Arc | 9/10 | Game-changing economics, perfect fit for this use case |

---

## One Line Summary

*The Circle + Arc stack is technically sound for high-frequency micro-payments.
The developer experience has 3-4 rough edges that a dedicated Nanopayments SDK would fix.*

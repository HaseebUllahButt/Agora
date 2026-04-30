# X402_GUIDE — architecture & protocol walkthrough

This document explains *what* AgoraAli does and *why* it does it that way.
Read [README.md](README.md) first for the quickstart.

## Why a separate facilitator?

x402 leaves the verification + settlement step pluggable. Three options:

1. **Each agent verifies + settles itself.** Simple, but every agent needs
   Circle credentials, and replay protection becomes hard (an attacker can
   replay the same nonce against multiple agents that don't share state).
2. **A central facilitator does verify + settle.** One trust boundary, one
   nonce store, one set of Circle keys. Agent code stays tiny.
3. **Hybrid.** Agents *can* run standalone, but default to the facilitator.

AgoraAli chose **option 2** because it makes the marketplace fee model
natural: every payment passes through the facilitator on its way to the
seller, so we can take a small skim with no extra moving parts.

## End-to-end x402 message flow

```
Buyer                  SummaryBot                  Facilitator               MoodReader
  │                        │                            │                        │
  │── POST /summarize ────▶│                            │                        │
  │                        │── (no X-PAYMENT) ─────┐    │                        │
  │◀───── 402 + accepts ───│                       │    │                        │
  │       (recipient,      │                       │    │                        │
  │        amount,         │                       │    │                        │
  │        resource,       │                       │    │                        │
  │        facilitator)    │                       │    │                        │
  │                        │                            │                        │
  │── sign X-PAYMENT ─▶                                 │                        │
  │── POST /summarize  ───▶│                            │                        │
  │   (X-PAYMENT: …)       │── /facilitator/verify ───▶│                        │
  │                        │◀── valid: true, nonce burnt│                        │
  │                        │── execute summarize() ──┐  │                        │
  │                        │                          ▼  │                        │
  │                        │── (calls X402Client.post) ──┼──── POST /analyze ────▶│
  │                        │                              │◀──── 402 + accepts ──│
  │                        │── sign X-PAYMENT (subsidy) ──┼──── retry w/ pay ────▶│
  │                        │                              │── verify+settle ────▶│
  │                        │                              │◀── 200 + sentiment ──│
  │                        │◀── sentiment dict ──────────┘                       │
  │                        │── /facilitator/settle ────▶│                        │
  │                        │   (gross, fee skim, net to seller wallet)           │
  │                        │◀── settlement record ──────│                        │
  │◀── 200 + result + ─────│                            │                        │
  │    settlement          │                            │                        │
```

Every numbered receipt the facilitator returns has:

```
gross_usdc           = what the buyer paid
marketplace_fee_usdc = what the marketplace took
net_usdc             = what the seller received  (gross - fee)
settlement_ref       = id from the settlement backend (mock or Circle)
```

## Payment header format

`X-PAYMENT` is base64-encoded JSON:

```json
{
  "scheme":     "agora-ecdsa-v1",
  "version":    1,
  "amount":     "0.0015",
  "asset":      "USDC",
  "network":    "arc-testnet",
  "sender":     "0xBuyer...",
  "recipient":  "0xSeller...",
  "resource":   "http://localhost:9001/summarize",
  "nonce":      "uuid",
  "expiry":     1738000000,
  "signature":  "0x... (ECDSA over canonical_payload)",
  "public_key": "0x..."
}
```

Canonical payload is a colon-separated string — fixed format, no JSON
serialisation surprises. See `agora_x402/x402_protocol.py:_canonical_payload_str`.

The facilitator atomically inserts the `nonce` into a SQLite table with a
`UNIQUE` constraint. Replays fail at the database, not in application code.

## What an agent application looks like

The smallest possible agent:

```python
from agora_x402 import AgentServer, Wallet, pay_for

@pay_for(price="0.001")
def echo(text: str) -> dict:
    return {"text": text}

server = AgentServer(
    agent_id="echobot",
    name="EchoBot",
    wallet=Wallet.from_env("ECHOBOT_PRIVATE_KEY"),
)
```

Run it:

```bash
agora-agent run echobot/agent.py --port 9010
```

What `agora-agent run` does:

1. Imports your file.
2. Reads the global `server = AgentServer(...)`.
3. Reads the in-process `ServiceRegistry` populated by `@pay_for`.
4. Mounts a route per service (`POST /echo`).
5. Runs uvicorn on the chosen port.

## Server-side guards

`AgentServer` enforces, before executing any decorated function:

- `X-PAYMENT` is present and base64-decodable.
- Signature recovers to `payment.sender`.
- `payment.recipient == wallet.address`.
- `payment.resource == this URL`.
- `payment.amount >= service.price`.
- `payment.expiry > now()`.
- Facilitator verify call succeeds (which also burns the nonce).

Any failure returns `402` with a structured JSON body. The function never
runs unless all checks pass.

## Client-side guards

`X402Client` enforces, before retrying with a payment:

- `payment.amount <= max_price` (configurable cap).
- `payment.recipient` is in `allowed_recipients` (optional allow-list).

This keeps a misbehaving remote from tricking your agent into paying
$1000 USDC for a single call.

## Marketplace economics

Two fees, both configurable in `.env`:

| Lever | Default | Goes to |
|---|---|---|
| Listing fee | `0.10 USDC`, one-time at registration | `MARKETPLACE_TREASURY_ADDRESS` |
| Per-transaction fee | `250 bps` (2.5%) on every settled service call | `MARKETPLACE_TREASURY_ADDRESS` |

The fee is taken out of the buyer's payment before the seller sees it. So
when SummaryBot prices its summarize endpoint at `0.0015 USDC`, the seller
actually receives `0.001463` and the marketplace gets `0.0000375`. (Yes, the
math works at six decimals — USDC has six on-chain.)

## Why not real Circle by default?

To keep the demo working with zero credentials and zero network. The
facilitator's `Settler` is an interface — flip `SETTLEMENT_MODE=circle` in
`.env`, fill in `CIRCLE_API_KEY` / `CIRCLE_ENTITY_SECRET`, and every transfer
calls Circle's Programmable Wallet API on Arc-testnet for real. The agent
code does not change.

The settlement abstraction also makes it trivial to swap in Solana, Base,
or any other chain — implement a `Settler` subclass and update
`get_settler()`.

## Files & where to look

- Protocol primitives: `agora_x402/x402_protocol.py`
- Server-side enforcement: `agora_x402/agent_server.py`
- Client-side auto-pay: `agora_x402/x402_client.py`
- @pay_for decorator: `agora_x402/pay_for.py`
- Facilitator HTTP API: `facilitator/api.py`
- Fee math: `facilitator/fees.py`
- Replay protection: `facilitator/nonce.py`
- Mock vs Circle settlement: `facilitator/settlement.py`
- Three example agents: `agents/{summarybot,moodreader,datawizard}/agent.py`
- Headline demo: `scripts/x402_demo.py`

## Limitations & next steps

- **No batching.** Each API call is one signed payment. For high-frequency
  flows you'd want session-scoped channels (deposit once, sign cheap
  off-chain debits, settle the net). Add a `agora-channel-v1` scheme to
  `x402_protocol.py` to support this.
- **No reputation layer.** AgoraAli intentionally drops the original Agora
  ERC-8004 reputation pieces to keep the surface area small. Bring them back
  by adding a `proof_of_service_hash` column to the `transactions` table and
  recomputing the SHA-256 of the result before settlement.
- **Mock settlement is local-only.** Two facilitators running side-by-side
  cannot see each other's nonces. For multi-region facilitators, swap the
  SQLite nonce store for Redis (with `SETNX` + TTL).
- **No rate limiting.** A failed payment costs the buyer nothing. For
  production, add rate limits per `payment.sender` to discourage probing.

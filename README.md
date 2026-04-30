# Agora — x402 agent economy

Agora is a fresh, self-contained reference implementation of the [x402
payment protocol](https://www.x402.org) for AI agents. Each agent is a
**standalone HTTP application** that exposes paid endpoints; agents discover
and pay each other per API call in USDC; a shared **facilitator service**
verifies payments, settles them, and skims a small marketplace fee.

The result is a working agent-to-agent micro-economy in ~1500 lines of
Python.

## Architecture at a glance

```
                  ┌────────────────────────────────────────────────┐
                  │      Marketplace Facilitator  (port 8000)      │
                  │   verify · settle · listing · fee accounting   │
                  └──┬───────────────────┬──────────────────────┬──┘
                     │   /facilitator/   │     /agents/         │
                     │     verify+settle │     /services/       │
                     │                   │     /transactions    │
   ┌─────────────────▼─────┐   ┌─────────▼────────┐   ┌─────────▼────────┐
   │ SummaryBot   :9001    │   │ MoodReader :9002 │   │ DataWizard :9003 │
   │ wallet 0xS...         │   │ wallet 0xM...    │   │ wallet 0xD...    │
   │ POST /summarize       │   │ POST /analyze-…  │   │ POST /json-to-csv│
   └────────┬──────────────┘   └──────────────────┘   └──────────────────┘
            │ x402: pays MoodReader for sentiment on every summarize call
            ▼
        MoodReader (different agent, different wallet, charges per call)

         Buyer  ──x402──▶  SummaryBot  ──x402──▶  MoodReader
                                │
                                └──x402──▶  DataWizard (optional)
```

Every horizontal arrow is a real HTTP request that started with a `402
Payment Required`, was retried with a signed `X-PAYMENT` header, was verified
by the facilitator, and was settled in USDC (mock or real Circle).

## Quickstart (4 terminals)

### 0. One-time setup

```bash
cd Agora
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                       # installs the agora-agent CLI

python scripts/setup_env.py            # generates .env with fresh wallets
set -a && source .env && set +a        # export everything to the shell
```

`SETTLEMENT_MODE=mock` (the default) means no real Circle calls — every
settlement is recorded locally so the demo runs offline. To use real Circle
on Arc-testnet, run the interactive Circle bootstrap (asks only for your
Circle API key — generates the entity secret + wallet set automatically and
writes them into `.env`):

```bash
python scripts/bootstrap_circle.py
```

It also offers to flip `SETTLEMENT_MODE=mock` → `SETTLEMENT_MODE=circle` so
the facilitator starts settling on-chain immediately.

### 1. Start the facilitator

```bash
bash scripts/run_facilitator.sh        # listens on :8000
```

### 2. Start the agents (one terminal each, or all in one with the helper)

```bash
agora-agent run agents/moodreader/agent.py  --port 9002
agora-agent run agents/datawizard/agent.py  --port 9003
agora-agent run agents/summarybot/agent.py  --port 9001
```

…or, in a single shell:

```bash
bash scripts/run_all_agents.sh
```

### 3. Register agents on the marketplace (pays the listing fee via x402)

```bash
python scripts/register_agents.py
```

You'll see each agent settle a `0.10 USDC` listing fee to the marketplace
treasury.

### 4. Run the end-to-end demo

```bash
python scripts/x402_demo.py
```

This makes a buyer call SummaryBot, which internally pays MoodReader, then
calls DataWizard, then prints the marketplace ledger and treasury balance.

## What you get

- `agora_x402/` — SDK: `@pay_for` decorator, `AgentServer`, `X402Client`,
  `Wallet`, low-level x402 protocol primitives, CLI runner.
- `facilitator/` — FastAPI service implementing `/facilitator/verify`,
  `/facilitator/settle`, `/agents/register` (charges listing fee),
  `/services/register`, `/transactions`, `/marketplace/{fees,treasury}`.
- `agents/{summarybot,moodreader,datawizard}/agent.py` — three independent
  agent applications. SummaryBot internally pays MoodReader, demonstrating
  agent-to-agent x402 composition.
- `scripts/` — facilitator + agents launchers, env bootstrapper, listing
  registration, headline demo.
- `tests/test_smoke.py` — fast unit tests for protocol, fees, nonce dedupe,
  route mounting.

## Marketplace economics

Two configurable knobs (`.env`):

| Variable | Default | What it does |
|---|---|---|
| `MARKETPLACE_LISTING_FEE` | `0.10` USDC | Flat, one-time fee paid by an agent owner when they list their agent. |
| `MARKETPLACE_TX_FEE_BPS` | `250` (= 2.5%) | Skim taken out of every settled service payment. The seller gets the net. |

Both are paid in USDC, signed and verified through the same x402 path as
service calls — the listing fee is just a special-case payment with the
treasury as recipient.

## Writing your own agent

```python
# my_agent/agent.py
from agora_x402 import AgentServer, Wallet, pay_for

@pay_for(price="0.002", description="Reverses a string. Surprisingly costly.")
def reverse(text: str) -> dict:
    return {"reversed": text[::-1]}

server = AgentServer(
    agent_id="reversebot",
    name="ReverseBot",
    wallet=Wallet.from_env("REVERSEBOT_PRIVATE_KEY"),
)
```

Then:

```bash
agora-agent run my_agent/agent.py --port 9010
```

Your function is now a paid HTTP endpoint at `POST /reverse` that requires a
valid x402 payment to execute. See [X402_GUIDE.md](X402_GUIDE.md) for the
full architecture and protocol walkthrough.

# Agora Economic Platform

Minimal agent-to-agent marketplace with cryptographic payments, anti-fraud, and reputation.

## Quick Start

```bash
# 1. Generate a wallet for your agent
python scripts/quickstart.py

# 2. Fund your address on Arc testnet
# https://arc-testnet.example.com/faucet

# 3. Run the demo (4 agents, 12 transactions)
python scripts/demo.py

# 4. Start the API (for real marketplace)
python -m uvicorn api.v1:app --port 8000
```

## Wallets & Real Blockchain

Agents use **secp256k1 wallets** (Ethereum-compatible) on **Arc testnet**:

```python
from agora.sdk import generate_wallet, Agent

# Generate wallet (private key + address)
private_key, address = generate_wallet()

# Fund address on Arc testnet faucet
print(f"Fund this: {address}")

# Create agent (address auto-derived from private key)
agent = Agent(
    agent_id="my_agent",
    name="My Bot",
    private_key=private_key,  # Address derived automatically
    capabilities=["trading", "analysis"]
)
agent.register()
```

See **[WALLET_GUIDE.md](WALLET_GUIDE.md)** for production setup.

## Core Modules

### `shared/database.py`
SQLite schema: agents, providers (services), transactions, reputation, nonces.

### `shared/ecdsa_signing.py`
x402 header signing/verification with ECDSA (secp256k1).

### `shared/nonce_registry.py`
Atomic nonce registration (Redis SET NX) — prevents replay attacks.

### `sdk/provider.py`
`@pay_for` decorator for monetizing functions.

### `sdk/consumer.py`
`AgoraClient` for autonomous service purchasing.

### `api/v1.py`
REST endpoints:
- `POST /agents/register` — Register agent (any id, address, private_key)
- `POST /agents/{id}/services` — Register service
- `GET /services/search?q=` — Search services
- `POST /purchase` — Buy service (x402 payment)
- `GET /transactions` — View history
- `GET /agents` — List agents

## Payment Flow

```
1. Buyer signs x402 header (ECDSA)
2. API validates signature math
3. Nonce registered atomically (Redis)
4. Transaction recorded (SQLite)
5. Reputation updated (+5 seller, +1 buyer)
6. Confirmation returned with tx_id, nonce
```

## Usage Example

```python
# Register agent
curl -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my_agent", "name": "My Agent", "address": "0x...", "private_key": "0x..."}'

# Register service
curl -X POST http://localhost:8000/agents/my_agent/services \
  -H "Content-Type: application/json" \
  -d '{"name": "My Service", "service_type": "data", "description": "...", "price_usdc": 0.001}'

# Search
curl 'http://localhost:8000/services/search?q=service'

# Purchase
curl -X POST http://localhost:8000/purchase \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "...",
    "buyer_agent_id": "...",
    "buyer_private_key": "0x..."
  }'
```

## Anti-Fraud

1. **Atomic nonce**: Reddit SET NX (fails if replayed)
2. **Signature validation**: ECDSA math check
3. **Expiry**: x402 headers time-bound (60s)
4. **Reputation decay**: Bad actors lose trust over time

---

**Status:** Core platform ready. Agents plug in dynamically via API.

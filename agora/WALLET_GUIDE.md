# Agora SDK: Wallet Integration Guide

## Quick Start: Create & Fund an Agent

### Step 1: Generate a Wallet

```python
from agora.sdk import generate_wallet, Agent

# Generate a new secp256k1 wallet
private_key, address = generate_wallet()

print(f"Private Key: {private_key}")  # Save this safely!
print(f"Address: {address}")           # Fund this address on Arc
```

### Step 2: Fund the Agent on Arc Testnet

**Option A: Via Faucet (Easiest)**
```bash
# Visit the Arc testnet faucet
https://arc-testnet.example.com/faucet

# Enter your address from Step 1
# Request test USDC (e.g., $10)
```

**Option B: Via CLI**
```bash
# If Arc has a testnet faucet CLI
arc faucet fund --address 0x6eD7318942e6b887947c24F8d96C035a7e4C7aC5 --amount 10 usdc
```

### Step 3: Initialize Your Agent

```python
from agora.sdk import Agent, generate_wallet

# Generate wallet
private_key, address = generate_wallet()

# Create agent (address is auto-derived, so it matches what you funded)
alice = Agent(
    agent_id="alice_trading_bot",
    name="Alice",
    private_key=private_key,
    description="AI data analyst for CSV operations",
    capabilities=["csv_analysis", "pandas", "sql"]
)

# Register in marketplace
alice.register()
print(f"✓ Agent registered: {alice.address}")
```

## Production Setup: Environment Variables

### 1. Generate Keys (One Time)
```bash
cd ~/.agora
python3 << 'EOF'
from agora.sdk import generate_wallet
private_key, address = generate_wallet()
print(f"Key: {private_key}")
print(f"Address: {address}")
EOF

# Output:
# Key: 0x1a2b3c4d5e...
# Address: 0x6eD7318942e6b887947c24F8d96C035a7e4C7aC5
```

### 2. Store in .env
```bash
# ~/.agora/.env
AGENT_ID=production_alice
AGENT_NAME=Alice Bot
AGENT_PRIVATE_KEY=0x1a2b3c4d5e...
AGENT_DESCRIPTION="Production trading agent"
AGENT_CAPABILITIES=analysis,data_processing,reporting

# Arc configuration
ARC_RPC_URL=https://arc-testnet.example.com/rpc
ARC_CHAIN_ID=123  # Arc testnet chain ID
```

### 3. Load and Initialize Agent
```python
import os
from dotenv import load_dotenv
from agora.sdk import Agent

# Load from .env
load_dotenv(os.path.expanduser("~/.agora/.env"))

agent = Agent(
    agent_id=os.getenv("AGENT_ID"),
    name=os.getenv("AGENT_NAME"),
    private_key=os.getenv("AGENT_PRIVATE_KEY"),
    description=os.getenv("AGENT_DESCRIPTION"),
    capabilities=os.getenv("AGENT_CAPABILITIES", "").split(",")
)

agent.register()
print(f"✓ Production agent ready: {agent.address}")
```

## Multi-Agent Setup (Team)

```python
from agora.sdk import Agent, generate_wallet
import json

# Generate wallets for a team
team_size = 4
wallets = {}

for i in range(team_size):
    private_key, address = generate_wallet()
    wallets[f"agent_{i}"] = {
        "private_key": private_key,
        "address": address
    }

# Save to file (with restricted permissions)
with open("wallets.json", "w") as f:
    json.dump(wallets, f, indent=2)

# Set permissions (Unix)
os.chmod("wallets.json", 0o600)  # Read/write by owner only

# Load and register agents
for agent_name, wallet_data in wallets.items():
    agent = Agent(
        agent_id=agent_name,
        name=agent_name.replace("_", " ").title(),
        private_key=wallet_data["private_key"],
        description=f"Team member {agent_name}",
        capabilities=["trading", "analysis", "data_processing"]
    )
    agent.register()
    print(f"✓ {agent_name}: {wallet_data['address']}")
```

## Argon Integration: Real Balance Verification

The SDK automatically verifies agent balance on Arc before signing transactions:

```python
from agora.sdk import Agent
from shared.arc_client import has_sufficient_balance

agent = Agent(
    agent_id="alice",
    name="Alice",
    private_key="0x...",
    capabilities=["analysis"]
)

# SDK will check Arc balance before signing
# If balance < service cost: raises BudgetExceeded (graceful failure)
# If balance >= cost: signs and executes transaction

client = agent.create_client(budget_usdc=0.50)

try:
    result = client.purchase_service(
        seller_id="bob",
        service_name="CSV Analysis",
        params={"file": "data.csv"}
    )
    print(f"✓ Transaction successful: {result['transaction_id']}")
except BudgetExceeded as e:
    print(f"✗ Insufficient budget: {e.message}")
    # Handle gracefully: skip, retry, or stop
```

## Key Rotation (Security)

For long-running agents, rotate keys periodically:

```python
from agora.sdk import generate_wallet, Agent

# Generate new wallet
new_private_key, new_address = generate_wallet()

# Fund the new address
print(f"Fund this address: {new_address}")
# (wait for funds to arrive on Arc)

# Create new agent with updated key
agent = Agent(
    agent_id="alice_v2",  # New ID for tracking
    name="Alice",
    private_key=new_private_key,
    description="Rotated key for security",
    capabilities=["analysis"]
)
agent.register()

# Old agent (alice) is now deprecated
# Transfer remaining funds from old address to new address
```

## Hardware Wallet Support (Production)

For enterprise agents using Ledger/Trezor:

```python
from agora.sdk import Agent, WalletConfig
from ledger.eth_account import HardwareWalletSigner

# Ledger hardware wallet
signer = HardwareWalletSigner(derivation_path="m/44'/60'/0'/0/0")
address = signer.get_address()

# Wrapper for hardware-signed transactions
wallet = WalletConfig(
    private_key=address,  # Will use signer internally
    arc_rpc_url="https://arc-testnet.example.com/rpc"
)

# Create agent with hardware security
agent = Agent(
    agent_id="enterprise_alice",
    name="Enterprise Alice",
    private_key=wallet.private_key,
    capabilities=["trading", "risk_management"]
)
agent.register()
```

## Monitoring & Alerts

```python
from agora.sdk import Agent
from shared.arc_client import get_balance

agent = Agent(
    agent_id="alice",
    name="Alice",
    private_key="0x...",
    capabilities=["analysis"]
)

# Check balance
balance = get_balance(agent.address)
print(f"Current balance: ${balance:.2f}")

# Set up monitoring
MIN_BALANCE = 0.10
if balance < MIN_BALANCE:
    print(f"⚠️  Low balance alert: ${balance:.4f}")
    # Trigger refund from sponsor account or faucet
```

## Common Issues

### Problem: "Invalid private key"
**Solution:** Ensure key is 64 hex characters (32 bytes)
```python
# Wrong
private_key = "alice_key"  # Invalid!

# Right
private_key = "0x" + "a" * 64  # Valid 32-byte hex
```

### Problem: "Address mismatch"
**Solution:** Address is derived from private key, don't change it
```python
# Don't override derived address
agent = Agent(
    agent_id="alice",
    private_key="0x...",
    # Don't pass address parameter - it's auto-derived
)
```

### Problem: "Insufficient balance for transaction"
**Solution:** Fund your address on Arc testnet
```python
# Check your address
agent = Agent(private_key="0x...", ...)
print(f"Fund this address: {agent.address}")

# Visit faucet: https://arc-testnet.example.com/faucet
```

## Summary

| Component | Purpose |
|-----------|---------|
| `generate_wallet()` | Create secp256k1 keypair |
| `get_address_from_private_key()` | Derive address from key |
| `WalletConfig` | Validate wallet setup |
| Agent with private_key | Auto-derives address |
| Arc RPC | Verify balance before signing |
| `BudgetExceeded` exception | Graceful failure on low balance |

**Ready to trade!** Your agents are now blockchain-ready with real wallets on Arc testnet.

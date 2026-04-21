"""
sdk/wallet.py — Wallet Management for Agents

Handles agent wallet generation, key management, and Arc testnet funding.
Agents need:
1. Private key (secp256k1)
2. Derived Ethereum address
3. Arc testnet USDC funding (for testing)

For production:
- Keys should be stored in env vars or secure vaults
- Private keys should never be logged
- Use hardware wallets for production agents
"""

import secrets
from typing import Tuple, Optional
from eth_keys import keys
from eth_utils import to_checksum_address


def generate_wallet() -> Tuple[str, str]:
    """
    Generate a new secp256k1 wallet (private key + address).
    
    Returns:
        (private_key_hex, address_hex): Both with "0x" prefix
        
    Example:
        >>> private_key, address = generate_wallet()
        >>> print(f"Key: {private_key[:10]}...")
        >>> print(f"Address: {address}")
        Key: 0x1a2b3c4d5e...
        Address: 0x742D35Cc6634C0532925a3b844Bc183e0F5e324...
    """
    # Generate 32 random bytes for secp256k1 private key
    private_key_bytes = secrets.token_bytes(32)
    private_key_hex = "0x" + private_key_bytes.hex()
    
    # Derive public key and address from private key
    private_key_obj = keys.PrivateKey(private_key_bytes)
    address = to_checksum_address(private_key_obj.public_key.to_checksum_address())
    
    return private_key_hex, address


def get_address_from_private_key(private_key_hex: str) -> str:
    """
    Derive an Ethereum address from a private key (secp256k1).
    
    Args:
        private_key_hex: Private key with or without "0x" prefix
        
    Returns:
        Checksum address with "0x" prefix
    """
    private_key_hex_clean = private_key_hex.replace("0x", "")
    private_key_obj = keys.PrivateKey(bytes.fromhex(private_key_hex_clean))
    return to_checksum_address(private_key_obj.public_key.to_checksum_address())


class WalletConfig:
    """Configuration for agent wallet setup."""
    
    def __init__(self, private_key: str, arc_rpc_url: str = "https://arc-testnet.example.com"):
        """
        Initialize wallet config.
        
        Args:
            private_key: secp256k1 private key (with or without 0x prefix)
            arc_rpc_url: Arc testnet RPC endpoint
        """
        self.private_key = private_key if private_key.startswith("0x") else f"0x{private_key}"
        self.address = get_address_from_private_key(self.private_key)
        self.arc_rpc_url = arc_rpc_url
    
    def is_valid(self) -> bool:
        """Check if wallet config is valid."""
        try:
            # Try to derive address - if this works, key is valid
            get_address_from_private_key(self.private_key)
            return len(self.address) == 42  # Checksum address is 42 chars
        except Exception:
            return False


# AGENT WALLET SETUP GUIDE
# =======================
#
# Quick Start:
# -----------
# 1. Generate a new wallet:
#    
#    from sdk.wallet import generate_wallet
#    private_key, address = generate_wallet()
#    print(f"Save this key safely: {private_key}")
#    print(f"Fund this address on Arc: {address}")
#
#
# 2. Fund on Arc testnet (via faucet or testnet account):
#    - Visit: https://arc-testnet.example.com/faucet
#    - Enter your address
#    - Request test USDC (e.g., $10)
#
#
# 3. Initialize agent with wallet:
#    
#    from sdk.agent import Agent
#    from sdk.wallet import generate_wallet
#    
#    private_key, address = generate_wallet()
#    
#    agent = Agent(
#        agent_id="my_agent",
#        name="My Agent",
#        address=address,  # Auto-derived from key
#        private_key=private_key,
#        description="Agent description",
#        capabilities=["capability1", "capability2"]
#    )
#    agent.register()
#
#
# Production Best Practices:
# --------------------------
#
# 1. NEVER commit private keys to git:
#    - Use environment variables: export AGENT_PRIVATE_KEY="0x..."
#    - Or use .env files (with .env in .gitignore)
#    - Or use secure vaults (AWS Secrets, HashiCorp Vault)
#
# 2. Store keys with restricted permissions:
#    chmod 600 ~/.agora/wallet.key
#
# 3. For production agents, use hardware wallets:
#    - Ledger / Trezor hardware signer
#    - Hardware-backed KMS
#
# 4. Rotate keys regularly:
#    - Generate new wallet periodically
#    - Move funds to new address
#    - Sunset old address
#
# 5. Monitor balance:
#    - Track spending via Arc RPC
#    - Set up alerts if balance drops below threshold
#    - Auto-replenish via faucet or sponsor account
#
#
# Example: Loading from environment:
# -----------------------------------
#
# import os
# from sdk.agent import Agent
# from sdk.wallet import WalletConfig
#
# # Load from env
# private_key = os.getenv("AGENT_PRIVATE_KEY")
# if not private_key:
#     raise ValueError("AGENT_PRIVATE_KEY not set. Run: export AGENT_PRIVATE_KEY='0x...'")
#
# wallet = WalletConfig(private_key)
# if not wallet.is_valid():
#     raise ValueError("Invalid private key")
#
# agent = Agent(
#     agent_id="production_agent",
#     name="Production Agent",
#     address=wallet.address,
#     private_key=wallet.private_key,
#     description="Production agent for marketplace",
#     capabilities=["analysis", "data_processing"]
# )
# agent.register()
#
# print(f"Agent registered at: {wallet.address}")
# print(f"Fund it with Arc testnet USDC to start trading")

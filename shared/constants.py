"""
shared/constants.py

Central configuration constants for the Agora system.
All values are read from environment variables only — never hardcoded.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Chain & Token ────────────────────────────────────────────────────────────
BLOCKCHAIN = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")
ARC_TESTNET_USDC = os.getenv("ARC_TESTNET_USDC", "0x3600000000000000000000000000000000000000")
ARC_EXPLORER_API = os.getenv("ARC_EXPLORER_API", "https://testnet.arcscan.app/api/v2")
ARC_EXPLORER_BASE = "https://testnet.arcscan.app"

# ─── Wallet Set ───────────────────────────────────────────────────────────────
CIRCLE_WALLET_SET_ID = os.getenv("CIRCLE_WALLET_SET_ID", "de6bdaa1-4c6a-58bb-90fc-8bb337d93080")

# ─── Transaction Settings ─────────────────────────────────────────────────────
TX_FEE_LEVEL = "MEDIUM"
TX_POLL_INITIAL_DELAY = 1.5    # seconds
TX_POLL_MAX_DELAY = 5.0        # seconds
TX_POLL_BACKOFF_FACTOR = 1.2
TX_TERMINAL_STATES = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}

# ─── Agent Prices (USDC) ──────────────────────────────────────────────────────
PRICE_WEB_SEARCH  = "0.0005"
PRICE_EXTRACTOR   = "0.0005"
PRICE_SUMMARIZER  = "0.001"
PRICE_ANALYST     = "0.002"
PRICE_FORMATTER   = "0.0005"

# Cost per full research loop
COST_PER_LOOP = (
    float(PRICE_WEB_SEARCH) +
    float(PRICE_EXTRACTOR) +
    float(PRICE_SUMMARIZER) +
    float(PRICE_ANALYST) +
    float(PRICE_FORMATTER)
)

# ─── Ethereum Gas Comparison (for MarginCalculator) ───────────────────────────
# Average ERC-20 transfer gas cost on Ethereum mainnet (USD, as of 2024)
ETH_GAS_PER_TX_USD = 2.95

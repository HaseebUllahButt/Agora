"""
shared/arc_client.py

Balance verification via Arc testnet RPC.
Minimal, cached balance checks before service execution.
"""

import os
import time
import requests
from typing import Dict, Optional
from functools import lru_cache

# Arc testnet RPC endpoint (Real Testnet URL)
ARC_RPC_URL = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
ARC_USDC_ADDRESS = os.getenv("ARC_TESTNET_USDC", "0x3600000000000000000000000000000000000000")
MIN_BALANCE_USDC = float(os.getenv("MIN_BALANCE_USDC", "0.01"))

# Simple cache: {address: (balance, timestamp)}
_BALANCE_CACHE: Dict[str, tuple[float, float]] = {}
_CACHE_TTL_SECONDS = 30


def get_balance(address: str) -> Optional[float]:
    """
    Get USDC balance for wallet address via Arc RPC.
    Cached with 30-second TTL.
    """
    # Check cache
    if address in _BALANCE_CACHE:
        balance, timestamp = _BALANCE_CACHE[address]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            return balance
    
    # Real RPC Call to Arc
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": ARC_USDC_ADDRESS,
                # balanceOf(address) selector: 0x70a08231
                "data": f"0x70a08231{address[2:].lower().zfill(64)}"
            }, "latest"],
            "id": 1
        }
        response = requests.post(ARC_RPC_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json().get("result", "0x0")
        # USDC on Arc has 6 decimals
        balance = int(result, 16) / 10**6
        
        _BALANCE_CACHE[address] = (balance, time.time())
        return balance
    except Exception as e:
        print(f"⚠️  RPC Balance check failed for {address}: {e}")
        return None


def has_sufficient_balance(address: str, required_usdc: float) -> bool:
    """
    Check if wallet has sufficient USDC balance.
    
    Args:
        address: Wallet address
        required_usdc: Amount needed
    
    Returns:
        True if balance >= required_usdc, False otherwise
    """
    balance = get_balance(address)
    if balance is None:
        # If we can't verify, fail closed (reject the purchase)
        return False
    return balance >= required_usdc


def clear_balance_cache(address: Optional[str] = None):
    """Clear balance cache for testing."""
    global _BALANCE_CACHE
    if address:
        _BALANCE_CACHE.pop(address, None)
    else:
        _BALANCE_CACHE.clear()


if __name__ == "__main__":
    # Quick test
    test_address = "0x1234567890123456789012345678901234567890"
    
    balance = get_balance(test_address)
    print(f"Balance for {test_address}: {balance} USDC")
    
    has_enough = has_sufficient_balance(test_address, 0.001)
    print(f"Has 0.001 USDC: {has_enough}")

"""
shared/x402_middleware.py

x402 HTTP Payment Protocol — Agora implementation.

The x402 standard defines a request/response pattern for machine-readable payments:
  1. Client calls agent endpoint without payment → receives 402 Payment Required
  2. Client sends USDC on-chain and gets a transaction hash
  3. Client retries with X-402-Payment-Proof: <tx_hash> header
  4. Agent verifies payment on-chain, then serves the response

This module handles steps 1 (response factory) and 4 (on-chain verification).

Payment verification uses the Arc testnet explorer API with retry + backoff.
"""

import os
import asyncio
import httpx
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

ARC_EXPLORER_API = os.getenv("ARC_EXPLORER_API", "https://testnet.arcscan.app/api/v2")


async def verify_payment_on_chain(
    tx_hash: str,
    expected_recipient: str,
    expected_amount: float,
    max_retries: int = 10
) -> tuple[bool, str]:
    """
    Verify a USDC payment on Arc testnet by polling the explorer API.

    Waits for the transaction to confirm then checks:
      - Recipient address matches expected agent wallet
      - Transfer value >= expected amount

    Args:
        tx_hash:            On-chain transaction hash from the payer
        expected_recipient: Agent wallet address that should receive funds
        expected_amount:    Minimum USDC amount (as float, e.g. 0.0005)
        max_retries:        How many polling attempts before timeout

    Returns:
        (True, tx_hash)   if verified
        (False, reason)   if not verified
    """
    delay = 1.5
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                # Try token transfers endpoint first (more reliable for ERC-20)
                response = await client.get(
                    f"{ARC_EXPLORER_API}/transactions/{tx_hash}/token-transfers",
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    for transfer in items:
                        to_addr = transfer.get("to", {}).get("hash", "").lower()
                        # USDC has 6 decimals
                        raw_value = float(transfer.get("total", {}).get("value", 0))
                        value_usdc = raw_value / 1_000_000
                        if to_addr == expected_recipient.lower():
                            if value_usdc >= expected_amount:
                                return True, tx_hash

                # Fallback: raw transaction lookup
                response2 = await client.get(
                    f"{ARC_EXPLORER_API}/transactions/{tx_hash}",
                    timeout=5.0
                )
                if response2.status_code == 200:
                    tx = response2.json()
                    recipient = tx.get("to", {}).get("hash", "").lower()
                    raw_value = float(tx.get("value", 0))
                    value_usdc = raw_value / 1_000_000
                    if recipient == expected_recipient.lower() and value_usdc >= expected_amount:
                        return True, tx_hash

        except Exception:
            pass

        await asyncio.sleep(delay)
        delay = min(delay * 1.2, 5.0)

    return False, f"timeout: payment not confirmed after {max_retries} attempts"


def make_402_response(
    agent_wallet_address: str,
    price: str,
    agent_name: str
) -> JSONResponse:
    """
    Return a canonical x402 Payment Required response.

    The response body follows the x402 standard:
    - status 402
    - payment instructions including recipient, amount, network
    - retry instructions telling the caller exactly what to do next

    The caller should:
      1. Send `price` USDC to `agent_wallet_address` on ARC-TESTNET
      2. Retry the original request with header:
         X-402-Payment-Proof: <transaction_hash>
    """
    return JSONResponse(
        status_code=402,
        content={
            "x402_version": "1.0",
            "error": "Payment Required",
            "agent": agent_name,
            "payment": {
                "amount": price,
                "currency": "USDC",
                "network": "ARC-TESTNET",
                "token_address": os.getenv(
                    "ARC_TESTNET_USDC",
                    "0x3600000000000000000000000000000000000000"
                ),
                "recipient": agent_wallet_address
            },
            "retry_instructions": (
                f"Send {price} USDC to {agent_wallet_address} on Arc testnet, "
                "then retry this request with header: "
                "X-402-Payment-Proof: <transaction_hash>"
            )
        }
    )

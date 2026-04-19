"""
shared/circle_client.py

Agora Nanopayments Engine

This module implements Circle's Nanopayments pattern:
  - Sub-cent USDC transfers (as low as $0.0005 per agent call)
  - High-frequency: up to 25 payments per research pipeline
  - Settled on Arc testnet with near-zero gas cost
  - Uses Circle Developer Controlled Wallets SDK

Economic comparison:
  Ethereum mainnet: 50 agent payments × ~$2.95 gas = ~$147.50 in gas fees alone
  Arc Nanopayments: 50 agent payments × ~$0.0001 gas = ~$0.005 in gas fees

This 99.99% cost reduction is what makes autonomous agent labor markets viable.
Without Nanopayments on Arc, this entire system would cost more in gas than the
value it produces.

Usage:
  client = get_circle_client()
  result = await send_usdc("0xFrom...", "0xTo...", "0.0005")
"""

import os
import asyncio
from dotenv import load_dotenv
from developer_controlled_wallets import initiateDeveloperControlledWalletsClient

load_dotenv()


def get_circle_client():
    """
    Initialise and return a Circle Developer Controlled Wallets client.
    API key and entity secret are read from environment only.
    """
    return initiateDeveloperControlledWalletsClient(
        apiKey=os.getenv("CIRCLE_API_KEY"),
        entitySecret=os.getenv("CIRCLE_ENTITY_SECRET")
    )


async def send_usdc(
    from_wallet_address: str,
    to_wallet_address: str,
    amount: str,
    client=None
) -> dict:
    """
    Nanopayment: send USDC on Arc testnet and poll until terminal state.

    This is the core Nanopayment call — designed for sub-cent, high-frequency
    agent-to-agent payments that settle on-chain in seconds.

    Args:
        from_wallet_address: Sender wallet address (orchestrator pays agents)
        to_wallet_address:   Recipient agent wallet address
        amount:              Amount string e.g. "0.0005"
        client:              Optional pre-initialised Circle client

    Returns:
        dict with tx_id, tx_hash, amount, from, to, explorer_url

    Raises:
        Exception if transaction fails or doesn't reach COMPLETE state
    """
    if client is None:
        client = get_circle_client()

    blockchain = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")
    usdc_address = os.getenv("ARC_TESTNET_USDC")
    explorer_base = "https://testnet.arcscan.app"

    tx = await client.createTransaction({
        "blockchain": blockchain,
        "walletAddress": from_wallet_address,
        "destinationAddress": to_wallet_address,
        "amounts": [amount],
        "tokenAddress": usdc_address,
        "fee": {"type": "level", "config": {"feeLevel": "MEDIUM"}}
    })

    tx_id = tx.data.id
    if not tx_id:
        raise Exception("Transaction creation failed — no ID returned")

    # ── Poll with exponential backoff until terminal state ────────────────────
    terminal = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}
    state = tx.data.state
    delay = 1.5
    poll = None

    while state not in terminal:
        await asyncio.sleep(delay)
        poll = await client.getTransaction({"id": tx_id})
        state = poll.data.transaction.state
        delay = min(delay * 1.2, 5.0)

    if state != "COMPLETE":
        raise Exception(f"Nanopayment failed — terminal state: {state}")

    tx_hash = poll.data.transaction.txHash
    return {
        "tx_id": tx_id,
        "tx_hash": tx_hash,
        "amount": amount,
        "from": from_wallet_address,
        "to": to_wallet_address,
        "explorer_url": f"{explorer_base}/tx/{tx_hash}"
    }


async def create_wallet_in_set(wallet_set_id: str, name: str, client=None) -> dict:
    """
    Create a new wallet inside an existing wallet set.
    Used by scripts/create_analyst_wallet.py.

    Returns:
        dict with wallet id and address
    """
    if client is None:
        client = get_circle_client()

    result = await client.createWallets({
        "blockchains": [os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")],
        "count": 1,
        "walletSetId": wallet_set_id,
        "metadata": [{"name": name, "refId": name.lower().replace(" ", "_")}]
    })

    wallet = result.data.wallets[0]
    return {
        "id": wallet.id,
        "address": wallet.address,
        "blockchain": wallet.blockchain,
        "state": wallet.state
    }

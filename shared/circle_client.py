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
from circle.web3.developer_controlled_wallets.api_client import ApiClient
from circle.web3.developer_controlled_wallets.configuration import Configuration
from circle.web3.developer_controlled_wallets.api.transactions_api import TransactionsApi
from circle.web3.developer_controlled_wallets.api.wallets_api import WalletsApi
from circle.web3.developer_controlled_wallets.models.create_transfer_transaction_for_developer_request import (
    CreateTransferTransactionForDeveloperRequest,
)
from circle.web3.developer_controlled_wallets.models.create_transfer_transaction_for_developer_request_blockchain import (
    CreateTransferTransactionForDeveloperRequestBlockchain,
)
from circle.web3.developer_controlled_wallets.models.transfer_blockchain import TransferBlockchain
from circle.web3.developer_controlled_wallets.models.create_wallet_request import CreateWalletRequest
from circle.web3.configurations.api_client import ApiClient as ConfigApiClient
from circle.web3.configurations.configuration import Configuration as ConfigConfiguration
from circle.web3.configurations.api.developer_account_api import DeveloperAccountApi

load_dotenv()


def get_circle_client():
    """
    Initialise and return a Circle Developer Controlled Wallets client.
    API key and entity secret are read from environment only.
    """
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    public_key = os.getenv("CIRCLE_PUBLIC_KEY")

    if not public_key:
        config_client = ConfigApiClient(
            configuration=ConfigConfiguration(access_token=api_key)
        )
        account_api = DeveloperAccountApi(config_client)
        key_response = account_api.get_public_key()
        public_key = key_response.data.public_key if key_response and key_response.data else None

    if not public_key:
        raise Exception(
            "Unable to resolve Circle public key. Set CIRCLE_PUBLIC_KEY in .env or verify CIRCLE_API_KEY."
        )

    config = Configuration(
        access_token=api_key,
        entity_secret=entity_secret,
        public_key=public_key,
    )
    api_client = ApiClient(configuration=config)
    return {
        "api_client": api_client,
        "transactions": TransactionsApi(api_client),
        "wallets": WalletsApi(api_client),
    }


def _run_sdk_call(method, *args, **kwargs):
    """Run blocking Circle SDK calls in a worker thread."""
    return asyncio.to_thread(method, *args, **kwargs)


def _extract_transfer_amount_usdc(tx_data: dict, fallback_amount: str) -> str:
    amounts = tx_data.get("amounts") or []
    return amounts[0] if amounts else fallback_amount


def _extract_transfer_destination(tx_data: dict, fallback_destination: str) -> str:
    return tx_data.get("destinationAddress") or fallback_destination


def _extract_transfer_source(tx_data: dict, fallback_source: str) -> str:
    return tx_data.get("sourceAddress") or fallback_source


def _extract_tx_hash(tx_data: dict) -> str:
    return tx_data.get("txHash") or ""


def _extract_state(tx_data: dict) -> str:
    state = tx_data.get("state")
    if hasattr(state, "value"):
        return state.value
    return str(state)


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

    request = CreateTransferTransactionForDeveloperRequest(
        wallet_address=from_wallet_address,
        destination_address=to_wallet_address,
        amounts=[amount],
        token_address=usdc_address,
        blockchain=CreateTransferTransactionForDeveloperRequestBlockchain(
            TransferBlockchain(blockchain)
        ),
        fee_level="MEDIUM",
    )

    tx = await _run_sdk_call(
        client["transactions"].create_developer_transaction_transfer,
        create_transfer_transaction_for_developer_request=request,
    )

    tx_id = tx.data.id if tx and tx.data else None
    if not tx_id:
        raise Exception("Transaction creation failed — no ID returned")

    # ── Poll with exponential backoff until terminal state ────────────────────
    terminal = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}
    state = tx.data.state.value if hasattr(tx.data.state, "value") else str(tx.data.state)
    delay = 1.5
    tx_data = {"state": state}

    while state not in terminal:
        await asyncio.sleep(delay)
        poll = await _run_sdk_call(client["transactions"].get_transaction, id=tx_id)
        tx_data = poll.to_dict().get("data", {}).get("transaction", {})
        state = _extract_state(tx_data)
        delay = min(delay * 1.2, 5.0)

    if state != "COMPLETE":
        raise Exception(f"Nanopayment failed — terminal state: {state}")

    tx_hash = _extract_tx_hash(tx_data)
    return {
        "tx_id": tx_id,
        "tx_hash": tx_hash,
        "amount": _extract_transfer_amount_usdc(tx_data, amount),
        "from": _extract_transfer_source(tx_data, from_wallet_address),
        "to": _extract_transfer_destination(tx_data, to_wallet_address),
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

    request = CreateWalletRequest(
        blockchains=[os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")],
        count=1,
        wallet_set_id=wallet_set_id,
        metadata=[{"name": name, "refId": name.lower().replace(" ", "_")}],
    )

    result = await _run_sdk_call(
        client["wallets"].create_wallet,
        create_wallet_request=request,
    )

    wallets = result.to_dict().get("data", {}).get("wallets", [])
    if not wallets:
        raise Exception("Wallet creation failed — no wallet returned")
    wallet = wallets[0]
    return {
        "id": wallet.get("id"),
        "address": wallet.get("address"),
        "blockchain": wallet.get("blockchain"),
        "state": wallet.get("state"),
    }

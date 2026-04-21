"""
Circle API client for developer-controlled wallets on Arc testnet.
Handles wallet creation, balance checks, and USDC transfers.
"""

import httpx
import os
import uuid
from typing import Optional
import logging

logger = logging.getLogger(__name__)

CIRCLE_API_URL = "https://api.circle.com/v1"
ARC_CHAIN_ID = "5042002"
USDC_ADDRESS = "0x3600000000000000000000000000000000000000"


class CircleWalletConfig:
    """Configuration for Circle wallet integration."""
    
    def __init__(
        self,
        api_key: str,
        entity_secret: str,
        wallet_set_id: str
    ):
        self.api_key = api_key
        self.entity_secret = entity_secret
        self.wallet_set_id = wallet_set_id
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )
    
    def close(self):
        """Close HTTP client."""
        self.client.close()


class CircleClient:
    """
    Circle Wallets API client for Arc testnet.
    Uses Developer-Controlled Wallets (backend signs transactions).
    """
    
    def __init__(self, config: CircleWalletConfig):
        self.config = config
    
    def create_wallet(self, agent_id: str) -> dict:
        """
        Create a developer-controlled wallet for an agent on Arc testnet.
        
        Returns:
            {
                "wallet_id": "uuid",
                "address": "0x...",
                "state": "LIVE",
                "blockchain": "MATIC"  # Arc mapped as MATIC in Circle
            }
        """
        try:
            idempotency_key = str(uuid.uuid4())
            payload = {
                "idempotencyKey": idempotency_key,
                "description": f"Agent {agent_id} wallet on Arc"
            }
            
            # Create wallet under wallet set
            url = f"{CIRCLE_API_URL}/wallets/{self.config.wallet_set_id}/wallets"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Circle wallet creation failed: {response.text}")
                raise Exception(f"Failed to create wallet: {response.text}")
            
            wallet = response.json()["data"]
            logger.info(f"Created wallet for {agent_id}: {wallet['id']}")
            
            return {
                "wallet_id": wallet["id"],
                "address": wallet["address"],
                "state": wallet["state"],
                "blockchain": wallet["blockchains"][0]["chain"]
            }
        except Exception as e:
            logger.error(f"Circle wallet creation error: {e}")
            raise
    
    def get_wallet(self, wallet_id: str) -> dict:
        """Get wallet details including balance."""
        try:
            url = f"{CIRCLE_API_URL}/wallets/{wallet_id}"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Circle wallet fetch failed: {response.text}")
                raise Exception(f"Failed to fetch wallet: {response.text}")
            
            return response.json()["data"]
        except Exception as e:
            logger.error(f"Circle wallet fetch error: {e}")
            raise
    
    def get_balance(self, wallet_id: str) -> float:
        """
        Get USDC balance for a wallet on Arc.
        
        Returns balance in USDC (float).
        """
        try:
            wallet = self.get_wallet(wallet_id)
            
            # Find Arc/MATIC balance
            for blockchain in wallet.get("blockchains", []):
                if blockchain["chain"] in ["MATIC", "POLYGON"]:  # Arc mapped as MATIC
                    for token in blockchain.get("tokenBalances", []):
                        if token["token"]["address"].lower() == USDC_ADDRESS.lower():
                            return float(token["amount"])
            
            return 0.0
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return 0.0
    
    def transfer_usdc(
        self,
        from_wallet_id: str,
        to_address: str,
        amount_usdc: float,
        idempotency_key: Optional[str] = None
    ) -> dict:
        """
        Transfer USDC from wallet to destination address on Arc.
        
        Args:
            from_wallet_id: Source wallet ID
            to_address: Destination address (0x format)
            amount_usdc: Amount in USDC
            idempotency_key: Optional for idempotency (auto-generated if None)
        
        Returns:
            {
                "transaction_id": "uuid",
                "from_address": "0x...",
                "to_address": "0x...",
                "amount": "100.00",
                "state": "PENDING",
                "txHash": "0x..." (if confirmed)
            }
        """
        try:
            if not idempotency_key:
                idempotency_key = str(uuid.uuid4())
            
            payload = {
                "idempotencyKey": idempotency_key,
                "amounts": [str(amount_usdc)],
                "destinations": [to_address],
                "feeLevel": "MEDIUM"
            }
            
            url = f"{CIRCLE_API_URL}/wallets/{from_wallet_id}/transfers"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Circle transfer failed: {response.text}")
                raise Exception(f"Transfer failed: {response.text}")
            
            tx = response.json()["data"]
            logger.info(f"Transfer initiated: {tx['id']} ({amount_usdc} USDC to {to_address})")
            
            return {
                "transaction_id": tx["id"],
                "from_address": tx["source"]["address"],
                "to_address": to_address,
                "amount": str(amount_usdc),
                "state": tx["state"],
                "txHash": tx.get("txHash", None)
            }
        except Exception as e:
            logger.error(f"Circle transfer error: {e}")
            raise
    
    def get_transaction_status(self, transaction_id: str) -> dict:
        """
        Get transaction status.
        
        Returns:
            {
                "state": "PENDING" | "CONFIRMED" | "FAILED",
                "txHash": "0x...",
                "confirmations": int
            }
        """
        try:
            url = f"{CIRCLE_API_URL}/transfer/{transaction_id}"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Transaction status fetch failed: {response.text}")
                raise Exception(f"Failed to get transaction status: {response.text}")
            
            tx = response.json()["data"]
            return {
                "state": tx["state"],
                "txHash": tx.get("txHash", None),
                "confirmations": tx.get("blockchainTxId", {}).get("confirmations", 0)
            }
        except Exception as e:
            logger.error(f"Transaction status error: {e}")
            raise


def get_circle_client() -> CircleClient:
    """
    Factory function: Get Circle client from environment variables.
    
    Requires:
        CIRCLE_API_KEY
        CIRCLE_ENTITY_SECRET
        CIRCLE_WALLET_SET_ID
    """
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
    
    if not all([api_key, entity_secret, wallet_set_id]):
        raise ValueError(
            "Circle credentials not configured. "
            "Set CIRCLE_API_KEY, CIRCLE_ENTITY_SECRET, CIRCLE_WALLET_SET_ID"
        )
    
    config = CircleWalletConfig(api_key, entity_secret, wallet_set_id)
    return CircleClient(config)

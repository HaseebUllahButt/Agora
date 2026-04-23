"""
Circle API client for developer-controlled wallets on Arc testnet.
Handles wallet creation, balance checks, and USDC transfers.
"""

import httpx
import os
import uuid
from typing import Optional
import logging
import base64
import binascii
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

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
        wallet_set_id: str = None
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
    
    def _get_entity_secret_ciphertext(self) -> str:
        """
        Encrypt the entity secret using Circle's public key.
        Required for state-changing API calls.
        """
        try:
            # 1. Fetch the Public Key from Circle
            url = f"{CIRCLE_API_URL}/w3s/config/entity/publicKey"
            response = self.config.client.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch Circle public key: {response.text}")
            
            public_key_pem = response.json()["data"]["publicKey"]
            
            # 2. Encrypt the entity secret
            # The entity secret is 32 bytes (64 hex characters)
            entity_secret_bytes = binascii.unhexlify(self.config.entity_secret)
            
            pub_key = RSA.importKey(public_key_pem)
            cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)
            ciphertext = cipher.encrypt(entity_secret_bytes)
            
            return base64.b64encode(ciphertext).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to generate entitySecretCiphertext: {e}")
            raise

    def create_wallet_set(self, name: str) -> str:
        """Create a new developer-controlled wallet set."""
        try:
            idempotency_key = str(uuid.uuid4())
            payload = {
                "idempotencyKey": idempotency_key,
                "name": name,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext()
            }
            
            url = f"{CIRCLE_API_URL}/w3s/developer/walletSets"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Wallet Set creation failed: {response.text}")
                raise Exception(f"Failed to create wallet set: {response.text}")
            
            wallet_set_id = response.json()["data"]["walletSet"]["id"]
            logger.info(f"Created Wallet Set: {wallet_set_id}")
            self.config.wallet_set_id = wallet_set_id
            return wallet_set_id
        except Exception as e:
            logger.error(f"Wallet Set creation error: {e}")
            raise

    def create_wallet(self, agent_id: str) -> dict:
        """
        Create a developer-controlled wallet for an agent on Arc testnet.
        """
        try:
            idempotency_key = str(uuid.uuid4())
            blockchain = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "MATIC")
            payload = {
                "idempotencyKey": idempotency_key,
                "description": f"Agent {agent_id} wallet on Arc",
                "blockchains": [blockchain],
                "walletSetId": self.config.wallet_set_id,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext(),
                "count": 1
            }
            
            # Use developer-controlled wallets endpoint
            url = f"{CIRCLE_API_URL}/w3s/developer/wallets"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Circle wallet creation failed: {response.text}")
                raise Exception(f"Failed to create wallet: {response.text}")
            
            # Response returns a list of wallets
            wallets = response.json()["data"]["wallets"]
            wallet = wallets[0]
            logger.info(f"Created wallet for {agent_id}: {wallet['id']}")
            
            return {
                "wallet_id": wallet["id"],
                "address": wallet["address"],
                "state": wallet["state"],
                "blockchain": wallet["blockchain"]
            }
        except Exception as e:
            logger.error(f"Circle wallet creation error: {e}")
            raise
    
    def get_wallet(self, wallet_id: str) -> dict:
        """Get wallet details including balance."""
        try:
            # Note: For developer-controlled, fetch by ID uses /w3s/wallets/
            url = f"{CIRCLE_API_URL}/w3s/wallets/{wallet_id}"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Circle wallet fetch failed: {response.text}")
                raise Exception(f"Failed to fetch wallet: {response.text}")
            
            return response.json()["data"]["wallet"]
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
            
            # Standard balance check for W3S wallets
            balances = wallet.get("balances", [])
            for b in balances:
                # Some APIs return amount as a string
                if b.get("token", {}).get("address", "").lower() == USDC_ADDRESS.lower():
                    return float(b.get("amount", 0.0))
            
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
                "amount": [str(amount_usdc)],
                "destinationAddress": to_address,
                "feeLevel": "MEDIUM",
                "walletId": from_wallet_id,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext()
            }
            
            url = f"{CIRCLE_API_URL}/w3s/developer/transactions/transfer"
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
        """Get transaction status."""
        try:
            url = f"{CIRCLE_API_URL}/w3s/developer/transactions/{transaction_id}"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Transaction status fetch failed: {response.text}")
                raise Exception(f"Failed to get transaction status: {response.text}")
            
            tx = response.json()["data"]["transaction"]
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
    
    if not all([api_key, entity_secret]):
        raise ValueError(
            "Core Circle credentials not configured. "
            "Set CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET"
        )
    
    config = CircleWalletConfig(api_key, entity_secret, wallet_set_id)
    return CircleClient(config)

"""
sdk/consumer.py

Consumer-side SDK: AgoraClient for autonomous service purchasing with Circle settlement.

The client handles:
1. Registry search (semantic or keyword-based)
2. Service discovery
3. x402 header generation and signing (for non-repudiation)
4. Circle wallet integration for real USDC transfers on Arc
5. Atomic settlement broadcasting
6. Result verification
7. Session budget management
"""

import uuid
import time
import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.ecdsa_signing import sign_x402_header
from shared.database import (
    search_providers, get_all_providers, record_transaction,
    update_transaction_status, update_agent_reputation, get_agent,
    get_db
)
from sdk.exceptions import BudgetExceeded
from shared.circle_client import CircleClient, CircleWalletConfig

logger = logging.getLogger(__name__)


class AgoraClient:
    """
    Client for autonomous agents to purchase services on Agora with Circle settlement.
    
    Handles:
    - Budget management (per-session spending limit, tracked on Circle wallet)
    - Service discovery and search
    - x402 payment header generation (for cryptographic proof)
    - Circle wallet USDC transfers on Arc
    - Purchase transactions with atomic checkout
    - Result retrieval and tracking
    
    Usage:
        client = AgoraClient(
            agent_id="alice",
            private_key="0xAlicePrivateKey",
            circle_wallet_id="...",
            circle_api_key=os.getenv("CIRCLE_API_KEY"),
            circle_entity_secret="yyy",
            circle_wallet_set_id="zzz",
            budget_usdc=0.50
        )
        
        # Search for services
        results = client.search("web search")
        
        # Purchase a service (will raise BudgetExceeded if cost > available budget)
        try:
            result = client.purchase_service(
                seller_id="bob",
                service_name="Web Search",
                params={"query": "AI agents"}
            )
        except BudgetExceeded as e:
            print(f"Out of budget: {e.message}")
    """
    
    def __init__(self, 
                 agent_id: str, 
                 private_key: str = None,
                 circle_wallet_id: str = None,
                 circle_api_key: str = None,
                 circle_entity_secret: str = None,
                 circle_wallet_set_id: str = None,
                 budget_usdc: float = 1.0):
        """
        Initialize Agora client with Circle settlement.
        If parameters are missing, they are loaded from the local vault or environment.
        """
        self.agent_id = agent_id
        self.budget_usdc = budget_usdc
        self.spent_usdc = 0.0
        self.transactions = []
        self.start_time = datetime.utcnow()

        # 1. Load from Vault if possible
        from sdk.agent import CONFIG_FILE
        vault_data = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                vault_data = json.load(f).get(agent_id, {})

        self.private_key = private_key or vault_data.get("private_key")
        self.circle_wallet_id = circle_wallet_id or vault_data.get("circle_wallet_id")
        
        # 2. Circle Infrastructure
        api_key = circle_api_key or os.getenv("CIRCLE_API_KEY")
        secret = circle_entity_secret or os.getenv("CIRCLE_ENTITY_SECRET")
        set_id = circle_wallet_set_id or os.getenv("CIRCLE_WALLET_SET_ID")

        if not all([api_key, secret]):
            raise ValueError(f"Circle credentials missing for buyer {agent_id}")

        # Initialize Circle client
        config = CircleWalletConfig(api_key, secret, set_id)
        self.circle_client = CircleClient(config)
        
        logger.info(f"AgoraClient initialized for {agent_id}")
    
    def available_budget(self) -> float:
        """Calculate remaining budget."""
        return self.budget_usdc - self.spent_usdc
    
    def is_budget_exhausted(self) -> bool:
        """Check if spent >= budget."""
        return self.spent_usdc >= self.budget_usdc
    
    def can_afford(self, service_cost: float) -> bool:
        """
        Check if agent can afford a service (raises BudgetExceeded if not).
        
        Args:
            service_cost: Cost of the service in USDC
        
        Returns:
            True if affordable
        
        Raises:
            BudgetExceeded if cost > remaining budget
        """
        remaining = self.available_budget()
        if service_cost > remaining:
            raise BudgetExceeded(service_cost=service_cost, remaining_budget=remaining)
        return True
    
    def settle_payment_circle(self, 
                             seller_id: str, 
                             amount_usdc: float, 
                             idempotency_key: Optional[str] = None) -> Dict:
        """
        Settle payment on Arc via Circle wallet transfer.
        
        Performs real USDC transfer from buyer's Circle wallet to seller's wallet.
        
        Args:
            seller_id: Seller's agent ID
            amount_usdc: Amount in USDC to transfer
            idempotency_key: Optional idempotency key for retry safety
        
        Returns:
            {
                "transaction_id": str,
                "status": "pending" | "confirmed" | "failed",
                "arc_tx_hash": str (if available),
                "amount": float
            }
        
        Raises:
            Exception if seller not found or Circle transfer fails
        """
        try:
            # Get seller's Circle address
            seller = get_agent(seller_id)
            if not seller:
                raise ValueError(f"Seller not found: {seller_id}")
            
            # Get seller's address from the agent record
            seller_circle_address = seller.get("address")
            if not seller_circle_address:
                raise ValueError(f"Seller {seller_id} has no registered wallet address")
            
            # Execute Circle transfer
            logger.info(f"Settling {amount_usdc} USDC from {self.agent_id} to {seller_id} on Arc...")
            tx_result = self.circle_client.transfer_usdc(
                from_wallet_id=self.circle_wallet_id,
                to_address=seller_circle_address,
                amount_usdc=amount_usdc,
                idempotency_key=idempotency_key
            )
            
            logger.info(f"Circle transfer initiated: {tx_result['transaction_id']}")
            
            return {
                "transaction_id": tx_result["transaction_id"],
                "status": tx_result["state"].lower(),
                "arc_tx_hash": tx_result.get("txHash"),
                "amount": amount_usdc,
                "from_address": tx_result["from_address"],
                "to_address": seller_circle_address
            }
        except Exception as e:
            logger.error(f"Circle settlement failed: {e}")
            raise

    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search the registry for services.
        
        Args:
            query: Natural language description of what you need
                   (e.g., "web search", "text summarization")
            limit: Max results to return
        
        Returns:
            List of provider configs with names, prices, reputation scores
        """
        # Search by keyword (simple keyword matching for MVP)
        results = search_providers(query)
        
        # Rank by reputation and price
        ranked = sorted(
            results,
            key=lambda x: (-x.get("reputation_score", 0), x.get("price_usdc", 999))
        )
        
        return ranked[:limit]
    
    def list_providers(self, service_type: str = None) -> List[Dict]:
        """
        List all available providers, optionally filtered by type.
        
        Args:
            service_type: Filter by "data", "compute", "capability", "validation"
        
        Returns:
            List of all active providers
        """
        providers = get_all_providers()
        
        if service_type:
            providers = [p for p in providers if p.get("service_type") == service_type]
        
        return providers
    
    async def call_service(self, provider_id: str, params: Dict = None,
                          budget_override: float = None) -> Dict:
        """
        Call a service and handle payment atomically.
        
        Args:
            provider_id: ID of the provider to call
            params: Parameters to pass to the service
            budget_override: Override session budget for this call
        
        Returns:
            {
                "result": <service_result>,
                "transaction_id": str,
                "service_id": str,
                "amount": float,
                "timestamp": int,
                "arc_tx_hash": str (populated after async settlement)
            }
        """
        params = params or {}
        
        # Get provider config from database
        providers = get_all_providers()
        provider = next((p for p in providers if p["id"] == provider_id), None)
        
        if not provider:
            return {"error": f"Provider not found: {provider_id}"}
        
        price = provider["price_usdc"]
        seller_id = provider["agent_id"]
        
        # Check budget (raises BudgetExceeded if insufficient)
        self.can_afford(price)
        
        # Generate nonce
        nonce = str(uuid.uuid4())
        
        # Generate expiry (60 seconds in future)
        expiry = int(time.time()) + 60
        
        # Sign x402 header
        seller = get_agent(seller_id)
        seller_address = seller.get("address") if seller else "0x0"
        
        x402_header = sign_x402_header(
            private_key_hex=self.private_key,
            amount_usdc=price,
            sender=self.wallet_address,
            recipient=seller_address,
            nonce=nonce,
            expiry_timestamp=expiry
        )
        
        # Record transaction locally
        tx_id = str(uuid.uuid4())[:8]
        self.transactions.append({
            "id": tx_id,
            "provider_id": provider_id,
            "nonce": nonce,
            "amount": price,
            "timestamp": datetime.utcnow().isoformat(),
            "x402_header": x402_header
        })
        
        # Update spent budget
        self.spent_usdc += price
        
        # REGISTRY MODEL:
        # Agora is a SETTLEMENT + REPUTATION LAYER, not a service provider.
        # 
        # 1. Buyer sends x402_header (Circle payment proof) to Marketplace
        # 2. Marketplace validates via Agora Guard (x402 Facilitator)
        # 3. Marketplace calls the provider function
        # 4. Result returned with cryptographic proof hash
        #
        # No mock results. Real settlement via Circle on Arc.
        
        settlement_record = {
            "transaction_id": tx_id,
            "buyer_id": self.agent_id,
            "seller_id": provider_id,
            "amount_usdc": price,
            "payment_method": "circle_programmable_wallet",
            "x402_header": x402_header,
            "nonce": nonce,
            "status": "authorized",
            "settled": False,
            "timestamp": int(time.time()),
            "settlement_chain": "arc-testnet"
        }
        
        return settlement_record
    
    def buy_service(self, seller_id: str, service_name: str = None, params: Dict = None):
        """Alias for purchase_service with simplified signature."""
        name = service_name or "General Service"
        return self.purchase_service(seller_id=seller_id, service_name=name, params=params)

    def purchase_service(self, seller_id: str, service_name: str, params: Dict = None) -> Dict:
        """
        Purchase a service by seller ID and service name with Circle settlement.
        
        Handles:
        1. Budget validation
        2. x402 header generation (for cryptographic proof)
        3. Real USDC transfer via Circle on Arc
        4. Transaction recording
        
        Args:
            seller_id: Agent ID of the seller
            service_name: Name of the service to purchase
            params: Parameters to pass to the service
        
        Returns:
            {
                "transaction_id": str,
                "service_id": str,
                "service_name": str,
                "seller_id": str,
                "amount_usdc": float,
                "circle_tx_id": str (Arc transaction ID),
                "arc_tx_hash": str (if confirmed),
                "status": "pending_execution" | "executed" | "failed",
                "timestamp": int
            }
        
        Raises:
            BudgetExceeded if cost exceeds remaining budget
        """
        params = params or {}
        
        # Find service by seller_id and name
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, price_usdc FROM providers
                WHERE agent_id = ? AND name = ? AND is_active = 1
            """, (seller_id, service_name))
            row = cursor.fetchone()
        
        if not row:
            return {"error": f"Service '{service_name}' not found from seller '{seller_id}'"}
        
        provider_id, price = row[0], row[1]
        
        # Check budget first (raises BudgetExceeded if can't afford)
        self.can_afford(price)
        
        # Generate nonce
        nonce = str(uuid.uuid4())
        
        # Generate expiry (60 seconds in future)
        expiry = int(time.time()) + 60
        
        # Get seller address from DB
        seller = get_agent(seller_id)
        if not seller:
            return {"error": f"Seller '{seller_id}' not found"}
        
        seller_address = seller.get("address", "0x0")
        
        # Derive buyer address directly from private key (never trust stale DB records)
        from eth_keys import keys as eth_keys_lib
        _pk = eth_keys_lib.PrivateKey(bytes.fromhex(self.private_key.replace("0x", "")))
        buyer_address = _pk.public_key.to_checksum_address()
        
        # Sign x402 header (cryptographic proof of payment authorization)
        x402_header = sign_x402_header(
            private_key_hex=self.private_key,
            amount_usdc=price,
            sender=buyer_address,    # derived from actual key - always correct
            recipient=seller_address,
            nonce=nonce,
            expiry_timestamp=expiry
        )
        
        # Record transaction locally (before settlement for atomicity tracking)
        tx_id = str(uuid.uuid4())[:8]
        
        # ──────────────────────────────────────────────────────────────────────
        # NEW: BRIDGE TO MARKETPLACE GATEWAY
        # Instead of settling locally, we send the intent to the Marketplace
        # ──────────────────────────────────────────────────────────────────────
        try:
            logger.info(f"🚀 Sending purchase intent to Marketplace Gateway for {service_name}...")
            
            # Marketplace API URL (Default to localhost:8000)
            AGORA_API_URL = os.getenv("AGORA_API_URL", "http://localhost:8000")
            
            import requests
            response = requests.post(
                f"{AGORA_API_URL}/purchase",
                json={
                    "service_id": provider_id,
                    "buyer_agent_id": self.agent_id,
                    "circle_wallet_id": self.circle_wallet_id,
                    "x402_header": x402_header,
                    "params": params
                },
                timeout=30 # Allow time for on-chain settlement
            )
            
            if response.status_code != 200:
                try:
                    error_msg = response.json().get("detail", "Marketplace rejected purchase")
                except Exception:
                    error_msg = f"Server error {response.status_code}: {response.text[:200] or 'empty response'}"
                logger.error(f"❌ Marketplace Error: {error_msg}")
                return {"error": error_msg}
                
            marketplace_tx = response.json()
            
            # Update local spent budget
            self.spent_usdc += price
            
            logger.info(f"✅ Purchase completed via Gateway: {marketplace_tx['transaction_id']}")
            
            return marketplace_tx
            
        except Exception as e:
            logger.error(f"❌ Gateway connection failed: {e}")
            return {"error": f"Could not connect to Marketplace Gateway: {e}"}

    
    def get_transaction_history(self) -> List[Dict]:
        """Get all transactions in this session."""
        return self.transactions
    
    def get_session_stats(self) -> Dict:
        """Get session statistics."""
        return {
            "start_time": self.start_time.isoformat(),
            "duration_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "budget_total": self.budget_usdc,
            "budget_spent": self.spent_usdc,
            "budget_remaining": self.available_budget(),
            "transaction_count": len(self.transactions),
            "average_transaction": self.spent_usdc / len(self.transactions) if self.transactions else 0
        }


def create_agora_client(agent_id: str, budget_usdc: float) -> AgoraClient:
    """
    Factory function: Create AgoraClient using environment variables for Circle.
    """
    # Get agent
    agent = get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")
    
    # Get Circle config from environment
    circle_api_key = os.getenv("CIRCLE_API_KEY")
    circle_entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    circle_wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
    circle_wallet_id = os.getenv("CIRCLE_WALLET_ID") # Buyer's source wallet
    
    if not all([circle_api_key, circle_entity_secret, circle_wallet_set_id]):
        raise ValueError("Missing Circle credentials in .env")

    # Create client
    return AgoraClient(
        agent_id=agent_id,
        private_key=agent.get("private_key"),
        circle_wallet_id=circle_wallet_id,
        circle_api_key=circle_api_key,
        circle_entity_secret=circle_entity_secret,
        circle_wallet_set_id=circle_wallet_set_id,
        budget_usdc=budget_usdc
    )


if __name__ == "__main__":
    # Note: To use in tests, agents must be registered with Circle credentials first
    print("AgoraClient with Circle integration")
    print("✓ Consumer client module ready")

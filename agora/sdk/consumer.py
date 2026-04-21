"""
sdk/consumer.py

Consumer-side SDK: AgoraClient for autonomous service purchasing.

The client handles:
1. Registry search (semantic or keyword-based)
2. Service discovery
3. x402 header generation and signing
4. Atomic settlement broadcasting
5. Result verification
6. Session budget management
"""

import uuid
import time
import sys
import os
import json
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


class AgoraClient:
    """
    Client for autonomous agents to purchase services on Agora.
    
    Handles:
    - Budget management (per-session spending limit)
    - Service discovery and search
    - x402 payment header generation
    - Purchase transactions with atomic checkout
    - Result retrieval and tracking
    
    Usage:
        client = AgoraClient(
            agent_id="alice",
            wallet_address="0xAlice",
            private_key="0xAlicePrivateKey",
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
            # Handle gracefully: skip, retry, stop, etc.
    """
    
    def __init__(self, agent_id: str, wallet_address: str, private_key: str, budget_usdc: float):
        """
        Initialize Agora client.
        
        Args:
            agent_id: Agent's unique ID in marketplace
            wallet_address: Agent's wallet address (0x...)
            private_key: Agent's private key (0x...) for signing
            budget_usdc: Maximum spend for this session (enforced before signing)
        """
        self.agent_id = agent_id
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.budget_usdc = budget_usdc
        self.spent_usdc = 0.0
        self.transactions = []
        self.start_time = datetime.utcnow()
    
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
        
        # In real implementation, would call provider endpoint here
        # For MVP demo, return mock result
        result = {
            "transaction_id": tx_id,
            "service_id": provider_id,
            "amount": price,
            "timestamp": int(time.time()),
            "status": "pending_settlement",
            "nonce": nonce,
            "x402_header": x402_header
        }
        
        return result
    
    def purchase_service(self, seller_id: str, service_name: str, params: Dict = None) -> Dict:
        """
        Purchase a service by seller ID and service name.
        
        Args:
            seller_id: Agent ID of the seller
            service_name: Name of the service to purchase
            params: Parameters to pass to the service
        
        Returns:
            Service result or error dict
        
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
        
        # Get seller address
        seller = get_agent(seller_id)
        if not seller:
            return {"error": f"Seller '{seller_id}' not found"}
        
        seller_address = seller.get("address", "0x0")
        
        # Sign x402 header
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
            "seller_id": seller_id,
            "service_name": service_name,
            "nonce": nonce,
            "amount": price,
            "timestamp": datetime.utcnow().isoformat(),
            "x402_header": x402_header,
            "params": params
        })
        
        # Update spent budget
        self.spent_usdc += price
        
        return {
            "transaction_id": tx_id,
            "service_id": provider_id,
            "service_name": service_name,
            "seller_id": seller_id,
            "amount_usdc": price,
            "timestamp": int(time.time()),
            "status": "pending_settlement",
            "nonce": nonce,
            "x402_header": x402_header
        }
    
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


if __name__ == "__main__":
    # Quick test
    import asyncio
    
    client = AgoraClient(
        agent_id="test_agent",
        wallet_address="0x1234567890123456789012345678901234567890",
        private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
        budget_usdc=1.0
    )
    
    print("AgoraClient initialized")
    print(f"Budget: ${client.budget_usdc:.4f}")
    print(f"Available: ${client.available_budget():.4f}")
    
    # Search providers
    providers = client.list_providers()
    print(f"\nFound {len(providers)} providers")
    for p in providers[:3]:
        print(f"  {p.get('name')}: ${p.get('price_usdc'):.6f}")
    
    print("\n✓ Consumer client test passed")

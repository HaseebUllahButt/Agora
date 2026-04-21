"""
sdk/agent.py

Agent class: dual-mode buy/sell with budget enforcement.

Usage:
    alice = Agent(
        id="alice",
        name="Data Analyzer",
        description="Analyzes CSV files and produces insights",
        capabilities=["analysis", "sql", "pandas"],
        address="0xAlice",
        private_key="0xAlicePrivateKey"
    )
    alice.register()
    
    # SELLER: Offer services
    alice.offer_service(
        name="CSV Analysis",
        service_type="analysis",
        price_usdc=0.01
    )
    
    # BUYER: Create client and purchase
    client = alice.create_client(budget_usdc=0.50)
    result = client.purchase_service(
        seller_id="bob",
        service_name="Web Search",
        params={"query": "AI agents"}
    )
"""

import json
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.database import create_agent, register_provider, get_all_providers
from sdk.consumer import AgoraClient
from sdk.exceptions import BudgetExceeded
from sdk.wallet import get_address_from_private_key


class Agent:
    """
    Dual-mode agent: can be both buyer and seller.
    
    Attributes:
        id: Unique agent identifier
        name: Display name
        address: Wallet address (for signing transactions)
        private_key: Private key (for ECDSA signing)
        description: What this agent does
        capabilities: List of capabilities/skills
    """
    
    def __init__(self, 
                 agent_id: str,
                 name: str,
                 private_key: str,
                 description: str = "",
                 capabilities: List[str] = None,
                 address: Optional[str] = None):
        """
        Initialize an agent.
        
        Args:
            agent_id: Unique identifier for the agent
            name: Display name
            private_key: secp256k1 private key (with or without 0x prefix)
            description: What this agent does
            capabilities: List of skills/capabilities (e.g., ["analysis", "web_scraping"])
            address: Ethereum address (optional, auto-derived from private_key if not provided)
        """
        self.id = agent_id
        self.name = name
        self.private_key = private_key
        
        # Auto-derive address from private key if not provided
        self.address = address if address else get_address_from_private_key(private_key)
        
        self.description = description
        self.capabilities = capabilities or []
        self.created_at = datetime.utcnow().isoformat()
    
    def register(self) -> Dict:
        """Register agent in the marketplace."""
        try:
            capabilities_json = json.dumps(self.capabilities)
            create_agent(
                agent_id=self.id,
                name=self.name,
                address=self.address,
                private_key=self.private_key,
                description=self.description,
                capabilities=capabilities_json
            )
            return {
                "agent_id": self.id,
                "name": self.name,
                "status": "registered",
                "description": self.description,
                "capabilities": self.capabilities
            }
        except Exception as e:
            return {"error": str(e)}
    
    # ──────────────────────────────────────────────────────────────────
    # SELLER INTERFACE: Register and manage services
    # ──────────────────────────────────────────────────────────────────
    
    def offer_service(self, 
                     name: str,
                     service_type: str,
                     price_usdc: float,
                     description: str = "") -> Optional[str]:
        """
        Register a service to sell.
        
        Args:
            name: Service name (e.g., "CSV Analysis")
            service_type: Category (e.g., "analysis", "ml", "web_search")
            price_usdc: Price per call in USDC
            description: What the service does
        
        Returns:
            service_id if successful, None otherwise
        """
        try:
            import uuid
            provider_id = str(uuid.uuid4())[:8]
            register_provider(
                provider_id=provider_id,
                agent_id=self.id,
                name=name,
                service_type=service_type,
                description=description,
                price_usdc=price_usdc
            )
            return provider_id
        except Exception as e:
            print(f"Failed to offer service: {e}")
            return None
    
    def list_my_services(self) -> List[Dict]:
        """List all services this agent offers."""
        from shared.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, service_type, description, price_usdc FROM providers WHERE agent_id = ?",
                (self.id,)
            )
            return [
                {
                    "provider_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "description": row[3],
                    "price": row[4]
                }
                for row in cursor.fetchall()
            ]
    
    # ──────────────────────────────────────────────────────────────────
    # BUYER INTERFACE: Create client with budget and purchase
    # ──────────────────────────────────────────────────────────────────
    
    def create_client(self, budget_usdc: float) -> "AgoraClient":
        """
        Create a buying client with budget.
        
        Args:
            budget_usdc: Maximum spending for this client session
        
        Returns:
            AgoraClient instance ready to purchase services
        
        Example:
            client = agent.create_client(budget_usdc=0.50)
            result = client.purchase_service(seller_id="bob", service_name="Web Search")
        """
        return AgoraClient(
            agent_id=self.id,
            wallet_address=self.address,
            private_key=self.private_key,
            budget_usdc=budget_usdc
        )
    
    # ──────────────────────────────────────────────────────────────────
    # UTILITY: Discovery and info
    # ──────────────────────────────────────────────────────────────────
    
    def discover_services(self, query: str = "") -> List[Dict]:
        """Discover services available in marketplace."""
        from shared.database import search_providers, get_all_providers
        
        if not query:
            results = get_all_providers()
        else:
            results = search_providers(query)
        
        return [
            {
                "provider_id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("service_type"),
                "description": r.get("description"),
                "price": r.get("price_usdc"),
                "seller": r.get("agent_name"),
                "seller_reputation": r.get("reputation_score", 0)
            }
            for r in results
        ]


def create_agent_with_services(agent_id: str,
                              name: str,
                              address: str,
                              private_key: str,
                              description: str,
                              capabilities: List[str],
                              services: List[Dict] = None) -> Agent:
    """
    Convenience function to create an agent and register services in one call.
    
    Args:
        services: List of dicts: {"name": "...", "type": "...", "price": 0.01}
    
    Returns:
        Registered Agent instance
    """
    agent = Agent(
        agent_id=agent_id,
        name=name,
        address=address,
        private_key=private_key,
        description=description,
        capabilities=capabilities
    )
    agent.register()
    
    if services:
        for service in services:
            agent.offer_service(
                name=service.get("name"),
                service_type=service.get("type"),
                price_usdc=service.get("price", 0.01),
                description=service.get("description", "")
            )
    
    return agent

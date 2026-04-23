import json
import sys
import uuid
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.consumer import AgoraClient
from sdk.exceptions import BudgetExceeded
from sdk.wallet import get_address_from_private_key
from shared.circle_client import CircleClient, CircleWalletConfig
import logging

logger = logging.getLogger(__name__)

# Local config directory for agent persistence
AGORA_HOME = Path.home() / ".agora"
CONFIG_FILE = AGORA_HOME / "agent_config.json"

class Agent:
    """
    Dual-mode agent: can be both buyer and seller.
    
    In the Local-First model, the agent manages its own Circle wallet
    and only shares public metadata (address, name) with the marketplace.
    """
    
    def __init__(self, 
                 agent_id: str,
                 name: str,
                 private_key: str,
                 circle_api_key: str = None,
                 circle_entity_secret: str = None,
                 circle_wallet_set_id: str = None,
                 description: str = "",
                 capabilities: List[str] = None):
        """
        Initialize an agent with local-first Circle integration.
        """
        self.id = agent_id
        self.name = name
        self.private_key = private_key
        
        # Identity address (secp256k1)
        self.address = get_address_from_private_key(private_key)
        
        self.description = description
        self.capabilities = capabilities or []
        
        # Circle configuration (loaded from env if not provided)
        self.circle_api_key = circle_api_key or os.getenv("CIRCLE_API_KEY")
        self.circle_entity_secret = circle_entity_secret or os.getenv("CIRCLE_ENTITY_SECRET")
        self.circle_wallet_set_id = circle_wallet_set_id or os.getenv("CIRCLE_WALLET_SET_ID")
        
        self.circle_client = None
        self.circle_wallet_id = None
        self.circle_address = None # The Arc blockchain address
        
        if self.circle_api_key:
            config = CircleWalletConfig(
                self.circle_api_key, 
                self.circle_entity_secret, 
                self.circle_wallet_set_id
            )
            self.circle_client = CircleClient(config)
        
        # Load local persistence
        self._load_config()

    def _load_config(self):
        """Load local wallet and agent state."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    if self.id in data:
                        agent_data = data[self.id]
                        self.circle_wallet_id = agent_data.get("circle_wallet_id")
                        self.circle_address = agent_data.get("circle_address")
            except Exception as e:
                logger.error(f"Failed to load local config: {e}")

    def _save_config(self):
        """Save local wallet and agent state."""
        AGORA_HOME.mkdir(exist_ok=True, parents=True)
        data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
            except: pass
        
        data[self.id] = {
            "name": self.name,
            "circle_wallet_id": self.circle_wallet_id,
            "circle_address": self.circle_address,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def create_wallet(self) -> str:
        """
        Create a Circle-managed wallet on Arc for this agent.
        """
        if not self.circle_client:
            raise ValueError("Circle credentials missing. Cannot create wallet.")
        
        if self.circle_wallet_id:
            return self.circle_address

        logger.info(f"Creating local Circle wallet for {self.id}...")
        wallet_info = self.circle_client.create_wallet(self.id)
        self.circle_wallet_id = wallet_info["wallet_id"]
        self.circle_address = wallet_info["address"]
        
        self._save_config()
        return self.circle_address

    def get_status(self) -> Dict:
        """View wallet address, balance, and marketplace status."""
        balance = 0.0
        if self.circle_client and self.circle_wallet_id:
            balance = self.circle_client.get_balance(self.circle_wallet_id)
        
        return {
            "agent_id": self.id,
            "name": self.name,
            "secp256k1_address": self.address,
            "arc_address": self.circle_address,
            "usdc_balance": balance,
            "wallet_id": self.circle_wallet_id
        }

    def withdraw_earnings(self, to_address: str) -> Dict:
        """
        [MERCHANT SWEEP] Move all USDC from agent wallet to a destination.
        """
        if not self.circle_client or not self.circle_wallet_id:
            raise ValueError("No wallet found to withdraw from.")
        
        balance = self.circle_client.get_balance(self.circle_wallet_id)
        if balance <= 0:
            return {"error": "No balance to withdraw", "amount": 0}
        
        logger.info(f"Sweeping {balance} USDC from {self.id} to {to_address}...")
        tx = self.circle_client.transfer_usdc(
            from_wallet_id=self.circle_wallet_id,
            to_address=to_address,
            amount_usdc=balance
        )
        return tx

    def register(self) -> Dict:
        """
        Register agent in the marketplace registry (Public Data Only).
        """
        try:
            # Ensure wallet exists first
            if not self.circle_address:
                self.create_wallet()

            import requests
            api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
            
            payload = {
                "agent_id": self.id,
                "name": self.name,
                "address": self.circle_address, 
                "description": self.description,
                "capabilities": self.capabilities
            }
            
            response = requests.post(f"{api_url}/agents/register", json=payload)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return {"error": str(e)}

    # ──────────────────────────────────────────────────────────────────
    # SELLER INTERFACE
    # ──────────────────────────────────────────────────────────────────
    
    def offer_service(self, name: str, service_type: str, price_usdc: float, description: str = "") -> str:
        """Register a service in the marketplace registry."""
        try:
            import requests
            api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
            
            payload = {
                "name": name,
                "service_type": service_type,
                "description": description,
                "price_usdc": price_usdc
            }
            
            resp = requests.post(f"{api_url}/agents/{self.id}/services", json=payload)
            resp.raise_for_status()
            return resp.json().get("provider_id")
        except Exception as e:
            logger.error(f"Failed to offer service: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    # BUYER INTERFACE
    # ──────────────────────────────────────────────────────────────────
    
    def create_client(self, budget_usdc: float) -> AgoraClient:
        """Create a client session for purchasing."""
        if not self.circle_wallet_id:
            self._load_config()
            if not self.circle_wallet_id:
                raise ValueError("Agent must have a wallet to buy stuff.")

        return AgoraClient(
            agent_id=self.id,
            private_key=self.private_key,
            circle_wallet_id=self.circle_wallet_id,
            circle_api_key=self.circle_api_key,
            circle_entity_secret=self.circle_entity_secret,
            circle_wallet_set_id=self.circle_wallet_set_id,
            budget_usdc=budget_usdc
        )

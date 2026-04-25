import json
import sys
import uuid
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.consumer import AgoraClient
from sdk.exceptions import BudgetExceeded
from sdk.wallet import get_address_from_private_key
from shared.circle_client import CircleClient, CircleWalletConfig
import logging

logger = logging.getLogger(__name__)

# Local config directory for agent persistence
AGORA_HOME = Path.home() / ".agora"
CONFIG_FILE = AGORA_HOME / "vault.json"

class Agent:
    """
    Dual-mode agent: can be both buyer and seller.
    
    In the Local-First model, the agent manages its own Circle wallet
    and only shares public metadata (address, name) with the marketplace.
    """
    
    def __init__(self, 
                 agent_id: str,
                 name: str = None,
                 private_key: str = None,
                 circle_api_key: str = None,
                 circle_entity_secret: str = None,
                 circle_wallet_set_id: str = None,
                 description: str = "",
                 capabilities: List[str] = None,
                 auto_sweep_threshold: float = None,
                 main_wallet_address: str = None):
        """
        Initialize an agent with local-first Circle integration.
        """
        self.id = agent_id
        self.name = name or agent_id
        self.private_key = private_key
        
        # Identity address (secp256k1)
        self.address = get_address_from_private_key(private_key) if private_key else None
        
        self.description = description
        self.capabilities = capabilities or []
        self.auto_sweep_threshold = auto_sweep_threshold
        self.main_wallet_address = main_wallet_address
        
        # Circle configuration (loaded from env if not provided)
        self.circle_api_key = circle_api_key or os.getenv("CIRCLE_API_KEY")
        self.circle_entity_secret = circle_entity_secret or os.getenv("CIRCLE_ENTITY_SECRET")
        self.circle_wallet_set_id = circle_wallet_set_id or os.getenv("CIRCLE_WALLET_SET_ID")
        
        self.circle_client = None
        self.circle_wallet_id = None
        self.circle_address = None # The Arc blockchain address
        
        self._init_circle_client()
        
        # Load local persistence
        self._load_config()
        
        # Ensure we have a valid keypair for signing
        if not self.private_key:
            from shared.ecdsa_signing import generate_keypair
            keys = generate_keypair()
            self.private_key = keys["private_key_hex"]
            self.address = keys["address"]
            self._save_config()

    def _init_circle_client(self):
        """Initialize or refresh the Circle client using current credentials."""
        if self.circle_api_key and self.circle_entity_secret:
            config = CircleWalletConfig(
                self.circle_api_key, 
                self.circle_entity_secret, 
                self.circle_wallet_set_id
            )
            self.circle_client = CircleClient(config)

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
                        self.private_key = agent_data.get("private_key")
                        self.address = agent_data.get("address")
                        self.name = agent_data.get("name", self.id)
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
            "role": getattr(self, "role", "agent"),
            "address": self.address,
            "private_key": self.private_key,
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
        
        # If this is a Buyer with an internal client, update its wallet ID too
        if hasattr(self, "client") and self.client:
            self.client.circle_wallet_id = self.circle_wallet_id
        
        self._save_config()
        return self.circle_address

    def fund(self, amount_usdc: float = 0.5) -> Dict:
        """
        Request funds from the Master Funder wallet (if configured).
        This allows agents to bootstrap their budget automatically.
        """
        master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
        if master_wallet_id:
            master_wallet_id = master_wallet_id.strip("'\"")
            
        if not master_wallet_id:
            logger.warning("No CIRCLE_MASTER_WALLET_ID configured in .env. Faucet unavailable.")
            return {"error": "No CIRCLE_MASTER_WALLET_ID configured in .env"}
        
        if not self.circle_address:
            self.create_wallet()
            
        logger.info(f"💰 [Faucet] Checking current balance for {self.id}...")
        try:
            current_balance = self.circle_client.get_balance(self.circle_wallet_id)
            if current_balance >= amount_usdc:
                logger.info(f"✅ {self.id} already has sufficient balance ({current_balance} USDC). Skipping fund.")
                return {"status": "skipped", "reason": "sufficient_balance"}
            
            amount_needed = round(amount_usdc - current_balance, 6)
            logger.info(f"💰 [Faucet] Requesting {amount_needed} USDC from Master Funder for {self.id}...")
            
            # Check master balance first
            master_balance = self.circle_client.get_balance(master_wallet_id)
            if master_balance < amount_needed:
                return {"error": f"Master Funder has insufficient balance ({master_balance} USDC)"}

            tx = self.circle_client.transfer_usdc(
                from_wallet_id=master_wallet_id,
                to_address=self.circle_address,
                amount_usdc=amount_needed
            )
            return tx
        except Exception as e:
            logger.error(f"Faucet transfer failed: {e}")
            return {"error": str(e)}

    @classmethod
    def bootstrap_system(cls):
        """Global initialization: Preps .env with Circle secrets and Wallet Set."""
        import secrets
        from shared.circle_client import CircleWalletConfig, CircleClient
        
        load_dotenv()
        env_path = Path(".env")
        api_key = os.getenv("CIRCLE_API_KEY")
        
        if not api_key:
            print("❌ CIRCLE_API_KEY missing from .env. Please add it first.")
            return False

        print("\n🛠️  AGORA SYSTEM BOOTSTRAP")
        print("--------------------------")
        
        # 1. Entity Secret
        secret = os.getenv("CIRCLE_ENTITY_SECRET")
        if not secret:
            print("🔐 Generating global Entity Secret...")
            secret = secrets.token_hex(32)
            set_key(str(env_path), "CIRCLE_ENTITY_SECRET", secret)
        else:
            print("✅ Entity Secret already configured.")

        # 2. Wallet Set
        set_id = os.getenv("CIRCLE_WALLET_SET_ID")
        if not set_id:
            print("⛓️  Creating global Circle Wallet Set...")
            client = CircleClient(CircleWalletConfig(api_key, secret))
            set_id = client.create_wallet_set("Agora_Agent_Pool")
            set_key(str(env_path), "CIRCLE_WALLET_SET_ID", set_id)
        else:
            print(f"✅ Wallet Set already configured: {set_id}")
            
        print("🎉 SYSTEM READY. You can now create agents.")
        return True

    def _ensure_bootstrapped(self):
        """Internal check to ensure the system is ready."""
        if not self.circle_api_key or not self.circle_entity_secret or not self.circle_wallet_set_id:
            print("⚠️  System not bootstrapped. Running auto-bootstrap...")
            self.bootstrap_system()
            # Reload env
            load_dotenv()
            self.circle_api_key = os.getenv("CIRCLE_API_KEY")
            self.circle_entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
            self.circle_wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
            self._init_circle_client()

    def setup_wizard(self):
        """Interactive setup for Duplex Agents (Buyer/Seller)."""
        print(f"\n🎭 AGORA AGENT SETUP: {self.id}")
        self._ensure_bootstrapped()
        
        # 1. Choose Mode
        print("\nWhat is your primary role?")
        print(" [1] Merchant (I want to list and sell services)")
        print(" [2] Consumer (I only want to buy services)")
        role = input("Choice [1/2]: ").strip() or "1"
        
        # 2. Handle Identity & Wallet (Required for both)
        if not self.private_key:
            print("🔑 Generating identity keys...")
            from sdk.wallet import generate_wallet
            self.private_key, self.address = generate_wallet()
            
        if not self.circle_wallet_id:
            print("⛓️  Creating on-chain Circle wallet...")
            self.create_wallet()
        
        # 3. Details Gathering
        self.name = input(f"   - Display Name [{self.id}]: ").strip() or self.id
        self.description = input("   - Agency Description: ").strip() or "Verified Agora Agent"
        
        # 4. Role-Specific Details
        if role == "1":
            print("\n🛍️ Service Listing Details:")
            self.tmp_service = {
                "name": input("   - Service Title: ").strip() or "General Task",
                "price": float(input("   - Service Price (USDC): ").strip() or "0.001"),
                "description": input("   - Service Description: ").strip() or f"Service by {self.id}"
            }
        else:
            print("\n🛒 Consumer mode activated. (No services listed)")
            if hasattr(self, 'tmp_service'): del self.tmp_service
        
    def publish(self):
        """The 'Go-Live' button: Pushes agent and services to the world."""
        print(f"\n🚀 PUBLISHING {self.id} TO AGORA...")
        self.register()
        
        if hasattr(self, 'tmp_service'):
            self.register_service(
                name=self.tmp_service["name"],
                service_type="ai_task",
                description=f"Professional service by {self.id}",
                price_usdc=self.tmp_service["price"]
            )
            print(f"✅ Live at {self.tmp_service['price']} USDC!")
        else:
            print("✅ Profile updated. (No new services registered)")

    def get_status(self) -> Dict:
        """View wallet address, balance, and marketplace status."""
        balance = 0.0
        if self.circle_client and self.circle_wallet_id:
            balance = self.circle_client.get_balance(self.circle_wallet_id)
        
        return {
            "agent_id": self.id,
            "name": self.name,
            "secp256k1_address": self.address,
            "circle_address": self.circle_address,
            "balance_usdc": balance,
            "has_private_key": self.private_key is not None
        }

    def delete(self) -> bool:
        """Unregister from marketplace and clean up local data."""
        try:
            api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
            import requests
            resp = requests.delete(f"{api_url}/agents/{self.id}", timeout=10)
            
            # Clean up local config
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                if self.id in data:
                    del data[self.id]
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(data, f, indent=2)
            
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            return False

    def set_status(self, active: bool) -> bool:
        """Toggle agent availability on the marketplace."""
        self.active = active
        return self.register()

    def sweep_to_address(self, target_address: str) -> str:
        """Harvest all USDC from agent wallet to a master treasury."""
        if not self.circle_wallet_id or not self.circle_client:
            raise ValueError("No circle wallet found.")
            
        balance = self.circle_client.get_balance(self.circle_wallet_id)
        if balance <= 0.01: # Maintain small amount for gas if needed
            return "Insufficient balance to sweep"
            
        logger.info(f"Sweeping {balance} USDC from {self.id} to {target_address}")
        tx_id = self.circle_client.transfer_usdc(
            from_wallet_id=self.circle_wallet_id,
            to_address=target_address,
            amount_usdc=balance - 0.01 # Leave dust for network fees
        )
        return tx_id

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

    def check_and_sweep(self):
        """
        [AUTONOMOUS FINANCIAL POLICY]
        Check if the current balance exceeds the auto_sweep_threshold.
        If it does, automatically sweep earnings to the main wallet.
        """
        if not self.auto_sweep_threshold or not self.main_wallet_address or not self.circle_client:
            return
            
        logger.info(f"🛡️ [Autonomous Policy Engine] Evaluating financial guardrails for {self.id}...")
        try:
            balance = self.circle_client.get_balance(self.circle_wallet_id)
            if balance >= self.auto_sweep_threshold:
                logger.info(f"💰 [Policy Triggered] Balance (${balance}) >= Threshold ($self.auto_sweep_threshold). Initiating autonomous sweep...")
                self.withdraw_earnings(self.main_wallet_address)
                logger.info(f"✅ [Policy Executed] Funds successfully moved to main wallet.")
        except Exception as e:
            logger.error(f"❌ [Policy Failed] Auto-sweep failed: {e}")

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
            
            response = requests.post(f"{api_url}/agents/register", json=payload, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return {"error": str(e)}

    def register_service(self, name: str, service_type: str, description: str, price_usdc: float):
        """List a specific service on the marketplace."""
        # Forward to the correct method
        res = self.offer_service(name, service_type, price_usdc, description)
        return res is not None

    # ──────────────────────────────────────────────────────────────────
    # SELLER INTERFACE
    # ──────────────────────────────────────────────────────────────────
    
    def offer_service(self, name: str, service_type: str, price_usdc: float, description: str = "") -> str:
        """Register a service in the marketplace registry."""
        try:
            import requests
            api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
            
            payload = {
                "agent_id": self.id,
                "name": name,
                "service_type": service_type,
                "description": description,
                "price_usdc": price_usdc
            }
            
            resp = requests.post(f"{api_url}/agents/{self.id}/services", json=payload, timeout=10)
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

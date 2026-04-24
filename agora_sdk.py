import os
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

# Internal Imports
from sdk.agent import Agent, CONFIG_FILE as VAULT_FILE
from sdk.wallet import generate_wallet as generate_identity
from sdk.seller import Seller
from sdk.buyer import Buyer

def _migrate_vault():
    """Silently migrates data from the old config file to the new vault."""
    OLD_FILE = VAULT_FILE.parent / "agent_config.json"
    if OLD_FILE.exists() and not VAULT_FILE.exists():
        print("🚚 Migrating old agent data to the new Vault...")
        try:
            with open(OLD_FILE, "r") as f:
                data = json.load(f)
            with open(VAULT_FILE, "w") as f:
                json.dump(data, f, indent=2)
            print("✅ Migration complete.")
        except Exception as e:
            print(f"⚠️ Migration failed: {e}")

# Trigger migration on import
_migrate_vault()

def bootstrap_faucet():
    """
    One-click setup for the Master Funder.
    Creates a faucet agent and saves its wallet ID to .env.
    """
    print("\n💧 Bootstrapping Agora Faucet...")
    # 1. Create a hidden system agent for funding
    # Use a non-interactive approach here
    from sdk.seller import Seller
    agent = Seller(agent_id="faucet_master")
    agent._ensure_bootstrapped()
    if not agent.circle_wallet_id: agent.create_wallet()
    
    agent.name = "Agora Master Funder"
    agent.set_service("System Faucet", "Provides liquidity to agents", 0.0, service_type="system")
    agent.register()
    
    # 2. Save its ID to .env automatically
    env_path = Path(".env")
    set_key(str(env_path), "CIRCLE_MASTER_WALLET_ID", agent.circle_wallet_id)
    
    print(f"\n✅ Faucet Bootstrapped!")
    print(f"🆔 Master Wallet ID: {agent.circle_wallet_id}")
    print(f"🔗 Deposit Address: {agent.circle_address}")
    print(f"\nNext Step: Send USDC to the address above at faucet.circle.com")
    return agent

def bootstrap_circle():
    """Programmatic handshake for Circle."""
    from sdk.agent import Agent
    Agent.bootstrap_system()

def create_seller(agent_id: str, name: str = None, service: str = None, price: float = None, service_type: str = None, description: str = None):
    """Factory for Merchant agents."""
    from sdk.seller import Seller
    agent = Seller(agent_id=agent_id)
    agent._ensure_bootstrapped()
    if not agent.circle_wallet_id: agent.create_wallet()
    
    agent.name = name or agent.name or agent_id
    service_name = service or "General Service"
    stype = service_type or "ai_task"
    service_desc = description or f"Professional service by {agent_id}"
    service_price = price if price is not None else 0.001
    
    # Only register if name/service provided or not yet live
    agent.register()
    agent.set_service(service_name, service_desc, service_price, service_type=stype)
    return agent

def create_buyer(agent_id: str, budget: float = 0.1, auto_fund: bool = True):
    """Factory for Consumer agents."""
    agent = Buyer(agent_id=agent_id, budget=budget)
    agent._ensure_bootstrapped()
    if not agent.circle_wallet_id: agent.create_wallet()
    
    if auto_fund:
        # Request bootstrap funds from master faucet
        agent.fund(amount_usdc=budget)
        
    agent.register()
    return agent

def fund_agent(agent_id: str, amount: float = 0.5):
    """Fund an existing agent's wallet."""
    agent = get_agent(agent_id)
    if not agent:
        print(f"❌ Agent '{agent_id}' not found.")
        return
    
    print(f"💰 Funding '{agent_id}' with {amount} USDC from Master Faucet...")
    result = agent.fund(amount)
    if "error" in result:
        print(f"❌ Faucet failed: {result['error']}")
    else:
        print(f"✅ Faucet transfer initiated: {result.get('transaction_id')}")

def edit_buyer(agent_id: str, budget: float = None, instruction: str = None):
    """Quickly update a buyer's mission and budget."""
    agent = get_agent(agent_id)
    if not isinstance(agent, Buyer):
        print(f"❌ '{agent_id}' is not a Buyer.")
        return
    
    if budget is not None: agent.budget = budget
    if instruction is not None: agent.instruction = instruction
    agent._save_config()
    print(f"✅ Buyer '{agent_id}' updated.")

def edit_seller(agent_id: str, name: str = None, service: str = None, price: float = None, service_type: str = None):
    """Quickly update a seller's listing."""
    agent = get_agent(agent_id)
    if not isinstance(agent, Seller):
        print(f"❌ '{agent_id}' is not a Seller.")
        return
        
    # Update registration on Marketplace
    new_name = name or agent.name
    new_service = service or agent.service_name
    new_price = price or agent.price
    new_type = service_type or agent.service_type
    
    agent.set_service(new_service, agent.description, new_price, service_type=new_type)
    agent.name = new_name
    agent._save_config()
    print(f"✅ Seller '{agent_id}' updated and re-registered.")

def search(query: str):
    """Vector search the marketplace for agents."""
    from sdk.consumer import AgoraClient
    client = AgoraClient(agent_id="SearchTool")
    return client.search(query)

def list_agents():
    """Retrieve all local agent details and wallets."""
    if not VAULT_FILE.exists():
        return []
    with open(VAULT_FILE, "r") as f:
        vault = json.load(f)
    return [{
        "id": aid,
        "name": d.get("name"),
        "wallet": d.get("circle_address"),
        "identity": d.get("address"),
        "role": d.get("role", "merchant")
    } for aid, d in vault.items()]

def get_agent(agent_id: str):
    """Restore an existing agent from the vault with the correct role."""
    if not VAULT_FILE.exists():
        return Agent(agent_id=agent_id)
        
    with open(VAULT_FILE, "r") as f:
        vault = json.load(f)
    
    data = vault.get(agent_id, {})
    role = data.get("role", "merchant")
    
    if role == "merchant":
        return Seller(agent_id=agent_id)
    else:
        return Buyer(agent_id=agent_id)

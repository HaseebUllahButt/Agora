import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.agent import Agent, CONFIG_FILE
from sdk.wallet import generate_wallet
import json

def main():
    load_dotenv()
    
    print("🚀 AGORA MARKETPLACE - QUICKSTART")
    print("---------------------------------")
    
    # 1. Credentials Check
    api_key = os.getenv("CIRCLE_API_KEY")
    if not api_key:
        print("❌ Error: CIRCLE_API_KEY not found in .env")
        return
        
    # 2. Identity Generation
    # 2. Agent Details & ID (Ask first to check existence)
    agent_id = input("1. Enter a unique ID for your agent (e.g. alice, bob): ").strip() or "demo_agent"
    
    # 3. Identity Check (Persistence)
    existing_agent = None
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            if agent_id in data:
                existing_agent = data[agent_id]
                
    if existing_agent and "private_key" in existing_agent:
        print(f"   ✓ Existing identity found for {agent_id}. Logging in...")
        private_key = existing_agent["private_key"]
        address = existing_agent["address"]
        agent_name = existing_agent.get("name", agent_id)
        agent_desc = existing_agent.get("description", "Agent")
    else:
        if existing_agent:
            print(f"   ⚠️  Warning: Local config for {agent_id} is incomplete. Regenerating keys...")
        else:
            print("   ✓ No local identity found. Generating new SECP256K1 keys...")
        
        private_key, address = generate_wallet()
        print(f"   ✓ Address: {address}")
        agent_name = input("2. Enter your agent's name (e.g. Alice): ").strip() or "Demo Agent"
        agent_desc = input("3. Enter agent description: ").strip() or "A specialized AI agent on Agora."

    agent_caps = input("4. Enter capabilities (comma-separated): ").strip() or "web_search"
    capabilities = [c.strip() for c in agent_caps.split(",")]
    
    agent = Agent(
        agent_id=agent_id,
        name=agent_name,
        private_key=private_key,
        description=agent_desc,
        capabilities=capabilities
    )
    
    # 4. Local Wallet Creation (Circle on Arc)
    print("\n6. Initializing Circle Wallet on Arc (Local-First)...")
    try:
        arc_address = agent.create_wallet()
        print(f"   ✓ Arc Address: {arc_address}")
        print(f"   ⚠️  FUND THIS WALLET with testnet USDC at: https://arc-testnet.example.com/faucet")
    except Exception as e:
        print(f"   ❌ Wallet creation failed: {e}")
        return

    # 5. Marketplace Registration
    print("\n7. Registering with Agora Registry (Public Data Only)...")
    result = agent.register()
    if "error" in result:
        print(f"   ❌ Registration failed: {result['error']}")
    else:
        print(f"   ✓ Registered! ID: {result.get('agent_id')}")
    # 6. Service Listing
    print("\n8. Listing Initial Service for the Marketplace...")
    srv_name = input("   - Service Name (e.g. Web Research): ").strip() or "Web Search"
    srv_type = input("   - Service Type (slug, e.g. web_search): ").strip() or "web_search"
    srv_desc = input("   - Service Description: ").strip() or "High quality AI search results."
    srv_price = input("   - Price in USDC (e.g. 0.05): ").strip() or "0.05"
    
    service_payload = {
        "agent_id": agent_id,
        "name": srv_name,
        "service_type": srv_type,
        "description": srv_desc,
        "price_usdc": float(srv_price)
    }
    try:
        import requests
        api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
        resp = requests.post(f"{api_url}/agents/{agent_id}/services", json=service_payload)
        if resp.status_code == 200:
            print(f"   ✓ Service '{srv_name}' listed for {srv_price} USDC")
        else:
            print(f"   ⚠️  Service listing failed: {resp.text}")
    except Exception as e:
        print(f"   ⚠️  Service listing error: {e}")

    print("\n🎉 Setup Complete! Your agent and services are live on the marketplace.")
    print(f"   You can view your status anytime: python scripts/status.py --id {agent_id}")

if __name__ == "__main__":
    main()

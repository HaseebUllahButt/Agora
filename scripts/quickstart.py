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
    
    print("🚀 AGORA MARKETPLACE - QUICKSTART (MINIMAL)")
    print("-------------------------------------------")
    
    # 1. Get ID (The only identity we need)
    agent_id = input("1. Enter Agent ID (e.g. bob, alice): ").strip() or "demo_agent"
    
    # 2. Setup Identity
    existing_agent = None
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            if agent_id in data:
                existing_agent = data[agent_id]
                
    if existing_agent and "private_key" in existing_agent:
        print(f"   ✓ Welcome back, {agent_id}. Logging in...")
        private_key = existing_agent["private_key"]
        address = existing_agent["address"]
    else:
        print("   ✓ New Agent identity generated.")
        private_key, address = generate_wallet()
    
    agent = Agent(
        agent_id=agent_id,
        name=agent_id.capitalize(), # Auto-capitalize for the UI
        private_key=private_key,
        description=f"Automated service provider: {agent_id}",
        capabilities=["analysis", "search"] # Sensible defaults
    )

    # 3. Handle Wallet
    print("\n2. Initializing Circle Wallet on Arc...")
    try:
        arc_address = agent.create_wallet()
        print(f"   ✓ Arc Address: {arc_address}")
    except Exception as e:
        print(f"   ❌ Wallet error: {e}")
        return

    # 4. Final Marketplace Steps
    print("\n3. Registration & Listing...")
    agent.register()
    
    service_name = input("   - Service Name (e.g. Analysis): ").strip() or "General AI Service"
    service_desc = input("   - Description (e.g. Deep Research): ").strip() or f"Verified service by {agent_id}"
    price = input("   - Price in USDC (e.g. 0.001): ").strip() or "0.001"
    
    agent.register_service(
        name=service_name,
        service_type="ai_task",
        description=service_desc,
        price_usdc=float(price)
    )
    
    print(f"\n✅ SUCCESS! {agent_id} is live with '{service_name}' for {price} USDC.")
    print(f"   Monitor status: python scripts/status.py --id {agent_id}")

if __name__ == "__main__":
    main()

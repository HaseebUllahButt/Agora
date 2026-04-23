import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.agent import Agent
from sdk.wallet import generate_wallet

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
    print("1. Generating Agent Identity (secp256k1)...")
    private_key, address = generate_wallet()
    print(f"   ✓ Address: {address}")
    
    # 3. Agent Creation
    agent_id = input("2. Enter a unique ID for your agent: ").strip() or "demo_agent"
    agent_name = input("3. Enter your agent's name: ").strip() or "Demo Agent"
    
    agent = Agent(
        agent_id=agent_id,
        name=agent_name,
        private_key=private_key,
        description="A default agent created via Quickstart.",
        capabilities=["data_analysis", "web_search"]
    )
    
    # 4. Local Wallet Creation (Circle on Arc)
    print("\n4. Initializing Circle Wallet on Arc (Local-First)...")
    try:
        arc_address = agent.create_wallet()
        print(f"   ✓ Arc Address: {arc_address}")
        print(f"   ⚠️  FUND THIS WALLET with testnet USDC at: https://arc-testnet.example.com/faucet")
    except Exception as e:
        print(f"   ❌ Wallet creation failed: {e}")
        return

    # 5. Marketplace Registration
    print("\n5. Registering with Agora Registry (Public Data Only)...")
    result = agent.register()
    if "error" in result:
        print(f"   ❌ Registration failed: {result['error']}")
    else:
        print(f"   ✓ Registered! ID: {result.get('agent_id')}")
        print("\n🎉 Setup Complete! Your agent is live on the marketplace.")
        print(f"   You can view your status anytime: python scripts/status.py --id {agent_id}")

if __name__ == "__main__":
    main()

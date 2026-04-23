import os
import sys
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.circle_client import get_circle_client
from sdk.agent import CONFIG_FILE

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Check Agora Agent Status")
    parser.add_argument("--id", required=True, help="Agent ID to check")
    args = parser.parse_args()
    
    print(f"\n--- Agora Agent Status: {args.id} ---")
    
    # 1. Check Local Config
    if not CONFIG_FILE.exists():
        print("❌ Error: No agent configuration found locally at ~/.agora/agent_config.json")
        return
        
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        
    if args.id not in config:
        print(f"❌ Error: Agent '{args.id}' not found in local config.")
        return
        
    agent_data = config[args.id]
    identity_address = agent_data.get("address")
    circle_address = agent_data.get("circle_address")
    wallet_id = agent_data.get("circle_wallet_id")
    
    print(f"🆔 Registry ID: {args.id}")
    print(f"🔑 Arc Identity (Registry): {identity_address}")
    print(f"🏦 Circle Wallet (Settlement): {circle_address}")
    
    # 2. Check On-Chain Balance
    print("\n🔗 On-Chain Status (Arc Testnet):")
    try:
        client = get_circle_client()
        balance = client.get_balance(wallet_id)
        print(f"   💰 Balance: {balance} USDC")
        if balance == 0:
            print(f"   ⚠️  Wallet is empty. Top up at: https://faucet.circle.com/ (Select Arc)")
    except Exception as e:
        print(f"   ❌ Could not fetch balance: {e}")

    # 3. Check Marketplace Status
    print("\n⚖️  Marketplace Stats:")
    try:
        import requests
        api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
        resp = requests.get(f"{api_url}/agents")
        if resp.status_code == 200:
            agents = resp.json()
            match = next((a for a in agents if a["agent_id"] == args.id), None)
            if match:
                print(f"   📈 Reputation: {match.get('reputation', 0)}")
                print(f"   ✓ Verified in Registry")
            else:
                print("   ⚠️  Agent not found in Marketplace Registry (Did you run quickstart.py?)")
        else:
            print("   ⚠️  Marketplace API unreachable or returned error.")
    except Exception as e:
        print(f"   ⚠️  Could not fetch marketplace stats: {e}")

    print("\n-----------------------------------\n")

if __name__ == "__main__":
    main()

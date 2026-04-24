import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from sdk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agora_sdk as agora

def main():
    load_dotenv()
    
    print("💧 AGORA SDK FAUCET")
    print("------------------")
    
    master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if not master_wallet_id:
        print("❌ Error: CIRCLE_MASTER_WALLET_ID not set in .env")
        print("   Please fund a wallet at faucet.circle.com and add its ID to .env")
        return

    agents = agora.list_agents()
    if not agents:
        print("❌ No agents found to fund.")
        return

    print("Select an agent to fund:")
    for i, agent in enumerate(agents, 1):
        print(f"[{i}] {agent['id']} ({agent['name']}) - {agent['wallet'][:10]}...")
    
    print("[0] Cancel")
    
    choice = input("\nChoice: ").strip()
    if not choice or choice == "0":
        return

    try:
        idx = int(choice)
        if 1 <= idx <= len(agents):
            target = agents[idx-1]["id"]
            amount_str = input(f"Amount to send to {target} (USDC) [0.5]: ").strip() or "0.5"
            amount = float(amount_str)
            
            agora.fund_agent(target, amount)
        else:
            print("Invalid choice.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()

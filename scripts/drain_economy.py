import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.agent import Agent, CONFIG_FILE
from shared.core import get_circle_client

def drain_economy():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Agora Economy Drain - Reclaim USDC from agents")
    parser.add_argument("--all", action="store_true", help="Drain all agents found in the local vault")
    parser.add_argument("--id", type=str, help="Drain a specific agent ID")
    parser.add_argument("--role", type=str, choices=["merchant", "consumer", "agent"], help="Filter by role (merchant/consumer)")
    parser.add_argument("--threshold", type=float, default=0.0, help="Only drain if balance is above this threshold")
    parser.add_argument("--to", type=str, help="Destination address (defaults to Master Wallet address)")
    args = parser.parse_args()

    if not args.all and not args.id and not args.role:
        parser.print_help()
        return

    # ... (Circle Client initialization remains the same) ...
    master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if not master_wallet_id:
        print("❌ Error: CIRCLE_MASTER_WALLET_ID not set in .env")
        return

    client = get_circle_client()
    
    # Resolve destination address
    target_address = args.to
    if not target_address:
        print(f"🔍 Fetching address for Master Wallet {master_wallet_id[:8]}...")
        try:
            master_info = client.get_wallet(master_wallet_id)
            target_address = master_info["address"]
            print(f"🎯 Target Address (Master Wallet): {target_address}")
        except Exception as e:
            print(f"❌ Could not get Master Wallet address: {e}")
            return

    # 2. Load the Vault
    if not CONFIG_FILE.exists():
        print(f"❌ No vault file found at {CONFIG_FILE}")
        return

    with open(CONFIG_FILE, "r") as f:
        vault = json.load(f)

    agents_to_drain = []
    if args.id:
        if args.id in vault:
            agents_to_drain.append(args.id)
        else:
            print(f"❌ Agent {args.id} not found in vault.")
            return
    else:
        # Filter by role if requested
        for aid, adata in vault.items():
            if args.role and adata.get("role") != args.role:
                continue
            agents_to_drain.append(aid)

    if not agents_to_drain:
        print("ℹ️  No agents matched the criteria.")
        return

    print(f"💸 Starting drain process for {len(agents_to_drain)} agents (Role: {args.role or 'all'}, Threshold: {args.threshold} USDC)...")
    print("-" * 50)

    for agent_id in agents_to_drain:
        data = vault[agent_id]
        wallet_id = data.get("circle_wallet_id")
        
        if not wallet_id:
            print(f"⏭️  Skipping {agent_id}: No wallet ID found.")
            continue

        try:
            balance = client.get_balance(wallet_id)
            if balance <= args.threshold:
                print(f"ℹ️  {agent_id}: Balance ({balance} USDC) is below threshold ({args.threshold}). Skipping.")
                continue

            print(f"💰 Draining {agent_id} ({balance} USDC)...")
            # We use 0.0001 as a buffer for any potential dust/fees (though Arc is cheap)
            tx = client.transfer_usdc(
                from_wallet_id=wallet_id,
                to_address=target_address,
                amount_usdc=balance
            )
            print(f"   ✅ Success! TX: {tx.get('transaction_id')}")
            
        except Exception as e:
            print(f"   ❌ Failed to drain {agent_id}: {e}")

    print("-" * 50)
    print("✅ Drain complete.")

if __name__ == "__main__":
    drain_economy()

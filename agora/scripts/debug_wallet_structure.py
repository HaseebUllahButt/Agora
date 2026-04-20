"""
scripts/debug_wallet_structure.py

Debug: inspect the actual wallet data structure from Circle API

  python scripts/debug_wallet_structure.py
"""

import os
import sys
import asyncio
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from shared.circle_client import get_circle_client

WALLET_SET_ID = os.getenv("CIRCLE_WALLET_SET_ID")


async def main():
    print("Fetching wallet data from Circle API...\n")
    
    client = get_circle_client()
    
    try:
        result = await asyncio.to_thread(
            client["wallets"].get_wallets,
            wallet_set_id=WALLET_SET_ID
        )
        
        # Convert to dict and print the full structure
        data = result.to_dict()
        print("Full Response Structure:")
        print(json.dumps(data, indent=2, default=str)[:2000])  # First 2000 chars
        
        wallets = data.get("data", {}).get("wallets", [])
        if wallets:
            print("\n\nFirst Wallet Full Structure:")
            print(json.dumps(wallets[0], indent=2, default=str))
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

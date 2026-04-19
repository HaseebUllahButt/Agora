"""
scripts/create_analyst_wallet.py

Creates the Analyst Agent wallet inside the existing Circle wallet set,
then appends ANALYST_AGENT_ID and ANALYST_AGENT_ADDRESS to .env

Run once before starting the system:
  python scripts/create_analyst_wallet.py
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from shared.circle_client import get_circle_client, create_wallet_in_set

WALLET_SET_ID = os.getenv("CIRCLE_WALLET_SET_ID", "de6bdaa1-4c6a-58bb-90fc-8bb337d93080")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


async def main():
    print("=" * 50)
    print("Creating Analyst Agent wallet...")
    print(f"Wallet Set: {WALLET_SET_ID}")

    client = get_circle_client()

    wallet = await create_wallet_in_set(
        wallet_set_id=WALLET_SET_ID,
        name="Analyst Agent",
        client=client
    )

    wallet_id = wallet["id"]
    wallet_address = wallet["address"]

    print("\n✓ Wallet created!")
    print(f"  ID:      {wallet_id}")
    print(f"  Address: {wallet_address}")
    print(f"  Chain:   {wallet.get('blockchain', 'ARC-TESTNET')}")

    # Append to .env
    env_path = os.path.abspath(ENV_FILE)
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.read()

        # Replace placeholder lines
        content = content.replace(
            "ANALYST_AGENT_ID=to_be_filled_by_create_analyst_wallet_script",
            f"ANALYST_AGENT_ID={wallet_id}"
        )
        content = content.replace(
            "ANALYST_AGENT_ADDRESS=to_be_filled_by_create_analyst_wallet_script",
            f"ANALYST_AGENT_ADDRESS={wallet_address}"
        )
        # Also handle .env.example-style placeholders
        content = content.replace(
            "ANALYST_AGENT_ADDRESS=to_be_created",
            f"ANALYST_AGENT_ADDRESS={wallet_address}"
        )
        content = content.replace(
            "ANALYST_AGENT_ID=to_be_created",
            f"ANALYST_AGENT_ID={wallet_id}"
        )

        with open(env_path, "w") as f:
            f.write(content)

        print(f"\n✓ Appended to {env_path}")
    else:
        print(f"\n⚠ .env not found at {env_path}")
        print("Add these lines to your .env manually:")
        print(f"  ANALYST_AGENT_ID={wallet_id}")
        print(f"  ANALYST_AGENT_ADDRESS={wallet_address}")

    print("\nNext step: python scripts/fund_analyst.py")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

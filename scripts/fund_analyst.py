"""
scripts/fund_analyst.py

Sends 2 USDC from the Orchestrator wallet to the Analyst Agent wallet.
Run after create_analyst_wallet.py.

  python scripts/fund_analyst.py
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from shared.circle_client import send_usdc

ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_ADDRESS")
ANALYST_ADDRESS      = os.getenv("ANALYST_AGENT_ADDRESS")
FUND_AMOUNT          = "2"   # 2 USDC


async def main():
    print("=" * 50)
    print("Funding Analyst Agent wallet...")
    print(f"From: {ORCHESTRATOR_ADDRESS}")
    print(f"To:   {ANALYST_ADDRESS}")
    print(f"Amount: {FUND_AMOUNT} USDC")

    if not ANALYST_ADDRESS or ANALYST_ADDRESS.startswith("to_be"):
        print("\n✗ ANALYST_AGENT_ADDRESS not set in .env")
        print("  Run: python scripts/create_analyst_wallet.py first")
        return

    if not ORCHESTRATOR_ADDRESS:
        print("\n✗ ORCHESTRATOR_ADDRESS not set in .env")
        return

    print("\nSending... (polling for confirmation)")

    try:
        result = await send_usdc(
            from_wallet_address=ORCHESTRATOR_ADDRESS,
            to_wallet_address=ANALYST_ADDRESS,
            amount=FUND_AMOUNT
        )
        print("\n✓ Funded successfully!")
        print(f"  TX Hash:  {result['tx_hash']}")
        print(f"  Explorer: {result['explorer_url']}")
        print("\nAnalyst Agent wallet is ready.")
    except Exception as e:
        print(f"\n✗ Funding failed: {e}")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

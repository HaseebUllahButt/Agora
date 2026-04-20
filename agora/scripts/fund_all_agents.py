"""
scripts/fund_all_agents.py

Distribute USDC from Orchestrator to all agent wallets for testing.

The Orchestrator wallet receives USDC from the Arc faucet, then distributes
sub-cent amounts to each agent for their work.

Run after funding the Orchestrator wallet via the Arc faucet:
  https://testnet.arcscan.app/faucet

  python scripts/fund_all_agents.py
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from shared.circle_client import send_usdc

ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_ADDRESS")

# Each agent gets seeded with enough for 50+ calls
AGENT_FUNDING = {
    "Web Search Agent": (os.getenv("WEB_SEARCH_AGENT_ADDRESS"), "0.10"),
    "Extractor Agent": (os.getenv("EXTRACTOR_AGENT_ADDRESS"), "0.10"),
    "Summarizer Agent": (os.getenv("SUMMARIZER_AGENT_ADDRESS"), "0.20"),
    "Analyst Agent": (os.getenv("ANALYST_AGENT_ADDRESS"), "0.50"),
    "Formatter Agent": (os.getenv("FORMATTER_AGENT_ADDRESS"), "0.10"),
    "Consultancy Agent": (os.getenv("CONSULTANCY_AGENT_ADDRESS"), "0.25") if os.getenv("CONSULTANCY_AGENT_ADDRESS") else None,
}


async def fund_agent(agent_name: str, agent_address: str, amount: str) -> bool:
    """Fund a single agent wallet."""
    if not agent_address or agent_address.startswith("to_be"):
        print(f"⏭️  {agent_name:25} | Skipped (address not set)")
        return False
    
    try:
        print(f"💸 {agent_name:25} | Sending ${amount} USDC...", end=" ", flush=True)
        
        result = await send_usdc(
            from_wallet_address=ORCHESTRATOR_ADDRESS,
            to_wallet_address=agent_address,
            amount=amount
        )
        
        print(f"✅ {result['tx_hash'][:16]}...")
        return True
    
    except Exception as e:
        print(f"❌ {str(e)[:60]}")
        return False


async def main():
    print("=" * 80)
    print("FUNDING ALL AGENT WALLETS")
    print("=" * 80)
    print(f"Orchestrator: {ORCHESTRATOR_ADDRESS}\n")
    
    if not ORCHESTRATOR_ADDRESS or ORCHESTRATOR_ADDRESS.startswith("to_be"):
        print("❌ ORCHESTRATOR_ADDRESS not set in .env")
        return
    
    total_to_fund = 0.0
    funded = []
    skipped = []
    
    for agent_name, agent_info in AGENT_FUNDING.items():
        if agent_info is None:
            continue
        agent_address, amount = agent_info
        total_to_fund += float(amount)
        
        success = await fund_agent(agent_name, agent_address, amount)
        if success:
            funded.append(agent_name)
        else:
            skipped.append(agent_name)
    
    print("\n" + "=" * 80)
    print(f"Funded: {len(funded)} agents | Skipped: {len(skipped)}")
    print(f"Total distributed: ${total_to_fund:.2f} USDC")
    print("=" * 80)
    
    if funded:
        print("\n✅ Agents funded and ready to run the pipeline!")
        print("   Next: python scripts/check_balances_onchain.py")
    else:
        print("\n⚠️  No agents were funded. Check your settings.")


if __name__ == "__main__":
    asyncio.run(main())

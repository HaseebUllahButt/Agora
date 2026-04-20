"""
scripts/check_circle_balances.py

Query Circle API directly for wallet token balances

  python scripts/check_circle_balances.py
"""

import os
import sys
import asyncio
from decimal import Decimal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()
import requests

from shared.circle_client import get_circle_client

WALLET_SET_ID = os.getenv("CIRCLE_WALLET_SET_ID")

AGENT_ADDRESSES = {
    "Orchestrator": os.getenv("ORCHESTRATOR_ADDRESS"),
    "Web Search": os.getenv("WEB_SEARCH_AGENT_ADDRESS"),
    "Extractor": os.getenv("EXTRACTOR_AGENT_ADDRESS"),
    "Summarizer": os.getenv("SUMMARIZER_AGENT_ADDRESS"),
    "Analyst": os.getenv("ANALYST_AGENT_ADDRESS"),
    "Formatter": os.getenv("FORMATTER_AGENT_ADDRESS"),
    "Consultancy": os.getenv("CONSULTANCY_AGENT_ADDRESS"),
}

AGENT_IDS = {
    "Orchestrator": os.getenv("ORCHESTRATOR_ID"),
    "Web Search": os.getenv("WEB_SEARCH_AGENT_ID"),
    "Extractor": os.getenv("EXTRACTOR_AGENT_ID"),
    "Summarizer": os.getenv("SUMMARIZER_AGENT_ID"),
    "Analyst": os.getenv("ANALYST_AGENT_ID"),
    "Formatter": os.getenv("FORMATTER_AGENT_ID"),
    "Consultancy": os.getenv("CONSULTANCY_AGENT_ID"),
}

ARC_EXPLORER_API = os.getenv("ARC_EXPLORER_API", "https://testnet.arcscan.app/api/v2")
USDC_ADDRESS = os.getenv("ARC_TESTNET_USDC", "0x3600000000000000000000000000000000000000").lower()


def _fetch_onchain_usdc_balance_sync(address: str) -> float:
    """Fetch USDC balance using ArcScan API and convert from 6-decimal raw units."""
    url = f"{ARC_EXPLORER_API}/addresses/{address}/token-balances"

    try:
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        data = response.json()

        items = data if isinstance(data, list) else data.get("items", [])
        usdc = next(
            (
                item
                for item in items
                if ((item.get("token") or {}).get("address_hash", "").lower() == USDC_ADDRESS)
            ),
            None,
        )

        raw = Decimal(str(usdc.get("value", "0"))) if usdc else Decimal("0")
        return float(raw / Decimal("1000000"))
    except Exception:
        return 0.0


async def main():
    print("=" * 70)
    print("CIRCLE WALLET BALANCES (FROM CIRCLE API)")
    print("=" * 70)
    
    client = get_circle_client()
    
    try:
        wallets_data = []

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    client["wallets"].get_wallets,
                    wallet_set_id=WALLET_SET_ID,
                ),
                timeout=30,
            )
            wallets_data = result.to_dict().get("data", {}).get("wallets", [])
        except Exception as e:
            print(f"⚠️  Circle wallet list unavailable ({e.__class__.__name__}). Falling back to .env addresses.")

        if not wallets_data:
            wallets_data = [
                {
                    "id": AGENT_IDS.get(name) or "N/A",
                    "address": address,
                    "state": "UNKNOWN",
                    "name_hint": name,
                }
                for name, address in AGENT_ADDRESSES.items()
                if address
            ]

        if not wallets_data:
            print("❌ No wallets found (Circle API and .env fallback both empty)")
            return
        
        print(f"\nWallet Set: {WALLET_SET_ID}")
        print(f"Total wallets from Circle: {len(wallets_data)}\n")

        # First pass: capture Circle API balances and determine if fallback is needed
        wallet_rows = []
        circle_total = 0.0
        any_circle_balance = False

        for wallet in wallets_data:
            wallet_id = wallet.get("id", "N/A")
            addr = wallet.get("address", "N/A")
            state = wallet.get("state", "UNKNOWN")

            name = wallet.get("name_hint") or next((k for k, v in AGENT_IDS.items() if v == wallet_id), f"Unknown ({wallet_id[:8]}...)")

            balances = wallet.get("balances", [])
            usdc_balance = 0.0

            if balances:
                for balance in balances:
                    try:
                        amount = float(balance.get("amount", 0))
                        usdc_balance += amount
                    except Exception:
                        pass

            if usdc_balance > 0:
                any_circle_balance = True

            circle_total += usdc_balance
            wallet_rows.append(
                {
                    "wallet_id": wallet_id,
                    "addr": addr,
                    "state": state,
                    "name": name,
                    "balance": usdc_balance,
                }
            )

        use_fallback = not any_circle_balance

        if use_fallback:
            print("⚠️  Circle API returned empty balance data; fetching on-chain balances from ArcScan...\n")

            for row in wallet_rows:
                row["balance"] = _fetch_onchain_usdc_balance_sync(row["addr"])

        total_balance = 0.0
        
        for row in wallet_rows:
            total_balance += row["balance"]

            status = "✅" if row["balance"] > 0 else "❌"
            addr = row["addr"]
            print(f"{status} {row['name']:20} | ${row['balance']:10.4f} USDC | {addr[:14]}...{addr[-6:] if len(addr) >= 6 else addr} | {row['state']}")
        
        print("\n" + "=" * 70)
        print(f"Total USDC: ${total_balance:.4f}")
        print("=" * 70)

        if total_balance == 0 and not use_fallback:
            print("\n⚠️  Note: Circle API may not return balance data in wallet list.")
            print("     Actual balances may exist on-chain (Arc testnet).")
            print("     Try: https://testnet.arcscan.app and search wallet addresses")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

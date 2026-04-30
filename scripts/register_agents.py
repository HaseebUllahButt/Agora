"""
Register the three demo agents with the marketplace facilitator.

Each agent pays its own listing fee out of its own wallet via x402.

Run AFTER the facilitator and the three agent servers are running, with the
*same* env vars (so the keys match)::

    source .env
    python scripts/register_agents.py
"""

from __future__ import annotations

import os
import sys
import time

import httpx

# Make the repo importable when run as `python scripts/register_agents.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from agora_x402 import FacilitatorClient, Wallet
from agora_x402.x402_protocol import sign_payment_header

load_dotenv()

FACILITATOR_URL = os.getenv("FACILITATOR_URL", "http://localhost:8000")

AGENTS = [
    {
        "agent_id": "summarybot",
        "name": "SummaryBot",
        "description": "Summarises text and tags it with sentiment.",
        "endpoint_url": os.getenv("SUMMARYBOT_URL", "http://localhost:9001"),
        "key_env": "SUMMARYBOT_PRIVATE_KEY",
    },
    {
        "agent_id": "moodreader",
        "name": "MoodReader",
        "description": "Cheap, fast sentiment classifier.",
        "endpoint_url": os.getenv("MOODREADER_URL", "http://localhost:9002"),
        "key_env": "MOODREADER_PRIVATE_KEY",
    },
    {
        "agent_id": "datawizard",
        "name": "DataWizard",
        "description": "Pure data-shaping utilities.",
        "endpoint_url": os.getenv("DATAWIZARD_URL", "http://localhost:9003"),
        "key_env": "DATAWIZARD_PRIVATE_KEY",
    },
]


_HTTP = httpx.Client(timeout=2.0, trust_env=False)


def _wait_for(url: str, attempts: int = 30, delay: float = 0.3) -> dict | None:
    for _ in range(attempts):
        try:
            r = _HTTP.get(url)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(delay)
    return None


def main() -> None:
    fac = FacilitatorClient(FACILITATOR_URL)
    fees = fac.get_listing_fee()
    listing_fee = float(fees.get("listing_fee_usdc", 0))
    treasury = fees.get("treasury_address", "")

    print(f"Marketplace listing fee: {listing_fee} USDC → {treasury}\n")

    for agent in AGENTS:
        if not os.getenv(agent["key_env"]):
            print(
                f"⚠️  {agent['key_env']} is not set. The running agent generated "
                f"an ephemeral wallet that won't match this script. "
                f"Run `python scripts/setup_env.py` to provision keys."
            )
        wallet = Wallet.from_env(agent["key_env"])

        # Optional sanity: make sure the live agent uses the same wallet
        live = _wait_for(agent["endpoint_url"])
        if live and live["wallet_address"].lower() != wallet.address.lower():
            print(
                f"❌ {agent['name']} is running with wallet {live['wallet_address']} "
                f"but {agent['key_env']} resolves to {wallet.address}. "
                f"Restart the agent with the same env, or re-run setup_env.py."
            )
            continue

        listing_payment = None
        if listing_fee > 0:
            listing_payment = sign_payment_header(
                private_key_hex=wallet.private_key,
                amount=str(listing_fee),
                sender=wallet.address,
                recipient=treasury,
                resource=f"{FACILITATOR_URL}/agents/register",
                expiry_seconds=120,
            )

        try:
            res = fac.register_agent(
                agent_id=agent["agent_id"],
                name=agent["name"],
                address=wallet.address,
                endpoint_url=agent["endpoint_url"],
                description=agent["description"],
                listing_fee_payment=listing_payment,
            )
            print(
                f"✅ {agent['name']:<12} listed   "
                f"fee={res.get('listing_fee_paid_usdc')} USDC   tx={res.get('listing_tx_id')}"
            )
        except Exception as e:
            print(f"❌ {agent['name']:<12} listing failed: {e}")
            continue

        # Pull the services from the live agent + register each one
        if live and live.get("services"):
            for svc in live["services"]:
                try:
                    fac.register_service(
                        agent_id=agent["agent_id"],
                        service_id=f"{agent['agent_id']}-{svc['service_id']}",
                        name=svc["name"],
                        description=svc.get("description", ""),
                        price=str(svc["price_usdc"]),
                        category=svc.get("category", "capability"),
                        endpoint_url=f"{agent['endpoint_url']}{svc['path']}",
                    )
                    print(f"   ↳ service '{svc['name']}' @ {svc['price_usdc']} USDC")
                except Exception as e:
                    print(f"   ↳ service '{svc['name']}' failed: {e}")

    print()
    treasury_total = _HTTP.get(f"{FACILITATOR_URL}/marketplace/treasury").json()
    print(f"Treasury balance: {treasury_total}")


if __name__ == "__main__":
    main()

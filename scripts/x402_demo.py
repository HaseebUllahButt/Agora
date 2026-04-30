"""
End-to-end x402 demo.

Pre-requisites (in separate terminals)::

    bash scripts/run_facilitator.sh                      # :8000
    agora-agent run agents/moodreader/agent.py --port 9002
    agora-agent run agents/datawizard/agent.py --port 9003
    agora-agent run agents/summarybot/agent.py --port 9001
    python scripts/register_agents.py

Then::

    python scripts/x402_demo.py

What you'll see
---------------
1. A buyer agent calls SummaryBot's ``/summarize`` endpoint with one tweet.
2. The first request is met with a 402; the buyer signs an X-PAYMENT and retries.
3. The facilitator verifies the header, burns the nonce, settles the buyer's
   USDC to SummaryBot's wallet (minus the marketplace fee).
4. SummaryBot, in handling the request, in turn pays MoodReader for sentiment.
5. The buyer also pays DataWizard to pretty-print the final result.
6. The script prints the marketplace's transaction ledger so you can see all
   three settlements with the marketplace fee skim.
"""

from __future__ import annotations

import os
import sys

import httpx
from rich.console import Console
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from agora_x402 import FacilitatorClient, Wallet, X402Client


FACILITATOR_URL = os.getenv("FACILITATOR_URL", "http://localhost:8000")
SUMMARYBOT_URL = os.getenv("SUMMARYBOT_URL", "http://localhost:9001")
DATAWIZARD_URL = os.getenv("DATAWIZARD_URL", "http://localhost:9003")

SAMPLE_TEXT = (
    "I just shipped the new release and the customers are absolutely loving it! "
    "The whole team came together this week and pulled off something genuinely great."
)

console = Console()


def main() -> None:
    buyer_wallet = Wallet.from_env("BUYER_PRIVATE_KEY")
    console.rule("[bold cyan]Agora x402 demo")
    console.print(f"Buyer wallet : [yellow]{buyer_wallet.address}[/yellow]")
    console.print(f"Facilitator  : {FACILITATOR_URL}")
    console.print(f"SummaryBot   : {SUMMARYBOT_URL}")
    console.print(f"DataWizard   : {DATAWIZARD_URL}")
    console.print()

    buyer = X402Client(wallet=buyer_wallet, max_price="0.05")

    # Step 1: Pay SummaryBot to summarise the tweet.
    console.print("[bold]1. Buyer → SummaryBot.summarize  (will internally call MoodReader)[/bold]")
    sresp = buyer.post(f"{SUMMARYBOT_URL}/summarize", json={"text": SAMPLE_TEXT}, timeout=30)
    if sresp.status_code != 200:
        console.print(f"[red]SummaryBot failed: {sresp.status_code}[/red] {sresp.text[:500]}")
        sys.exit(1)
    sbody = sresp.json()
    console.print(f"   summary  : {sbody['result']['summary']!r}")
    console.print(f"   sentiment: {sbody['result'].get('sentiment')}")
    console.print(f"   primary settlement  : "
                  f"net {sbody['settlement'].get('net_usdc')} USDC, "
                  f"fee {sbody['settlement'].get('marketplace_fee_usdc')} USDC")
    console.print(f"   upstream settlement : {sbody['result'].get('upstream_payment')}")
    console.print()

    # Step 2: Pay DataWizard to pretty-print the SummaryBot output.
    console.print("[bold]2. Buyer → DataWizard.pretty-json  (separate independent agent)[/bold]")
    dresp = buyer.post(f"{DATAWIZARD_URL}/pretty-json", json={"payload": sbody["result"]}, timeout=15)
    if dresp.status_code != 200:
        console.print(f"[red]DataWizard failed: {dresp.status_code}[/red] {dresp.text[:500]}")
    else:
        dbody = dresp.json()
        console.print(dbody["result"]["pretty"])
        console.print(f"   settlement: net {dbody['settlement'].get('net_usdc')} USDC, "
                      f"fee {dbody['settlement'].get('marketplace_fee_usdc')} USDC")
    console.print()

    # Step 3: Show the marketplace ledger
    console.print("[bold]3. Marketplace settlement ledger[/bold]")
    fac = FacilitatorClient(FACILITATOR_URL)
    txs = fac.list_transactions(limit=20)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("when", style="dim", overflow="fold")
    table.add_column("kind")
    table.add_column("buyer", overflow="fold")
    table.add_column("→ seller", overflow="fold")
    table.add_column("gross")
    table.add_column("fee")
    table.add_column("net")
    table.add_column("ref", overflow="fold")

    for t in reversed(txs):
        table.add_row(
            t["created_at"][11:19],
            t["kind"],
            (t["buyer_address"] or "")[:10],
            (t.get("seller_address") or "")[:10],
            f"{t['gross_usdc']:.6f}",
            f"{t['marketplace_fee_usdc']:.6f}",
            f"{t['net_usdc']:.6f}",
            t["settlement_ref"] or "",
        )
    console.print(table)

    treasury = httpx.Client(trust_env=False, timeout=5).get(
        f"{FACILITATOR_URL}/marketplace/treasury"
    ).json()
    console.print(f"\n[bold green]Marketplace treasury balance:[/bold green] "
                  f"{treasury['treasury_balance_usdc']} USDC")


if __name__ == "__main__":
    main()

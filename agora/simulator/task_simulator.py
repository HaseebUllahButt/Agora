"""
simulator/task_simulator.py

Demo task simulator — fires 3 pre-defined research tasks sequentially.
Designed to generate 50+ on-chain transactions for the submission demo.

Run AFTER all agent servers and the main API are running:
  python simulator/task_simulator.py

Expected output:
  Task 1: ~15-20 transactions
  Task 2: ~10-15 transactions
  Task 3: ~15-20 transactions
  Total:  50+ on-chain Nanopayments on Arc testnet
"""

import asyncio
import httpx

API_BASE = "http://localhost:8000"

TASKS = [
    {
        "topic": "Stripe payment processing competitive analysis",
        "budget": 0.18,
        "task_type": "competitive_intelligence",
        "company_context": {
            "company_size": "startup",
            "stage": "seed",
            "main_strength": "developer experience",
            "main_weakness": "brand recognition",
            "budget": "limited",
            "target_market": "SMBs and developer teams"
        }
    },
    {
        "topic": "OpenAI API pricing and features competitive analysis 2024",
        "budget": 0.12,
        "task_type": "competitive_intelligence",
        "company_context": {
            "company_size": "startup",
            "stage": "pre-seed",
            "main_strength": "inference speed",
            "main_weakness": "model quality vs GPT-4",
            "budget": "very limited",
            "target_market": "developers and AI-native companies"
        }
    },
    {
        "topic": "Notion vs Linear vs Jira project management tool analysis",
        "budget": 0.15,
        "task_type": "competitive_intelligence",
        "company_context": {
            "company_size": "smb",
            "stage": "series-a",
            "main_strength": "deep customization",
            "main_weakness": "onboarding complexity",
            "budget": "moderate",
            "target_market": "engineering and product teams"
        }
    }
]


async def run_simulation():
    print("=" * 60)
    print("AGORA TASK SIMULATOR")
    print("Autonomous Research Protocol on Arc")
    print("=" * 60)
    print(f"Running {len(TASKS)} tasks to generate 50+ transactions")
    print(f"API: {API_BASE}")
    print()

    total_txns = 0
    total_spent = 0.0

    async with httpx.AsyncClient(timeout=600.0) as client:
        # Verify API is up
        try:
            health = await client.get(f"{API_BASE}/health")
            print(f"✓ API healthy: {health.json()['status']}")
        except Exception as e:
            print(f"✗ API not reachable at {API_BASE}: {e}")
            print("  Start the API first: uvicorn api.main:app --port 8000")
            return

        for i, task in enumerate(TASKS, 1):
            print(f"\n{'─' * 50}")
            print(f"Task {i}/{len(TASKS)}: {task['topic']}")
            print(f"Budget: ${task['budget']} USDC")
            print("Running...")

            try:
                response = await client.post(
                    f"{API_BASE}/run",
                    json=task
                )

                if response.status_code != 200:
                    print(f"  ✗ Error: HTTP {response.status_code}")
                    continue

                result = response.json()
                budget_summary = result.get("budget_summary", {})
                tx_count = result.get("transaction_count", 0)
                spent = budget_summary.get("total_spent", 0)

                total_txns += tx_count
                total_spent += spent

                print("  ✓ Complete")
                print(f"  Transactions: {tx_count}")
                print(f"  Spent: ${spent:.4f} USDC")
                print(f"  Remaining: ${budget_summary.get('remaining', 0):.4f} USDC")

                if result.get("report") and result["report"].get("report_markdown"):
                    preview = result["report"]["report_markdown"][:200]
                    print(f"  Report preview: {preview}...")

            except Exception as e:
                print(f"  ✗ Task failed: {e}")

    print(f"\n{'=' * 60}")
    print("SIMULATION COMPLETE")
    print(f"Total transactions: {total_txns}")
    print(f"Total spent: ${total_spent:.4f} USDC")
    print("View all transactions: https://testnet.arcscan.app")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_simulation())

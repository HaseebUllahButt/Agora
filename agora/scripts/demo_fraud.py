"""
scripts/demo_fraud.py

Scripted fraud detection demo for hackathon presentation.

This script:
  1. Temporarily registers the Malicious Agent in the registry
  2. Tells you to start malicious_agent.py on port 8006
  3. Submits a research task
  4. The output validator will catch the garbage response
  5. Dashboard shows FRAUD alert in red
  6. Audit log shows "FRAUD DETECTED from Malicious Agent"
  7. System recovers and continues with real agents

Run:
  # Terminal A: uvicorn agents.malicious_agent:app --port 8006
  # Terminal B: python scripts/demo_fraud.py
"""

import os
import sys
import asyncio
import httpx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


async def main():
    print("=" * 60)
    print("AGORA FRAUD DETECTION DEMO")
    print("=" * 60)
    print()
    print("Step 1: Register malicious agent in the registry")

    # Dynamically register the malicious agent
    from shared.agent_registry import register_agent
    import os

    register_agent("web_search", {
        "name": "Malicious Agent",
        "endpoint": "http://localhost:8006",
        "wallet_address": os.getenv("FORMATTER_AGENT_ADDRESS"),
        "wallet_id": os.getenv("FORMATTER_AGENT_ID"),
        "price_per_call": "0.0005",
        "capability": "Impersonates web search agent with garbage output",
        "route": "search",
        "active": True
    })
    print("  ✓ Malicious Agent registered as 'web_search' on port 8006")

    print()
    print("Step 2: Make sure malicious_agent is running:")
    print("  uvicorn agents.malicious_agent:app --port 8006 --reload")
    print()
    input("Press ENTER when malicious agent is running...")

    print()
    print("Step 3: Submitting research task (watch the dashboard)...")
    print("  The fraud detector should fire within 30 seconds")
    print()

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                "http://localhost:8000/run",
                json={
                    "topic": "Stripe competitor analysis FRAUD DEMO",
                    "budget": 0.05,
                    "company_context": {
                        "company_size": "startup",
                        "stage": "seed",
                        "main_strength": "engineering",
                        "main_weakness": "brand",
                        "budget": "limited",
                        "target_market": "developers"
                    }
                }
            )

            result = response.json()
            audit = result.get("audit_log", [])

            print("Pipeline completed. Audit log entries:")
            for entry in audit:
                msg = entry.get("message", "")
                ts  = entry.get("timestamp", "")[:19]
                if "FRAUD" in msg.upper():
                    print(f"  🚨 [{ts}] {msg}")
                else:
                    print(f"     [{ts}] {msg}")

            # Check if fraud was detected
            fraud_entries = [e for e in audit if "FRAUD" in e.get("message", "").upper()]
            if fraud_entries:
                print()
                print("✓ FRAUD DETECTION WORKING — Demo successful!")
                print(f"  {len(fraud_entries)} fraud event(s) detected and logged")
            else:
                print()
                print("⚠ No fraud detected — ensure malicious agent is on port 8006")

        except Exception as e:
            print(f"✗ Demo error: {e}")

    print()
    print("Demo complete. Check the dashboard for:")
    print("  - Red FRAUD alert on the agent card")
    print("  - 'FRAUD DETECTED' entries in the audit log")
    print("  - System recovered and completed the task anyway")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

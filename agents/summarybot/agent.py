"""
SummaryBot — composes a summary by:

1. Producing a naive summary itself, and
2. Calling MoodReader (a separate agent) over x402 to add a sentiment label.

This demonstrates *agent-to-agent x402 payment*: SummaryBot pays MoodReader
out of its own wallet for every summarize request it serves. Net economics:

* Buyer pays SummaryBot ``$0.0015`` per call.
* SummaryBot pays MoodReader ``$0.0008`` per call.
* SummaryBot keeps the spread minus marketplace fees on both legs.

Run::

    agora-agent run agents/summarybot/agent.py --port 9001
"""

from __future__ import annotations
from agora_x402 import pay_for

import os
from pathlib import Path

from agora_x402 import AgentServer, Wallet, X402Client
from dotenv import load_dotenv

# Auto-load the repo .env so this file works whether you `agora-agent run …`
# it from any shell, import it for tests, or start it via uvicorn directly.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


# Wallet / config — loaded once at import time
_wallet = Wallet.from_env("SUMMARYBOT_PRIVATE_KEY")
_moodreader_url = os.getenv("MOODREADER_URL", "http://localhost:9002")

# Buying-side client — SummaryBot will use this to pay MoodReader for sentiment
_buyer = X402Client(
    wallet=_wallet,
    max_price="0.01",  # safety cap — never auto-pay > 1 cent per upstream call
)


def _naive_summary(text: str) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= 240:
        return text
    return text[:237] + "..."


@pay_for(
    price="0.0015",
    category="llm",
    description="Summarize text and tag it with a sentiment label (calls MoodReader internally).",
)
def summarize(text: str) -> dict:
    summary = _naive_summary(text)
    sentiment: dict | None = None
    sentiment_settlement: dict | None = None
    try:
        resp = _buyer.post(
            f"{_moodreader_url}/analyze-sentiment", json={"text": text})
        if resp.status_code == 200:
            body = resp.json()
            sentiment = body.get("result")
            sentiment_settlement = body.get("settlement")
        else:
            sentiment = {
                "error": f"MoodReader returned {resp.status_code}", "body": resp.text[:200]}
    except Exception as e:  # network / payment cap / etc.
        sentiment = {"error": f"Could not reach MoodReader: {e}"}

    return {
        "summary": summary,
        "length_in": len(text or ""),
        "length_out": len(summary),
        "sentiment": sentiment,
        "upstream_payment": sentiment_settlement,
    }


server = AgentServer(
    agent_id="summarybot",
    name="SummaryBot",
    description="Summarises text and tags it with sentiment from MoodReader.",
    wallet=_wallet,
)

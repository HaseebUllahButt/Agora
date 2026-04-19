"""
agents/summarizer_agent.py — Port 8003

Summarizer Agent: condenses batches of extracted research into key findings.
Price: $0.001 USDC per call (Nanopayment).

Receives multiple extraction results and synthesises them into a concise,
high-signal paragraph that feeds into the Analyst Agent.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from shared.x402_middleware import verify_payment_on_chain, make_402_response
from shared.llm import generate_gemini_content

load_dotenv()

app = FastAPI(title="Agora — Summarizer Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_NAME    = "Summarizer Agent"
AGENT_WALLET  = os.getenv("SUMMARIZER_AGENT_ADDRESS")
PRICE         = "0.001"


class SummarizeRequest(BaseModel):
    extractions: list
    topic: str


@app.post("/summarize")
async def summarize(
    request: SummarizeRequest,
    x_402_payment_proof: str = Header(None)
):
    # ── Step 1: Require payment ───────────────────────────────────────────────
    if not x_402_payment_proof:
        return make_402_response(AGENT_WALLET, PRICE, AGENT_NAME)

    # ── Step 2: Verify Nanopayment on Arc ─────────────────────────────────────
    verified, result = await verify_payment_on_chain(
        tx_hash=x_402_payment_proof,
        expected_recipient=AGENT_WALLET,
        expected_amount=float(PRICE)
    )
    if not verified:
        return JSONResponse(
            status_code=402,
            content={"error": f"Payment verification failed: {result}"}
        )

    # ── Step 3: Summarize with Gemini ──────────────────────────────────────────
    extraction_text = "\n\n".join([str(e) for e in request.extractions])

    prompt = f"""You are a senior competitive intelligence analyst.

Topic: {request.topic}

You have received the following extracted data from multiple research passes:

{extraction_text[:6000]}

Synthesise this into a structured competitive intelligence summary with these sections:

**Market Position:** (2-3 sentences on where they sit in the market)

**Pricing:** (concrete numbers and tiers if found)

**Key Strengths:** (3-5 bullet points)

**Key Weaknesses:** (3-5 bullet points)

**Recent Developments:** (any notable news or changes)

**Customer Sentiment:** (what customers actually say)

Be specific. Use numbers when available. Do not speculate beyond what the data supports.
"""
    try:
        summary = await generate_gemini_content(prompt)
        summary = summary.strip()
    except Exception as e:
        summary = f"Summarization failed: {str(e)}"

    return {
        "agent": AGENT_NAME,
        "topic": request.topic,
        "summary": summary,
        "extraction_count": len(request.extractions),
        "payment_verified": x_402_payment_proof,
        "cost": PRICE
    }


@app.get("/health")
async def health():
    return {"agent": AGENT_NAME, "wallet": AGENT_WALLET, "price": PRICE, "status": "ok"}

"""
agents/extractor_agent.py — Port 8002

Extractor Agent: pulls structured competitive intelligence data from raw text.
Price: $0.0005 USDC per call (Nanopayment).

Extracts: pricing, features, weaknesses, differentiators, market position,
          customer sentiment from raw search results or scraped content.
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

app = FastAPI(title="Agora — Extractor Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_NAME    = "Extractor Agent"
AGENT_WALLET  = os.getenv("EXTRACTOR_AGENT_ADDRESS")
PRICE         = "0.0005"


class ExtractRequest(BaseModel):
    text: str
    topic: str


@app.post("/extract")
async def extract(
    request: ExtractRequest,
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

    # ── Step 3: Extract structured data with Gemini ───────────────────────────
    prompt = f"""You are a competitive intelligence data extractor.

Topic: {request.topic}

Raw content to extract from:
{request.text[:4000]}

Extract the following data points if present. If a field is not mentioned, write "not found".

Return as JSON with these exact keys:
{{
  "pricing": "pricing tiers or plans mentioned",
  "key_features": ["list of key product features"],
  "weaknesses": ["customer complaints or product limitations"],
  "differentiators": ["unique selling points"],
  "market_position": "their market positioning statement",
  "customer_segments": ["who they target"],
  "recent_news": ["any recent launches or announcements"],
  "sentiment": "overall customer sentiment: positive/neutral/negative"
}}

Return ONLY the JSON. No explanation.
"""
    try:
        response_text = await generate_gemini_content(prompt)
        import json
        text = response_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        extracted = json.loads(text.strip())
    except Exception as e:
        extracted = {"raw": response_text if 'response_text' in locals() else f"extraction failed: {str(e)}"}

    return {
        "agent": AGENT_NAME,
        "topic": request.topic,
        "extracted": extracted,
        "payment_verified": x_402_payment_proof,
        "cost": PRICE
    }


@app.get("/health")
async def health():
    return {"agent": AGENT_NAME, "wallet": AGENT_WALLET, "price": PRICE, "status": "ok"}

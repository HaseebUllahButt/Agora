"""
agents/web_search_agent.py — Port 8001

Web Search Agent: searches the web using Tavily API.
Price: $0.0005 USDC per call (Nanopayment).

x402 flow:
  POST /search           → 402 Payment Required
  POST /search + proof   → 200 + search results
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from tavily import TavilyClient

from shared.x402_middleware import verify_payment_on_chain, make_402_response

load_dotenv()

app = FastAPI(title="Agora — Web Search Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_NAME    = "Web Search Agent"
AGENT_WALLET  = os.getenv("WEB_SEARCH_AGENT_ADDRESS")
PRICE         = "0.0005"

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


@app.post("/search")
async def search(
    request: SearchRequest,
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

    # ── Step 3: Execute the task ──────────────────────────────────────────────
    try:
        response = tavily.search(
            query=request.query,
            max_results=request.max_results,
            include_answer=True,
            include_raw_content=False
        )
        results = response.get("results", [])
        return {
            "agent": AGENT_NAME,
            "query": request.query,
            "results": results,
            "result_count": len(results),
            "payment_verified": x_402_payment_proof,
            "cost": PRICE
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
async def health():
    return {"agent": AGENT_NAME, "wallet": AGENT_WALLET, "price": PRICE, "status": "ok"}

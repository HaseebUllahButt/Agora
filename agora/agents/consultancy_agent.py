"""
agents/consultancy_agent.py — Port 8006

Consultancy Agent: turns full pipeline outputs into practical consulting advice.
Price: $0.0015 USDC per call (Nanopayment).

Activated only when user enables consultancy advice in the frontend.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from shared.x402_middleware import verify_payment_on_chain, make_402_response
from shared.llm import generate_gemini_content

load_dotenv()

app = FastAPI(title="Agora — Consultancy Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_NAME = "Consultancy Agent"
AGENT_WALLET = os.getenv("CONSULTANCY_AGENT_ADDRESS")
PRICE = "0.0015"


class ConsultancyRequest(BaseModel):
    topic: str
    company_context: dict = {}
    search_results: list = []
    summaries: list = []
    analyst_recommendations: Optional[dict] = None
    formatted_report: Optional[dict] = None


@app.post("/consult")
async def consult(
    request: ConsultancyRequest,
    x_402_payment_proof: str = Header(None)
):
    if not x_402_payment_proof:
        return make_402_response(AGENT_WALLET, PRICE, AGENT_NAME)

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

    summaries_text = "\n\n".join([
        s.get("summary", str(s)) for s in request.summaries
    ]) if request.summaries else "No summaries provided"

    recommendations_text = ""
    if request.analyst_recommendations:
        recommendations_text = request.analyst_recommendations.get("recommendations", "")

    report_text = ""
    if request.formatted_report:
        report_text = request.formatted_report.get("report_markdown", "")

    prompt = f"""You are a senior management consultant.

Create consultancy advice for this company using the full research context.

Topic: {request.topic}
Company context: {request.company_context}

Research summaries:
{summaries_text[:5000]}

Analyst recommendations:
{recommendations_text[:3500]}

Formatted report:
{report_text[:3500]}

Return concise markdown with exactly these sections:

## Consultancy Advice
- 5 practical, high-impact moves for the next 90 days

## Execution Plan (30-60-90)
- Week-by-week practical milestones

## KPIs to Track
- 6 measurable metrics with target direction

## Risks & Mitigations
- Top 3 execution risks and concrete mitigations

Keep it direct and practical for operators.
"""

    try:
        advice = await generate_gemini_content(prompt)
    except Exception as e:
        advice = f"## Consultancy Advice\n\nGeneration failed: {str(e)}"

    return {
        "agent": AGENT_NAME,
        "topic": request.topic,
        "consultancy_advice": advice.strip(),
        "payment_verified": x_402_payment_proof,
        "cost": PRICE
    }


@app.get("/health")
async def health():
    return {"agent": AGENT_NAME, "wallet": AGENT_WALLET, "price": PRICE, "status": "ok"}

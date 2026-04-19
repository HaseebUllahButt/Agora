"""
agents/analyst_agent.py — Port 8004

Analyst Agent: generates 5 actionable strategic recommendations.
Price: $0.002 USDC per call (Nanopayment — highest value agent).

This is the most expensive agent because it does the most valuable work:
turning raw research findings into specific, company-tailored strategy.
Every recommendation must directly reference the research evidence.
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

app = FastAPI(title="Agora — Analyst Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AGENT_NAME    = "Analyst Agent"
AGENT_WALLET  = os.getenv("ANALYST_AGENT_ADDRESS")
PRICE         = "0.002"


class CompanyContext(BaseModel):
    company_size: str = "startup"
    stage: str = "seed"
    main_strength: str = "engineering"
    main_weakness: str = "distribution"
    budget: str = "limited"
    target_market: str = "SMBs"


class AnalystRequest(BaseModel):
    research_findings: str
    company_context: dict


@app.post("/analyze")
async def analyze(
    request: AnalystRequest,
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

    # ── Step 3: Generate strategic recommendations with Gemini ────────────────
    ctx = request.company_context
    prompt = f"""You are a senior business strategist at a top-tier consulting firm.

You have been given competitive intelligence research and a client's company profile.
Your job is to deliver 5 specific, actionable strategic recommendations.

━━━ RESEARCH FINDINGS ━━━
{request.research_findings[:5000]}

━━━ CLIENT COMPANY PROFILE ━━━
Company Size:    {ctx.get('company_size', 'startup')}
Growth Stage:    {ctx.get('stage', 'seed')}
Main Strength:   {ctx.get('main_strength', 'engineering')}
Main Weakness:   {ctx.get('main_weakness', 'distribution')}
Budget Level:    {ctx.get('budget', 'limited')}
Target Market:   {ctx.get('target_market', 'SMBs')}

━━━ YOUR DELIVERABLE ━━━
Write exactly 5 strategic recommendations. For each:

## Recommendation [N]: [Short Title]

**The Action:** What specifically should they do?

**Why Now:** What from the research makes this urgent or relevant?

**Evidence:** Quote or reference the specific research finding that supports this.

**30-Day Step:** One concrete action they can take in the next 30 days.

**Resource Required:** Time, money, or headcount estimate.

---

Rules:
- Every recommendation must cite specific evidence from the research
- No generic advice ("improve your product" is not acceptable)
- Tailor every recommendation to their specific stage and budget
- Be contrarian where the data supports it
"""
    try:
        recommendations = await generate_gemini_content(prompt)
        recommendations = recommendations.strip()
    except Exception as e:
        recommendations = f"Analysis failed: {str(e)}"

    return {
        "agent": AGENT_NAME,
        "recommendations": recommendations,
        "company_context": request.company_context,
        "based_on_findings": request.research_findings[:300] + "...",
        "payment_verified": x_402_payment_proof,
        "cost": PRICE
    }


@app.get("/health")
async def health():
    return {"agent": AGENT_NAME, "wallet": AGENT_WALLET, "price": PRICE, "status": "ok"}

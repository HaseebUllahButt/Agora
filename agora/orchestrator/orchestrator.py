"""
orchestrator/orchestrator.py

The brain of Agora. Orchestrates the multi-agent research pipeline.

Flow per loop:
  1. TaskDecomposer generates a unique search query for this loop
  2. WebSearchAgent finds raw information (x402: pay → verify → work)
  3. ExtractorAgent pulls structured insights from raw results
  4. Every 3 loops: SummarizerAgent condenses findings
  Final:
  5. AnalystAgent generates 5 actionable strategic recommendations
  6. FormatterAgent produces the final polished markdown report

Every agent call follows the x402 pattern:
  - Initial call → 402 Payment Required
  - Orchestrator pays via Circle Nanopayments (send_usdc)
  - Retry with X-402-Payment-Proof header
  - Output validated by Gemini before accepting
  - Budget checked before every payment

WebSocket events emitted throughout for real-time frontend updates.
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

from shared.circle_client import send_usdc
from shared.budget_guardian import BudgetGuardian
from shared.output_validator import validate_output
from shared.agent_registry import get_active_agents
from orchestrator.audit_logger import AuditLogger
from orchestrator.task_decomposer import decompose_task

load_dotenv()

ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_ADDRESS")


async def call_agent_with_payment(
    agent_key: str,
    payload: dict,
    budget: BudgetGuardian,
    audit: AuditLogger,
    websocket_emit=None,
    max_retries: int = 2
) -> dict | None:
    """
    Call an agent using the full x402 Nanopayment flow.

    Steps:
      1. POST to agent endpoint (expect 402)
      2. Pay agent wallet via Circle Nanopayments
      3. Retry POST with X-402-Payment-Proof header
      4. Validate output quality with Gemini
      5. Return result or None on failure

    Args:
        agent_key:       Registry key for the agent to hire
        payload:         JSON payload for the agent request
        budget:          BudgetGuardian for this pipeline run
        audit:           AuditLogger for this pipeline run
        websocket_emit:  Async callable to broadcast events to frontend
        max_retries:     How many times to retry on failure

    Returns:
        Validated agent response dict, or None if all attempts failed
    """
    registry = get_active_agents()
    if agent_key not in registry:
        audit.log(f"Agent '{agent_key}' not found in registry — skipping")
        return None

    agent = registry[agent_key]
    price = float(agent["price_per_call"])
    endpoint = agent["endpoint"]
    wallet_address = agent["wallet_address"]
    route = agent.get("route", agent_key.replace("_", "-"))

    if not budget.can_spend(price):
        audit.log(f"BUDGET GUARD: Cannot hire {agent['name']} (${price}) — insufficient funds")
        return None

    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(max_retries):
            try:
                # ── Step 1: Initial call, expect 402 ─────────────────────────
                response = await client.post(
                    f"{endpoint}/{route}",
                    json=payload,
                    timeout=6.0
                )

                if response.status_code not in (402, 200):
                    audit.log(
                        f"Unexpected {response.status_code} from {agent['name']} "
                        f"attempt {attempt + 1}"
                    )
                    await asyncio.sleep(min(0.8 * (attempt + 1), 2.0))
                    continue

                # Agent returned 200 without payment (e.g. during testing)
                if response.status_code == 200:
                    result = response.json()
                    is_valid, reason = await validate_output(agent["name"], str(payload), result)
                    if is_valid:
                        return result
                    audit.log(f"FRAUD: {agent['name']} pre-payment 200 invalid: {reason}")
                    continue

                # ── Step 2: Pay the agent via Circle Nanopayments ─────────────
                audit.log(f"Paying {agent['name']} ${price} USDC (Nanopayment)")
                if websocket_emit:
                    await websocket_emit({
                        "event": "payment_initiated",
                        "agent": agent["name"],
                        "amount": price,
                        "attempt": attempt + 1
                    })

                tx = await send_usdc(
                    from_wallet_address=ORCHESTRATOR_ADDRESS,
                    to_wallet_address=wallet_address,
                    amount=str(price)
                )

                budget.record_spend(price, tx["tx_hash"], agent["name"], str(payload)[:100])
                audit.log(
                    f"Nanopayment confirmed: {tx['tx_hash']}",
                    {"explorer": tx["explorer_url"], "amount": price}
                )

                if websocket_emit:
                    await websocket_emit({
                        "event": "payment_confirmed",
                        "agent": agent["name"],
                        "tx_hash": tx["tx_hash"],
                        "explorer_url": tx["explorer_url"],
                        "amount": price,
                        "remaining_budget": budget.remaining()
                    })

                # ── Step 3: Retry with payment proof ─────────────────────────
                retry_response = await client.post(
                    f"{endpoint}/{route}",
                    json=payload,
                    headers={"x-402-payment-proof": tx["tx_hash"]},
                    timeout=60.0
                )

                if retry_response.status_code != 200:
                    raise Exception(
                        f"Agent returned {retry_response.status_code} after payment"
                    )

                result = retry_response.json()

                # ── Step 4: Validate output quality ───────────────────────────
                is_valid, validation_reason = await validate_output(
                    agent_name=agent["name"],
                    task=str(payload)[:200],
                    output=result
                )

                if not is_valid:
                    if validation_reason.lower().startswith("validation service error"):
                        audit.log(
                            f"VALIDATOR UNAVAILABLE: {validation_reason}"
                        )
                        if websocket_emit:
                            await websocket_emit({
                                "event": "validator_unavailable",
                                "agent": agent["name"],
                                "reason": validation_reason,
                                "tx_hash": tx["tx_hash"]
                            })
                        return {
                            "fatal_error": "validation_service_unavailable",
                            "reason": validation_reason,
                            "agent": agent["name"]
                        }

                    audit.log(
                        f"FRAUD DETECTED from {agent['name']}: {validation_reason}"
                    )
                    if websocket_emit:
                        await websocket_emit({
                            "event": "fraud_detected",
                            "agent": agent["name"],
                            "reason": validation_reason,
                            "tx_hash": tx["tx_hash"]
                        })
                    # Do NOT record this as a valid spend — agent stole payment
                    continue

                audit.log(f"Output validated from {agent['name']}")
                return result

            except Exception as e:
                audit.log(f"Error calling {agent_key} attempt {attempt + 1}: {str(e)}")
                await asyncio.sleep(min(0.8 * (attempt + 1), 2.0))

    audit.log(f"FAILED: {agent_key} did not return valid output after {max_retries} attempts")
    return None


async def run_agora_pipeline(
    topic: str,
    user_budget: float,
    company_context: dict,
    task_type: str = "competitive_intelligence",
    include_consultancy: bool = False,
    websocket_emit=None
) -> dict:
    """
    Run the full Agora multi-agent research pipeline.

    Budget determines depth — more USDC = more loops = more agent calls.
    Loops are capped at 25 to prevent runaway spending.
    Each loop uses TaskDecomposer for a unique search query.
    Summarizer fires every 3 loops to consolidate findings.
    Analyst and Formatter run once at the end.

    Args:
        topic:            Research topic (e.g. "Stripe competitor analysis")
        user_budget:      Maximum USDC to spend across all agents
        company_context:  User's company details for analyst recommendations
        task_type:        Research type tag for audit log
        websocket_emit:   Async callable to broadcast to frontend

    Returns:
        dict with report, recommendations, audit_log, budget_summary, transaction_count
    """
    budget = BudgetGuardian(total_budget=user_budget)
    audit = AuditLogger()
    findings_so_far: list[str] = []

    audit.log(f"Pipeline start: {topic}")
    audit.log(f"Budget: ${user_budget} USDC | Task type: {task_type}")

    # Calculate loop budget — reserve budget for analyst + formatter at the end
    reserved = float("0.002") + float("0.0005")  # analyst + formatter
    loop_cost = float("0.0005") + float("0.0005")  # search + extract per loop
    summarize_cost = float("0.001")               # summarizer every 3 loops

    available = user_budget - reserved
    # Rough estimate: 2/3 of loops trigger summarizer
    effective_cost_per_loop = loop_cost + (summarize_cost / 3)
    max_loops = max(1, int(available / effective_cost_per_loop))
    loops = min(max_loops, 12)

    audit.log(f"Research loops planned: {loops}")
    if websocket_emit:
        await websocket_emit({
            "event": "pipeline_started",
            "topic": topic,
            "budget": user_budget,
            "planned_loops": loops
        })

    all_search_results = []
    all_extracted = []
    all_summaries = []

    def _is_fatal(result: dict | None) -> bool:
        return bool(result and result.get("fatal_error") == "validation_service_unavailable")

    # ── Research loops ─────────────────────────────────────────────────────────
    for i in range(loops):
        if budget.is_exhausted():
            audit.log(f"Budget exhausted at loop {i} — stopping early")
            break

        loop_label = f"Loop {i + 1}/{loops}"
        audit.log(f"{loop_label}: Decomposing query")

        # Get unique search query for this loop
        query = await decompose_task(
            topic=topic,
            company_context=company_context,
            budget=user_budget,
            loop_index=i,
            findings_so_far=findings_so_far
        )
        audit.log(f"{loop_label}: Query → {query}")

        if websocket_emit:
            await websocket_emit({
                "event": "loop_start",
                "loop": i + 1,
                "query": query
            })

        # Web search
        search_result = await call_agent_with_payment(
            "web_search",
            {"query": query, "max_results": 3},
            budget, audit, websocket_emit
        )
        if _is_fatal(search_result):
            audit.log("Stopping pipeline early: validator service unavailable")
            break
        if search_result:
            new_results = search_result.get("results", [])
            all_search_results.extend(new_results)
            audit.log(f"{loop_label}: Got {len(new_results)} search results")

        # Extract structured data from latest results
        if all_search_results and budget.can_spend(float("0.0005")):
            latest = all_search_results[-3:]
            extract_result = await call_agent_with_payment(
                "extractor",
                {"text": str(latest), "topic": topic},
                budget, audit, websocket_emit
            )
            if _is_fatal(extract_result):
                audit.log("Stopping pipeline early: validator service unavailable")
                break
            if extract_result:
                all_extracted.append(extract_result)

        # Summarize every 3 loops to consolidate findings
        if i % 3 == 2 and all_extracted and budget.can_spend(float("0.001")):
            summary_result = await call_agent_with_payment(
                "summarizer",
                {"extractions": all_extracted[-9:], "topic": topic},
                budget, audit, websocket_emit
            )
            if _is_fatal(summary_result):
                audit.log("Stopping pipeline early: validator service unavailable")
                break
            if summary_result:
                summary_text = summary_result.get("summary", "")
                all_summaries.append(summary_result)
                if summary_text:
                    findings_so_far.append(summary_text)
                audit.log(f"{loop_label}: Summarized {len(all_extracted)} extractions")

    # ── Analyst — runs once after all research ─────────────────────────────────
    analyst_result = None
    if all_summaries or all_extracted:
        research_text = "\n\n".join([
            s.get("summary", str(s)) for s in all_summaries
        ]) if all_summaries else str(all_extracted[:5])

        if budget.can_spend(float("0.002")):
            analyst_result = await call_agent_with_payment(
                "analyst",
                {
                    "research_findings": research_text,
                    "company_context": company_context
                },
                budget, audit, websocket_emit
            )
            if _is_fatal(analyst_result):
                audit.log("Stopping pipeline before analyst output: validator service unavailable")
                analyst_result = None
            if analyst_result:
                audit.log("Analyst recommendations generated")
        else:
            audit.log("Skipping analyst — insufficient budget")
    else:
        audit.log("Skipping analyst — no research findings available")

    # ── Formatter — final polished report ─────────────────────────────────────
    formatter_result = None
    if budget.can_spend(float("0.0005")):
        formatter_result = await call_agent_with_payment(
            "formatter",
            {
                "topic": topic,
                "company_context": company_context,
                "search_results": all_search_results[:20],
                "summaries": all_summaries,
                "analyst_recommendations": analyst_result,
                "budget_summary": budget.summary()
            },
            budget, audit, websocket_emit
        )
        if _is_fatal(formatter_result):
            audit.log("Skipping formatter output: validator service unavailable")
            formatter_result = None
        if formatter_result:
            audit.log("Final report formatted")
    else:
        audit.log("Skipping formatter — insufficient budget")

    # ── Consultancy — optional expert advice (checkbox-controlled) ───────────
    consultancy_result = None
    if include_consultancy:
        if budget.can_spend(float("0.0015")):
            consultancy_result = await call_agent_with_payment(
                "consultancy",
                {
                    "topic": topic,
                    "company_context": company_context,
                    "search_results": all_search_results[:20],
                    "summaries": all_summaries,
                    "analyst_recommendations": analyst_result,
                    "formatted_report": formatter_result,
                },
                budget, audit, websocket_emit
            )
            if _is_fatal(consultancy_result):
                audit.log("Skipping consultancy output: validator service unavailable")
                consultancy_result = None
            if consultancy_result:
                audit.log("Consultancy advice generated")
        else:
            audit.log("Skipping consultancy — insufficient budget")
    else:
        audit.log("Skipping consultancy — not requested")

    # ── Pipeline complete ──────────────────────────────────────────────────────
    tx_count = len(budget.transactions)
    audit.log(
        f"Pipeline complete: {tx_count} Nanopayments, "
        f"${budget.spent:.4f} spent, ${budget.remaining():.4f} remaining"
    )

    if websocket_emit:
        await websocket_emit({
            "event": "pipeline_complete",
            "transaction_count": tx_count,
            "total_spent": budget.spent,
            "remaining": budget.remaining()
        })

    no_successful_paid_calls = tx_count == 0 and formatter_result is None and analyst_result is None
    error_message = (
        "No paid agent calls succeeded. Check GROQ_API_KEY for validation and Circle wallet/payment configuration."
        if no_successful_paid_calls else None
    )

    return {
        "topic": topic,
        "task_type": task_type,
        "report": formatter_result,
        "recommendations": analyst_result,
        "consultancy_advice": consultancy_result,
        "summaries": all_summaries,
        "audit_log": audit.get_log(),
        "budget_summary": budget.summary(),
        "transaction_count": tx_count,
        "loops_completed": min(loops, len(all_search_results)),
        "status": "failed" if no_successful_paid_calls else "ok",
        "error": error_message,
    }

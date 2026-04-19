"""
orchestrator/task_decomposer.py

Intelligent research query generator — the brain that makes loops non-repetitive.

Without this, a 25-loop pipeline would search "Stripe competitor analysis" 25 times.
With this, each loop gets a unique angle targeted at what's still unknown.

The decomposer uses Gemini to:
  1. Rotate through standard competitive intelligence angles (pricing, features,
     reviews, news, market position, customer segments)
  2. Analyse what's already been found and target gaps in the research
  3. Tailor queries to the user's company context (stage, strength, weakness)
  4. Generate queries that produce varied, complementary search results
"""

from dotenv import load_dotenv

from shared.llm import generate_gemini_content

load_dotenv()

# Standard competitive intelligence angles cycled in order for the first loops
_BASE_ANGLES = [
    "market overview, key players, and market size",
    "pricing models, plans, and packaging strategy",
    "customer reviews, complaints, and satisfaction scores",
    "recent product launches, feature updates, and roadmap signals",
    "enterprise vs SMB customer segments and go-to-market strategy",
    "funding history, investors, and growth trajectory",
    "technical architecture, integrations, and developer experience",
    "marketing strategy, brand positioning, and content approach",
    "weaknesses, limitations, and areas of customer dissatisfaction",
    "vs alternatives comparison and switching costs",
]


async def decompose_task(
    topic: str,
    company_context: dict,
    budget: float,
    loop_index: int,
    findings_so_far: list[str]
) -> str:
    """
    Generate a unique, targeted search query for a specific research loop.

    Each loop gets a different angle so 25 loops produce 25 varied datasets
    rather than 25 repetitive searches on the same query.

    Args:
        topic:            The research topic (e.g. "Stripe competitor analysis")
        company_context:  User's company info — stage, strength, weakness, market
        budget:           Total pipeline budget (used to set depth expectations)
        loop_index:       0-based loop number (used to cycle angles)
        findings_so_far:  List of summary strings already gathered this pipeline

    Returns:
        A specific search query string for this loop
    """
    # For the first N loops, cycle through standard angles deterministically
    # so we always cover fundamentals before going deeper
    if loop_index < len(_BASE_ANGLES):
        base_angle = _BASE_ANGLES[loop_index]

        # Tailor the base angle to company context
        company_size = company_context.get("company_size", "startup")
        target_market = company_context.get("target_market", "SMBs")

        return f"{topic}: {base_angle} — focus on {company_size} relevance and {target_market} segment"

    # For later loops, use Gemini to identify gaps in what's been found
    if not findings_so_far:
        return f"{topic} deep dive loop {loop_index}"

    recent_findings = "\n".join(findings_so_far[-5:])  # last 5 summaries

    prompt = f"""You are a competitive intelligence researcher.

Research topic: {topic}
Company context:
  - Size: {company_context.get('company_size', 'startup')}
  - Stage: {company_context.get('stage', 'seed')}
  - Main strength: {company_context.get('main_strength', 'engineering')}
  - Main weakness: {company_context.get('main_weakness', 'distribution')}
  - Target market: {company_context.get('target_market', 'SMBs')}

We have already gathered the following research findings:
{recent_findings}

Based on what we already know, what specific aspect of this topic has NOT been 
covered yet that would be most valuable to research next?

Generate ONE specific search query (10-15 words max) that:
1. Targets an information gap in the research so far
2. Is directly relevant to the company's situation
3. Has not been searched in any variation already

Reply with ONLY the search query — no explanation, no quotes.
"""
    try:
        response_text = await generate_gemini_content(prompt)
        query = response_text.strip().strip('"\'')
        return query if query else f"{topic} competitive analysis loop {loop_index}"
    except Exception:
        # Fallback to simple rotation if Gemini fails
        angle_idx = loop_index % len(_BASE_ANGLES)
        return f"{topic}: {_BASE_ANGLES[angle_idx]}"

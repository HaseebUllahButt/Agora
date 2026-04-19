"""
shared/agent_registry.py

Agora Agent Registry

This is the core of Agora's open protocol vision.
Any developer can register a new specialist agent here
with their wallet address and price per call.
The orchestrator discovers agents dynamically at runtime.
No orchestrator code changes needed to add new agents.
This is how the agentic labor market stays open and extensible.

── How it works ──────────────────────────────────────────────────────────────

Each entry in AGENT_REGISTRY maps a capability key to a config dict:
  - name:            Human-readable agent name
  - endpoint:        Base URL of the running FastAPI agent server
  - wallet_address:  Arc testnet address where this agent receives payment
  - wallet_id:       Circle wallet ID for the agent
  - price_per_call:  USDC cost per successful task (string, e.g. "0.0005")
  - capability:      Description Gemini uses to decide which agent to hire
  - active:          Set to False to disable an agent without removing it

── Adding a new agent ────────────────────────────────────────────────────────

1. Deploy your FastAPI agent server following the x402 pattern
2. Create a Circle wallet for it and fund it
3. Add an entry to AGENT_REGISTRY with your endpoint and wallet info
4. The orchestrator will automatically discover and hire it

No changes to orchestrator.py required.

── Economic model ────────────────────────────────────────────────────────────

Agents compete on price and capability. Lower price_per_call → more hirings.
Higher quality (validated by output_validator) → preserved reputation.
Malicious or low-quality agents get flagged and avoided automatically.
"""

import os
from dotenv import load_dotenv

load_dotenv()

AGENT_REGISTRY: dict[str, dict] = {
    "web_search": {
        "name": "Web Search Agent",
        "endpoint": "http://localhost:8001",
        "wallet_address": os.getenv("WEB_SEARCH_AGENT_ADDRESS"),
        "wallet_id": os.getenv("WEB_SEARCH_AGENT_ID"),
        "price_per_call": "0.0005",
        "capability": (
            "Searches the web for URLs, summaries, and raw information on a topic. "
            "Returns structured search results with titles, URLs, and excerpts."
        ),
        "route": "search",
        "active": True
    },
    "extractor": {
        "name": "Extractor Agent",
        "endpoint": "http://localhost:8002",
        "wallet_address": os.getenv("EXTRACTOR_AGENT_ADDRESS"),
        "wallet_id": os.getenv("EXTRACTOR_AGENT_ID"),
        "price_per_call": "0.0005",
        "capability": (
            "Extracts structured data points from raw text: pricing, features, "
            "weaknesses, differentiators, customer sentiment, and market position."
        ),
        "route": "extract",
        "active": True
    },
    "summarizer": {
        "name": "Summarizer Agent",
        "endpoint": "http://localhost:8003",
        "wallet_address": os.getenv("SUMMARIZER_AGENT_ADDRESS"),
        "wallet_id": os.getenv("SUMMARIZER_AGENT_ID"),
        "price_per_call": "0.001",
        "capability": (
            "Condenses large volumes of extracted research data into concise, "
            "high-signal key findings paragraphs suitable for strategic analysis."
        ),
        "route": "summarize",
        "active": True
    },
    "analyst": {
        "name": "Analyst Agent",
        "endpoint": "http://localhost:8004",
        "wallet_address": os.getenv("ANALYST_AGENT_ADDRESS"),
        "wallet_id": os.getenv("ANALYST_AGENT_ID"),
        "price_per_call": "0.002",
        "capability": (
            "Generates 5 specific, actionable strategic recommendations based on "
            "competitive intelligence research and the user's company context. "
            "Every recommendation directly references evidence from the research."
        ),
        "route": "analyze",
        "active": True
    },
    "formatter": {
        "name": "Formatter Agent",
        "endpoint": "http://localhost:8005",
        "wallet_address": os.getenv("FORMATTER_AGENT_ADDRESS"),
        "wallet_id": os.getenv("FORMATTER_AGENT_ID"),
        "price_per_call": "0.0005",
        "capability": (
            "Formats all pipeline outputs into a polished, well-structured "
            "competitive intelligence report in markdown format."
        ),
        "route": "format",
        "active": True
    }
}


def get_active_agents() -> dict[str, dict]:
    """Return only agents marked as active."""
    return {k: v for k, v in AGENT_REGISTRY.items() if v.get("active", False)}


def register_agent(key: str, config: dict) -> None:
    """
    Register a new agent at runtime.

    Allows new specialist agents to join Agora without touching
    orchestrator logic. The orchestrator will discover this agent
    on the next pipeline run.

    Args:
        key:    Unique capability key (e.g. "sentiment_analyst")
        config: Dict matching the AGENT_REGISTRY schema above
    """
    AGENT_REGISTRY[key] = config


def deregister_agent(key: str) -> None:
    """Remove an agent from the registry (e.g. after fraud detection)."""
    if key in AGENT_REGISTRY:
        AGENT_REGISTRY[key]["active"] = False


def get_agent(key: str) -> dict | None:
    """Get a single agent config by key."""
    return AGENT_REGISTRY.get(key)

"""
sdk/__init__.py

Agora SDK — Provider and Consumer APIs for the agent economy.

Usage:

  PROVIDER SIDE:
  ──────────────
  
  from agora.sdk import pay_for
  
  @pay_for(price=0.001, category="data")
  def search(query: str) -> str:
    return f"Results for: {query}"
  
  # Service is automatically registered and monetized
  
  
  CONSUMER SIDE:
  ──────────────
  
  from agora.sdk import AgoraClient
  
  client = AgoraClient(
    wallet_address="0x...",
    private_key="0x...",
    budget_usdc=5.0
  )
  
  # Query registry
  results = client.search_services("web search")
  
  # Call a service
  response = await client.call_service(
    service_id="web_search",
    params={"query": "AI agents"}
  )
  
  # Money is handled automatically
"""

from .provider import pay_for, get_service_registry
from .consumer import AgoraClient
from .agent import Agent
from .exceptions import BudgetExceeded
from .wallet import generate_wallet, get_address_from_private_key, WalletConfig

__all__ = [
    "pay_for",
    "get_service_registry",
    "AgoraClient",
    "Agent",
    "BudgetExceeded",
    "generate_wallet",
    "get_address_from_private_key",
    "WalletConfig",
]

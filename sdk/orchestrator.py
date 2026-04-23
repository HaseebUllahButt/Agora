import os
import json
import logging
from typing import List, Dict, Any, Optional
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.agent import Agent
from sdk.consumer import AgoraClient

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    The 'Guide' Agent for the Agora Marketplace.
    
    Takes a natural language task, decomposes it, searches the marketplace 
    for providers, and executes a chain of autonomous purchases.
    """
    
    def __init__(self, agent: Agent, budget_usdc: float = 1.0):
        """
        Initialize the orchestrator with an agent (for identity/wallet) 
        and a session budget.
        """
        self.agent = agent
        self.budget_usdc = budget_usdc
        self.client = agent.create_client(budget_usdc=budget_usdc)
        self.history = []
        
        # Marketplace API URL
        self.api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")

    def plan_task(self, task_description: str) -> List[Dict]:
        """
        [Autonomous Planning Engine] Decomposes natural language tasks into 
        required market capabilities. In a production environment, this uses 
        Gemini/GPT-4 for multi-agent reasoning.
        """
        # Simple rule-based decomposition for demo purposes
        plan = []
        task_lower = task_description.lower()
        
        if "search" in task_lower or "find" in task_lower:
            plan.append({"capability": "web_search", "description": "Search for news/data"})
        
        if "summarize" in task_lower or "analysis" in task_lower or "analyze" in task_lower:
            plan.append({"capability": "analysis", "description": "Summarize or analyze data"})
            
        if not plan:
            # Default fallback
            plan.append({"capability": "data", "description": "General data request"})
            
        return plan

    async def execute(self, task_description: str) -> Dict:
        """
        Autonomous execution flow:
        Plan -> Discover -> Purchase -> Result Chain
        """
        logger.info(f"Orchestrating task: {task_description}")
        
        # 1. Plan
        required_steps = self.plan_task(task_description)
        last_result = task_description # Feed task info into first agent
        results_chain = []
        
        # 2. Execution Loop
        for step in required_steps:
            capability = step["capability"]
            
            # 2a. Discover
            import requests
            search_resp = requests.get(f"{self.api_url}/services/search?q={capability}")
            providers = search_resp.json()
            
            if not providers:
                logger.warning(f"No providers found for capability: {capability}")
                continue
                
            # Pick best provider (highest reputation, then lowest price)
            # Sorting already handled by API, so pick first
            best_provider = providers[0]
            
            logger.info(f"Selected provider: {best_provider['name']} (${best_provider['price']})")
            
            # 2b. Purchase & Execute
            # Note: client.purchase_service handles Circle settlement
            purchase_resp = self.client.purchase_service(
                seller_id=best_provider["provider_id"].split("_")[0] if "_" in best_provider["provider_id"] else best_provider["name"], # Mock logic for demo
                service_name=best_provider["name"],
                params={"input": last_result}
            )
            
            if "error" in purchase_resp:
                logger.error(f"Purchase failed: {purchase_resp['error']}")
                break
                
            last_result = purchase_resp.get("result", "No result returned")
            results_chain.append({
                "step": capability,
                "provider": best_provider["name"],
                "cost": best_provider["price"],
                "result": last_result
            })
            
        return {
            "task": task_description,
            "final_answer": last_result,
            "steps": results_chain,
            "total_spent": self.client.spent_usdc,
            "remaining_budget": self.client.available_budget()
        }

if __name__ == "__main__":
    print("Agora Orchestrator Module Ready")

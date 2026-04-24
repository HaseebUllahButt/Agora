import json
import os
import requests
from typing import Dict, Any, Optional
from .buyer import Buyer

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

class SmartBuyer(Buyer):
    """An autonomous buyer that uses an LLM to decide what to purchase based on a goal."""
    
    def __init__(self, agent_id: str, budget: float = 0.0, **kwargs):
        super().__init__(agent_id, budget=budget, **kwargs)
        self.role = "smart_consumer"

    def _think(self, prompt: str) -> str:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return '{"error": "GROQ_API_KEY not set in environment"}'
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 512,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"⚠️ LLM Error: {e}")
            return "{}"

    def execute_mission(self, task_description: str, task_params: dict) -> Optional[Dict[str, Any]]:
        """
        1. Search the registry for relevant services
        2. Send the search results + task to Groq
        3. LLM picks the best service and explains why
        4. Execute the purchase
        5. Return result + LLM reasoning
        """
        print(f"\n🧠 {self.name} is planning: '{task_description}'")
        
        # Search the marketplace (get all for the LLM to review)
        results = self.client.search("")
        
        if not results:
            print("❌ No relevant services found on the marketplace.")
            return None
            
        services_json = json.dumps([
            {
                "service_id": r.get("id", r.get("provider_id")), 
                "name": r.get("name"), 
                "description": r.get("description"), 
                "price": r.get("price_usdc", r.get("price", 0))
            } for r in results
        ], indent=2)
        
        prompt = f"""
        You are an autonomous AI agent with a budget of {self.budget} USDC.
        Your task is: "{task_description}"
        
        Here are the available services on the Agora marketplace:
        {services_json}
        
        Pick the single best service to accomplish this task.
        You must respond in valid JSON format exactly like this:
        {{
            "service_id": "the_chosen_id",
            "reason": "Brief explanation of why this service is the best fit."
        }}
        """
        
        print("🤔 Consulting LLM for decision...")
        decision_str = self._think(prompt)
        print(f"   [Debug] LLM Response: {decision_str}")
        print(f"   [Debug] Services JSON sent to LLM: {services_json}")
        
        try:
            decision = json.loads(decision_str)
            chosen_id = decision.get("service_id")
            reason = decision.get("reason", "No reason provided")
        except json.JSONDecodeError:
            print("❌ LLM returned invalid JSON.")
            return None
            
        if not chosen_id:
            print("❌ LLM could not decide on a service.")
            return None
            
        chosen_service = next((s for s in results if s.get("id", s.get("provider_id")) == chosen_id), None)
        if not chosen_service:
            print(f"❌ LLM picked an invalid service ID: {chosen_id}")
            return None
            
        price = chosen_service.get("price_usdc", chosen_service.get("price", 0))
        print(f"✅ Decision made: Purchasing '{chosen_service.get('name')}'")
        print(f"   Reason: {reason}")
        print(f"   Cost: {price} USDC")
        
        if price > self.budget:
            print(f"❌ Cannot afford service. Price ({price}) > Budget ({self.budget})")
            return None
            
        print("💸 Initiating payment...")
        seller_id = chosen_service.get("agent_id")
        service_name = chosen_service.get("name")
        tx_result = self.client.purchase_service(
            seller_id=seller_id, 
            service_name=service_name, 
            params=task_params
        )
        
        return {
            "decision": decision,
            "transaction": tx_result
        }

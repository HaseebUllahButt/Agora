import json
import os
import time
import requests
from typing import Dict, Any, Optional
from .buyer import Buyer

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# gemini-2.5-flash: stable, best price-performance, high rate limits on free tier
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class SmartBuyer(Buyer):
    """An autonomous buyer that uses Gemini 2.0 Flash to decide what to purchase based on a goal."""

    def __init__(self, agent_id: str, budget: float = 0.0, **kwargs):
        super().__init__(agent_id, budget=budget, **kwargs)
        self.role = "smart_consumer"

    def _think(self, prompt: str) -> str:
        """Call Gemini 2.0 Flash to reason about the best service to purchase.
        
        Free tier limits:
          - 15 RPM (we do ~0.5 RPM in frenzy due to sleep(2) between txs)
          - 1,500 RPD
          - 1M TPM
        Includes exponential backoff for 429 rate-limit errors.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return '{"error": "GEMINI_API_KEY not set in environment"}'

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
                "responseMimeType": "application/json"
            }
        }

        url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"

        for attempt in range(4):  # up to 4 attempts with backoff
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)

                if response.status_code == 429:
                    wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                    print(f"   ⏳ Gemini rate limit hit, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            except requests.exceptions.Timeout:
                print(f"   ⚠️ Gemini timeout (attempt {attempt + 1}/4)")
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"   ⚠️ Gemini Error: {e}")
                return "{}"

        return "{}"

    def execute_mission(self, task_description: str, task_params: dict) -> Optional[Dict[str, Any]]:
        """
        1. Search the registry for relevant services
        2. Send the search results + task to Gemini 2.0 Flash
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

        print("🤔 Consulting Gemini 2.5 Flash for decision...")
        decision_str = self._think(prompt)
        print(f"   [Debug] Gemini Response: {decision_str}")
        print(f"   [Debug] Services JSON sent to Gemini: {services_json}")

        try:
            decision = json.loads(decision_str)
            chosen_id = decision.get("service_id")
            reason = decision.get("reason", "No reason provided")
        except json.JSONDecodeError:
            print("❌ Gemini returned invalid JSON.")
            return None

        # If Gemini was rate-limited and returned {}, fall back to keyword matching
        if not chosen_id:
            print("   ⚠️  Gemini rate-limited. Using keyword fallback...")
            chosen_id, reason = self._fallback_pick(task_description, results)

        if not chosen_id:
            print("❌ Could not decide on a service (Gemini + fallback both failed).")
            return None

        chosen_service = next((s for s in results if s.get("id", s.get("provider_id")) == chosen_id), None)
        if not chosen_service:
            print(f"❌ Gemini picked an invalid service ID: {chosen_id}")
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

    def _fallback_pick(self, task_description: str, services: list):
        """Keyword-based fallback when Gemini is rate-limited.
        Maps common task keywords to known service name fragments.
        Returns (service_id, reason) tuple.
        """
        task_lower = task_description.lower()
        keyword_map = [
            (["sentiment", "mood", "emotion", "feeling", "review"], "moodreader"),
            (["summar", "condense", "article", "tldr", "brief", "report"], "summarybot"),
            (["csv", "format", "convert", "table", "spreadsheet", "json"], "datawizard"),
            (["hash", "sha", "md5", "encrypt", "checksum", "secure"], "cryptoutils"),
            (["tagline", "slogan", "marketing", "copy", "ad ", "brand", "app"], "adcopyai"),
        ]
        for keywords, name_fragment in keyword_map:
            if any(kw in task_lower for kw in keywords):
                match = next(
                    (s for s in services if name_fragment in s.get("name", "").lower()),
                    None
                )
                if match:
                    sid = match.get("id", match.get("provider_id"))
                    return sid, f"Keyword fallback: matched '{name_fragment}' from task description."
        # Last resort: pick cheapest service
        cheapest = min(services, key=lambda s: s.get("price_usdc", s.get("price", 999)))
        sid = cheapest.get("id", cheapest.get("provider_id"))
        return sid, "Keyword fallback: selected cheapest available service."

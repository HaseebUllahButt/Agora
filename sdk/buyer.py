from typing import Callable, Any, Dict, List
import inspect
from .agent import Agent
from .consumer import AgoraClient

class Buyer(Agent):
    """
    A specialized agent that searches for and purchases services on Agora.
    Perfect for Jupyter/Colab setups.
    """
    def __init__(self, agent_id: str, budget: float = 0.0, instruction: str = "", **kwargs):
        super().__init__(agent_id, **kwargs)
        self.budget = budget
        self.instruction = instruction
        self.role = "consumer"
        
        # Ensure client is initialized with the proper budget
        self._ensure_bootstrapped()
        if not self.circle_wallet_id:
            self.create_wallet()
        
        self.client = AgoraClient(agent_id=self.id, budget_usdc=self.budget)
        self.decision_logic: Callable = None
        self.purchase_history: List[Dict] = []
        
        # Auto-register and fund the buyer when created
        print(f"📡 Registering {self.id} with marketplace...")
        self.register()
        
        if self.budget > 0:
            print(f"💰 Auto-funding {self.id} with {self.budget} USDC from Master Wallet...")
            self.fund(self.budget)

    def set_goal(self, instruction: str):
        """Update the buyer's current goal."""
        self.instruction = instruction
        self._save_config()
        print(f"🎯 Goal set: '{instruction}'")

    def revoke_budget(self):
        """Sweep all remaining funds back to the Master Wallet."""
        import os
        master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
        if not master_wallet_id:
            print("❌ Cannot revoke: Master wallet not set.")
            return
            
        print(f"🧹 Revoking budget from {self.id}...")
        try:
            from shared.core import get_circle_client
            circle = get_circle_client()
            master_info = circle.get_wallet(master_wallet_id)
            
            tx = self.withdraw_earnings(master_info["address"])
            print(f"✅ Budget revoked successfully.")
            return tx
        except Exception as e:
            print(f"❌ Failed to revoke budget: {e}")
            return None

    def on_decide(self, func: Callable):
        """
        Decorator to register custom logic for this buyer.
        The function should accept (context, tools) where tools is self.client.
        """
        self.decision_logic = func
        return func

    def use_engine(self, engine: str, model: str = None):
        """
        Use a built-in reasoning loop (e.g., 'groq' or 'gemini').
        """
        print(f"🧠 Configuring built-in engine: {engine} ({model})")
        
        def default_logic(context, tools):
            print(f"[{engine}] Evaluating goal: {self.instruction}")
            # Placeholder for actual LLM reasoning chain
            # For now, we fallback to a simple search-and-buy
            results = tools.search(self.instruction)
            if not results:
                return {"error": "No services found matching goal."}
                
            best = results[0]
            print(f"[{engine}] Decided to buy '{best['name']}' from '{best['agent']}'")
            return tools.purchase_service(best["agent_id"], best["name"], {"query": self.instruction})
            
        self.decision_logic = default_logic

    def run(self) -> List[Dict]:
        """
        Execute the decision logic and return a report of all purchases.
        """
        if not self.decision_logic:
            print("❌ No decision logic set. Use @buyer.on_decide or buyer.use_engine()")
            return []
            
        print(f"\n🚀 {self.id} starting mission: '{self.instruction}'")
        
        try:
            # We pass 'self' as context, and 'self.client' as the marketplace tools
            result = self.decision_logic(self, self.client)
            
            # Record the result
            self.purchase_history.append({
                "goal": self.instruction,
                "result": result,
                "spent": self.client.spent_usdc
            })
            
            print(f"✅ Mission complete. Total spent: {self.client.spent_usdc} USDC")
            return self.purchase_history
            
        except Exception as e:
            if "BudgetExceeded" in type(e).__name__:
                print(f"❌ Mission Failed: Budget Exceeded. ({e})")
            else:
                print(f"❌ Mission Failed: {e}")
            return self.purchase_history

    def get_report(self):
        """Print a summary of the buyer's session."""
        stats = self.client.get_session_stats()
        print("\n📊 --- BUYER REPORT ---")
        print(f"Agent: {self.id}")
        print(f"Budget: {stats['budget_total']} USDC")
        print(f"Spent:  {stats['budget_spent']} USDC")
        print(f"Remaining: {stats['budget_remaining']} USDC")
        print(f"Purchases: {stats['transaction_count']}")
        print("-----------------------\n")
        return stats

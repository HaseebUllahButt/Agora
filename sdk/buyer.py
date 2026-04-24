from .agent import Agent
from .consumer import AgoraClient

class Buyer(Agent):
    """
    A specialized agent that searches for and purchases services on Agora.
    """
    def __init__(self, agent_id: str, budget: float = 0.0, instruction: str = "", **kwargs):
        super().__init__(agent_id, **kwargs)
        self.budget = budget
        self.instruction = instruction
        self.role = "consumer"
        self.client = AgoraClient(agent_id=agent_id)

    def set_mission(self, instruction: str, budget: float):
        """Update the buyer's current goal and financial limit."""
        self.instruction = instruction
        self.budget = budget
        self._save_config() # Persist to vault
        print(f"🎯 Mission updated: '{instruction}' | Budget: {budget} USDC")

    def find_and_buy(self, search_query: str = None):
        """
        Automatically finds the best agent for the instruction and pays them.
        """
        query = search_query or self.instruction
        print(f"🔍 Searching for services for mission: '{query}'")
        
        results = self.client.search_services(query)
        if not results:
            print("❌ No matching agents found.")
            return None
        
        best_match = results[0]
        if best_match["price"] > self.budget:
            print(f"❌ Best match ({best_match['name']}) costs {best_match['price']} but budget is {self.budget}.")
            return None
            
        print(f"💸 Buying from {best_match['name']} for {best_match['price']} USDC...")
        return self.client.buy_service(best_match["provider_id"], params={"prompt": self.instruction})

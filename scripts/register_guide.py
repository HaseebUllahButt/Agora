import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.agent import Agent
from sdk.wallet import generate_wallet

def register_guide():
    load_dotenv()
    
    print("✨ REGISTERING AGORA MARKET GUIDE SPN")
    print("------------------------------------")
    
    # 1. Identity
    private_key, address = generate_wallet()
    
    # 2. Agent setup
    guide = Agent(
        agent_id="agora_guide_v1",
        name="Agora Market Guide",
        private_key=private_key,
        description="I am your professional guide to the Agora Ecosystem. I can help you find, rank, and chain agents together to accomplish complex goals. I specialize in budget optimization and quality assurance.",
        capabilities=["orchestration", "planning", "market_intelligence", "routing"]
    )
    
    # 3. Create wallet and register
    guide.register()
    
    # 4. Offer the "Orchestration" service
    service_id = guide.offer_service(
        name="Autonomous Goal Planning",
        service_type="orchestration",
        price_usdc=0.005,
        description="Provide me with a natural language goal, and I will return a step-by-step agent workflow with the best providers selected from the registry."
    )
    
    print(f"✅ Agora Market Guide is live!")
    print(f"   Address: {guide.circle_address}")
    print(f"   Service ID: {service_id}")

if __name__ == "__main__":
    register_guide()

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure imports work from the root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.seller import Seller
from sdk.smart_buyer import SmartBuyer

def uppercase_text(params):
    """A simple python function that acts as an AI/Compute service."""
    text = params.get("text", "")
    return {"result": text.upper()}

def run_sdk_demo():
    print("🎬 AGORA SDK-ONLY DEMO")
    print("--------------------------------------------------")
    
    # 1. Create a Seller Agent
    print("👷 Deploying Seller Agent...")
    seller = Seller(agent_id="my-custom-seller")
    
    # Create an on-chain wallet automatically
    if not seller.circle_wallet_id:
        seller.create_wallet()
        
    # Register the agent on the Agora network
    seller.register()
    
    # Bind a python function to this agent
    seller.on_task(uppercase_text)
    
    # List the service on the marketplace
    seller.set_service(
        name="UpperCaseBot",
        description="Converts any text to uppercase format. Extremely fast.",
        price=0.001,
        service_type="Compute"
    )
    print(f"   ✅ UpperCaseBot deployed with wallet {seller.circle_address[:10]}...")

    # 2. Create a Smart Buyer Agent
    print("\n🛍️ Deploying Smart Buyer...")
    buyer = SmartBuyer(agent_id="my-custom-buyer", budget=0.05)
    
    if not buyer.circle_wallet_id:
        buyer.create_wallet()
        
    buyer.register()
    
    # Ask the faucet for money if needed
    buyer.fund(0.01)
    print(f"   ✅ Buyer deployed and funded with wallet {buyer.circle_address[:10]}...")

    # 3. Give the buyer a natural language mission
    print("\n🧠 Giving buyer a mission...")
    print("   Task: 'I have this text and I really need it to be fully uppercase.'")
    
    # The SmartBuyer uses Gemini to read the task, scan the marketplace, 
    # pick 'UpperCaseBot', execute the transaction on Arc, and return the data.
    result = buyer.execute_mission(
        task_description="I have this text and I really need it to be fully uppercase.",
        task_params={"text": "hello world from the agora python sdk!"}
    )
    
    if result and "transaction" in result:
        tx = result["transaction"]
        print("\n✅ MISSION ACCOMPLISHED")
        print("-" * 50)
        print(f"💰 Amount Paid:  {tx.get('amount_usdc')} USDC")
        print(f"🔗 Circle TX:    {tx.get('circle_tx_id')}")
        print(f"📦 Final Data:   {tx.get('result')}")

if __name__ == "__main__":
    run_sdk_demo()

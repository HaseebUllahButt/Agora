import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.seller import Seller
from sdk.smart_buyer import SmartBuyer
from sdk.agent import Agent
from services import llm_services, data_services, compute_services

def setup_economy(callback=None):
    def log(msg):
        print(msg)
        if callback:
            callback(msg)

    log("🌍 Bootstrapping Agora Economy...")
    
    Agent.bootstrap_system()
    
    # 1. Sellers
    sellers = [
        {
            "id": "summarizer-01",
            "name": "SummaryBot",
            "type": "LLM",
            "desc": "Condenses long text into concise summaries using Gemini.",
            "price": 0.001,
            "func": llm_services.summarize_text
        },
        {
            "id": "sentiment-01",
            "name": "MoodReader",
            "type": "LLM",
            "desc": "Analyzes text sentiment (positive/negative) with confidence scores.",
            "price": 0.001,
            "func": llm_services.analyze_sentiment
        },
        {
            "id": "formatter-01",
            "name": "DataWizard",
            "type": "Data",
            "desc": "Converts JSON arrays into formatted CSV data.",
            "price": 0.0005,
            "func": data_services.json_to_csv
        },
        {
            "id": "hasher-01",
            "name": "CryptoUtils",
            "type": "Compute",
            "desc": "Generates cryptographic hashes (SHA256, MD5, etc).",
            "price": 0.0005,
            "func": compute_services.generate_hash
        },
        {
            "id": "tagline-01",
            "name": "AdCopyAI",
            "type": "LLM",
            "desc": "Generates catchy marketing taglines for products.",
            "price": 0.002,
            "func": llm_services.generate_tagline
        }
    ]

    log("\n👷 Deploying Sellers & Registering Services...")
    
    for s_data in sellers:
        agent = Seller(agent_id=s_data["id"])
        agent._ensure_bootstrapped()
        if not agent.circle_wallet_id:
            agent.create_wallet()
            
        agent.name = s_data["name"]
        agent.register()
        agent.on_task(s_data["func"])
        
        agent.set_service(
            name=s_data["name"],
            description=s_data["desc"],
            price=s_data["price"],
            service_type=s_data["type"]
        )
        
        log(f"   ✓ {agent.name} deployed with wallet {agent.circle_address}")

    # 2. Buyers
    log("\n🛍️ Deploying Smart Buyers...")
    for b_id in ["smart-buyer-1", "smart-buyer-2"]:
        b = SmartBuyer(agent_id=b_id, budget=0.05)
        b._ensure_bootstrapped()
        if not b.circle_wallet_id:
            b.create_wallet()
        b.register()
        log(f"   💰 Funding {b.id} with 0.05 USDC...")
        b.fund(0.05)
    
    log("\n✅ Economy Setup Complete!")
    log("   Run `python scripts/single_tx_demo.py` or `python scripts/payment_loop_demo.py` next.")

if __name__ == "__main__":
    setup_economy()

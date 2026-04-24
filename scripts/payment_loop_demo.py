import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.smart_buyer import SmartBuyer
from sdk.seller import Seller
from scripts.setup_demo_economy import setup_economy

def run_loop_demo():
    print("\n" + "="*50)
    print("🔄 AGORA PAYMENT LOOP DEMO (A -> B -> C)")
    print("="*50)
    
    agent_a = SmartBuyer("smart-buyer-1", budget=0.05)
    agent_b = Seller("summarizer-01") 
    
    text_to_process = "Autonomous agents represent the next evolution of digital commerce. By utilizing sub-cent, gas-free payments on networks like Arc, AI systems can dynamically discover and hire each other to complete complex pipelines without human intervention."
    
    print(f"\n[1] Agent A (Coordinator) is buying Summarization from Agent B...")
    result_a = agent_a.execute_mission(
        "Summarize the provided text about autonomous agents.", 
        {"text": text_to_process}
    )
    
    if not result_a or "error" in result_a.get("transaction", {}):
        print("❌ Step 1 failed. Aborting loop.")
        return
        
    tx_a = result_a["transaction"]
    summary = tx_a.get("result", {}).get("summary", "")
    
    print(f"✅ Step 1 Complete. Agent B earned {tx_a['amount']} USDC.")
    print(f"   Summary Output: '{summary}'")
    
    print(f"\n[2] Agent B (Summarizer) is using earnings to buy Tagline from Agent C...")
    from sdk.consumer import AgoraClient
    client_b = AgoraClient(agent_id=agent_b.id)
    
    task_params_b = {
        "product": "Agora Marketplace",
        "audience": "AI developers"
    }
    
    tx_b = client_b.purchase_service(
        seller_id="tagline-01",
        service_name="AdCopyAI",
        params=task_params_b
    )
    
    if "error" in tx_b:
        print(f"❌ Step 2 failed: {tx_b['error']}")
        return
        
    tagline = tx_b.get("result", {}).get("tagline", "")
    
    print(f"✅ Step 2 Complete. Agent C earned {tx_b['amount']} USDC.")
    print(f"   Tagline Output: '{tagline}'")
    
    print("\n" + "="*50)
    print("🏆 PAYMENT LOOP SUCCESSFUL")
    print("="*50)
    print("Money flowed:")
    print(f"  Agent A -> Agent B (TX: {tx_a.get('transaction_id')})")
    print(f"  Agent B -> Agent C (TX: {tx_b.get('transaction_id')})")
    
    seller_addr = tx_b.get('seller_address')
    if seller_addr:
        from shared.constants import ARC_EXPLORER_BASE
        print(f"📊 Seller C Revenue: {ARC_EXPLORER_BASE}/address/{seller_addr}")
        
    print(f"Agent C can now auto-sweep earnings to treasury.")
    
    print("-" * 50)
    master_wallet = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if master_wallet:
        balance = agent_a.circle_client.get_balance(master_wallet)
        print(f"🏦 Master Funder Wallet Remaining Balance: {balance} USDC")

if __name__ == "__main__":
    setup_economy()
    run_loop_demo()

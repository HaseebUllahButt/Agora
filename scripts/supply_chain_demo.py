import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.smart_buyer import SmartBuyer
from shared.constants import ARC_EXPLORER_BASE

def log(msg):
    print(msg)

def run_supply_chain_demo():
    print("\n🚀 [DEBUG] EXECUTING NESTED SUPPLY CHAIN DEMO")
    log("\n" + "="*50)
    log("🎬 AGORA NESTED AGENT SUPPLY CHAIN DEMO")
    log("="*50)
    log("Scenario: A user requests a 'Formatted Deep Sentiment Report'.")
    log("Agent A (Orchestrator) accepts the task, but needs to:")
    log("  1. Buy Sentiment Analysis from Agent B.")
    log("  2. Buy JSON Formatting from Agent C.")
    log("This proves true Agent-to-Agent nested commerce.")
    log("-" * 50)
    
    from scripts.setup_demo_economy import setup_economy
    setup_economy()

    # The Orchestrator is funded by the master wallet
    orchestrator = SmartBuyer("orchestrator-agent", budget=0.05)
    log("   💰 Funding orchestrator-agent with 0.05 USDC...")
    orchestrator.fund(0.05)
    orchestrator.register()
    
    raw_data = "The new arc network is incredibly fast and has completely changed our business model. However, the onboarding process is still slightly confusing."
    
    log("\n[1] Orchestrator realizes it needs sentiment analysis. Buying from 'MoodReader'...")
    # Orchestrator buys sentiment analysis
    sentiment_result = orchestrator.execute_mission(
        "I need sentiment analysis for some text.",
        {"text": raw_data}
    )
    
    if not sentiment_result or "error" in sentiment_result.get("transaction", {}):
        log("❌ Failed to get sentiment analysis.")
        return
        
    tx1 = sentiment_result["transaction"]
    log(f"   ✅ Paid {tx1.get('amount_usdc')} USDC to {tx1.get('seller_agent')}")
    log(f"   [Result]: {json.dumps(tx1.get('result'))}")
    
    log("\n[2] Orchestrator realizes it needs to format the result into CSV. Buying from 'DataWizard'...")
    # Orchestrator buys formatting
    format_result = orchestrator.execute_mission(
        "I need to convert this JSON sentiment data into CSV format.",
        {"data": [tx1.get('result')]}
    )
    
    if not format_result or "error" in format_result.get("transaction", {}):
        log("❌ Failed to format data.")
        return
        
    tx2 = format_result["transaction"]
    log(f"   ✅ Paid {tx2.get('amount_usdc')} USDC to {tx2.get('seller_agent')}")
    log(f"   [Result]: {json.dumps(tx2.get('result'))}")
    
    log("\n[3] Orchestrator combines the results and returns to User.")
    log("="*50)
    log("🏆 NESTED SUPPLY CHAIN COMPLETE")
    log(f"   Total Spend by Orchestrator: {tx1.get('amount_usdc') + tx2.get('amount_usdc')} USDC")
    log("   Final Output:")
    log(f"   {tx2.get('result', {}).get('csv', 'Error generating CSV')}")
    log("="*50)
    
    log("\nTo view the on-chain settlements, check the Arc Explorer for:")
    
    # Poll for TX 1
    circle_tx1 = tx1.get('circle_tx_id', tx1.get('transaction_id'))
    arc_hash1 = tx1.get('arc_tx_hash')
    if not arc_hash1 and circle_tx1 and not str(circle_tx1).startswith("DEMO"):
        log("⏳ Waiting for TX 1 blockchain confirmation...")
        for i in range(40):
            try:
                status = orchestrator.circle_client.get_transaction_status(circle_tx1)
                if status.get("txHash"):
                    arc_hash1 = status["txHash"]
                    log("   ✅ TX 1 Confirmed!")
                    break
            except Exception: pass
            time.sleep(2)
            
    # Poll for TX 2
    circle_tx2 = tx2.get('circle_tx_id', tx2.get('transaction_id'))
    arc_hash2 = tx2.get('arc_tx_hash')
    if not arc_hash2 and circle_tx2 and not str(circle_tx2).startswith("DEMO"):
        log("⏳ Waiting for TX 2 blockchain confirmation...")
        for i in range(40):
            try:
                status = orchestrator.circle_client.get_transaction_status(circle_tx2)
                if status.get("txHash"):
                    arc_hash2 = status["txHash"]
                    log("   ✅ TX 2 Confirmed!")
                    break
            except Exception: pass
            time.sleep(2)

    log(f"   TX 1 Hash: {arc_hash1 or 'Pending...'}")
    log(f"   TX 2 Hash: {arc_hash2 or 'Pending...'}")


if __name__ == "__main__":
    run_supply_chain_demo()

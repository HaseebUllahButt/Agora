import os
import sys
import time
import random
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sdk as agora_sdk
from shared.core import ARC_EXPLORER_BASE

def run_frenzy(callback=None, skip_setup=False):
    def log(msg):
        print(msg)
        if callback:
            callback(msg)

    log("\n" + "="*50)
    log("🔥 AGORA ECONOMY STRESS TEST (FRENZY DEMO)")
    log("="*50)

    # 1. Bootstrap
    agora_sdk.bootstrap()

    # 2. Setup Sellers
    log("\n👷 Setting up Sellers...")

    # Text Summarizer
    s1 = agora_sdk.Seller(agent_id="summarizer-01", price=0.001)
    s1.set_service("SummaryBot", "Condenses long text.", 0.001, "LLM")
    @s1.on_task
    def handle_summary(payload):
        text = payload.get("text", "")
        return {"summary": f"Summary of: {text[:50]}..."}
    s1.publish()

    # Sentiment Analyzer
    s2 = agora_sdk.Seller(agent_id="sentiment-01", price=0.001)
    s2.set_service("MoodReader", "Analyzes sentiment.", 0.001, "LLM")
    @s2.on_task
    def handle_sentiment(payload):
        return {"sentiment": "positive", "confidence": 0.92}
    s2.publish()

    # 3. Setup Buyers
    log("\n🛍️ Setting up Buyers...")
    b1 = agora_sdk.Buyer(agent_id="frenzy-buyer-1", budget=0.05)
    b2 = agora_sdk.Buyer(agent_id="frenzy-buyer-2", budget=0.05)

    queries = [
        ("SummaryBot", "summarizer-01", {"text": "A new AI model was released today."}),
        ("MoodReader", "sentiment-01", {"text": "I absolutely love programmable wallets!"})
    ]

    log(f"\n🚀 STARTING BURST OF TRANSACTIONS...")
    start_time = time.time()

    total_tx = 0
    for i in range(10):
        buyer = random.choice([b1, b2])
        service_name, seller_id, params = random.choice(queries)

        log(f"\n[{i+1}/10] {buyer.id} is hiring '{service_name}'...")

        try:
            tx = buyer.client.purchase_service(seller_id, service_name, params)
            if isinstance(tx, dict) and "error" in tx:
                log(f"   ❌ Payment Failed: {tx['error']}")
            elif isinstance(tx, dict):
                total_tx += 1
                result_data = tx.get("result", {})
                log(f"   ✅ TX: {tx.get('transaction_id')} | Seller: {tx.get('seller_agent')}")
                log(f"   📦 Result: {json.dumps(result_data)}")
            else:
                log(f"   ⚠️ Could not complete purchase.")
        except Exception as e:
            log(f"   ⚠️ System Error: {e}")

        time.sleep(1.0)

    duration = time.time() - start_time
    log("\n" + "="*45)
    log(f"🏁 FRENZY COMPLETE!")
    log(f"📊 Total Transactions: {total_tx}")
    log(f"⏱️ Time Elapsed: {duration:.2f} seconds")
    log(f"💰 Traditional Gas Saved: ${total_tx * 2.95:.2f}")
    log(f"💎 Arc Native Settlement Cost: $0.00")
    log("="*45)

    master_wallet = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if master_wallet:
        try:
            from shared.core import ARC_TESTNET_USDC
            log(f"🏦 Master Funder Balance: {b1.circle_client.get_balance(master_wallet)} USDC")
        except:
            pass

    # Cleanup
    b1.revoke_budget()
    b2.revoke_budget()
    s1.unpublish()
    s2.unpublish()

if __name__ == "__main__":
    run_frenzy()

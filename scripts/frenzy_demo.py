import os
import sys
import time
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.smart_buyer import SmartBuyer
from scripts.setup_demo_economy import setup_economy
from shared.constants import ARC_EXPLORER_BASE

def run_frenzy(callback=None, skip_setup=False):
    def log(msg):
        print(msg)
        if callback:
            callback(msg)

    log("🔥 AGORA ECONOMY STRESS TEST: 50+ TRANSACTIONS 🔥")
    log("-----------------------------------------------")
    
    if not skip_setup:
        setup_economy()
    
    b1 = SmartBuyer("smart-buyer-1", budget=0.05)
    b2 = SmartBuyer("smart-buyer-2", budget=0.05)

    log("⏳ Waiting for faucet transactions to settle on Arc...")
    time.sleep(1.5)

    total_tx = 0
    estimated_l1_gas_saved = 0
    
    queries = [
        ("Summarize this news article", {"text": "A new AI model was released today that is 10x faster."}),
        ("Check sentiment of this review", {"text": "I absolutely love the new programmable wallets feature!"}),
        ("Convert this data to CSV", {"data": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}),
        ("Generate a hash for this data", {"input": "secure_password_123", "algorithm": "sha256"}),
        ("Write a tagline for my app", {"product": "AI Crypto Wallet", "audience": "gen-z"})
    ]

    log(f"\n🚀 STARTING 50-TRANSACTION BURST...")
    start_time = time.time()

    for i in range(50):
        buyer = random.choice([b1, b2])
        task_desc, params = random.choice(queries)
        
        log(f"\n[{i+1}/50] {buyer.id} is hiring for: '{task_desc}'...")
        
        try:
            result = buyer.execute_mission(task_desc, params)
            if result and "transaction" in result:
                tx = result["transaction"]
                if "error" in tx:
                    log(f"   ❌ Payment Failed: {tx['error']}")
                else:
                    total_tx += 1
                    estimated_l1_gas_saved += 2.95 # Average ETH L1 ERC-20 transfer gas cost
                    full_tx_id = tx.get('transaction_id', 'SUCCESS')
                    seller_addr = tx.get('seller_address', '0x...')
                    circle_tx = tx.get('circle_tx_id', full_tx_id)
                    arc_hash = tx.get('arc_tx_hash')
                    
                    if not arc_hash and circle_tx and not str(circle_tx).startswith("DEMO"):
                        for poll in range(15):
                            try:
                                status = buyer.circle_client.get_transaction_status(circle_tx)
                                if status.get("txHash"):
                                    arc_hash = status["txHash"]
                                    break
                            except Exception: pass
                            time.sleep(1)
                            
                    if arc_hash:
                        log(f"   ✅ Verified on Arc! Hash: {arc_hash[:15]}... -> Seller: {seller_addr[:10]}...")
                    else:
                        log(f"   ✅ Payment Sent! TX: {full_tx_id} -> Seller: {seller_addr[:10]}... (Pending Hash)")
                        
                    result_data = tx.get("result", {})
                    import json
                    log(f"   📦 Result: {json.dumps(result_data)}")
            else:
                log(f"   ⚠️ Buyer could not complete mission.")
        except Exception as e:
            log(f"   ⚠️ System Error: {e}")
            
        time.sleep(2.0)

    duration = time.time() - start_time
    log("\n" + "="*45)
    log(f"🏁 FRENZY COMPLETE!")
    log(f"📊 Total AI Transactions: {total_tx}")
    log(f"⏱️  Time Elapsed: {duration:.2f} seconds")
    log(f"💰 Traditional Gas Saved: ${estimated_l1_gas_saved:.2f}")
    log(f"💎 Arc Native Settlement Cost: $0.00")
    log("="*45)
    
    master_wallet = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if master_wallet:
        # Get the master address to show the ledger link
        try:
            master_addr = b1.circle_client.get_wallet_address(master_wallet)
            from shared.constants import ARC_TESTNET_USDC
            log(f"🏦 Master Funder Balance: {b1.circle_client.get_balance(master_wallet)} USDC")
            log(f"🔗 Master Funder Ledger:  {ARC_EXPLORER_BASE}/address/{master_addr}")
            log(f"🌎 Global USDC Activity:  {ARC_EXPLORER_BASE}/token/{ARC_TESTNET_USDC}")
        except:
            pass
            
    log("\n🌍 LIVE DASHBOARD: http://localhost:8000")
    log("🔗 Check the Circle Dashboard to see the Live Settlement Feed!")

if __name__ == "__main__":
    run_frenzy()

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk.smart_buyer import SmartBuyer
from shared.constants import ARC_EXPLORER_BASE
import json

def run_single_demo(callback=None, skip_setup=False):
    print("\n🚀 [DEBUG] EXECUTING LATEST VERSION OF SINGLE_TX_DEMO.PY")
    def log(msg):
        print(msg)
        if callback:
            callback(msg)

    log("\n" + "="*50)
    log("🎬 AGORA SINGLE TRANSACTION DEMO")
    log("="*50)
    
    if not skip_setup:
        from scripts.setup_demo_economy import setup_economy
        setup_economy()

    buyer = SmartBuyer("smart-buyer-1", budget=0.05)
    
    task_desc = "I have a long financial report and I need a concise summary."
    task_params = {
        "text": "Circle announced today that Programmable Wallets are now live on the Arc network. This allows developers to build high-frequency, sub-cent microtransaction networks without worrying about gas fees. The integration is expected to drastically increase the viability of autonomous AI agents paying each other for micro-services."
    }
    
    result = buyer.execute_mission(task_desc, task_params)
    
    if result and "transaction" in result:
        tx = result["transaction"]
        if "error" in tx:
            log(f"\n❌ Transaction Failed: {tx['error']}")
        else:
            log("\n✅ TRANSACTION SUCCESSFUL")
            log("-" * 50)
            log(f"💰 Amount Paid:      {tx.get('amount_usdc')} USDC")
            
            circle_tx = tx.get('circle_tx_id', tx.get('transaction_id'))
            log(f"🔗 Circle TX ID:     {circle_tx}")
            
            arc_hash = tx.get('arc_tx_hash')
            if not arc_hash and circle_tx and not str(circle_tx).startswith("DEMO"):
                log("⏳ Waiting for Arc blockchain confirmation...")
                import time
                for i in range(40):
                    try:
                        # Log a dot without newline for the console, but the callback might need full lines
                        # For the dashboard, we'll just log a 'Checking...' message periodically
                        if i % 5 == 0: log(f"   ... polling blockchain (attempt {i+1}/40)")
                        status = buyer.circle_client.get_transaction_status(circle_tx)
                        if status.get("txHash"):
                            arc_hash = status["txHash"]
                            log(" ✅ Confirmed!")
                            break
                    except Exception as e:
                        # Print the error instead of silently swallowing it
                        log(f"   [ERROR] Polling failed: {e}")
                    time.sleep(2)
                if not arc_hash: log(" ⏳ Taking longer than usual, checking explorer manually...")

            if arc_hash:
                log(f"🌐 Explorer Link:    {ARC_EXPLORER_BASE}/tx/{arc_hash}")
            elif circle_tx and not str(circle_tx).startswith("DEMO"):
                log(f"🌐 Explorer Link:    Pending (Check Circle Dashboard)")
            
            log(f"🔏 Proof Hash:       {tx.get('erc8004_proof', 'N/A')}")
            
            seller_id = tx.get('seller_agent')
            seller_addr = tx.get('seller_address')
            if seller_id and seller_addr:
                log(f"👤 Seller Agent:     {seller_id} ({seller_addr[:10]}...)")
                log(f"📊 Seller Revenue:   {ARC_EXPLORER_BASE}/address/{seller_addr}")
            
            log("\n📦 SERVICE RESULT:")
            result_data = tx.get("result", {})
            log(json.dumps(result_data, indent=2))
            log("-" * 50)
            
            master_wallet = os.getenv("CIRCLE_MASTER_WALLET_ID")
            if master_wallet:
                try:
                    balance = buyer.circle_client.get_balance(master_wallet)
                    log(f"🏦 Master Funder Wallet Remaining Balance: {balance} USDC")
                except: pass
                
            log("To view this transaction, open your Circle Developer Console.")

if __name__ == "__main__":
    run_single_demo()

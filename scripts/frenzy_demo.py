import os
import sys
import time
import random

# Ensure we can import from the root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agora_sdk as agora

def run_frenzy():
    print("🔥 AGORA ECONOMY STRESS TEST: 50+ TRANSACTIONS 🔥")
    print("-----------------------------------------------")
    
    # 1. Setup Infrastructure
    agora.bootstrap_circle()
    
    # 2. Create the Labor Force (Sellers)
    print("\n👷 Deploying Sellers...")
    s1 = agora.create_seller("worker-1", name="Alpha Dev", service="Code Review", price=0.001, service_type="CODE")
    s2 = agora.create_seller("worker-2", name="Beta Data", service="Data Cleaning", price=0.002, service_type="DATA")
    s3 = agora.create_seller("worker-3", name="Gamma News", service="Trend Analysis", price=0.001, service_type="RESEARCH")

    # 3. Create the Consumers (Buyers)
    print("\n🛍️  Deploying Buyers...")
    
    # Pre-check Master Wallet Balance
    master_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
    if master_id:
        master_id = master_id.strip("'\"")
        try:
            # Get balance of master to ensure we can actually run the demo
            from shared.circle_client import get_circle_client
            client = get_circle_client()
            balance = client.get_balance(master_id)
            print(f"💰 Master Wallet Balance: {balance} USDC")
            
            if balance < 0.20: # 0.08 * 2 buyers + some buffer
                print("❌ ERROR: Master Wallet balance is too low for this demo.")
                print("   Please fund your Master Wallet at faucet.circle.com")
                print("   Exiting to prevent failed transactions.")
                return
        except Exception as e:
            print(f"⚠️  Could not verify Master balance: {e}")

    b1 = agora.create_buyer("buyer-1", budget=0.08)
    b2 = agora.create_buyer("buyer-2", budget=0.08)

    if not master_id:
        print("\n⚠️  WARNING: CIRCLE_MASTER_WALLET_ID not set. Buyers may have 0 balance.")
        print("   If transactions fail with 402 errors, fund the buyers at faucet.circle.com")
    else:
        print("⏳ Waiting for faucet transactions to settle on Arc...")
        time.sleep(1.5)

    # 4. The Frenzy Loop
    total_tx = 0
    estimated_l1_gas_saved = 0
    queries = ["Fix my code", "Clean this CSV", "What is trending?", "Audit contract", "Research Arc"]

    print(f"\n🚀 STARTING 60-TRANSACTION BURST...")
    start_time = time.time()

    for i in range(60):
        buyer = random.choice([b1, b2])
        query = random.choice(queries)
        
        print(f"[{i+1}/60] {buyer.id} is hiring for: '{query}'...")
        
        try:
            results = agora.search(query)
            if results:
                target = results[0]
                seller_id = target["agent_id"]
                service_name = target["name"]
            else:
                # FALLBACK: If Search index is still warming up, pick a live seller directly
                target_seller = random.choice([s1, s2, s3])
                seller_id = target_seller.id
                service_name = target_seller.service_name

            tx = buyer.client.buy_service(
                seller_id, 
                service_name=service_name, 
                params={"q": query}
            )
            
            if "error" in tx:
                print(f"   ❌ Payment Failed: {tx['error']}")
            else:
                total_tx += 1
                estimated_l1_gas_saved += 0.50
                full_tx_id = tx.get('transaction_id', 'SUCCESS')
                print(f"   ✅ Payment Confirmed! TX: {full_tx_id}")
        except Exception as e:
            print(f"   ⚠️ System Error: {e}")
        
        # Let it rip! No sleep timer.

    duration = time.time() - start_time
    print("\n" + "="*45)
    print(f"🏁 FRENZY COMPLETE!")
    print(f"📊 Total AI Transactions: {total_tx}")
    print(f"⏱️  Time Elapsed: {duration:.2f} seconds")
    print(f"💰 Traditional Gas Saved: ${estimated_l1_gas_saved:.2f}")
    print(f"💎 Arc Native Settlement Cost: $0.00")
    print("="*45)
    print("\n🔗 Check the Dashboard to see the Live Settlement Feed!")
    print("💡 TIP: Verify these are real transactions by checking your")
    print("   Circle Developer Console at https://console.circle.com")

if __name__ == "__main__":
    run_frenzy()

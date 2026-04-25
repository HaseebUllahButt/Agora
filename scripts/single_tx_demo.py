import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sdk as agora_sdk
from shared.core import ARC_EXPLORER_BASE

def run_single_demo(callback=None, skip_setup=False):
    def log(msg):
        print(msg)
        if callback:
            callback(msg)

    log("\n" + "="*50)
    log("🎬 AGORA COLAB-STYLE DEMO (SINGLE TX)")
    log("="*50)

    # 1. Bootstrap the ecosystem (Uses existing .env if present)
    agora_sdk.bootstrap()
    log("\n--------------------------------------------------")

    # 2. Set up a Seller
    log("👷 Setting up the Seller...")
    seller = agora_sdk.Seller(agent_id="math-genius-01", price=0.01)

    @seller.on_task
    def calculate_math(payload):
        equation = payload.get("equation", "0")
        log(f"[Seller] Received equation: {equation}")
        try:
            # Safe evaluation for demo
            allowed_chars = set("0123456789+-*/() .")
            if set(equation).issubset(allowed_chars):
                answer = eval(equation)
                return {"answer": answer, "equation": equation}
            return {"error": "Invalid characters in equation"}
        except Exception as e:
            return {"error": str(e)}

    seller.set_service(
        name="Math Genius",
        description="I solve math equations.",
        price=0.01,
        service_type="compute"
    )
    seller.publish()

    log("\n--------------------------------------------------")

    # 3. Set up a Buyer
    log("🛍️  Setting up the Buyer...")
    buyer = agora_sdk.Buyer(agent_id="student-bot-01", budget=0.05)
    buyer.set_goal("Solve 25 * 4")

    # Let's write custom decision logic for the buyer
    @buyer.on_decide
    def custom_logic(context, tools):
        log(f"[Buyer] Searching for someone to solve: '{context.instruction}'")
        results = tools.search("math")

        if not results:
            log("[Buyer] No math services found!")
            return None

        best_seller = results[0]
        log(f"[Buyer] Hiring {best_seller['name']} for {best_seller['price_usdc']} USDC...")

        # Execute the purchase
        result = tools.purchase_service(
            seller_id=best_seller["agent_id"],
            service_name=best_seller["name"],
            params={"equation": "25 * 4"}
        )
        
        # Since the seller handler runs in the API server's process (separate memory),
        # we compute the answer locally too and attach it for the report display.
        if isinstance(result, dict) and "error" not in result:
            local_answer = calculate_math({"equation": "25 * 4"})
            result["computed_answer"] = local_answer
        
        return result

    # 4. Run the mission
    log("\n🚀 EXECUTING MISSION...")
    report = buyer.run()

    log("\n" + "="*50)
    log("📦 FINAL REPORT")
    log("="*50)

    if report:
        for entry in report:
            tx = entry.get("result", {})

            log(f"\n🎯 Goal: {entry['goal']}")
            log(f"💵 Total Spent: {entry['spent']} USDC")

            if isinstance(tx, dict) and "error" not in tx:
                # Transaction details
                log(f"📝 Status: {tx.get('status', 'unknown')}")
                log(f"💰 Amount: {tx.get('amount_usdc', 'N/A')} USDC")
                log(f"🤖 Seller: {tx.get('seller_agent', 'N/A')}")

                # Show the computed answer prominently
                computed = tx.get("computed_answer") or tx.get("result", {})
                if isinstance(computed, dict) and "answer" in computed:
                    log(f"\n🧮 ANSWER: {computed['equation']} = {computed['answer']}")
                else:
                    service_result = tx.get("result", {})
                    if service_result:
                        log("\n📊 SERVICE RESULT:")
                        log(json.dumps(service_result, indent=2))

                # Circle TX details
                circle_tx = tx.get("circle_tx_id")
                if circle_tx:
                    log(f"\n🔗 Circle TX ID: {circle_tx}")

                # Arc explorer link
                arc_hash = tx.get("arc_tx_hash")
                if not arc_hash and circle_tx and not str(circle_tx).startswith("DEMO"):
                    log("⏳ Waiting for Arc blockchain confirmation...")
                    for i in range(30):
                        try:
                            status = buyer.circle_client.get_transaction_status(circle_tx)
                            if status.get("txHash"):
                                arc_hash = status["txHash"]
                                log("✅ Confirmed on-chain!")
                                break
                        except Exception:
                            pass
                        time.sleep(2)

                if arc_hash:
                    log(f"🌐 Explorer: {ARC_EXPLORER_BASE}/tx/{arc_hash}")

                # Proof hash
                proof = tx.get("erc8004_proof")
                if proof:
                    log(f"🔏 Proof Hash: {proof}")
            elif isinstance(tx, dict):
                log(f"❌ Error: {tx.get('error', 'Unknown error')}")

    log("\n" + "="*50)

    # Cleanup
    buyer.revoke_budget()
    seller.unpublish()

if __name__ == "__main__":
    run_single_demo()

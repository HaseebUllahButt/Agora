#!/usr/bin/env python3
"""
Complete Workflow Guide: Buy, Sell, and Trade with Agora Agents

Shows exactly how to:
1. Create a BUYER agent (fund wallet → buy from marketplace)
2. Create a SELLER agent (offer services → receive payments)
3. Create a DUAL-MODE agent (buy AND sell simultaneously)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk import generate_wallet, Agent
from shared.database import init_database


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 1: BUYER AGENT (Buy from Marketplace)
# ═══════════════════════════════════════════════════════════════════════════

def flow_1_buyer():
    """
    Flow: Fund wallet → Generate keys → Register agent → Purchase service from marketplace
    """
    print("\n" + "="*70)
    print("  FLOW 1: BUYER AGENT - Buy from Marketplace")
    print("="*70 + "\n")
    
    # STEP 1: Generate wallet
    print("STEP 1: Generate Wallet")
    print("-" * 70)
    private_key, address = generate_wallet()
    print(f"\n✓ Wallet Generated!")
    print(f"  Private Key: {private_key}")
    print(f"  Address: {address}")
    
    # STEP 2: Fund wallet (Manual)
    print("\n\nSTEP 2: Fund Wallet on Arc Testnet")
    print("-" * 70)
    print(f"""
⚠️  MANUAL STEP: Fund this address on Arc testnet:
   
   1. Go to: https://arc-testnet.example.com/faucet
   2. Enter address: {address}
   3. Request $10 test USDC
   4. Wait ~30 seconds for funds to arrive
   
Why? Because we're using REAL Circle USDC on Arc blockchain.
""")
    
    # STEP 3: Create buyer agent
    print("\nSTEP 3: Create Buyer Agent")
    print("-" * 70)
    buyer_agent = Agent(
        agent_id="alice_buyer",
        name="Alice (Buyer)",
        private_key=private_key,  # Auto-derives address
        description="I buy data analysis services",
        capabilities=["consulting", "decision_making"]
    )
    print(f"\n✓ Agent created:")
    print(f"  Agent ID: {buyer_agent.id}")
    print(f"  Name: {buyer_agent.name}")
    print(f"  Address: {buyer_agent.address}")
    print(f"  Capabilities: {buyer_agent.capabilities}")
    
    # STEP 4: Register in marketplace
    print("\n\nSTEP 4: Register in Marketplace")
    print("-" * 70)
    result = buyer_agent.register()
    if "error" not in result:
        print(f"\n✓ Registered successfully")
    else:
        print(f"\n✗ Error: {result['error']}")
    
    # STEP 5: Search for services
    print("\n\nSTEP 5: Search for Available Services")
    print("-" * 70)
    services = buyer_agent.discover_services(query="analysis")
    print(f"\n✓ Found {len(services)} services")
    for svc in services[:3]:  # Show first 3
        print(f"  - {svc['name']} by {svc.get('agent', 'unknown')}: ${svc['price']:.4f}")
    
    # STEP 6: Create buyer client (scoped budget)
    print("\n\nSTEP 6: Create Buyer Client with Budget")
    print("-" * 70)
    buyer_client = buyer_agent.create_client(budget_usdc=5.0)
    print(f"\n✓ Buyer client created")
    print(f"  Budget: $5.00 USD")
    print(f"  Address: {buyer_client.wallet_address}")
    print(f"  Available: ${buyer_client.available_budget():.2f}")
    
    # STEP 7: Purchase service
    print("\n\nSTEP 7: Purchase Service from Marketplace")
    print("-" * 70)
    print(f"""
✓ Ready to purchase!
  
  Example purchase (once marketplace has sellers):
  
    result = buyer_client.purchase_service(
        seller_id="bob_seller",
        service_name="CSV Analysis",
        params={{"file": "data.csv"}}
    )
    
  What happens:
    1. SDK checks budget: $5.00 - $0.01 (service cost) = $4.99 remaining
    2. If insufficient: raises BudgetExceeded (safe fail)
    3. If sufficient: signs x402 payment header
    4. API verifies signature + nonce
    5. Service executes atomically
    6. Payment settled on Arc blockchain
    7. Both agents' reputation updated
    8. Result returned to buyer
    
  Result object contains:
    - transaction_id: unique ID for this transaction
    - status: "success" or "failed"
    - result: service output (e.g., analysis results)
    - amount_usdc: $0.01 deducted from budget
""")
    
    print("\n✓ FLOW 1 COMPLETE: Ready to buy from marketplace!")
    return buyer_agent


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 2: SELLER AGENT (Receive Payments)
# ═══════════════════════════════════════════════════════════════════════════

def flow_2_seller():
    """
    Flow: Generate keys → Register agent → Offer services → Receive payments
    """
    print("\n" + "="*70)
    print("  FLOW 2: SELLER AGENT - Offer Services & Receive Payments")
    print("="*70 + "\n")
    
    # STEP 1: Generate wallet
    print("STEP 1: Generate Wallet")
    print("-" * 70)
    private_key, address = generate_wallet()
    print(f"\n✓ Wallet Generated!")
    print(f"  Address: {address}")
    
    # STEP 2: Fund wallet (optional—sellers don't need initial funds to sell)
    print("\n\nSTEP 2: Optional—Fund Wallet")
    print("-" * 70)
    print(f"""
Note: Sellers DON'T need to fund their wallet initially.
But they MAY want to fund it if they want to:
  - Buy other services themselves
  - Hold USDC from sales

For now, skipping faucet funding (optional).
""")
    
    # STEP 3: Create seller agent
    print("\n\nSTEP 3: Create Seller Agent")
    print("-" * 70)
    seller_agent = Agent(
        agent_id="bob_seller",
        name="Bob (Seller)",
        private_key=private_key,
        description="I provide CSV analysis and data insights",
        capabilities=["csv_analysis", "pandas", "data_science"]
    )
    print(f"\n✓ Agent created:")
    print(f"  Agent ID: {seller_agent.id}")
    print(f"  Name: {seller_agent.name}")
    print(f"  Address: {seller_agent.address}")
    print(f"  Capabilities: {seller_agent.capabilities}")
    
    # STEP 4: Register in marketplace
    print("\n\nSTEP 4: Register in Marketplace")
    print("-" * 70)
    result = seller_agent.register()
    print(f"\n✓ Registered successfully")
    
    # STEP 5: Offer services (Register what you sell)
    print("\n\nSTEP 5: Offer Services (Register What You Sell)")
    print("-" * 70)
    
    service_1_id = seller_agent.offer_service(
        name="CSV Analysis",
        service_type="analysis",
        price_usdc=0.01
    )
    print(f"\n✓ Service 1 registered")
    print(f"  Service ID: {service_1_id}")
    print(f"  Name: CSV Analysis")
    print(f"  Price: $0.01")
    
    service_2_id = seller_agent.offer_service(
        name="Data Visualization",
        service_type="visualization",
        price_usdc=0.02
    )
    print(f"\n✓ Service 2 registered")
    print(f"  Service ID: {service_2_id}")
    print(f"  Name: Data Visualization")
    print(f"  Price: $0.02")
    
    # STEP 6: Show services in marketplace
    print("\n\nSTEP 6: View Your Services")
    print("-" * 70)
    my_services = seller_agent.list_my_services()
    print(f"\n✓ You're offering {len(my_services)} services")
    for svc in my_services:
        print(f"  - {svc['name']}: ${svc['price']:.4f}")
    
    # STEP 7: Wait for buyers
    print("\n\nSTEP 7: Wait for Buyers & Receive Payments")
    print("-" * 70)
    seller_addr = seller_agent.address
    print(f"""
✓ Services live in marketplace!

What happens when a buyer purchases:
  
  1. Buyer signs x402 payment header with your price (e.g., $0.01)
  2. API validates signature + nonce + balance
  3. Service function executes (your code)
  4. Payment settles on Arc blockchain → Your wallet receives $0.01
  5. Your reputation +5 for successful delivery
  6. Buyer sees result + gets reputation +1
  
Payments received on: {seller_addr}

To check incoming USDC:
  from shared.arc_client import get_balance
  balance = get_balance("{seller_addr}")
""")
    
    print("\n✓ FLOW 2 COMPLETE: Ready to sell services!")
    return seller_agent


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 3: DUAL-MODE AGENT (Buy AND Sell)
# ═══════════════════════════════════════════════════════════════════════════

def flow_3_dual_mode():
    """
    Flow: Single agent that can buy services, process them, and sell results
    """
    print("\n" + "="*70)
    print("  FLOW 3: DUAL-MODE AGENT - Buy, Process, Sell (Create Value)")
    print("="*70 + "\n")
    
    # STEP 1: Generate wallet
    print("STEP 1: Generate Wallet")
    print("-" * 70)
    private_key, address = generate_wallet()
    print(f"\n✓ Wallet Generated!")
    print(f"  Address: {address}")
    
    # STEP 2: Fund wallet (CRITICAL for dual-mode—need budget to BUY)
    print("\n\nSTEP 2: Fund Wallet (Required for Buying)")
    print("-" * 70)
    print(f"""
⚠️  CRITICAL: Dual-mode agents MUST fund wallet to BUY services.
   
   Fund this address on Arc testnet:
   {address}
   
   Request $5-10 test USDC to have budget for purchases.
""")
    
    # STEP 3: Create dual-mode agent
    print("\n\nSTEP 3: Create Dual-Mode Agent")
    print("-" * 70)
    dual_agent = Agent(
        agent_id="charlie_trader",
        name="Charlie (Data Processor)",
        private_key=private_key,
        description="I buy raw data, analyze it, and sell insights",
        capabilities=["data_processing", "analysis", "insights"]
    )
    print(f"\n✓ Agent created:")
    print(f"  Agent ID: {dual_agent.id}")
    print(f"  Name: {dual_agent.name}")
    print(f"  Address: {dual_agent.address}")
    
    # STEP 4: Register (works for both buy and sell)
    print("\n\nSTEP 4: Register in Marketplace")
    print("-" * 70)
    result = dual_agent.register()
    print(f"\n✓ Registered successfully")
    
    # STEP 5: Offer services (SELLER mode)
    print("\n\nSTEP 5: Offer Your Services (SELLER Mode)")
    print("-" * 70)
    service_id = dual_agent.offer_service(
        name="Advanced Analytics",
        service_type="analytics",
        price_usdc=0.05  # Higher price for processed insights
    )
    print(f"\n✓ Service registered: Advanced Analytics @ $0.05")
    
    # STEP 6: Create buyer client (BUYER mode)
    print("\n\nSTEP 6: Create Buyer Client with Budget (BUYER Mode)")
    print("-" * 70)
    buyer_client = dual_agent.create_client(budget_usdc=2.0)
    print(f"\n✓ Buyer client created")
    print(f"  Budget for buying: $2.00")
    print(f"  Available: ${buyer_client.available_budget():.2f}")
    
    # STEP 7: The Dual-Mode Workflow
    print("\n\nSTEP 7: Dual-Mode Workflow (Buy → Process → Sell)")
    print("-" * 70)
    print(f"""
✓ WORKFLOW: Same agent does BUY and SELL

Architecture in CODE:
  
  # SELLER phase - Advertise services
  dual_agent.offer_service("Advanced Analytics", "analytics", 0.05)
  
  # BUYER phase - Set budget
  buyer_client = dual_agent.create_client(budget_usdc=2.0)
  
  # BUYER phase - Purchase raw data from other agents
  raw_data = buyer_client.purchase_service(
      seller_id="alice_seller",
      service_name="Raw Data Export",
      params={{"export_format": "csv"}}
  )  # Costs $0.01, leaves $1.99 budget
  
  # PROCESS - Internal logic (not marketplace)
  insights = process_and_analyze(raw_data)  # Your custom logic
  
  # SELLER phase - Buyers purchase YOUR processed insights
  # (Automatically handled by API when buyers call your service)
  
  # REPEAT - Buy more data, sell more insights
  more_data = buyer_client.purchase_service(
      seller_id="bob_seller",
      service_name="Market Data",
      params={{"date": "2026-04-21"}}
  )  # Costs $0.02, leaves $1.97 budget


Economics Flow:
  
  Starting state:
    - Wallet has $10 USDC (funded from faucet)
    - Offering "Advanced Analytics" @ $0.05
  
  Transaction 1 (YOU BUY):
    - Buy "Raw Data" @ $0.01
    - Wallet: $10.00 - $0.01 = $9.99
    - Reputation: +1
  
  Transaction 2 (YOU SELL):
    - Buyer purchases "Advanced Analytics" @ $0.05
    - Wallet: $9.99 + $0.05 = $10.04
    - Reputation: +5
  
  Transaction 3 (YOU BUY again):
    - Buy "Market Data" @ $0.02
    - Wallet: $10.04 - $0.02 = $10.02
    - Reputation: +1
  
  Transaction 4 (YOU SELL again):
    - Buyer purchases "Advanced Analytics" @ $0.05
    - Wallet: $10.02 + $0.05 = $10.07
    - Reputation: +5 (now 11 total)


Key Insights:
  
  ✓ SAME agent instance = both buyer and seller
  ✓ Budget scoped per session (client = buyer, agent = seller)
  ✓ Each transaction atomic: sign → verify → execute → settle
  ✓ Multi-step workflows: buy low, add value, sell high
  ✓ Reputation compounds: successful traders get +5 per sale
  ✓ Real money: USDC on Arc blockchain
""")
    
    print("\n✓ FLOW 3 COMPLETE: Ready for dual-mode trading!")
    return dual_agent


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: Run All Three Flows
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Run all three workflows."""
    # Initialize database
    init_database()
    
    print("\n" + "#"*70)
    print("# AGORA MARKETPLACE: Complete Workflow Guide")
    print("# Demonstrates: Buy, Sell, and Dual-Mode Trading")
    print("#"*70)
    
    # Flow 1: Buyer
    buyer = flow_1_buyer()
    
    # Flow 2: Seller
    seller = flow_2_seller()
    
    # Flow 3: Dual-Mode
    dual = flow_3_dual_mode()
    
    # Summary
    print("\n" + "="*70)
    print("  SUMMARY: Three Agent Archetypes")
    print("="*70 + "\n")
    
    print(f"""
Agent 1: BUYER (Pure Consumer)
  ID: {buyer.id}
  Address: {buyer.address}
  Capabilities: {buyer.capabilities}
  Action: Funds wallet → Purchases services → Gets results
  Payment flow: Wallet → Marketplace → Seller
  Arc impact: Sends Circle USDC to sellers

Agent 2: SELLER (Pure Provider)
  ID: {seller.id}
  Address: {seller.address}
  Capabilities: {seller.capabilities}
  Action: Registers services → Waits for buyers → Receives payments
  Payment flow: Buyer → Marketplace → Wallet
  Arc impact: Receives Circle USDC from buyers

Agent 3: DUAL MODE (Trader/Creator)
  ID: {dual.id}
  Address: {dual.address}
  Capabilities: {dual.capabilities}
  Action: Buys data → Processes → Sells insights
  Payment flow: Buy (send) → Process → Sell (receive)
  Arc impact: Net flow depends on margins (buy @0.01, sell @0.05)
  Economics: Profitable if you add value!
""")
    
    print("\n" + "="*70)
    print("  NEXT STEPS")
    print("="*70 + "\n")
    
    print("""
1. FUND WALLETS:
   - Go to Arc faucet for each address
   - Request $5-10 test USDC per agent
   
2. CONNECT TO MARKETPLACE:
   - Start API: python -m uvicorn api.v1:app --port 8000
   - Agents auto-register when you call agent.register()
   
3. START TRADING:
   - Buyer: buyer_client.purchase_service(seller_id, service_name, params)
   - Seller: buyer_purchase_from_marketplace → Your wallet receives USDC
   - Dual: Loop buying cheap → processing → selling high-value
   
4. MONITOR:
   - WebSocket: ws://localhost:8000/ws (real-time transactions)
   - REST: GET /transactions (history)
   - Balance: get_balance(address) (check Arc wallet)
   - Reputation: Earned automatically via SDK
""")
    
    print("\n" + "="*70)
    print("✓ Complete Workflow Guide Ready!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

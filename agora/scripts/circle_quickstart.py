#!/usr/bin/env python3
"""
Quick start: Register agents with Circle and perform transactions on Arc

This demonstrates the end-to-end flow for the submission.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from shared.database import init_database
from sdk.agent import Agent
from sdk.consumer import create_agora_client

# Initialize database
init_database()

# Get Circle credentials from environment
api_key = os.getenv("CIRCLE_API_KEY")
entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")

print("="*70)
print("AGORA MARKETPLACE - CIRCLE INTEGRATION QUICKSTART")
print("="*70)

# Step 1: Register Alice with Circle wallet on Arc
print("\n[Step 1] Registering Alice with Circle wallet...\n")

alice = Agent(
    agent_id="alice",
    name="Alice (Data Analyst)",
    private_key="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    circle_api_key=api_key,
    circle_entity_secret=entity_secret,
    circle_wallet_set_id=wallet_set_id,
    description="Analyzes data and generates insights",
    capabilities=["analysis", "pandas"]
)

result = alice.register()

if "error" in result:
    print(f"❌ Registration failed: {result['error']}")
    exit(1)

print(f"✅ Alice registered!")
print(f"   - Secp256k1 address: {result['address']}")
print(f"   - Circle wallet ID: {result['circle_wallet_id']}")
print(f"   - Arc address: {result['circle_address']}")

# Step 2: Register Bob
print("\n[Step 2] Registering Bob with Circle wallet...\n")

bob = Agent(
    agent_id="bob",
    name="Bob (Web Researcher)",
    private_key="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    circle_api_key=api_key,
    circle_entity_secret=entity_secret,
    circle_wallet_set_id=wallet_set_id,
    description="Performs web research and data extraction",
    capabilities=["web_search", "scraping"]
)

result = bob.register()

if "error" in result:
    print(f"❌ Registration failed: {result['error']}")
    exit(1)

print(f"✅ Bob registered!")
print(f"   - Circle wallet ID: {result['circle_wallet_id']}")
print(f"   - Arc address: {result['circle_address']}")

# Step 3: Register services
print("\n[Step 3] Registering services...\n")

alice_service_id = alice.offer_service(
    name="CSV Analysis",
    service_type="analysis",
    price_usdc=0.05,
    description="Analyze CSV files and extract insights"
)
print(f"✅ Alice offers: CSV Analysis (0.05 USDC)")

bob_service_id = bob.offer_service(
    name="Web Search",
    service_type="web_search",
    price_usdc=0.03,
    description="Search the web and extract data"
)
print(f"✅ Bob offers: Web Search (0.03 USDC)")

# Step 4: Alice purchases from Bob with Circle settlement
print("\n[Step 4] Alice purchasing from Bob with Circle settlement...\n")

try:
    # Create buyer client for Alice
    buyer_client = create_agora_client(
        agent_id="alice",
        budget_usdc=1.00  # 1 USDC budget
    )
    
    print(f"✅ Buyer session created")
    print(f"   - Budget: ${buyer_client.budget_usdc:.4f} USDC")
    print(f"   - Available: ${buyer_client.available_budget():.4f} USDC\n")
    
    # Make purchase (this triggers Circle USDC transfer on Arc)
    print("Executing purchase with Circle settlement...")
    result = buyer_client.purchase_service(
        seller_id="bob",
        service_name="Web Search",
        params={"query": "AI agents on Arc blockchain"}
    )
    
    if "error" in result:
        print(f"❌ Purchase failed: {result['error']}")
    else:
        print(f"\n✅ Purchase successful!")
        print(f"   - Transaction ID: {result['transaction_id']}")
        print(f"   - Circle TX: {result.get('circle_tx_id')}")
        print(f"   - Status: {result['status']}")
        print(f"   - Amount: ${result['amount_usdc']:.4f} USDC")
        print(f"   - Arc TX Hash: {result.get('arc_tx_hash', 'Pending...')}")
        
        # Show budget after purchase
        print(f"\n   - Budget after purchase:")
        print(f"     - Spent: ${buyer_client.spent_usdc:.4f} USDC")
        print(f"     - Remaining: ${buyer_client.available_budget():.4f} USDC")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("✅ Quickstart complete!")
print("="*70)
print("\nNext steps:")
print("1. Check Circle wallet balances on Arc testnet")
print("2. Verify transactions on testnet.arcscan.app")
print("3. Generate 50+ transactions for hackathon submission")
print("4. Record demo video showing live settlement")

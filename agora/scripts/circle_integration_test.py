#!/usr/bin/env python3
"""
scripts/circle_integration_test.py

Test Circle SDK integration with Agent registration and USDC transfers on Arc.

Flow:
1. Initialize database
2. Register agents with Circle credentials
3. Create services
4. Perform purchases with real Circle transfers on Arc
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.database import init_database, get_agent, get_circle_credentials
from sdk.agent import Agent
from sdk.consumer import create_agora_client
from sdk.exceptions import BudgetExceeded


def test_agent_registration():
    """Test agent registration with Circle credentials."""
    print("\n" + "="*70)
    print("TEST 1: Agent Registration with Circle")
    print("="*70)
    
    # Get credentials from env
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
    
    if not all([api_key, entity_secret, wallet_set_id]):
        print("❌ Circle credentials not configured in .env")
        return False
    
    try:
        # Check if agents already exist
        alice_existing = get_agent("alice")
        alice_creds = get_circle_credentials("alice") if alice_existing else None
        
        if alice_existing and alice_creds:
            print("[1.1] Alice already registered with Circle")
            print(f"✓ Alice ready")
            print(f"  - Agent ID: alice")
            print(f"  - Address: {alice_existing.get('address')}")
            print(f"  - Circle Wallet: {alice_creds.get('circle_wallet_id')}")
            print(f"  - Circle Address: {alice_creds.get('circle_address')}")
        else:
            # Create Alice agent
            print("[1.1] Creating Alice agent with Circle...")
            alice = Agent(
                agent_id="alice",
                name="Alice (Data Analyst)",
                private_key="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                circle_api_key=api_key,
                circle_entity_secret=entity_secret,
                circle_wallet_set_id=wallet_set_id,
                description="Performs data analysis and CSV processing",
                capabilities=["analysis", "pandas", "sql"]
            )
            
            alice_result = alice.register()
            
            if "error" in alice_result:
                print(f"❌ Alice registration failed: {alice_result['error']}")
                return False
            
            print(f"✓ Alice registered successfully")
            print(f"  - Agent ID: {alice_result['agent_id']}")
            print(f"  - Address: {alice_result['address']}")
            print(f"  - Circle Wallet: {alice_result['circle_wallet_id']}")
            print(f"  - Circle Address: {alice_result['circle_address']}")
        
        # Check Bob
        bob_existing = get_agent("bob")
        bob_creds = get_circle_credentials("bob") if bob_existing else None
        
        if bob_existing and bob_creds:
            print("\n[1.2] Bob already registered with Circle")
            print(f"✓ Bob ready")
            print(f"  - Agent ID: bob")
            print(f"  - Circle Wallet: {bob_creds.get('circle_wallet_id')}")
        else:
            print("\n[1.2] Creating Bob agent with Circle...")
            bob = Agent(
                agent_id="bob",
                name="Bob (Web Researcher)",
                private_key="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                circle_api_key=api_key,
                circle_entity_secret=entity_secret,
                circle_wallet_set_id=wallet_set_id,
                description="Performs web research and data extraction",
                capabilities=["web_search", "scraping", "extraction"]
            )
            
            bob_result = bob.register()
            
            if "error" in bob_result:
                print(f"❌ Bob registration failed: {bob_result['error']}")
                return False
            
            print(f"✓ Bob registered successfully")
            print(f"  - Agent ID: {bob_result['agent_id']}")
            print(f"  - Circle Wallet: {bob_result['circle_wallet_id']}")
        
        # Register services
        print("\n[1.3] Checking services...")
        
        from shared.database import search_providers, register_provider
        import uuid
        
        alice_services = [p for p in search_providers("CSV Analysis") if p.get("agent_id") == "alice"]
        if not alice_services:
            provider_id = str(uuid.uuid4())[:8]
            register_provider(
                provider_id=provider_id,
                agent_id="alice",
                name="CSV Analysis",
                service_type="analysis",
                description="Analyze CSV files and produce insights",
                price_usdc=0.05
            )
            print(f"✓ Alice offered: CSV Analysis (0.05 USDC)")
        else:
            print(f"⚠ Alice service already exists")
        
        bob_services = [p for p in search_providers("Web Search") if p.get("agent_id") == "bob"]
        if not bob_services:
            provider_id = str(uuid.uuid4())[:8]
            register_provider(
                provider_id=provider_id,
                agent_id="bob",
                name="Web Search",
                service_type="web_search",
                description="Search the web and extract data",
                price_usdc=0.03
            )
            print(f"✓ Bob offered: Web Search (0.03 USDC)")
        else:
            print(f"⚠ Bob service already exists")
        
        return True
    
    except Exception as e:
        print(f"❌ Registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_purchase_with_circle():
    """Test purchasing services with Circle USDC transfers on Arc."""
    print("\n" + "="*70)
    print("TEST 2: Purchase Service with Circle Settlement")
    print("="*70)
    
    try:
        # Verify agents exist
        alice = get_agent("alice")
        bob = get_agent("bob")
        
        if not alice or not bob:
            print("❌ Agents not registered. Run test 1 first.")
            return False
        
        print(f"\n[2.1] Alice purchasing from Bob with 0.50 USDC budget...")
        
        # Create buyer client
        buyer_client = create_agora_client(
            agent_id="alice",
            budget_usdc=0.50
        )
        
        print(f"✓ Buyer client created")
        print(f"  - Budget: ${buyer_client.budget_usdc:.4f} USDC")
        print(f"  - Available: ${buyer_client.available_budget():.4f} USDC")
        
        # Search for Bob's service
        print(f"\n[2.2] Searching for 'Web Search' service...")
        services = buyer_client.search("Web Search", limit=5)
        
        if not services:
            print("❌ No services found")
            return False
        
        print(f"✓ Found {len(services)} service(s)")
        for svc in services:
            print(f"  - {svc.get('name')}: ${svc.get('price_usdc'):.4f} USDC (seller: {svc.get('agent_id')})")
        
        # Purchase service
        print(f"\n[2.3] Purchasing 'Web Search' from Bob...")
        purchase_result = buyer_client.purchase_service(
            seller_id="bob",
            service_name="Web Search",
            params={"query": "AI agents arc blockchain"}
        )
        
        if "error" in purchase_result:
            print(f"❌ Purchase failed: {purchase_result['error']}")
            return False
        
        print(f"✓ Purchase successful")
        print(f"  - Transaction ID: {purchase_result['transaction_id']}")
        print(f"  - Circle TX: {purchase_result.get('circle_tx_id')}")
        print(f"  - Arc Hash: {purchase_result.get('arc_tx_hash')}")
        print(f"  - Status: {purchase_result['status']}")
        print(f"  - Amount: ${purchase_result['amount_usdc']:.4f} USDC")
        
        # Check budget
        print(f"\n[2.4] Final budget status:")
        print(f"  - Started with: ${0.50:.4f} USDC")
        print(f"  - Spent: ${buyer_client.spent_usdc:.4f} USDC")
        print(f"  - Remaining: ${buyer_client.available_budget():.4f} USDC")
        print(f"  - Transactions: {len(buyer_client.transactions)}")
        
        return True
    
    except Exception as e:
        print(f"❌ Purchase test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_budget_enforcement():
    """Test budget enforcement during purchases."""
    print("\n" + "="*70)
    print("TEST 3: Budget Enforcement")
    print("="*70)
    
    try:
        print("\n[3.1] Creating buyer with small budget (0.02 USDC)...")
        buyer_client = create_agora_client(
            agent_id="alice",
            budget_usdc=0.02  # Less than Bob's service price (0.03)
        )
        
        print(f"✓ Budget: ${buyer_client.budget_usdc:.4f} USDC")
        
        # Try to purchase (should fail due to budget)
        print(f"\n[3.2] Attempting purchase that exceeds budget...")
        try:
            result = buyer_client.purchase_service(
                seller_id="bob",
                service_name="Web Search",
                params={"query": "test"}
            )
            print(f"❌ Expected BudgetExceeded but got: {result}")
            return False
        except BudgetExceeded as e:
            print(f"✓ Budget enforcement working as expected")
            print(f"  - Service cost: ${e.service_cost:.4f} USDC")
            print(f"  - Available: ${e.remaining_budget:.4f} USDC")
            return True
    
    except Exception as e:
        print(f"❌ Budget test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "🔵"*35)
    print("CIRCLE SDK INTEGRATION TEST SUITE")
    print("🔵"*35)
    
    # Initialize database
    print("\n[Setup] Initializing database...")
    init_database()
    print("✓ Database ready")
    
    # Run tests
    tests = [
        test_agent_registration,
        test_purchase_with_circle,
        test_budget_enforcement
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        time.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total: {len(results)} tests")
    print(f"Passed: {sum(results)} tests")
    print(f"Failed: {len(results) - sum(results)} tests")
    
    if all(results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())

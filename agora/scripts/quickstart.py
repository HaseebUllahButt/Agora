#!/usr/bin/env python3
"""
scripts/quickstart.py — Quick Start: Generate & Initialize Agent

Shows developers how to create a real agent with a blockchain wallet.

Usage:
  python scripts/quickstart.py

This will:
1. Generate a new secp256k1 wallet
2. Print the address to fund on Arc testnet
3. Show how to initialize the agent
4. Demonstrate the marketplace workflow
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk import generate_wallet, Agent


def quickstart():
    print("\n" + "="*70)
    print("  AGORA SDK: QUICK START")
    print("="*70 + "\n")
    
    # Step 1: Generate wallet
    print("STEP 1: Generate Wallet")
    print("-" * 70)
    private_key, address = generate_wallet()
    print(f"\n✓ Wallet Generated!")
    print(f"\nPrivate Key (KEEP SAFE):")
    print(f"  {private_key}\n")
    print(f"Address (Fund this on Arc testnet):")
    print(f"  {address}\n")
    
    # Step 2: Initialize agent
    print("\nSTEP 2: Initialize Agent")
    print("-" * 70)
    agent = Agent(
        agent_id="my_first_agent",
        name="My Trading Bot",
        private_key=private_key,
        description="My first Agora agent - demo",
        capabilities=["trading", "analysis", "data_processing"]
    )
    print(f"\n✓ Agent created (not yet registered)\n")
    print(f"  Agent ID:  {agent.id}")
    print(f"  Name:      {agent.name}")
    print(f"  Address:   {agent.address}")
    print(f"  Capabilities: {', '.join(agent.capabilities)}\n")
    
    # Step 3: Register agent
    print("\nSTEP 3: Register Agent")
    print("-" * 70)
    result = agent.register()
    if "error" not in result:
        print(f"\n✓ Agent registered successfully!\n")
        print(f"  Status: {result['status']}")
        print(f"  Description: {result['description']}\n")
    else:
        print(f"\n✗ Registration failed: {result['error']}\n")
        return
    
    # Step 4: Offer a service
    print("\nSTEP 4: Offer a Service")
    print("-" * 70)
    service_id = agent.offer_service(
        name="Data Analysis",
        service_type="analysis",
        price_usdc=0.01
    )
    print(f"\n✓ Service registered!\n")
    print(f"  Service ID:  {service_id}")
    print(f"  Name:        Data Analysis")
    print(f"  Price:       $0.01 USD\n")
    
    # Step 5: Create buyer client
    print("\nSTEP 5: Create Buyer Client")
    print("-" * 70)
    buyer = agent.create_client(budget_usdc=0.50)
    print(f"\n✓ Buyer client created!\n")
    print(f"  Budget:      $0.50 USD")
    print(f"  Address:     {buyer.wallet_address}\n")
    
    # Step 6: Check available budget
    print("\nSTEP 6: Check Budget")
    print("-" * 70)
    available = buyer.available_budget()
    print(f"\n✓ Budget check:\n")
    print(f"  Available: ${available:.4f}")
    print(f"  Status:    Ready to purchase\n")
    
    # Summary
    print("\n" + "="*70)
    print("  NEXT STEPS:")
    print("="*70)
    print("""
1. Fund your wallet on Arc testnet:
   https://arc-testnet.example.com/faucet
   → Enter address: """ + address + """

2. Wait for funds to arrive (~30 seconds)

3. Start trading:
   - Discover services: agent.discover_services(query="analysis")
   - Buy services: buyer.purchase_service(seller_id, service_name, params)
   - Sell services: agent.offer_service(name, type, price)

4. See transaction feed:
   - HTTP: /transactions endpoint
   - WebSocket: /ws for real-time updates

5. For production:
   - See WALLET_GUIDE.md for environment setup
   - Use .env files for key management
   - Monitor balance with get_balance(address)
""")
    print("="*70 + "\n")


if __name__ == "__main__":
    quickstart()

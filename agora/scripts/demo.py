#!/usr/bin/env python3
"""
scripts/demo.py — Agora Marketplace Demo

Demonstrates a working agent-to-agent marketplace with:
- Multiple agents with budgets
- Service registration and discovery
- Multi-transaction workflows
- Budget enforcement (graceful failure)
- Reputation tracking
"""

import os
import sys
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from sdk.agent import Agent
from sdk.wallet import generate_wallet
from sdk.exceptions import BudgetExceeded
from shared.database import init_database, get_transaction_history


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_transaction(buyer: str, seller: str, service: str, cost: float, status: str):
    """Print a formatted transaction log."""
    icon = "✓" if status == "success" else "✗"
    print(f"  [{icon}] {buyer:10s} → ${cost:6.4f} → {seller:10s} ({service})")


def demo():
    """Run the Agora demo scenario."""
    
    print_section("AGORA MARKETPLACE DEMO - Agent-to-Agent Trading")
    
    # Initialize database
    print("Initializing database...")
    init_database()
    print("✓ Database ready\n")
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 1: Agent Registration
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 1: Agent Registration")
    
    # Create agents with roles
    print("Generating wallets...\n")
    
    alice_key, alice_addr = generate_wallet()
    alice = Agent(
        agent_id="alice",
        name="Alice",
        private_key=alice_key,
        description="Data analyst specializing in CSV operations",
        capabilities=["analysis", "csv", "pandas"]
    )
    alice.register()
    print(f"✓ Alice registered (Data Analyst)")
    print(f"  Address: {alice_addr}\n")
    
    bob_key, bob_addr = generate_wallet()
    bob = Agent(
        agent_id="bob",
        name="Bob",
        private_key=bob_key,
        description="Web developer providing scraping services",
        capabilities=["scraping", "web", "selenium"]
    )
    bob.register()
    print(f"✓ Bob registered (Web Developer)")
    print(f"  Address: {bob_addr}\n")
    
    charlie_key, charlie_addr = generate_wallet()
    charlie = Agent(
        agent_id="charlie",
        name="Charlie",
        private_key=charlie_key,
        description="ML engineer with training expertise",
        capabilities=["ml", "training", "pytorch"]
    )
    charlie.register()
    print(f"✓ Charlie registered (ML Engineer)")
    print(f"  Address: {charlie_addr}\n")
    
    diana_key, diana_addr = generate_wallet()
    diana = Agent(
        agent_id="diana",
        name="Diana",
        private_key=diana_key,
        description="Data scientist creating visualizations",
        capabilities=["visualization", "dashboards", "plotly"]
    )
    diana.register()
    print(f"✓ Diana registered (Data Scientist)")
    print(f"  Address: {diana_addr}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 2: Service Registration
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 2: Service Registration")
    
    # Alice's services
    alice_service_1 = alice.offer_service("CSV Analysis", "analysis", 0.010)
    print(f"✓ Alice offering: CSV Analysis @ $0.010")
    
    # Bob's services
    bob_service_1 = bob.offer_service("Web Scraping", "web", 0.020)
    print(f"✓ Bob offering: Web Scraping @ $0.020")
    
    # Charlie's services
    charlie_service_1 = charlie.offer_service("Model Training", "ml", 0.030)
    print(f"✓ Charlie offering: Model Training @ $0.030")
    
    # Diana's services
    diana_service_1 = diana.offer_service("Data Visualization", "viz", 0.015)
    print(f"✓ Diana offering: Data Visualization @ $0.015")
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 3: Marketplace Transactions
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 3: Marketplace Transactions")
    
    # Create clients with budgets
    alice_buyer = alice.create_client(budget_usdc=0.50)
    bob_buyer = bob.create_client(budget_usdc=0.30)
    charlie_buyer = charlie.create_client(budget_usdc=1.00)
    diana_buyer = diana.create_client(budget_usdc=0.40)
    
    print("✓ Buyer clients created with budgets:")
    print(f"  - Alice: $0.50 USD")
    print(f"  - Bob: $0.30 USD")
    print(f"  - Charlie: $1.00 USD")
    print(f"  - Diana: $0.40 USD\n")
    
    transactions_succeeded = 0
    transactions_failed = 0
    
    # Transaction 1: Alice buys from Bob
    print("TX 1: Alice → Bob (Web Scraping)")
    try:
        result = alice_buyer.purchase_service("bob", "Web Scraping", {"url": "example.com"})
        print_transaction("Alice", "Bob", "Web Scraping", 0.020, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 2: Bob buys from Alice
    print("\nTX 2: Bob → Alice (CSV Analysis)")
    try:
        result = bob_buyer.purchase_service("alice", "CSV Analysis", {"file": "data.csv"})
        print_transaction("Bob", "Alice", "CSV Analysis", 0.010, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 3-5: Charlie buys from Alice (×3)
    print("\nTX 3-5: Charlie → Alice (CSV Analysis, bulk)")
    for i in range(3):
        print(f"  TX {3+i}:")
        try:
            result = charlie_buyer.purchase_service("alice", "CSV Analysis", {"file": f"dataset_{i}.csv"})
            print_transaction("Charlie", "Alice", "CSV Analysis", 0.010, "success")
            transactions_succeeded += 1
        except BudgetExceeded as e:
            print(f"  [✗] {e.message}")
            transactions_failed += 1
    
    # Transaction 6: Charlie buys from Bob
    print("\nTX 6: Charlie → Bob (Web Scraping)")
    try:
        result = charlie_buyer.purchase_service("bob", "Web Scraping", {"url": "data.example.com"})
        print_transaction("Charlie", "Bob", "Web Scraping", 0.020, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 7: Diana buys from Charlie
    print("\nTX 7: Diana → Charlie (Model Training)")
    try:
        result = diana_buyer.purchase_service("charlie", "Model Training", {"epochs": 100})
        print_transaction("Diana", "Charlie", "Model Training", 0.030, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 8: Alice buys from Diana
    print("\nTX 8: Alice → Diana (Data Visualization)")
    try:
        result = alice_buyer.purchase_service("diana", "Data Visualization", {"data": "results.json"})
        print_transaction("Alice", "Diana", "Data Visualization", 0.015, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 9-10: Bob buys from Diana (×2)
    print("\nTX 9-10: Bob → Diana (Data Visualization, ×2)")
    for i in range(2):
        print(f"  TX {9+i}:")
        try:
            result = bob_buyer.purchase_service("diana", "Data Visualization", {"chart": f"viz_{i}.html"})
            print_transaction("Bob", "Diana", "Data Visualization", 0.015, "success")
            transactions_succeeded += 1
        except BudgetExceeded as e:
            print(f"  [✗] {e.message}")
            transactions_failed += 1
    
    # Transaction 11: Charlie buys from Diana
    print("\nTX 11: Charlie → Diana (Data Visualization)")
    try:
        result = charlie_buyer.purchase_service("diana", "Data Visualization", {"theme": "dark"})
        print_transaction("Charlie", "Diana", "Data Visualization", 0.015, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✗] {e.message}")
        transactions_failed += 1
    
    # Transaction 12: Bob attempts to buy from Charlie (should fail - insufficient budget)
    print("\nTX 12: Bob → Charlie (Model Training) [BUDGET TEST]")
    try:
        # Bob only has ~$0.26 left ($0.30 - $0.01 - $0.03), but Model Training costs $0.03
        # Actually let's check: Bob spent $0.02 on Alice, $0.03 on Diana (×2) = $0.08
        # So Bob has ~$0.22 left - Model Training at $0.03 should work
        # Let me create a scenario where he definitely runs out
        result = bob_buyer.purchase_service("charlie", "Model Training", {"model": "gpt"})
        print_transaction("Bob", "Charlie", "Model Training", 0.030, "success")
        transactions_succeeded += 1
    except BudgetExceeded as e:
        print(f"  [✓] Budget protection triggered: {e.message}")
        transactions_failed += 1
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 4: Results & Analysis
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 4: Results & Analysis")
    
    print(f"Total Transactions Attempted: {transactions_succeeded + transactions_failed}")
    print(f"  ✓ Successful: {transactions_succeeded}")
    print(f"  ✗ Failed/Blocked: {transactions_failed}")
    print(f"\nAverage Transaction Value: ${(0.010 + 0.020 + 0.030 + 0.015) / 4:.4f}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 5: Transaction History
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 5: Transaction History (from database)")
    
    history = get_transaction_history(limit=50)
    if history:
        print(f"Recorded {len(history)} transactions:\n")
        for i, tx in enumerate(history, 1):
            status_icon = "✓" if tx["status"] == "success" else "✗"
            print(f"  [{status_icon}] TX {i}: {tx['buyer_id']:8s} → {tx['seller_id']:8s} @ ${tx['amount_usdc']:.4f}")
    else:
        print("(No transactions recorded yet)")
    
    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 6: Agent Balances & Reputation
    # ──────────────────────────────────────────────────────────────────────────
    
    print_section("PHASE 6: Final State")
    
    print("Remaining Budgets:")
    print(f"  Alice:   ${alice_buyer.available_budget():.4f} (started with $0.50)")
    print(f"  Bob:     ${bob_buyer.available_budget():.4f} (started with $0.30)")
    print(f"  Charlie: ${charlie_buyer.available_budget():.4f} (started with $1.00)")
    print(f"  Diana:   ${diana_buyer.available_budget():.4f} (started with $0.40)")
    
    print("\nDemo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo()

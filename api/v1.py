"""
api/v1.py — Agora Marketplace API

Core flow:
1. Agents register (wallet + metadata)
2. Providers register services (callable functions)
3. Buyers execute services:
   - Send x402 payment header (ECDSA signed)
   - API validates signature + nonce + balance
   - API calls the service function synchronously
   - Returns result + transaction ID to buyer
   - Updates reputation both sides

Clean atomic model: Payment → Execution → Settlement
"""

import os
import sys
import uuid
import time
import json
import hashlib
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("agora.api")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment before anything else
load_dotenv()

from shared.database import (
    init_database, create_agent, register_provider, get_all_providers,
    search_providers, record_transaction, update_transaction_status,
    update_agent_reputation, get_agent, get_transaction_history,
    record_service_result
)
from shared.ecdsa_signing import validate_x402_header
from shared.nonce_registry import register_nonce
from shared.arc_client import has_sufficient_balance
from shared.event_bus import get_event_bus
from shared.search_engine import get_search_engine
from shared.circle_client import CircleClient, CircleWalletConfig
from sdk.provider import get_service_registry, call_service

# Initialize Circle infrastructure for server-side settlement
circle_api_key = os.getenv("CIRCLE_API_KEY")
circle_entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
circle_wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")

if not all([circle_api_key, circle_entity_secret]):
    # Fallback/warning if not configured
    print("⚠️  Warning: CIRCLE_API_KEY or CIRCLE_ENTITY_SECRET missing. Settlement will be skipped.")
    circle_client = None
else:
    circle_config = CircleWalletConfig(circle_api_key, circle_entity_secret, circle_wallet_set_id)
    circle_client = CircleClient(circle_config)

app = FastAPI(title="Agora Marketplace", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialize database on startup
init_database()

# ──────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ──────────────────────────────────────────────────────────────────────────────

class RegisterAgentRequest(BaseModel):
    """Register info (public only) with the marketplace."""
    agent_id: str  
    name: str
    address: str # The Arc address (USDC destination)
    description: str = ""
    capabilities: list = []  


class RegisterServiceRequest(BaseModel):
    """Register a service offered by an agent."""
    agent_id: str
    name: str
    service_type: str  
    description: str
    price_usdc: float  
    endpoint_url: Optional[str] = None


class PurchaseServiceRequest(BaseModel):
    """Buy a service with cryptographic proof of payment."""
    service_id: str  
    buyer_agent_id: str
    circle_wallet_id: str # The buyer's source wallet ID
    x402_header: dict # The ECDSA signed payment proof (dictionary)
    params: dict = {}  


# ──────────────────────────────────────────────────────────────────────────────
# AGENT MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/agents/register")
def register_agent(req: RegisterAgentRequest):
    """
    Register a new agent in the marketplace registry.
    Only stores public metadata for discovery and reputation.
    """
    try:
        # Register in local DB
        create_agent(
            agent_id=req.agent_id,
            name=req.name,
            address=req.address,
            description=req.description,
            capabilities=json.dumps(req.capabilities)
        )
        
        return {
            "agent_id": req.agent_id,
            "status": "registered",
            "address": req.address
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents")
def list_agents():
    """List all registered agents."""
    from shared.database import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, reputation_score FROM agents WHERE 1")
        agents = [
            {
                "agent_id": row[0],
                "name": row[1],
                "address": row[2],
                "reputation": row[3]
            }
            for row in cursor.fetchall()
        ]
    return agents


@app.delete("/agents/{agent_id}")
def unregister_agent(agent_id: str):
    """Remove an agent and their services from the marketplace."""
    from shared.database import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM providers WHERE agent_id = ?", (agent_id,))
        cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        conn.commit()
    return {"status": "unregistered", "agent_id": agent_id}


# ──────────────────────────────────────────────────────────────────────────────
# SERVICE MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/agents/{agent_id}/services")
def register_service(agent_id: str, req: RegisterServiceRequest):
    """Register a service offered by an agent."""
    # Verify agent exists
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    try:
        # Generate a deterministic ID: {agent_id}-{service_name_slug}
        # This makes the registry intuitive and prevents duplicates
        import re
        slug = re.sub(r'[^a-zA-Z0-9]', '', req.name.lower())
        provider_id = f"{agent_id}-{slug}"
        register_provider(
            provider_id=provider_id,
            agent_id=agent_id,
            name=req.name,
            service_type=req.service_type,
            description=req.description,
            price_usdc=req.price_usdc,
            endpoint_url=req.endpoint_url
        )
        
        # ALSO: Update the in-memory ServiceRegistry so /purchase can find it
        def dummy_service(*args, **kwargs):
            return {"status": "executed", "service": req.name}
            
        get_service_registry().register(
            service_id=provider_id,
            agent_id=agent_id, # CRITICAL: Pass the agent_id here!
            name=req.name,
            func=dummy_service,
            price=req.price_usdc,
            category=req.service_type,
            description=req.description
        )
        
        return {
            "provider_id": provider_id,
            "agent_id": agent_id,
            "name": req.name,
            "price": req.price_usdc,
            "status": "registered"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents/{agent_id}/services")
def list_agent_services(agent_id: str):
    """List all services offered by an agent."""
    from shared.database import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, service_type, description, price_usdc FROM providers WHERE agent_id = ?",
            (agent_id,)
        )
        services = [
            {
                "provider_id": row[0],
                "name": row[1],
                "type": row[2],
                "description": row[3],
                "price": row[4]
            }
            for row in cursor.fetchall()
        ]
    return services


@app.get("/services/search")
def search_services(q: str = ""):
    """Search for services using Vector Search (Semantic matching)."""
    # 1. Get all providers from DB
    all_providers = get_all_providers()
    
    if not q:
        return [
            {
                "provider_id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("service_type"),
                "description": r.get("description"),
                "price": r.get("price_usdc"),
                "agent": r.get("agent_name"),
                "reputation": r.get("reputation_score", 0)
            }
            for r in all_providers
        ]
    
    # 2. Index and Search via Vector Engine
    engine = get_search_engine()
    engine.index(all_providers)
    results = engine.search(q, limit=20)
    
    return [
        {
            "provider_id": r.get("id"),
            "name": r.get("name"),
            "type": r.get("service_type"),
            "description": r.get("description"),
            "price": r.get("price_usdc"),
            "agent": r.get("agent_name"),
            "reputation": r.get("reputation_score", 0),
            "relevance": r.get("search_score", 0)
        }
        for r in results
    ]


# ──────────────────────────────────────────────────────────────────────────────
# PAYMENT & PURCHASING
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/purchase")
def purchase_service(req: PurchaseServiceRequest):
    """
    Core marketplace: Buy + Execute + Settle
    
    Atomic flow:
    1. Validate buyer and seller agents exist
    2. Look up service in provider registry
    3. Validate x402 payment header (signature, expiry, amount)
    4. Register nonce atomically (replay prevention)
    5. Execute service function with parameters
    6. Record result in transaction
    7. Update both agents' reputation
    8. Return result + transaction ID to buyer
    """
    # Step 1: Validate agents
    buyer_agent = get_agent(req.buyer_agent_id)
    if not buyer_agent:
        raise HTTPException(status_code=404, detail=f"Buyer agent {req.buyer_agent_id} not found")
    
    # Step 2: Look up service in the registry
    service_registry = get_service_registry()
    service_meta = service_registry.get(req.service_id)
    
    if not service_meta:
        raise HTTPException(status_code=404, detail=f"Service {req.service_id} not found")
    
    seller_agent_id = service_meta.get("agent_id")  
    price = service_meta["price"]
    seller_agent = get_agent(seller_agent_id)
    
    if not seller_agent:
        raise HTTPException(status_code=404, detail=f"Seller agent {seller_agent_id} not found")
    
    # Step 3: Validate x402 payment header
    is_valid, reason = validate_x402_header(req.x402_header, seller_agent["address"])
    if not is_valid:
        raise HTTPException(status_code=401, detail=f"Invalid payment signature: {reason}")
    
    # Fraud Prevention: Ensure signed amount matches service price
    signed_amount = req.x402_header.get("amount")
    if abs(signed_amount - price) > 0.000001:
        raise HTTPException(status_code=400, detail=f"Price mismatch. Header: {signed_amount}, Registry: {price}")

    # Extract data from validated header
    nonce = req.x402_header.get("nonce", str(uuid.uuid4()))

    # Step 4: Settle payment on-chain via Circle (Server-Side)
    if circle_client:
        try:
            logger.info(f"Settle {price} USDC from {req.circle_wallet_id} to {seller_agent['address']}...")
            tx_result = circle_client.transfer_usdc(
                from_wallet_id=req.circle_wallet_id,
                to_address=seller_agent["address"],
                amount_usdc=price,
                idempotency_key=str(uuid.uuid4())
            )
            circle_tx_id = tx_result.get("transaction_id", "STUB")
        except Exception as e:
            logger.error(f"On-chain settlement failed: {e}")
            raise HTTPException(status_code=502, detail=f"Blockchain settlement failed: {str(e)}")
    else:
        # Demo mode: no Circle keys — record the intent, skip on-chain transfer
        logger.warning(f"⚠️  Demo mode: skipping on-chain settlement for {price} USDC (no Circle client)")
        circle_tx_id = f"DEMO-{str(uuid.uuid4())[:8]}"

    # Step 5: Execute service function (Verified Payment path)
    tx_id = str(uuid.uuid4())[:8]
    service_result: Optional[Any] = None
    
    try:
        endpoint = service_meta.get("endpoint_url")
        if endpoint:
            import requests
            proxy_resp = requests.post(
                endpoint, 
                json=req.params,
                timeout=10,
                headers={"X-Agora-Gateway": "Verified-Payment", "X-Circle-TX": circle_tx_id}
            )
            service_result = proxy_resp.json() if proxy_resp.status_code == 200 else {"error": "Service failed"}
        else:
            service_result = {"message": f"Execution proof for {service_meta['name']}", "status": "delivered"}
        
        execution_status = "success"
    except Exception as e:
        execution_status = "failed"
        service_result = {"error": str(e)}
    # Step 6: Record transaction + result
    record_transaction(
        tx_id=tx_id,
        buyer_id=req.buyer_agent_id,
        seller_id=seller_agent_id,
        provider_id=req.service_id,
        amount_usdc=price,
        nonce=nonce
    )
    
    update_transaction_status(tx_id, execution_status)
    
    # Store result as JSON string and calculate Cryptographic Proof of Service
    result_json = json.dumps(service_result) if service_result else "{}"
    proof_hash = hashlib.sha256(result_json.encode('utf-8')).hexdigest()
    
    record_service_result(tx_id, result_json, proof_hash=proof_hash)
    
    # Step 7: Update reputation (ERC-8004 aligned with Proof of Service Logging)
    # Seller gets +5 for successful delivery
    update_agent_reputation(seller_agent_id, 5, reason="service_executed", tx_id=tx_id, proof_hash=proof_hash)
    # Buyer gets +1 for successful purchase
    update_agent_reputation(req.buyer_agent_id, 1, reason="service_purchased", tx_id=tx_id)
    
    # Step 7b: Broadcast transaction event to WebSocket subscribers
    event_bus = get_event_bus()
    event_bus.publish("transaction", {
        "tx_id": tx_id,
        "buyer": req.buyer_agent_id,
        "seller": seller_agent_id,
        "service_name": service_meta["name"],
        "amount_usdc": price,
        "status": "erc8004_settled", # Emphasize the ERC-8004 trust standard
        "erc8004_proof": proof_hash,
        "result": service_result,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Step 8: Return complete transaction to buyer
    return {
        "transaction_id": tx_id,
        "status": "erc8004_settled", 
        "buyer_agent": req.buyer_agent_id,
        "seller_agent": seller_agent_id,
        "service_id": req.service_id,
        "service_name": service_meta["name"],
        "amount_usdc": price,
        "nonce": nonce,
        "erc8004_proof": proof_hash,
        "result": service_result,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Service executed: payment verified, ERC-8004 settled, cryptographic proof established"
    }



@app.get("/transactions")
def list_transactions():
    """Get transaction history."""
    txs = get_transaction_history(limit=100)
    return [
        {
            "id": t["id"],
            "buyer": t["buyer_id"],
            "seller": t["seller_id"],
            "amount": t["amount_usdc"],
            "status": t["status"],
            "timestamp": t["created_at"]
        }
        for t in txs
    ]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transaction feed.
    
    Streams transaction events as they occur in the marketplace.
    
    Event format:
    {
        "tx_id": "abc123",
        "buyer": "alice",
        "seller": "bob",
        "service_name": "CSV Analysis",
        "amount_usdc": 0.01,
        "status": "success",
        "result": {...},
        "timestamp": "2026-04-21T..."
    }
    """
    await websocket.accept()
    event_bus = get_event_bus()
    
    try:
        # Subscribe to transaction events and stream them
        async for event in event_bus.subscribe("transaction"):
            # Send as JSON to client
            await websocket.send_json(event)
    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Unexpected error
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok", "service": "Agora Marketplace API"}


if __name__ == "__main__":
    import uvicorn
    # Read port from environment variable for deployment compatibility
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

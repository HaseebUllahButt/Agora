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
from datetime import datetime
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from shared.database import (
    init_database, create_agent, register_provider, get_all_providers,
    search_providers, record_transaction, update_transaction_status,
    update_agent_reputation, get_agent, get_transaction_history,
    record_service_result, store_circle_credentials, get_circle_credentials,
    update_circle_wallet
)
from shared.ecdsa_signing import validate_x402_header
from shared.nonce_registry import register_nonce
from shared.arc_client import has_sufficient_balance
from shared.event_bus import get_event_bus
from sdk.provider import get_service_registry, call_service

load_dotenv()

app = FastAPI(title="Agora Marketplace", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialize database on startup
init_database()

# ──────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ──────────────────────────────────────────────────────────────────────────────

class RegisterAgentRequest(BaseModel):
    """Register a new agent (wallet) with Circle integration."""
    agent_id: str  
    name: str
    private_key: str  
    circle_api_key: str
    circle_entity_secret: str
    circle_wallet_set_id: str
    description: str = ""
    capabilities: list = []  


class RegisterServiceRequest(BaseModel):
    """Register a service offered by an agent."""
    name: str
    service_type: str  
    description: str
    price_usdc: float  


class PurchaseServiceRequest(BaseModel):
    """Buy a service."""
    service_id: str  
    buyer_agent_id: str
    buyer_private_key: str  
    params: dict = {}  


# ──────────────────────────────────────────────────────────────────────────────
# AGENT MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/agents/register")
async def register_agent(req: RegisterAgentRequest):
    """
    Register a new agent in the marketplace with Circle wallet creation.
    
    Agent must provide Circle credentials to transact on Arc.
    A Circle wallet will be created automatically on Arc testnet.
    """
    try:
        from sdk.agent import Agent
        from sdk.wallet import get_address_from_private_key
        
        # Create agent with Circle integration
        agent = Agent(
            agent_id=req.agent_id,
            name=req.name,
            private_key=req.private_key,
            circle_api_key=req.circle_api_key,
            circle_entity_secret=req.circle_entity_secret,
            circle_wallet_set_id=req.circle_wallet_set_id,
            description=req.description,
            capabilities=req.capabilities
        )
        
        # Register (creates Circle wallet)
        result = agent.register()
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents")
async def list_agents():
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


# ──────────────────────────────────────────────────────────────────────────────
# SERVICE MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/agents/{agent_id}/services")
async def register_service(agent_id: str, req: RegisterServiceRequest):
    """Register a service offered by an agent."""
    # Verify agent exists
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    try:
        provider_id = str(uuid.uuid4())[:8]
        register_provider(
            provider_id=provider_id,
            agent_id=agent_id,
            name=req.name,
            service_type=req.service_type,
            description=req.description,
            price_usdc=req.price_usdc
        )
        return {
            "provider_id": provider_id,
            "agent_id": agent_id,
            "name": req.name,
            "price": req.price_usdc,
            "status": "registered"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents/{agent_id}/services")
async def list_agent_services(agent_id: str):
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
async def search_services(q: str = ""):
    """Search for services by keyword."""
    if not q:
        results = get_all_providers()
    else:
        results = search_providers(q)
    
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
        for r in results
    ]


# ──────────────────────────────────────────────────────────────────────────────
# PAYMENT & PURCHASING
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/purchase")
async def purchase_service(req: PurchaseServiceRequest):
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
    nonce = str(uuid.uuid4())
    expiry = int(time.time()) + 60
    
    # Build x402 payload
    from shared.ecdsa_signing import sign_x402_header
    try:
        x402_header = sign_x402_header(
            private_key_hex=req.buyer_private_key,
            amount_usdc=price,
            sender=buyer_agent["address"],
            recipient=seller_agent["address"],
            nonce=nonce,
            expiry_timestamp=expiry
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to sign x402 header: {str(e)}")
    
    # Validate the header
    valid, reason = validate_x402_header(x402_header, seller_agent["address"])
    if not valid:
        raise HTTPException(status_code=401, detail=f"Payment validation failed: {reason}")
    
    # Pre-verify buyer has sufficient balance
    has_balance = has_sufficient_balance(buyer_agent["address"], price)
    if not has_balance:
        raise HTTPException(status_code=402, detail=f"Insufficient balance. Required: ${price:.6f}")
    
    # Step 4: Register nonce atomically
    nonce_ok, nonce_msg = register_nonce(req.buyer_agent_id, nonce)
    if not nonce_ok:
        raise HTTPException(status_code=409, detail=f"Nonce check failed: {nonce_msg}")
    
    # Step 5: Execute service function
    tx_id = str(uuid.uuid4())[:8]
    service_result: Optional[Any] = None
    
    try:
        # Call the registered service function with buyer's parameters
        service_result = call_service(req.service_id, **req.params)
        execution_status = "success"
    except Exception as e:
        execution_status = "failed"
        service_result = {"error": str(e)}
        raise HTTPException(status_code=500, detail=f"Service execution failed: {str(e)}")
    
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
    
    # Store result as JSON string
    result_json = json.dumps(service_result) if service_result else None
    record_service_result(tx_id, result_json)
    
    # Step 7: Update reputation
    # Seller gets +5 for successful delivery
    update_agent_reputation(seller_agent_id, 5, reason="service_executed", tx_id=tx_id)
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
        "status": execution_status,
        "result": service_result,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Step 8: Return complete transaction to buyer
    return {
        "transaction_id": tx_id,
        "status": execution_status,
        "buyer_agent": req.buyer_agent_id,
        "seller_agent": seller_agent_id,
        "service_id": req.service_id,
        "service_name": service_meta["name"],
        "amount_usdc": price,
        "nonce": nonce,
        "result": service_result,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Service executed: payment verified, result delivered"
    }



@app.get("/transactions")
async def list_transactions():
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
async def health():
    """Health check."""
    return {"status": "ok", "service": "Agora Marketplace API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

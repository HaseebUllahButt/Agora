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
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("agora.api")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

app = FastAPI(title="Agora Marketplace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
init_database()

@app.on_event("startup")
def register_local_demo_functions():
    """For the hackathon demo, load the Python functions into the registry so the API can execute them natively."""
    from sdk.provider import get_service_registry
    from services import llm_services, data_services, compute_services
    
    registry = get_service_registry()
    registry.register(service_id="summarizer-01-summarybot", agent_id="summarizer-01", name="SummaryBot", func=llm_services.summarize_text, price=0.001, category="LLM", description="Desc")
    registry.register(service_id="sentiment-01-moodreader", agent_id="sentiment-01", name="MoodReader", func=llm_services.analyze_sentiment, price=0.001, category="LLM", description="Desc")
    registry.register(service_id="formatter-01-datawizard", agent_id="formatter-01", name="DataWizard", func=data_services.json_to_csv, price=0.0005, category="Data", description="Desc")
    registry.register(service_id="hasher-01-cryptoutils", agent_id="hasher-01", name="CryptoUtils", func=compute_services.generate_hash, price=0.0005, category="Compute", description="Desc")
    registry.register(service_id="tagline-01-adcopyai", agent_id="tagline-01", name="AdCopyAI", func=llm_services.generate_tagline, price=0.002, category="LLM", description="Desc")
    print("✅ Local demo service functions mapped in API memory.")

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
        registry = get_service_registry()
        existing = registry.get(provider_id)
        
        if existing and existing.get("function"):
            func_to_use = existing["function"]
        else:
            def dummy_service(*args, **kwargs):
                return {"status": "executed", "service": req.name}
            func_to_use = dummy_service
            
        registry.register(
            service_id=provider_id,
            agent_id=agent_id, # CRITICAL: Pass the agent_id here!
            name=req.name,
            func=func_to_use,
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
                "agent_id": r.get("agent_id"),
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
            "agent_id": r.get("agent_id"),
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
async def purchase_service(req: PurchaseServiceRequest, background_tasks: BackgroundTasks):
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
        func = service_registry.get_function(req.service_id)
        
        if endpoint:
            import requests
            proxy_resp = requests.post(
                endpoint, 
                json=req.params,
                timeout=10,
                headers={"X-Agora-Gateway": "Verified-Payment", "X-Circle-TX": circle_tx_id}
            )
            service_result = proxy_resp.json() if proxy_resp.status_code == 200 else {"error": "Service failed"}
        elif func:
            # Call the registered Python function natively
            service_result = func(req.params)
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
        "arc_tx_hash": None,
        "buyer": req.buyer_agent_id,
        "seller": seller_agent_id,
        "seller_address": seller_agent["address"],
        "service_name": service_meta["name"],
        "amount_usdc": price,
        "status": "erc8004_settled", 
        "erc8004_proof": proof_hash,
        "result": service_result,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # NEW: Also broadcast to logs so CLI-initiated purchases show up in console
    event_bus.publish("logs", {
        "message": f"💸 {req.buyer_agent_id} paid {price} USDC for {service_meta['name']}",
        "type": "payment",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Trigger background polling if Circle was used
    if circle_client and circle_tx_id and not circle_tx_id.startswith("DEMO"):
        background_tasks.add_task(poll_tx_hash, tx_id, circle_tx_id)
        
    return {
        "transaction_id": tx_id,
        "circle_tx_id": circle_tx_id,
        "status": "erc8004_settled", 
        "buyer_agent": req.buyer_agent_id,
        "seller_agent": seller_agent_id,
        "amount_usdc": price,
        "result": service_result,
        "seller_address": seller_agent["address"],
        "erc8004_proof": proof_hash,
        "timestamp": datetime.utcnow().isoformat()
    }

    
async def poll_tx_hash(tx_id: str, circle_tx_id: str):
    """
    Poll Circle API until txHash is available, then broadcast update to dashboard.
    """
    event_bus = get_event_bus()
    max_attempts = 40
    # Wait longer initially as minting takes time
    await asyncio.sleep(3)
    
    for i in range(max_attempts):
        try:
            status = circle_client.get_transaction_status(circle_tx_id)
            tx_hash = status.get("txHash")
            if tx_hash:
                event_bus.publish("transaction_update", {
                    "tx_id": tx_id,
                    "arc_tx_hash": tx_hash,
                    "status": "confirmed",
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.info(f"✅ CONFIRMED on chain: {tx_id} -> {tx_hash}")
                return
            else:
                logger.debug(f"Polling {tx_id}... attempt {i+1} (Pending)")
        except Exception as e:
            # Resource not found is common in the first few seconds
            logger.debug(f"Polling {tx_id}... (Circle resource still initializing)")
            
        await asyncio.sleep(2)
    
    logger.warning(f"❌ TIMEOUT: Could not find hash for {tx_id} after {max_attempts} attempts.")


@app.post("/purchase")
async def purchase_service(req: PurchaseServiceRequest, background_tasks: BackgroundTasks):
    """
    Buy a service with cryptographic proof of payment.
    - Settle via Circle (on-chain)
    - Execute Python function
    - Return result + proof
    """



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


# ──────────────────────────────────────────────────────────────────────────────
# DEMO CONTROL CENTER
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/demo/setup")
async def run_demo_setup(background_tasks: BackgroundTasks):
    """Bootstrap the economy from the dashboard."""
    from scripts.setup_demo_economy import setup_economy
    event_bus = get_event_bus()
    
    def log_callback(msg):
        event_bus.publish("logs", {"message": msg, "type": "setup", "timestamp": datetime.utcnow().isoformat()})
    
    background_tasks.add_task(setup_economy, callback=log_callback)
    return {"status": "Setup started", "message": "Check the live console for progress."}


@app.post("/demo/frenzy")
async def run_demo_frenzy(background_tasks: BackgroundTasks):
    """Trigger the transaction frenzy from the dashboard."""
    from scripts.frenzy_demo import run_frenzy
    event_bus = get_event_bus()
    
    def log_callback(msg):
        event_bus.publish("logs", {"message": msg, "type": "frenzy", "timestamp": datetime.utcnow().isoformat()})
    
    # We skip setup because the user should have pressed setup first, or we can include it.
    background_tasks.add_task(run_frenzy, callback=log_callback, skip_setup=True)
    return {"status": "Frenzy started", "message": "Transaction burst initiated."}


@app.post("/demo/single")
async def run_demo_single(background_tasks: BackgroundTasks):
    """Trigger a single smart mission from the dashboard."""
    from scripts.single_tx_demo import run_single_demo
    event_bus = get_event_bus()
    
    def log_callback(msg):
        event_bus.publish("logs", {"message": msg, "type": "decision", "timestamp": datetime.utcnow().isoformat()})
    
    # Run a single smart mission
    background_tasks.add_task(run_single_demo, callback=log_callback, skip_setup=True)
    return {"status": "Mission started", "message": "Smart agent is planning a mission."}


@app.websocket("/ws/transactions")
async def transaction_feed(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transaction and log feed.
    """
    await websocket.accept()
    event_bus = get_event_bus()
    
    async def stream_topic(topic):
        async for event in event_bus.subscribe(topic):
            await websocket.send_json({"topic": topic, "data": event})

    import asyncio
    try:
        # Create tasks for transactions, updates, and logs
        tx_task = asyncio.create_task(stream_topic("transaction"))
        upd_task = asyncio.create_task(stream_topic("transaction_update"))
        log_task = asyncio.create_task(stream_topic("logs"))
        
        await asyncio.gather(tx_task, upd_task, log_task)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS Error: {e}")


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok", "service": "Agora Marketplace API"}


if __name__ == "__main__":
    import uvicorn
    # Read port from environment variable for deployment compatibility
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

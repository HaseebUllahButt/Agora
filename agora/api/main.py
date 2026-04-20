"""
api/main.py — Port 8000

Agora main API: REST + WebSocket gateway.

Endpoints:
  POST /run         — Submit a research task, runs full pipeline
  GET  /agents      — List registered agents and their prices
  GET  /health      — Health check
  WS   /ws          — WebSocket for real-time pipeline events

WebSocket events broadcast:
  pipeline_started    — pipeline kicked off, budget and loop count
  loop_start          — each research loop begins, query shown
  payment_initiated   — about to send Nanopayment to an agent
  payment_confirmed   — Nanopayment on-chain, tx hash available
  fraud_detected      — output validator flagged an agent's response
  pipeline_complete   — all done, final stats
"""

import os
import sys
import asyncio
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from orchestrator.orchestrator import run_agora_pipeline

load_dotenv()

app = FastAPI(
    title="Agora API",
    description="Autonomous Research Protocol on Arc — competitive intelligence via AI Nanopayments",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── WebSocket connection manager ───────────────────────────────────────────────
active_connections: list[WebSocket] = []


async def broadcast(message: dict) -> None:
    """Broadcast a JSON message to all connected WebSocket clients."""
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive — client sends pings
            await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
    except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
        if websocket in active_connections:
            active_connections.remove(websocket)


# ── Request models ─────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    topic: str
    budget: float                  # user-set USDC budget, minimum $0.05
    task_type: str = "competitive_intelligence"
    include_consultancy: bool = False
    company_context: dict = {
        "company_size": "startup",
        "stage": "seed",
        "main_strength": "engineering",
        "main_weakness": "distribution",
        "budget": "limited",
        "target_market": "SMBs"
    }


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.post("/run")
async def run_task(request: TaskRequest):
    """
    Submit a research task and run the full Agora agent pipeline.

    Budget determines depth:
      $0.05  → ~5 loops  → ~10 transactions
      $0.10  → ~10 loops → ~20 transactions
      $0.50  → ~50 loops → ~100 transactions (capped at 25 loops)

    All WebSocket clients receive real-time events throughout.
    """
    if request.budget < 0.05:
        return {"error": "Minimum budget is $0.05 USDC"}

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or groq_key == "your_groq_api_key_here":
        return {
            "error": (
                "GROQ_API_KEY is not configured. "
                "Set a valid key in .env before running the paid pipeline."
            )
        }

    result = await run_agora_pipeline(
        topic=request.topic,
        user_budget=request.budget,
        company_context=request.company_context,
        task_type=request.task_type,
        include_consultancy=request.include_consultancy,
        websocket_emit=broadcast
    )
    return result


@app.get("/agents")
async def list_agents():
    """List all registered active agents with their capabilities and prices."""
    from shared.agent_registry import get_active_agents
    agents = get_active_agents()
    # Remove internal wallet_id for public API
    return {
        k: {
            "name": v["name"],
            "endpoint": v["endpoint"],
            "wallet_address": v["wallet_address"],
            "price_per_call": v["price_per_call"],
            "capability": v["capability"],
            "active": v["active"]
        }
        for k, v in agents.items()
    }


@app.get("/health")
async def health():
    return {
        "status": "running",
        "service": "Agora API",
        "version": "1.0.0",
        "active_connections": len(active_connections)
    }

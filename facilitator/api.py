"""
Marketplace + x402 facilitator service.

Endpoints
---------

* ``POST /facilitator/verify``          — verify an x402 payment header.
* ``POST /facilitator/settle``          — settle a verified payment, skim fee.
* ``POST /agents/register``             — list an agent (charges listing fee).
* ``POST /services/register``           — list a service belonging to an agent.
* ``GET  /agents``                      — list registered agents.
* ``GET  /services``                    — list registered services.
* ``GET  /transactions``                — settlement ledger (gross/fee/net).
* ``GET  /marketplace/fees``            — current listing + per-tx fees.
* ``GET  /marketplace/treasury``        — total fees collected.
* ``GET  /health``                      — liveness probe.

Run with::

    uvicorn facilitator.api:app --reload --port 8000
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from agora_x402.x402_protocol import verify_payment_header
from facilitator import db
from facilitator.fees import load_fees
from facilitator.nonce import consume_nonce
from facilitator.settlement import get_settler

# ────────────────────────────────────────────────────────────────────────────
# App + bootstrap
# ────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Agora x402 Facilitator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    fees = load_fees()
    settler = get_settler()
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║              Agora x402 Facilitator                  ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print(f"   DB              : {db.DB_PATH}")
    print(f"   Settlement mode : {settler.mode}")
    print(f"   Listing fee     : {fees.listing_fee_usdc} USDC")
    print(f"   Per-tx fee      : {fees.tx_fee_bps} bps  ({fees.tx_fee_bps / 100:.2f}%)")
    print(f"   Treasury        : {fees.treasury_address}")
    print()


# ────────────────────────────────────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────────────────────────────────────


class VerifyRequest(BaseModel):
    payment_payload: dict
    expected_recipient: str
    expected_resource: str
    min_amount: str


class SettleRequest(BaseModel):
    payment_payload: dict
    seller_agent_id: str
    service_id: Optional[str] = None


class RegisterAgentRequest(BaseModel):
    agent_id: str
    name: str
    address: str
    endpoint_url: str
    description: str = ""
    listing_fee_payment: Optional[dict] = Field(
        default=None,
        description="Signed x402 payload paying the listing fee to the marketplace treasury.",
    )


class RegisterServiceRequest(BaseModel):
    agent_id: str
    service_id: str
    name: str
    description: str = ""
    category: str = "capability"
    price_usdc: str
    endpoint_url: str


# ────────────────────────────────────────────────────────────────────────────
# Verify
# ────────────────────────────────────────────────────────────────────────────


@app.post("/facilitator/verify")
def verify(req: VerifyRequest) -> dict:
    """Verify a payment header and atomically burn its nonce."""
    payload = req.payment_payload

    ok, reason = verify_payment_header(
        payload,
        expected_recipient=req.expected_recipient,
        expected_resource=req.expected_resource,
        min_amount=req.min_amount,
    )
    if not ok:
        return {"valid": False, "reason": reason}

    # Atomic nonce check
    nonce_ok, nonce_reason = consume_nonce(
        nonce=str(payload["nonce"]),
        sender=str(payload["sender"]),
        resource=str(payload["resource"]),
        amount=float(payload["amount"]),
    )
    if not nonce_ok:
        return {"valid": False, "reason": nonce_reason}

    return {"valid": True, "reason": "OK", "nonce": payload["nonce"]}


# ────────────────────────────────────────────────────────────────────────────
# Settle (with marketplace fee skim)
# ────────────────────────────────────────────────────────────────────────────


@app.post("/facilitator/settle")
def settle(req: SettleRequest) -> dict:
    """Move USDC from buyer → seller, taking the marketplace fee out of the gross.

    Pre-condition: the corresponding header has already passed
    ``/facilitator/verify`` (which burned the nonce). Re-checking the signature
    here is cheap and keeps settle independently safe to call.
    """
    payload = req.payment_payload

    # Defence in depth: re-verify the signature
    seller_agent = db.get_agent(req.seller_agent_id)
    if not seller_agent:
        raise HTTPException(404, f"Unknown seller agent: {req.seller_agent_id}")

    ok, reason = verify_payment_header(
        payload,
        expected_recipient=seller_agent["address"],
        expected_resource=str(payload.get("resource", "")),
        min_amount=str(payload.get("amount", "0")),
    )
    if not ok:
        raise HTTPException(400, f"Invalid payment payload: {reason}")

    fees = load_fees()
    gross = float(payload["amount"])
    fee, net = fees.split(gross)

    settler = get_settler()
    tx_id = uuid.uuid4().hex[:12]

    # Net to seller
    seller_settlement = settler.transfer(
        from_address=str(payload["sender"]),
        to_address=seller_agent["address"],
        amount_usdc=net,
        memo=f"agora:service:{req.service_id or '-'}",
    )

    # Marketplace fee → treasury
    fee_settlement = None
    if fee > 0:
        fee_settlement = settler.transfer(
            from_address=str(payload["sender"]),
            to_address=fees.treasury_address,
            amount_usdc=fee,
            memo=f"agora:marketplace_fee:{tx_id}",
        )
        db.append_treasury(tx_id, fee, "service")

    db.insert_transaction(
        id=tx_id,
        buyer_address=str(payload["sender"]),
        seller_agent_id=req.seller_agent_id,
        seller_address=seller_agent["address"],
        service_id=req.service_id,
        resource=str(payload.get("resource", "")),
        gross_usdc=gross,
        marketplace_fee_usdc=fee,
        net_usdc=net,
        kind="service",
        settlement_mode=settler.mode,
        settlement_ref=seller_settlement.settlement_ref,
        status="settled",
        nonce=str(payload["nonce"]),
        created_at=datetime.utcnow().isoformat(),
    )

    return {
        "tx_id": tx_id,
        "status": "settled",
        "gross_usdc": gross,
        "marketplace_fee_usdc": fee,
        "net_usdc": net,
        "seller_address": seller_agent["address"],
        "treasury_address": fees.treasury_address,
        "settlement_mode": settler.mode,
        "seller_settlement_ref": seller_settlement.settlement_ref,
        "fee_settlement_ref": fee_settlement.settlement_ref if fee_settlement else None,
    }


# ────────────────────────────────────────────────────────────────────────────
# Marketplace registry
# ────────────────────────────────────────────────────────────────────────────


@app.get("/marketplace/fees")
def marketplace_fees() -> dict:
    fees = load_fees()
    return {
        "listing_fee_usdc": fees.listing_fee_usdc,
        "tx_fee_bps": fees.tx_fee_bps,
        "tx_fee_pct": fees.tx_fee_bps / 100,
        "treasury_address": fees.treasury_address,
    }


@app.get("/marketplace/treasury")
def marketplace_treasury() -> dict:
    return {"treasury_balance_usdc": db.treasury_total()}


@app.post("/agents/register")
def register_agent(req: RegisterAgentRequest) -> dict:
    """List an agent on the marketplace.

    Charges the listing fee from the agent's wallet to the marketplace treasury.
    Listing fee can be ``0`` (in which case no payment payload is required).
    """
    fees = load_fees()
    listing_tx_id: Optional[str] = None
    paid = 0.0

    if fees.listing_fee_usdc > 0:
        if not req.listing_fee_payment:
            raise HTTPException(
                402,
                detail={
                    "error": "listing_fee_required",
                    "amount_usdc": fees.listing_fee_usdc,
                    "treasury_address": fees.treasury_address,
                    "asset": "USDC",
                },
            )

        # Verify the listing payment
        payload = req.listing_fee_payment
        ok, reason = verify_payment_header(
            payload,
            expected_recipient=fees.treasury_address,
            expected_resource=None,  # any resource string is fine for listing
            min_amount=str(fees.listing_fee_usdc),
        )
        if not ok:
            raise HTTPException(400, f"Invalid listing payment: {reason}")

        # Burn nonce
        nonce_ok, nonce_reason = consume_nonce(
            nonce=str(payload["nonce"]),
            sender=str(payload["sender"]),
            resource=str(payload.get("resource", "agents/register")),
            amount=float(payload["amount"]),
        )
        if not nonce_ok:
            raise HTTPException(400, f"Listing payment nonce: {nonce_reason}")

        # Settle the listing fee → 100% to treasury (no skim on the skim)
        settler = get_settler()
        listing_tx_id = uuid.uuid4().hex[:12]
        settlement = settler.transfer(
            from_address=str(payload["sender"]),
            to_address=fees.treasury_address,
            amount_usdc=fees.listing_fee_usdc,
            memo=f"agora:listing_fee:{req.agent_id}",
        )
        db.insert_transaction(
            id=listing_tx_id,
            buyer_address=str(payload["sender"]),
            seller_agent_id=None,
            seller_address=fees.treasury_address,
            service_id=None,
            resource="agents/register",
            gross_usdc=fees.listing_fee_usdc,
            marketplace_fee_usdc=fees.listing_fee_usdc,
            net_usdc=0,
            kind="listing_fee",
            settlement_mode=settler.mode,
            settlement_ref=settlement.settlement_ref,
            status="settled",
            nonce=str(payload["nonce"]),
            created_at=datetime.utcnow().isoformat(),
        )
        db.append_treasury(listing_tx_id, fees.listing_fee_usdc, "listing_fee")
        paid = fees.listing_fee_usdc

    db.upsert_agent(
        agent_id=req.agent_id,
        name=req.name,
        address=req.address,
        endpoint_url=req.endpoint_url,
        description=req.description,
        listing_fee_paid=paid,
        listing_tx_id=listing_tx_id,
    )

    return {
        "agent_id": req.agent_id,
        "status": "registered",
        "listing_fee_paid_usdc": paid,
        "listing_tx_id": listing_tx_id,
    }


@app.post("/services/register")
def register_service(req: RegisterServiceRequest) -> dict:
    """List a service belonging to a registered agent."""
    if not db.get_agent(req.agent_id):
        raise HTTPException(404, f"Agent {req.agent_id} not registered")

    db.upsert_service(
        service_id=req.service_id,
        agent_id=req.agent_id,
        name=req.name,
        description=req.description,
        category=req.category,
        price_usdc=float(req.price_usdc),
        endpoint_url=req.endpoint_url,
    )
    return {"service_id": req.service_id, "status": "registered"}


@app.get("/agents")
def get_agents() -> dict:
    return {"agents": db.list_agents()}


@app.get("/services")
def get_services() -> dict:
    return {"services": db.list_services()}


@app.get("/transactions")
def get_transactions(limit: int = 50) -> dict:
    return {"transactions": db.list_transactions(limit=limit)}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "agora-x402-facilitator"}


# ────────────────────────────────────────────────────────────────────────────
# Entrypoint for `agora-facilitator` console script
# ────────────────────────────────────────────────────────────────────────────


def run() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("facilitator.api:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()

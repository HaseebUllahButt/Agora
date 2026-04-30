"""
Thin HTTP client for the marketplace facilitator.

Agent servers use this to delegate signature verification + on-chain settlement
to the marketplace, instead of every agent embedding Circle credentials.

The facilitator exposes:

  POST /facilitator/verify        — does the X-PAYMENT match the requirements?
  POST /facilitator/settle        — please move USDC + record the transaction.
  POST /agents/register           — list an agent (charges listing fee).
  GET  /agents                    — list registered agents.
  GET  /services                  — list registered services.
  GET  /transactions              — settlement history (with marketplace fee).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from agora_x402.exceptions import FacilitatorUnreachable, SettlementFailed


class FacilitatorClient:
    """Synchronous facilitator client.

    Async support isn't needed: agent endpoints make a single round-trip per
    request, and FastAPI handlers are happy to call sync code in a thread
    via ``run_in_threadpool``.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        # trust_env=False to ignore sandbox/CI proxies for localhost calls
        self._client = httpx.Client(
            base_url=self.base_url, timeout=timeout, trust_env=False
        )

    # ── Verification ────────────────────────────────────────────────────────
    def verify(
        self,
        *,
        payment_payload: dict,
        expected_recipient: str,
        expected_resource: str,
        min_amount: str,
    ) -> dict:
        """Ask the facilitator to verify a payment payload.

        The facilitator confirms signature, expiry, recipient, resource, and
        minimum amount, AND that the nonce is unused (atomically marking it).
        """
        try:
            resp = self._client.post(
                "/facilitator/verify",
                json={
                    "payment_payload": payment_payload,
                    "expected_recipient": expected_recipient,
                    "expected_resource": expected_resource,
                    "min_amount": min_amount,
                },
            )
        except httpx.HTTPError as e:
            raise FacilitatorUnreachable(
                f"Could not reach facilitator at {self.base_url}: {e}"
            ) from e

        body = _safe_json(resp)
        if resp.status_code != 200 or not body.get("valid"):
            return {"valid": False, "reason": body.get("reason", f"HTTP {resp.status_code}")}
        return body

    # ── Settlement ──────────────────────────────────────────────────────────
    def settle(
        self,
        *,
        payment_payload: dict,
        seller_agent_id: str,
        service_id: str,
    ) -> dict:
        """Settle a verified payment. Returns the settlement record on success.

        The facilitator skims a marketplace fee from the gross amount before
        forwarding net USDC to the seller's wallet.
        """
        try:
            resp = self._client.post(
                "/facilitator/settle",
                json={
                    "payment_payload": payment_payload,
                    "seller_agent_id": seller_agent_id,
                    "service_id": service_id,
                },
            )
        except httpx.HTTPError as e:
            raise FacilitatorUnreachable(
                f"Could not reach facilitator at {self.base_url}: {e}"
            ) from e

        body = _safe_json(resp)
        if resp.status_code != 200:
            raise SettlementFailed(
                body.get("detail") or body.get("reason") or f"HTTP {resp.status_code}",
                raw=body,
            )
        return body

    # ── Marketplace registry ────────────────────────────────────────────────
    def register_agent(
        self,
        *,
        agent_id: str,
        name: str,
        address: str,
        endpoint_url: str,
        description: str = "",
        listing_fee_payment: Optional[dict] = None,
    ) -> dict:
        """Register an agent with the marketplace.

        ``listing_fee_payment`` is a signed x402 payload paying the listing fee
        to the marketplace treasury. It can be omitted if the marketplace
        listing fee is configured to ``0``.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "name": name,
            "address": address,
            "endpoint_url": endpoint_url,
            "description": description,
        }
        if listing_fee_payment is not None:
            payload["listing_fee_payment"] = listing_fee_payment

        resp = self._client.post("/agents/register", json=payload)
        body = _safe_json(resp)
        if resp.status_code >= 400:
            raise SettlementFailed(
                body.get("detail") or f"register_agent failed: HTTP {resp.status_code}",
                raw=body,
            )
        return body

    def register_service(
        self,
        *,
        agent_id: str,
        service_id: str,
        name: str,
        description: str,
        price: str,
        category: str,
        endpoint_url: str,
    ) -> dict:
        resp = self._client.post(
            "/services/register",
            json={
                "agent_id": agent_id,
                "service_id": service_id,
                "name": name,
                "description": description,
                "price_usdc": price,
                "category": category,
                "endpoint_url": endpoint_url,
            },
        )
        body = _safe_json(resp)
        if resp.status_code >= 400:
            raise SettlementFailed(
                body.get("detail") or f"register_service failed: HTTP {resp.status_code}",
                raw=body,
            )
        return body

    def get_listing_fee(self) -> dict:
        resp = self._client.get("/marketplace/fees")
        return _safe_json(resp)

    def list_agents(self) -> list[dict]:
        resp = self._client.get("/agents")
        return _safe_json(resp).get("agents", [])

    def list_services(self) -> list[dict]:
        resp = self._client.get("/services")
        return _safe_json(resp).get("services", [])

    def list_transactions(self, limit: int = 50) -> list[dict]:
        resp = self._client.get("/transactions", params={"limit": limit})
        return _safe_json(resp).get("transactions", [])

    def close(self) -> None:
        self._client.close()


def _safe_json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {"detail": resp.text}

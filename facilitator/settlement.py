"""
Settlement abstraction.

Two backends:

* ``mock`` — pure local accounting. The facilitator records every transfer in
  SQLite. Perfect for the demo and CI.
* ``circle`` — calls Circle Programmable Wallets to actually move USDC on
  Arc-testnet. Requires CIRCLE_API_KEY + CIRCLE_ENTITY_SECRET.

The agent server doesn't care which backend is in use — it just calls the
facilitator's ``/facilitator/settle`` endpoint.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class SettlementResult:
    settlement_ref: str
    mode: str
    raw: dict


class Settler:
    """Base class. ``transfer`` returns a settlement reference (id + raw)."""

    mode = "abstract"

    def transfer(
        self,
        *,
        from_address: str,
        to_address: str,
        amount_usdc: float,
        memo: str = "",
    ) -> SettlementResult:
        raise NotImplementedError


# ── Mock backend ────────────────────────────────────────────────────────────


class MockSettler(Settler):
    """No external calls — just emits a deterministic-looking ref."""

    mode = "mock"

    def transfer(self, *, from_address, to_address, amount_usdc, memo=""):
        ref = f"MOCK-{uuid.uuid4().hex[:12]}"
        return SettlementResult(
            settlement_ref=ref,
            mode=self.mode,
            raw={
                "from": from_address,
                "to": to_address,
                "amount_usdc": amount_usdc,
                "memo": memo,
                "settled_at": "now",
            },
        )


# ── Circle backend ──────────────────────────────────────────────────────────


class CircleSettler(Settler):
    """Real settlement via Circle Programmable Wallets on Arc-testnet.

    Imports the Circle SDK lazily so the demo doesn't need it installed.
    """

    mode = "circle"

    def __init__(self):
        api_key = os.getenv("CIRCLE_API_KEY")
        entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
        if not api_key or not entity_secret:
            raise RuntimeError(
                "SETTLEMENT_MODE=circle but CIRCLE_API_KEY / CIRCLE_ENTITY_SECRET not set."
            )
        self.api_key = api_key
        self.entity_secret = entity_secret
        self.wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
        self.blockchain = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")
        # Demo simplification: every transfer sources USDC from a single
        # master wallet, regardless of which agent "logically" owes the money
        # in the x402 header. This avoids needing one Circle wallet per agent
        # for the demo. In a real deployment, each agent would have its own
        # Circle wallet and the buyer-side payments would source from there.
        self.master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID")
        # Optional per-agent override map: address -> wallet_id
        self._wallet_index: dict[str, str] = {}

    def register_wallet(self, address: str, wallet_id: str) -> None:
        self._wallet_index[address.lower()] = wallet_id

    def transfer(self, *, from_address, to_address, amount_usdc, memo=""):
        import httpx

        # Per-agent wallet wins; otherwise fall back to the master wallet.
        wallet_id = self._wallet_index.get(from_address.lower()) or self.master_wallet_id
        if not wallet_id:
            raise RuntimeError(
                f"No Circle wallet registered for {from_address} and no "
                f"CIRCLE_MASTER_WALLET_ID set in the environment."
            )

        # Lazy import — same pattern as agora's CircleClient
        try:
            from circle.web3 import utils as circle_utils

            ciphertext = circle_utils.generate_entity_secret_ciphertext(
                self.api_key, self.entity_secret
            )
        except Exception as e:
            raise RuntimeError(f"Circle SDK error: {e}") from e

        payload = {
            "idempotencyKey": str(uuid.uuid4()),
            "amounts": [str(amount_usdc)],
            "blockchain": self.blockchain,
            "destinationAddress": to_address,
            "feeLevel": "MEDIUM",
            "walletId": wallet_id,
            "entitySecretCiphertext": ciphertext,
        }
        with httpx.Client(headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30, trust_env=False) as c:
            resp = c.post("https://api.circle.com/v1/w3s/developer/transactions/transfer", json=payload)
        if resp.status_code != 201:
            raise RuntimeError(f"Circle transfer failed: {resp.text}")
        data = resp.json().get("data", {})
        return SettlementResult(
            settlement_ref=data.get("id", "circle-?"),
            mode=self.mode,
            raw=data,
        )


# ── Factory ─────────────────────────────────────────────────────────────────


_settler: Optional[Settler] = None


def get_settler() -> Settler:
    global _settler
    if _settler is not None:
        return _settler

    mode = os.getenv("SETTLEMENT_MODE", "mock").lower()
    if mode == "circle":
        _settler = CircleSettler()
    else:
        _settler = MockSettler()
    return _settler

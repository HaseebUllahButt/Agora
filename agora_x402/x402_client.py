"""
x402-aware HTTP client.

Drop-in replacement for "I want to call another agent's endpoint and pay
for it":

    from agora_x402 import X402Client, Wallet

    client = X402Client(wallet=Wallet.from_env("BUYER_PRIVATE_KEY"))
    result = client.post(
        "http://localhost:9001/summarize",
        json={"text": "..."},
    )

Internally the client makes the request, expects a 402 with payment
requirements, signs an X-PAYMENT, and retries once.

Auto-pay caps
-------------
``max_price`` and ``allowed_recipients`` give you guard-rails so a misbehaving
remote can't trick you into paying $1000 USDC. ``PaymentRequired`` is raised
if either limit is exceeded.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import httpx

from agora_x402.exceptions import PaymentRequired
from agora_x402.wallet import Wallet
from agora_x402.x402_protocol import (
    PaymentRequirements,
    X402_HEADER,
    encode_payment_header,
    sign_payment_header,
)


class X402Client:
    """Synchronous HTTP client that auto-pays x402 challenges."""

    def __init__(
        self,
        wallet: Wallet,
        *,
        max_price: Optional[str] = None,
        allowed_recipients: Optional[Iterable[str]] = None,
        timeout: float = 30.0,
        auto_pay: bool = True,
    ):
        self.wallet = wallet
        self.max_price = max_price
        self.allowed_recipients = (
            {a.lower() for a in allowed_recipients} if allowed_recipients else None
        )
        self.auto_pay = auto_pay
        # trust_env=False so sandbox/CI proxies (e.g. SOCKS) don't break
        # in-cluster localhost calls. Set ``HTTP_PROXY`` etc. via httpx args
        # explicitly if you need proxying.
        self._http = httpx.Client(timeout=timeout, trust_env=False)

    # ── HTTP verbs ──────────────────────────────────────────────────────────
    def get(self, url: str, **kwargs) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self._request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        return self._request(method, url, **kwargs)

    # ── Internals ───────────────────────────────────────────────────────────
    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        # First attempt
        resp = self._http.request(method, url, **kwargs)
        if resp.status_code != 402 or not self.auto_pay:
            return resp

        # Parse payment requirements from the 402 body
        try:
            body = resp.json()
        except ValueError as e:
            raise PaymentRequired(f"402 with non-JSON body from {url}: {e}") from e

        accepts = body.get("accepts") or []
        if not accepts:
            raise PaymentRequired(
                f"402 from {url} did not advertise any accepted payment options",
                requirements=body,
            )

        # Pick the first scheme we support — we only speak agora-ecdsa-v1 today
        for raw_req in accepts:
            req = PaymentRequirements.from_dict(raw_req)
            if req.scheme != "agora-ecdsa-v1":
                continue

            self._enforce_safety(req, url)
            payload = sign_payment_header(
                private_key_hex=self.wallet.private_key,
                amount=req.amount,
                sender=self.wallet.address,
                recipient=req.recipient,
                resource=req.resource or url,
                network=req.network,
                asset=req.asset,
                expiry_seconds=min(req.max_timeout_seconds, 120),
            )
            header_value = encode_payment_header(payload)

            # Retry with X-PAYMENT
            headers = dict(kwargs.pop("headers", {}) or {})
            headers[X402_HEADER] = header_value
            return self._http.request(method, url, headers=headers, **kwargs)

        raise PaymentRequired(
            f"402 from {url} did not advertise a scheme this client supports.",
            requirements=body,
        )

    def _enforce_safety(self, req: PaymentRequirements, url: str) -> None:
        if self.max_price is not None and float(req.amount) > float(self.max_price):
            raise PaymentRequired(
                f"{url} demands {req.amount} {req.asset} but max_price is {self.max_price}",
                requirements=req.to_dict(),
            )
        if self.allowed_recipients is not None and req.recipient.lower() not in self.allowed_recipients:
            raise PaymentRequired(
                f"{url} pays to {req.recipient}, which is not in the allow-list",
                requirements=req.to_dict(),
            )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()

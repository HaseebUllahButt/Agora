"""
AgentServer — turns a pile of @pay_for-decorated functions into a standalone
FastAPI application that speaks the x402 protocol.

How a request flows
-------------------

1. ``POST /summarize {"text": "..."}``
2. Server has not seen ``X-PAYMENT`` → returns ``402 Payment Required`` with
   a body advertising ``PaymentRequirements`` (price, recipient, resource).
3. Caller (typically :class:`X402Client`) signs an x402 payload and retries
   with ``X-PAYMENT: base64(json(payload))``.
4. Server decodes + verifies (locally + via facilitator), settles via the
   facilitator (which moves USDC + skims the marketplace fee), then runs the
   underlying Python function.
5. Server returns ``200`` with the result, plus an ``X-PAYMENT-RESPONSE``
   header carrying the settlement record.

Verification model
------------------
Local signature check ALWAYS runs (cheap, safe). Facilitator verification
is invoked because only the facilitator can atomically burn the nonce + move
the funds — without that hop, an attacker could replay a valid header against
multiple agents.
"""

from __future__ import annotations

import base64
import inspect
import json
import os
from dataclasses import asdict
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agora_x402.exceptions import SettlementFailed
from agora_x402.facilitator_client import FacilitatorClient
from agora_x402.pay_for import ServiceSpec, get_service_registry
from agora_x402.wallet import Wallet
from agora_x402.x402_protocol import (
    PaymentRequirements,
    X402_HEADER,
    decode_payment_header,
    verify_payment_header,
)


class AgentServer:
    """Wraps a registered set of @pay_for services as a paid HTTP service."""

    def __init__(
        self,
        *,
        agent_id: str,
        name: str,
        wallet: Wallet,
        description: str = "",
        facilitator_url: Optional[str] = None,
        public_base_url: Optional[str] = None,
        require_facilitator: bool = True,
    ):
        self.agent_id = agent_id
        self.name = name
        self.wallet = wallet
        self.description = description
        self.facilitator_url = facilitator_url or os.getenv(
            "FACILITATOR_URL", "http://localhost:8000"
        )
        self.public_base_url = public_base_url
        self.require_facilitator = require_facilitator

        self._facilitator: Optional[FacilitatorClient] = None
        self._app = FastAPI(title=f"{name} (Agora x402 agent)")
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._mount_meta_routes()
        self._mount_service_routes()

    # ── App surface ─────────────────────────────────────────────────────────
    @property
    def app(self) -> FastAPI:
        return self._app

    def _facilitator_client(self) -> FacilitatorClient:
        if self._facilitator is None:
            self._facilitator = FacilitatorClient(self.facilitator_url)
        return self._facilitator

    def run(self, *, host: str = "0.0.0.0", port: int = 9001) -> None:
        import uvicorn

        if self.public_base_url is None:
            self.public_base_url = f"http://localhost:{port}"
        self._print_banner(host, port)
        uvicorn.run(self._app, host=host, port=port, log_level="info")

    # ── Meta endpoints ──────────────────────────────────────────────────────
    def _mount_meta_routes(self) -> None:
        registry = get_service_registry()

        @self._app.get("/")
        def root():
            return {
                "agent_id": self.agent_id,
                "name": self.name,
                "description": self.description,
                "wallet_address": self.wallet.address,
                "facilitator_url": self.facilitator_url,
                "services": [
                    {
                        "service_id": s.service_id,
                        "name": s.name,
                        "path": s.path,
                        "method": s.method,
                        "price_usdc": s.price,
                        "category": s.category,
                        "description": s.description,
                        "params": s.signature_params(),
                    }
                    for s in registry.all().values()
                ],
            }

        @self._app.get("/health")
        def health():
            return {"status": "ok", "agent_id": self.agent_id}

    # ── Per-service routes ──────────────────────────────────────────────────
    def _mount_service_routes(self) -> None:
        registry = get_service_registry()
        for spec in registry.all().values():
            self._mount_route(spec)

    def _mount_route(self, spec: ServiceSpec) -> None:
        handler = self._build_handler(spec)
        # Register on FastAPI under the spec's method+path
        self._app.add_api_route(
            spec.path,
            handler,
            methods=[spec.method],
            name=spec.service_id,
            summary=f"{spec.name} — costs {spec.price} USDC",
            description=spec.description,
        )

    def _build_handler(self, spec: ServiceSpec) -> Callable:
        async def handler(request: Request) -> Response:
            resource_url = self._resource_url(request, spec)

            payment_header = request.headers.get(X402_HEADER)
            if not payment_header:
                return self._challenge_response(spec, resource_url)

            # 1. Decode + locally verify the header
            try:
                payload = decode_payment_header(payment_header)
            except ValueError as e:
                return JSONResponse(
                    {"error": "invalid_x402_header", "detail": str(e)}, status_code=400
                )

            ok, reason = verify_payment_header(
                payload,
                expected_recipient=self.wallet.address,
                expected_resource=resource_url,
                min_amount=spec.price,
            )
            if not ok:
                return JSONResponse(
                    {"error": "invalid_x402_header", "detail": reason}, status_code=402
                )

            # 2. Ask the facilitator to verify (burns nonce atomically)
            if self.require_facilitator:
                vresp = self._facilitator_client().verify(
                    payment_payload=payload,
                    expected_recipient=self.wallet.address,
                    expected_resource=resource_url,
                    min_amount=spec.price,
                )
                if not vresp.get("valid"):
                    return JSONResponse(
                        {
                            "error": "facilitator_rejected",
                            "detail": vresp.get("reason", "unknown"),
                        },
                        status_code=402,
                    )

            # 3. Parse params (JSON body or query, depending on the method)
            try:
                kwargs = await self._extract_kwargs(request, spec)
            except ValueError as e:
                return JSONResponse(
                    {"error": "bad_request", "detail": str(e)}, status_code=400
                )

            # 4. Execute the service
            try:
                if inspect.iscoroutinefunction(spec.func):
                    result = await spec.func(**kwargs)
                else:
                    result = spec.func(**kwargs)
            except TypeError as e:
                return JSONResponse(
                    {"error": "bad_params", "detail": str(e)}, status_code=400
                )
            except Exception as e:  # pragma: no cover - service-specific
                return JSONResponse(
                    {"error": "service_failure", "detail": str(e)}, status_code=500
                )

            # 5. Settle on-chain (or mock) via facilitator
            settlement: dict[str, Any] = {}
            if self.require_facilitator:
                try:
                    settlement = self._facilitator_client().settle(
                        payment_payload=payload,
                        seller_agent_id=self.agent_id,
                        service_id=spec.service_id,
                    )
                except SettlementFailed as e:
                    return JSONResponse(
                        {
                            "error": "settlement_failed",
                            "detail": str(e),
                            "raw": e.raw,
                            "result": result,  # so the buyer doesn't lose work entirely
                        },
                        status_code=502,
                    )

            # 6. Respond with result + settlement breadcrumb
            response = JSONResponse({"result": result, "settlement": settlement})
            response.headers["X-PAYMENT-RESPONSE"] = base64.b64encode(
                json.dumps(settlement, separators=(",", ":")).encode("utf-8")
            ).decode("ascii")
            return response

        handler.__name__ = f"handle_{spec.service_id}"
        return handler

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _challenge_response(self, spec: ServiceSpec, resource_url: str) -> JSONResponse:
        """Return the 402 advertising payment requirements."""
        req = PaymentRequirements(
            amount=spec.price,
            recipient=self.wallet.address,
            resource=resource_url,
            description=f"{spec.name}: {spec.description}",
            facilitator_url=self.facilitator_url,
        )
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_required",
                "x402_version": 1,
                "accepts": [req.to_dict()],
            },
            headers={
                "WWW-Authenticate": (
                    f'X402 realm="{self.name}", '
                    f'amount="{spec.price}", '
                    f'asset="{req.asset}", '
                    f'recipient="{self.wallet.address}", '
                    f'facilitator="{self.facilitator_url}"'
                )
            },
        )

    def _resource_url(self, request: Request, spec: ServiceSpec) -> str:
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}{spec.path}"
        # Reconstruct from request
        base = str(request.base_url).rstrip("/")
        return f"{base}{spec.path}"

    async def _extract_kwargs(self, request: Request, spec: ServiceSpec) -> dict[str, Any]:
        """Map the incoming request to the service function's kwargs."""
        param_names = spec.signature_params()
        if spec.method.upper() == "GET":
            qp = dict(request.query_params)
            return {k: qp[k] for k in param_names if k in qp}

        # POST / PUT / DELETE — accept JSON body
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = await request.json()
            except Exception as e:
                raise ValueError(f"Invalid JSON body: {e}") from e
        else:
            body = {}

        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object")

        # If the function takes a single dict-typed param, pass the whole body
        if len(param_names) == 1:
            only = param_names[0]
            if only in body:
                return {only: body[only]}
            # Heuristic: pass full body if its key set looks foreign
            return {only: body if not body else body.get(only, body)}

        return {k: body[k] for k in param_names if k in body}

    def _print_banner(self, host: str, port: int) -> None:
        registry = get_service_registry()
        print()
        print(f"  ╔════════════════════════════════════════════════╗")
        print(f"  ║  Agora x402 Agent: {self.name:<26} ║")
        print(f"  ╚════════════════════════════════════════════════╝")
        print(f"   Agent ID         : {self.agent_id}")
        print(f"   Wallet           : {self.wallet.address}")
        print(f"   Listening        : http://{host}:{port}")
        print(f"   Facilitator      : {self.facilitator_url}")
        print(f"   Services         : {len(registry.all())}")
        for spec in registry.all().values():
            print(f"      {spec.method} {spec.path:<24}  {spec.price} USDC   ({spec.name})")
        print()

"""
agora_x402 — SDK for building agents that pay each other per-API-call via x402.

Quick example
-------------

    from agora_x402 import pay_for, AgentServer, Wallet

    wallet = Wallet.from_env("SUMMARYBOT_PRIVATE_KEY")

    @pay_for(price="0.001", description="Summarize a chunk of text")
    def summarize(text: str) -> dict:
        return {"summary": text[:120] + "..."}

    server = AgentServer(
        agent_id="summarybot",
        name="SummaryBot",
        wallet=wallet,
    )
    server.run(port=9001)
"""

from agora_x402.exceptions import (
    AgoraError,
    PaymentRequired,
    InvalidPaymentHeader,
    SettlementFailed,
)
from agora_x402.pay_for import pay_for, get_service_registry
from agora_x402.wallet import Wallet, generate_keypair
from agora_x402.x402_protocol import (
    sign_payment_header,
    verify_payment_header,
    encode_payment_header,
    decode_payment_header,
    PaymentRequirements,
    X402_HEADER,
)
from agora_x402.facilitator_client import FacilitatorClient
from agora_x402.x402_client import X402Client
from agora_x402.agent_server import AgentServer

__all__ = [
    "AgoraError",
    "PaymentRequired",
    "InvalidPaymentHeader",
    "SettlementFailed",
    "pay_for",
    "get_service_registry",
    "Wallet",
    "generate_keypair",
    "sign_payment_header",
    "verify_payment_header",
    "encode_payment_header",
    "decode_payment_header",
    "PaymentRequirements",
    "X402_HEADER",
    "FacilitatorClient",
    "X402Client",
    "AgentServer",
]

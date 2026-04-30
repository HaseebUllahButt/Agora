"""
Smoke tests — runs without spinning up subprocesses or networking.

* x402 protocol round-trips (sign → encode → decode → verify)
* @pay_for registers services
* Fee math
* Facilitator DB init + nonce dedupe
* AgentServer mounts routes for each @pay_for service
"""

from __future__ import annotations

import os
import tempfile

# Use a throwaway DB for tests
os.environ["FACILITATOR_DB_PATH"] = os.path.join(tempfile.gettempdir(), "agora_test.db")
if os.path.exists(os.environ["FACILITATOR_DB_PATH"]):
    os.remove(os.environ["FACILITATOR_DB_PATH"])

from agora_x402.pay_for import _REGISTRY, pay_for
from agora_x402.wallet import generate_keypair, Wallet
from agora_x402.x402_protocol import (
    decode_payment_header,
    encode_payment_header,
    sign_payment_header,
    verify_payment_header,
)


def test_sign_verify_roundtrip():
    buyer = generate_keypair()
    seller = generate_keypair()
    payload = sign_payment_header(
        private_key_hex=buyer["private_key"],
        amount="0.001",
        sender=buyer["address"],
        recipient=seller["address"],
        resource="http://localhost:9001/x",
    )
    encoded = encode_payment_header(payload)
    decoded = decode_payment_header(encoded)
    ok, reason = verify_payment_header(decoded, expected_recipient=seller["address"])
    assert ok, reason

    # Wrong recipient should fail
    other = generate_keypair()
    bad_ok, bad_reason = verify_payment_header(decoded, expected_recipient=other["address"])
    assert not bad_ok
    assert "Recipient" in bad_reason


def test_min_amount_enforcement():
    buyer = generate_keypair()
    seller = generate_keypair()
    payload = sign_payment_header(
        private_key_hex=buyer["private_key"],
        amount="0.0001",
        sender=buyer["address"],
        recipient=seller["address"],
        resource="http://localhost/x",
    )
    ok, reason = verify_payment_header(
        payload, expected_recipient=seller["address"], min_amount="0.001"
    )
    assert not ok
    assert "Amount too low" in reason


def test_pay_for_registers_service():
    _REGISTRY.clear()

    @pay_for(price="0.005", category="test", description="Adds two ints")
    def adder(a: int, b: int) -> int:
        return a + b

    spec = _REGISTRY.get("adder")
    assert spec is not None
    assert spec.price == "0.005"
    assert spec.category == "test"
    assert spec.path == "/adder"
    assert spec.method == "POST"
    assert adder(2, 3) == 5  # function still callable directly


def test_marketplace_fee_split():
    from facilitator.fees import MarketplaceFees

    fees = MarketplaceFees(listing_fee_usdc=0.10, tx_fee_bps=250, treasury_address="0x0")
    fee, net = fees.split(1.0)
    assert round(fee, 6) == 0.025
    assert round(net, 6) == 0.975


def test_nonce_replay_protection():
    from facilitator.db import init_db
    from facilitator.nonce import consume_nonce

    init_db()
    ok1, _ = consume_nonce(nonce="abc-123", sender="0x1", resource="r", amount=0.001)
    ok2, reason = consume_nonce(nonce="abc-123", sender="0x1", resource="r", amount=0.001)
    assert ok1
    assert not ok2
    assert "Replay" in reason


def test_agent_server_mounts_routes():
    _REGISTRY.clear()

    @pay_for(price="0.001", category="test")
    def echo(text: str) -> dict:
        return {"text": text}

    from agora_x402.agent_server import AgentServer

    server = AgentServer(
        agent_id="echobot",
        name="EchoBot",
        wallet=Wallet.generate(),
        require_facilitator=False,
    )
    paths = {r.path for r in server.app.routes}
    assert "/echo" in paths
    assert "/health" in paths
    assert "/" in paths


if __name__ == "__main__":
    # Bare-bones runner so you don't need pytest installed
    import traceback

    funcs = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  ✗ {fn.__name__}")
            traceback.print_exc()
    print()
    print("FAILED" if failed else "OK", f"({len(funcs) - failed}/{len(funcs)})")
    raise SystemExit(failed)

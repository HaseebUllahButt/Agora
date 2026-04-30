"""
x402 protocol primitives — sign / verify / encode / decode payment headers.

Wire format
-----------
Following the x402 standard (https://www.x402.org), payment headers are
transported as a single HTTP header:

    X-PAYMENT: base64(json({...payment_payload}))

This module is transport-agnostic: it does not know about FastAPI or httpx.
``agent_server`` and ``x402_client`` import from here.

Payment payload schema
----------------------
::

    {
        "scheme":      "agora-ecdsa-v1",
        "version":     1,
        "amount":      "0.001",                 # USDC, decimal string
        "asset":       "USDC",
        "network":     "arc-testnet",
        "sender":      "0x...",                  # buyer wallet address
        "recipient":   "0x...",                  # seller wallet address
        "resource":    "http://host:port/path",  # the protected URL
        "nonce":       "uuid",
        "expiry":      1734567890,               # unix seconds
        "signature":   "0x...",                  # ECDSA over hash(payload)
        "public_key":  "0x..."                   # for offline verification
    }

The ``PaymentRequirements`` dataclass mirrors what a 402 response advertises so
clients know exactly how to construct a valid X-PAYMENT.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from eth_keys import keys

# HTTP header name used for x402 payments
X402_HEADER = "X-PAYMENT"

# Default scheme + version. Bump if you change the signing payload format.
SCHEME = "agora-ecdsa-v1"
VERSION = 1


# ────────────────────────────────────────────────────────────────────────────
# Payment requirements (advertised by a 402 response)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class PaymentRequirements:
    """What a server tells a client it needs to be paid.

    Returned in the body of a 402 response. The client uses this to construct
    a valid X-PAYMENT header.
    """

    scheme: str = SCHEME
    version: int = VERSION
    amount: str = "0"  # USDC, as a decimal string for precision
    asset: str = "USDC"
    network: str = "arc-testnet"
    recipient: str = ""  # seller wallet address
    resource: str = ""  # absolute URL of the protected endpoint
    description: str = ""
    facilitator_url: str = ""  # where the buyer can verify, if they want
    max_timeout_seconds: int = 60
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PaymentRequirements":
        return cls(
            scheme=d.get("scheme", SCHEME),
            version=int(d.get("version", VERSION)),
            amount=str(d.get("amount", "0")),
            asset=d.get("asset", "USDC"),
            network=d.get("network", "arc-testnet"),
            recipient=d.get("recipient", ""),
            resource=d.get("resource", ""),
            description=d.get("description", ""),
            facilitator_url=d.get("facilitator_url", ""),
            max_timeout_seconds=int(d.get("max_timeout_seconds", 60)),
            extra=d.get("extra", {}) or {},
        )


# ────────────────────────────────────────────────────────────────────────────
# Hashing + signing
# ────────────────────────────────────────────────────────────────────────────


def _canonical_payload_str(
    *,
    scheme: str,
    version: int,
    amount: str,
    asset: str,
    network: str,
    sender: str,
    recipient: str,
    resource: str,
    nonce: str,
    expiry: int,
) -> str:
    """Deterministic colon-separated payload used as the signing message.

    A fixed string rather than JSON so reordered keys / whitespace can never
    change the signature."""
    return (
        f"{scheme}|{version}|{amount}|{asset}|{network}|"
        f"{sender.lower()}|{recipient.lower()}|{resource}|{nonce}|{expiry}"
    )


def _payload_hash(payload_str: str) -> bytes:
    return hashlib.sha256(payload_str.encode("utf-8")).digest()


def sign_payment_header(
    *,
    private_key_hex: str,
    amount: str,
    sender: str,
    recipient: str,
    resource: str,
    network: str = "arc-testnet",
    asset: str = "USDC",
    nonce: Optional[str] = None,
    expiry_seconds: int = 60,
) -> dict:
    """Build and ECDSA-sign a payment payload.

    Returns the payload dict (suitable for ``encode_payment_header``).
    """
    nonce = nonce or str(uuid.uuid4())
    expiry = int(time.time()) + int(expiry_seconds)

    payload_str = _canonical_payload_str(
        scheme=SCHEME,
        version=VERSION,
        amount=str(amount),
        asset=asset,
        network=network,
        sender=sender,
        recipient=recipient,
        resource=resource,
        nonce=nonce,
        expiry=expiry,
    )
    msg = _payload_hash(payload_str)

    pk = keys.PrivateKey(bytes.fromhex(private_key_hex.replace("0x", "")))
    sig = pk.sign_msg_hash(msg)

    return {
        "scheme": SCHEME,
        "version": VERSION,
        "amount": str(amount),
        "asset": asset,
        "network": network,
        "sender": sender,
        "recipient": recipient,
        "resource": resource,
        "nonce": nonce,
        "expiry": expiry,
        "signature": sig.to_hex(),
        "public_key": pk.public_key.to_hex(),
    }


def verify_payment_header(
    payload: dict,
    *,
    expected_recipient: str,
    expected_resource: Optional[str] = None,
    min_amount: Optional[str] = None,
) -> tuple[bool, str]:
    """Verify a payment payload.

    Checks signature, expiry, recipient, optional resource match, and
    optional minimum amount.

    Returns
    -------
    (valid, reason)
    """
    try:
        # Required fields
        for k in ("amount", "sender", "recipient", "resource", "nonce", "expiry", "signature"):
            if k not in payload:
                return False, f"Missing field: {k}"

        # Expiry
        if int(payload["expiry"]) < int(time.time()):
            return False, "Header expired"

        # Recipient
        if str(payload["recipient"]).lower() != expected_recipient.lower():
            return False, "Recipient mismatch"

        # Resource (optional)
        if expected_resource is not None and payload["resource"] != expected_resource:
            return False, "Resource mismatch"

        # Amount (optional)
        if min_amount is not None:
            if float(payload["amount"]) + 1e-9 < float(min_amount):
                return False, f"Amount too low: paid {payload['amount']}, needed {min_amount}"

        # Signature
        payload_str = _canonical_payload_str(
            scheme=payload.get("scheme", SCHEME),
            version=int(payload.get("version", VERSION)),
            amount=str(payload["amount"]),
            asset=payload.get("asset", "USDC"),
            network=payload.get("network", "arc-testnet"),
            sender=payload["sender"],
            recipient=payload["recipient"],
            resource=payload["resource"],
            nonce=payload["nonce"],
            expiry=int(payload["expiry"]),
        )
        msg = _payload_hash(payload_str)

        sig_bytes = bytes.fromhex(str(payload["signature"]).replace("0x", ""))
        sig = keys.Signature(sig_bytes)
        recovered = sig.recover_public_key_from_msg_hash(msg)
        if recovered.to_checksum_address().lower() != payload["sender"].lower():
            return False, "Signature does not match sender"

        return True, "OK"
    except (ValueError, binascii.Error) as e:
        return False, f"Malformed header: {e}"
    except Exception as e:  # pragma: no cover - defensive
        return False, f"Verification error: {e}"


# ────────────────────────────────────────────────────────────────────────────
# Wire encoding (HTTP header value)
# ────────────────────────────────────────────────────────────────────────────


def encode_payment_header(payload: dict) -> str:
    """Encode a payment payload as a base64 string for the X-PAYMENT header."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_payment_header(header_value: str) -> dict:
    """Reverse of :func:`encode_payment_header`. Raises ValueError on bad input."""
    try:
        raw = base64.b64decode(header_value.encode("ascii"))
        return json.loads(raw)
    except (binascii.Error, json.JSONDecodeError, UnicodeError) as e:
        raise ValueError(f"Invalid X-PAYMENT header: {e}") from e


# ────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from agora_x402.wallet import generate_keypair

    buyer = generate_keypair()
    seller = generate_keypair()

    payload = sign_payment_header(
        private_key_hex=buyer["private_key"],
        amount="0.001",
        sender=buyer["address"],
        recipient=seller["address"],
        resource="http://localhost:9001/summarize",
    )
    encoded = encode_payment_header(payload)
    print(f"X-PAYMENT length: {len(encoded)} bytes")

    decoded = decode_payment_header(encoded)
    ok, reason = verify_payment_header(decoded, expected_recipient=seller["address"])
    print(f"Verify: {ok} ({reason})")
    assert ok, reason
    print("✅ x402_protocol self-test passed")

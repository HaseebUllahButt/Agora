"""
Lightweight ECDSA wallet for agents.

Each agent owns a secp256k1 keypair. The private key is used to sign x402
payment headers; the derived address is the on-chain identity / USDC
destination.

Wallets are intentionally minimal — they do NOT talk to Circle here. Settlement
is handled by the facilitator. This keeps the SDK pure-Python and easy to test.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Tuple

from eth_keys import keys


def generate_keypair() -> dict:
    """Generate a fresh secp256k1 keypair.

    Returns
    -------
    dict
        ``{"private_key": "0x...", "public_key": "0x...", "address": "0x..."}``
    """
    private_key_bytes = secrets.token_bytes(32)
    pk = keys.PrivateKey(private_key_bytes)
    return {
        "private_key": pk.to_hex(),
        "public_key": pk.public_key.to_hex(),
        "address": pk.public_key.to_checksum_address(),
    }


@dataclass
class Wallet:
    """An agent's local wallet.

    Holds a private key and exposes its derived address. Sign operations are
    delegated to ``x402_protocol.sign_payment_header``.
    """

    private_key: str  # 0x-prefixed hex
    address: str  # checksum 0x address

    # ── Constructors ─────────────────────────────────────────────────────────
    @classmethod
    def generate(cls) -> "Wallet":
        kp = generate_keypair()
        return cls(private_key=kp["private_key"], address=kp["address"])

    @classmethod
    def from_private_key(cls, private_key_hex: str) -> "Wallet":
        clean = private_key_hex.replace("0x", "")
        if len(clean) != 64:
            raise ValueError(
                f"Private key must be 32 bytes (64 hex chars), got {len(clean)}"
            )
        pk = keys.PrivateKey(bytes.fromhex(clean))
        return cls(
            private_key="0x" + clean,
            address=pk.public_key.to_checksum_address(),
        )

    @classmethod
    def from_env(cls, env_var: str) -> "Wallet":
        """Load a wallet from an env var, generating + warning if absent.

        For production, the env var MUST be set. For local demos, an ephemeral
        wallet is generated so a fresh checkout still runs.
        """
        raw = os.getenv(env_var)
        if raw:
            return cls.from_private_key(raw)
        # Ephemeral fallback so demos work without setup
        wallet = cls.generate()
        print(
            f"⚠️  {env_var} not set — using ephemeral wallet {wallet.address}. "
            f"Funds sent to this address are lost when the process exits."
        )
        return wallet

    # ── Helpers ──────────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return f"Wallet(address={self.address})"

    def short(self) -> str:
        return f"{self.address[:6]}…{self.address[-4:]}"

"""
encrypt_entity_secret.py — produce the ~684-char ciphertext that Circle's
developer console asks for when you "Register Entity Secret" or "Rotate
Entity Secret".

The Circle developer console does not accept the raw 32-byte hex secret —
it wants the secret RSA-encrypted with your account's public key, then
base64-encoded. This script does exactly that and prints the ciphertext.

Usage
-----

    python scripts/encrypt_entity_secret.py
        --api-key TEST_API_KEY:...
        --entity-secret 01969e601e0d1476c...

Or run with no args to be prompted interactively.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

# Lazy install of the Circle SDK
try:
    from circle.web3 import utils as circle_utils
except ImportError:
    print("📦 Installing circle-developer-controlled-wallets …")
    if os.system(f"{sys.executable} -m pip install -q circle-developer-controlled-wallets") != 0:
        sys.exit("❌ Failed to install Circle SDK.")
    from circle.web3 import utils as circle_utils  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api-key", default=None, help="Circle API key (or read from CIRCLE_API_KEY).")
    p.add_argument(
        "--entity-secret",
        default=None,
        help="32-byte hex secret. If omitted, a fresh one is generated.",
    )
    args = p.parse_args()

    api_key = args.api_key or os.getenv("CIRCLE_API_KEY") or input("🔑 Circle API Key: ").strip()
    if not api_key:
        sys.exit("❌ No API key provided.")

    entity_secret = args.entity_secret
    if not entity_secret:
        entity_secret = input(
            "🔐 Entity secret (64 hex chars, blank to generate): "
        ).strip()
        if not entity_secret:
            entity_secret = secrets.token_hex(32)
            print(f"\n✨ Generated raw entity secret:\n   {entity_secret}")

    if len(entity_secret.replace("0x", "")) != 64:
        sys.exit("❌ Entity secret must be exactly 32 bytes (64 hex chars).")

    print("\n🔒 Asking Circle for your account's public key + encrypting…")
    try:
        ciphertext = circle_utils.generate_entity_secret_ciphertext(api_key, entity_secret)
    except Exception as e:
        sys.exit(f"❌ Could not generate ciphertext: {e}")

    print()
    print("════════════════════════════════════════════════════════════")
    print(f"  Ciphertext length: {len(ciphertext)} chars")
    print("  Paste this into Circle's console → Register / Rotate Entity Secret:")
    print("════════════════════════════════════════════════════════════")
    print()
    print(ciphertext)
    print()
    print("After Circle accepts it, save the raw entity secret to .env:")
    print()
    print(f"  CIRCLE_ENTITY_SECRET={entity_secret}")
    print()
    print("Then run:  python scripts/bootstrap_circle.py")


if __name__ == "__main__":
    main()

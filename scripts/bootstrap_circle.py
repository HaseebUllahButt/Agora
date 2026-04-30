"""
bootstrap_circle.py — Circle setup for AgoraAli.

Port of the original Agora bootstrap script, adapted to AgoraAli's standalone
layout. Run AFTER ``scripts/setup_env.py``.

Flow
----
1. Verify ``.env`` exists (created by ``setup_env.py``).
2. Read ``CIRCLE_API_KEY`` from ``.env`` or prompt for it on the terminal.
3. Generate ``CIRCLE_ENTITY_SECRET`` locally (32-byte hex) and register it
   with Circle (saving the recovery file to ``.recovery/``).
4. Create a developer-controlled Wallet Set on Arc-testnet and store its ID.
5. Optionally create a Master Funder wallet and store its ID + address.

All values are written into ``.env`` via :func:`_write_env_var`.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Lazy install of the Circle SDK
try:
    from circle.web3 import utils as circle_utils
except ImportError:
    print("📦 Circle SDK not installed. Installing circle-developer-controlled-wallets …")
    if os.system(f"{sys.executable} -m pip install -q circle-developer-controlled-wallets") != 0:
        sys.exit("❌ Failed to install Circle SDK.")
    from circle.web3 import utils as circle_utils  # noqa: E402

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
RECOVERY_DIR = REPO_ROOT / ".recovery"

CIRCLE_API_URL = "https://api.circle.com/v1"


# ────────────────────────────────────────────────────────────────────────────
# Circle HTTP helpers (inline, so AgoraAli stays standalone)
# ────────────────────────────────────────────────────────────────────────────


def _ciphertext(api_key: str, entity_secret: str) -> str:
    return circle_utils.generate_entity_secret_ciphertext(api_key, entity_secret)


def _create_wallet_set(api_key: str, entity_secret: str, name: str) -> str:
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "name": name,
        "entitySecretCiphertext": _ciphertext(api_key, entity_secret),
    }
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=30, trust_env=False) as c:
        resp = c.post(f"{CIRCLE_API_URL}/w3s/developer/walletSets", json=payload)
    if resp.status_code != 201:
        raise RuntimeError(f"Wallet Set creation failed: {resp.text}")
    return resp.json()["data"]["walletSet"]["id"]


def _create_wallet(api_key: str, entity_secret: str, wallet_set_id: str, description: str) -> dict:
    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "description": description,
        "blockchains": [os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")],
        "walletSetId": wallet_set_id,
        "entitySecretCiphertext": _ciphertext(api_key, entity_secret),
        "count": 1,
    }
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=30, trust_env=False) as c:
        resp = c.post(f"{CIRCLE_API_URL}/w3s/developer/wallets", json=payload)
    if resp.status_code != 201:
        raise RuntimeError(f"Wallet creation failed: {resp.text}")
    w = resp.json()["data"]["wallets"][0]
    return {"wallet_id": w["id"], "address": w["address"]}


# ────────────────────────────────────────────────────────────────────────────
# .env helpers
# ────────────────────────────────────────────────────────────────────────────


def _write_env_var(key: str, value: str) -> None:
    """Safely append/replace a variable in .env without duplicates."""
    existing = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    lines = [line for line in existing.split("\n") if not line.startswith(f"{key}=")]
    # Drop trailing blank lines so the file stays tidy
    while lines and lines[-1] == "":
        lines.pop()
    lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


# ────────────────────────────────────────────────────────────────────────────
# Main bootstrap (mirrors the old Agora script's flow)
# ────────────────────────────────────────────────────────────────────────────


def bootstrap() -> None:
    if not ENV_PATH.exists():
        sys.exit("❌ .env not found. Run `python scripts/setup_env.py` first.")

    load_dotenv(ENV_PATH)

    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║              AgoraAli Circle Bootstrap                ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    # 1. CIRCLE_API_KEY ─────────────────────────────────────────────────────
    api_key = os.getenv("CIRCLE_API_KEY", "").strip()
    if api_key:
        print(f"✅ Found existing CIRCLE_API_KEY: {api_key[:20]}…")
    else:
        api_key = input("\n🔑 Enter your Circle API Key (https://developers.circle.com): ").strip()
        if not api_key:
            sys.exit("❌ No API key entered.")
        _write_env_var("CIRCLE_API_KEY", api_key)

    # 2. CIRCLE_ENTITY_SECRET ───────────────────────────────────────────────
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET", "").strip()
    if entity_secret:
        print(f"✅ Found existing CIRCLE_ENTITY_SECRET: {entity_secret[:16]}…")
        print("   (Using existing secret. To reset, delete this line from .env)")
    else:
        print("\n🔐 Generating new Entity Secret (32-byte secure random)…")
        entity_secret = secrets.token_hex(32)
        print(f"✅ Generated: {entity_secret}")

        print("\n📤 Registering Entity Secret with Circle Console…")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                circle_utils.register_entity_secret_ciphertext(
                    api_key=api_key,
                    entity_secret=entity_secret,
                    recoveryFileDownloadPath=tmpdir,
                )
                recovery_files = list(Path(tmpdir).glob("*.json"))
                if recovery_files:
                    RECOVERY_DIR.mkdir(exist_ok=True)
                    safe_recovery_path = RECOVERY_DIR / "entity_secret_recovery.json"
                    safe_recovery_path.write_text(recovery_files[0].read_text())
                    print(f"✅ Successfully registered Entity Secret with Circle")
                    print(f"   💾 Recovery file saved → {safe_recovery_path.relative_to(REPO_ROOT)}")
                else:
                    # The Circle SDK prints "HTTP Error: 409 - Conflict" but
                    # doesn't raise — the absence of a recovery file is the only
                    # signal that registration silently failed. This usually
                    # means the API key's developer account already has an
                    # entity secret registered.
                    print()
                    print("❌ Circle did not return a recovery file — registration failed.")
                    print("   The API key's developer account most likely already has")
                    print("   an entity secret registered.")
                    print()
                    print("   Fix it one of two ways:")
                    print("     1. Paste the existing entity secret into .env as")
                    print("        CIRCLE_ENTITY_SECRET=… and re-run this script.")
                    print("        (Check Agora/.env if you used Circle there before.)")
                    print("     2. Rotate the entity secret on Circle's console:")
                    print("        https://console.circle.com/wallets/dev-controlled/configurator")
                    print("        then clear CIRCLE_ENTITY_SECRET in .env and re-run.")
                    sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to register Entity Secret: {e}")
            print("   Make sure your CIRCLE_API_KEY is valid")
            sys.exit(1)

        _write_env_var("CIRCLE_ENTITY_SECRET", entity_secret)

    # 3. CIRCLE_WALLET_SET_ID ───────────────────────────────────────────────
    print("\n⛓️  Configuring Circle Wallet Set on Arc Testnet…")
    wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID", "").strip()
    if wallet_set_id:
        print(f"✅ Using existing Wallet Set: {wallet_set_id}")
    else:
        print("🚀 Creating new Wallet Set…")
        try:
            wallet_set_id = _create_wallet_set(api_key, entity_secret, name="AgoraAli")
            _write_env_var("CIRCLE_WALLET_SET_ID", wallet_set_id)
            print(f"✅ Successfully created Wallet Set: {wallet_set_id}")
        except Exception as e:
            print(f"❌ Failed to create Wallet Set: {e}")
            print("   Make sure your CIRCLE_API_KEY is valid and the entity secret is")
            print("   registered with Circle Console.")
            sys.exit(1)

    # 4. (Optional) Master Funder wallet ────────────────────────────────────
    print("\n💰 Faucet Configuration")
    master_wallet_id = os.getenv("CIRCLE_MASTER_WALLET_ID", "").strip()
    if master_wallet_id:
        print(f"✅ Found existing CIRCLE_MASTER_WALLET_ID: {master_wallet_id}")
    else:
        print("🚀 Creating new Master Funder wallet…")
        try:
            wallet_info = _create_wallet(api_key, entity_secret, wallet_set_id, "Master_Funder")
            _write_env_var("CIRCLE_MASTER_WALLET_ID", wallet_info["wallet_id"])
            _write_env_var("CIRCLE_MASTER_WALLET_ADDRESS", wallet_info["address"])
            print(f"✅ Successfully created Master Wallet: {wallet_info['wallet_id']}")
            print(f"⚠️  IMPORTANT: fund this address at https://faucet.circle.com/")
            print(f"   Address: {wallet_info['address']}")
        except Exception as e:
            print(f"❌ Failed to create Master Wallet: {e}")
            print("   You can create one manually and add it to .env if you need it.")

    # ─── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ BOOTSTRAP COMPLETE")
    print("=" * 60)
    print("\n📝 Configuration saved to .env:")
    print(f"   - CIRCLE_API_KEY: {api_key[:30]}…")
    print(f"   - CIRCLE_ENTITY_SECRET: {entity_secret[:16]}…")
    print(f"   - CIRCLE_WALLET_SET_ID: {wallet_set_id}")
    print("\n🚀 Next steps:")
    print("   1. set -a && source .env && set +a")
    print("   2. bash scripts/run_facilitator.sh   # picks up the new keys")
    print("   3. bash scripts/run_all_agents.sh")
    print("   4. python scripts/x402_demo.py")
    print()


if __name__ == "__main__":
    bootstrap()

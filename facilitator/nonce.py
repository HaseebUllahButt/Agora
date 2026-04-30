"""
Atomic nonce registry — replay protection for x402 payment headers.

Each verified payment must carry a unique ``nonce`` (typically a UUID). This
module records every consumed nonce in SQLite with a TTL; any subsequent
verify attempt with the same nonce returns ``False`` (replay detected).

We use SQLite (rather than Redis) so the facilitator has zero external
runtime deps for the demo. The ``UNIQUE`` constraint on ``nonces.nonce`` makes
the insert atomic across concurrent requests.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Tuple

from facilitator.db import get_db

NONCE_TTL_SECONDS = int(os.getenv("NONCE_TTL_SECONDS", 120))


def consume_nonce(*, nonce: str, sender: str, resource: str, amount: float) -> Tuple[bool, str]:
    """Atomically reserve a nonce. Returns ``(True, "OK")`` on first use."""
    now = datetime.utcnow()
    expires = now + timedelta(seconds=NONCE_TTL_SECONDS)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO nonces (nonce, sender, resource, amount, used_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (nonce, sender, resource, amount, now.isoformat(), expires.isoformat()),
            )
        return True, "OK"
    except Exception as e:  # sqlite3.IntegrityError or similar
        if "UNIQUE" in str(e).upper():
            return False, "Replay detected (nonce already used)"
        return False, f"Nonce store error: {e}"


def gc_expired() -> int:
    """Best-effort cleanup of nonces older than TTL. Returns rows deleted."""
    cutoff = datetime.utcnow().isoformat()
    with get_db() as conn:
        cur = conn.execute("DELETE FROM nonces WHERE expires_at < ?", (cutoff,))
        return cur.rowcount or 0

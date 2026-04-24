"""
shared/nonce_registry.py

Redis-based atomic nonce validation (prevents replay attacks).
Uses Redis SET NX (set-if-not-exists) for atomicity.
"""

import redis
import os
from datetime import datetime, timedelta

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
NONCE_TTL_SECONDS = int(os.getenv("NONCE_TTL_SECONDS", 60))

# Global Redis client
_redis_client = None
_redis_available = None

def get_redis():
    """Get Redis connection. Falls back to SQLite if unavailable for demo purposes."""
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
        
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_keepalive=True
            )
            # Test connection
            _redis_client.ping()
            print(f"✓ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            _redis_available = True
        except Exception as e:
            print(f"⚠️ Redis connection failed at {REDIS_HOST}:{REDIS_PORT}. Falling back to SQLite for nonces.")
            _redis_available = False
            _redis_client = None
    return _redis_client


def register_nonce(agent_id: str, nonce: str) -> tuple[bool, str]:
    """Atomically register a nonce."""
    redis_client = get_redis()
    
    if redis_client:
        key = f"nonce:{nonce}"
        now = datetime.utcnow().isoformat()
        value = f"{agent_id}|{now}"
        try:
            result = redis_client.set(key, value, nx=True, ex=NONCE_TTL_SECONDS)
            return (True, "OK") if result else (False, "Replay detected")
        except Exception as e:
            return False, f"Nonce check error: {e}"
    else:
        # SQLite fallback
        from shared.database import get_db
        now = datetime.utcnow().isoformat()
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO nonces (nonce, agent_id, used_at, expires_at) VALUES (?, ?, ?, ?)",
                    (nonce, agent_id, now, now)
                )
                conn.commit()
            return True, "OK"
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return False, "Replay detected"
            return False, f"SQLite nonce check error: {e}"


def is_nonce_used(nonce: str) -> bool:
    """Check if a nonce has already been used."""
    redis_client = get_redis()
    if redis_client:
        return redis_client.get(f"nonce:{nonce}") is not None
    else:
        from shared.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM nonces WHERE nonce = ?", (nonce,))
            return cursor.fetchone() is not None


def clear_nonce(nonce: str) -> bool:
    """Manually clear a nonce (for cleanup/testing)."""
    redis_client = get_redis()
    if redis_client:
        redis_client.delete(f"nonce:{nonce}")
    else:
        from shared.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM nonces WHERE nonce = ?", (nonce,))
            conn.commit()
    return True


def cleanup_expired_nonces():
    """Redis automatically expires keys based on TTL, so no manual cleanup needed."""
    pass


if __name__ == "__main__":
    # Quick test
    print("Testing nonce registry...")
    
    agent = "agent_123"
    nonce = "test-nonce-001"
    
    # First registration should succeed
    success, msg = register_nonce(agent, nonce)
    print(f"First registration: {success} ({msg})")
    assert success, "First registration should succeed"
    
    # Second registration (replay) should fail
    success2, msg2 = register_nonce(agent, nonce)
    print(f"Second registration (replay): {success2} ({msg2})")
    assert not success2, "Replay should be detected"
    
    print("✓ Nonce registry test passed")

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


def get_redis():
    """Get Redis connection. Fails if Redis is unavailable (Zero-Slop)."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            _redis_client.ping()
            print(f"✓ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            # Production Rule: No mock storage allowed for nonce protection
            raise ConnectionError(f"CRITICAL: Redis connection failed at {REDIS_HOST}:{REDIS_PORT}. Nonce protection required. {e}")
    return _redis_client



def register_nonce(agent_id: str, nonce: str) -> tuple[bool, str]:
    """
    Atomically register a nonce.
    
    Uses Redis SET NX (atomic set-if-not-exists) to prevent concurrent registration
    of the same nonce. This prevents replay attacks.
    
    Args:
        agent_id: Wallet ID using the nonce
        nonce: UUID nonce string
    
    Returns:
        (True, "OK") if nonce was registered (first time)
        (False, "Replay detected") if nonce was already registered (failure)
    """
    redis_client = get_redis()
    
    # Key format: "nonce:{nonce}" (nonce must be globally unique)
    key = f"nonce:{nonce}"
    
    # Value: agent_id and timestamp for auditing
    now = datetime.utcnow().isoformat()
    value = f"{agent_id}|{now}"
    
    try:
        # SET with NX (set-if-not-exists) and EX (expiry in seconds)
        # This is atomic at the Redis level
        result = redis_client.set(key, value, nx=True, ex=NONCE_TTL_SECONDS)
        
        if result:
            # Successfully set (first time)
            return True, "OK"
        else:
            # Key already existed (replay attempt)
            return False, "Replay detected"
    
    except Exception as e:
        print(f"⚠️  Nonce check failed: {e}")
        # Fail closed (reject) on error
        return False, f"Nonce check error: {e}"


def is_nonce_used(nonce: str) -> bool:
    """Check if a nonce has already been used."""
    redis_client = get_redis()
    key = f"nonce:{nonce}"
    return redis_client.get(key) is not None


def clear_nonce(nonce: str) -> bool:
    """Manually clear a nonce (for cleanup/testing)."""
    redis_client = get_redis()
    key = f"nonce:{nonce}"
    redis_client.delete(key)
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

"""
Unified shared module containing all core utilities.
"""

# circle.web3 is imported lazily inside CircleClient._get_entity_secret_ciphertext()
# to avoid crashing if the circle SDK isn't installed yet.
from contextlib import contextmanager
from datetime import datetime
from datetime import datetime, timedelta
from dotenv import load_dotenv
from eth_keys import keys
from eth_utils import keccak
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
from typing import Optional
from typing import Set, Any
import asyncio
import base64
import binascii
import hashlib
import httpx
import json
import logging
import numpy as np
import os
import redis
import secrets
import sqlite3
import threading
import uuid




load_dotenv()

# ─── Chain & Token ────────────────────────────────────────────────────────────
BLOCKCHAIN = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")
ARC_TESTNET_USDC = os.getenv("ARC_TESTNET_USDC", "0x3600000000000000000000000000000000000000")
ARC_EXPLORER_API = os.getenv("ARC_EXPLORER_API", "https://testnet.arcscan.app/api/v2")
ARC_EXPLORER_BASE = "https://testnet.arcscan.app"

# ─── Wallet Set ───────────────────────────────────────────────────────────────
CIRCLE_WALLET_SET_ID = os.getenv("CIRCLE_WALLET_SET_ID", "de6bdaa1-4c6a-58bb-90fc-8bb337d93080")

# ─── Transaction Settings ─────────────────────────────────────────────────────
TX_FEE_LEVEL = "MEDIUM"
TX_POLL_INITIAL_DELAY = 1.5    # seconds
TX_POLL_MAX_DELAY = 5.0        # seconds
TX_POLL_BACKOFF_FACTOR = 1.2
TX_TERMINAL_STATES = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}

# ─── Agent Prices (USDC) ──────────────────────────────────────────────────────
PRICE_WEB_SEARCH  = "0.0005"
PRICE_EXTRACTOR   = "0.0005"
PRICE_SUMMARIZER  = "0.001"
PRICE_ANALYST     = "0.002"
PRICE_FORMATTER   = "0.0005"

# Cost per full research loop
COST_PER_LOOP = (
    float(PRICE_WEB_SEARCH) +
    float(PRICE_EXTRACTOR) +
    float(PRICE_SUMMARIZER) +
    float(PRICE_ANALYST) +
    float(PRICE_FORMATTER)
)

# ─── Ethereum Gas Comparison (for MarginCalculator) ───────────────────────────
# Average ERC-20 transfer gas cost on Ethereum mainnet (USD, as of 2024)
ETH_GAS_PER_TX_USD = 2.95




logger = logging.getLogger(__name__)

class EventBus:
    """
    Truly thread-safe pub/sub event bus that bridges synchronous threads and the asyncio loop.
    """
    
    def __init__(self):
        """Initialize event bus with empty subscribers."""
        self._subscribers: dict[str, Set[asyncio.Queue]] = {}
        self._lock = threading.Lock() # Use threading lock for cross-thread safety
        self._loop = None # Will be captured lazily in the main thread
    
    def _get_loop(self):
        """Lazily capture or return the running loop."""
        if self._loop and self._loop.is_running():
            return self._loop
        try:
            self._loop = asyncio.get_running_loop()
            return self._loop
        except RuntimeError:
            return None

    async def subscribe(self, event_type: str):
        """Subscribe to events (must be called from an async context)."""
        loop = self._get_loop()
        if not loop:
            raise RuntimeError("EventBus.subscribe must be called from a running event loop")
            
        queue: asyncio.Queue = asyncio.Queue()
        
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = set()
            self._subscribers[event_type].add(queue)
        
        try:
            while True:
                yield await queue.get()
        finally:
            with self._lock:
                self._subscribers[event_type].discard(queue)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
    
    def publish(self, event_type: str, data: dict[str, Any]):
        """Broadcast an event to all subscribers (can be called from ANY thread)."""
        with self._lock:
            if event_type not in self._subscribers:
                return
            queues = list(self._subscribers.get(event_type, set()))
        
        # Schedule the push to each queue on the main loop
        if not self._loop:
            # If we haven't captured a loop yet, try to find one
            # This handles cases where publish is called before any subscription
            try:
                # We can't use get_running_loop from a thread, but we can try to find it
                pass 
            except:
                pass

        for queue in queues:
            # queue.put_nowait is NOT thread-safe, so we must call it on the loop
            try:
                # We use loop.call_soon_threadsafe to interact with the queue
                queue._loop.call_soon_threadsafe(queue.put_nowait, data)
            except Exception as e:
                logger.debug(f"Failed to push to queue: {e}")
    

# Global singleton instance
_event_bus = None

def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus



class VectorSearch:
    """
    A simple TF-IDF based vector search engine for the marketplace.
    Provides semantic-like matching for agent descriptions.
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.providers = []
        self.tfidf_matrix = None

    def index(self, providers: List[Dict]):
        """Index provider descriptions into the vector space."""
        if not providers:
            self.providers = []
            self.tfidf_matrix = None
            return

        self.providers = providers
        # Create a corpus of Name + Description + Type
        corpus = [
            f"{p['name']} {p['description']} {p['service_type']}"
            for p in providers
        ]
        
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Perform vector search using cosine similarity."""
        if self.tfidf_matrix is None or not self.providers:
            return []

        # Vectorize the query
        query_vec = self.vectorizer.transform([query])
        
        # Calculate similarity scores
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Get top indices
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices:
            # Only include results with some similarity
            if similarities[idx] > 0:
                provider = self.providers[idx].copy()
                provider["search_score"] = float(similarities[idx])
                results.append(provider)
                
            if len(results) >= limit:
                break
                
        return results

# Singleton instance
_ENGINE = VectorSearch()

def get_search_engine() -> VectorSearch:
    return _ENGINE




logger = logging.getLogger(__name__)

CIRCLE_API_URL = "https://api.circle.com/v1"
ARC_CHAIN_ID = "5042002"
USDC_ADDRESS = "0x3600000000000000000000000000000000000000"


class CircleWalletConfig:
    """Configuration for Circle wallet integration."""
    
    def __init__(
        self,
        api_key: str,
        entity_secret: str,
        wallet_set_id: str = None
    ):
        self.api_key = api_key
        self.entity_secret = entity_secret
        self.wallet_set_id = wallet_set_id
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )
    
    def close(self):
        """Close HTTP client."""
        self.client.close()


class CircleClient:
    """
    Circle Wallets API client for Arc testnet.
    Uses Developer-Controlled Wallets (backend signs transactions).
    """
    
    def __init__(self, config: CircleWalletConfig):
        print(f"📡 [DEBUG] CircleClient initialized (Code Version: 1.2)")
        self.config = config
    
    def _get_entity_secret_ciphertext(self) -> str:
        """
        Encrypt the entity secret using the official Circle SDK utility.
        The SDK internally handles the public key fetch.
        """
        try:
            from circle.web3 import utils as circle_utils
            return circle_utils.generate_entity_secret_ciphertext(
                self.config.api_key,
                self.config.entity_secret
            )
        except Exception as e:
            logger.error(f"Failed to generate entitySecretCiphertext via SDK: {e}")
            raise

    def create_wallet_set(self, name: str) -> str:
        """Create a new developer-controlled wallet set."""
        try:
            idempotency_key = str(uuid.uuid4())
            payload = {
                "idempotencyKey": idempotency_key,
                "name": name,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext()
            }
            
            url = f"{CIRCLE_API_URL}/w3s/developer/walletSets"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Wallet Set creation failed: {response.text}")
                raise Exception(f"Failed to create wallet set: {response.text}")
            
            wallet_set_id = response.json()["data"]["walletSet"]["id"]
            logger.info(f"Created Wallet Set: {wallet_set_id}")
            self.config.wallet_set_id = wallet_set_id
            return wallet_set_id
        except Exception as e:
            logger.error(f"Wallet Set creation error: {e}")
            raise

    def create_wallet(self, agent_id: str) -> dict:
        """
        Create a developer-controlled wallet for an agent on Arc testnet.
        """
        try:
            idempotency_key = str(uuid.uuid4())
            blockchain = os.getenv("CIRCLE_WALLET_BLOCKCHAIN", "ARC-TESTNET")
            payload = {
                "idempotencyKey": idempotency_key,
                "description": f"Agent {agent_id} wallet on Arc",
                "blockchains": [blockchain],
                "walletSetId": self.config.wallet_set_id,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext(),
                "count": 1
            }
            
            # Use developer-controlled wallets endpoint
            url = f"{CIRCLE_API_URL}/w3s/developer/wallets"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Circle wallet creation failed: {response.text}")
                raise Exception(f"Failed to create wallet: {response.text}")
            
            # Response returns a list of wallets
            wallets = response.json()["data"]["wallets"]
            wallet = wallets[0]
            logger.info(f"Created wallet for {agent_id}: {wallet['id']}")
            
            return {
                "wallet_id": wallet["id"],
                "address": wallet["address"],
                "state": wallet["state"],
                "blockchain": wallet["blockchain"]
            }
        except Exception as e:
            logger.error(f"Circle wallet creation error: {e}")
            raise
    
    def get_wallet(self, wallet_id: str) -> dict:
        """Get wallet details including balance."""
        try:
            # Note: For developer-controlled, fetch by ID uses /w3s/wallets/
            url = f"{CIRCLE_API_URL}/w3s/wallets/{wallet_id}"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Circle wallet fetch failed: {response.text}")
                raise Exception(f"Failed to fetch wallet: {response.text}")
            
            return response.json()["data"]["wallet"]
        except Exception as e:
            logger.error(f"Circle wallet fetch error: {e}")
            raise
    
    def get_balance(self, wallet_id: str) -> float:
        """
        Get USDC balance for a wallet on Arc.
        Handles both native and ERC-20 USDC.
        """
        try:
            # For developer-controlled wallets, use the /balances endpoint
            url = f"{CIRCLE_API_URL}/w3s/wallets/{wallet_id}/balances"
            response = self.config.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Circle balance fetch failed: {response.text}")
                return 0.0
            
            data = response.json().get("data", {})
            token_balances = data.get("tokenBalances", [])
            
            for b in token_balances:
                token = b.get("token", {})
                symbol = token.get("symbol", "")
                
                # On Arc, USDC is often native and has 18 decimals
                # We check symbol and blockchain to be robust
                if symbol == "USDC":
                    return float(b.get("amount", 0.0))
                
                # Fallback for standard ERC-20 USDC address
                if token.get("address", "").lower() == USDC_ADDRESS.lower():
                    return float(b.get("amount", 0.0))
            
            return 0.0
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return 0.0
    
    def transfer_usdc(
        self,
        from_wallet_id: str,
        to_address: str,
        amount_usdc: float,
        idempotency_key: Optional[str] = None
    ) -> dict:
        """
        Transfer USDC from wallet to destination address on Arc.
        
        Args:
            from_wallet_id: Source wallet ID
            to_address: Destination address (0x format)
            amount_usdc: Amount in USDC
            idempotency_key: Optional for idempotency (auto-generated if None)
        
        Returns:
            {
                "transaction_id": "uuid",
                "from_address": "0x...",
                "to_address": "0x...",
                "amount": "100.00",
                "state": "PENDING",
                "txHash": "0x..." (if confirmed)
            }
        """
        try:
            if not idempotency_key:
                idempotency_key = str(uuid.uuid4())
            
            payload = {
                "idempotencyKey": idempotency_key,
                "amounts": [str(amount_usdc)],
                "blockchain": "ARC-TESTNET",
                "destinationAddress": to_address,
                "feeLevel": "MEDIUM",
                "walletId": from_wallet_id,
                "entitySecretCiphertext": self._get_entity_secret_ciphertext()
            }
            
            url = f"{CIRCLE_API_URL}/w3s/developer/transactions/transfer"
            response = self.config.client.post(url, json=payload)
            
            if response.status_code != 201:
                logger.error(f"Circle transfer failed: {response.text}")
                raise Exception(f"Transfer failed: {response.text}")
            
            tx = response.json()["data"]
            logger.info(f"Transfer initiated: {tx['id']} ({amount_usdc} USDC to {to_address})")
            
            return {
                "transaction_id": tx["id"],
                "from_address": tx.get("source", {}).get("address", ""),
                "to_address": to_address,
                "amount": str(amount_usdc),
                "state": tx["state"],
                "txHash": tx.get("txHash", None)
            }
        except Exception as e:
            logger.error(f"Circle transfer error: {e}")
            raise
    
    def get_transaction_status(self, transaction_id: str) -> dict:
        """Get transaction status."""
        try:
            # The GET endpoint for transactions does not use /developer
            url = f"{CIRCLE_API_URL}/w3s/transactions/{transaction_id}"
            response = self.config.client.get(url)
            
            # FORCE DEBUG PRINT FOR 404s TOO
            if response.status_code == 404:
                print(f"   [DEBUG] Circle API returned 404 Not Found for {transaction_id[:8]}...")
                return {"state": "INDEXING", "txHash": None, "confirmations": 0}
            
            if response.status_code != 200:
                logger.error(f"Transaction status fetch failed: {response.text}")
                raise Exception(f"Failed to get transaction status: {response.text}")
            
            data = response.json()["data"]
            # For developer-controlled wallets, the fields are top-level in 'data'
            tx = data.get("transaction", data) 
            
            state = tx.get("state")
            tx_hash = tx.get("txHash")
            
            # FORCE DEBUG PRINT
            print(f"   [DEBUG] ID: {transaction_id[:8]} | State: {state} | Hash: {tx_hash}")
            
            return {
                "state": state,
                "txHash": tx_hash,
                "confirmations": tx.get("blockchainTxId", {}).get("confirmations", 0) if isinstance(tx.get("blockchainTxId"), dict) else 0
            }
        except Exception as e:
            logger.error(f"Transaction status error: {e}")
            raise


def get_circle_client(
    api_key: Optional[str] = None,
    entity_secret: Optional[str] = None,
    wallet_set_id: Optional[str] = None
) -> CircleClient:
    """
    Factory function: Get Circle client from parameters or environment variables.
    
    Args (can pass directly to avoid .env re-reads):
        api_key: Circle API Key (or reads from CIRCLE_API_KEY)
        entity_secret: Entity Secret (or reads from CIRCLE_ENTITY_SECRET)
        wallet_set_id: Wallet Set ID (or reads from CIRCLE_WALLET_SET_ID)
    
    This allows bootstrap to pass in-memory values directly rather than 
    relying on .env file re-reads which can be stale.
    """
    # Use provided values, fallback to .env
    api_key = api_key or os.getenv("CIRCLE_API_KEY")
    entity_secret = entity_secret or os.getenv("CIRCLE_ENTITY_SECRET")
    wallet_set_id = wallet_set_id or os.getenv("CIRCLE_WALLET_SET_ID")
    
    if not all([api_key, entity_secret]):
        raise ValueError(
            "Core Circle credentials not configured. "
            "Set CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET"
        )
    
    config = CircleWalletConfig(api_key, entity_secret, wallet_set_id)
    return CircleClient(config)





def generate_keypair():
    """Generate a new secure random ECDSA keypair (secp256k1)."""
    # Use secrets module for cryptographically secure random private key
    private_key_bytes = secrets.token_bytes(32)
    private_key = keys.PrivateKey(private_key_bytes)
    return {
        "private_key_hex": private_key.to_hex(),
        "public_key_hex": private_key.public_key.to_hex(),
        "address": private_key.public_key.to_checksum_address()
    }


def create_payload_hash(amount_usdc: float, sender: str, recipient: str, 
                        nonce: str, expiry_timestamp: int) -> str:
    """
    Create a deterministic SHA256 hash of the payment payload.
    Uses a stable colon-separated format to avoid JSON serialization quirks.
    """
    # Format amount to exactly 6 decimal places for deterministic stringification
    amount_str = "{:.6f}".format(float(amount_usdc))
    
    payload = f"{amount_str}:{sender.lower()}:{recipient.lower()}:{nonce}:{expiry_timestamp}"
    return hashlib.sha256(payload.encode()).hexdigest()


def sign_x402_header(private_key_hex: str, amount_usdc: float, sender: str, 
                     recipient: str, nonce: str, expiry_timestamp: int) -> dict:
    """
    Generate a signed x402 payment header.
    
    Returns:
        {
            "amount": float,
            "sender": str,
            "recipient": str,
            "nonce": str,
            "expiry": int,
            "signature": str (hex)
        }
    """
    private_key = keys.PrivateKey(bytes.fromhex(private_key_hex.replace("0x", "")))
    
    # Create payload hash
    payload_hash = create_payload_hash(amount_usdc, sender, recipient, nonce, expiry_timestamp)
    
    # Sign with private key (ECDSA secp256k1)
    message_bytes = bytes.fromhex(payload_hash)
    signature = private_key.sign_msg(message_bytes)
    
    return {
        "amount": amount_usdc,
        "sender": sender,
        "recipient": recipient,
        "nonce": nonce,
        "expiry": expiry_timestamp,
        "signature": signature.to_hex(),
        "public_key": private_key.public_key.to_hex()
    }


def verify_x402_signature(header: dict) -> bool:
    """
    Verify an x402 payment header signature.
    
    Args:
        header: {
            "amount": float,
            "sender": str,
            "recipient": str,
            "nonce": str,
            "expiry": int,
            "signature": str,
            "public_key": str
        }
    
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Recreate payload hash
        payload_hash = create_payload_hash(
            header["amount"],
            header["sender"],
            header["recipient"],
            header["nonce"],
            header["expiry"]
        )
        
        # Recover public key from signature
        message_bytes = bytes.fromhex(payload_hash)
        sig_bytes = bytes.fromhex(header["signature"].replace("0x", ""))
        sig = keys.Signature(sig_bytes)
        
        recovered_pubkey = sig.recover_public_key_from_msg(message_bytes)
        recovered_address = recovered_pubkey.to_checksum_address()
        
        # Check if recovered address matches sender
        return recovered_address.lower() == header["sender"].lower()
    
    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False


def validate_x402_header(header: dict, expected_recipient: str) -> tuple[bool, str]:
    """
    Full validation of x402 header:
    1. Signature is valid
    2. Recipient matches expected recipient
    3. Expiry is in the future
    
    Returns:
        (valid: bool, reason: str)
    """
    import time
    
    # Check expiry
    if header["expiry"] < int(time.time()):
        return False, "Header expired"
    
    # Check recipient
    if header["recipient"].lower() != expected_recipient.lower():
        return False, "Recipient mismatch"
    
    # Check signature
    if not verify_x402_signature(header):
        return False, "Invalid signature"
    
    return True, "OK"


if __name__ == "__main__":
    # Quick test
    keypair = generate_keypair()
    print(f"Private key: {keypair['private_key_hex']}")
    print(f"Address: {keypair['address']}")
    
    # Create a signed header
    import time
    now = int(time.time())
    header = sign_x402_header(
        keypair["private_key_hex"],
        0.001,  # $0.001 USDC
        keypair["address"],
        "0x1234567890123456789012345678901234567890",  # recipient
        "nonce-12345",
        now + 60
    )
    
    print(f"\nSigned header: {header}")
    
    # Verify it
    valid, reason = validate_x402_header(header, header["recipient"])
    print(f"Verification: {valid} ({reason})")




DATABASE_PATH = os.getenv("AGORA_DB_PATH", "agora_local.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    
    # Proactive check: If DB was wiped while server is running, recreate tables
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
        if not cursor.fetchone():
            from shared.core import init_database
            init_database()
    except:
        pass
        
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Agents table (wallets)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT UNIQUE NOT NULL,
                description TEXT,
                capabilities TEXT,
                reputation_score INTEGER DEFAULT 100,
                total_transactions INTEGER DEFAULT 0,
                successful_transactions INTEGER DEFAULT 0,
                failed_transactions INTEGER DEFAULT 0,
                unique_counterparties INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Providers table (services offered by agents)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                description TEXT,
                price_usdc REAL NOT NULL,
                endpoint_url TEXT,
                capacity INTEGER DEFAULT 100,
                current_load INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                buyer_id TEXT NOT NULL,
                seller_id TEXT NOT NULL,
                provider_id TEXT,
                amount_usdc REAL NOT NULL,
                nonce TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'pending',
                service_delivered BOOLEAN DEFAULT 0,
                result TEXT,
                arc_tx_hash TEXT,
                proof_of_service_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (buyer_id) REFERENCES agents(id),
                FOREIGN KEY (seller_id) REFERENCES agents(id),
                FOREIGN KEY (provider_id) REFERENCES providers(id)
            )
        """)

        # Nonces table (for replay prevention)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nonces (
                nonce TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                used_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Reputation events table (audit trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reputation_events (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                delta INTEGER,
                reason TEXT,
                transaction_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        conn.commit()
        print("✓ Database initialized")


def create_agent(agent_id: str, name: str, address: str,
                 description: str = None, capabilities: str = None):
    """Create a new agent."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents (id, name, address, description, capabilities, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_id, name, address, description, capabilities, now, now))
        conn.commit()


def register_provider(provider_id: str, agent_id: str, name: str, service_type: str, 
                     description: str, price_usdc: float, endpoint_url: str = None):
    """Register a new service provider."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO providers 
            (id, agent_id, name, service_type, description, price_usdc, endpoint_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (provider_id, agent_id, name, service_type, description, price_usdc, endpoint_url, now, now))
        conn.commit()


def record_transaction(tx_id: str, buyer_id: str, seller_id: str, provider_id: str,
                       amount_usdc: float, nonce: str):
    """Record a new transaction."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions 
            (id, buyer_id, seller_id, provider_id, amount_usdc, nonce, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tx_id, buyer_id, seller_id, provider_id, amount_usdc, nonce, now, now))
        conn.commit()


def get_agent(agent_id: str):
    """Fetch agent by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_providers():
    """Fetch all active providers."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, a.reputation_score, a.name as agent_name
            FROM providers p
            JOIN agents a ON p.agent_id = a.id
            WHERE p.is_active = 1
            ORDER BY a.reputation_score DESC, p.price_usdc ASC
        """)
        return [dict(row) for row in cursor.fetchall()]


def search_providers(query: str):
    """Search providers by name or description (keyword matching)."""
    query_lower = query.lower()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, a.reputation_score, a.name as agent_name
            FROM providers p
            JOIN agents a ON p.agent_id = a.id
            WHERE (LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ?)
            AND p.is_active = 1
            ORDER BY a.reputation_score DESC, p.price_usdc ASC
        """, (f"%{query_lower}%", f"%{query_lower}%"))
        return [dict(row) for row in cursor.fetchall()]


def get_transaction_history(agent_id: str = None, limit: int = 100):
    """Fetch transaction history, optionally filtered by agent."""
    with get_db() as conn:
        cursor = conn.cursor()
        if agent_id:
            cursor.execute("""
                SELECT * FROM transactions
                WHERE buyer_id = ? OR seller_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (agent_id, agent_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM transactions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def update_transaction_status(tx_id: str, status: str, arc_tx_hash: str = None):
    """Update transaction status."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET status = ?, arc_tx_hash = ?, updated_at = ?
            WHERE id = ?
        """, (status, arc_tx_hash, now, tx_id))
        conn.commit()


def record_service_result(tx_id: str, result: str, proof_hash: str = None):
    """Record service execution result (JSON stringified) and cryptographic proof."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET result = ?, proof_of_service_hash = ?, service_delivered = 1, updated_at = ?
            WHERE id = ?
        """, (result, proof_hash, now, tx_id))
        conn.commit()

def update_agent_reputation(agent_id: str, delta: int, reason: str = None, tx_id: str = None, proof_hash: str = None):
    """Update agent's reputation score with cryptographic proof (ERC-8004 alignment)."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Update score
        cursor.execute("""
            UPDATE agents
            SET reputation_score = reputation_score + ?,
                updated_at = ?
            WHERE id = ?
        """, (delta, now, agent_id))
        
        # If there's a cryptographic proof of service, append to reason
        if proof_hash:
            reason = f"{reason} | Proof: {proof_hash}"

        # Log event
        import uuid
        event_id = str(uuid.uuid4())[:8]
        cursor.execute("""
            INSERT INTO reputation_events (id, agent_id, event_type, delta, reason, transaction_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_id, agent_id, "score_update", delta, reason, tx_id, now))
        
        conn.commit()


if __name__ == "__main__":
    init_database()




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
        from shared.core import get_db
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
        from shared.core import get_db
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
        from shared.core import get_db
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



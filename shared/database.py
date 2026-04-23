"""
shared/database.py

SQLite database initialization and utilities for Agora.
Handles agents, transactions, nonces, and reputation.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = os.getenv("AGORA_DB_PATH", "agora_local.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
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
                private_key TEXT,
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


def create_agent(agent_id: str, name: str, address: str, private_key: str = None,
                 description: str = None, capabilities: str = None):
    """Create a new agent."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents (id, name, address, private_key, description, capabilities, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (agent_id, name, address, private_key, description, capabilities, now, now))
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

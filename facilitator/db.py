"""
SQLite-backed storage for the facilitator.

Tables
------
agents          — registered agents (one row per agent)
services        — services exposed by an agent (many per agent)
nonces          — used x402 nonces, with TTL
transactions    — settlement ledger (gross, fee, net)
treasury_log    — every fee credited to the marketplace treasury
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

DB_PATH = os.getenv("FACILITATOR_DB_PATH", "agora_facilitator.db")
_LOCK = threading.Lock()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        c = conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                endpoint_url TEXT,
                description TEXT,
                listing_fee_paid REAL DEFAULT 0,
                listing_tx_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price_usdc REAL NOT NULL,
                endpoint_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );

            CREATE TABLE IF NOT EXISTS nonces (
                nonce TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                resource TEXT NOT NULL,
                amount REAL NOT NULL,
                used_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                buyer_address TEXT NOT NULL,
                seller_agent_id TEXT,
                seller_address TEXT NOT NULL,
                service_id TEXT,
                resource TEXT NOT NULL,
                gross_usdc REAL NOT NULL,
                marketplace_fee_usdc REAL NOT NULL,
                net_usdc REAL NOT NULL,
                kind TEXT NOT NULL,        -- 'service' | 'listing_fee'
                settlement_mode TEXT NOT NULL,
                settlement_ref TEXT,
                status TEXT NOT NULL,
                nonce TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS treasury_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id TEXT NOT NULL,
                amount_usdc REAL NOT NULL,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_nonces_expires ON nonces(expires_at);
            CREATE INDEX IF NOT EXISTS idx_tx_seller ON transactions(seller_agent_id);
            CREATE INDEX IF NOT EXISTS idx_tx_buyer ON transactions(buyer_address);
            """
        )


# ── Agents ──────────────────────────────────────────────────────────────────


def upsert_agent(
    *,
    agent_id: str,
    name: str,
    address: str,
    endpoint_url: str,
    description: str,
    listing_fee_paid: float,
    listing_tx_id: Optional[str],
) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO agents (id, name, address, endpoint_url, description,
                                listing_fee_paid, listing_tx_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                endpoint_url = excluded.endpoint_url,
                description = excluded.description,
                listing_fee_paid = agents.listing_fee_paid + excluded.listing_fee_paid,
                listing_tx_id = excluded.listing_tx_id
            """,
            (agent_id, name, address, endpoint_url, description, listing_fee_paid, listing_tx_id, now),
        )


def get_agent(agent_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None


def list_agents() -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY created_at DESC")]


# ── Services ────────────────────────────────────────────────────────────────


def upsert_service(
    *,
    service_id: str,
    agent_id: str,
    name: str,
    description: str,
    category: str,
    price_usdc: float,
    endpoint_url: str,
) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO services (id, agent_id, name, description, category, price_usdc,
                                  endpoint_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                category = excluded.category,
                price_usdc = excluded.price_usdc,
                endpoint_url = excluded.endpoint_url
            """,
            (service_id, agent_id, name, description, category, price_usdc, endpoint_url, now),
        )


def list_services() -> list[dict]:
    with get_db() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT s.*, a.name AS agent_name, a.address AS agent_address
                FROM services s JOIN agents a ON s.agent_id = a.id
                ORDER BY s.created_at DESC
                """
            )
        ]


# ── Transactions ────────────────────────────────────────────────────────────


def insert_transaction(**kwargs) -> None:
    fields = (
        "id", "buyer_address", "seller_agent_id", "seller_address", "service_id",
        "resource", "gross_usdc", "marketplace_fee_usdc", "net_usdc", "kind",
        "settlement_mode", "settlement_ref", "status", "nonce", "created_at",
    )
    with get_db() as conn:
        conn.execute(
            f"INSERT INTO transactions ({', '.join(fields)}) "
            f"VALUES ({', '.join('?' for _ in fields)})",
            tuple(kwargs.get(f) for f in fields),
        )


def list_transactions(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        ]


def append_treasury(tx_id: str, amount: float, kind: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO treasury_log (tx_id, amount_usdc, kind, created_at) VALUES (?, ?, ?, ?)",
            (tx_id, amount, kind, now),
        )


def treasury_total() -> float:
    with get_db() as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount_usdc), 0) AS t FROM treasury_log").fetchone()
        return float(row["t"])

"""
agora-agent CLI

Usage
-----

    agora-agent run agents/summarybot/agent.py --port 9001
    agora-agent keygen
    agora-agent register agents/summarybot/agent.py --port 9001

The ``run`` command imports the user's agent module — the module is expected
to define a top-level ``server`` of type :class:`AgentServer`. The CLI just
calls ``server.run(port=...)``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import click

from agora_x402.agent_server import AgentServer
from agora_x402.facilitator_client import FacilitatorClient
from agora_x402.pay_for import get_service_registry
from agora_x402.wallet import Wallet, generate_keypair
from agora_x402.x402_protocol import (
    encode_payment_header,
    sign_payment_header,
)


def _load_agent_module(path: str):
    """Import a Python file as a one-off module, returning the module object.

    The user's agent file is expected to construct a top-level
    ``server = AgentServer(...)``.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise click.ClickException(f"Agent file not found: {p}")

    # Make the parent dir importable so the agent can `from agora_x402 import ...`
    repo_root = _find_repo_root(p)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Auto-load .env BEFORE importing the agent module, so each agent's
    # `Wallet.from_env(...)` call sees the keys regardless of how this CLI
    # was invoked. Without this, agents started from a fresh shell silently
    # fall back to ephemeral wallets that don't match the rest of the system.
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
        env_file = repo_root / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
    except ImportError:
        pass  # dotenv is in requirements; if absent, just skip

    spec = importlib.util.spec_from_file_location(p.stem, p)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"Cannot import {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_repo_root(start: Path) -> Path:
    """Walk up until we find a dir containing pyproject.toml; fall back to cwd."""
    cur = start.parent
    while cur != cur.parent:
        if (cur / "pyproject.toml").exists():
            return cur
        cur = cur.parent
    return Path.cwd()


def _get_server(mod) -> AgentServer:
    server = getattr(mod, "server", None)
    if not isinstance(server, AgentServer):
        raise click.ClickException(
            f"Agent module {mod.__name__} must define a top-level "
            f"`server = AgentServer(...)`"
        )
    return server


# ────────────────────────────────────────────────────────────────────────────
# CLI commands
# ────────────────────────────────────────────────────────────────────────────


@click.group()
def main() -> None:
    """Agora x402 — agent runner & utilities."""


@main.command()
@click.argument("agent_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", type=int, default=9001, help="HTTP port to bind on.")
@click.option("--host", default=None, help="Bind host (default $AGENT_HOST or 0.0.0.0).")
@click.option(
    "--public-base-url",
    default=None,
    help="Override the public URL advertised in 402 challenges (e.g. behind a reverse proxy).",
)
def run(agent_file: str, port: int, host: Optional[str], public_base_url: Optional[str]) -> None:
    """Start an agent application defined in AGENT_FILE."""
    mod = _load_agent_module(agent_file)
    server = _get_server(mod)
    if public_base_url:
        server.public_base_url = public_base_url
    host = host or os.getenv("AGENT_HOST", "0.0.0.0")
    server.run(host=host, port=port)


@main.command()
@click.option("--out", default=None, help="Write the keypair to this .env file.")
@click.option("--prefix", default="AGENT", help="Env var prefix (e.g. SUMMARYBOT).")
def keygen(out: Optional[str], prefix: str) -> None:
    """Generate a fresh ECDSA keypair for an agent."""
    kp = generate_keypair()
    click.echo(f"{prefix}_PRIVATE_KEY={kp['private_key']}")
    click.echo(f"{prefix}_ADDRESS={kp['address']}")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{prefix}_PRIVATE_KEY={kp['private_key']}\n")
            f.write(f"{prefix}_ADDRESS={kp['address']}\n")
        click.echo(f"\n→ appended to {out}")


@main.command()
@click.argument("agent_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", type=int, default=9001, help="Port the agent will run on.")
@click.option("--public-base-url", default=None, help="Public base URL of the agent.")
@click.option(
    "--facilitator-url",
    default=None,
    help="Facilitator URL (default $FACILITATOR_URL).",
)
def register(
    agent_file: str,
    port: int,
    public_base_url: Optional[str],
    facilitator_url: Optional[str],
) -> None:
    """Register an agent + its services with the marketplace facilitator.

    Pays the listing fee from the agent's own wallet (no extra setup needed).
    """
    mod = _load_agent_module(agent_file)
    server = _get_server(mod)
    base = public_base_url or f"http://localhost:{port}"

    fac = FacilitatorClient(facilitator_url or server.facilitator_url)
    fees = fac.get_listing_fee()
    listing_fee = str(fees.get("listing_fee_usdc", "0"))
    treasury = fees.get("treasury_address", "")

    # Build a signed payment for the listing fee
    listing_payment = None
    if float(listing_fee) > 0:
        if not treasury:
            raise click.ClickException("Marketplace did not advertise a treasury address.")
        listing_payment = sign_payment_header(
            private_key_hex=server.wallet.private_key,
            amount=listing_fee,
            sender=server.wallet.address,
            recipient=treasury,
            resource=f"{fac.base_url}/agents/register",
            expiry_seconds=120,
        )

    res = fac.register_agent(
        agent_id=server.agent_id,
        name=server.name,
        address=server.wallet.address,
        endpoint_url=base,
        description=server.description,
        listing_fee_payment=listing_payment,
    )
    click.echo(f"✅ Registered agent: {res}")

    registry = get_service_registry()
    for spec in registry.all().values():
        sres = fac.register_service(
            agent_id=server.agent_id,
            service_id=f"{server.agent_id}-{spec.service_id}",
            name=spec.name,
            description=spec.description,
            price=spec.price,
            category=spec.category,
            endpoint_url=f"{base}{spec.path}",
        )
        click.echo(f"   ↳ service '{spec.name}' registered: {sres.get('service_id')}")


if __name__ == "__main__":
    main()

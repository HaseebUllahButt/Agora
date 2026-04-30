"""
@pay_for decorator + service registry.

Decorate a Python function to expose it as a paid HTTP endpoint on an
``AgentServer``. The decorator only registers metadata; the server module is
what actually publishes the route and enforces payment.

Usage
-----

    from agora_x402 import pay_for

    @pay_for(price="0.001", description="Summarize a chunk of text")
    def summarize(text: str) -> dict:
        return {"summary": text[:120] + "..."}

The decorated function is unmodified — calling it directly inside Python still
runs the body without any payment checks. Payment enforcement is a server-side
concern.
"""

from __future__ import annotations

import functools
import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "service"


@dataclass
class ServiceSpec:
    """Static metadata for a paid service."""

    service_id: str
    name: str
    price: str  # USDC, decimal string
    description: str
    category: str
    func: Callable[..., Any]
    method: str = "POST"
    path: Optional[str] = None  # filled in by AgentServer if not given

    def signature_params(self) -> List[str]:
        """Names of parameters the underlying function accepts (for docs)."""
        try:
            sig = inspect.signature(self.func)
            return [p for p in sig.parameters if p != "self"]
        except (TypeError, ValueError):
            return []


class ServiceRegistry:
    """Process-wide registry of @pay_for-decorated services.

    Backed by an ordinary dict — agents are single-process by design, so
    threading concerns are limited to FastAPI request handlers reading the
    registry, which is safe (the registry is populated at import time).
    """

    def __init__(self) -> None:
        self._services: Dict[str, ServiceSpec] = {}

    def register(self, spec: ServiceSpec) -> None:
        if spec.service_id in self._services:
            raise ValueError(
                f"Service id '{spec.service_id}' already registered. "
                f"Pass a unique `name=` to @pay_for to disambiguate."
            )
        self._services[spec.service_id] = spec

    def get(self, service_id: str) -> Optional[ServiceSpec]:
        return self._services.get(service_id)

    def all(self) -> Dict[str, ServiceSpec]:
        return dict(self._services)

    def clear(self) -> None:  # for tests
        self._services.clear()


_REGISTRY = ServiceRegistry()


def get_service_registry() -> ServiceRegistry:
    """Return the global :class:`ServiceRegistry`."""
    return _REGISTRY


def pay_for(
    *,
    price: str,
    description: str = "",
    name: Optional[str] = None,
    category: str = "capability",
    method: str = "POST",
    path: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a paid x402 endpoint.

    Parameters
    ----------
    price
        USDC price per call, as a decimal string (e.g. ``"0.001"``). Strings are
        used to avoid floating-point surprises in money math.
    description
        Human-readable description, surfaced in payment requirements + docs.
    name
        Public service name (defaults to the function name).
    category
        Free-form label, e.g. ``"llm"``, ``"data"``, ``"compute"``.
    method
        HTTP method to expose (``POST`` is the right answer in almost every case).
    path
        URL path. Defaults to ``/<slug(name)>``.
    """

    if isinstance(price, (int, float)):
        price = format(float(price), "f")
    price_str = str(price)
    try:
        if float(price_str) < 0:
            raise ValueError("price must be ≥ 0")
    except ValueError as e:
        raise ValueError(f"@pay_for(price=...): {e}") from None

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        service_name = name or func.__name__
        slug = _slugify(service_name)
        service_path = path or f"/{slug}"
        service_desc = description or (func.__doc__ or "").strip().split("\n")[0] or service_name

        spec = ServiceSpec(
            service_id=slug,
            name=service_name,
            price=price_str,
            description=service_desc,
            category=category,
            func=func,
            method=method.upper(),
            path=service_path,
        )
        _REGISTRY.register(spec)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__agora_spec__ = spec  # type: ignore[attr-defined]
        return wrapper

    return decorator

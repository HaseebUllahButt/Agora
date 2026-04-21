"""
sdk/provider.py

Provider-side SDK: @pay_for decorator for monetizing services.

Clean, atomic payment + execution model:
- Function decorated with @pay_for gets registered with a unique service ID
- Buyer pays first → atomic nonce check → function executes → result returned
- Registry stores callable references for the API to invoke
"""

import functools
import uuid
from datetime import datetime
from typing import Callable, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ──────────────────────────────────────────────────────────────────────────────
# SERVICE REGISTRY
# ──────────────────────────────────────────────────────────────────────────────

class ServiceRegistry:
    """Thread-safe registry of callable services."""
    
    def __init__(self):
        self._services: Dict[str, Dict[str, Any]] = {}
    
    def register(self, service_id: str, name: str, func: Callable, 
                 price: float, category: str, description: str):
        """Register a callable service."""
        self._services[service_id] = {
            "id": service_id,
            "name": name,
            "function": func,
            "price": price,
            "category": category,
            "description": description,
            "created_at": datetime.utcnow().isoformat()
        }
    
    def get(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Fetch service metadata + callable."""
        return self._services.get(service_id)
    
    def get_function(self, service_id: str) -> Optional[Callable]:
        """Get just the callable function."""
        service = self.get(service_id)
        return service["function"] if service else None
    
    def all(self) -> Dict[str, Dict[str, Any]]:
        """Get all services (without function callables for safety)."""
        return {
            sid: {k: v for k, v in svc.items() if k != "function"}
            for sid, svc in self._services.items()
        }


# Global registry instance
_REGISTRY = ServiceRegistry()


# ──────────────────────────────────────────────────────────────────────────────
# DECORATOR
# ──────────────────────────────────────────────────────────────────────────────

def pay_for(price: float, category: str = "capability", 
            name: Optional[str] = None, description: Optional[str] = None):
    """
    Decorator: Mark a function as a paid Agora service.
    
    Args:
        price: Price in USDC per call
        category: Service type (data, compute, capability, etc.)
        name: Service name (defaults to function name)
        description: Registry description (defaults to docstring)
    
    Returns:
        Decorated function registered in global service registry
    
    The decorator doesn't modify the function itself — it just registers it.
    The API's /purchase endpoint will look up the service and execute it.
    """
    def decorator(func: Callable) -> Callable:
        service_name = name or func.__name__
        service_id = str(uuid.uuid4())[:8]
        service_desc = description or func.__doc__ or f"{service_name} service"
        
        # Register in global registry
        _REGISTRY.register(
            service_id=service_id,
            name=service_name,
            func=func,
            price=price,
            category=category,
            description=service_desc
        )
        
        # Return unwrapped function (API handles payment validation)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Attach metadata for introspection
        wrapper.__agora_service_id__ = service_id
        wrapper.__agora_price__ = price
        
        return wrapper
    
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def get_service_registry() -> ServiceRegistry:
    """Get the global service registry."""
    return _REGISTRY


def call_service(service_id: str, *args, **kwargs) -> Any:
    """
    Execute a registered service function.
    
    Args:
        service_id: Service ID from registry
        *args, **kwargs: Arguments to pass to the service
    
    Returns:
        Result from the service function
    
    Raises:
        ValueError: If service not found
    """
    func = _REGISTRY.get_function(service_id)
    if not func:
        raise ValueError(f"Service {service_id} not found in registry")
    
    return func(*args, **kwargs)


if __name__ == "__main__":
    # Test decorator registration
    
    @pay_for(price=0.001, category="data", description="Example search")
    def example_search(query: str) -> str:
        return f"Found results for: {query}"
    
    @pay_for(price=0.002, category="capability", description="Example analysis")
    def example_analyze(data: str) -> str:
        return f"Analysis of: {data}"
    
    registry = get_service_registry()
    services = registry.all()
    
    print(f"✓ {len(services)} services registered:")
    for sid, svc in services.items():
        print(f"  - {svc['name']} (${svc['price']:.6f})")



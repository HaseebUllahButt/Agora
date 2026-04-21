"""
shared/event_bus.py — WebSocket Event Bus for Live Transactions

Simple pub/sub for broadcasting real-time transaction events to subscribed clients.
"""

import asyncio
from typing import Set, Callable, Any
import json


class EventBus:
    """
    Thread-safe pub/sub event bus.
    
    Usage:
        event_bus = EventBus()
        
        # Broadcast an event
        event_bus.publish("transaction", {
            "tx_id": "abc123",
            "buyer": "alice",
            "seller": "bob",
            "amount": 0.01,
            ...
        })
        
        # Subscribe to stream
        async def receive_events():
            async for event in event_bus.subscribe("transaction"):
                print(f"New event: {event}")
    """
    
    def __init__(self):
        """Initialize event bus with empty subscribers."""
        self._subscribers: dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, event_type: str):
        """
        Subscribe to events of a given type.
        
        Yields events as they are published.
        Generator pattern: `async for event in bus.subscribe("transaction")`
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = set()
            self._subscribers[event_type].add(queue)
        
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[event_type].discard(queue)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
    
    def publish(self, event_type: str, data: dict[str, Any]):
        """Broadcast an event to all subscribers."""
        if event_type not in self._subscribers:
            return  # No subscribers
        
        # Create a task to push to all queues (non-blocking)
        asyncio.create_task(self._broadcast(event_type, data))
    
    async def _broadcast(self, event_type: str, data: dict[str, Any]):
        """Internal: push event to all subscriber queues."""
        async with self._lock:
            # Make a copy in case subscribers change during iteration
            queues = list(self._subscribers.get(event_type, set()))
        
        for queue in queues:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                # Queue full, skip this subscriber
                pass


# Global singleton instance
_event_bus = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

"""
shared/event_bus.py — Thread-Safe WebSocket Event Bus
"""

import asyncio
import threading
from typing import Set, Any
import logging

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

"""
orchestrator/audit_logger.py

Structured audit trail for every orchestrator decision.

The audit log is Agora's chain-of-thought. Every agent hire, every payment,
every validation decision, and every budget check is recorded here with a
timestamp. The log is returned in the final pipeline result and streamed
to the frontend audit panel in real time.
"""

from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    """
    Append-only timestamped log for a single pipeline run.

    Usage:
        audit = AuditLogger()
        audit.log("Starting pipeline", {"topic": topic, "budget": budget})
        ...
        entries = audit.get_log()
    """

    def __init__(self):
        self.entries: list[dict] = []

    def log(self, message: str, data: Any = None) -> None:
        """
        Append a log entry with UTC timestamp.

        Args:
            message: Human-readable description of what happened
            data:    Optional structured data (dict, list, or any serialisable value)
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "data": data
        }
        self.entries.append(entry)
        print(f"[AGORA AUDIT] {entry['timestamp']}: {message}")

    def get_log(self) -> list[dict]:
        """Return all entries as a list of dicts."""
        return self.entries

    def get_last(self, n: int = 10) -> list[dict]:
        """Return the most recent n entries."""
        return self.entries[-n:]

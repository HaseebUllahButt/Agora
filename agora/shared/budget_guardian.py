"""
shared/budget_guardian.py

Spending limit enforcement and real-time budget tracking for the Agora pipeline.

The BudgetGuardian is the financial safety layer of Agora.
Every payment goes through can_spend() before it's initiated.
Every completed payment is recorded via record_spend().
If the budget drops below 20%, warnings are emitted.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class BudgetGuardian:
    """
    Tracks spending against a user-defined budget for a single pipeline run.

    Attributes:
        total_budget:   Maximum USDC the orchestrator can spend
        spent:          Running total of confirmed payments
        transactions:   Ledger of every payment made
        warnings:       List of budget warning messages emitted
    """
    total_budget: float
    spent: float = 0.0
    transactions: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def can_spend(self, amount: float) -> bool:
        """True if spending `amount` would not exceed total_budget."""
        return (self.spent + amount) <= self.total_budget

    def record_spend(
        self,
        amount: float,
        tx_hash: str,
        agent: str,
        task: str
    ) -> None:
        """
        Record a confirmed on-chain payment.

        Args:
            amount:   USDC amount paid
            tx_hash:  On-chain transaction hash
            agent:    Agent name that received the payment
            task:     Description of the task the agent was paid for
        """
        self.spent = round(self.spent + amount, 6)
        entry = {
            "amount": amount,
            "tx_hash": tx_hash,
            "agent": agent,
            "task": task,
            "cumulative_spent": self.spent,
            "remaining": self.remaining()
        }
        self.transactions.append(entry)

        # Emit 20% warning
        if self.remaining() < (self.total_budget * 0.2):
            msg = f"WARNING: Only ${self.remaining():.4f} USDC remaining"
            self.warnings.append(msg)

    def remaining(self) -> float:
        """USDC remaining in budget."""
        return round(self.total_budget - self.spent, 6)

    def is_exhausted(self) -> bool:
        """True when no budget remains."""
        return self.spent >= self.total_budget

    def summary(self) -> dict:
        """Full budget summary for audit log and final report."""
        return {
            "total_budget": self.total_budget,
            "total_spent": self.spent,
            "remaining": self.remaining(),
            "utilization_pct": round((self.spent / self.total_budget) * 100, 1),
            "transaction_count": len(self.transactions),
            "transactions": self.transactions,
            "warnings": self.warnings
        }

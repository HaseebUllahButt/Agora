"""
sdk/exceptions.py

Custom exceptions for Agora SDK.
"""


class BudgetExceeded(Exception):
    """Raised when an agent tries to purchase beyond their budget."""
    
    def __init__(self, service_cost: float, remaining_budget: float):
        self.service_cost = service_cost
        self.remaining_budget = remaining_budget
        self.message = (
            f"Insufficient budget: service costs ${service_cost:.4f}, "
            f"but only ${remaining_budget:.4f} remaining"
        )
        super().__init__(self.message)

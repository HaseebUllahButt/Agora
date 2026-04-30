"""Exception hierarchy for agora_x402."""


class AgoraError(Exception):
    """Base for all agora_x402 errors."""


class PaymentRequired(AgoraError):
    """Raised by clients when a server returned 402 and the client could not
    (or was configured not to) pay automatically."""

    def __init__(self, message: str, requirements: dict | None = None):
        super().__init__(message)
        self.requirements = requirements or {}


class InvalidPaymentHeader(AgoraError):
    """The submitted X-PAYMENT header could not be decoded or verified."""


class SettlementFailed(AgoraError):
    """The facilitator (or Circle) refused or failed to settle the payment."""

    def __init__(self, message: str, raw: dict | None = None):
        super().__init__(message)
        self.raw = raw or {}


class FacilitatorUnreachable(AgoraError):
    """The facilitator service could not be reached."""

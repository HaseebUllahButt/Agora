"""
Marketplace fee logic.

Two fees:

1. **Listing fee** — flat, paid once when an agent registers itself.
   Example: ``0.10`` USDC.
2. **Per-transaction fee** — basis-points cut taken from every settled
   service payment. Example: ``250`` bps (= 2.5%).

Both are configurable via env vars (see ``.env.example``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceFees:
    listing_fee_usdc: float
    tx_fee_bps: int  # basis points; 250 = 2.5%
    treasury_address: str

    def split(self, gross_usdc: float) -> tuple[float, float]:
        """Return ``(marketplace_fee, net_to_seller)``."""
        fee = round(gross_usdc * self.tx_fee_bps / 10_000, 8)
        # Never charge more than the gross
        fee = min(fee, gross_usdc)
        net = round(gross_usdc - fee, 8)
        return fee, net


def load_fees() -> MarketplaceFees:
    return MarketplaceFees(
        listing_fee_usdc=float(os.getenv("MARKETPLACE_LISTING_FEE", "0.10")),
        tx_fee_bps=int(os.getenv("MARKETPLACE_TX_FEE_BPS", "250")),
        treasury_address=os.getenv(
            "MARKETPLACE_TREASURY_ADDRESS",
            "0x000000000000000000000000000000000000dEaD",
        ),
    )

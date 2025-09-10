"""Reconciliation status enum for unified reconciliation results."""

from enum import Enum


class ReconStatus(Enum):
    """Reconciliation status for unified trade matching results.

    This is the standardized enum used across all matching modules.
    - MATCHED: Normal successful match
    - PENDING_EXCHANGE: SGX-specific, when exchange trade has pending clearing status
    - PENDING_APPROVAL: ICE-specific, for matches awaiting approval
    - UNMATCHED_TRADERS: Trader trades that didn't match
    - UNMATCHED_EXCH: Exchange trades that didn't match
    """

    MATCHED = "matched"
    PENDING_EXCHANGE = (
        "pending_exchange"  # SGX-specific: Exchange trade has pending clearing status
    )
    PENDING_APPROVAL = "pending_approval"  # ICE-specific: Match awaiting approval
    UNMATCHED_TRADERS = "unmatched_traders"
    UNMATCHED_EXCH = "unmatched_exch"

"""Reconciliation status enum for standardized reporting."""

from enum import Enum


class ReconStatus(Enum):
    """Reconciliation status for trade matching results."""

    MATCHED = "matched"
    UNMATCHED_TRADERS = "unmatched_traders"
    UNMATCHED_EXCH = "unmatched_exch"
    PENDING_EXCHANGE = "pending_exchange"
    PENDING_APPROVAL = "pending_approval"

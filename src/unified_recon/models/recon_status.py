"""Reconciliation status enum for unified reconciliation results."""

from enum import Enum


class ReconStatus(Enum):
    """Reconciliation status for unified trade matching results."""

    MATCHED = "matched"
    UNMATCHED_TRADERS = "unmatched_traders"
    UNMATCHED_EXCH = "unmatched_exch"
"""Reconciliation status and aggregation type enums for standardized reporting."""

from enum import Enum


class ReconStatus(Enum):
    """Reconciliation status for trade matching results."""

    MATCHED = "matched"
    GROUP_MATCHED = "group_matched"
    UNMATCHED_TRADERS = "unmatched_traders"
    UNMATCHED_EXCH = "unmatched_exch"


class AggregationType(Enum):
    """Type of aggregation used in trade matching."""

    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:N"

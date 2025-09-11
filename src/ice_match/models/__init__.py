"""Data models for energy trade matching system."""

from typing import Union

from .trade import Trade, TradeSource
from .match_result import MatchResult, MatchType
from .recon_status import ReconStatus

# Type alias for matching signature components
# Using float instead of Decimal for signature compatibility (consistent hashing)
SignatureValue = Union[str, float, int, None]

__all__ = [
    "Trade",
    "TradeSource",
    "MatchResult",
    "MatchType",
    "ReconStatus",
    "SignatureValue",
]

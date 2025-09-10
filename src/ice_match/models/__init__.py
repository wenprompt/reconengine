"""Data models for energy trade matching system."""

from typing import Union
from decimal import Decimal

from .trade import Trade, TradeSource
from .match_result import MatchResult, MatchType
from .recon_status import ReconStatus

# Type alias for matching signature components
# Signatures typically contain: str (product, month, buy_sell), Decimal (price, qty), Optional[int] (broker, clearing)
SignatureValue = Union[str, Decimal, int, None]

__all__ = [
    "Trade",
    "TradeSource",
    "MatchResult",
    "MatchType",
    "ReconStatus",
    "SignatureValue",
]

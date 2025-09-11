"""EEX trade matching system data models."""

from typing import Union

from .trade import EEXTrade, EEXTradeSource
from .match_result import EEXMatchResult, EEXMatchType

# Type alias for matching signature components
# Using float instead of Decimal for signature compatibility
SignatureValue = Union[str, float, int, None]

__all__ = [
    "EEXTrade",
    "EEXTradeSource",
    "EEXMatchResult",
    "EEXMatchType",
    "SignatureValue",
]

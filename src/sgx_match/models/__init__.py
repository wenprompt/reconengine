"""SGX Match Models Module"""

from typing import Union
from decimal import Decimal

from .trade import SGXTrade, SGXTradeSource
from .match_result import SGXMatchResult, SGXMatchType

# Type alias for matching signature components
SignatureValue = Union[str, Decimal, int, None]

__all__ = [
    "SGXTrade",
    "SGXTradeSource",
    "SGXMatchResult",
    "SGXMatchType",
    "SignatureValue",
]

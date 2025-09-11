"""SGX Match Models Module"""

from typing import Union

from .trade import SGXTrade, SGXTradeSource
from .match_result import SGXMatchResult, SGXMatchType

# Type alias for matching signature components
# Using float instead of Decimal for signature compatibility (consistent hashing)
SignatureValue = Union[str, float, int, None]

__all__ = [
    "SGXTrade",
    "SGXTradeSource",
    "SGXMatchResult",
    "SGXMatchType",
    "SignatureValue",
]

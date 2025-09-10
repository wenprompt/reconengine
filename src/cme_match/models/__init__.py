"""CME match models module."""

from typing import Union

from .trade import CMETrade, CMETradeSource
from .match_result import CMEMatchResult, CMEMatchType

# Type alias for matching signature components
# Using float instead of Decimal for signature compatibility
SignatureValue = Union[str, float, int, None]

__all__ = [
    "CMETrade",
    "CMETradeSource",
    "CMEMatchResult",
    "CMEMatchType",
    "SignatureValue",
]

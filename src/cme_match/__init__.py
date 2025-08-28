"""CME trade matching system."""

from .models import CMETrade, CMETradeSource, CMEMatchResult, CMEMatchType
from .matchers.exact_matcher import ExactMatcher
from .config import CMEConfigManager
from .core import CMEUnmatchedPool
from .loaders import CMECSVLoader
from .normalizers import CMETradeNormalizer
from .cli import CMEDisplay

__version__ = "0.1.0"
__all__ = [
    "CMETrade",
    "CMETradeSource", 
    "CMEMatchResult",
    "CMEMatchType",
    "ExactMatcher",
    "CMEConfigManager",
    "CMEUnmatchedPool",
    "CMECSVLoader",
    "CMETradeNormalizer",
    "CMEDisplay",
]
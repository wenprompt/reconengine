"""SGX Match Module - Singapore Exchange Trade Matching System

This module provides trade matching capabilities for Singapore Exchange (SGX) data,
focusing on iron ore (FE) futures and options trading.

Features:
- Simple exact matching for SGX trades
- Universal field validation for consistent matching
- Options support (puts/calls with strike prices)
- Non-duplication pool management
- Rich CLI interface with detailed statistics

Architecture:
- config/: Configuration management and normalizer settings
- core/: Core system components (pool management)
- loaders/: CSV data loading with normalization
- matchers/: Matching rule implementations
- models/: Pydantic data models for trades and results
- normalizers/: Data normalization and standardization
- utils/: Helper functions and utilities
- cli/: Rich terminal interface and display
"""

__version__ = "0.1.0"
__author__ = "Reconengine Team"

# Module level imports for convenience
from .models.trade import SGXTrade, SGXTradeSource
from .models.match_result import SGXMatchResult, SGXMatchType

__all__ = [
    "SGXTrade",
    "SGXTradeSource", 
    "SGXMatchResult",
    "SGXMatchType",
]
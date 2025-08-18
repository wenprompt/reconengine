"""Match result data model for energy trade matching system."""

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, ConfigDict
from .trade import Trade


class MatchType(str, Enum):
    """Type of matching rule that produced this match."""
    EXACT = "exact"  # Rule 1 - Exact 6-field match
    SPREAD = "spread"  # Rule 2 - Spread matching
    CRACK = "crack"  # Rule 3 - Crack spread matching with unit conversion
    COMPLEX_CRACK = "complex_crack"  # Rule 4 - Complex crack matching (base product + brent swap)
    PRODUCT_SPREAD = "product_spread"  # Rule 5 - Product spread matching (hyphenated products)
    AGGREGATION = "aggregation"  # Rule 6 - Aggregation matching
    AGGREGATED_COMPLEX_CRACK = "aggregated_complex_crack"  # Rule 7 - Aggregated complex crack matching
    AGGREGATED_SPREAD = "aggregated_spread"  # Rule 8 - Aggregated spread matching


class MatchResult(BaseModel):
    """Represents a successful match between two trades.
    
    Contains information about which trades matched, the rule used,
    confidence level, and audit trail information.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable for thread safety
        validate_assignment=True
    )
    
    # Match identification
    match_id: str = Field(..., description="Unique identifier for this match")
    match_type: MatchType = Field(..., description="Type of matching rule used")
    confidence: Decimal = Field(..., ge=0, le=100, description="Match confidence percentage")
    
    # Matched trades
    trader_trade: Trade = Field(..., description="Primary trade from trader source")
    exchange_trade: Trade = Field(..., description="Primary trade from exchange source")
    
    # Additional trades for spread matches (Rule 2)
    additional_trader_trades: List[Trade] = Field(
        default_factory=list, 
        description="Additional trader trades for spread matches"
    )
    additional_exchange_trades: List[Trade] = Field(
        default_factory=list, 
        description="Additional exchange trades for spread matches"
    )
    
    # Match details
    matched_fields: List[str] = Field(..., description="Fields that matched exactly")
    differing_fields: List[str] = Field(default_factory=list, description="Fields that differed")
    tolerances_applied: dict = Field(default_factory=dict, description="Tolerances applied during matching")
    
    # Metadata
    matched_at: datetime = Field(default_factory=datetime.now, description="When match was created")
    rule_order: int = Field(..., ge=1, le=8, description="Order of rule that created this match (1-8)")
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return (f"Match({self.match_id}: {self.trader_trade.trade_id} <-> "
                f"{self.exchange_trade.trade_id} via {self.match_type.value} "
                f"@ {self.confidence}%)")
    
    def __repr__(self) -> str:
        """Developer string representation."""
        return (f"MatchResult(id={self.match_id}, type={self.match_type.value}, "
                f"confidence={self.confidence}, rule={self.rule_order})")
    
    @property
    def match_quality(self) -> str:
        """Get human-readable match quality based on confidence."""
        if self.confidence >= 90:
            return "Excellent"
        elif self.confidence >= 80:
            return "Very Good"
        elif self.confidence >= 70:
            return "Good"
        elif self.confidence >= 60:
            return "Fair"
        else:
            return "Poor"
    
    @property
    def quantity_difference(self) -> Decimal:
        """Get absolute difference in quantities (in MT)."""
        return abs(self.trader_trade.quantity_mt - self.exchange_trade.quantity_mt)
    
    @property
    def price_difference(self) -> Decimal:
        """Get absolute difference in prices."""
        return abs(self.trader_trade.price - self.exchange_trade.price)
    
    @property
    def is_opposite_sides(self) -> bool:
        """Check if trades are on opposite sides (required for valid match)."""
        return self.trader_trade.buy_sell != self.exchange_trade.buy_sell
    
    @property
    def is_spread_match(self) -> bool:
        """Check if this is a spread match with multiple trades."""
        return self.match_type == MatchType.SPREAD and (
            len(self.additional_trader_trades) > 0 or 
            len(self.additional_exchange_trades) > 0
        )

    @property
    def is_multi_leg_match(self) -> bool:
        """Check if this match involves multiple legs (additional trades)."""
        return len(self.additional_trader_trades) > 0 or \
               len(self.additional_exchange_trades) > 0
    
    @property
    def all_trader_trades(self) -> List[Trade]:
        """Get all trader trades (primary + additional)."""
        return [self.trader_trade] + self.additional_trader_trades
    
    @property
    def all_exchange_trades(self) -> List[Trade]:
        """Get all exchange trades (primary + additional)."""
        return [self.exchange_trade] + self.additional_exchange_trades
    
    def get_summary(self) -> dict:
        """Get a summary dictionary of match information.
        
        Returns:
            Dictionary with match summary including trades, differences, and metadata
        """
        return {
            "match_id": self.match_id,
            "match_type": self.match_type.value,
            "confidence": float(self.confidence),
            "quality": self.match_quality,
            "rule_order": self.rule_order,
            "trader_trade": {
                "id": self.trader_trade.trade_id,
                "product": self.trader_trade.product_name,
                "quantity_mt": float(self.trader_trade.quantity_mt),
                "price": float(self.trader_trade.price),
                "side": self.trader_trade.buy_sell,
                "contract": self.trader_trade.contract_month
            },
            "exchange_trade": {
                "id": self.exchange_trade.trade_id,
                "product": self.exchange_trade.product_name,
                "quantity_mt": float(self.exchange_trade.quantity_mt),
                "price": float(self.exchange_trade.price),
                "side": self.exchange_trade.buy_sell,
                "contract": self.exchange_trade.contract_month
            },
            "differences": {
                "quantity_mt": float(self.quantity_difference),
                "price": float(self.price_difference),
                "differing_fields": self.differing_fields
            },
            "tolerances_applied": self.tolerances_applied,
            "matched_fields": self.matched_fields,
            "matched_at": self.matched_at.isoformat()
        }
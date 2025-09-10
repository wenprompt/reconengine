"""Match result data model for EEX trade matching system."""

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, ConfigDict
from ...unified_recon.models.recon_status import ReconStatus
from .trade import EEXTrade


class EEXMatchType(str, Enum):
    """Type of matching rule that produced this EEX match."""

    EXACT = "exact"  # Rule 1 - Exact field matching for EEX trades


class EEXMatchResult(BaseModel):
    """Represents a successful match between EEX trades.

    Contains information about which trades matched, the rule used,
    confidence level, and audit trail information specific to EEX trading.
    """

    model_config = ConfigDict(
        frozen=True,  # Immutable for audit trail
        validate_assignment=True,
    )

    # Match identification
    match_id: str = Field(..., description="Unique identifier for this match")
    match_type: EEXMatchType = Field(..., description="Type of matching rule applied")
    rule_order: int = Field(
        ..., ge=1, description="Order in which this rule was applied"
    )
    confidence: Decimal = Field(
        ..., ge=0, le=100, description="Confidence level (0-100%)"
    )
    status: ReconStatus = Field(
        default=ReconStatus.MATCHED, description="Match status (always matched for EEX)"
    )

    # Matched trades
    trader_trade: EEXTrade = Field(..., description="The trader trade in this match")
    exchange_trade: EEXTrade = Field(
        ..., description="The exchange trade in this match"
    )

    # Additional trades for complex matches (future use)
    additional_trader_trades: List[EEXTrade] = Field(
        default_factory=list,
        description="Additional trader trades for multi-leg matches",
    )
    additional_exchange_trades: List[EEXTrade] = Field(
        default_factory=list,
        description="Additional exchange trades for multi-leg matches",
    )

    # Match metadata
    matched_fields: List[str] = Field(
        default_factory=list, description="List of fields that matched exactly"
    )

    # Timestamps
    match_timestamp: datetime = Field(
        default_factory=datetime.now, description="When this match was created"
    )

    @property
    def total_trades(self) -> int:
        """Total number of trades involved in this match."""
        return (
            1  # trader_trade
            + 1  # exchange_trade
            + len(self.additional_trader_trades)
            + len(self.additional_exchange_trades)
        )

    @property
    def matched_quantity(self) -> Decimal:
        """Get the matched quantity (from trader trade)."""
        return self.trader_trade.quantityunit

    @property
    def matched_product(self) -> str:
        """Get the matched product name."""
        return self.trader_trade.product_name

    @property
    def matched_contract(self) -> str:
        """Get the matched contract month."""
        return self.trader_trade.contract_month

    @property
    def price_difference(self) -> Decimal:
        """Calculate the price difference between trader and exchange."""
        return abs(self.trader_trade.price - self.exchange_trade.price)

    @property
    def quantity_difference(self) -> Decimal:
        """Calculate the quantity difference between trader and exchange."""
        return abs(self.trader_trade.quantityunit - self.exchange_trade.quantityunit)

    @property
    def is_exact_match(self) -> bool:
        """Check if this is an exact match."""
        return self.price_difference == Decimal(
            "0"
        ) and self.quantity_difference == Decimal("0")

    @property
    def summary_line(self) -> str:
        """Get a one-line summary of this match for display."""
        return (
            f"Match #{self.match_id}: {self.trader_trade.display_id} ↔ "
            f"{self.exchange_trade.display_id} | {self.matched_product} "
            f"{self.matched_contract} | Qty: {self.matched_quantity} | "
            f"Price: {self.trader_trade.price} ↔ {self.exchange_trade.price} | "
            f"Rule: {self.rule_order} ({self.match_type.value}) | "
            f"Confidence: {self.confidence}%"
        )

    def get_all_trades(self) -> List[EEXTrade]:
        """Get all trades involved in this match."""
        return [
            self.trader_trade,
            self.exchange_trade,
            *self.additional_trader_trades,
            *self.additional_exchange_trades,
        ]

    def get_trader_trades(self) -> List[EEXTrade]:
        """Get all trader trades in this match."""
        return [self.trader_trade, *self.additional_trader_trades]

    def get_exchange_trades(self) -> List[EEXTrade]:
        """Get all exchange trades in this match."""
        return [self.exchange_trade, *self.additional_exchange_trades]

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"EEXMatchResult({self.match_id}: {self.match_type.value}, {self.total_trades} trades)"

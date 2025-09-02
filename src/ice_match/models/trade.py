"""Trade data model for ice trade matching system."""

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Optional, ClassVar
from pydantic import BaseModel, Field, ConfigDict


class TradeSource(str, Enum):
    """Source of trade data."""
    TRADER = "trader"
    EXCHANGE = "exchange"


class Trade(BaseModel):
    """Represents a single ice trade with normalized fields.
    
    This model handles both trader and exchange data with unified field names
    and normalization for matching purposes.
    """

    _bbl_to_mt_ratio: ClassVar[Decimal] = Decimal("6.35")  # Default value

    model_config = ConfigDict(
        frozen=True,  # Immutable for thread safety
        validate_assignment=True,
        str_strip_whitespace=True
    )

    # Core identification
    trade_id: str = Field(..., description="Unique identifier for this trade")
    source: TradeSource = Field(..., description="Whether from trader or exchange")

    # Trading details
    product_name: str = Field(..., description="Normalized product name")
    quantity: Decimal = Field(..., gt=0, description="Trade quantity in MT")
    unit: str = Field(..., description="Quantity unit (mt or bbl)")
    price: Decimal = Field(..., description="Trade price (can be negative for crack spreads)")
    contract_month: str = Field(..., description="Normalized contract month")
    buy_sell: str = Field(..., pattern=r"^[BS]$", description="Buy (B) or Sell (S)")

    # Additional fields
    broker_group_id: Optional[int] = Field(None, description="Broker group identifier")
    exchange_group_id: Optional[int] = Field(None, description="Exchange group identifier")
    exch_clearing_acct_id: Optional[int] = Field(None, description="Clearing account identifier")

    # Metadata
    trade_date: Optional[datetime] = Field(None, description="Trade date")
    trade_time: Optional[datetime] = Field(None, description="Trade time")

    # Special fields
    special_comms: Optional[str] = Field(None, description="Special comments")
    spread: Optional[str] = Field(None, description="Spread information")

    # Raw data for audit trail
    raw_data: dict = Field(default_factory=dict, description="Original raw data")

    @classmethod
    def set_conversion_ratio(cls, ratio: Decimal):
        """Set the BBL to MT conversion ratio for all Trade instances."""
        cls._bbl_to_mt_ratio = ratio

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (f"Trade({self.trade_id}: {self.product_name} "
                f"{self.quantity}{self.unit} @ {self.price} "
                f"{self.contract_month} {self.buy_sell})")

    def __repr__(self) -> str:
        """Developer string representation."""
        return (f"Trade(id={self.trade_id}, source={self.source.value}, "
                f"product={self.product_name}, qty={self.quantity}, "
                f"price={self.price}, month={self.contract_month}, "
                f"side={self.buy_sell})")

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy trade."""
        return self.buy_sell == "B"

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell trade."""
        return self.buy_sell == "S"

    @property
    def quantity_mt(self) -> Decimal:
        """Get quantity in MT, converting from BBL if necessary."""
        if self.unit.lower() == "bbl":
            return self.quantity / self._bbl_to_mt_ratio  # Use configured ratio
        return self.quantity

    @property
    def quantity_bbl(self) -> Decimal:
        """Get quantity in BBL, converting from MT if necessary."""
        if self.unit.lower() == "mt":
            return self.quantity * self._bbl_to_mt_ratio  # Use configured ratio
        return self.quantity

    @property
    def matching_signature(self) -> tuple[str, Decimal, Decimal, str, str]:
        """Get a signature for exact matching (excluding universal fields).
        
        Returns:
            Tuple containing core matching fields for consistency with SGX/CME
        """
        return (
            self.product_name,
            self.quantity_mt,
            self.price,
            self.contract_month,
            self.buy_sell
        )

    def can_match_opposite_side(self, other: "Trade") -> bool:
        """Check if this trade can potentially match with another on opposite side.
        
        Args:
            other: The other trade to check
            
        Returns:
            True if trades are on opposite sides (one buy, one sell)
        """
        if not isinstance(other, Trade):
            return False
        return self.buy_sell != other.buy_sell

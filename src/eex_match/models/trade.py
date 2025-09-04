"""Trade data model for EEX trade matching system."""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EEXTradeSource(str, Enum):
    """Source of EEX trade data."""
    TRADER = "trader"
    EXCHANGE = "exchange"


class EEXTrade(BaseModel):
    """Represents a single EEX trade with normalized fields.
    
    This model handles both trader and exchange data with unified field names
    and normalization for matching purposes. Focused on EEX products like
    CAPE (Capesize freight) and other derivatives.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable for thread safety
        validate_assignment=True,
        str_strip_whitespace=True
    )
    
    # Core identification
    internal_trade_id: str = Field(..., description="Unique identifier for this trade")
    source: EEXTradeSource = Field(..., description="Whether from trader or exchange")
    
    # Trading details
    product_name: str = Field(..., description="Normalized product name (CAPE, etc.)")
    quantitylot: Optional[Decimal] = Field(
        default=None, ge=0, description="Trade quantity in lots (matches CSV column)"
    )
    quantityunit: Decimal = Field(..., gt=0, description="Trade quantity in units (matches CSV column)")
    unit: Optional[str] = Field(default=None, description="Quantity unit (Day, etc.)")
    price: Decimal = Field(..., description="Trade price")
    contract_month: str = Field(..., description="Contract month (e.g., 25-Oct)")
    buy_sell: str = Field(..., pattern=r"^[BS]$", description="Buy (B) or Sell (S)")
    
    # Universal matching fields - must match across all rules
    broker_group_id: Optional[int] = Field(default=None, description="Broker group identifier")
    exch_clearing_acct_id: Optional[int] = Field(default=None, description="Exchange clearing account ID")
    
    # Additional EEX-specific fields
    exchange_group_id: Optional[int] = Field(default=None, description="Exchange group identifier")
    
    # Options-specific fields
    strike: Optional[Decimal] = Field(default=None, description="Strike price for options")
    put_call: Optional[str] = Field(default=None, description="Put (P) or Call (C) for options")
    
    # Spread trading fields
    spread: Optional[str] = Field(default=None, description="Spread indicator")
    
    # Metadata fields
    trade_date: Optional[str] = Field(default=None, description="Trade date")
    trade_time: Optional[str] = Field(default=None, description="Trade time")
    
    # Trader-specific fields
    trader_id: Optional[str] = Field(default=None, description="Trader identifier")
    product_id: Optional[str] = Field(default=None, description="Product identifier")
    product_group_id: Optional[int] = Field(default=None, description="Product group identifier")
    special_comms: Optional[str] = Field(default=None, description="Special comments")
    
    # Exchange-specific fields
    deal_id: Optional[str] = Field(default=None, description="Deal identifier")
    trade_id: Optional[str] = Field(default=None, description="Trade ID from exchange")
    clearing_status: Optional[str] = Field(default=None, description="Clearing status")
    
    @property
    def is_option(self) -> bool:
        """Check if this trade is an option (has strike price or put/call indicator)."""
        return self.strike is not None or bool(self.put_call)
    
    @property
    def is_spread_trade(self) -> bool:
        """Check if this trade is part of a spread (has spread indicator)."""
        return bool(self.spread)
    
    @property
    def display_id(self) -> str:
        """Get a display-friendly ID for logging and output."""
        return self.internal_trade_id  # Show the unique internal_trade_id
    
    @property
    def product_contract_key(self) -> str:
        """Get a key for product-contract matching."""
        return f"{self.product_name}_{self.contract_month}"
    
    @property
    def matching_signature(self) -> tuple[str, str, Decimal, Decimal, str]:
        """Get a signature for exact matching (excluding universal fields)."""
        return (
            self.product_name,
            self.contract_month,
            self.quantityunit,
            self.price,
            self.buy_sell
        )
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return (
            f"EEXTrade({self.display_id}: {self.product_name} "
            f"{self.contract_month} {self.quantityunit} @ {self.price} {self.buy_sell})"
        )
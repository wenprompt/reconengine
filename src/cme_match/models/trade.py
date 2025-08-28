"""Trade data model for CME trade matching system."""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CMETradeSource(str, Enum):
    """Source of CME trade data."""
    TRADER = "trader"
    EXCHANGE = "exchange"


class CMETrade(BaseModel):
    """Represents a single CME trade with normalized fields.
    
    This model handles both trader and exchange data with unified field names
    and normalization for matching purposes. Focused on CME products like
    commodities futures and derivatives.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable for thread safety
        validate_assignment=True,
        str_strip_whitespace=True
    )
    
    # Core identification
    trade_id: str = Field(..., description="Unique identifier for this trade")
    source: CMETradeSource = Field(..., description="Whether from trader or exchange")
    
    # Trading details
    product_name: str = Field(..., description="Normalized product name")
    quantity_lots: Decimal = Field(..., gt=0, description="Trade quantity in lots")
    unit: Optional[str] = Field(None, description="Quantity unit (MT, Bu, etc.)")
    price: Decimal = Field(..., description="Trade price")
    contract_month: str = Field(..., description="Contract month (e.g., Mar25)")
    buy_sell: str = Field(..., pattern=r"^[BS]$", description="Buy (B) or Sell (S)")
    
    # Universal matching fields - must match across all rules
    broker_group_id: Optional[int] = Field(None, description="Broker group identifier")
    exch_clearing_acct_id: Optional[int] = Field(None, description="Exchange clearing account ID")
    
    # Additional CME-specific fields
    exchange_group_id: Optional[int] = Field(None, description="Exchange group identifier")
    
    # Options-specific fields
    strike: Optional[Decimal] = Field(None, description="Strike price for options")
    put_call: Optional[str] = Field(None, description="Put (P) or Call (C) for options")
    
    # Spread trading fields
    spread: Optional[str] = Field(None, description="Spread indicator")
    
    # Metadata fields
    trade_date: Optional[str] = Field(None, description="Trade date")
    trade_time: Optional[str] = Field(None, description="Trade time")
    trade_datetime: Optional[str] = Field(None, description="Trade date and time combined")
    
    # Trader-specific fields
    trader_id: Optional[str] = Field(None, description="Trader identifier")
    product_id: Optional[str] = Field(None, description="Product identifier")
    product_group_id: Optional[int] = Field(None, description="Product group identifier")
    special_comms: Optional[str] = Field(None, description="Special comments")
    remarks: Optional[str] = Field(None, description="Trading remarks")
    broker: Optional[str] = Field(None, description="Broker name")
    
    # Exchange-specific fields
    deal_id: Optional[int] = Field(None, description="Deal identifier")
    clearing_status: Optional[str] = Field(None, description="Clearing status")
    trader_name: Optional[str] = Field(None, description="Trader name")
    trading_session: Optional[str] = Field(None, description="Trading session")
    cleared_date: Optional[str] = Field(None, description="Cleared date")
    
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
        return self.trade_id
    
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
            self.quantity_lots,
            self.price,
            self.buy_sell
        )
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return (
            f"CMETrade({self.display_id}: {self.product_name} "
            f"{self.contract_month} {self.quantity_lots} @ {self.price} {self.buy_sell})"
        )

"""
Pydantic schemas for input validation with flexible type handling.

These schemas define the expected structure and types for trader and exchange
input data. They use Union types to handle data from different sources:
- CSV files (all strings)
- JSON files (typed data)
- API payloads (typed data)

Type Strategy:
1. ID fields (dealid, tradeid) - Always string to prevent scientific notation
2. Integer fields - Union[str, int] with coercion
3. Decimal fields - Union[str, float, Decimal] with coercion
"""

from decimal import Decimal
from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TraderInputSchema(BaseModel):
    """
    Schema for validating trader input data.
    
    Uses Union types to accept data from various sources (CSV strings, JSON typed).
    Validation and coercion ensure consistent types regardless of input format.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,  # Auto-strip whitespace from strings
        validate_assignment=True,   # Validate on field updates
    )
    
    # ID fields - Accept int or str but convert to string to prevent scientific notation
    dealid: Optional[Union[str, int]] = Field(None, description="Deal ID from source data - accepts int or str, converts to string")
    tradeid: Optional[Union[str, int]] = Field(None, description="Trade ID from source data (exchange) - accepts int or str, converts to string")
    internaltradeid: Union[str, int] = Field(..., description="Internal trade ID for tracking - our row index (required for JSON/API)")
    
    # Core trading fields
    productname: str = Field(..., min_length=1, description="Product name")
    contractmonth: str = Field(..., min_length=1, description="Contract month")
    buysell: str = Field(..., min_length=1, alias="b/s", description="Buy/Sell indicator")
    
    # Quantity fields with flexible types
    quantitylots: Optional[Union[str, float, Decimal]] = Field(
        None,
        description="Quantity in lots"
    )
    quantityunits: Optional[Union[str, float, Decimal]] = Field(
        None, 
        description="Quantity in units (MT, BBL, etc.)"
    )
    
    # Price field with flexible type
    price: Union[str, float, Decimal] = Field(
        ..., 
        description="Trade price"
    )
    
    # Universal fields with flexible types
    brokergroupid: Optional[Union[str, int]] = Field(
        None,
        description="Broker group ID"
    )
    exchclearingacctid: Optional[Union[str, int]] = Field(
        None,
        description="Exchange clearing account ID"
    )
    exchangegroupid: Optional[Union[str, int]] = Field(
        None,
        description="Exchange group ID for routing"
    )
    
    # Date and time fields
    tradedate: Optional[str] = Field(None, description="Trade date")
    tradetime: Optional[str] = Field(None, description="Trade time")
    
    # Additional trader fields
    traderid: Optional[str] = Field(None, description="Trader ID")
    productid: Optional[str] = Field(None, description="Product ID")
    productgroupid: Optional[Union[str, int]] = Field(None, description="Product group ID")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    strike: Optional[Union[str, float, Decimal]] = Field(None, description="Strike price")
    specialcomms: Optional[str] = Field(None, alias="specialComms", description="Special commissions")
    spread: Optional[str] = Field(None, description="Spread indicator")
    putcall: Optional[str] = Field(None, alias="put/call", description="Put/Call indicator")
    
    # Validators for type coercion
    @field_validator("dealid", "tradeid", "internaltradeid")
    @classmethod
    def ensure_id_string(cls, v: Optional[Union[str, int]]) -> Optional[str]:
        """Convert ID fields to strings to prevent scientific notation."""
        if v is not None:
            return str(v)
        return v
    
    @field_validator("brokergroupid", "exchclearingacctid", "exchangegroupid", "productgroupid")
    @classmethod
    def coerce_to_int(cls, v: Optional[Union[str, int]]) -> Optional[int]:
        """Coerce string to int for ID fields, handling None and empty strings."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except (ValueError, TypeError):
                return None
        return v
    
    @field_validator("quantitylots", "quantityunits", "price", "strike")
    @classmethod
    def coerce_to_decimal(cls, v: Optional[Union[str, float, Decimal]]) -> Optional[Decimal]:
        """Coerce string or float to Decimal for numeric fields."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                # Handle commas in numbers
                cleaned = v.replace(',', '')
                return Decimal(cleaned)
            except (ValueError, TypeError):
                return None
        elif isinstance(v, float):
            return Decimal(str(v))  # Convert via string to avoid float precision issues
        return v
    


class ExchangeInputSchema(BaseModel):
    """
    Schema for validating exchange input data.
    
    Similar to TraderInputSchema but may have different required fields
    or additional exchange-specific fields.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    # ID fields - Accept int or str but convert to string to prevent scientific notation
    dealid: Optional[Union[str, int]] = Field(None, description="Deal ID from source data - accepts int or str, converts to string")
    tradeid: Optional[Union[str, int]] = Field(None, description="Trade ID from source data (exchange) - accepts int or str, converts to string")
    internaltradeid: Union[str, int] = Field(..., description="Internal trade ID for tracking - our row index (required for JSON/API)")
    
    # Core trading fields
    productname: str = Field(..., min_length=1, description="Product name")
    contractmonth: str = Field(..., min_length=1, description="Contract month")
    buysell: str = Field(..., min_length=1, alias="b/s", description="Buy/Sell indicator")
    
    # Quantity fields
    quantitylots: Optional[Union[str, float, Decimal]] = Field(
        None,
        description="Quantity in lots"
    )
    quantityunits: Optional[Union[str, float, Decimal]] = Field(
        None,
        description="Quantity in units (MT, BBL, etc.)"
    )
    
    # Price field
    price: Union[str, float, Decimal] = Field(
        ...,
        description="Trade price"
    )
    
    # Universal fields
    brokergroupid: Optional[Union[str, int]] = Field(
        None,
        description="Broker group ID"
    )
    exchclearingacctid: Optional[Union[str, int]] = Field(
        None,
        description="Exchange clearing account ID"
    )
    exchangegroupid: Optional[Union[str, int]] = Field(
        None,
        description="Exchange group ID for routing"
    )
    
    # Date fields
    tradedate: Optional[str] = Field(None, description="Trade date")
    tradedatetime: Optional[str] = Field(None, description="Trade date and time")
    cleareddate: Optional[str] = Field(None, description="Cleared date")
    
    # Additional exchange fields
    traderid: Optional[str] = Field(None, description="Trader ID")
    productid: Optional[str] = Field(None, description="Product ID")
    productgroupid: Optional[Union[str, int]] = Field(None, description="Product group ID")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    strike: Optional[Union[str, float, Decimal]] = Field(None, description="Strike price")
    putcall: Optional[str] = Field(None, alias="put/call", description="Put/Call indicator")
    clearingstatus: Optional[str] = Field(None, description="Clearing status")
    tradingsession: Optional[str] = Field(None, description="Trading session")
    source: Optional[str] = Field(None, description="Source of trade")
    
    # Use same validators as TraderInputSchema
    @field_validator("dealid", "tradeid", "internaltradeid")
    @classmethod
    def ensure_id_string(cls, v: Optional[Union[str, int]]) -> Optional[str]:
        """Convert ID fields to strings to prevent scientific notation."""
        if v is not None:
            return str(v)
        return v
    
    @field_validator("brokergroupid", "exchclearingacctid", "exchangegroupid", "productgroupid")
    @classmethod
    def coerce_to_int(cls, v: Optional[Union[str, int]]) -> Optional[int]:
        """Coerce string to int for ID fields."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except (ValueError, TypeError):
                return None
        return v
    
    @field_validator("quantitylots", "quantityunits", "price", "strike")
    @classmethod
    def coerce_to_decimal(cls, v: Optional[Union[str, float, Decimal]]) -> Optional[Decimal]:
        """Coerce string or float to Decimal for numeric fields."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                # Handle commas in numbers
                cleaned = v.replace(',', '')
                return Decimal(cleaned)
            except (ValueError, TypeError):
                return None
        elif isinstance(v, float):
            return Decimal(str(v))
        return v
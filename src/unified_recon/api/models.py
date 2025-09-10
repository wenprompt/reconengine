"""Pydantic models for API request and response."""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Any, Optional
from decimal import Decimal


class ReconciliationRequest(BaseModel):
    """Request model for trade reconciliation API."""

    traderTrades: list[dict[str, Any]] = Field(
        ..., description="List of trader trade records", min_length=1
    )
    exchangeTrades: list[dict[str, Any]] = Field(
        ..., description="List of exchange trade records", min_length=1
    )

    @field_validator("traderTrades", "exchangeTrades")
    @classmethod
    def validate_trades_not_empty(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure trade arrays are not empty."""
        if not v:
            raise ValueError("Trade arrays cannot be empty")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "traderTrades": [
                        {
                            "internalTradeId": 124,
                            "exchangeGroupId": 4,
                            "productName": "380cst",
                            "quantityLot": 10,
                            "quantityUnit": 1000,
                            "unit": "mt",
                            "price": 178.0,
                            "contractMonth": "Jul25",
                            "b/s": "B",
                            "brokerGroupId": 22,
                            "exchClearingAcctId": 2,
                        }
                    ],
                    "exchangeTrades": [
                        {
                            "internalTradeId": 214,
                            "exchangeGroupId": 4,
                            "productName": "380cst",
                            "quantityLot": 10,
                            "quantityUnit": 1000,
                            "unit": "mt",
                            "price": 178.0,
                            "contractMonth": "Jul25",
                            "b/s": "B",
                            "brokerGroupId": 22,
                            "exchClearingAcctId": 2,
                        }
                    ],
                }
            ]
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


class Rule0Request(BaseModel):
    """Request model for Rule 0 position analysis API."""

    traderTrades: list[dict[str, Any]] = Field(
        ..., description="List of trader trade records"
    )
    exchangeTrades: list[dict[str, Any]] = Field(
        ..., description="List of exchange trade records"
    )
    exchangeGroups: Optional[dict[str, str]] = Field(
        default=None, description="Mapping of exchange group IDs to names"
    )
    brokerGroups: Optional[dict[str, str]] = Field(
        default=None, description="Mapping of broker group IDs to names"
    )

    @field_validator("traderTrades", "exchangeTrades")
    @classmethod
    def validate_trades(cls, v: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        """Ensure trade arrays exist (can be empty for Rule 0)."""
        if v is None:
            return []
        return v


class TradeDetail(BaseModel):
    """Trade detail in Rule 0 response."""

    contractMonth: str
    source: str  # "1" for trader, "2" for exchange
    internalId: str
    quantity: float
    unit: str
    price: float
    brokerGroupId: str
    exchClearingAcctId: str
    tradeType: Optional[str] = ""
    matchId: Optional[str] = None


class PositionSummary(BaseModel):
    """Position summary for a product and contract month."""

    contractMonth: str
    traderQuantity: float
    exchangeQuantity: float
    difference: float
    unit: str
    status: str  # "MATCHED", "MISMATCH", "MISSING_TRADER", "MISSING_EXCHANGE"
    traderTradeCount: int
    exchangeTradeCount: int


class ProductResult(BaseModel):
    """Result for a single product."""

    positionSummary: list[PositionSummary]
    tradeDetails: list[TradeDetail]


class ExchangeResult(BaseModel):
    """Result for a single exchange group."""

    products: dict[str, ProductResult]


class Rule0Response(BaseModel):
    """Response model for Rule 0 position analysis API."""

    # Exchange group ID to results mapping
    # e.g., {"1": {...}, "4": {...}}
    root: dict[str, ExchangeResult] = Field(
        ..., description="Position analysis results by exchange group ID"
    )

    model_config = ConfigDict(
        json_encoders={
            Decimal: lambda v: float(v),
        },
    )

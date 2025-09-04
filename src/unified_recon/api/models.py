"""Pydantic models for API request and response."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Any, Dict


class ReconciliationRequest(BaseModel):
    """Request model for trade reconciliation API."""

    traderTrades: List[Dict[str, Any]] = Field(
        ..., description="List of trader trade records", min_length=1
    )
    exchangeTrades: List[Dict[str, Any]] = Field(
        ..., description="List of exchange trade records", min_length=1
    )

    @field_validator("traderTrades", "exchangeTrades")
    @classmethod
    def validate_trades_not_empty(cls, v):
        """Ensure trade arrays are not empty."""
        if not v:
            raise ValueError("Trade arrays cannot be empty")
        return v

    model_config = {
        "json_schema_extra": {
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
    }


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str

"""TypedDict classes for JSON data structures used in the reconciliation engine."""

from typing import Optional, Any, Union, TypedDict
from typing_extensions import NotRequired


# Base trade data structures
class ExchangeTradeData(TypedDict):
    """Exchange trade data structure from JSON input."""

    internalTradeId: int
    tradeDate: str
    tradeTime: str
    productName: str
    quantityLot: int
    quantityUnit: Union[int, float]
    unit: str
    price: Union[int, float]
    contractMonth: str
    exchangeGroupId: int
    brokerGroupId: int
    exchangeClearingAccountId: int
    # Optional fields
    dealId: NotRequired[str]
    tradeId: NotRequired[str]
    clearedAt: NotRequired[str]
    clearingStatus: NotRequired[str]
    tradingSession: NotRequired[str]
    traderId: NotRequired[int]
    source: NotRequired[str]
    strikePrice: NotRequired[Union[int, float]]
    optionType: NotRequired[str]  # "Put" or "Call"
    b_s: NotRequired[str]  # "B" or "S" - key with slash in JSON


class TraderTradeData(TypedDict):
    """Trader trade data structure from JSON input."""

    internalTradeId: int
    tradeDate: str
    tradeTime: str
    productName: str
    quantityUnit: Union[int, float]
    unit: str
    price: Union[int, float]
    contractMonth: str
    exchangeGroupId: int
    brokerGroupId: int
    exchangeClearingAccountId: int
    # Optional fields
    spread: NotRequired[str]  # "S" for spread indicator
    traderId: NotRequired[int]
    b_s: NotRequired[str]  # "B" or "S" - key with slash in JSON


# JSON payload structure
class ReconciliationPayload(TypedDict):
    """Complete JSON payload structure for reconciliation requests."""

    date: str
    exchangeTrades: list[ExchangeTradeData]
    traderTrades: list[TraderTradeData]
    exchangeGroups: dict[str, str]
    brokerGroups: dict[str, str]
    traders: NotRequired[dict[str, str]]
    exchangeClearingAccounts: NotRequired[dict[str, str]]


# Configuration structures
class UniversalMatchingFields(TypedDict):
    """Universal matching fields configuration."""

    description: str
    required_fields: list[str]
    field_mappings: dict[str, str]


class UniversalTolerances(TypedDict):
    """Universal tolerance configuration for ICE."""

    description: str
    tolerance_mt: Union[int, float]
    tolerance_bbl: Union[int, float]


class BuySellMappings(TypedDict):
    """Buy/sell mappings configuration."""

    description: NotRequired[str]
    mappings: NotRequired[dict[str, str]]  # For ICE nested structure
    # For SGX direct structure, the keys are direct buy/sell mappings


class NormalizerConfig(TypedDict):
    """Trade normalizer configuration structure."""

    product_mappings: dict[str, str]
    month_patterns: dict[str, str]
    buy_sell_mappings: Union[
        dict[str, str], BuySellMappings
    ]  # SGX uses direct dict, ICE uses nested structure
    universal_matching_fields: UniversalMatchingFields
    # Optional fields for ICE
    product_conversion_ratios: NotRequired[dict[str, float]]
    traders_product_unit_defaults: NotRequired[dict[str, str]]
    universal_tolerances: NotRequired[UniversalTolerances]


class RuleConfig(TypedDict):
    """Rule configuration structure."""

    rule_number: int
    confidence: float
    enabled: bool
    description: str
    requirements: list[str]


class ToleranceConfig(TypedDict):
    """Tolerance configuration for quantity matching."""

    quantity_mt: float
    quantity_bbl: float
    price_tolerance: float


class ProductMappingConfig(TypedDict):
    """Product-specific configuration mappings."""

    product_name: str
    conversion_ratio: float
    unit_type: str
    exchange_mapping: Optional[str]


class ConversionConfig(TypedDict):
    """Unit conversion configuration."""

    mt_to_bbl_ratios: dict[str, float]
    default_ratio: float
    supported_units: list[str]


# Aggregated configuration structure
class SystemConfig(TypedDict):
    """Complete system configuration structure."""

    normalizer: NormalizerConfig
    rules: dict[str, RuleConfig]
    tolerances: ToleranceConfig
    product_mappings: dict[str, ProductMappingConfig]
    conversions: ConversionConfig
    universal_fields: list[str]


# API response structures
class MatchSummary(TypedDict):
    """Match summary for API responses."""

    matchId: str
    traderTradeIds: list[int]
    exchangeTradeIds: list[int]
    status: str
    remarks: Optional[str]
    confidence: float


class ReconciliationResponse(TypedDict):
    """API response structure for reconciliation results."""

    success: bool
    total_matches: int
    match_rate: float
    processing_time: float
    matches: list[MatchSummary]
    unmatched_traders: list[int]
    unmatched_exchange: list[int]
    errors: NotRequired[list[str]]


# Configuration file loading types
ConfigDict = dict[str, Any]  # Generic config dictionary
JsonConfig = dict[
    str, Union[str, int, float, bool, list[Any], dict[str, Any]]
]  # JSON config structure

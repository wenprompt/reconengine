"""JSON output formatting for unified Rule 0."""

from typing import Any, Optional
from decimal import Decimal
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from src.unified_recon.rule_0.position_matrix import PositionMatrix
from src.unified_recon.rule_0.matrix_comparator import PositionComparison
from src.unified_recon.utils import rule0_trade_utils as trade_utils
from src.unified_recon.utils import rule0_json_utils as json_utils

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal values."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


@dataclass
class TradeDetailJSON:
    """Trade detail for JSON output."""

    contract_month: str
    source: str  # "trader" or "exchange"
    internal_id: str
    quantity: float
    unit: str
    price: float
    broker_group_id: str
    exch_clearing_acct_id: str
    trade_type: str  # "Crack", "PS", "S", or empty
    match_id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contractMonth": self.contract_month,
            "source": self.source,
            "internalId": self.internal_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "price": self.price,
            "brokerGroupId": self.broker_group_id,
            "exchClearingAcctId": self.exch_clearing_acct_id,
            "tradeType": self.trade_type,
            "matchId": self.match_id,
        }


@dataclass
class PositionSummaryJSON:
    """Position summary for JSON output."""

    contract_month: str
    trader_quantity: float
    exchange_quantity: float
    difference: float
    unit: str
    status: str
    trader_trade_count: int
    exchange_trade_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contractMonth": self.contract_month,
            "traderQuantity": self.trader_quantity,
            "exchangeQuantity": self.exchange_quantity,
            "difference": self.difference,
            "unit": self.unit,
            "status": self.status,
            "traderTradeCount": self.trader_trade_count,
            "exchangeTradeCount": self.exchange_trade_count,
        }


class FieldExtractor:
    """Extract fields from PositionComparison based on exchange configuration."""

    def __init__(self, unified_config: dict[str, Any], exchange_group_id: str):
        """Initialize field extractor with configs.

        Args:
            unified_config: Main unified configuration
            exchange_group_id: Exchange group identifier
        """
        self.unified_config = unified_config
        self.exchange_group_id = exchange_group_id

        # Get the specific exchange for this group
        mappings = unified_config.get("exchange_group_mappings", {})
        self.exchange = mappings.get(exchange_group_id, "")

        # Get exchange-specific rule_0 config
        rule0_configs = unified_config.get("rule_0_config", {})
        self.exchange_config = rule0_configs.get(self.exchange, {})

        # Load normalizer config if available
        self.normalizer_config = self._load_normalizer_config()

    def _load_normalizer_config(self) -> Optional[dict[str, Any]]:
        """Load normalizer config if path is specified."""
        normalizer_path = self.exchange_config.get("normalizer_config")
        if normalizer_path:
            path = Path(normalizer_path)
            if path.exists():
                try:
                    with open(path) as f:
                        data: dict[str, Any] = json.load(f)
                        return data
                except (json.JSONDecodeError, OSError) as e:
                    # Log error but don't raise - config is optional
                    print(f"Warning: Failed to load normalizer config from {path}: {e}")
                    return None
        return None

    def extract_quantities_and_unit(self, comp: Any) -> dict[str, Any]:
        """Extract quantities and unit based on this exchange's configuration.

        Args:
            comp: PositionComparison object (could be ICE or unified type)

        Returns:
            dict with trader_quantity, exchange_quantity, difference, unit
        """
        # Handle based on the specific exchange this group belongs to
        if self.exchange == "ice_match":
            # ICE uses MT/BBL fields
            return self._extract_ice_fields(comp)

        elif self.exchange == "cme_match":
            # CME uses quantitylot with LOTS unit
            return self._extract_cme_fields(comp)

        else:
            # SGX, EEX use standard fields
            return self._extract_standard_fields(comp)

    def _extract_ice_fields(self, comp: Any) -> dict[str, Any]:
        """Extract ICE-specific MT/BBL fields."""
        # Check if this is a unified comparison (has trader_quantity/exchange_quantity)
        # or an ICE-specific comparison (has trader_mt/trader_bbl)

        # First try unified fields (used by unified Rule 0)
        if hasattr(comp, "trader_quantity"):
            return {
                "trader_quantity": float(getattr(comp, "trader_quantity", 0)),
                "exchange_quantity": float(getattr(comp, "exchange_quantity", 0)),
                "difference": float(getattr(comp, "difference", 0)),
                "unit": getattr(comp, "unit", "MT"),
            }

        # Fall back to ICE-specific fields for backward compatibility
        trader_mt = float(getattr(comp, "trader_mt", 0))
        trader_bbl = float(getattr(comp, "trader_bbl", 0))
        exchange_mt = float(getattr(comp, "exchange_mt", 0))
        exchange_bbl = float(getattr(comp, "exchange_bbl", 0))

        # Determine primary unit based on non-zero values
        # Prefer BBL if it has values, otherwise MT
        if trader_bbl != 0 or exchange_bbl != 0:
            return {
                "trader_quantity": trader_bbl,
                "exchange_quantity": exchange_bbl,
                "difference": float(getattr(comp, "difference_bbl", 0)),
                "unit": "BBL",
            }
        else:
            return {
                "trader_quantity": trader_mt,
                "exchange_quantity": exchange_mt,
                "difference": float(getattr(comp, "difference_mt", 0)),
                "unit": "MT",
            }

    def _extract_cme_fields(self, comp: Any) -> dict[str, Any]:
        """Extract CME-specific quantitylot fields."""
        # CME config specifies quantity_field and default_unit
        quantity_field = self.exchange_config.get("quantity_field", "quantity")
        default_unit = self.exchange_config.get("default_unit", "LOTS")

        # Build field names dynamically
        trader_field = f"trader_{quantity_field}"
        exchange_field = f"exchange_{quantity_field}"

        return {
            "trader_quantity": float(getattr(comp, trader_field, 0)),
            "exchange_quantity": float(getattr(comp, exchange_field, 0)),
            "difference": float(getattr(comp, "difference", 0)),
            "unit": default_unit,
        }

    def _extract_standard_fields(self, comp: Any) -> dict[str, Any]:
        """Extract standard quantity/unit fields (SGX, EEX)."""
        return {
            "trader_quantity": float(getattr(comp, "trader_quantity", 0)),
            "exchange_quantity": float(getattr(comp, "exchange_quantity", 0)),
            "difference": float(getattr(comp, "difference", 0)),
            "unit": getattr(comp, "unit", ""),
        }


class Rule0JSONOutput:
    """JSON output formatter for Rule 0 results."""

    def __init__(
        self,
        tolerances: Optional[dict[str, float]] = None,
        unified_config: Optional[dict[str, Any]] = None,
        external_match_ids: Optional[dict[str, str]] = None,
    ):
        """Initialize JSON output formatter.

        Args:
            tolerances: Optional tolerance values for matching
            unified_config: Optional unified configuration for field extraction
            external_match_ids: Optional mapping of trade IDs to external match IDs
        """
        self.tolerances = tolerances or {}
        self.unified_config = unified_config or {}
        self.external_match_ids = external_match_ids or {}
        self.field_extractors: dict[str, FieldExtractor] = {}

    def _determine_trade_type(self, original_product: str, spread_flag: str) -> str:
        """Determine trade type based on product and flags."""
        return trade_utils.determine_trade_type(original_product, spread_flag)

    def _match_trades(
        self, trader_trades: list[dict[str, Any]], exchange_trades: list[dict[str, Any]]
    ) -> None:
        """Match trader and exchange trades with optional external match IDs.

        If external match IDs are provided (from reconciliation engine), use them exclusively.
        Otherwise, use position-based matching for /poscheck endpoint.
        """
        # Reset match status
        trade_utils.reset_match_status(trader_trades + exchange_trades)

        # If we have external match IDs, use them exclusively (no fallback)
        if self.external_match_ids:
            # Apply external match IDs from reconciliation engine
            for t_trade in trader_trades:
                t_id = str(t_trade.get("internal_trade_id", ""))
                external_match_id = self.external_match_ids.get(f"T_{t_id}")
                if external_match_id:
                    t_trade["matched"] = True
                    t_trade["match_id"] = external_match_id
                # If no match from reconciliation engine, trade remains unmatched

            for e_trade in exchange_trades:
                e_id = str(e_trade.get("internal_trade_id", ""))
                external_match_id = self.external_match_ids.get(f"E_{e_id}")
                if external_match_id:
                    e_trade["matched"] = True
                    e_trade["match_id"] = external_match_id
                # If no match from reconciliation engine, trade remains unmatched

            # Validate for orphaned match IDs (only one side has the match)
            trader_match_ids = {
                t["match_id"] for t in trader_trades if t.get("matched")
            }
            exchange_match_ids = {
                e["match_id"] for e in exchange_trades if e.get("matched")
            }

            orphaned_trader_only = trader_match_ids - exchange_match_ids
            orphaned_exchange_only = exchange_match_ids - trader_match_ids

            if orphaned_trader_only:
                logger.debug(
                    "Match IDs found only in trader trades (no exchange counterpart): %s",
                    orphaned_trader_only,
                )
            if orphaned_exchange_only:
                logger.debug(
                    "Match IDs found only in exchange trades (no trader counterpart): %s",
                    orphaned_exchange_only,
                )
        else:
            # Use position-based matching for /poscheck endpoint
            for t_trade in trader_trades:
                t_unit = t_trade.get("unit", "").upper()

                # Determine tolerance
                tolerance = trade_utils.determine_tolerance(t_unit, self.tolerances)

                # Find best matching exchange trade
                best_match = trade_utils.find_best_match(
                    t_trade, exchange_trades, tolerance
                )

                # Apply best match
                if best_match:
                    t_id = t_trade.get("internal_trade_id", "NA")
                    e_id = best_match.get("internal_trade_id", "NA")
                    match_id = trade_utils.generate_match_id(t_id, e_id)
                    trade_utils.apply_match(t_trade, best_match, match_id)

    def _get_field_extractor(self, exchange_group_id: str) -> FieldExtractor:
        """Get or create field extractor for exchange group."""
        if exchange_group_id not in self.field_extractors:
            self.field_extractors[exchange_group_id] = FieldExtractor(
                self.unified_config, exchange_group_id
            )
        return self.field_extractors[exchange_group_id]

    def generate_json_output_for_exchange(
        self,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix,
        comparisons: list[PositionComparison],
        exchange_group_id: str,
    ) -> dict[str, Any]:
        """Generate JSON output for a single exchange group.

        Args:
            trader_matrix: Trader position matrix
            exchange_matrix: Exchange position matrix
            comparisons: List of position comparisons
            exchange_group_id: Exchange group identifier

        Returns:
            Dictionary containing products data for this exchange group
        """
        result: dict[str, Any] = {"products": {}}

        # Group comparisons by product
        by_product = json_utils.group_comparisons_by_product(comparisons)

        # Process each product
        for product, product_comps in sorted(by_product.items()):
            product_data = json_utils.create_product_data_structure()

            # Add position summary for each contract month
            for comp in sorted(product_comps, key=lambda x: x.contract_month):
                # Skip zero positions unless they have trades
                if json_utils.should_skip_position(comp):
                    continue

                # Determine status string
                status_str = json_utils.get_status_string(comp.status)

                # Use field extractor to handle different exchange formats
                extractor = self._get_field_extractor(exchange_group_id)
                quantities = extractor.extract_quantities_and_unit(comp)

                summary = PositionSummaryJSON(
                    contract_month=comp.contract_month,
                    trader_quantity=quantities["trader_quantity"],
                    exchange_quantity=quantities["exchange_quantity"],
                    difference=quantities["difference"],
                    unit=quantities["unit"],
                    status=status_str,
                    trader_trade_count=comp.trader_trades,
                    exchange_trade_count=comp.exchange_trades,
                )
                product_data["positionSummary"].append(summary.to_dict())

            # Collect all contract months for this product
            all_months = json_utils.collect_contract_months(
                trader_matrix, exchange_matrix, product
            )

            # Process trade details for each month
            for month in sorted(all_months):
                trader_trades = []
                exchange_trades = []

                # Get trader trades
                trader_trades = json_utils.get_trades_for_position(
                    trader_matrix, month, product
                )

                # Get exchange trades
                exchange_trades = json_utils.get_trades_for_position(
                    exchange_matrix, month, product
                )

                # Perform matching
                if trader_trades and exchange_trades:
                    self._match_trades(trader_trades, exchange_trades)

                # Add trader trades to output
                for detail in trader_trades:
                    trade_type = self._determine_trade_type(
                        detail.get("original_product", ""),
                        detail.get("spread_flag", ""),
                    )

                    trade_json = TradeDetailJSON(
                        contract_month=month,
                        source="1",  # Trader source
                        internal_id=str(detail.get("internal_trade_id", "N/A")),
                        quantity=float(detail.get("quantity", 0)),
                        unit=detail.get("unit", ""),
                        price=float(detail.get("price", 0)),
                        broker_group_id=str(detail.get("broker_group_id", "")),
                        exch_clearing_acct_id=str(
                            detail.get("exch_clearing_acct_id", "")
                        ),
                        trade_type=trade_type,
                        match_id=detail.get("match_id", ""),
                    )
                    product_data["tradeDetails"].append(trade_json.to_dict())

                # Add exchange trades to output
                for detail in exchange_trades:
                    trade_type = self._determine_trade_type(
                        detail.get("original_product", ""),
                        detail.get("spread_flag", ""),
                    )

                    trade_json = TradeDetailJSON(
                        contract_month=month,
                        source="2",  # Exchange source
                        internal_id=str(detail.get("internal_trade_id", "N/A")),
                        quantity=float(detail.get("quantity", 0)),
                        unit=detail.get("unit", ""),
                        price=float(detail.get("price", 0)),
                        broker_group_id=str(detail.get("broker_group_id", "")),
                        exch_clearing_acct_id=str(
                            detail.get("exch_clearing_acct_id", "")
                        ),
                        trade_type=trade_type,
                        match_id=detail.get("match_id", ""),
                    )
                    product_data["tradeDetails"].append(trade_json.to_dict())

            # Only add product if it has data
            if json_utils.has_product_data(product_data):
                result["products"][product] = product_data

        return result

    def generate_multi_exchange_json(
        self, exchange_results: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate JSON output for multiple exchange groups.

        Args:
            exchange_results: Dictionary mapping exchange_group_id to results
                Each result contains: trader_matrix, exchange_matrix, comparisons

        Returns:
            Dictionary grouped by exchange_group_id
        """
        output = {}

        for exchange_group_id, data in exchange_results.items():
            trader_matrix = data["trader_matrix"]
            exchange_matrix = data["exchange_matrix"]
            comparisons = data["comparisons"]

            # Generate output for this exchange group
            exchange_output = self.generate_json_output_for_exchange(
                trader_matrix, exchange_matrix, comparisons, exchange_group_id
            )

            # Only add if there's data
            if exchange_output["products"]:
                output[exchange_group_id] = exchange_output

        return output

    def to_json_string(
        self, exchange_results: dict[str, dict[str, Any]], indent: int = 2
    ) -> str:
        """Generate JSON string output for multiple exchanges.

        Args:
            exchange_results: Dictionary mapping exchange_group_id to results
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        data = self.generate_multi_exchange_json(exchange_results)
        return json.dumps(data, cls=DecimalEncoder, indent=indent)

"""Exchange-aware position matrix builder for unified Rule 0."""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Optional, Any, Set

import pandas as pd

from src.unified_recon.rule_0.decomposer import UnifiedDecomposer, DecomposedProduct

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a position for a specific product and contract month."""

    product: str
    contract_month: str
    quantity: Decimal
    unit: Optional[str] = None  # MT, BBL, LOTS, DAYS, MW, etc.
    trade_count: int = 0
    is_synthetic: bool = False
    trade_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def display_quantity(self) -> str:
        """Get quantity with unit for display."""
        if self.unit:
            return f"{self.quantity} {self.unit}"
        return str(self.quantity)


@dataclass
class PositionMatrix:
    """Matrix of positions organized by contract month and product."""

    positions: dict[tuple[str, str], Position] = field(default_factory=dict)
    contract_months: Set[str] = field(default_factory=set)
    products: Set[str] = field(default_factory=set)
    exchange: str = ""
    source: str = "trader"  # "trader" or "exchange"

    def add_position(
        self,
        product: str,
        contract_month: str,
        quantity: Decimal,
        unit: Optional[str] = None,
        is_synthetic: bool = False,
        trade_detail: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add or update a position in the matrix."""
        key = (contract_month, product)

        if key not in self.positions:
            self.positions[key] = Position(
                product=product,
                contract_month=contract_month,
                quantity=Decimal("0"),
                unit=unit,
                is_synthetic=is_synthetic,
            )
            self.contract_months.add(contract_month)
            self.products.add(product)

        position = self.positions[key]
        position.quantity += quantity
        position.trade_count += 1

        if trade_detail is not None:
            position.trade_details.append(trade_detail)

    def get_position(self, contract_month: str, product: str) -> Optional[Position]:
        """Get a position for a specific contract month and product."""
        return self.positions.get((contract_month, product))

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the matrix to a pandas DataFrame for display."""
        data = []
        for (month, product), position in self.positions.items():
            data.append(
                {
                    "Contract Month": month,
                    "Product": product,
                    "Quantity": float(position.quantity),
                    "Unit": position.unit or "",
                    "Trade Count": position.trade_count,
                    "Synthetic": position.is_synthetic,
                }
            )

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.sort_values(["Contract Month", "Product"])
        return df


class UnifiedPositionMatrixBuilder:
    """Builds position matrices for any exchange using config-driven logic."""

    def __init__(
        self,
        exchange: str,
        config: dict[str, Any],
        field_mappings: Optional[dict[str, list[str]]] = None,
    ):
        """Initialize the matrix builder for a specific exchange.

        Args:
            exchange: Exchange name (ice_match, sgx_match, etc.)
            config: Exchange-specific config from rule_0_config
            field_mappings: Optional field mappings for handling naming differences
        """
        self.exchange = exchange
        self.config = config
        self.field_mappings = field_mappings or {}

        # Get exchange-specific settings
        self.quantity_field = config.get("quantity_field", "quantityunit")
        self.default_unit = config.get("default_unit", "")

        # Load decomposer with patterns if available
        decomposition_patterns = config.get("decomposition_patterns")
        self.decomposer = UnifiedDecomposer(decomposition_patterns)

        # Load normalizer config if specified
        self.normalizer_config = {}
        if "normalizer_config" in config:
            config_path = Path(config["normalizer_config"])
            if config_path.exists():
                with open(config_path, "r") as f:
                    self.normalizer_config = json.load(f)

        # Get conversion ratios for ICE
        self.conversion_ratios = {}
        if exchange == "ice_match":
            self.conversion_ratios = self.normalizer_config.get(
                "product_conversion_ratios", {}
            )

        # Get unit defaults
        self.unit_defaults = self.normalizer_config.get(
            "traders_product_unit_defaults", {}
        )

    def _get_conversion_ratio(self, product_name: str) -> Decimal:
        """Get the conversion ratio for a specific product (ICE only)."""
        if not self.conversion_ratios:
            return Decimal("1")  # No conversion for non-ICE

        product_lower = product_name.lower()
        if product_lower in self.conversion_ratios:
            return Decimal(str(self.conversion_ratios[product_lower]))

        # Default ratio
        return Decimal(str(self.conversion_ratios.get("default", 7.0)))

    def _determine_unit(self, product: str, original_unit: str, source: str) -> str:
        """Determine the unit for a product based on exchange rules.

        Args:
            product: Product name
            original_unit: Unit from the data
            source: 'trader' or 'exchange' to identify data source
        """
        # First check if we have a unit from the data
        if original_unit:
            unit = str(original_unit).upper()
            # If unit is empty string or pandas NaN, leave it empty
            if unit in ["", "NAN"]:
                return ""
            else:
                return unit

        # If no valid unit from data, check config ONLY for ICE trader files
        if source == "trader" and self.exchange == "ice_match" and self.unit_defaults:
            # ICE has explicit unit defaults in config for traders
            # Check if product has specific unit default
            product_lower = product.lower()
            if product_lower in self.unit_defaults:
                unit_value: str = str(self.unit_defaults[product_lower]).upper()
                return unit_value
            # Use default unit if specified
            elif "default" in self.unit_defaults:
                default_unit: str = str(self.unit_defaults["default"]).upper()
                return default_unit

        # No unit from data or config - return empty
        return ""

    def build_matrix(
        self, trades: list[dict[str, Any]], source: str = "trader"
    ) -> PositionMatrix:
        """Build a position matrix from a list of trades.

        Args:
            trades: List of trade dictionaries
            source: 'trader' or 'exchange' to identify data source

        Returns:
            PositionMatrix with aggregated positions
        """
        if not trades:
            return PositionMatrix(exchange=self.exchange)

        matrix = PositionMatrix(exchange=self.exchange, source=source)

        # Process trades with index assignment for CSV files
        for index, trade in enumerate(trades, start=1):
            # Check for internal trade ID in a case-insensitive manner
            # DataFrames convert field names to lowercase
            has_internal_id = False
            internal_id_value = None

            # Check both camelCase and lowercase versions
            if "internalTradeId" in trade:
                has_internal_id = True
                internal_id_value = trade["internalTradeId"]
            elif "internaltradeid" in trade:
                has_internal_id = True
                internal_id_value = trade["internaltradeid"]
                # Normalize to camelCase for consistency
                trade["internalTradeId"] = internal_id_value

            # Debug logging for first few trades
            if index <= 3:
                logger.debug(
                    f"Trade {index}: has internal ID? {has_internal_id}, value: {internal_id_value}"
                )

            # If no internal trade ID (CSV file), assign the index
            if not has_internal_id:
                trade["internalTradeId"] = index
            self._process_trade(trade, matrix, source)
            # Clear cached key-map for this trade to prevent unbounded memory growth
            if hasattr(self, "_trade_keys_cache"):
                self._trade_keys_cache.pop(id(trade), None)

        logger.info(
            f"Built {self.exchange} matrix with {len(matrix.positions)} positions across "
            f"{len(matrix.contract_months)} months and {len(matrix.products)} products"
        )

        return matrix

    def _get_trade_field(
        self, trade: dict[str, Any], field_key: str, default: Any = ""
    ) -> Any:
        """Get a field value from trade data, handling case variations.

        Args:
            trade: Trade dictionary
            field_key: Base field name (e.g., 'productname', 'contractmonth')
            default: Default value if field not found

        Returns:
            Field value or default
        """
        # Create a lowercase mapping of all keys for case-insensitive lookup
        # Cache this if not already done
        if not hasattr(self, "_trade_keys_cache"):
            self._trade_keys_cache: dict[int, dict[str, str]] = {}

        trade_id = id(trade)
        if trade_id not in self._trade_keys_cache:
            self._trade_keys_cache[trade_id] = {k.lower(): k for k in trade.keys()}

        lowercase_map = self._trade_keys_cache[trade_id]

        # Check if this field has special mappings defined in config
        if field_key in self.field_mappings:
            # Try each variant in the configured list
            for variant in self.field_mappings[field_key]:
                variant_lower = variant.lower()
                if variant_lower in lowercase_map:
                    return trade[lowercase_map[variant_lower]]

        # For all other fields, just use lowercase lookup
        field_lower = field_key.lower()
        if field_lower in lowercase_map:
            return trade[lowercase_map[field_lower]]

        return default

    def _extract_trade_fields(self, trade: dict[str, Any]) -> tuple[str, str, str]:
        """Extract and normalize basic trade fields.

        Args:
            trade: Trade dictionary

        Returns:
            Tuple of (product_name, contract_month, buy_sell)
        """
        # Get trade fields using field mapping helper
        product_name = self._get_trade_field(trade, "productname", "")
        contract_month = self._get_trade_field(trade, "contractmonth", "")
        # Normalize contract month format (remove spaces)
        contract_month = contract_month.replace(" ", "")
        buy_sell = self._get_trade_field(trade, "b/s", "B")

        # Normalize buy/sell values
        if buy_sell and buy_sell.upper() in ["BOUGHT", "BUY"]:
            buy_sell = "B"
        elif buy_sell and buy_sell.upper() in ["SOLD", "SELL"]:
            buy_sell = "S"

        return product_name, contract_month, buy_sell

    def _extract_quantity_and_unit(self, trade: dict[str, Any]) -> tuple[Decimal, str]:
        """Extract quantity and unit based on exchange configuration.

        Args:
            trade: Trade dictionary

        Returns:
            Tuple of (quantity, original_unit)
        """
        # Get quantity using configured field name
        qty_value = self._get_trade_field(trade, self.quantity_field, 0)

        # Handle empty or invalid values, and remove commas
        try:
            qty_str = str(qty_value).replace(",", "") if qty_value else "0"
            quantity = Decimal(qty_str) if qty_str.strip() else Decimal("0")
        except (ValueError, TypeError, DecimalException):
            quantity = Decimal("0")

        # Get unit - use default from config if specified, otherwise from trade
        if self.default_unit:
            original_unit = self.default_unit
        else:
            # Get unit from trade using field mappings
            original_unit = str(self._get_trade_field(trade, "unit", ""))
            # Only handle pandas NaN, leave everything else as-is
            if original_unit.upper() == "NAN":
                original_unit = ""

        return quantity, original_unit

    def _create_trade_detail(
        self,
        trade: dict[str, Any],
        component: Any,
        final_quantity: Decimal,
        unit: str,
        product_name: str,
    ) -> dict[str, Any]:
        """Create trade detail dictionary for tracking.

        Args:
            trade: Original trade dictionary
            component: Decomposed product component
            final_quantity: Final calculated quantity
            unit: Unit string
            product_name: Original product name

        Returns:
            Trade detail dictionary
        """
        # Get internal trade ID - check both camelCase and lowercase versions
        # DataFrames convert field names to lowercase
        internal_id = trade.get("internalTradeId", trade.get("internaltradeid", ""))

        # Debug log for first few trades
        if not hasattr(self, "_logged_trade_ids"):
            self._logged_trade_ids = 0
        if self._logged_trade_ids < 3:
            logger.debug(
                f"Creating trade detail: internal_id={internal_id}, product={product_name}"
            )
            self._logged_trade_ids += 1

        # Get additional fields using field mapping helper
        price = self._get_trade_field(trade, "price", "")
        broker_group = self._get_trade_field(trade, "brokergroupid", "")
        clearing_acct = self._get_trade_field(trade, "exchclearingacctid", "")
        spread_flag = self._get_trade_field(
            trade, "spread", ""
        )  # Get spread flag if present

        # Check if this is from a decomposed product (crack or spread)
        is_decomposed = "crack" in product_name.lower() or "-" in product_name

        # Convert price to float, handle empty/invalid values
        try:
            price_value = float(price) if price not in [None, "", "nan", "NaN"] else 0.0
        except (ValueError, TypeError):
            price_value = 0.0

        return {
            "internal_trade_id": str(internal_id) if internal_id else "",
            "quantity": float(final_quantity),
            "unit": unit,
            "price": price_value,
            "broker_group_id": str(broker_group) if broker_group else "",
            "exch_clearing_acct_id": str(clearing_acct) if clearing_acct else "",
            "is_synthetic": component.is_synthetic,
            "original_product": product_name
            if (component.is_synthetic or is_decomposed)
            else None,
            "spread_flag": spread_flag,  # Store spread flag for display
        }

    def _process_trade(
        self, trade: dict[str, Any], matrix: PositionMatrix, source: str
    ) -> None:
        """Process a single trade and add to the matrix."""
        # Extract basic trade fields
        product_name, contract_month, buy_sell = self._extract_trade_fields(trade)

        # Debug logging for first trade
        if not hasattr(self, "_logged_first"):
            logger.debug(f"First trade keys: {list(trade.keys())[:10]}")
            logger.debug(
                f"Product: {product_name}, Month: {contract_month}, B/S: {buy_sell}"
            )
            self._logged_first = True

        # Extract quantity and unit
        quantity, original_unit = self._extract_quantity_and_unit(trade)

        # Decompose the product
        decomposed = self.decomposer.decompose(product_name, quantity, buy_sell)

        for component in decomposed:
            # Determine quantity and unit based on exchange
            final_quantity = component.quantity

            # For decomposed components (cracks/spreads), inherit the unit from the original trade
            # Don't use product-specific defaults for synthetic components
            if component.is_synthetic or (
                "crack" in product_name.lower() or "-" in product_name
            ):
                # Inherit unit from original trade for all decomposed components
                unit = self._determine_unit(product_name, original_unit, source)
            else:
                # For non-decomposed trades, use normal unit determination
                unit = self._determine_unit(
                    component.base_product, original_unit, source
                )

            # For ICE: Apply conversion if needed
            if (
                self.exchange == "ice_match" and unit
            ):  # Only apply conversion if we have a unit
                # Check if this product should be displayed in BBL based on config
                product_lower = component.base_product.lower()
                target_unit_from_config = self.unit_defaults.get(
                    product_lower, self.unit_defaults.get("default", "mt")
                ).upper()

                if target_unit_from_config == "BBL":
                    # Product should be displayed in BBL (based on config)
                    if unit == "MT":
                        # The decomposed component is in MT (from a crack that was in MT)
                        # Convert MT to BBL using product-specific ratio
                        # For cracks, use the base product name (without "crack") to get the ratio
                        ratio_product = (
                            product_name.replace(" crack", "").replace(" Crack", "")
                            if "crack" in product_name.lower()
                            else product_name
                        )
                        ratio = self._get_conversion_ratio(ratio_product)
                        final_quantity = component.quantity * ratio
                        unit = "BBL"  # Override unit for display
                    elif unit == "BBL":
                        # Already in BBL (from a crack that was in BBL), keep as is
                        unit = "BBL"
                    else:
                        # No unit specified, use target unit from config
                        unit = target_unit_from_config
                else:
                    # Product should be displayed in MT (based on config)
                    if unit == "BBL":
                        # The decomposed component is in BBL (from a crack that was in BBL)
                        # Convert BBL to MT using product-specific ratio
                        # For cracks, use the base product name (without "crack") to get the ratio
                        ratio_product = (
                            product_name.replace(" crack", "").replace(" Crack", "")
                            if "crack" in product_name.lower()
                            else product_name
                        )
                        ratio = self._get_conversion_ratio(ratio_product)
                        final_quantity = component.quantity / ratio
                        unit = "MT"  # Override unit for display
                    elif unit == "MT":
                        # Already in MT, keep as is
                        unit = "MT"
                    else:
                        # No unit specified, use target unit from config
                        unit = target_unit_from_config

            # Apply buy/sell direction
            final_quantity = self._apply_direction(
                buy_sell, component, final_quantity, product_name
            )

            # Create trade detail for tracking
            trade_detail = self._create_trade_detail(
                trade, component, final_quantity, unit, product_name
            )

            # Add to matrix
            matrix.add_position(
                product=component.base_product,
                contract_month=contract_month,
                quantity=final_quantity,
                unit=unit,
                is_synthetic=component.is_synthetic,
                trade_detail=trade_detail,
            )

    def _apply_direction(
        self,
        buy_sell: str,
        component: DecomposedProduct,
        quantity: Decimal,
        original_product: str,
    ) -> Decimal:
        """Apply direction logic for trades and synthetic components."""
        product_lower = original_product.lower()

        if component.is_synthetic:
            # Synthetic component from decomposition
            if "crack" in product_lower:
                # For cracks: synthetic component (e.g., brent swap) has opposite direction
                if (
                    self.decomposer.crack_pattern
                    and component.base_product.lower()
                    == self.decomposer.crack_pattern.lower()
                ):
                    if buy_sell == "B":
                        quantity = (
                            -quantity
                        )  # Buying crack = selling synthetic component
                else:
                    # Base product follows crack direction
                    if buy_sell == "S":
                        quantity = -quantity
            elif "-" in product_lower:
                # For spreads: second product has opposite direction
                if buy_sell == "B":
                    quantity = -quantity  # Buying spread = selling second product
            else:
                # Default: follow trade direction
                if buy_sell == "S":
                    quantity = -quantity
        else:
            # Regular trade or first component of spread
            if "-" in product_lower and component.base_product != original_product:
                # First component of spread follows spread direction
                if buy_sell == "S":
                    quantity = -quantity
            elif "crack" not in product_lower:
                # Regular trade (not part of crack)
                if buy_sell == "S":
                    quantity = -quantity
            else:
                # Base product of crack follows crack direction
                if buy_sell == "S":
                    quantity = -quantity

        return quantity

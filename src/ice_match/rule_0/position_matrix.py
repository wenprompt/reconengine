"""Position matrix builder for aggregating trade positions by product and contract month."""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from src.ice_match.models.trade import Trade, TradeSource
from src.ice_match.rule_0.product_decomposer import ProductDecomposer, DecomposedProduct

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a position for a specific product and contract month."""
    
    product: str
    contract_month: str
    quantity_mt: Optional[Decimal] = None  # None for brent swap
    quantity_bbl: Optional[Decimal] = None  # None for non-brent products
    trade_count: int = 0
    is_synthetic: bool = False  # True if derived from decomposition
    
    @property
    def is_brent_swap(self) -> bool:
        """Check if this is a brent swap position."""
        return self.product.lower() == "brent swap"


@dataclass 
class PositionMatrix:
    """Matrix of positions organized by contract month and product."""
    
    # Key: (contract_month, product) -> Position
    positions: Dict[Tuple[str, str], Position] = field(default_factory=dict)
    contract_months: Set[str] = field(default_factory=set)
    products: Set[str] = field(default_factory=set)
    source: TradeSource = TradeSource.TRADER
    
    def add_position(
        self, 
        product: str, 
        contract_month: str, 
        quantity_mt: Optional[Decimal],
        quantity_bbl: Optional[Decimal],
        is_synthetic: bool = False
    ) -> None:
        """Add or update a position in the matrix."""
        key = (contract_month, product)
        
        if key not in self.positions:
            self.positions[key] = Position(
                product=product,
                contract_month=contract_month,
                is_synthetic=is_synthetic
            )
            self.contract_months.add(contract_month)
            self.products.add(product)
        
        position = self.positions[key]
        
        # Add quantities based on product type
        if product.lower() == "brent swap":
            # Brent swap only tracks BBL
            if position.quantity_bbl is None:
                position.quantity_bbl = Decimal("0")
            if quantity_bbl is not None:
                position.quantity_bbl += quantity_bbl
        else:
            # All other products only track MT
            if position.quantity_mt is None:
                position.quantity_mt = Decimal("0")
            if quantity_mt is not None:
                position.quantity_mt += quantity_mt
        
        position.trade_count += 1
        
    def get_position(self, contract_month: str, product: str) -> Optional[Position]:
        """Get a position for a specific contract month and product."""
        return self.positions.get((contract_month, product))
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert the matrix to a pandas DataFrame for display."""
        data = []
        for (month, product), position in self.positions.items():
            data.append({
                "Contract Month": month,
                "Product": product,
                "Quantity MT": float(position.quantity_mt or 0),
                "Quantity BBL": float(position.quantity_bbl or 0),
                "Trade Count": position.trade_count,
                "Synthetic": position.is_synthetic
            })
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df = df.sort_values(["Contract Month", "Product"])
        return df


class PositionMatrixBuilder:
    """Builds position matrices from trade data with product decomposition."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the matrix builder.
        
        Args:
            config_path: Path to normalizer_config.json
        """
        self.decomposer = ProductDecomposer()
        self.conversion_ratios = self._load_conversion_ratios(config_path)
        
    def _load_conversion_ratios(self, config_path: Optional[Path] = None) -> Dict[str, Decimal]:
        """Load product-specific conversion ratios from config.
        
        Args:
            config_path: Path to config file
            
        Returns:
            Dictionary of product to conversion ratio (keys are lowercased)
        """
        if config_path is None:
            # Robust path: src/ice_match/rule_0/position_matrix.py -> up to src/ice_match
            config_path = Path(__file__).resolve().parents[1] / "config" / "normalizer_config.json"
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                ratios = config.get("product_conversion_ratios", {})
                # Convert to Decimal with lowercased keys for case-insensitive lookup
                return {
                    product.lower(): Decimal(str(ratio))
                    for product, ratio in ratios.items()
                }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config from {config_path}: {e}. Using fallback default 7.0")
            return {"default": Decimal("7.0")}
    
    def _get_conversion_ratio(self, product_name: str) -> Decimal:
        """Get the conversion ratio for a specific product.
        
        Args:
            product_name: Product name
            
        Returns:
            Conversion ratio (MT to BBL)
        """
        product_lower = product_name.lower()
        
        # Check for exact match
        if product_lower in self.conversion_ratios:
            return self.conversion_ratios[product_lower]
        
        # Default ratio
        return self.conversion_ratios.get("default", Decimal("7.0"))
    
    def build_matrix(self, trades: List[Trade]) -> PositionMatrix:
        """Build a position matrix from a list of trades.
        
        Args:
            trades: List of trades to process
            
        Returns:
            PositionMatrix with aggregated positions
        """
        if not trades:
            return PositionMatrix()
        
        # Determine source from first trade
        source = trades[0].source if trades else TradeSource.TRADER
        matrix = PositionMatrix(source=source)
        
        for trade in trades:
            self._process_trade(trade, matrix)
        
        logger.info(
            f"Built matrix with {len(matrix.positions)} positions across "
            f"{len(matrix.contract_months)} months and {len(matrix.products)} products"
        )
        
        return matrix
    
    def _process_trade(self, trade: Trade, matrix: PositionMatrix) -> None:
        """Process a single trade and add to the matrix.
        
        Args:
            trade: Trade to process
            matrix: Matrix to update
        """
        # Decompose the product
        decomposed = self.decomposer.decompose(
            trade.product_name,
            trade.quantityunit,
            trade.unit,
            trade.buy_sell
        )
        
        # Store original product name for ratio lookup
        original_product = trade.product_name
        
        for component in decomposed:
            # Determine quantities based on product type
            quantity_mt = None
            quantity_bbl = None
            
            if component.base_product.lower() == "brent swap":
                # Brent swap is always in BBL
                if trade.unit.lower() == "mt":
                    # If crack was in MT, convert to BBL using crack's ratio
                    ratio = self._get_conversion_ratio(original_product)
                    quantity_bbl = component.quantity * ratio
                else:
                    # Already in BBL
                    quantity_bbl = component.quantity
            else:
                # All other products are in MT
                if trade.unit.lower() == "mt":
                    quantity_mt = component.quantity
                else:  # bbl
                    # Convert BBL to MT using original product's ratio (for cracks/spreads)
                    # or base product ratio (for regular products)
                    if component.is_synthetic:
                        # For decomposed products, use the original product's ratio
                        ratio = self._get_conversion_ratio(original_product)
                    else:
                        # For regular products, use the product's own ratio
                        ratio = self._get_conversion_ratio(component.base_product)
                    quantity_mt = component.quantity / ratio
            
            # Apply buy/sell direction
            if component.is_synthetic:
                quantity_mt, quantity_bbl = self._apply_synthetic_direction(
                    trade, component, quantity_mt, quantity_bbl
                )
            else:
                # Regular trades: Buy is positive, Sell is negative
                if trade.buy_sell == "S":
                    if quantity_mt is not None:
                        quantity_mt = -quantity_mt
                    if quantity_bbl is not None:
                        quantity_bbl = -quantity_bbl
            
            # Add to matrix
            matrix.add_position(
                product=component.base_product,
                contract_month=trade.contract_month,
                quantity_mt=quantity_mt,
                quantity_bbl=quantity_bbl,
                is_synthetic=component.is_synthetic
            )
    
    def _apply_synthetic_direction(
        self,
        trade: Trade,
        component: DecomposedProduct,
        quantity_mt: Optional[Decimal],
        quantity_bbl: Optional[Decimal]
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Apply direction logic for synthetic components from cracks/spreads.
        
        Args:
            trade: Original trade
            component: Decomposed component
            quantity_mt: Quantity in MT (may be None)
            quantity_bbl: Quantity in BBL (may be None)
            
        Returns:
            Tuple of (adjusted_mt, adjusted_bbl)
        """
        product_lower = trade.product_name.lower()
        
        if "crack" in product_lower:
            # For crack trades:
            # Base product follows crack direction
            # Brent swap has opposite direction
            if component.base_product.lower() == "brent swap":
                # Brent swap: opposite of crack direction
                if trade.buy_sell == "B":
                    # Buying crack = selling brent
                    if quantity_bbl is not None:
                        quantity_bbl = -quantity_bbl
                # else: Selling crack = buying brent (positive)
            else:
                # Base product: same as crack direction
                if trade.buy_sell == "S":
                    if quantity_mt is not None:
                        quantity_mt = -quantity_mt
                    
        elif "-" in product_lower:
            # For spread trades (e.g., 0.5% marine-380cst):
            # First product follows spread direction
            # Second product has opposite direction
            parts = product_lower.split("-", 1)
            if len(parts) == 2:
                # Determine if this is the first or second product
                is_second_product = (
                    component.base_product.lower() == parts[1].strip().lower()
                )
                
                if is_second_product:
                    # Second product: opposite of spread direction
                    if trade.buy_sell == "B":
                        # Buying spread = selling second product
                        if quantity_mt is not None:
                            quantity_mt = -quantity_mt
                        if quantity_bbl is not None:
                            quantity_bbl = -quantity_bbl
                    # else: Selling spread = buying second product (positive)
                else:
                    # First product: same as spread direction
                    if trade.buy_sell == "S":
                        if quantity_mt is not None:
                            quantity_mt = -quantity_mt
                        if quantity_bbl is not None:
                            quantity_bbl = -quantity_bbl
        else:
            # Default: follow trade direction
            if trade.buy_sell == "S":
                if quantity_mt is not None:
                    quantity_mt = -quantity_mt
                if quantity_bbl is not None:
                    quantity_bbl = -quantity_bbl
        
        return quantity_mt, quantity_bbl
    
    def merge_matrices(self, matrices: List[PositionMatrix]) -> PositionMatrix:
        """Merge multiple position matrices into one.
        
        Args:
            matrices: List of matrices to merge
            
        Returns:
            Merged position matrix
        """
        if not matrices:
            return PositionMatrix()
        
        merged = PositionMatrix(source=matrices[0].source)
        
        for matrix in matrices:
            for (month, product), position in matrix.positions.items():
                key = (month, product)
                
                if key not in merged.positions:
                    # First time seeing this position - copy it directly
                    merged.positions[key] = Position(
                        product=product,
                        contract_month=month,
                        quantity_mt=position.quantity_mt,
                        quantity_bbl=position.quantity_bbl,
                        trade_count=position.trade_count,
                        is_synthetic=position.is_synthetic
                    )
                    merged.contract_months.add(month)
                    merged.products.add(product)
                else:
                    # Merge with existing position
                    existing = merged.positions[key]
                    if position.quantity_mt is not None:
                        if existing.quantity_mt is None:
                            existing.quantity_mt = position.quantity_mt
                        else:
                            existing.quantity_mt += position.quantity_mt
                    if position.quantity_bbl is not None:
                        if existing.quantity_bbl is None:
                            existing.quantity_bbl = position.quantity_bbl
                        else:
                            existing.quantity_bbl += position.quantity_bbl
                    existing.trade_count += position.trade_count
        
        return merged
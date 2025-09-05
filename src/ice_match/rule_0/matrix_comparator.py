"""Matrix comparison logic for identifying position matches and discrepancies."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.ice_match.rule_0.position_matrix import PositionMatrix

logger = logging.getLogger(__name__)


class MatchStatus(Enum):
    """Status of position comparison."""
    MATCHED = "matched"
    QUANTITY_MISMATCH = "quantity_mismatch"
    MISSING_IN_EXCHANGE = "missing_in_exchange"
    MISSING_IN_TRADER = "missing_in_trader"
    ZERO_POSITION = "zero_position"


@dataclass
class PositionComparison:
    """Result of comparing positions between trader and exchange."""
    
    product: str
    contract_month: str
    trader_mt: Decimal
    trader_bbl: Decimal
    exchange_mt: Decimal
    exchange_bbl: Decimal
    status: MatchStatus
    difference_mt: Decimal
    difference_bbl: Decimal
    trader_trades: int = 0
    exchange_trades: int = 0
    
    @property
    def has_discrepancy(self) -> bool:
        """Check if there's any discrepancy."""
        return self.status != MatchStatus.MATCHED and self.status != MatchStatus.ZERO_POSITION
    
    @property
    def percentage_diff(self) -> Optional[float]:
        """Calculate percentage difference if both positions exist."""
        if self.trader_mt == 0 or self.exchange_mt == 0:
            return None
        return abs(float((self.difference_mt / self.trader_mt) * 100))


class MatrixComparator:
    """Compares position matrices between trader and exchange data."""
    
    def __init__(self, tolerance_mt: Decimal = Decimal("0.01")):
        """Initialize the comparator.
        
        Args:
            tolerance_mt: Tolerance for quantity matching in MT
        """
        self.tolerance_mt = tolerance_mt
        self.tolerance_bbl = tolerance_mt * Decimal("6.35")  # Approximate BBL tolerance
    
    def compare_matrices(
        self, 
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> List[PositionComparison]:
        """Compare two position matrices and identify discrepancies.
        
        Args:
            trader_matrix: Trader position matrix
            exchange_matrix: Exchange position matrix
            
        Returns:
            List of position comparisons
        """
        comparisons = []
        
        # Get all unique (contract_month, product) combinations
        all_positions: set[Tuple[str, str]] = set()
        all_positions.update(trader_matrix.positions.keys())
        all_positions.update(exchange_matrix.positions.keys())
        
        for month, product in sorted(all_positions):
            comparison = self._compare_position(
                month, product, trader_matrix, exchange_matrix
            )
            comparisons.append(comparison)
        
        logger.info(
            f"Compared {len(comparisons)} positions between trader and exchange"
        )
        
        return comparisons
    
    def _compare_position(
        self,
        month: str,
        product: str,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> PositionComparison:
        """Compare a single position between matrices.
        
        Args:
            month: Contract month
            product: Product name
            trader_matrix: Trader matrix
            exchange_matrix: Exchange matrix
            
        Returns:
            Position comparison result
        """
        trader_pos = trader_matrix.get_position(month, product)
        exchange_pos = exchange_matrix.get_position(month, product)
        
        # Extract quantities - handle None for product-specific units
        trader_mt = trader_pos.quantity_mt if trader_pos and trader_pos.quantity_mt is not None else Decimal("0")
        trader_bbl = trader_pos.quantity_bbl if trader_pos and trader_pos.quantity_bbl is not None else Decimal("0")
        exchange_mt = exchange_pos.quantity_mt if exchange_pos and exchange_pos.quantity_mt is not None else Decimal("0")
        exchange_bbl = exchange_pos.quantity_bbl if exchange_pos and exchange_pos.quantity_bbl is not None else Decimal("0")
        
        # Calculate differences
        diff_mt = trader_mt - exchange_mt if product.lower() != "brent swap" else Decimal("0")
        diff_bbl = trader_bbl - exchange_bbl if product.lower() == "brent swap" else Decimal("0")
        
        # Determine status based on product type
        if product.lower() == "brent swap":
            status = self._determine_status(
                trader_bbl, exchange_bbl, diff_bbl
            )
        else:
            status = self._determine_status(
                trader_mt, exchange_mt, diff_mt
            )
        
        return PositionComparison(
            product=product,
            contract_month=month,
            trader_mt=trader_mt,
            trader_bbl=trader_bbl,
            exchange_mt=exchange_mt,
            exchange_bbl=exchange_bbl,
            status=status,
            difference_mt=diff_mt,
            difference_bbl=diff_bbl,
            trader_trades=trader_pos.trade_count if trader_pos else 0,
            exchange_trades=exchange_pos.trade_count if exchange_pos else 0
        )
    
    def _determine_status(
        self,
        trader_mt: Decimal,
        exchange_mt: Decimal,
        diff_mt: Decimal
    ) -> MatchStatus:
        """Determine the match status based on quantities.
        
        Args:
            trader_mt: Trader quantity in MT
            exchange_mt: Exchange quantity in MT
            diff_mt: Difference in MT
            
        Returns:
            Match status
        """
        # Both zero
        if trader_mt == 0 and exchange_mt == 0:
            return MatchStatus.ZERO_POSITION
        
        # Missing in one side
        if trader_mt == 0:
            return MatchStatus.MISSING_IN_TRADER
        if exchange_mt == 0:
            return MatchStatus.MISSING_IN_EXCHANGE
        
        # Check if within tolerance
        if abs(diff_mt) <= self.tolerance_mt:
            return MatchStatus.MATCHED
        
        return MatchStatus.QUANTITY_MISMATCH
    
    def get_summary_statistics(
        self, 
        comparisons: List[PositionComparison]
    ) -> Dict[str, Any]:
        """Generate summary statistics from comparisons.
        
        Args:
            comparisons: List of position comparisons
            
        Returns:
            Dictionary of statistics
        """
        stats = {
            "total_positions": len(comparisons),
            "matched_positions": 0,
            "quantity_mismatches": 0,
            "missing_in_exchange": 0,
            "missing_in_trader": 0,
            "zero_positions": 0,
            "total_discrepancies": 0,
            "match_rate": 0.0
        }
        
        for comp in comparisons:
            if comp.status == MatchStatus.MATCHED:
                stats["matched_positions"] += 1
            elif comp.status == MatchStatus.QUANTITY_MISMATCH:
                stats["quantity_mismatches"] += 1
            elif comp.status == MatchStatus.MISSING_IN_EXCHANGE:
                stats["missing_in_exchange"] += 1
            elif comp.status == MatchStatus.MISSING_IN_TRADER:
                stats["missing_in_trader"] += 1
            elif comp.status == MatchStatus.ZERO_POSITION:
                stats["zero_positions"] += 1
            
            if comp.has_discrepancy:
                stats["total_discrepancies"] += 1
        
        # Calculate match rate (excluding zero positions)
        non_zero = len(comparisons) - stats["zero_positions"]
        if non_zero > 0:
            stats["match_rate"] = (stats["matched_positions"] / non_zero) * 100
        
        return stats
    
    def get_discrepancies_by_month(
        self,
        comparisons: List[PositionComparison]
    ) -> Dict[str, List[PositionComparison]]:
        """Group discrepancies by contract month.
        
        Args:
            comparisons: List of position comparisons
            
        Returns:
            Dictionary mapping contract months to their discrepancies
        """
        discrepancies: Dict[str, List[PositionComparison]] = {}
        
        for comp in comparisons:
            if comp.has_discrepancy:
                if comp.contract_month not in discrepancies:
                    discrepancies[comp.contract_month] = []
                discrepancies[comp.contract_month].append(comp)
        
        return discrepancies
    
    def get_discrepancies_by_product(
        self,
        comparisons: List[PositionComparison]
    ) -> Dict[str, List[PositionComparison]]:
        """Group discrepancies by product.
        
        Args:
            comparisons: List of position comparisons
            
        Returns:
            Dictionary mapping products to their discrepancies
        """
        discrepancies: Dict[str, List[PositionComparison]] = {}
        
        for comp in comparisons:
            if comp.has_discrepancy:
                if comp.product not in discrepancies:
                    discrepancies[comp.product] = []
                discrepancies[comp.product].append(comp)
        
        return discrepancies
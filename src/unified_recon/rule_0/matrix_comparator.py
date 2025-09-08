"""Generic matrix comparison logic for unified Rule 0."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.unified_recon.rule_0.position_matrix import PositionMatrix

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
    trader_quantity: Decimal
    exchange_quantity: Decimal
    unit: str
    status: MatchStatus
    difference: Decimal
    trader_trades: int = 0
    exchange_trades: int = 0
    
    @property
    def has_discrepancy(self) -> bool:
        """Check if there's any discrepancy."""
        return self.status != MatchStatus.MATCHED and self.status != MatchStatus.ZERO_POSITION
    
    @property
    def percentage_diff(self) -> Optional[float]:
        """Calculate percentage difference if both positions exist."""
        if self.trader_quantity == 0 and self.exchange_quantity == 0:
            return 0.0
        if self.trader_quantity == 0:
            return None
        return abs(float((self.difference / self.trader_quantity) * 100))


class UnifiedMatrixComparator:
    """Compares position matrices between trader and exchange data for any exchange."""
    
    def __init__(self, exchange: str, tolerance: Decimal = Decimal("0.01")):
        """Initialize the comparator.
        
        Args:
            exchange: Exchange name for context
            tolerance: Tolerance for quantity matching
        """
        self.exchange = exchange
        self.tolerance = tolerance
    
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
        all_positions: Set[Tuple[str, str]] = set()
        all_positions.update(trader_matrix.positions.keys())
        all_positions.update(exchange_matrix.positions.keys())
        
        logger.debug(f"Trader positions: {len(trader_matrix.positions)}, Exchange positions: {len(exchange_matrix.positions)}")
        logger.debug(f"All unique positions to compare: {len(all_positions)}")
        
        for month, product in sorted(all_positions):
            comparison = self._compare_position(
                month, product, trader_matrix, exchange_matrix
            )
            comparisons.append(comparison)
        
        logger.info(
            f"Compared {len(comparisons)} positions between trader and exchange for {self.exchange}"
        )
        
        return comparisons
    
    def _compare_position(
        self,
        month: str,
        product: str,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix
    ) -> PositionComparison:
        """Compare a single position between matrices."""
        trader_pos = trader_matrix.get_position(month, product)
        exchange_pos = exchange_matrix.get_position(month, product)
        
        # Extract quantities
        trader_qty = trader_pos.quantity if trader_pos else Decimal("0")
        exchange_qty = exchange_pos.quantity if exchange_pos else Decimal("0")
        
        # Get unit (prefer trader's unit if available)
        unit = ""
        if trader_pos and trader_pos.unit:
            unit = trader_pos.unit
        elif exchange_pos and exchange_pos.unit:
            unit = exchange_pos.unit
        
        # Calculate difference
        diff = trader_qty - exchange_qty
        
        # Determine status
        status = self._determine_status(trader_qty, exchange_qty, diff)
        
        return PositionComparison(
            product=product,
            contract_month=month,
            trader_quantity=trader_qty,
            exchange_quantity=exchange_qty,
            unit=unit,
            status=status,
            difference=diff,
            trader_trades=trader_pos.trade_count if trader_pos else 0,
            exchange_trades=exchange_pos.trade_count if exchange_pos else 0
        )
    
    def _determine_status(
        self,
        trader_qty: Decimal,
        exchange_qty: Decimal,
        diff: Decimal
    ) -> MatchStatus:
        """Determine the match status based on quantities."""
        # Both zero
        if trader_qty == 0 and exchange_qty == 0:
            return MatchStatus.ZERO_POSITION
        
        # Missing in one side
        if trader_qty == 0:
            return MatchStatus.MISSING_IN_TRADER
        if exchange_qty == 0:
            return MatchStatus.MISSING_IN_EXCHANGE
        
        # Check if within tolerance
        if abs(diff) <= self.tolerance:
            return MatchStatus.MATCHED
        
        return MatchStatus.QUANTITY_MISMATCH
    
    def get_summary_statistics(
        self,
        comparisons: List[PositionComparison]
    ) -> Dict[str, Any]:
        """Generate summary statistics from comparisons."""
        stats: Dict[str, Any] = {
            "exchange": self.exchange,
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
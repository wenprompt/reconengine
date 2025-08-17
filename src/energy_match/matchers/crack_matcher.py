"""Crack matching implementation for Rule 3."""

from typing import List, Dict, Tuple, Union
from decimal import Decimal
import logging
import uuid
from collections import defaultdict

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager

logger = logging.getLogger(__name__)


class CrackMatcher:
    """Implements Rule 3: Crack matching with unit conversion.
    
    From rules.md:
    A crack match occurs when a trader executes a crack spread trade (price 
    differential between refined products and crude oil) that appears in both 
    data sources but may require unit conversion between metric tons (MT) and 
    barrels (BBL).
    
    Confidence: 95%
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the crack matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        self.config_manager = config_manager
        self.rule_number = 3
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        # Unit conversion tolerances from config
        self.BBL_TOLERANCE = config_manager.get_crack_tolerance_bbl()  # ±100 BBL
        self.MT_TOLERANCE = config_manager.get_crack_tolerance_mt()   # ±50 MT
        self.BBL_TO_MT_RATIO = config_manager.get_conversion_ratio()  # 6.35
        
        logger.info(f"Initialized CrackMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all crack matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched trades
            
        Returns:
            List of MatchResult objects for crack matches found
        """
        logger.info("Starting crack matching (Rule 3)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        # Filter for crack trades only
        crack_trader_trades = self._filter_crack_trades(trader_trades)
        crack_exchange_trades = self._filter_crack_trades(exchange_trades)
        
        logger.info(f"Checking {len(crack_trader_trades)} crack trader trades against "
                   f"{len(crack_exchange_trades)} crack exchange trades")
        
        # Build optimized index from exchange trades for O(1) lookup
        exchange_index = self._build_exchange_index(crack_exchange_trades, pool_manager)
        
        # Find matches using indexed lookup - O(N) instead of O(N*M)
        for trader_trade in crack_trader_trades:
            # CRITICAL: Verify trade is still unmatched
            if pool_manager.is_trade_matched(trader_trade):
                continue
                
            # Build lookup key for this trader trade
            match_key = self._build_match_key(trader_trade)
            
            # Get potential candidates from index - O(1) lookup
            candidates = exchange_index.get(match_key, [])
            
            # Find first valid match among candidates
            for exchange_trade in candidates:
                # CRITICAL: Verify trade is still unmatched (prevents duplicates)
                if pool_manager.is_trade_matched(exchange_trade):
                    continue
                
                # Validate quantity with conversion tolerance
                if self._validate_quantity_with_conversion(trader_trade, exchange_trade):
                    match_result = self._create_crack_match_result(trader_trade, exchange_trade)
                    matches.append(match_result)
                    
                    # Remove matched trades from pools (prevents duplicates)
                    success = pool_manager.remove_matched_trades(
                        trader_trade, exchange_trade, MatchType.CRACK.value
                    )
                    
                    if not success:
                        logger.error("Failed to remove crack matched trades from pool")
                    else:
                        logger.debug(f"Created crack match: {match_result}")
                    
                    break  # Move to next trader trade
        
        logger.info(f"Found {len(matches)} crack matches")
        return matches
    
    def _filter_crack_trades(self, trades: List[Trade]) -> List[Trade]:
        """Filter trades to only include crack trades.
        
        Args:
            trades: List of trades to filter
            
        Returns:
            List of trades that contain "crack" in product name
        """
        crack_trades = []
        for trade in trades:
            if "crack" in trade.product_name.lower():
                crack_trades.append(trade)
        
        logger.debug(f"Filtered {len(crack_trades)} crack trades from {len(trades)} total")
        return crack_trades
    
    def _build_exchange_index(self, exchange_trades: List[Trade], pool_manager: UnmatchedPoolManager) -> Dict[Tuple, List[Trade]]:
        """Build optimized index from exchange trades for fast lookup.
        
        Args:
            exchange_trades: List of exchange crack trades
            pool_manager: Pool manager to check if trades are already matched
            
        Returns:
            Dictionary mapping match keys to lists of candidate exchange trades
        """
        index: Dict[Tuple, List[Trade]] = defaultdict(list)
        
        for trade in exchange_trades:
            # CRITICAL: Only index unmatched trades (prevents duplicates)
            if not pool_manager.is_trade_matched(trade):
                match_key = self._build_match_key(trade)
                index[match_key].append(trade)
        
        logger.debug(f"Built exchange index with {len(index)} unique match keys")
        return index
    
    def _build_match_key(self, trade: Trade) -> Tuple[str, str, Decimal, Union[int, None], str]:
        """Build consistent match key for indexing and lookup.
        
        For crack matches, trades must match exactly on:
        1. Product name (already filtered for "crack")
        2. Contract month 
        3. Price
        4. Broker group ID
        5. Buy/Sell indicator
        
        Quantity is handled separately with tolerance validation.
        
        Args:
            trade: Trade to build key for
            
        Returns:
            Tuple key for consistent matching
        """
        return (
            trade.product_name,
            trade.contract_month,
            trade.price,
            trade.broker_group_id,
            trade.buy_sell
        )
    
    
    def _validate_quantity_with_conversion(self, trader_trade: Trade, exchange_trade: Trade) -> bool:
        """Validate quantities match after unit conversion with tolerance.
        
        Args:
            trader_trade: Trade from trader source
            exchange_trade: Trade from exchange source
            
        Returns:
            True if quantities match within tolerance after conversion
        """
        # Convert to common unit for comparison (use MT as reference)
        trader_qty_mt = trader_trade.quantity_mt
        exchange_qty_mt = exchange_trade.quantity_mt
        
        # Calculate difference in MT
        qty_diff_mt = abs(trader_qty_mt - exchange_qty_mt)
        
        # Check if within MT tolerance
        if qty_diff_mt <= self.MT_TOLERANCE:
            logger.debug(f"Quantity match within MT tolerance: {qty_diff_mt} MT <= {self.MT_TOLERANCE} MT")
            return True
        
        # Also check in BBL for additional validation
        trader_qty_bbl = trader_trade.quantity_bbl
        exchange_qty_bbl = exchange_trade.quantity_bbl
        qty_diff_bbl = abs(trader_qty_bbl - exchange_qty_bbl)
        
        if qty_diff_bbl <= self.BBL_TOLERANCE:
            logger.debug(f"Quantity match within BBL tolerance: {qty_diff_bbl} BBL <= {self.BBL_TOLERANCE} BBL")
            return True
        
        logger.debug(f"Quantity mismatch: {qty_diff_mt} MT / {qty_diff_bbl} BBL exceed tolerances")
        return False
    
    def _create_crack_match_result(self, trader_trade: Trade, exchange_trade: Trade) -> MatchResult:
        """Create MatchResult for crack match.
        
        Args:
            trader_trade: Matched trader trade
            exchange_trade: Matched exchange trade
            
        Returns:
            MatchResult representing the crack match
        """
        # Generate unique match ID
        match_id = f"CRACK_{uuid.uuid4().hex[:8].upper()}"
        
        # Fields that matched for cracks
        matched_fields = [
            "product_name",
            "contract_month", 
            "price",
            "broker_group_id",
            "buy_sell"
        ]
        
        # Check if unit conversion was applied
        tolerances_applied: dict[str, str | float] = {}
        if trader_trade.unit.lower() != exchange_trade.unit.lower():
            matched_fields.append("quantity_with_conversion")
            tolerances_applied["unit_conversion"] = f"{trader_trade.unit} ↔ {exchange_trade.unit}"
            tolerances_applied["conversion_ratio"] = float(self.BBL_TO_MT_RATIO)
        else:
            matched_fields.append("quantity")
        
        # Calculate quantity difference for tolerance tracking
        qty_diff_mt = abs(trader_trade.quantity_mt - exchange_trade.quantity_mt)
        qty_diff_bbl = abs(trader_trade.quantity_bbl - exchange_trade.quantity_bbl)
        
        if qty_diff_mt > 0 or qty_diff_bbl > 0:
            tolerances_applied["quantity_tolerance_mt"] = float(qty_diff_mt)
            tolerances_applied["quantity_tolerance_bbl"] = float(qty_diff_bbl)
        
        # No differing fields for successful crack matches
        differing_fields: List[str] = []
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.CRACK,
            confidence=self.confidence,
            trader_trade=trader_trade,
            exchange_trade=exchange_trade,
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            tolerances_applied=tolerances_applied,
            rule_order=self.rule_number
        )
    
    def get_rule_info(self) -> dict[str, str | int | float | list[str] | dict[str, float]]:
        """Get information about this matching rule.
        
        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Crack Match",
            "match_type": MatchType.CRACK.value,
            "confidence": float(self.confidence),
            "description": "Matches crack spread trades with unit conversion between MT and BBL",
            "requirements": [
                "Product name must contain 'crack'",
                "Same contract month",
                "Same price", 
                "Same broker group",
                "Same buy/sell indicator",
                "Quantity match after unit conversion (±100 BBL or ±50 MT)"
            ],
            "tolerances": {
                "quantity_bbl": float(self.config_manager.get_crack_tolerance_bbl()),
                "quantity_mt": float(self.config_manager.get_crack_tolerance_mt()),
                "conversion_ratio": float(self.config_manager.get_conversion_ratio())
            }
        }
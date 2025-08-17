"""Spread matching implementation for Rule 2."""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
import logging
import uuid
from collections import defaultdict

from ..models import Trade, TradeSource, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager

logger = logging.getLogger(__name__)


class SpreadMatcher:
    """Implements Rule 2: Spread matching.
    
    From rules.md:
    A spread match occurs when a trader executes a spread trade (buying one 
    contract and selling another related contract simultaneously) that appears 
    as two separate trades in the exchange data but as a calculated spread in 
    the trader data.
    
    Confidence: 95%
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the spread matcher.
        
        Args:
            config_manager: Configuration manager with rule settings
        """
        self.config_manager = config_manager
        self.rule_number = 2
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        
        logger.info(f"Initialized SpreadMatcher with {self.confidence}% confidence")
    
    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all spread matches between unmatched trader and exchange trades.
        
        Args:
            pool_manager: Pool manager containing unmatched trades
            
        Returns:
            List of MatchResult objects for spread matches found
        """
        logger.info("Starting spread matching (Rule 2)")
        
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()
        
        logger.info(f"Checking {len(trader_trades)} trader trades against "
                   f"{len(exchange_trades)} exchange trades for spreads")
        
        # Group trader trades into potential spreads
        trader_spread_groups = self._group_trader_spreads(trader_trades, pool_manager)
        
        # Group exchange trades by criteria for spread matching  
        exchange_spread_groups = self._group_exchange_spreads(exchange_trades, pool_manager)
        
        # Find matches between trader spread groups and exchange spread groups
        for trader_group in trader_spread_groups:
            # CRITICAL: Verify all trades in group are still unmatched
            if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                continue  # Skip if any trade already matched
                
            match_result = self._find_spread_match(
                trader_group, exchange_spread_groups, pool_manager
            )
            if match_result:
                matches.append(match_result)
                
                # Remove matched trades from pools (2 trader + 2 exchange)
                exchange_trades_for_removal = [match_result.exchange_trade] + match_result.additional_exchange_trades
                success = self._remove_spread_trades_from_pool(
                    trader_group, exchange_trades_for_removal, pool_manager
                )
                
                if not success:
                    logger.error("Failed to remove spread matched trades from pool")
                else:
                    logger.debug(f"Created spread match: {match_result}")
        
        logger.info(f"Found {len(matches)} spread matches")
        return matches
    
    def _group_trader_spreads(
        self, 
        trader_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> List[List[Trade]]:
        """Group trader trades into potential spread pairs.
        
        Args:
            trader_trades: List of unmatched trader trades
            pool_manager: Pool manager to check if trades are already matched
            
        Returns:
            List of trade pairs that could be spread legs
        """
        spread_groups = []
        
        # Group by key characteristics for spread identification
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        
        for trade in trader_trades:
            # CRITICAL: Only include trades that are still unmatched
            if not pool_manager.is_trade_matched(trade):
                # Group by: product, quantity, broker_group_id
                # This groups potential spread legs together
                key = (
                    trade.product_name,
                    trade.quantity_mt,  # Use MT for consistent comparison
                    trade.broker_group_id
                )
                trade_groups[key].append(trade)
        
        # Look for pairs within each group
        for key, trades in trade_groups.items():
            if len(trades) >= 2:
                # Look for potential spread patterns
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        trade1, trade2 = trades[i], trades[j]
                        
                        # Check if this could be a spread pair
                        if self._is_potential_trader_spread_pair(trade1, trade2):
                            spread_groups.append([trade1, trade2])
        
        logger.debug(f"Identified {len(spread_groups)} potential trader spread groups")
        return spread_groups
    
    def _is_potential_trader_spread_pair(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trader trades could form a spread pair.
        
        Args:
            trade1: First trade
            trade2: Second trade
            
        Returns:
            True if trades could be spread legs
        """
        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False
        
        # Must have different contract months
        if trade1.contract_month == trade2.contract_month:
            return False
        
        # Check for spread indicators
        has_spread_flag = (
            (trade1.spread == "S" or trade2.spread == "S") or
            (trade1.price == Decimal("0") or trade2.price == Decimal("0"))
        )
        
        return has_spread_flag
    
    def _group_exchange_spreads(
        self, 
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> Dict[Tuple, List[Trade]]:
        """Group exchange trades by criteria for spread matching.
        
        Args:
            exchange_trades: List of unmatched exchange trades
            pool_manager: Pool manager to check if trades are already matched
            
        Returns:
            Dictionary mapping group keys to lists of trades
        """
        trade_groups: Dict[Tuple, List[Trade]] = defaultdict(list)
        
        for trade in exchange_trades:
            # CRITICAL: Only include trades that are still unmatched
            # This prevents already matched exchange trades from being considered
            if not pool_manager.is_trade_matched(trade):
                # Group by: product, quantity, broker_group_id
                key = (
                    trade.product_name,
                    trade.quantity_mt,  # Use MT for consistent comparison
                    trade.broker_group_id
                )
                trade_groups[key].append(trade)
        
        logger.debug(f"Grouped exchange trades into {len(trade_groups)} groups")
        return trade_groups
    
    def _find_spread_match(
        self, 
        trader_group: List[Trade],
        exchange_groups: Dict[Tuple, List[Trade]],
        pool_manager: UnmatchedPoolManager
    ) -> Optional[MatchResult]:
        """Find spread match for a trader spread group.
        
        Args:
            trader_group: List of 2 trader trades forming a spread
            exchange_groups: Grouped exchange trades
            pool_manager: Pool manager for validation
            
        Returns:
            MatchResult if spread match found, None otherwise
        """
        if len(trader_group) != 2:
            return None
        
        trader_trade1, trader_trade2 = trader_group
        
        # Create group key for this trader spread
        group_key = (
            trader_trade1.product_name,
            trader_trade1.quantity_mt,
            trader_trade1.broker_group_id
        )
        
        # Look for matching exchange trades
        if group_key not in exchange_groups:
            return None
        
        exchange_candidates = exchange_groups[group_key]
        
        # Look for two exchange trades that match the spread pattern
        for i in range(len(exchange_candidates)):
            for j in range(i + 1, len(exchange_candidates)):
                exchange_trade1, exchange_trade2 = exchange_candidates[i], exchange_candidates[j]
                
                # CRITICAL: Skip if either trade is already matched
                if (pool_manager.is_trade_matched(exchange_trade1) or 
                    pool_manager.is_trade_matched(exchange_trade2)):
                    continue
                
                # CRITICAL: Double-check trader trades are still unmatched
                if any(pool_manager.is_trade_matched(trade) for trade in trader_group):
                    return None  # Trader trades were matched by another rule
                
                # Check if this forms a valid spread match
                if self._validate_spread_match(
                    trader_group, [exchange_trade1, exchange_trade2]
                ):
                    return self._create_spread_match_result(
                        trader_group, [exchange_trade1, exchange_trade2]
                    )
        
        return None
    
    def _validate_spread_match(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade]
    ) -> bool:
        """Validate that trader and exchange trades form a valid spread match.
        
        Args:
            trader_trades: List of 2 trader trades
            exchange_trades: List of 2 exchange trades
            
        Returns:
            True if valid spread match
        """
        if len(trader_trades) != 2 or len(exchange_trades) != 2:
            return False
        
        trader_trade1, trader_trade2 = trader_trades
        exchange_trade1, exchange_trade2 = exchange_trades
        
        # Exchange trades must have opposite B/S directions
        if exchange_trade1.buy_sell == exchange_trade2.buy_sell:
            return False
        
        # Exchange trades must have different contract months
        if exchange_trade1.contract_month == exchange_trade2.contract_month:
            return False
        
        # Contract months must match between trader and exchange
        trader_months = {trader_trade1.contract_month, trader_trade2.contract_month}
        exchange_months = {exchange_trade1.contract_month, exchange_trade2.contract_month}
        
        if trader_months != exchange_months:
            return False
        
        # B/S directions must match appropriately
        if not self._validate_spread_directions(trader_trades, exchange_trades):
            return False
        
        # Price calculation must match (if both legs have prices)
        if not self._validate_spread_prices(trader_trades, exchange_trades):
            return False
        
        return True
    
    def _validate_spread_directions(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade]
    ) -> bool:
        """Validate that B/S directions match between trader and exchange spreads.
        
        Args:
            trader_trades: List of 2 trader trades
            exchange_trades: List of 2 exchange trades
            
        Returns:
            True if directions match correctly
        """
        # Create mapping of contract month to B/S for each side
        trader_month_bs = {
            trade.contract_month: trade.buy_sell for trade in trader_trades
        }
        exchange_month_bs = {
            trade.contract_month: trade.buy_sell for trade in exchange_trades
        }
        
        # For each contract month, B/S should match
        for month in trader_month_bs:
            if month not in exchange_month_bs:
                return False
            if trader_month_bs[month] != exchange_month_bs[month]:
                return False
        
        return True
    
    def _validate_spread_prices(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade]
    ) -> bool:
        """Validate spread price calculation.
        
        Args:
            trader_trades: List of 2 trader trades
            exchange_trades: List of 2 exchange trades
            
        Returns:
            True if price calculation is valid
        """
        # Find the trader trade with non-zero price (the spread price)
        trader_spread_price = None
        for trade in trader_trades:
            if trade.price != Decimal("0"):
                trader_spread_price = trade.price
                break
        
        if trader_spread_price is None:
            # Both prices are zero, can't validate
            return True
        
        # Calculate exchange spread price using earlier contract - later contract
        # First, identify which exchange trade has the earlier contract month
        exchange_trade1, exchange_trade2 = exchange_trades[0], exchange_trades[1]
        
        # Parse contract months to determine chronological order
        # Format is "MMM-YY" (e.g., "Jun-25", "Jul-25")
        def parse_contract_month(month_str: str) -> tuple[int, int]:
            """Parse contract month string into (year, month_order) for comparison."""
            try:
                month_abbr, year_str = month_str.split('-')
                year = int('20' + year_str)  # Convert "25" to 2025
                
                # Month order mapping
                month_order = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                
                return (year, month_order.get(month_abbr, 0))
            except (ValueError, AttributeError):
                # If parsing fails, fall back to string comparison
                return (0, 0)
        
        month1_tuple = parse_contract_month(exchange_trade1.contract_month)
        month2_tuple = parse_contract_month(exchange_trade2.contract_month)
        
        # Calculate spread as earlier_contract_price - later_contract_price
        if month1_tuple < month2_tuple:
            # trade1 is earlier, trade2 is later
            exchange_spread_price = exchange_trade1.price - exchange_trade2.price
        else:
            # trade2 is earlier, trade1 is later
            exchange_spread_price = exchange_trade2.price - exchange_trade1.price
        
        # Prices should match exactly for spread validation
        return trader_spread_price == exchange_spread_price
    
    def _create_spread_match_result(
        self, 
        trader_trades: List[Trade], 
        exchange_trades: List[Trade]
    ) -> MatchResult:
        """Create MatchResult for spread match.
        
        Args:
            trader_trades: List of 2 matched trader trades
            exchange_trades: List of 2 matched exchange trades
            
        Returns:
            MatchResult representing the spread match
        """
        # Generate unique match ID
        match_id = f"SPREAD_{uuid.uuid4().hex[:8].upper()}"
        
        # Fields that matched for spreads
        matched_fields = [
            "product_name",
            "quantity_mt",
            "broker_group_id",
            "contract_months",
            "spread_price_calculation"
        ]
        
        # No differing fields for successful spread matches
        differing_fields: List[str] = []
        
        # Use the first trader trade as the primary trade for the result
        primary_trader = trader_trades[0]
        primary_exchange = exchange_trades[0]
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.SPREAD,
            confidence=self.confidence,
            trader_trade=primary_trader,
            exchange_trade=primary_exchange,
            matched_fields=matched_fields,
            differing_fields=differing_fields,
            tolerances_applied={},  # No tolerances for spread match
            rule_order=self.rule_number,
            # Store additional trades for spread
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:]
        )
    
    def _remove_spread_trades_from_pool(
        self,
        trader_trades: List[Trade],
        exchange_trades: List[Trade], 
        pool_manager: UnmatchedPoolManager
    ) -> bool:
        """Remove all spread trades from the unmatched pools.
        
        Args:
            trader_trades: List of trader trades to remove  
            exchange_trades: List of exchange trades to remove
            pool_manager: Pool manager to update
            
        Returns:
            True if all trades were successfully removed
        """
        if len(trader_trades) != len(exchange_trades):
            logger.error(f"Mismatch in trade counts: {len(trader_trades)} trader, {len(exchange_trades)} exchange")
            return False
        
        success = True
        
        # Remove each trader-exchange pair
        for trader_trade, exchange_trade in zip(trader_trades, exchange_trades):
            # CRITICAL: Verify trades are still unmatched before removal
            if pool_manager.is_trade_matched(trader_trade):
                logger.error(f"Trader trade {trader_trade.trade_id} already matched!")
                success = False
                continue
                
            if pool_manager.is_trade_matched(exchange_trade):
                logger.error(f"Exchange trade {exchange_trade.trade_id} already matched!")
                success = False
                continue
                
            if not pool_manager.remove_matched_trades(
                trader_trade, exchange_trade, MatchType.SPREAD.value
            ):
                success = False
                logger.error(f"Failed to remove spread trades: {trader_trade.trade_id} <-> {exchange_trade.trade_id}")
        
        return success
    
    def get_rule_info(self) -> dict:
        """Get information about this matching rule.
        
        Returns:
            Dictionary with rule information
        """
        return {
            "rule_number": self.rule_number,
            "rule_name": "Spread Match",
            "match_type": MatchType.SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches spread trades where trader shows calculated spread but exchange shows individual legs",
            "requirements": [
                "Both sources must have 2 trades each (spread legs)",
                "Same product, quantity, and broker group",
                "Opposite B/S directions for each leg",
                "Different contract months for legs",
                "Price calculation must match (if available)"
            ]
        }
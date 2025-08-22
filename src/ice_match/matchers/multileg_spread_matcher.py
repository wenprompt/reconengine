"""Multileg spread matching implementation for Rule 9."""

from typing import List, Optional, Dict, Tuple, Set
from decimal import Decimal
import logging
from collections import defaultdict
from itertools import combinations

from ..models import Trade, MatchResult, MatchType
from ..core import UnmatchedPoolManager
from ..config import ConfigManager
from ..normalizers import TradeNormalizer
from .multi_leg_base_matcher import MultiLegBaseMatcher
from ..utils.trade_helpers import get_month_order_tuple

logger = logging.getLogger(__name__)


class MultilegSpreadMatcher(MultiLegBaseMatcher):
    """Implements Rule 9: Multileg spread matching.
    
    Handles scenarios where 2 trader spread trades correspond to 4+ exchange trades
    that form multiple interconnected spreads with internal netting legs.
    """

    def __init__(self, config_manager: ConfigManager, normalizer: TradeNormalizer):
        """Initialize the multileg spread matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 9
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        logger.info(f"Initialized MultilegSpreadMatcher with {self.confidence}% confidence")

    def get_rule_info(self) -> dict:
        """Get rule information for display purposes."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Multileg Spread Match",
            "match_type": MatchType.MULTILEG_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches 2 trader spreads against 4+ exchange trades with netting",
            "fields_matched": self.get_universal_matched_fields([
                "product_name",
                "broker_group_id", 
                "exch_clearing_acct_id"
            ]),
            "requirements": [
                "Trader: Exactly 2 spread trades with different contract months and opposite B/S",
                "Tier 1: 4 exchange trades (3 months) with perfect internal netting",
                "Tier 2: 6 exchange trades (4 months) with flexible netting",
                "Perfect quantity matching across all trades",
                "Combined exchange spread prices must equal trader spread prices within ±0.01",
                "Same base product and broker details across all trades"
            ],
            "tolerances": {
                "price_difference": "±0.01"
            },
            "tiers": {
                "tier_1": {
                    "description": "4 exchange trades (3 months) with perfect internal netting",
                    "example": "Sep/Oct + Oct/Nov = Sep/Nov (Oct legs @ same price)",
                    "pattern": "A-sell, B-buy, B-sell, C-buy where B-buy price = B-sell price"
                },
                "tier_2": {
                    "description": "6 exchange trades (4 months) forming 3 consecutive spreads", 
                    "example": "Aug/Sep + Sep/Oct + Oct/Nov = Aug/Nov (-2.75 + 2.25 + 4.00 = 3.50)",
                    "pattern": "A-sell, B-buy, B-sell, C-buy, C-sell, D-buy (flexible pricing)"
                }
            }
        }

    def find_matches(self, pool_manager: UnmatchedPoolManager) -> List[MatchResult]:
        """Find all multileg spread matches."""
        logger.info("Starting multileg spread matching (Rule 9)")
        matches = []
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Group trader trades into potential spread pairs
        trader_spread_pairs = self._group_trader_spread_pairs(trader_trades, pool_manager)
        logger.debug(f"Found {len(trader_spread_pairs)} trader spread pairs")

        # Get available exchange trades for combination analysis
        available_exchange_trades = [
            trade for trade in exchange_trades 
            if not pool_manager.is_trade_matched(trade)
        ]
        logger.debug(f"Found {len(available_exchange_trades)} available exchange trades")

        for trader_pair in trader_spread_pairs:
            if any(pool_manager.is_trade_matched(trade) for trade in trader_pair):
                continue

            match_result = self._find_multileg_match(trader_pair, available_exchange_trades, pool_manager)
            if match_result:
                matches.append(match_result)
                # Record the match to remove all involved trades from unmatched pools
                pool_manager.record_match(match_result)
                logger.info(f"Found multileg spread match: {match_result.match_id}")

        logger.info(f"Completed multileg spread matching - found {len(matches)} matches")
        return matches

    def _group_trader_spread_pairs(self, trader_trades: List[Trade], pool_manager: UnmatchedPoolManager) -> List[List[Trade]]:
        """Group trader trades into spread pairs for multileg matching.
        
        Looks for trader spread pattern: one leg with price, one leg with price 0.00
        """
        available_trades = [
            trade for trade in trader_trades
            if not pool_manager.is_trade_matched(trade)
        ]
        
        pairs = []
        
        # Group by product, broker details, and quantity
        grouped_trades = defaultdict(list)
        for trade in available_trades:
            key = (
                trade.product_name,
                trade.broker_group_id,
                trade.exch_clearing_acct_id,
                self._get_quantity_for_grouping(trade, self.normalizer)
            )
            grouped_trades[key].append(trade)
        
        # Find spread pairs within each group
        for trades_list in grouped_trades.values():
            for i, trade1 in enumerate(trades_list):
                for j, trade2 in enumerate(trades_list[i+1:], i+1):
                    if self._is_trader_spread_pair(trade1, trade2):
                        pairs.append([trade1, trade2])
        
        return pairs

    def _is_trader_spread_pair(self, trade1: Trade, trade2: Trade) -> bool:
        """Check if two trader trades form a valid spread pair (price + 0.00 pattern)."""
        # Must have different contract months
        if trade1.contract_month == trade2.contract_month:
            return False
            
        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False
            
        # One must have price, other must have price 0.00
        prices = [trade1.price, trade2.price]
        if not (0 in prices and any(p != 0 for p in prices)):
            return False
            
        return True

    def _get_trader_spread_info(self, trader_pair: List[Trade]) -> Optional[Dict]:
        """Extract spread info from trader pair (price leg + zero leg)."""
        if len(trader_pair) != 2:
            return None
            
        # Identify price leg vs zero leg
        price_trade = next((t for t in trader_pair if t.price != 0), None)
        zero_trade = next((t for t in trader_pair if t.price == 0), None)
        
        if not price_trade or not zero_trade:
            return None
            
        # Determine spread direction and months
        if price_trade.buy_sell == 'S':  # Sell price leg means sell spread
            sold_month = price_trade.contract_month
            bought_month = zero_trade.contract_month
        else:  # Buy price leg means buy spread
            bought_month = price_trade.contract_month
            sold_month = zero_trade.contract_month
            
        return {
            'sold_month': sold_month,
            'bought_month': bought_month,
            'spread_price': abs(price_trade.price),  # Spread price magnitude
            'quantity': self._get_quantity_for_grouping(price_trade, self.normalizer),
            'is_sell_spread': price_trade.buy_sell == 'S'
        }

    def _find_tier1_netting_combination(self, trader_pair: List[Trade], trader_spread_info: Dict, exchange_trades: List[Trade]) -> Optional[MatchResult]:
        """Tier 1: Find 4 exchange trades (3 months) that net to match the trader spread."""
        target_sold_month = trader_spread_info['sold_month']
        target_bought_month = trader_spread_info['bought_month'] 
        target_price = trader_spread_info['spread_price']
        
        # Try all combinations of 4 exchange trades
        for combo in combinations(exchange_trades, 4):
            if self._validate_tier1_netting_pattern(combo, target_sold_month, target_bought_month, target_price):
                return self._create_match_result_from_combo(trader_pair, list(combo))
        
        return None

    def _validate_tier1_netting_pattern(self, exchange_combo: Tuple[Trade, ...], 
                                        target_sold_month: str, target_bought_month: str, target_price: Decimal) -> bool:
        """Tier 1: Check if 4 exchange trades (3 months) form required netting pattern."""
        # Group trades by contract month and direction
        month_trades = defaultdict(list)
        for trade in exchange_combo:
            month_trades[trade.contract_month].append(trade)
        
        # Must have exactly 3 months (target_sold, intermediate, target_bought)
        if len(month_trades) != 3:
            return False
            
        months = set(month_trades.keys())
        if target_sold_month not in months or target_bought_month not in months:
            return False
            
        # Find the intermediate month
        intermediate_month = next(m for m in months 
                                if m not in [target_sold_month, target_bought_month])
        
        # Check each month has the right pattern
        # Target sold month: should have one sell
        sold_trades = month_trades[target_sold_month]
        if len(sold_trades) != 1 or sold_trades[0].buy_sell != 'S':
            return False
            
        # Target bought month: should have one buy
        bought_trades = month_trades[target_bought_month] 
        if len(bought_trades) != 1 or bought_trades[0].buy_sell != 'B':
            return False
            
        # Intermediate month: should have one buy and one sell that net out
        intermediate_trades = month_trades[intermediate_month]
        if len(intermediate_trades) != 2:
            return False
            
        inter_buy = next((t for t in intermediate_trades if t.buy_sell == 'B'), None)
        inter_sell = next((t for t in intermediate_trades if t.buy_sell == 'S'), None)
        
        if not inter_buy or not inter_sell or inter_buy.price != inter_sell.price:
            return False
            
        # Calculate combined spread price
        # Calculate spread prices
        spread1_price = sold_trades[0].price - inter_buy.price  # First spread
        spread2_price = inter_sell.price - bought_trades[0].price  # Second spread
        combined_price = spread1_price + spread2_price
        
        # Check if combined price matches target (within small tolerance for decimal precision)
        return abs(combined_price - target_price) < Decimal('0.01')

    def _create_match_result_from_combo(self, trader_pair: List[Trade], exchange_combo: List[Trade]) -> MatchResult:
        """Create match result from validated combination."""
        # Use the first exchange trade as primary
        primary_exchange = exchange_combo[0]
        additional_exchange = exchange_combo[1:] if len(exchange_combo) > 1 else []
        
        # Use the first trader trade as primary
        primary_trader = trader_pair[0]
        additional_trader = trader_pair[1:] if len(trader_pair) > 1 else []
        
        match_id = f"multileg_spread_{primary_trader.trade_id}_{primary_exchange.trade_id}"
        
        matched_fields = self.get_universal_matched_fields([
            "product_name", "broker_group_id", "exch_clearing_acct_id"
        ])
        
        return MatchResult(
            match_id=match_id,
            match_type=MatchType.MULTILEG_SPREAD,
            confidence=self.confidence,
            trader_trade=primary_trader,
            exchange_trade=primary_exchange,
            additional_trader_trades=additional_trader,
            additional_exchange_trades=additional_exchange,
            matched_fields=matched_fields,
            tolerances_applied={},
            rule_order=self.rule_number
        )

    def _find_tier2_netting_combination(self, trader_pair: List[Trade], trader_spread_info: Dict, exchange_trades: List[Trade]) -> Optional[MatchResult]:
        """Tier 2: Find 6 exchange trades (4 months) forming multiple spreads."""
        target_sold_month = trader_spread_info['sold_month']
        target_bought_month = trader_spread_info['bought_month'] 
        target_price = trader_spread_info['spread_price']
        
        # Try all combinations of 6 exchange trades
        for combo in combinations(exchange_trades, 6):
            if self._validate_tier2_netting_pattern(combo, target_sold_month, target_bought_month, target_price):
                return self._create_match_result_from_combo(trader_pair, list(combo))
        
        return None

    def _validate_tier2_netting_pattern(self, exchange_combo: Tuple[Trade, ...], 
                                       target_sold_month: str, target_bought_month: str, target_price: Decimal) -> bool:
        """Tier 2: Check if 6 exchange trades (4 months) form consecutive spreads."""
        month_trades = self._group_trades_by_month(exchange_combo)
        
        # Validate basic structure: 4 months with target months present
        if not self._validate_tier2_structure(month_trades, target_sold_month, target_bought_month):
            return False
            
        # Sort months chronologically and validate pattern
        sorted_months = sorted(month_trades.keys(), key=lambda m: get_month_order_tuple(m))
        if not self._validate_tier2_month_pattern(month_trades, sorted_months, 
                                                 target_sold_month, target_bought_month):
            return False
            
        # Calculate and validate combined price
        combined_price = self._calculate_tier2_combined_price(month_trades, sorted_months)
        return abs(combined_price - target_price) < Decimal('0.01')

    def _group_trades_by_month(self, exchange_combo: Tuple[Trade, ...]) -> Dict[str, List[Trade]]:
        """Group trades by contract month."""
        month_trades = defaultdict(list)
        for trade in exchange_combo:
            month_trades[trade.contract_month].append(trade)
        return dict(month_trades)

    def _validate_tier2_structure(self, month_trades: Dict[str, List[Trade]], 
                                 target_sold_month: str, target_bought_month: str) -> bool:
        """Validate basic Tier 2 structure: 4 months with target months present."""
        if len(month_trades) != 4:
            return False
        months = set(month_trades.keys())
        return target_sold_month in months and target_bought_month in months

    def _validate_tier2_month_pattern(self, month_trades: Dict[str, List[Trade]], 
                                     sorted_months: List[str], target_sold_month: str, 
                                     target_bought_month: str) -> bool:
        """Validate Tier 2 month pattern: first=sell, last=buy, middle=buy+sell each."""
        if sorted_months[0] != target_sold_month or sorted_months[-1] != target_bought_month:
            return False
            
        for i, month in enumerate(sorted_months):
            trades = month_trades[month]
            if i == 0:  # First month: 1 sell
                if len(trades) != 1 or trades[0].buy_sell != 'S':
                    return False
            elif i == len(sorted_months) - 1:  # Last month: 1 buy
                if len(trades) != 1 or trades[0].buy_sell != 'B':
                    return False
            else:  # Intermediate months: 1 buy + 1 sell
                if len(trades) != 2:
                    return False
                buy_trades = [t for t in trades if t.buy_sell == 'B']
                sell_trades = [t for t in trades if t.buy_sell == 'S']
                if len(buy_trades) != 1 or len(sell_trades) != 1:
                    return False
        return True

    def _calculate_tier2_combined_price(self, month_trades: Dict[str, List[Trade]], 
                                       sorted_months: List[str]) -> Decimal:
        """Calculate combined spread price for consecutive spreads."""
        combined_price = Decimal('0')
        
        for i in range(len(sorted_months) - 1):
            current_month = sorted_months[i]
            next_month = sorted_months[i + 1]
            
            # Get sell trade from current month
            if i == 0:  # First month has only one trade (sell)
                sell_trade = month_trades[current_month][0]
            else:  # Intermediate months: find the sell trade
                sell_trade = next(t for t in month_trades[current_month] if t.buy_sell == 'S')
                
            # Get buy trade from next month
            if i == len(sorted_months) - 2:  # Last month has only one trade (buy)
                buy_trade = month_trades[next_month][0]
            else:  # Intermediate months: find the buy trade
                buy_trade = next(t for t in month_trades[next_month] if t.buy_sell == 'B')
            
            # Add this spread's contribution
            spread_price = sell_trade.price - buy_trade.price
            combined_price += spread_price
            
        return combined_price


    def _find_multileg_match(self, trader_pair: List[Trade], exchange_trades: List[Trade], 
                            pool_manager: UnmatchedPoolManager) -> Optional[MatchResult]:
        """Find multileg spread match by testing exchange trade combinations that net internally."""
        # Get trader spread info
        trader_spread_info = self._get_trader_spread_info(trader_pair)
        if not trader_spread_info:
            return None
        
        # Filter exchange trades to same product and broker details
        matching_exchange = [
            trade for trade in exchange_trades
            if (trade.product_name == trader_pair[0].product_name and
                trade.broker_group_id == trader_pair[0].broker_group_id and
                trade.exch_clearing_acct_id == trader_pair[0].exch_clearing_acct_id and
                self._get_quantity_for_grouping(trade, self.normalizer) == trader_spread_info['quantity'] and
                not pool_manager.is_trade_matched(trade))
        ]
        
        if len(matching_exchange) < 4:  # Need at least 4 exchange trades for multileg
            return None
            
        # Tier 1: Try 4-trade combinations first (3 months with perfect internal netting)
        logger.debug(f"Trying Tier 1 (4-trade) combinations for {len(matching_exchange)} exchange trades")
        match_result = self._find_tier1_netting_combination(trader_pair, trader_spread_info, matching_exchange)
        if match_result:
            logger.debug("Found Tier 1 multileg spread match")
            return match_result
            
        # Tier 2: Try 6-trade combinations (4 months with flexible netting)
        if len(matching_exchange) >= 6:
            logger.debug(f"Trying Tier 2 (6-trade) combinations for {len(matching_exchange)} exchange trades")
            match_result = self._find_tier2_netting_combination(trader_pair, trader_spread_info, matching_exchange)
            if match_result:
                logger.debug("Found Tier 2 multileg spread match")
                return match_result
        
        return None


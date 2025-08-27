"""Product spread matching implementation for Rule 3."""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
import logging
from collections import defaultdict

from ..models import SGXTrade, SGXMatchResult, SGXMatchType, SGXTradeSource
from ..core import SGXUnmatchedPool
from ..config import SGXConfigManager
from ..normalizers import SGXTradeNormalizer
from .multi_leg_base_matcher import MultiLegBaseMatcher

logger = logging.getLogger(__name__)


class ProductSpreadMatcher(MultiLegBaseMatcher):
    """Implements Rule 3: Product spread matching for SGX trades."""

    def __init__(self, config_manager: SGXConfigManager, normalizer: SGXTradeNormalizer):
        """Initialize the product spread matcher."""
        super().__init__(config_manager)
        self.normalizer = normalizer
        self.rule_number = 3
        self.confidence = config_manager.get_rule_confidence(self.rule_number)
        logger.info(f"Initialized ProductSpreadMatcher with {self.confidence}% confidence")

    def find_matches(self, pool_manager: SGXUnmatchedPool) -> List[SGXMatchResult]:
        """Find all product spread matches."""
        logger.info("Starting product spread matching (Rule 3)")
        matches = []
        
        trader_trades = pool_manager.get_unmatched_trader_trades()
        exchange_trades = pool_manager.get_unmatched_exchange_trades()

        # Find trader product spread pairs (marked with PS)
        trader_product_spread_pairs = self._find_trader_product_spread_pairs(trader_trades, pool_manager)
        
        # Find exchange product spread pairs using dealid grouping
        exchange_product_spread_pairs = self._find_exchange_product_spread_pairs(exchange_trades, pool_manager)
        
        logger.debug(f"Found {len(trader_product_spread_pairs)} trader product spread pairs")
        logger.debug(f"Found {len(exchange_product_spread_pairs)} exchange product spread pairs")

        # Match trader product spread pairs with exchange product spread pairs
        for trader_pair in trader_product_spread_pairs:
            # Skip if any trader trade is already matched
            if any(not pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.TRADER) for trade in trader_pair):
                continue

            match_result = self._match_product_spread_pair(trader_pair, exchange_product_spread_pairs, pool_manager)
            if match_result:
                matches.append(match_result)
                
                # Mark all trades as matched
                for trade in trader_pair:
                    pool_manager.mark_as_matched(trade.trade_id, SGXTradeSource.TRADER, "product_spread")
                
                for trade in [match_result.exchange_trade] + match_result.additional_exchange_trades:
                    pool_manager.mark_as_matched(trade.trade_id, SGXTradeSource.EXCHANGE, "product_spread")
                
                # Record in audit trail
                pool_manager.record_match(
                    match_result.trader_trade.trade_id,
                    match_result.exchange_trade.trade_id,
                    match_result.match_type.value
                )
                
                logger.debug(f"Created product spread match: {match_result.match_id}")

        logger.info(f"Found {len(matches)} product spread matches")
        return matches

    def _find_trader_product_spread_pairs(self, trader_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find trader product spread pairs with PS spread indicators or identical non-zero spread prices."""
        product_spread_pairs = []
        
        # Log all PS trades to see what we have
        ps_trades = [trade for trade in trader_trades if trade.spread and 'PS' in str(trade.spread).upper()]
        logger.debug(f"Total PS trades in trader_trades: {len(ps_trades)}")
        for trade in ps_trades:
            logger.debug(f"PS trade: {trade.product_name}/{trade.buy_sell}, price={trade.price}, contract_month={trade.contract_month}, unmatched={pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.TRADER)}")
        
        # Group trades by contract month, quantity, and universal fields
        trade_groups: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        for trade in trader_trades:
            if pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.TRADER):
                key = self.create_universal_signature(trade, [trade.contract_month, trade.quantity_units])
                trade_groups[key].append(trade)
        
        logger.debug(f"Trader product spread groups: {len(trade_groups)}")
        
        # Find pairs within each group
        for trades in trade_groups.values():
            logger.debug(f"Checking trader group with {len(trades)} trades")
            if len(trades) >= 1:
                # Log details of all trades in this group
                for idx, trade in enumerate(trades):
                    logger.debug(f"  Trade {idx}: {trade.product_name}/{trade.buy_sell}, price={trade.price}, spread={trade.spread}, contract_month={trade.contract_month}, quantity={trade.quantity_units}")
            
            if len(trades) >= 2:
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        logger.debug(f"Checking trader pair: {trades[i].product_name}/{trades[i].buy_sell} + {trades[j].product_name}/{trades[j].buy_sell}")
                        if self._is_trader_product_spread_pair(trades[i], trades[j]):
                            logger.debug(f"Found trader product spread pair: {trades[i].trade_id} + {trades[j].trade_id}")
                            product_spread_pairs.append([trades[i], trades[j]])
        
        return product_spread_pairs

    def _is_trader_product_spread_pair(self, trade1: SGXTrade, trade2: SGXTrade) -> bool:
        """Check if two trader trades form a product spread pair.
        
        Supports two patterns:
        1. PS indicator pattern (spread column contains 'PS')
        2. Identical spread price pattern (both trades have same non-zero price, different products)
        """
        # Basic requirements: opposite B/S directions and different products
        if (trade1.buy_sell == trade2.buy_sell or 
            trade1.product_name == trade2.product_name):
            return False
        
        # Must have same contract month
        if trade1.contract_month != trade2.contract_month:
            return False
        
        # Pattern 1: Look for PS spread indicators in trader data
        has_ps_indicator = (
            (trade1.spread and 'PS' in str(trade1.spread).upper()) and
            (trade2.spread and 'PS' in str(trade2.spread).upper())
        )
        
        # Pattern 2: Both trades have identical non-zero spread price (product spread pattern)
        has_identical_spread_price = (
            trade1.price != 0 and 
            trade2.price != 0 and 
            trade1.price == trade2.price
        )
        
        return has_ps_indicator or (has_identical_spread_price and trade1.product_name != trade2.product_name)

    def _find_exchange_product_spread_pairs(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find exchange product spread pairs using dealid grouping."""
        product_spread_pairs = []
        
        # Group trades by dealid
        dealid_groups: Dict[str, List[SGXTrade]] = defaultdict(list)
        for trade in exchange_trades:
            if not pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.EXCHANGE):
                continue
                
            # SGX trades have deal_id field directly
            dealid = trade.deal_id
            tradeid = trade.trade_id
            
            # Only include trades that have both dealid and tradeid
            if dealid is not None and tradeid and str(dealid).strip() and str(tradeid).strip():
                dealid_str = str(dealid).strip()
                if dealid_str.lower() not in ['nan', 'none', '']:
                    dealid_groups[dealid_str].append(trade)
        
        # Find valid product spread pairs within each dealid group
        for dealid_str, trades_in_group in dealid_groups.items():
            # A product spread group must have exactly 2 legs for SGX
            if len(trades_in_group) == 2:
                trade1, trade2 = trades_in_group
                
                # Extract tradeids for comparison - must be different
                tradeid1 = str(trade1.trade_id).strip()
                tradeid2 = str(trade2.trade_id).strip()
                
                if tradeid1 != tradeid2 and tradeid1 and tradeid2:
                    # Validate product spread characteristics
                    if self._validate_exchange_product_spread_pair(trade1, trade2):
                        product_spread_pairs.append([trade1, trade2])
                        logger.debug(f"Found dealid product spread pair: {tradeid1}/{tradeid2} (dealid: {dealid_str})")
            elif len(trades_in_group) > 2:
                # Multiple legs - try to find all valid pairs
                for i in range(len(trades_in_group)):
                    for j in range(i + 1, len(trades_in_group)):
                        trade1, trade2 = trades_in_group[i], trades_in_group[j]
                        
                        # Must have different tradeids
                        tradeid1 = str(trade1.trade_id).strip()
                        tradeid2 = str(trade2.trade_id).strip()
                        
                        if tradeid1 != tradeid2 and tradeid1 and tradeid2:
                            if self._validate_exchange_product_spread_pair(trade1, trade2):
                                product_spread_pairs.append([trade1, trade2])
                                logger.debug(f"Found dealid product spread pair: {tradeid1}/{tradeid2} (dealid: {dealid_str})")
        
        return product_spread_pairs

    def _validate_exchange_product_spread_pair(self, trade1: SGXTrade, trade2: SGXTrade) -> bool:
        """Validate that two exchange trades form a valid product spread pair."""
        # Must have different products
        if trade1.product_name == trade2.product_name:
            return False
        
        # Must have same contract month
        if trade1.contract_month != trade2.contract_month:
            return False
        
        # Must have same quantity
        if trade1.quantity_units != trade2.quantity_units:
            return False
        
        # Must have opposite B/S directions
        if trade1.buy_sell == trade2.buy_sell:
            return False
        
        # Universal field validation
        return self.validate_universal_fields(trade1, trade2)

    def _match_product_spread_pair(
        self, 
        trader_pair: List[SGXTrade], 
        exchange_product_spread_pairs: List[List[SGXTrade]], 
        pool_manager: SGXUnmatchedPool
    ) -> Optional[SGXMatchResult]:
        """Match a trader product spread pair with exchange product spread pairs."""
        if len(trader_pair) != 2:
            return None
        
        # Try to match with each exchange product spread pair
        for exchange_pair in exchange_product_spread_pairs:
            if len(exchange_pair) != 2:
                continue
                
            # Skip if either exchange trade is already matched
            if any(not pool_manager.is_unmatched(trade.trade_id, SGXTradeSource.EXCHANGE) 
                   for trade in exchange_pair):
                continue
            
            # Validate this is a valid product spread match
            if self._validate_product_spread_match(trader_pair, exchange_pair):
                return self._create_product_spread_match_result(trader_pair, exchange_pair)
        
        return None

    def _validate_product_spread_match(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> bool:
        """Validate that trader and exchange trades form a valid product spread match."""
        if len(trader_trades) != 2 or len(exchange_trades) != 2:
            logger.debug("Product spread validation failed: incorrect number of trades")
            return False

        trader_trade1, trader_trade2 = trader_trades
        exchange_trade1, exchange_trade2 = exchange_trades

        # Validate exchange trades form a valid product spread pair
        if not self._validate_exchange_product_spread_pair(exchange_trade1, exchange_trade2):
            logger.debug("Product spread validation failed: invalid exchange product spread pair")
            return False

        # Validate products match between trader and exchange
        trader_products = {trader_trade1.product_name, trader_trade2.product_name}
        exchange_products = {exchange_trade1.product_name, exchange_trade2.product_name}
        if trader_products != exchange_products:
            logger.debug(f"Product spread validation failed: product mismatch - trader: {trader_products}, exchange: {exchange_products}")
            return False

        # Validate contract months match
        if (trader_trade1.contract_month != exchange_trade1.contract_month or
            trader_trade1.contract_month != exchange_trade2.contract_month):
            logger.debug(f"Product spread validation failed: contract month mismatch - trader: {trader_trade1.contract_month}, exchange: {exchange_trade1.contract_month}/{exchange_trade2.contract_month}")
            return False

        # Validate quantities match
        if (trader_trade1.quantity_units != exchange_trade1.quantity_units or
            trader_trade1.quantity_units != exchange_trade2.quantity_units):
            logger.debug(f"Product spread validation failed: quantity mismatch - trader: {trader_trade1.quantity_units}, exchange: {exchange_trade1.quantity_units}/{exchange_trade2.quantity_units}")
            return False

        # Validate B/S directions and product spread prices
        directions_valid = self._validate_product_spread_directions(trader_trades, exchange_trades)
        prices_valid = self._validate_product_spread_prices(trader_trades, exchange_trades)
        
        if not directions_valid:
            logger.debug("Product spread validation failed: B/S directions mismatch")
        if not prices_valid:
            logger.debug("Product spread validation failed: price calculation mismatch")
            
        return directions_valid and prices_valid

    def _validate_product_spread_directions(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> bool:
        """Validate that B/S directions match exactly between trader and exchange product spreads.
        
        Each product must have the same direction in both trader and exchange data:
        - If trader has M65(B) + FE(S), exchange must have M65(B) + FE(S)
        - Directions must match by product for a valid product spread match
        """
        # Create product->direction mappings
        trader_product_bs = {
            trade.product_name: trade.buy_sell for trade in trader_trades
        }
        exchange_product_bs = {
            trade.product_name: trade.buy_sell for trade in exchange_trades
        }
        
        # Both sides must have one B and one S
        trader_directions = set(trader_product_bs.values())
        exchange_directions = set(exchange_product_bs.values())
        expected_directions = {'B', 'S'}
        
        if trader_directions != expected_directions or exchange_directions != expected_directions:
            return False
        
        # Validate that each product has matching B/S direction between trader and exchange
        return all(
            product in exchange_product_bs
            and trader_product_bs[product] == exchange_product_bs[product]
            for product in trader_product_bs
        )

    def _validate_product_spread_prices(
        self, trader_trades: List[SGXTrade], exchange_trades: List[SGXTrade]
    ) -> bool:
        """Validate product spread price calculation between trader and exchange trades."""
        # Get trader spread price (should be same for both legs)
        trader_spread_price = trader_trades[0].price

        # Calculate exchange product spread price (M65 - FE convention)
        # Find M65 and FE prices from exchange trades
        m65_price = None
        fe_price = None
        
        for trade in exchange_trades:
            if trade.product_name == "M65":
                m65_price = trade.price
            elif trade.product_name == "FE":
                fe_price = trade.price
        
        if m65_price is None or fe_price is None:
            # Handle other product pairs - use alphabetical order for consistency
            sorted_trades = sorted(exchange_trades, key=lambda t: t.product_name)
            exchange_spread_price = sorted_trades[1].price - sorted_trades[0].price
        else:
            # M65 - FE calculation
            exchange_spread_price = m65_price - fe_price

        return trader_spread_price == exchange_spread_price

    def _create_product_spread_match_result(
        self,
        trader_trades: List[SGXTrade],
        exchange_trades: List[SGXTrade],
    ) -> SGXMatchResult:
        """Create SGXMatchResult for product spread match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_names",
            "contract_month", 
            "quantity_units",
            "product_spread_price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        return SGXMatchResult(
            match_id=self._generate_match_id(),
            match_type=SGXMatchType.PRODUCT_SPREAD,
            confidence=self.confidence,
            trader_trade=trader_trades[0],
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:],
        )

    def _generate_match_id(self) -> str:
        """Generate unique match ID for product spread matches."""
        import uuid
        prefix = self.config_manager.get_match_id_prefix()
        uuid_suffix = uuid.uuid4().hex[:6]
        return f"{prefix}_PRODUCT_SPREAD_{self.rule_number}_{uuid_suffix}"

    def get_rule_info(self) -> dict:
        """Get information about this matching rule."""
        return {
            "rule_number": self.rule_number,
            "rule_name": "Product Spread Match",
            "match_type": SGXMatchType.PRODUCT_SPREAD.value,
            "confidence": float(self.confidence),
            "description": "Matches product spreads where trader shows calculated spread price for different products but exchange shows individual legs",
            "requirements": [
                "Both sources must have 2 trades each (different products)",
                "Same contract month and quantity for all trades",
                "Different products for each leg (e.g., M65 and FE)",
                "Opposite B/S directions for each leg",
                "Price calculation must match (M65 - FE = spread price)",
                "Trader trades must have PS (Product Spread) indicator",
                "Universal fields must match (brokergroupid, exchclearingacctid)",
            ],
        }
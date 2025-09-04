"""Product spread matching implementation for Rule 3."""

from typing import List, Optional, Dict, Tuple
import logging
from collections import defaultdict
from decimal import Decimal

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

        # Tier 1 & 2: Find trader product spread pairs (with and without PS)
        trader_product_spread_pairs = self._find_trader_product_spread_pairs(trader_trades, pool_manager)
        
        # Tier 1 & 2: Find exchange product spread pairs using dealid grouping
        exchange_product_spread_pairs = self._find_exchange_product_spread_pairs(exchange_trades, pool_manager)
        
        logger.debug(f"Found {len(trader_product_spread_pairs)} trader product spread pairs")
        logger.debug(f"Found {len(exchange_product_spread_pairs)} exchange product spread pairs")

        # Process Tier 1 & 2: Trader spread pairs vs Exchange spread pairs (2-to-2)
        for trader_pair_with_tier in trader_product_spread_pairs:
            # Extract trades and confidence tier
            trader_trade1, trader_trade2, confidence_tier = trader_pair_with_tier
            trader_trades_list = [trader_trade1, trader_trade2]  # Convert to list
            
            # Skip if any trader trade is already matched
            if any(not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER) for trade in trader_trades_list):
                continue

            match_result = self._match_product_spread_pair(trader_trades_list, exchange_product_spread_pairs, pool_manager, confidence_tier)
            if match_result:
                matches.append(match_result)
                
                # Mark all trades as matched
                for trade in trader_trades_list:
                    pool_manager.mark_as_matched(trade.internal_trade_id, SGXTradeSource.TRADER, "product_spread")
                
                for trade in [match_result.exchange_trade] + match_result.additional_exchange_trades:
                    pool_manager.mark_as_matched(trade.internal_trade_id, SGXTradeSource.EXCHANGE, "product_spread")
                
                # Record in audit trail
                pool_manager.record_match(
                    match_result.trader_trade.internal_trade_id,
                    match_result.exchange_trade.internal_trade_id,
                    match_result.match_type.value
                )
                
                logger.debug(f"Created product spread match: {match_result.match_id}")

        # Tier 3: Process hyphenated exchange spreads vs trader pairs (1-to-2)
        hyphenated_matches = self._find_hyphenated_exchange_matches(trader_trades, exchange_trades, pool_manager)
        matches.extend(hyphenated_matches)

        logger.info(f"Found {len(matches)} total product spread matches")
        return matches

    def _find_trader_product_spread_pairs(self, trader_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[Tuple[SGXTrade, SGXTrade, int]]:
        """Find trader product spread pairs with PS spread indicators or identical non-zero spread prices."""
        product_spread_pairs = []
        
        # Log all PS trades to see what we have
        ps_trades = [trade for trade in trader_trades if trade.spread and 'PS' in str(trade.spread).upper()]
        logger.debug(f"Total PS trades in trader_trades: {len(ps_trades)}")
        for trade in ps_trades:
            logger.debug(f"PS trade: {trade.product_name}/{trade.buy_sell}, price={trade.price}, contract_month={trade.contract_month}, unmatched={pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER)}")
        
        # Group trades by contract month, quantity, and universal fields
        trade_groups: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        for trade in trader_trades:
            if pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER):
                key = self.create_universal_signature(trade, [trade.contract_month, trade.quantityunit])
                trade_groups[key].append(trade)
        
        logger.debug(f"Trader product spread groups: {len(trade_groups)}")
        
        # Find pairs within each group
        for trades in trade_groups.values():
            logger.debug(f"Checking trader group with {len(trades)} trades")
            if len(trades) >= 1:
                # Log details of all trades in this group
                for idx, trade in enumerate(trades):
                    logger.debug(f"  Trade {idx}: {trade.product_name}/{trade.buy_sell}, price={trade.price}, spread={trade.spread}, contract_month={trade.contract_month}, quantity={trade.quantityunit}")
            
            if len(trades) >= 2:
                for i in range(len(trades)):
                    for j in range(i + 1, len(trades)):
                        logger.debug(f"Checking trader pair: {trades[i].product_name}/{trades[i].buy_sell} + {trades[j].product_name}/{trades[j].buy_sell}")
                        is_match, confidence_tier = self._is_trader_product_spread_pair(trades[i], trades[j])
                        if is_match:
                            tier_desc = "PS required" if confidence_tier == 1 else "no PS required"
                            logger.debug(f"Found trader product spread pair (Tier {confidence_tier} - {tier_desc}): {trades[i].internal_trade_id} + {trades[j].internal_trade_id}")
                            # Store trades with confidence tier information
                            product_spread_pairs.append((trades[i], trades[j], confidence_tier))
        
        return product_spread_pairs

    def _is_trader_product_spread_pair(self, trade1: SGXTrade, trade2: SGXTrade) -> Tuple[bool, int]:
        """Check if two trader trades form a product spread pair.
        
        Returns tuple of (is_match, confidence_tier):
        - Tier 1 (95%): PS indicator pattern (spread column contains 'PS') 
        - Tier 2 (92%): No PS required, just identical spread price + different products
        """
        # Basic requirements: opposite B/S directions and different products
        if (trade1.buy_sell == trade2.buy_sell or 
            trade1.product_name == trade2.product_name):
            return False, 0
        
        # Must have same contract month
        if trade1.contract_month != trade2.contract_month:
            return False, 0
        
        # Tier 1: PS indicator pattern (highest confidence)
        has_ps_indicator = (
            (trade1.spread and 'PS' in str(trade1.spread).upper()) and
            (trade2.spread and 'PS' in str(trade2.spread).upper())
        )
        
        if has_ps_indicator:
            return True, 1  # Tier 1 - 95% confidence
        
        # Tier 2: Identical spread price pattern (lower confidence, no PS required)
        has_identical_spread_price = (
            trade1.price != 0 and 
            trade2.price != 0 and 
            trade1.price == trade2.price
        )
        
        if has_identical_spread_price and trade1.product_name != trade2.product_name:
            return True, 2  # Tier 2 - 92% confidence
        
        return False, 0

    def _find_exchange_product_spread_pairs(self, exchange_trades: List[SGXTrade], pool_manager: SGXUnmatchedPool) -> List[List[SGXTrade]]:
        """Find exchange product spread pairs using dealid grouping."""
        product_spread_pairs = []
        
        # Group trades by dealid
        dealid_groups: Dict[str, List[SGXTrade]] = defaultdict(list)
        for trade in exchange_trades:
            if not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.EXCHANGE):
                continue
                
            # SGX trades have deal_id field directly
            dealid = trade.deal_id
            tradeid = trade.internal_trade_id
            
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
                tradeid1 = str(trade1.internal_trade_id).strip()
                tradeid2 = str(trade2.internal_trade_id).strip()
                
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
                        tradeid1 = str(trade1.internal_trade_id).strip()
                        tradeid2 = str(trade2.internal_trade_id).strip()
                        
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
        if trade1.quantityunit != trade2.quantityunit:
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
        pool_manager: SGXUnmatchedPool,
        confidence_tier: int = 1
    ) -> Optional[SGXMatchResult]:
        """Match a trader product spread pair with exchange product spread pairs."""
        if len(trader_pair) != 2:
            return None
        
        # Try to match with each exchange product spread pair
        for exchange_pair in exchange_product_spread_pairs:
            if len(exchange_pair) != 2:
                continue
                
            # Skip if either exchange trade is already matched
            if any(not pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.EXCHANGE) 
                   for trade in exchange_pair):
                continue
            
            # Validate this is a valid product spread match
            if self._validate_product_spread_match(trader_pair, exchange_pair):
                return self._create_product_spread_match_result(trader_pair, exchange_pair, confidence_tier)
        
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
        if (trader_trade1.quantityunit != exchange_trade1.quantityunit or
            trader_trade1.quantityunit != exchange_trade2.quantityunit):
            logger.debug(f"Product spread validation failed: quantity mismatch - trader: {trader_trade1.quantityunit}, exchange: {exchange_trade1.quantityunit}/{exchange_trade2.quantityunit}")
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
        confidence_tier: int = 1
    ) -> SGXMatchResult:
        """Create SGXMatchResult for product spread match."""
        # Rule-specific matched fields
        rule_specific_fields = [
            "product_names",
            "contract_month", 
            "quantityunit",
            "product_spread_price_calculation",
        ]

        # Get complete matched fields with universal fields
        matched_fields = self.get_universal_matched_fields(rule_specific_fields)

        # Calculate confidence using tier-based adjustments
        tier_confidence = self._calculate_tier_confidence(confidence_tier)

        return SGXMatchResult(
            match_id=self.generate_match_id(self.rule_number),
            match_type=SGXMatchType.PRODUCT_SPREAD,
            confidence=tier_confidence,
            trader_trade=trader_trades[0],
            exchange_trade=exchange_trades[0],
            matched_fields=matched_fields,
            rule_order=self.rule_number,
            additional_trader_trades=trader_trades[1:],
            additional_exchange_trades=exchange_trades[1:],
        )

    def _calculate_tier_confidence(self, confidence_tier: int) -> Decimal:
        """Calculate confidence level based on tier using configuration-driven approach.
        
        Args:
            confidence_tier: The confidence tier (1, 2, 3)
            
        Returns:
            Calculated confidence as Decimal
        """
        # Tier configuration: (description, confidence_adjustment)
        # Updated adjustments for 100% base confidence to achieve target confidences
        tier_config = {
            1: ("PS required", Decimal("5.0")),          # 100% - 5% = 95%
            2: ("no PS required", Decimal("8.0")),       # 100% - 8% = 92%
            3: ("hyphenated exchange", Decimal("10.0")), # 100% - 10% = 90%
        }
        
        base_confidence = self.confidence  # From config manager (100%)
        
        if confidence_tier in tier_config:
            description, adjustment = tier_config[confidence_tier]
            tier_confidence = base_confidence - adjustment
            
            # Ensure confidence doesn't go below 0
            tier_confidence = max(tier_confidence, Decimal("0"))
            
            logger.debug(f"Tier {confidence_tier} ({description}): {base_confidence} - {adjustment} = {tier_confidence}%")
        else:
            # Default to base confidence for unknown tiers
            tier_confidence = base_confidence
            logger.warning(f"Unknown confidence tier {confidence_tier}, using base confidence {base_confidence}%")
        
        return tier_confidence


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
                "TIER 1 (95%): Trader trades must have PS (Product Spread) indicator",
                "TIER 2 (92%): No PS required, just identical spread price + different products",
                "TIER 3 (90%): Hyphenated exchange spread vs trader pair (1-to-2 match)",
                "Universal fields must match (brokergroupid, exchclearingacctid)",
            ],
        }

    def _find_hyphenated_exchange_matches(
        self, 
        trader_trades: List[SGXTrade], 
        exchange_trades: List[SGXTrade], 
        pool_manager: SGXUnmatchedPool
    ) -> List[SGXMatchResult]:
        """Find Tier 3 matches: hyphenated exchange spreads vs trader pairs (1-to-2)."""
        matches: List[SGXMatchResult] = []
        
        # Filter exchange trades to only hyphenated products
        hyphenated_trades = [
            t for t in exchange_trades 
            if pool_manager.is_unmatched(t.internal_trade_id, SGXTradeSource.EXCHANGE) and 
               "-" in t.product_name and self._parse_hyphenated_product(t.product_name) is not None
        ]
        
        if not hyphenated_trades:
            logger.debug("No hyphenated exchange products found for Tier 3")
            return matches
        
        logger.debug(f"Processing {len(hyphenated_trades)} hyphenated exchange products for Tier 3")
        
        # Create index of trader trades by signature for efficient lookup
        trader_index = self._create_trader_index_for_hyphenated(trader_trades, pool_manager)
        
        for exchange_trade in hyphenated_trades:
            match = self._find_hyphenated_product_spread_match(exchange_trade, trader_index, pool_manager)
            if match:
                matches.append(match)
                
                # Mark all trades as matched
                pool_manager.mark_as_matched(exchange_trade.internal_trade_id, SGXTradeSource.EXCHANGE, "product_spread")
                for trader_trade in [match.trader_trade] + match.additional_trader_trades:
                    pool_manager.mark_as_matched(trader_trade.internal_trade_id, SGXTradeSource.TRADER, "product_spread")
                
                # Record in audit trail
                pool_manager.record_match(
                    match.trader_trade.internal_trade_id,
                    match.exchange_trade.internal_trade_id,
                    match.match_type.value
                )
                
                logger.debug(f"Found Tier 3 hyphenated product spread match: {match.match_id}")
        
        logger.debug(f"Found {len(matches)} Tier 3 hyphenated matches")
        return matches

    def _parse_hyphenated_product(self, product_name: str) -> Optional[Tuple[str, str]]:
        """Parse hyphenated product name into component products.
        
        Args:
            product_name: Product name that may contain hyphen (e.g., "bz-naphtha japan")
            
        Returns:
            Tuple of (first_product, second_product) or None if not parseable
        """
        if "-" not in product_name:
            return None
            
        parts = product_name.split("-", 1)  # Split on first hyphen only
        if len(parts) != 2:
            return None
            
        first_product = parts[0].strip()
        second_product = parts[1].strip()
        
        if not first_product or not second_product:
            return None
            
        return (first_product, second_product)

    def _create_trader_index_for_hyphenated(
        self, 
        trader_trades: List[SGXTrade], 
        pool_manager: SGXUnmatchedPool
    ) -> Dict[Tuple, List[SGXTrade]]:
        """Create index of trader trades for hyphenated exchange matching."""
        index: Dict[Tuple, List[SGXTrade]] = defaultdict(list)
        
        for trade in trader_trades:
            if pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER):
                # Index by contract month, quantity, and universal fields (same as regular matching)
                signature = self.create_universal_signature(trade, [trade.contract_month, trade.quantityunit])
                index[signature].append(trade)
        
        logger.debug(f"Created trader index for hyphenated matching with {len(index)} signatures")
        return index

    def _find_hyphenated_product_spread_match(
        self,
        exchange_trade: SGXTrade,
        trader_index: Dict[Tuple, List[SGXTrade]],
        pool_manager: SGXUnmatchedPool
    ) -> Optional[SGXMatchResult]:
        """Find hyphenated product spread match for an exchange trade.
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            trader_index: Index of trader trades by signature  
            pool_manager: Pool manager for validation
            
        Returns:
            SGXMatchResult if match found, None otherwise
        """
        # Parse the hyphenated product
        components = self._parse_hyphenated_product(exchange_trade.product_name)
        if not components:
            return None
            
        first_product, second_product = components
        logger.debug(f"Parsed '{exchange_trade.product_name}' into: '{first_product}' + '{second_product}'")
        
        # Create signature for finding matching trader trades
        signature = self.create_universal_signature(exchange_trade, [exchange_trade.contract_month, exchange_trade.quantityunit])
        
        if signature not in trader_index:
            logger.debug(f"No trader trades found for signature: {signature}")
            return None
        
        # Find matching component trades in trader data
        matching_trades = trader_index[signature]
        logger.debug(f"Found {len(matching_trades)} potential trader trades for signature")
        
        # Look for two trades: one for each component product
        first_trade = None
        second_trade = None
        
        for trade in matching_trades:
            if pool_manager.is_unmatched(trade.internal_trade_id, SGXTradeSource.TRADER):
                logger.debug(f"Checking trader trade: {trade.internal_trade_id} - {trade.product_name} {trade.price} {trade.buy_sell}")
                
                if trade.product_name == first_product:
                    first_trade = trade
                    logger.debug(f"Found first product match: {trade.internal_trade_id}")
                elif trade.product_name == second_product:
                    second_trade = trade
                    logger.debug(f"Found second product match: {trade.internal_trade_id}")
        
        # Must have both component trades
        if not first_trade or not second_trade:
            logger.debug(f"Missing component trades - first: {first_trade is not None}, second: {second_trade is not None}")
            return None
        
        # Validate the hyphenated spread match
        if not self._validate_hyphenated_spread_match(exchange_trade, first_trade, second_trade):
            logger.debug("❌ Hyphenated spread validation failed")
            return None
        
        logger.debug("✅ Hyphenated spread validation passed")
        
        # Create match result with Tier 3 confidence
        return self._create_product_spread_match_result([first_trade, second_trade], [exchange_trade], confidence_tier=3)

    def _validate_hyphenated_spread_match(
        self,
        exchange_trade: SGXTrade,
        first_trader_trade: SGXTrade,
        second_trader_trade: SGXTrade
    ) -> bool:
        """Validate that trades can form a hyphenated product spread match.
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade
            second_trader_trade: Second component trader trade
            
        Returns:
            True if valid hyphenated spread match, False otherwise
        """
        try:
            # Check that trader trades have opposite B/S directions
            if first_trader_trade.buy_sell == second_trader_trade.buy_sell:
                logger.debug(f"❌ Trader trades must have opposite B/S directions: {first_trader_trade.buy_sell}/{second_trader_trade.buy_sell}")
                return False
            
            # Validate B/S direction logic for hyphenated products
            if not self._validate_hyphenated_direction_logic(exchange_trade, first_trader_trade, second_trader_trade):
                logger.debug("❌ Hyphenated direction logic validation failed")
                return False
            
            # Validate price matching (exchange price should match both trader prices)
            if (exchange_trade.price != first_trader_trade.price or 
                exchange_trade.price != second_trader_trade.price):
                logger.debug(f"❌ Price mismatch: exchange={exchange_trade.price}, trader1={first_trader_trade.price}, trader2={second_trader_trade.price}")
                return False
            
            logger.debug("✅ All hyphenated spread validations passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating hyphenated spread match: {e}")
            return False

    def _validate_hyphenated_direction_logic(
        self,
        exchange_trade: SGXTrade,
        first_trader_trade: SGXTrade,
        second_trader_trade: SGXTrade
    ) -> bool:
        """Validate B/S direction logic for hyphenated products.
        
        For hyphenated products, the exchange B/S determines the leg directions:
        - Exchange "B" on "X-Y" means Buy X, Sell Y
        - Exchange "S" on "X-Y" means Sell X, Buy Y
        
        Args:
            exchange_trade: Exchange trade with hyphenated product
            first_trader_trade: First component trader trade  
            second_trader_trade: Second component trader trade
            
        Returns:
            True if direction logic is valid, False otherwise
        """
        components = self._parse_hyphenated_product(exchange_trade.product_name)
        if not components:
            return False
            
        first_product, second_product = components
        
        # Determine which trader trade corresponds to which product
        if first_trader_trade.product_name == first_product and second_trader_trade.product_name == second_product:
            first_leg_trade = first_trader_trade
            second_leg_trade = second_trader_trade
        elif first_trader_trade.product_name == second_product and second_trader_trade.product_name == first_product:
            first_leg_trade = second_trader_trade
            second_leg_trade = first_trader_trade
        else:
            logger.debug("❌ Product name mismatch in trader trades")
            return False
        
        # Apply hyphenated direction logic
        if exchange_trade.buy_sell == "B":
            # Buy "X-Y" = Buy X, Sell Y
            expected_first_direction = "B"
            expected_second_direction = "S"
        else:  # exchange_trade.buy_sell == "S"
            # Sell "X-Y" = Sell X, Buy Y
            expected_first_direction = "S"  
            expected_second_direction = "B"
        
        actual_first_direction = first_leg_trade.buy_sell
        actual_second_direction = second_leg_trade.buy_sell
        
        is_valid = (actual_first_direction == expected_first_direction and 
                   actual_second_direction == expected_second_direction)
        
        if not is_valid:
            logger.debug(f"❌ Direction logic failed: exchange {exchange_trade.buy_sell} on '{exchange_trade.product_name}' "
                        f"expects ({expected_first_direction}/{expected_second_direction}) "
                        f"but got ({actual_first_direction}/{actual_second_direction})")
        
        return is_valid

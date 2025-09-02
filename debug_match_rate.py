#!/usr/bin/env python3
"""Debug script to compare ICE direct vs unified system match rate calculation."""

import sys
from pathlib import Path
from decimal import Decimal

# Add source directory to path
sys.path.append('src')

from ice_match.loaders.csv_loader import CSVTradeLoader
from ice_match.config import ConfigManager
from ice_match.normalizers import TradeNormalizer
from ice_match.core import UnmatchedPoolManager
from ice_match.matchers import (
    ExactMatcher, SpreadMatcher, CrackMatcher, ComplexCrackMatcher,
    ProductSpreadMatcher, AggregationMatcher, AggregatedComplexCrackMatcher,
    AggregatedSpreadMatcher, MultilegSpreadMatcher, AggregatedCrackMatcher,
    ComplexCrackRollMatcher, AggregatedProductSpreadMatcher
)

def debug_ice_calculation():
    """Debug the ICE system calculation using the unified data."""
    
    # Load the unified data
    trader_csv = Path("src/unified_recon/data/sourceTraders.csv")
    exchange_csv = Path("src/unified_recon/data/sourceExchange.csv")
    
    print("🔍 DEBUG: ICE Match Rate Calculation")
    print("=" * 50)
    
    # Set up ICE system components
    config_manager = ConfigManager()
    normalizer = TradeNormalizer(config_manager)
    loader = CSVTradeLoader(normalizer)
    
    # Load data using ICE system's loader
    trader_trades = loader.load_trader_csv(trader_csv)
    exchange_trades = loader.load_exchange_csv(exchange_csv)
    
    print("📊 Data loaded:")
    print(f"   Trader trades: {len(trader_trades)}")
    print(f"   Exchange trades: {len(exchange_trades)}")
    
    # Create pool manager
    pool_manager = UnmatchedPoolManager(trader_trades, exchange_trades)
    
    # Get initial statistics
    initial_stats = pool_manager.get_statistics()
    print("\n📈 Initial pool statistics:")
    print(f"   Trader original: {initial_stats['original']['trader']}")
    print(f"   Exchange original: {initial_stats['original']['exchange']}")
    print(f"   Initial match rates: {initial_stats['match_rates']}")
    
    # Process through all rules (same as unified system)
    processing_order = config_manager.get_processing_order()
    
    # Create matcher instances
    matchers = {
        1: ExactMatcher(config_manager),
        2: SpreadMatcher(config_manager, normalizer), 
        3: CrackMatcher(config_manager, normalizer),
        4: ComplexCrackMatcher(config_manager, normalizer),
        5: ProductSpreadMatcher(config_manager, normalizer),
        6: AggregationMatcher(config_manager),
        7: AggregatedComplexCrackMatcher(config_manager, normalizer),
        8: AggregatedSpreadMatcher(config_manager, normalizer),
        9: MultilegSpreadMatcher(config_manager, normalizer),
        10: AggregatedCrackMatcher(config_manager, normalizer),
        11: ComplexCrackRollMatcher(config_manager, normalizer),
        12: AggregatedProductSpreadMatcher(config_manager, normalizer)
    }
    
    # Process through all rules in sequence
    all_matches = []
    for rule_num in processing_order:
        if rule_num in matchers:
            matcher = matchers[rule_num]
            rule_matches = matcher.find_matches(pool_manager)
            all_matches.extend(rule_matches)
            print(f"   Rule {rule_num}: {len(rule_matches)} matches")
    
    # Get final statistics
    final_stats = pool_manager.get_statistics()
    print("\n🎯 Final pool statistics:")
    print(f"   Total matches: {len(all_matches)}")
    print(f"   Trader matched: {final_stats['matched']['trader']}")
    print(f"   Exchange matched: {final_stats['matched']['exchange']}")
    print(f"   Trader unmatched: {final_stats['unmatched']['trader']}")
    print(f"   Exchange unmatched: {final_stats['unmatched']['exchange']}")
    print(f"   Match rates: {final_stats['match_rates']}")
    
    # Manual calculation
    trader_match_rate = float(final_stats['match_rates']['trader'].replace('%', ''))
    exchange_match_rate = float(final_stats['match_rates']['exchange'].replace('%', ''))
    overall_calculated = (Decimal(str(trader_match_rate)) * Decimal('0.5') + 
                         Decimal(str(exchange_match_rate)) * Decimal('0.5'))
    
    print("\n🧮 Manual verification:")
    print(f"   Trader match rate: {trader_match_rate}%")
    print(f"   Exchange match rate: {exchange_match_rate}%")  
    print(f"   Overall (50/50 avg): {overall_calculated}%")
    print(f"   Pool overall: {final_stats['match_rates']['overall']}")
    
    return final_stats

if __name__ == "__main__":
    debug_ice_calculation()
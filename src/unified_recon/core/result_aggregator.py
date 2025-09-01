"""Result collection and aggregation for unified reconciliation system."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SystemResult:
    """Results from a single matching system."""
    group_id: int
    system_name: str
    matches_found: int
    trader_count: int
    exchange_count: int
    match_rate: float
    system_config: Dict[str, Any]
    processing_time: Optional[float] = None
    detailed_results: Optional[Any] = None  # System-specific result format
    statistics: Optional[Dict[str, Any]] = None


@dataclass
class UnifiedResult:
    """Aggregated results from all matching systems."""
    total_groups_processed: int
    total_matches_found: int
    total_trader_trades: int
    total_exchange_trades: int
    overall_match_rate: float
    system_results: List[SystemResult]
    processing_summary: Dict[str, Any]


class ResultAggregator:
    """Collects and aggregates results from multiple matching systems."""
    
    def __init__(self) -> None:
        """Initialize result aggregator."""
        self.system_results: List[SystemResult] = []
        
    def add_system_result(self, 
                         group_id: int,
                         system_name: str, 
                         matches_found: int,
                         trader_count: int,
                         exchange_count: int,
                         system_config: Dict[str, Any],
                         processing_time: Optional[float] = None,
                         detailed_results: Optional[Any] = None,
                         statistics: Optional[Dict[str, Any]] = None,
                         match_rate: Optional[float] = None) -> None:
        """Add results from a matching system.
        
        Args:
            group_id: Exchange group ID
            system_name: Name of the matching system
            matches_found: Number of matches found
            trader_count: Number of trader trades processed
            exchange_count: Number of exchange trades processed
            system_config: System configuration used
            processing_time: Optional processing time in seconds
            detailed_results: Optional detailed results object
            statistics: Optional detailed statistics
            match_rate: Optional pre-calculated match rate (if None, will calculate from matches_found/trader_count)
        """
        # Use provided match rate or calculate (using trader trades as denominator for backward compatibility)
        if match_rate is None:
            match_rate = (matches_found / trader_count * 100) if trader_count > 0 else 0.0
        
        result = SystemResult(
            group_id=group_id,
            system_name=system_name,
            matches_found=matches_found,
            trader_count=trader_count,
            exchange_count=exchange_count,
            match_rate=match_rate,
            system_config=system_config,
            processing_time=processing_time,
            detailed_results=detailed_results,
            statistics=statistics
        )
        
        self.system_results.append(result)
        logger.info(f"Added result for group {group_id} ({system_name}): {matches_found} matches, {match_rate:.1f}% rate")
    
    def get_aggregated_results(self) -> UnifiedResult:
        """Get aggregated results from all systems.
        
        Returns:
            UnifiedResult with aggregated statistics
        """
        if not self.system_results:
            return UnifiedResult(
                total_groups_processed=0,
                total_matches_found=0,
                total_trader_trades=0,
                total_exchange_trades=0,
                overall_match_rate=0.0,
                system_results=[],
                processing_summary={}
            )
        
        # Aggregate totals
        total_groups = len(self.system_results)
        total_matches = sum(r.matches_found for r in self.system_results)
        total_trader_trades = sum(r.trader_count for r in self.system_results)
        total_exchange_trades = sum(r.exchange_count for r in self.system_results)
        
        # Calculate overall match rate as weighted average of individual system rates
        # This matches the ICE system convention of using individual system's calculated rates
        if self.system_results:
            total_trader_weight = sum(r.trader_count for r in self.system_results)
            if total_trader_weight > 0:
                overall_match_rate = sum(r.match_rate * r.trader_count for r in self.system_results) / total_trader_weight
            else:
                overall_match_rate = 0.0
        else:
            overall_match_rate = 0.0
        
        # Create processing summary
        system_breakdown = {}
        for result in self.system_results:
            if result.system_name not in system_breakdown:
                system_breakdown[result.system_name] = {
                    'groups': 0,
                    'matches': 0,
                    'trader_trades': 0,
                    'exchange_trades': 0,
                    'avg_match_rate': 0.0
                }
            
            system_breakdown[result.system_name]['groups'] += 1
            system_breakdown[result.system_name]['matches'] += result.matches_found
            system_breakdown[result.system_name]['trader_trades'] += result.trader_count
            system_breakdown[result.system_name]['exchange_trades'] += result.exchange_count
        
        # Calculate average match rates per system
        for system_name, stats in system_breakdown.items():
            system_results = [r for r in self.system_results if r.system_name == system_name]
            if system_results:
                stats['avg_match_rate'] = sum(r.match_rate for r in system_results) / len(system_results)
        
        processing_summary = {
            'systems_used': list(system_breakdown.keys()),
            'system_breakdown': system_breakdown,
            'total_processing_time': sum(r.processing_time for r in self.system_results if r.processing_time)
        }
        
        return UnifiedResult(
            total_groups_processed=total_groups,
            total_matches_found=total_matches,
            total_trader_trades=total_trader_trades,
            total_exchange_trades=total_exchange_trades,
            overall_match_rate=overall_match_rate,
            system_results=self.system_results.copy(),
            processing_summary=processing_summary
        )
    
    def get_results_by_system(self, system_name: str) -> List[SystemResult]:
        """Get results for a specific system.
        
        Args:
            system_name: Name of the system to filter by
            
        Returns:
            List of SystemResult objects for the specified system
        """
        return [r for r in self.system_results if r.system_name == system_name]
    
    def get_results_by_group(self, group_id: int) -> Optional[SystemResult]:
        """Get results for a specific exchange group.
        
        Args:
            group_id: Exchange group ID
            
        Returns:
            SystemResult for the group, or None if not found
        """
        for result in self.system_results:
            if result.group_id == group_id:
                return result
        return None
    
    def clear_results(self) -> None:
        """Clear all stored results."""
        self.system_results.clear()
        logger.info("Cleared all results from aggregator")
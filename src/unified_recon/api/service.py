"""Service layer for reconciliation API."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core.group_router import UnifiedTradeRouter
from ..core.result_aggregator import ResultAggregator
from ..utils.dataframe_output import create_unified_dataframe
from ..rule_0.main import process_exchanges, load_unified_config
from ..rule_0.json_output import Rule0JSONOutput
from ..main import (
    call_ice_match_system,
    call_sgx_match_system,
    call_cme_match_system,
    call_eex_match_system,
)
from .models import ReconciliationRequest, Rule0Request, Rule0Response

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Service layer that integrates with existing reconciliation infrastructure."""

    def __init__(self) -> None:
        # Use relative path from current file location
        config_path = Path(__file__).parent.parent / "config" / "unified_config.json"
        self.router: UnifiedTradeRouter = UnifiedTradeRouter(config_path)

    async def process_reconciliation(
        self, request: ReconciliationRequest
    ) -> List[Dict[str, Any]]:
        """
        Process reconciliation request asynchronously.
        Wraps synchronous processing to avoid blocking.
        """
        return await asyncio.to_thread(self._process_sync, request)

    def _process_sync(self, request: ReconciliationRequest) -> List[Dict[str, Any]]:
        """
        Synchronous processing using existing infrastructure.
        Validation happens in the Trade Factories.
        """
        try:
            # Prepare data dictionary from request
            json_data = {
                "traderTrades": request.traderTrades,
                "exchangeTrades": request.exchangeTrades,
            }

            # Use new method that processes data directly without filesystem I/O
            # This is where ICETradeFactory, SGXTradeFactory, etc. do validation
            trader_df, exchange_df = self.router.load_and_validate_json_dict(json_data)

            # Group trades by exchange group ID
            grouped_trades = self.router.group_trades_by_exchange_group(
                trader_df, exchange_df
            )
            processable_groups = self.router.get_processable_groups(grouped_trades)

            if not processable_groups:
                logger.warning("No processable trade groups found")
                return []

            # Process through matching systems
            result_aggregator = ResultAggregator()

            for group_id in processable_groups:
                group_info = grouped_trades[group_id]
                system_name = group_info["system"]

                logger.debug(f"Processing group {group_id} with system {system_name}")

                # Prepare data for system
                prepared_data = self.router.prepare_data_for_system(
                    group_info, system_name
                )

                # Call appropriate matching system
                results = self._call_matching_system(system_name, prepared_data)
                if results:
                    result_aggregator.add_system_result(
                        group_id=group_id,
                        system_name=system_name,
                        matches_found=results["matches_found"],
                        trader_count=group_info["trader_count"],
                        exchange_count=group_info["exchange_count"],
                        system_config=group_info["system_config"],
                        processing_time=results.get("processing_time"),
                        detailed_results=results.get("detailed_results"),
                        statistics=results,
                        match_rate=results["match_rate"],
                    )

            # Get aggregated results
            unified_results = result_aggregator.get_aggregated_results()

            # Convert to DataFrame format using existing logic
            df = create_unified_dataframe(unified_results)

            # Convert DataFrame to JSON records format (same as CLI --json-output)
            # Reuses the same logic as save_dataframe_to_json
            records_data = df.to_dict(orient="records")
            
            # Cast to ensure proper typing (DataFrame columns are always strings)
            typed_records: List[Dict[str, Any]] = records_data  # type: ignore[assignment]

            logger.info(
                f"Successfully processed reconciliation: {len(typed_records)} records"
            )
            return typed_records

        except Exception as e:
            logger.error(f"Error during reconciliation processing: {e}", exc_info=True)
            raise

    def _call_matching_system(
        self, system_name: str, prepared_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Call the appropriate matching system.
        Each system handles its own validation via Trade Factories.
        """
        system_callers = {
            "ice_match": call_ice_match_system,
            "sgx_match": call_sgx_match_system,
            "cme_match": call_cme_match_system,
            "eex_match": call_eex_match_system,
        }

        caller = system_callers.get(system_name)
        if not caller:
            logger.warning(f"Unknown system: {system_name}")
            return None

        trader_data = prepared_data["trader_data"]
        exchange_data = prepared_data["exchange_data"]
        return caller(trader_data, exchange_data)


class Rule0Service:
    """Service layer for Rule 0 position analysis."""

    def __init__(self) -> None:
        # Use relative path from current file location
        config_path = Path(__file__).parent.parent / "config" / "unified_config.json"
        self.router: UnifiedTradeRouter = UnifiedTradeRouter(config_path)
        self.config: Dict[str, Any] = load_unified_config()
        # Get supported exchanges from config
        self.supported_exchanges: List[str] = list(self.config.get("rule_0_config", {}).keys())

    async def process_rule0_analysis(self, request: Rule0Request) -> Rule0Response:
        """
        Process Rule 0 position analysis request asynchronously.
        """
        return await asyncio.to_thread(self._process_sync, request)

    def _process_sync(self, request: Rule0Request) -> Rule0Response:
        """
        Synchronous processing of Rule 0 analysis.
        """
        try:
            # Prepare data dictionary from request
            json_data = {
                "traderTrades": request.traderTrades,
                "exchangeTrades": request.exchangeTrades,
            }

            # Load and validate using router (reuses existing validation)
            trader_df, exchange_df = self.router.load_and_validate_json_dict(json_data)

            # Group trades by exchange group ID
            grouped_trades = self.router.group_trades_by_exchange_group(
                trader_df, exchange_df
            )

            # Process through Rule 0 for each exchange
            all_results = {}
            
            for group_id, group_info in grouped_trades.items():
                # Get system name for this group
                system_name = group_info["system"]
                
                # Only process supported exchanges from config
                if system_name not in self.supported_exchanges:
                    logger.info(
                        f"Skipping Rule 0 for {system_name} (not configured)"
                    )
                    continue
                
                # Prepare data for the exchange
                prepared_data = self.router.prepare_data_for_system(
                    group_info, system_name
                )
                
                # Create a namespace to simulate command line args
                args = argparse.Namespace(
                    json_output=True,
                    show_details=False
                )
                
                # Process Rule 0 analysis
                trader_records = prepared_data["trader_data"].to_dict('records')
                exchange_records = prepared_data["exchange_data"].to_dict('records')
                
                exchange_results = process_exchanges(
                    [system_name],  # exchanges_to_process
                    trader_records,  # trader_trades
                    exchange_records,  # exchange_trades
                    self.config,  # unified_config
                    args  # args
                )
                
                # Merge results
                all_results.update(exchange_results)
            
            # If no results, return empty response
            if not all_results:
                return Rule0Response(root={})
            
            # Generate JSON output using the JSON output generator
            # Get tolerances from first result (they're the same for all)
            first_key = list(all_results.keys())[0] if all_results else None
            tolerances = {}
            if first_key:
                tolerances = all_results.get(first_key, {}).get('tolerance_dict', {})
            
            json_output = Rule0JSONOutput(tolerances=tolerances, unified_config=self.config)
            json_dict = json_output.generate_multi_exchange_json(all_results)
            
            # Convert to Rule0Response format
            return Rule0Response(root=json_dict)

        except Exception as e:
            logger.error(f"Error during Rule 0 analysis: {e}", exc_info=True)
            raise

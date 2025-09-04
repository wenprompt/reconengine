"""Service layer for reconciliation API."""

from pathlib import Path
from typing import List, Dict, Any
import asyncio
import logging

from ..core.group_router import UnifiedTradeRouter
from ..core.result_aggregator import ResultAggregator
from ..utils.dataframe_output import create_unified_dataframe
from .models import ReconciliationRequest

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Service layer that integrates with existing reconciliation infrastructure."""

    def __init__(self):
        config_path = Path("src/unified_recon/config/unified_config.json")
        self.router = UnifiedTradeRouter(config_path)

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
            # This reuses the exact same logic as save_dataframe_to_json in dataframe_output.py
            records_data = df.to_dict(orient="records")

            logger.info(
                f"Successfully processed reconciliation: {len(records_data)} records"
            )
            return records_data  # type: ignore

        except Exception as e:
            logger.error(f"Error during reconciliation processing: {e}", exc_info=True)
            raise

    def _call_matching_system(
        self, system_name: str, prepared_data: Dict[str, Any]
    ) -> Any:
        """
        Call the appropriate matching system.
        Each system handles its own validation via Trade Factories.
        """
        from ..main import (
            call_ice_match_system,
            call_sgx_match_system,
            call_cme_match_system,
            call_eex_match_system,
        )

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

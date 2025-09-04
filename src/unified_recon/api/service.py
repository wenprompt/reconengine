"""Service layer for reconciliation API."""

import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import asyncio
import logging

from ..core.group_router import UnifiedTradeRouter
from ..core.result_aggregator import ResultAggregator
from ..utils.dataframe_output import create_unified_dataframe
from ..utils.data_validator import DataValidationError
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
        temp_path = None

        try:
            # Create temporary JSON file for router processing
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json_data = {
                    "traderTrades": request.traderTrades,
                    "exchangeTrades": request.exchangeTrades,
                }
                json.dump(json_data, f, ensure_ascii=False, indent=2)
                temp_path = Path(f.name)

            logger.debug(f"Created temporary file: {temp_path}")

            # Use existing router to load and validate via Trade Factories
            # This is where ICETradeFactory, SGXTradeFactory, etc. do validation
            trader_df, exchange_df = self.router.load_and_validate_json_data(temp_path)

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
        finally:
            # Cleanup temporary file
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_path}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup temporary file {temp_path}: {cleanup_error}"
                    )

    def _call_matching_system(
        self, system_name: str, prepared_data: Dict[str, Any]
    ) -> Any:
        """
        Call the appropriate matching system.
        Each system handles its own validation via Trade Factories.
        """
        trader_data = prepared_data["trader_data"]
        exchange_data = prepared_data["exchange_data"]

        if system_name == "ice_match":
            from ..main import call_ice_match_system

            return call_ice_match_system(trader_data, exchange_data)

        elif system_name == "sgx_match":
            from ..main import call_sgx_match_system

            return call_sgx_match_system(trader_data, exchange_data)

        elif system_name == "cme_match":
            from ..main import call_cme_match_system

            return call_cme_match_system(trader_data, exchange_data)

        elif system_name == "eex_match":
            from ..main import call_eex_match_system

            return call_eex_match_system(trader_data, exchange_data)

        else:
            logger.warning(f"Unknown system: {system_name}")
            return None

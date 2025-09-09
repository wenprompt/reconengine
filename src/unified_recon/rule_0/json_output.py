"""JSON output formatting for unified Rule 0."""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from dataclasses import dataclass
import json
from pathlib import Path

from src.unified_recon.rule_0.position_matrix import PositionMatrix
from src.unified_recon.rule_0.matrix_comparator import PositionComparison, MatchStatus


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal values."""
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


@dataclass
class TradeDetailJSON:
    """Trade detail for JSON output."""
    contract_month: str
    source: str  # "trader" or "exchange"
    internal_id: str
    quantity: float
    unit: str
    price: float
    broker_group_id: str
    exch_clearing_acct_id: str
    trade_type: str  # "Crack", "PS", "S", or empty
    match_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contractMonth": self.contract_month,
            "source": self.source,
            "internalId": self.internal_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "price": self.price,
            "brokerGroupId": self.broker_group_id,
            "exchClearingAcctId": self.exch_clearing_acct_id,
            "tradeType": self.trade_type,
            "matchId": self.match_id
        }


@dataclass
class PositionSummaryJSON:
    """Position summary for JSON output."""
    contract_month: str
    trader_quantity: float
    exchange_quantity: float
    difference: float
    unit: str
    status: str
    trader_trade_count: int
    exchange_trade_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contractMonth": self.contract_month,
            "traderQuantity": self.trader_quantity,
            "exchangeQuantity": self.exchange_quantity,
            "difference": self.difference,
            "unit": self.unit,
            "status": self.status,
            "traderTradeCount": self.trader_trade_count,
            "exchangeTradeCount": self.exchange_trade_count
        }


class FieldExtractor:
    """Extract fields from PositionComparison based on exchange configuration."""
    
    def __init__(self, unified_config: Dict[str, Any], exchange_group_id: str):
        """Initialize field extractor with configs.
        
        Args:
            unified_config: Main unified configuration
            exchange_group_id: Exchange group identifier
        """
        self.unified_config = unified_config
        self.exchange_group_id = exchange_group_id
        
        # Get the specific exchange for this group
        mappings = unified_config.get("exchange_group_mappings", {})
        self.exchange = mappings.get(exchange_group_id, "")
        
        # Get exchange-specific rule_0 config
        rule0_configs = unified_config.get("rule_0_config", {})
        self.exchange_config = rule0_configs.get(self.exchange, {})
        
        # Load normalizer config if available
        self.normalizer_config = self._load_normalizer_config()
    
    def _load_normalizer_config(self) -> Optional[Dict[str, Any]]:
        """Load normalizer config if path is specified."""
        normalizer_path = self.exchange_config.get("normalizer_config")
        if normalizer_path:
            path = Path(normalizer_path)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        return None
    
    def extract_quantities_and_unit(self, comp: Any) -> Dict[str, Any]:
        """Extract quantities and unit based on this exchange's configuration.
        
        Args:
            comp: PositionComparison object (could be ICE or unified type)
            
        Returns:
            Dict with trader_quantity, exchange_quantity, difference, unit
        """
        # Handle based on the specific exchange this group belongs to
        if self.exchange == "ice_match":
            # ICE uses MT/BBL fields
            return self._extract_ice_fields(comp)
        
        elif self.exchange == "cme_match":
            # CME uses quantitylot with LOTS unit
            return self._extract_cme_fields(comp)
        
        else:
            # SGX, EEX use standard fields
            return self._extract_standard_fields(comp)
    
    def _extract_ice_fields(self, comp: Any) -> Dict[str, Any]:
        """Extract ICE-specific MT/BBL fields."""
        # ICE has both MT and BBL, need to determine which to use
        trader_mt = float(getattr(comp, 'trader_mt', 0))
        trader_bbl = float(getattr(comp, 'trader_bbl', 0))
        exchange_mt = float(getattr(comp, 'exchange_mt', 0))
        exchange_bbl = float(getattr(comp, 'exchange_bbl', 0))
        
        # Determine primary unit based on non-zero values
        # Prefer BBL if it has values, otherwise MT
        if trader_bbl != 0 or exchange_bbl != 0:
            return {
                "trader_quantity": trader_bbl,
                "exchange_quantity": exchange_bbl,
                "difference": float(getattr(comp, 'difference_bbl', 0)),
                "unit": "BBL"
            }
        else:
            return {
                "trader_quantity": trader_mt,
                "exchange_quantity": exchange_mt,
                "difference": float(getattr(comp, 'difference_mt', 0)),
                "unit": "MT"
            }
    
    def _extract_cme_fields(self, comp: Any) -> Dict[str, Any]:
        """Extract CME-specific quantitylot fields."""
        # CME config specifies quantity_field and default_unit
        quantity_field = self.exchange_config.get("quantity_field", "quantity")
        default_unit = self.exchange_config.get("default_unit", "LOTS")
        
        # Build field names dynamically
        trader_field = f"trader_{quantity_field}"
        exchange_field = f"exchange_{quantity_field}"
        
        return {
            "trader_quantity": float(getattr(comp, trader_field, 0)),
            "exchange_quantity": float(getattr(comp, exchange_field, 0)),
            "difference": float(getattr(comp, 'difference', 0)),
            "unit": default_unit
        }
    
    def _extract_standard_fields(self, comp: Any) -> Dict[str, Any]:
        """Extract standard quantity/unit fields (SGX, EEX)."""
        return {
            "trader_quantity": float(getattr(comp, 'trader_quantity', 0)),
            "exchange_quantity": float(getattr(comp, 'exchange_quantity', 0)),
            "difference": float(getattr(comp, 'difference', 0)),
            "unit": getattr(comp, 'unit', '')
        }


class Rule0JSONOutput:
    """JSON output formatter for Rule 0 results."""
    
    def __init__(self, tolerances: Optional[Dict[str, float]] = None, 
                 unified_config: Optional[Dict[str, Any]] = None):
        """Initialize JSON output formatter.
        
        Args:
            tolerances: Optional tolerance values for matching
            unified_config: Optional unified configuration for field extraction
        """
        self.tolerances = tolerances or {}
        self.unified_config = unified_config or {}
        self.field_extractors: Dict[str, FieldExtractor] = {}
    
    def _determine_trade_type(self, original_product: str, spread_flag: str) -> str:
        """Determine trade type based on product and flags."""
        if original_product:
            if "crack" in original_product.lower():
                return "Crack"
            elif "-" in original_product:
                return "PS"
            else:
                return ""
        elif spread_flag == "S":
            return "S"
        else:
            return ""
    
    def _match_trades(self, trader_trades: List[Dict[str, Any]], exchange_trades: List[Dict[str, Any]]) -> None:
        """Match trader and exchange trades (same logic as display.py)."""
        # Reset match status
        for trade in trader_trades + exchange_trades:
            trade['matched'] = False
            trade['match_id'] = ""
        
        # Match each trader trade with best exchange trade
        for t_trade in trader_trades:
            best_match = None
            best_difference = float('inf')
            
            t_qty = t_trade.get('quantity', 0)
            t_unit = t_trade.get('unit', '').upper()
            
            # Determine tolerance
            tolerance = 0.0
            if self.tolerances:
                if t_unit == "BBL" and 'tolerance_bbl' in self.tolerances:
                    tolerance = self.tolerances.get('tolerance_bbl', 0)
                elif t_unit == "MT" and 'tolerance_mt' in self.tolerances:
                    tolerance = self.tolerances.get('tolerance_mt', 0)
                elif t_unit == "LOTS" and 'tolerance_lots' in self.tolerances:
                    tolerance = self.tolerances.get('tolerance_lots', 0)
                elif 'tolerance_default' in self.tolerances:
                    tolerance = self.tolerances.get('tolerance_default', 0)
                elif 'tolerance' in self.tolerances:
                    tolerance = self.tolerances.get('tolerance', 0)
            
            # Find best matching exchange trade
            for e_trade in exchange_trades:
                if e_trade.get('matched', False):
                    continue
                
                e_qty = e_trade.get('quantity', 0)
                
                # Check matching criteria
                if ((t_qty * e_qty > 0) and
                    t_trade.get('broker_group_id', '') == e_trade.get('broker_group_id', '') and
                    t_trade.get('exch_clearing_acct_id', '') == e_trade.get('exch_clearing_acct_id', '')):
                    
                    qty_difference = abs(abs(t_qty) - abs(e_qty))
                    
                    if qty_difference <= tolerance and qty_difference < best_difference:
                        best_match = e_trade
                        best_difference = qty_difference
            
            # Apply best match
            if best_match:
                t_id = t_trade.get('internal_trade_id', 'NA')
                e_id = best_match.get('internal_trade_id', 'NA')
                match_id = f"M_{t_id}_{e_id}"
                
                t_trade['matched'] = True
                t_trade['match_id'] = match_id
                best_match['matched'] = True
                best_match['match_id'] = match_id
    
    def _get_field_extractor(self, exchange_group_id: str) -> FieldExtractor:
        """Get or create field extractor for exchange group."""
        if exchange_group_id not in self.field_extractors:
            self.field_extractors[exchange_group_id] = FieldExtractor(
                self.unified_config, exchange_group_id
            )
        return self.field_extractors[exchange_group_id]
    
    def generate_json_output_for_exchange(
        self,
        trader_matrix: PositionMatrix,
        exchange_matrix: PositionMatrix,
        comparisons: List[PositionComparison],
        exchange_group_id: str
    ) -> Dict[str, Any]:
        """Generate JSON output for a single exchange group.
        
        Args:
            trader_matrix: Trader position matrix
            exchange_matrix: Exchange position matrix
            comparisons: List of position comparisons
            exchange_group_id: Exchange group identifier
            
        Returns:
            Dictionary containing products data for this exchange group
        """
        result: Dict[str, Any] = {
            "products": {}
        }
        
        # Group comparisons by product
        by_product: Dict[str, List[PositionComparison]] = {}
        for comp in comparisons:
            if comp.product not in by_product:
                by_product[comp.product] = []
            by_product[comp.product].append(comp)
        
        # Process each product
        for product, product_comps in sorted(by_product.items()):
            product_data: Dict[str, List[Any]] = {
                "positionSummary": [],
                "tradeDetails": []
            }
            
            # Add position summary for each contract month
            for comp in sorted(product_comps, key=lambda x: x.contract_month):
                # Skip zero positions unless they have trades
                if comp.status == MatchStatus.ZERO_POSITION:
                    continue
                
                # Determine status string
                if comp.status == MatchStatus.MATCHED:
                    status_str = "MATCHED"
                elif comp.status == MatchStatus.QUANTITY_MISMATCH:
                    status_str = "MISMATCH"
                elif comp.status == MatchStatus.MISSING_IN_EXCHANGE:
                    status_str = "MISSING_IN_EXCHANGE"
                elif comp.status == MatchStatus.MISSING_IN_TRADER:
                    status_str = "MISSING_IN_TRADER"
                else:
                    status_str = "ZERO"
                
                # Use field extractor to handle different exchange formats
                extractor = self._get_field_extractor(exchange_group_id)
                quantities = extractor.extract_quantities_and_unit(comp)
                
                summary = PositionSummaryJSON(
                    contract_month=comp.contract_month,
                    trader_quantity=quantities["trader_quantity"],
                    exchange_quantity=quantities["exchange_quantity"],
                    difference=quantities["difference"],
                    unit=quantities["unit"],
                    status=status_str,
                    trader_trade_count=comp.trader_trades,
                    exchange_trade_count=comp.exchange_trades
                )
                product_data["positionSummary"].append(summary.to_dict())
            
            # Collect all contract months for this product
            all_months = set()
            for month, prod in trader_matrix.positions.keys():
                if prod == product:
                    all_months.add(month)
            for month, prod in exchange_matrix.positions.keys():
                if prod == product:
                    all_months.add(month)
            
            # Process trade details for each month
            for month in sorted(all_months):
                trader_trades = []
                exchange_trades = []
                
                # Get trader trades
                trader_pos = trader_matrix.get_position(month, product)
                if trader_pos and trader_pos.trade_details:
                    trader_trades = list(trader_pos.trade_details)
                
                # Get exchange trades
                exchange_pos = exchange_matrix.get_position(month, product)
                if exchange_pos and exchange_pos.trade_details:
                    exchange_trades = list(exchange_pos.trade_details)
                
                # Perform matching
                if trader_trades and exchange_trades:
                    self._match_trades(trader_trades, exchange_trades)
                
                # Add trader trades to output
                for detail in trader_trades:
                    trade_type = self._determine_trade_type(
                        detail.get('original_product', ''),
                        detail.get('spread_flag', '')
                    )
                    
                    trade_json = TradeDetailJSON(
                        contract_month=month,
                        source="1",  # 1 = Trader
                        internal_id=str(detail.get('internal_trade_id', 'N/A')),
                        quantity=float(detail.get('quantity', 0)),
                        unit=detail.get('unit', ''),
                        price=float(detail.get('price', 0)),
                        broker_group_id=str(detail.get('broker_group_id', '')),
                        exch_clearing_acct_id=str(detail.get('exch_clearing_acct_id', '')),
                        trade_type=trade_type,
                        match_id=detail.get('match_id', '')
                    )
                    product_data["tradeDetails"].append(trade_json.to_dict())
                
                # Add exchange trades to output
                for detail in exchange_trades:
                    trade_type = self._determine_trade_type(
                        detail.get('original_product', ''),
                        detail.get('spread_flag', '')
                    )
                    
                    trade_json = TradeDetailJSON(
                        contract_month=month,
                        source="2",  # 2 = Exchange
                        internal_id=str(detail.get('internal_trade_id', 'N/A')),
                        quantity=float(detail.get('quantity', 0)),
                        unit=detail.get('unit', ''),
                        price=float(detail.get('price', 0)),
                        broker_group_id=str(detail.get('broker_group_id', '')),
                        exch_clearing_acct_id=str(detail.get('exch_clearing_acct_id', '')),
                        trade_type=trade_type,
                        match_id=detail.get('match_id', '')
                    )
                    product_data["tradeDetails"].append(trade_json.to_dict())
            
            # Only add product if it has data
            if product_data["positionSummary"] or product_data["tradeDetails"]:
                result["products"][product] = product_data
        
        return result
    
    def generate_multi_exchange_json(
        self,
        exchange_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate JSON output for multiple exchange groups.
        
        Args:
            exchange_results: Dictionary mapping exchange_group_id to results
                Each result contains: trader_matrix, exchange_matrix, comparisons
            
        Returns:
            Dictionary grouped by exchange_group_id
        """
        output = {}
        
        for exchange_group_id, data in exchange_results.items():
            trader_matrix = data['trader_matrix']
            exchange_matrix = data['exchange_matrix']
            comparisons = data['comparisons']
            
            # Generate output for this exchange group
            exchange_output = self.generate_json_output_for_exchange(
                trader_matrix, exchange_matrix, comparisons, exchange_group_id
            )
            
            # Only add if there's data
            if exchange_output["products"]:
                output[exchange_group_id] = exchange_output
        
        return output
    
    def to_json_string(
        self,
        exchange_results: Dict[str, Dict[str, Any]],
        indent: int = 2
    ) -> str:
        """Generate JSON string output for multiple exchanges.
        
        Args:
            exchange_results: Dictionary mapping exchange_group_id to results
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        data = self.generate_multi_exchange_json(exchange_results)
        return json.dumps(data, cls=DecimalEncoder, indent=indent)
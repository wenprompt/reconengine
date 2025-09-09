"""JSON output formatting for unified Rule 0."""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from dataclasses import dataclass
import json

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


class Rule0JSONOutput:
    """JSON output formatter for Rule 0 results."""
    
    def __init__(self, tolerances: Optional[Dict[str, float]] = None):
        """Initialize JSON output formatter.
        
        Args:
            tolerances: Optional tolerance values for matching
        """
        self.tolerances = tolerances or {}
    
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
                
                summary = PositionSummaryJSON(
                    contract_month=comp.contract_month,
                    trader_quantity=float(comp.trader_quantity),
                    exchange_quantity=float(comp.exchange_quantity),
                    difference=float(comp.difference),
                    unit=comp.unit or "",
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
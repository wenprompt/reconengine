"""Helper utilities for SGX trade processing."""

from typing import Optional, Tuple
import re
from decimal import Decimal


def get_month_order_tuple(contract_month: str) -> Optional[Tuple[int, int]]:
    """Convert contract month to sortable tuple (year, month_number).
    
    Args:
        contract_month: Contract month string like 'Oct-25' or 'Oct25'
        
    Returns:
        Tuple of (year, month_number) or None if parsing fails
        
    Examples:
        'Oct-25' -> (2025, 10)
        'Jan26' -> (2026, 1)
    """
    if not contract_month:
        return None
    
    # Month name to number mapping
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    try:
        # Handle formats like 'Oct-25', 'Oct25', 'Sept-25'
        normalized = contract_month.lower().replace('-', '')
        
        # Extract month name (first 3-4 letters)
        month_match = re.match(r'([a-z]{3,4})', normalized)
        if not month_match:
            return None
            
        month_str = month_match.group(1)
        month_num = month_map.get(month_str)
        if month_num is None:
            return None
        
        # Extract year (last 2 digits)
        year_match = re.search(r'(\d{2})$', normalized)
        if not year_match:
            return None
            
        year_suffix = int(year_match.group(1))
        # Assume 20XX for years 00-99
        year = 2000 + year_suffix
        
        return (year, month_num)
        
    except (ValueError, AttributeError):
        return None


def calculate_spread_price(trade1_price: Decimal, trade1_month: str, 
                          trade2_price: Decimal, trade2_month: str) -> Optional[Decimal]:
    """Calculate spread price (earlier month - later month).
    
    Args:
        trade1_price: Price of first trade
        trade1_month: Contract month of first trade
        trade2_price: Price of second trade  
        trade2_month: Contract month of second trade
        
    Returns:
        Spread price or None if calculation fails
    """
    month1_tuple = get_month_order_tuple(trade1_month)
    month2_tuple = get_month_order_tuple(trade2_month)
    
    if not month1_tuple or not month2_tuple:
        return None
    
    # Earlier month - later month
    if month1_tuple < month2_tuple:
        return trade1_price - trade2_price
    else:
        return trade2_price - trade1_price
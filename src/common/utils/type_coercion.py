"""Type coercion utilities for flexible data handling."""

from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Safely convert value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
        
    Examples:
        >>> safe_int("123")
        123
        >>> safe_int("abc")
        None
        >>> safe_int("123.45")
        123
        >>> safe_int(None)
        None
    """
    if value is None or value == "":
        return default
    
    if isinstance(value, int):
        return value
    
    try:
        if isinstance(value, float):
            return int(value)
        elif isinstance(value, str):
            # Try to handle strings that might be floats
            if "." in value:
                return int(float(value))
            return int(value)
        elif isinstance(value, Decimal):
            return int(value)
        else:
            return int(value)
    except (ValueError, TypeError, InvalidOperation):
        return default


def safe_decimal(
    value: Any,
    default: Optional[Decimal] = None
) -> Optional[Decimal]:
    """
    Safely convert value to Decimal.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Decimal value or default
        
    Examples:
        >>> safe_decimal("123.45")
        Decimal('123.45')
        >>> safe_decimal(123.45)
        Decimal('123.45')
        >>> safe_decimal("abc")
        None
        >>> safe_decimal(None)
        None
    """
    if value is None or value == "":
        return default
    
    if isinstance(value, Decimal):
        return value
    
    try:
        if isinstance(value, float):
            # Convert to string first to avoid float precision issues
            return Decimal(str(value))
        elif isinstance(value, (int, str)):
            return Decimal(value)
        else:
            return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        return default


def safe_str(
    value: Any,
    default: Optional[str] = None,
    preserve_none: bool = False
) -> Optional[str]:
    """
    Safely convert value to string.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        preserve_none: If True, return None for None values instead of default
        
    Returns:
        String value or default
        
    Examples:
        >>> safe_str(123)
        '123'
        >>> safe_str(None)
        None
        >>> safe_str(None, default="")
        ''
        >>> safe_str(123.45)
        '123.45'
    """
    if value is None:
        return None if preserve_none else default
    
    if value == "":
        return default
    
    if isinstance(value, str):
        return value
    
    try:
        return str(value)
    except (ValueError, TypeError):
        return default
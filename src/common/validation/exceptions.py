"""Custom exceptions for validation."""

from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """
    Base exception for validation errors.
    
    Provides structured error information for debugging and reporting.
    """
    
    def __init__(
        self, 
        message: str,
        errors: Optional[List[Dict[str, Any]]] = None,
        data_type: Optional[str] = None,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        """
        Initialize ValidationError with detailed error information.
        
        Args:
            message: Human-readable error message
            errors: List of detailed error dictionaries (e.g., from Pydantic)
            data_type: Type of data being validated ("trader" or "exchange")
            field: Specific field that failed validation
            value: The value that failed validation
        """
        super().__init__(message)
        self.errors = errors or []
        self.data_type = data_type
        self.field = field
        self.value = value
    
    def __str__(self) -> str:
        """Return detailed error message."""
        parts = [str(self.args[0]) if self.args else "Validation error"]
        
        if self.data_type:
            parts.append(f"Data type: {self.data_type}")
        
        if self.field:
            parts.append(f"Field: {self.field}")
        
        if self.value is not None:
            parts.append(f"Value: {self.value}")
        
        if self.errors:
            parts.append(f"Errors: {self.errors}")
        
        return " | ".join(parts)


class CSVValidationError(ValidationError):
    """Specific exception for CSV validation errors."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        row_number: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize CSV validation error.
        
        Args:
            message: Error message
            file_path: Path to the CSV file that failed validation
            row_number: Row number where error occurred
            **kwargs: Additional arguments passed to ValidationError
        """
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.row_number = row_number
    
    def __str__(self) -> str:
        """Return CSV-specific error message."""
        base_msg = super().__str__()
        
        parts = [base_msg]
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.row_number is not None:
            parts.append(f"Row: {self.row_number}")
        
        return " | ".join(parts)


class JSONValidationError(ValidationError):
    """Specific exception for JSON validation errors."""
    
    def __init__(
        self,
        message: str,
        json_path: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize JSON validation error.
        
        Args:
            message: Error message
            json_path: JSON path to the element that failed validation
            **kwargs: Additional arguments passed to ValidationError
        """
        super().__init__(message, **kwargs)
        self.json_path = json_path
    
    def __str__(self) -> str:
        """Return JSON-specific error message."""
        base_msg = super().__str__()
        
        if self.json_path:
            return f"{base_msg} | JSON Path: {self.json_path}"
        return base_msg


class FieldMappingError(ValidationError):
    """Exception for field mapping errors."""
    
    def __init__(
        self,
        message: str,
        missing_fields: Optional[List[str]] = None,
        unmapped_fields: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize field mapping error.
        
        Args:
            message: Error message
            missing_fields: List of required fields that are missing
            unmapped_fields: List of fields that couldn't be mapped
            **kwargs: Additional arguments passed to ValidationError
        """
        super().__init__(message, **kwargs)
        self.missing_fields = missing_fields or []
        self.unmapped_fields = unmapped_fields or []
    
    def __str__(self) -> str:
        """Return field mapping error message."""
        base_msg = super().__str__()
        
        parts = [base_msg]
        if self.missing_fields:
            parts.append(f"Missing fields: {', '.join(self.missing_fields)}")
        if self.unmapped_fields:
            parts.append(f"Unmapped fields: {', '.join(self.unmapped_fields)}")
        
        return " | ".join(parts)
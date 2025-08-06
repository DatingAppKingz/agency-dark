"""
SQL injection prevention layers
"""
import re
import json
from typing import Any, Dict, List, Optional, Union, Set
from sqlalchemy import text, inspect
from sqlalchemy.sql import Select
from sqlalchemy.orm import Query
from fastapi import HTTPException, status

from core.logging import logger


class SQLInjectionPrevention:
    """SQL injection prevention utilities"""
    
    # Common SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        # SQL keywords
        r"\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b",
        # Comments
        r"(--|#|\/\*|\*\/)",
        # Common injections
        r"(\b(or|and)\b\s*\d+\s*=\s*\d+)",
        r"(';|--;|';--)",
        # String terminators
        r"('|\"|`)\s*(;|--|\||&&)",
        # System functions
        r"\b(sleep|benchmark|waitfor|pg_sleep)\b\s*\(",
        # File operations
        r"\b(load_file|into\s+outfile|into\s+dumpfile)\b",
        # Stacked queries
        r";\s*(select|insert|update|delete|drop)",
        # Hex encoding
        r"0x[0-9a-fA-F]+",
        # Special characters in suspicious patterns
        r"(\||&&|<|>|!|~|\^)",
    ]
    
    # Whitelist of allowed characters for different input types
    INPUT_WHITELISTS = {
        "alphanumeric": r"^[a-zA-Z0-9]+$",
        "alphanumeric_space": r"^[a-zA-Z0-9\s]+$",
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "uuid": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "numeric": r"^[0-9]+$",
        "decimal": r"^[0-9]+\.?[0-9]*$",
        "date": r"^\d{4}-\d{2}-\d{2}$",
        "datetime": r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}",
        "boolean": r"^(true|false|True|False|1|0)$",
        "sort_order": r"^(asc|desc|ASC|DESC)$",
        "identifier": r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    }
    
    def __init__(self):
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.SQL_INJECTION_PATTERNS
        ]
    
    def detect_sql_injection(self, value: Any) -> bool:
        """
        Detect potential SQL injection in input value
        
        Returns:
            True if SQL injection detected, False otherwise
        """
        if value is None:
            return False
        
        # Convert to string for analysis
        str_value = str(value)
        
        # Check against patterns
        for pattern in self.compiled_patterns:
            if pattern.search(str_value):
                logger.warning(f"Potential SQL injection detected: {str_value[:100]}")
                return True
        
        return False
    
    def sanitize_input(
        self,
        value: Any,
        input_type: str = "alphanumeric_space",
        max_length: Optional[int] = None
    ) -> str:
        """
        Sanitize input based on type
        
        Args:
            value: Input value to sanitize
            input_type: Type of input (from INPUT_WHITELISTS)
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError if input doesn't match expected pattern
        """
        if value is None:
            return ""
        
        str_value = str(value).strip()
        
        # Check length
        if max_length and len(str_value) > max_length:
            raise ValueError(f"Input exceeds maximum length of {max_length}")
        
        # Check whitelist pattern
        if input_type in self.INPUT_WHITELISTS:
            pattern = self.INPUT_WHITELISTS[input_type]
            if not re.match(pattern, str_value):
                raise ValueError(f"Input does not match expected pattern for {input_type}")
        
        # Additional escaping for safety
        # Note: This is a last resort - parameterized queries should be used
        str_value = str_value.replace("'", "''")
        str_value = str_value.replace("\\", "\\\\")
        
        return str_value
    
    def validate_column_name(self, column_name: str, allowed_columns: List[str]) -> str:
        """
        Validate column name against whitelist
        
        Args:
            column_name: Column name to validate
            allowed_columns: List of allowed column names
            
        Returns:
            Validated column name
            
        Raises:
            ValueError if column name is not allowed
        """
        if column_name not in allowed_columns:
            raise ValueError(f"Column '{column_name}' is not allowed")
        
        # Additional validation
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", column_name):
            raise ValueError("Invalid column name format")
        
        return column_name
    
    def validate_table_name(self, table_name: str, allowed_tables: List[str]) -> str:
        """
        Validate table name against whitelist
        
        Args:
            table_name: Table name to validate
            allowed_tables: List of allowed table names
            
        Returns:
            Validated table name
            
        Raises:
            ValueError if table name is not allowed
        """
        if table_name not in allowed_tables:
            raise ValueError(f"Table '{table_name}' is not allowed")
        
        # Additional validation
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            raise ValueError("Invalid table name format")
        
        return table_name
    
    def validate_sort_params(
        self,
        sort_by: str,
        sort_order: str,
        allowed_columns: List[str]
    ) -> tuple[str, str]:
        """
        Validate sorting parameters
        
        Args:
            sort_by: Column to sort by
            sort_order: Sort order (asc/desc)
            allowed_columns: List of allowed column names
            
        Returns:
            Tuple of (validated_column, validated_order)
        """
        # Validate column
        sort_by = self.validate_column_name(sort_by, allowed_columns)
        
        # Validate order
        sort_order = self.sanitize_input(sort_order, "sort_order")
        
        return sort_by, sort_order
    
    def create_safe_like_pattern(self, search_term: str) -> str:
        """
        Create safe LIKE pattern for searches
        
        Args:
            search_term: User search input
            
        Returns:
            Safe pattern for LIKE queries
        """
        # Escape special LIKE characters
        safe_term = search_term.replace("\\", "\\\\")
        safe_term = safe_term.replace("%", "\\%")
        safe_term = safe_term.replace("_", "\\_")
        safe_term = safe_term.replace("[", "\\[")
        
        # Remove any SQL injection attempts
        if self.detect_sql_injection(safe_term):
            raise ValueError("Invalid search term")
        
        return f"%{safe_term}%"
    
    def validate_json_input(self, json_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JSON input against schema
        
        Args:
            json_data: JSON data to validate
            schema: Expected schema with types and constraints
            
        Returns:
            Validated data
        """
        validated = {}
        
        for field, constraints in schema.items():
            if field not in json_data and constraints.get("required", False):
                raise ValueError(f"Required field '{field}' is missing")
            
            if field in json_data:
                value = json_data[field]
                field_type = constraints.get("type", "string")
                
                # Type validation
                if field_type == "string":
                    if not isinstance(value, str):
                        raise ValueError(f"Field '{field}' must be a string")
                    
                    # Check pattern if specified
                    pattern = constraints.get("pattern")
                    if pattern and pattern in self.INPUT_WHITELISTS:
                        value = self.sanitize_input(value, pattern)
                    
                    # Check for SQL injection
                    if self.detect_sql_injection(value):
                        raise ValueError(f"Invalid value for field '{field}'")
                
                elif field_type == "integer":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Field '{field}' must be an integer")
                
                elif field_type == "boolean":
                    if not isinstance(value, bool):
                        raise ValueError(f"Field '{field}' must be a boolean")
                
                # Length constraints
                if "max_length" in constraints and isinstance(value, str):
                    if len(value) > constraints["max_length"]:
                        raise ValueError(
                            f"Field '{field}' exceeds maximum length of {constraints['max_length']}"
                        )
                
                validated[field] = value
        
        return validated


class SafeQueryBuilder:
    """Build safe SQLAlchemy queries with validation"""
    
    def __init__(self, model):
        self.model = model
        self.validator = SQLInjectionPrevention()
        
        # Get allowed columns from model
        mapper = inspect(model)
        self.allowed_columns = [col.key for col in mapper.columns]
    
    def build_filter_query(
        self,
        base_query: Select,
        filters: Dict[str, Any],
        allowed_filters: Optional[List[str]] = None
    ) -> Select:
        """
        Build query with safe filters
        
        Args:
            base_query: Base SQLAlchemy query
            filters: Dictionary of filters to apply
            allowed_filters: Whitelist of allowed filter fields
            
        Returns:
            Query with filters applied
        """
        if allowed_filters is None:
            allowed_filters = self.allowed_columns
        
        for field, value in filters.items():
            # Validate field name
            if field not in allowed_filters:
                logger.warning(f"Attempted to filter by non-allowed field: {field}")
                continue
            
            # Check for SQL injection in value
            if self.validator.detect_sql_injection(value):
                raise ValueError(f"Invalid filter value for field '{field}'")
            
            # Apply filter based on type
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                
                if isinstance(value, list):
                    # IN clause
                    for v in value:
                        if self.validator.detect_sql_injection(v):
                            raise ValueError(f"Invalid filter value in list for field '{field}'")
                    base_query = base_query.where(column.in_(value))
                
                elif isinstance(value, dict):
                    # Range queries
                    if "min" in value:
                        base_query = base_query.where(column >= value["min"])
                    if "max" in value:
                        base_query = base_query.where(column <= value["max"])
                
                else:
                    # Exact match
                    base_query = base_query.where(column == value)
        
        return base_query
    
    def build_search_query(
        self,
        base_query: Select,
        search_term: str,
        search_fields: List[str]
    ) -> Select:
        """
        Build safe search query
        
        Args:
            base_query: Base SQLAlchemy query
            search_term: Search term
            search_fields: Fields to search in
            
        Returns:
            Query with search conditions
        """
        # Validate search fields
        for field in search_fields:
            if field not in self.allowed_columns:
                raise ValueError(f"Invalid search field: {field}")
        
        # Create safe search pattern
        pattern = self.validator.create_safe_like_pattern(search_term)
        
        # Build OR conditions
        conditions = []
        for field in search_fields:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                conditions.append(column.ilike(pattern))
        
        if conditions:
            from sqlalchemy import or_
            base_query = base_query.where(or_(*conditions))
        
        return base_query
    
    def build_sort_query(
        self,
        base_query: Select,
        sort_by: str,
        sort_order: str = "asc"
    ) -> Select:
        """
        Build query with safe sorting
        
        Args:
            base_query: Base SQLAlchemy query
            sort_by: Column to sort by
            sort_order: Sort order (asc/desc)
            
        Returns:
            Query with sorting applied
        """
        # Validate sort parameters
        sort_by, sort_order = self.validator.validate_sort_params(
            sort_by,
            sort_order,
            self.allowed_columns
        )
        
        # Apply sorting
        if hasattr(self.model, sort_by):
            column = getattr(self.model, sort_by)
            if sort_order.lower() == "desc":
                base_query = base_query.order_by(column.desc())
            else:
                base_query = base_query.order_by(column.asc())
        
        return base_query


# Middleware for SQL injection prevention
class SQLInjectionMiddleware:
    """Middleware to check for SQL injection in requests"""
    
    def __init__(self):
        self.validator = SQLInjectionPrevention()
        # Paths to skip validation (e.g., file uploads)
        self.skip_paths = ["/upload", "/files"]
    
    async def __call__(self, request, call_next):
        """Check request for SQL injection attempts"""
        # Skip certain paths
        if any(request.url.path.startswith(path) for path in self.skip_paths):
            return await call_next(request)
        
        # Check query parameters
        for key, value in request.query_params.items():
            if self.validator.detect_sql_injection(value):
                logger.warning(
                    f"SQL injection attempt in query param '{key}' "
                    f"from {request.client.host if request.client else 'unknown'}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request parameters"
                )
        
        # Check path parameters
        for key, value in request.path_params.items():
            if self.validator.detect_sql_injection(value):
                logger.warning(
                    f"SQL injection attempt in path param '{key}' "
                    f"from {request.client.host if request.client else 'unknown'}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request parameters"
                )
        
        # Process request
        response = await call_next(request)
        return response


# Utility functions
def escape_sql_identifier(identifier: str) -> str:
    """
    Escape SQL identifier (table/column name)
    
    Note: This should only be used when parameterized queries cannot be used
    """
    # Remove any quotes
    identifier = identifier.replace('"', '').replace("'", '').replace("`", '')
    
    # Validate format
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError("Invalid SQL identifier")
    
    # Quote with double quotes (PostgreSQL style)
    return f'"{identifier}"'


def validate_sql_value(value: Any, expected_type: type) -> Any:
    """
    Validate and cast SQL value to expected type
    
    Args:
        value: Value to validate
        expected_type: Expected Python type
        
    Returns:
        Validated and cast value
    """
    if value is None:
        return None
    
    if expected_type == int:
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError("Invalid integer value")
    
    elif expected_type == float:
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError("Invalid decimal value")
    
    elif expected_type == bool:
        if isinstance(value, bool):
            return value
        if str(value).lower() in ["true", "1", "yes", "on"]:
            return True
        if str(value).lower() in ["false", "0", "no", "off"]:
            return False
        raise ValueError("Invalid boolean value")
    
    elif expected_type == str:
        return str(value)
    
    else:
        raise ValueError(f"Unsupported type: {expected_type}")


# Example usage
"""
# In your API endpoint
validator = SQLInjectionPrevention()

# Validate search input
try:
    safe_search = validator.create_safe_like_pattern(search_term)
except ValueError:
    raise HTTPException(400, "Invalid search term")

# Build safe query
query_builder = SafeQueryBuilder(User)
query = select(User)
query = query_builder.build_search_query(query, search_term, ["email", "full_name"])
query = query_builder.build_sort_query(query, sort_by, sort_order)
"""
"""CSV schema validation and parsing utilities."""

import pandas as pd
from pathlib import Path
from typing import Any
from decimal import Decimal


# Required columns in the CSV
REQUIRED_COLUMNS = {
    "client_legal_name": str,
    "tax_year": int,
    "project_id": str,
    "project_name": str,
    "project_status": str,
    "qualified_wages": float,
}

# Optional columns with defaults
OPTIONAL_COLUMNS = {
    "qualified_contractors": (float, 0.0),
    "qualified_supplies": (float, 0.0),
    "qualified_cloud": (float, 0.0),
    "federal_credit": (float, None),
    "project_description_facts": (str, ""),
    "uncertainty_facts": (str, ""),
    "experimentation_facts": (str, ""),
    "technology_facts": (str, ""),
    "employees": (str, ""),
    "man_hours": (int, None),
    "contract_type": (str, ""),
}

VALID_PROJECT_STATUSES = {"Qualified", "Non-qualified"}


class CSVValidationError(Exception):
    """Raised when CSV validation fails."""
    pass


def validate_csv_schema(csv_path: Path) -> pd.DataFrame:
    """
    Validate CSV schema and return DataFrame.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Validated DataFrame
        
    Raises:
        CSVValidationError: If validation fails
    """
    if not csv_path.exists():
        raise CSVValidationError(f"CSV file not found: {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise CSVValidationError(f"Failed to read CSV: {e}")
    
    # Check required columns
    missing_cols = set(REQUIRED_COLUMNS.keys()) - set(df.columns)
    if missing_cols:
        raise CSVValidationError(
            f"Missing required columns: {', '.join(sorted(missing_cols))}"
        )
    
    # Add optional columns with defaults if missing
    for col, (dtype, default) in OPTIONAL_COLUMNS.items():
        if col not in df.columns:
            df[col] = default
    
    # Validate project_status values
    invalid_statuses = set(df["project_status"].unique()) - VALID_PROJECT_STATUSES
    if invalid_statuses:
        raise CSVValidationError(
            f"Invalid project_status values: {invalid_statuses}. "
            f"Must be one of: {VALID_PROJECT_STATUSES}"
        )
    
    # Type validation for required columns
    try:
        df["tax_year"] = df["tax_year"].astype(int)
        df["qualified_wages"] = df["qualified_wages"].astype(float)
    except (ValueError, TypeError) as e:
        raise CSVValidationError(f"Type conversion error: {e}")
    
    # Type validation for optional numeric columns
    for col in ["qualified_contractors", "qualified_supplies", "qualified_cloud"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    
    if "federal_credit" in df.columns:
        df["federal_credit"] = pd.to_numeric(df["federal_credit"], errors="coerce")
    
    if "man_hours" in df.columns:
        df["man_hours"] = pd.to_numeric(df["man_hours"], errors="coerce")
    
    return df


def parse_semicolon_list(value: Any) -> list[str]:
    """
    Parse semicolon-separated string into list of non-empty strings.
    
    Args:
        value: String value or None
        
    Returns:
        List of trimmed, non-empty strings
    """
    if pd.isna(value) or not value:
        return []
    
    items = str(value).split(";")
    return [item.strip() for item in items if item.strip()]


def safe_decimal(value: Any) -> Decimal:
    """
    Safely convert value to Decimal, returning 0 for None/NaN.
    
    Args:
        value: Numeric value or None
        
    Returns:
        Decimal value
    """
    if pd.isna(value) or value is None:
        return Decimal("0")
    return Decimal(str(value))

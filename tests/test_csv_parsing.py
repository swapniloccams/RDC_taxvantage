"""Tests for CSV parsing and validation."""

import pytest
import pandas as pd
from pathlib import Path
from decimal import Decimal

from src.schema import (
    validate_csv_schema,
    parse_semicolon_list,
    safe_decimal,
    CSVValidationError,
)


def test_parse_semicolon_list():
    """Test semicolon-separated list parsing."""
    assert parse_semicolon_list("item1; item2; item3") == ["item1", "item2", "item3"]
    assert parse_semicolon_list("  item1  ;  item2  ") == ["item1", "item2"]
    assert parse_semicolon_list("") == []
    assert parse_semicolon_list(None) == []
    assert parse_semicolon_list("single") == ["single"]


def test_safe_decimal():
    """Test safe Decimal conversion."""
    assert safe_decimal(100.50) == Decimal("100.50")
    assert safe_decimal("200.75") == Decimal("200.75")
    assert safe_decimal(None) == Decimal("0")
    assert safe_decimal(pd.NA) == Decimal("0")


def test_validate_csv_missing_required_column(tmp_path):
    """Test validation fails when required column is missing."""
    csv_path = tmp_path / "test.csv"
    
    # Missing 'project_name' column
    df = pd.DataFrame({
        "client_legal_name": ["Test Corp"],
        "tax_year": [2023],
        "project_id": ["P001"],
        "project_status": ["Qualified"],
        "qualified_wages": [100000],
    })
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(CSVValidationError, match="Missing required columns"):
        validate_csv_schema(csv_path)


def test_validate_csv_invalid_status(tmp_path):
    """Test validation fails with invalid project status."""
    csv_path = tmp_path / "test.csv"
    
    df = pd.DataFrame({
        "client_legal_name": ["Test Corp"],
        "tax_year": [2023],
        "project_id": ["P001"],
        "project_name": ["Test Project"],
        "project_status": ["InvalidStatus"],  # Invalid
        "qualified_wages": [100000],
    })
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(CSVValidationError, match="Invalid project_status"):
        validate_csv_schema(csv_path)


def test_validate_csv_success(tmp_path):
    """Test successful CSV validation."""
    csv_path = tmp_path / "test.csv"
    
    df = pd.DataFrame({
        "client_legal_name": ["Test Corp"],
        "tax_year": [2023],
        "project_id": ["P001"],
        "project_name": ["Test Project"],
        "project_status": ["Qualified"],
        "qualified_wages": [100000],
    })
    df.to_csv(csv_path, index=False)
    
    result = validate_csv_schema(csv_path)
    assert len(result) == 1
    assert result["client_legal_name"].iloc[0] == "Test Corp"
    assert result["tax_year"].iloc[0] == 2023

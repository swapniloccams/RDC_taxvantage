"""Tests for deterministic computations."""

import pytest
from decimal import Decimal

from src.compute import (
    calculate_total_qres,
    calculate_federal_credit,
)


def test_calculate_total_qres():
    """Test total QRES calculation."""
    result = calculate_total_qres(
        Decimal("100000"),
        Decimal("50000"),
        Decimal("10000"),
        Decimal("5000"),
    )
    assert result == Decimal("165000")


def test_calculate_total_qres_with_zeros():
    """Test total QRES with some zero values."""
    result = calculate_total_qres(
        Decimal("100000"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    )
    assert result == Decimal("100000")


def test_calculate_federal_credit_simple():
    """Test federal credit calculation (simplified)."""
    total_qres = Decimal("100000")
    credit = calculate_federal_credit(total_qres)
    
    # Default 20% rate
    assert credit == Decimal("20000.00")


def test_calculate_federal_credit_with_base():
    """Test federal credit with base amount."""
    total_qres = Decimal("100000")
    base_amount = Decimal("60000")
    
    credit = calculate_federal_credit(total_qres, base_amount=base_amount)
    
    # 20% of incremental (100000 - 60000 = 40000)
    assert credit == Decimal("8000.00")


def test_calculate_federal_credit_below_base():
    """Test federal credit when QRES below base."""
    total_qres = Decimal("50000")
    base_amount = Decimal("100000")
    
    credit = calculate_federal_credit(total_qres, base_amount=base_amount)
    
    # No credit when below base
    assert credit == Decimal("0")


def test_decimal_precision():
    """Test that calculations maintain Decimal precision."""
    result = calculate_total_qres(
        Decimal("100000.12"),
        Decimal("50000.34"),
        Decimal("10000.56"),
        Decimal("5000.78"),
    )
    assert result == Decimal("165001.80")
    assert isinstance(result, Decimal)

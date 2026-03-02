"""Tests for Pydantic schema models."""

import pytest
from decimal import Decimal

from src.schema import (
    ReportMeta,
    Project,
    ProjectFacts,
    Expenditure,
    ReportData,
)


def test_report_meta_creation():
    """Test ReportMeta model creation."""
    meta = ReportMeta(
        client_company="Test Corp",
        years=[2023, 2024],
    )
    assert meta.client_company == "Test Corp"
    assert meta.years == [2023, 2024]
    assert meta.boilerplate_version == "v1.0"


def test_project_creation():
    """Test Project model creation."""
    facts = ProjectFacts(
        description_bullets=["Fact 1", "Fact 2"],
        uncertainty_bullets=["Uncertainty 1"],
        experimentation_bullets=["Experiment 1"],
        technology_bullets=["Tech 1"],
    )
    
    project = Project(
        project_id="P001",
        project_name="Test Project",
        status="Qualified",
        qualified_wages=Decimal("100000"),
        project_facts=facts,
        federal_credit=Decimal("20000"),
    )
    
    assert project.project_id == "P001"
    assert project.status == "Qualified"
    assert project.qualified_wages == Decimal("100000")
    assert len(project.project_facts.description_bullets) == 2


def test_project_invalid_status():
    """Test Project validation fails with invalid status."""
    facts = ProjectFacts()
    
    with pytest.raises(ValueError):
        Project(
            project_id="P001",
            project_name="Test",
            status="InvalidStatus",  # Should fail
            qualified_wages=Decimal("100000"),
            project_facts=facts,
            federal_credit=Decimal("20000"),
        )


def test_expenditure_decimal_conversion():
    """Test Expenditure converts values to Decimal."""
    exp = Expenditure(
        year=2023,
        qualified_wages=100000.50,  # Float input
        total_qres=165000.75,
        federal_credit=33000.15,
    )
    
    assert isinstance(exp.qualified_wages, Decimal)
    assert exp.qualified_wages == Decimal("100000.50")


def test_report_data_year_range():
    """Test ReportData year range formatting."""
    meta = ReportMeta(client_company="Test", years=[2022, 2023, 2024])
    data = ReportData(report_meta=meta, projects=[])
    
    assert data.get_year_range_str() == "2022-2024"
    
    # Single year
    meta_single = ReportMeta(client_company="Test", years=[2023])
    data_single = ReportData(report_meta=meta_single, projects=[])
    
    assert data_single.get_year_range_str() == "2023"

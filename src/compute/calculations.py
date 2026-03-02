"""Deterministic calculations for R&D expenditures and credits."""

from decimal import Decimal
from typing import Optional


def calculate_total_qres(
    qualified_wages: Decimal,
    qualified_contractors: Decimal,
    qualified_supplies: Decimal,
    qualified_cloud: Decimal,
) -> Decimal:
    """
    Calculate total Qualified Research Expenditures.
    
    Args:
        qualified_wages: QRE from wages
        qualified_contractors: QRE from contractors
        qualified_supplies: QRE from supplies
        qualified_cloud: QRE from cloud computing
        
    Returns:
        Total QRES
    """
    return qualified_wages + qualified_contractors + qualified_supplies + qualified_cloud


def calculate_federal_credit(
    total_qres: Decimal,
    credit_rate: Decimal = Decimal("0.20"),
    base_amount: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculate federal R&D tax credit.
    
    Uses simplified calculation: credit_rate * total_qres
    In production, this would use the actual IRS calculation method
    with base amount and fixed-base percentage.
    
    Args:
        total_qres: Total qualified research expenditures
        credit_rate: Credit rate (default 20% for regular credit)
        base_amount: Optional base amount for calculation
        
    Returns:
        Federal credit amount
    """
    if base_amount is not None:
        # Simplified: credit on amount exceeding base
        incremental = max(Decimal("0"), total_qres - base_amount)
        return credit_rate * incremental
    
    # Simplified: flat rate on total QRES
    return credit_rate * total_qres


def aggregate_expenditures_by_year(projects: list[dict]) -> dict[int, dict[str, Decimal]]:
    """
    Aggregate project expenditures by year.
    
    Args:
        projects: List of project dictionaries with financial data
        
    Returns:
        Dictionary mapping year to aggregated expenditures
    """
    year_totals: dict[int, dict[str, Decimal]] = {}
    
    for project in projects:
        year = project["year"]
        
        if year not in year_totals:
            year_totals[year] = {
                "qualified_wages": Decimal("0"),
                "qualified_contractors": Decimal("0"),
                "qualified_supplies": Decimal("0"),
                "qualified_cloud": Decimal("0"),
                "total_qres": Decimal("0"),
                "federal_credit": Decimal("0"),
            }
        
        year_totals[year]["qualified_wages"] += project.get("qualified_wages", Decimal("0"))
        year_totals[year]["qualified_contractors"] += project.get("qualified_contractors", Decimal("0"))
        year_totals[year]["qualified_supplies"] += project.get("qualified_supplies", Decimal("0"))
        year_totals[year]["qualified_cloud"] += project.get("qualified_cloud", Decimal("0"))
        year_totals[year]["federal_credit"] += project.get("federal_credit", Decimal("0"))
    
    # Calculate total QRES for each year
    for year in year_totals:
        year_totals[year]["total_qres"] = calculate_total_qres(
            year_totals[year]["qualified_wages"],
            year_totals[year]["qualified_contractors"],
            year_totals[year]["qualified_supplies"],
            year_totals[year]["qualified_cloud"],
        )
    
    return year_totals

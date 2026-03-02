"""Comprehensive QRE calculations for employee, contractor, supplies, cloud, and ASC."""

from decimal import Decimal
from typing import Dict, List


def calculate_employee_qre(study_data: dict) -> Dict:
    """
    Calculate QRE from employee-level data.
    
    Args:
        study_data: Validated RDStudyData dict
        
    Returns:
        Dict with employee_qre_schedule and total_employee_qre
    """
    employee_qre = []
    total_wages = Decimal("0")
    total_qualified = Decimal("0")
    
    for emp in study_data["employees"]:
        wages = Decimal(str(emp["w2_box_1_wages"]))
        qualified_pct = Decimal(str(emp["qualified_percentage"]))
        qualified_wages = wages * qualified_pct
        
        total_wages += wages
        total_qualified += qualified_wages
        
        employee_qre.append({
            "employee_id": emp["employee_id"],
            "employee_name": emp["employee_name"],
            "job_title": emp["job_title"],
            "department": emp["department"],
            "total_wages": wages,
            "qualified_percentage": qualified_pct,
            "qualified_wages": qualified_wages
        })
    
    return {
        "employee_qre_schedule": employee_qre,
        "total_employee_qre": total_qualified,
        "total_wages": total_wages
    }


def calculate_contractor_qre(study_data: dict) -> Dict:
    """
    Calculate QRE from contractor data with 65% rule.
    
    Args:
        study_data: Validated RDStudyData dict
        
    Returns:
        Dict with contractor_qre_schedule and total_contractor_qre
    """
    contractor_qre = []
    total_paid = Decimal("0")
    total_eligible = Decimal("0")
    
    for contractor in study_data["contractors"]:
        amount = Decimal(str(contractor["total_amount_paid"]))
        qualified_pct = Decimal(str(contractor["qualified_percentage"]))
        qualified_amount = amount * qualified_pct
        
        # Apply 65% rule if applicable
        if contractor["contract_research_65_percent_rule_applies"]:
            eligible_amount = qualified_amount * Decimal("0.65")
        else:
            eligible_amount = qualified_amount
        
        total_paid += amount
        total_eligible += eligible_amount
        
        contractor_qre.append({
            "vendor_id": contractor["vendor_id"],
            "vendor_name": contractor["vendor_name"],
            "description_of_work": contractor["description_of_work"],
            "total_paid": amount,
            "qualified_percentage": qualified_pct,
            "qualified_amount": qualified_amount,
            "apply_65_rule": contractor["contract_research_65_percent_rule_applies"],
            "eligible_amount": eligible_amount
        })
    
    return {
        "contractor_qre_schedule": contractor_qre,
        "total_contractor_qre": total_eligible,
        "total_paid": total_paid
    }


def calculate_supplies_cloud_qre(study_data: dict) -> Dict:
    """
    Calculate supplies and cloud QRE.
    
    Args:
        study_data: Validated RDStudyData dict
        
    Returns:
        Dict with supplies and cloud schedules and totals
    """
    # Supplies
    supplies_qre = []
    total_supplies = Decimal("0")
    
    for supply in study_data["supplies"]:
        amount = Decimal(str(supply["amount"]))
        qualified_pct = Decimal(str(supply["qualified_percentage"]))
        qualified_amount = amount * qualified_pct
        total_supplies += qualified_amount
        
        supplies_qre.append({
            "supply_id": supply["supply_id"],
            "description": supply["description"],
            "vendor": supply["vendor"],
            "invoice_reference": supply["invoice_reference"],
            "amount": amount,
            "qualified_percentage": qualified_pct,
            "qualified_amount": qualified_amount
        })
    
    # Cloud
    cloud_qre = []
    total_cloud = Decimal("0")
    
    for cloud in study_data["cloud_computing"]:
        amount = Decimal(str(cloud["amount"]))
        qualified_pct = Decimal(str(cloud["qualified_percentage"]))
        qualified_amount = amount * qualified_pct
        total_cloud += qualified_amount
        
        cloud_qre.append({
            "cloud_id": cloud["cloud_id"],
            "provider": cloud["provider"],
            "service_category": cloud["service_category"],
            "billing_reference": cloud["billing_reference"],
            "amount": amount,
            "qualified_percentage": qualified_pct,
            "qualified_amount": qualified_amount
        })
    
    return {
        "supplies_qre_schedule": supplies_qre,
        "cloud_qre_schedule": cloud_qre,
        "total_supplies_qre": total_supplies,
        "total_cloud_qre": total_cloud
    }


def calculate_asc_credit(current_qre: Decimal, study_data: dict) -> Dict:
    """
    Calculate ASC credit with prior years.
    
    Args:
        current_qre: Current year total QRE
        study_data: Validated RDStudyData dict
        
    Returns:
        Dict with ASC computation details
    """
    asc_inputs = study_data["asc_calculation_inputs"]["qre_prior_years_override"]
    
    if asc_inputs["enabled"]:
        year_1 = Decimal(str(asc_inputs["year_minus_1_qre"]))
        year_2 = Decimal(str(asc_inputs["year_minus_2_qre"]))
        year_3 = Decimal(str(asc_inputs["year_minus_3_qre"]))
    else:
        # If not provided, use zeros (simplified - could calculate from gross receipts)
        year_1 = year_2 = year_3 = Decimal("0")
    
    # ASC calculation
    avg_prior_3 = (year_1 + year_2 + year_3) / 3
    base_amount = avg_prior_3 * Decimal("0.50")
    excess_qre = max(current_qre - base_amount, Decimal("0"))
    credit = excess_qre * Decimal("0.14")
    
    return {
        "current_year_qre": current_qre,
        "prior_year_1_qre": year_1,
        "prior_year_2_qre": year_2,
        "prior_year_3_qre": year_3,
        "average_prior_3_years": avg_prior_3,
        "base_amount": base_amount,
        "excess_qre": excess_qre,
        "credit_rate": "14%",
        "federal_credit": credit
    }


def calculate_all_qre(study_data: dict) -> Dict:
    """
    Calculate all QRE components and ASC credit.
    
    Args:
        study_data: Validated RDStudyData dict
        
    Returns:
        Dict with all calculations
    """
    # Calculate each component
    employee_results = calculate_employee_qre(study_data)
    contractor_results = calculate_contractor_qre(study_data)
    supplies_cloud_results = calculate_supplies_cloud_qre(study_data)
    
    # Total QRE
    total_qre = (
        employee_results["total_employee_qre"] +
        contractor_results["total_contractor_qre"] +
        supplies_cloud_results["total_supplies_qre"] +
        supplies_cloud_results["total_cloud_qre"]
    )
    
    # ASC credit
    asc_results = calculate_asc_credit(total_qre, study_data)
    
    # Combine all results
    return {
        **employee_results,
        **contractor_results,
        **supplies_cloud_results,
        "total_qre": total_qre,
        "asc_computation": asc_results
    }

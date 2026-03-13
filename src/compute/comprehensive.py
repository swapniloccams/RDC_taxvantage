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
    
    # Startup / payroll-tax-offset flags (default False if not present)
    business_flags = study_data.get("business_flags") or {}
    is_startup = bool(business_flags.get("is_startup", False))
    payroll_offset = bool(business_flags.get("payroll_tax_offset_eligible", False))

    return {
        "current_year_qre": current_qre,
        "prior_year_1_qre": year_1,
        "prior_year_2_qre": year_2,
        "prior_year_3_qre": year_3,
        "average_prior_3_years": avg_prior_3,
        "base_amount": base_amount,
        "excess_qre": excess_qre,
        "credit_rate": "14%",
        "federal_credit": credit,
        "is_startup": is_startup,
        "payroll_tax_offset_eligible": payroll_offset,
    }


def calculate_all_qre_multi_year(multi_year_study_data: list) -> list:
    """
    Run calculate_all_qre() for each year in a multi-year study.

    Args:
        multi_year_study_data: List of RDStudyData dicts, one per tax year (oldest → newest).

    Returns:
        List of per-year result dicts, each containing all fields from calculate_all_qre()
        plus a 'year_label' key for identification.
    """
    results = []
    for year_study in multi_year_study_data:
        year_label = year_study["study_metadata"]["tax_year"]["year_label"]
        try:
            year_result = calculate_all_qre(year_study)
            year_result["year_label"] = year_label
            year_result["client_name"] = year_study["study_metadata"]["prepared_for"]["legal_name"]
            results.append(year_result)
        except Exception as exc:
            raise ValueError(f"QRE calculation failed for tax year {year_label}: {exc}") from exc
    return results


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
    
    # Build qre_summary — mirrors blueprint qre_summary{} in Input 1
    asc_comp = asc_results
    credit_method = "Startup_Payroll" if asc_comp.get("payroll_tax_offset_eligible") else "ASC"
    qre_summary = {
        "total_qualified_wages": float(employee_results["total_employee_qre"]),
        "total_qualified_contractors": float(contractor_results["total_contractor_qre"]),
        "total_qualified_supplies": float(supplies_cloud_results["total_supplies_qre"]),
        "total_qualified_cloud": float(supplies_cloud_results["total_cloud_qre"]),
        "total_qre": float(total_qre),
        "avg_qre_prior_3_years": float(asc_comp.get("avg_prior_qre", 0)),
        "asc_base_amount": float(asc_comp.get("base_amount", 0)),
        "asc_excess_qre": float(asc_comp.get("excess_qre", 0)),
        "asc_credit": float(asc_comp.get("federal_credit", 0)),
        "credit_method_used": credit_method,
    }

    # Arithmetic cross-check — blueprint processing Step 2: "Halt if mismatch"
    component_sum = (
        qre_summary["total_qualified_wages"]
        + qre_summary["total_qualified_contractors"]
        + qre_summary["total_qualified_supplies"]
        + qre_summary["total_qualified_cloud"]
    )
    discrepancy = abs(component_sum - qre_summary["total_qre"])
    if discrepancy > 0.01:
        raise ValueError(
            f"QRE arithmetic mismatch: component sum ${component_sum:,.2f} ≠ "
            f"total_qre ${qre_summary['total_qre']:,.2f} (diff=${discrepancy:,.2f}). "
            "Blueprint processing rule: halt before generating any content. "
            "Check calculate_employee_qre / contractor / supplies functions."
        )

    # Combine all results
    return {
        **employee_results,
        **contractor_results,
        **supplies_cloud_results,
        "total_qre": total_qre,
        "asc_computation": asc_results,
        "qre_summary": qre_summary,
    }

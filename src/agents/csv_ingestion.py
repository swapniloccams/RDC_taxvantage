"""
CSVIngestionAgent - Parses single comprehensive CSV into RDStudyData.
Mapping logic handles 'row_type' to extract correct fields from shared columns.
"""

from src.agents.framework import Agent, Handoff
from src.schema.study_schema import RDStudyData
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any

# Define the computation agent handoff (lazy import to avoid circular dep if needed, but handled inside function)
# Actually, the framework handles this, but we need to define the function.

def parse_single_csv(context: dict = None) -> dict:
    """
    Parse a single CSV file with 'row_type' column into structured RDStudyData.
    
    CSV Format expectation:
    row_type, id, name_or_description, param_1, ... (generic columns mapped per type)
    """
    csv_path = context.get("csv_path")
    if not csv_path:
        return {"status": "error", "message": "No csv_path in context"}

    try:
        # Read with types specified to avoid pandas inference issues
        df = pd.read_csv(csv_path, dtype=str)
        df.fillna("", inplace=True)
        
        # Containers
        metadata = {}
        projects = []
        employees = []
        contractors = []
        supplies = []
        cloud = []
        
        for index, row in df.iterrows():
            rtype = str(row.get("row_type", "")).upper().strip()
            
            try:
                if rtype == "METADATA":
                    metadata = _parse_metadata_row(row)
                elif rtype == "PROJECT":
                    projects.append(_parse_project_row(row))
                elif rtype == "EMPLOYEE":
                    employees.append(_parse_employee_row(row))
                elif rtype == "CONTRACTOR":
                    contractors.append(_parse_contractor_row(row))
                elif rtype == "EXPENSE":
                    item = _parse_expense_row(row)
                    if item:
                        if item["type"] == "supply":
                            supplies.append(item["data"])
                        else:  # cloud
                            cloud.append(item["data"])
            except Exception as e:
                print(f"Error parsing row {index} ({rtype}): {e}")
                # Continue parsing other rows, but log warning

        # Construct RDStudyData dict
        study_dict = {
            "study_metadata": metadata.get("study_metadata", {}),
            "company_background": metadata.get("company_background", {}),
            "gross_receipts": metadata.get("gross_receipts", {}),
            "asc_calculation_inputs": metadata.get("asc_calculation_inputs", {}),
            "rd_projects": projects,
            "employees": employees,
            "contractors": contractors,
            "supplies": supplies,
            "cloud_computing": cloud,
            "qre_calculation_rules": _default_calculation_rules(),
            "output_preferences": {"format": "StudyDocument", "currency": "USD"},
            "disclosures_and_assumptions": metadata.get("disclosures", {})
        }
        
        # Validate with Pydantic
        # This is CRITICAL: it ensures the CSV produced valid intermediate JSON structure
        try:
            print("Validating Parsed Data against Schema...")
            study_obj = RDStudyData(**study_dict)
            context["study_data"] = study_obj.model_dump()
            context["input_format"] = "comprehensive_csv"
            
            return {
                "status": "success", 
                "message": "Parsed single CSV successfully",
                "counts": {
                    "projects": len(projects),
                    "employees": len(employees),
                    "contractors": len(contractors),
                    "supplies": len(supplies),
                    "cloud": len(cloud)
                }
            }
        except Exception as e:
            return {"status": "error", "message": f"Schema Validation Error: {e}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Global Parsing Error: {str(e)}"}

def _default_calculation_rules():
    return {
        "include_wages": True,
        "include_contractors": True,
        "contractor_eligibility_rate": 0.65,
        "include_supplies": True,
        "include_cloud": True,
        "allow_sampling_methodology": False,
        "include_bonus_in_wages": True
    }

def _parse_metadata_row(row):
    # Mapping based on single_file_compact.csv template
    start_date = _safe_date(row.get("param_9")) or "2024-01-01"
    end_date = start_date.replace("-01-01", "-12-31") # Simple default logic
    
    return {
        "study_metadata": {
            "prepared_for": {
                "legal_name": row.get("name_or_description", ""),
                "ein": row.get("id", ""),
                "entity_type": row.get("param_1", "C-Corp"),
                "address": row.get("param_2", ""),
                "industry": row.get("param_3", ""),
                "website": row.get("param_4", "")
            },
            "prepared_by": {
                "firm_name": row.get("param_5", ""),
                "preparer_name": row.get("param_6", ""),
                "date_prepared": "2024-04-15"
            },
            "tax_year": {
                "year_label": str(row.get("param_7", 2024)),
                "start_date": start_date,
                "end_date": end_date
            },
            "credit_method": row.get("param_8", "ASC")
        },
        "company_background": {
             "business_overview": "From CSV Metadata",
             "products_and_services": ["Software"],
             "rd_departments": ["Engineering"],
             "locations": [row.get("param_2", "")],
             "org_structure_summary": "See breakdown"
        },
        "gross_receipts": {
             "year_0": _safe_float(row.get("extra_A")),
             "year_minus_1": _safe_float(row.get("extra_B")), 
             "year_minus_2": 0.0,
             "year_minus_3": 0.0
        },
        "asc_calculation_inputs": {
            "qre_prior_years_override": {
                "enabled": True,
                "year_minus_1_qre": 0.0,
                "year_minus_2_qre": 0.0,
                "year_minus_3_qre": 0.0
            }
        },
        "disclosures": {
            "methodology_summary": row.get("notes", ""),
            "limitations": ["Estimates used where contemporaneous records unavailable"],
            "disclaimer_text": row.get("notes", "")
        }
    }

def _parse_project_row(row):
    return {
        "project_id": row.get("id"),
        "project_name": row.get("name_or_description"),
        "business_component": row.get("param_1"),
        "start_date": _safe_date(row.get("param_2")),
        "end_date": _safe_date(row.get("param_3")),
        "status": row.get("param_4") or "Ongoing",
        "technical_summary": {
            "objective": row.get("param_5", ""),
            "problem_statement": row.get("param_5", ""),
            "technical_uncertainty": row.get("param_6", ""),
            "experimentation_process": [row.get("param_7", "")],
            "hypotheses_tested": ["See experimentation process details"],
            "alternatives_considered": [],
            "results_or_outcome": "See technical summary",
            "failures_or_iterations": "Multiple iterations performed"
        },
        "four_part_test": {
            "permitted_purpose": row.get("extra_A", ""),
            "technological_in_nature": row.get("extra_B", ""),
            "elimination_of_uncertainty": row.get("param_6", ""),
            "process_of_experimentation": row.get("param_7", "")
        },
        "evidence_links": {
            "jira_links": [], "github_links": [], "design_docs": []
        }
    }

def _parse_employee_row(row):
    allocs = _parse_alloc(row.get("param_7"), "percent_of_employee_time")
    # Clean percentages
    safe_allocs = []
    for a in allocs:
        p = a["percent_of_employee_time"]
        if p > 1.0: p = p / 100.0
        safe_allocs.append({"project_id": a["project_id"], "percent_of_employee_time": p})

    return {
        "employee_id": row.get("id"),
        "employee_name": row.get("name_or_description"),
        "job_title": row.get("param_1"),
        "department": row.get("param_2"),
        "location": row.get("param_3"),
        "w2_box_1_wages": _safe_float(row.get("param_4")),
        "qualified_percentage": _safe_pct_float(row.get("param_5")),
        "qualification_basis": row.get("param_6") or "Interview",
        "project_allocation": safe_allocs
    }

def _parse_contractor_row(row):
    allocs = _parse_alloc(row.get("param_8"), "percent_of_vendor_work")
    # Clean percentages
    safe_allocs = []
    for a in allocs:
        p = a["percent_of_vendor_work"]
        if p > 1.0: p = p / 100.0
        safe_allocs.append({"project_id": a["project_id"], "percent_of_vendor_work": p})

    return {
        "vendor_id": row.get("id"),
        "vendor_name": row.get("name_or_description"),
        "description_of_work": row.get("param_1"),
        "total_amount_paid": _safe_float(row.get("param_2")),
        "qualified_percentage": _safe_pct_float(row.get("param_3")),
        "contract_research_65_percent_rule_applies": str(row.get("param_4")).upper() == "TRUE",
        "rights_and_risk": {
             "company_retains_rights": str(row.get("param_5")).upper() == "TRUE",
             "company_bears_financial_risk": str(row.get("param_6")).upper() == "TRUE",
             "supporting_contract_reference": row.get("param_7", "Contract on file")
        },
        "project_allocation": safe_allocs
    }

def _parse_expense_row(row):
    etype = str(row.get("param_1", "")).lower().strip()
    alloc_str = row.get("param_6")
    
    if "supply" in etype:
        allocs = _parse_alloc(alloc_str, "percent_of_supply_usage")
        data = {
            "supply_id": row.get("id"),
            "description": row.get("name_or_description"),
            "vendor": row.get("param_2"),
            "invoice_reference": row.get("param_3", ""),
            "amount": _safe_float(row.get("param_4")),
            "qualified_percentage": _safe_pct_float(row.get("param_5")),
            "project_allocation": allocs,
            "notes": row.get("notes", "")
        }
        return {"type": "supply", "data": data}
    elif "cloud" in etype:
        allocs = _parse_alloc(alloc_str, "percent_of_cloud_usage")
        data = {
            "cloud_id": row.get("id"),
            "provider": row.get("param_2"),
            "service_category": row.get("param_3"),
            "billing_reference": "See Records",
            "amount": _safe_float(row.get("param_4")),
            "qualified_percentage": _safe_pct_float(row.get("param_5")),
            "project_allocation": allocs,
            "notes": row.get("notes", "")
        }
        return {"type": "cloud", "data": data}
    return None

def _parse_alloc(alloc_str, key):
    # "P001:0.85;P002:0.15"
    if not alloc_str: return []
    res = []
    try:
        parts = str(alloc_str).split(";")
        for part in parts:
            if ":" in part:
                pid, pct = part.split(":")
                val = _safe_float(pct)
                if val > 1.0: val = val / 100.0 # handle 85 vs 0.85
                res.append({"project_id": pid.strip(), key: val})
    except:
        pass # ignore bad allocs
    return res

def _safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def _safe_pct_float(val):
    try:
        f = float(val)
        if f > 1.0: return f / 100.0
        return f
    except:
        return 0.0

def _safe_date(val):
    if not val or str(val).lower() == "nan": return None
    return str(val).strip()

def handoff_to_computation(context: dict = None) -> Handoff:
    from src.agents.computation import computation_agent
    return Handoff(agent=computation_agent, context=context, reason="Parsed CSV, ready for calc")

csv_ingestion_agent = Agent(
    name="CSVIngestionAgent",
    instructions="Parses single comprehensive CSV (row_type=METADATA/PROJECT/etc) into RDStudyData.",
    functions=[parse_single_csv, handoff_to_computation]
)

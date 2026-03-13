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
        metadata_ext = {}
        golden_answer = None
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
                elif rtype == "METADATA_EXT":
                    metadata_ext = _parse_metadata_ext_row(row)
                elif rtype == "METADATA_GOLDEN":
                    golden_answer = _parse_golden_row(row)
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

        # Merge METADATA_EXT into company_background and business_flags
        company_bg = metadata.get("company_background", {})
        if metadata_ext:
            # Overlay richer narrative fields from METADATA_EXT
            if metadata_ext.get("business_overview"):
                company_bg["business_overview"] = metadata_ext["business_overview"]
            if metadata_ext.get("technical_complexity"):
                company_bg["technical_complexity"] = metadata_ext["technical_complexity"]
            if metadata_ext.get("rd_culture"):
                company_bg["rd_culture"] = metadata_ext["rd_culture"]

        base_meta = metadata.get("study_metadata", {})
        prepared_for = base_meta.get("prepared_for", {})
        if metadata_ext:
            prepared_for["dba"] = metadata_ext.get("dba") or prepared_for.get("dba", "")
            prepared_for["state_of_incorporation"] = metadata_ext.get("state_of_incorporation") or prepared_for.get("state_of_incorporation", "")
            prepared_for["states_of_operation"] = metadata_ext.get("states_of_operation") or prepared_for.get("states_of_operation", [])
        base_meta["prepared_for"] = prepared_for

        business_flags = metadata_ext.get("business_flags", {}) if metadata_ext else {}

        # Construct RDStudyData dict
        study_dict = {
            "study_metadata": base_meta,
            "company_background": company_bg,
            "gross_receipts": metadata.get("gross_receipts", {}),
            "asc_calculation_inputs": metadata.get("asc_calculation_inputs", {}),
            "rd_projects": projects,
            "employees": employees,
            "contractors": contractors,
            "supplies": supplies,
            "cloud_computing": cloud,
            "qre_calculation_rules": _default_calculation_rules(),
            "output_preferences": {"format": "StudyDocument", "currency": "USD"},
            "disclosures_and_assumptions": metadata.get("disclosures", {}),
            "business_flags": business_flags,
            "golden_answer": golden_answer,
        }
        
        # Validate with Pydantic
        # This is CRITICAL: it ensures the CSV produced valid intermediate JSON structure
        try:
            print("Validating Parsed Data against Schema...")
            study_obj = RDStudyData(**study_dict)
            # Use model_dump_json → parse cycle so all enums become plain strings
            context["study_data"] = json.loads(study_obj.model_dump_json())
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
             "business_overview": (
                 f"{row.get('name_or_description', 'The company')} is a company in the "
                 f"{row.get('param_3', 'technology')} industry."
             ),
             "products_and_services": [row.get("param_3", "Software products")],
             "rd_departments": ["Engineering", "Research & Development"],
             "locations": [row.get("param_2", "")],
             "org_structure_summary": (
                 f"The company operates out of {row.get('param_2', 'its primary office')}. "
                 "R&D activities are conducted by the engineering and research teams."
             ),
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

def _parse_metadata_ext_row(row):
    """
    Parse a METADATA_EXT row — carries QA1/QA2/QA3 narrative answers and
    business identity extension fields (DBA, state_of_incorporation, etc.).

    Column mapping:
      id                   → state_of_incorporation (also used for states_of_operation)
      name_or_description  → DBA name (if any)
      param_1              → is_startup (TRUE/FALSE)
      param_2              → section_174_filed (TRUE/FALSE)
      param_3              → funded_research_exists (TRUE/FALSE)
      param_4              → payroll_tax_offset_eligible (TRUE/FALSE)
      param_5              → wages_used_for_other_credits (TRUE/FALSE)
      notes                → QA1 — business description (technical narrative)
      extra_A              → QA2 — technical complexity vs. competitors
      extra_B              → QA3 — R&D culture (ongoing vs. project-based)
    """
    def _bool(val):
        return str(val or "").upper().strip() == "TRUE"

    states_raw = row.get("id", "")
    states = [s.strip() for s in states_raw.split(";") if s.strip()] if states_raw else []

    return {
        "state_of_incorporation": states[0] if states else "",
        "states_of_operation": states,
        "dba": row.get("name_or_description", "").strip() or None,
        "business_flags": {
            "is_startup": _bool(row.get("param_1")),
            "section_174_filed": _bool(row.get("param_2")),
            "funded_research_exists": _bool(row.get("param_3")),
            "funded_by_third_party": _bool(row.get("param_3")),
            "payroll_tax_offset_eligible": _bool(row.get("param_4")),
            "wages_used_for_other_credits": _bool(row.get("param_5")),
        },
        "business_overview": row.get("notes", "").strip() or None,
        "technical_complexity": row.get("extra_A", "").strip() or None,
        "rd_culture": row.get("extra_B", "").strip() or None,
    }


def _parse_golden_row(row):
    """
    Parse a METADATA_GOLDEN row — carries the QF2 verbatim client quote
    used as the opening of the Executive Summary.

    Column mapping:
      notes  → golden_answer (QF2 verbatim quote)
    """
    return (row.get("notes") or "").strip() or None


def _parse_project_row(row):
    resolution   = row.get("param_8", "")
    failures     = row.get("param_9", "")
    uncertainty  = row.get("param_6", "")
    experimentation = row.get("param_7", "")

    # Build a combined elimination_of_uncertainty that includes both the
    # uncertainty description (param_6) and the resolution (param_8) so the
    # NarrativeAgent has everything it needs for that four-part-test section.
    elim_of_uncertainty = uncertainty
    if resolution:
        elim_of_uncertainty = f"{uncertainty}\n{resolution}".strip()

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
            "technical_uncertainty": uncertainty,
            "experimentation_process": [experimentation] if experimentation else [],
            "hypotheses_tested": ["See experimentation process details"],
            "alternatives_considered": [],
            "results_or_outcome": resolution,
            "failures_or_iterations": failures,
        },
        "four_part_test": {
            "permitted_purpose": row.get("extra_A", ""),
            "technological_in_nature": row.get("extra_B", ""),
            "elimination_of_uncertainty": elim_of_uncertainty,
            "process_of_experimentation": experimentation,
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

    activity_raw = row.get("param_8") or "direct_research"
    valid_activities = {"direct_research", "supervision", "support"}
    activity = activity_raw.lower().strip() if activity_raw.lower().strip() in valid_activities else "direct_research"

    return {
        "employee_id": row.get("id"),
        "employee_name": row.get("name_or_description"),
        "job_title": row.get("param_1"),
        "department": row.get("param_2"),
        "location": row.get("param_3"),
        "w2_box_1_wages": _safe_float(row.get("param_4")),
        "qualified_percentage": _safe_pct_float(row.get("param_5")),
        "qualification_basis": row.get("param_6") or "Interview",
        "activity_type": activity,
        "rd_activities_description": (row.get("notes") or "").strip() or None,
        "is_owner_officer": str(row.get("extra_A", "")).upper() == "TRUE",
        "source_doc": row.get("extra_B") or None,
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

    source_doc_raw = row.get("extra_A") or ""
    source_docs = [d.strip() for d in source_doc_raw.split(";") if d.strip()]

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
        "source_docs": source_docs,
        "project_allocation": safe_allocs
    }

def _parse_expense_row(row):
    etype = str(row.get("param_1", "")).lower().strip()
    alloc_str = row.get("param_6")
    
    if "supply" in etype:
        allocs = _parse_alloc(alloc_str, "percent_of_supply_usage")
        supply_doc_raw = row.get("extra_A") or ""
        supply_docs = [d.strip() for d in supply_doc_raw.split(";") if d.strip()]
        data = {
            "supply_id": row.get("id"),
            "description": row.get("name_or_description"),
            "vendor": row.get("param_2"),
            "invoice_reference": row.get("param_3", ""),
            "amount": _safe_float(row.get("param_4")),
            "qualified_percentage": _safe_pct_float(row.get("param_5")),
            "consumed_in_research": str(row.get("extra_B", "TRUE")).upper() != "FALSE",
            "source_docs": supply_docs,
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
    instructions="""You are the CSV Ingestion Agent.

Your ONLY job is:
1. Call parse_single_csv() — always, immediately, with no preamble.
2. If the result has status='success': call handoff_to_computation() immediately.
3. If the result has status='error': return a structured JSON error with the error message.

RULES:
- Do NOT summarise the parsed data.
- Do NOT ask for confirmation.
- Do NOT output prose after a successful parse.
- After a successful parse you MUST call handoff_to_computation() — no exceptions.
""",
    functions=[parse_single_csv, handoff_to_computation]
)

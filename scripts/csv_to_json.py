#!/usr/bin/env python3
"""Convert single comprehensive CSV file to validated JSON study data."""

import sys
import json
import pandas as pd
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema.study_schema import RDStudyData


def convert_single_csv_to_json(csv_path: Path, output_path: Path) -> bool:
    """
    Convert single comprehensive CSV to JSON study data.
    
    CSV Format:
    - First column is 'row_type' with values: metadata, project, employee, contractor, expense
    - Each row type has different columns populated
    
    Args:
        csv_path: Path to comprehensive CSV file
        output_path: Path to save output JSON
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"📄 Reading CSV file: {csv_path}\n")
        
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Separate by row type
        metadata_rows = df[df['row_type'] == 'metadata']
        project_rows = df[df['row_type'] == 'project']
        employee_rows = df[df['row_type'] == 'employee']
        contractor_rows = df[df['row_type'] == 'contractor']
        expense_rows = df[df['row_type'] == 'expense']
        
        print(f"📊 Found:")
        print(f"  - {len(metadata_rows)} metadata row(s)")
        print(f"  - {len(project_rows)} project(s)")
        print(f"  - {len(employee_rows)} employee(s)")
        print(f"  - {len(contractor_rows)} contractor(s)")
        print(f"  - {len(expense_rows)} expense(s)\n")
        
        # 1. Parse metadata (should be 1 row)
        print("1️⃣  Parsing metadata...")
        if len(metadata_rows) == 0:
            raise ValueError("No metadata row found. CSV must have one row with row_type='metadata'")
        
        meta = metadata_rows.iloc[0]
        
        study_metadata = {
            "prepared_for": {
                "legal_name": meta["legal_name"],
                "ein": meta["ein"],
                "entity_type": meta["entity_type"],
                "address": meta["address"],
                "industry": meta["industry"],
                "website": meta.get("website", "") if pd.notna(meta.get("website")) else ""
            },
            "prepared_by": {
                "firm_name": meta["firm_name"],
                "preparer_name": meta["preparer_name"],
                "date_prepared": meta["date_prepared"]
            },
            "tax_year": {
                "year_label": str(meta["tax_year"]),
                "start_date": meta["start_date"],
                "end_date": meta["end_date"],
                "return_type": meta.get("return_type", "Original") if pd.notna(meta.get("return_type")) else "Original"
            },
            "credit_method": meta.get("credit_method", "ASC") if pd.notna(meta.get("credit_method")) else "ASC",
            "notes": ""
        }
        
        company_background = {
            "business_overview": meta["business_overview"],
            "products_and_services": [s.strip() for s in meta["products_and_services"].split(";")],
            "rd_departments": [s.strip() for s in meta["rd_departments"].split(";")],
            "locations": [s.strip() for s in meta["locations"].split(";")],
            "org_structure_summary": meta["org_structure_summary"]
        }
        
        gross_receipts = {
            "year_0": float(meta["gross_receipts_year_0"]),
            "year_minus_1": float(meta["gross_receipts_year_minus_1"]),
            "year_minus_2": float(meta["gross_receipts_year_minus_2"]),
            "year_minus_3": float(meta["gross_receipts_year_minus_3"])
        }
        print("   ✓ Metadata parsed")
        
        # 2. Parse projects
        print("2️⃣  Parsing projects...")
        rd_projects = []
        
        for _, row in project_rows.iterrows():
            rd_projects.append({
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "business_component": row["business_component"],
                "start_date": row.get("project_start_date") if pd.notna(row.get("project_start_date")) else None,
                "end_date": row.get("project_end_date") if pd.notna(row.get("project_end_date")) else None,
                "status": row.get("status", "Ongoing"),
                "technical_summary": {
                    "objective": row["objective"],
                    "problem_statement": row["problem_statement"],
                    "technical_uncertainty": row["technical_uncertainty"],
                    "hypotheses_tested": [s.strip() for s in row["hypotheses_tested"].split(";")],
                    "experimentation_process": [s.strip() for s in row["experimentation_process"].split(";")],
                    "alternatives_considered": [s.strip() for s in row["alternatives_considered"].split(";")],
                    "results_or_outcome": row.get("results_or_outcome", ""),
                    "failures_or_iterations": row.get("failures_or_iterations", "")
                },
                "four_part_test": {
                    "permitted_purpose": row["permitted_purpose"],
                    "technological_in_nature": row["technological_in_nature"],
                    "elimination_of_uncertainty": row["elimination_of_uncertainty"],
                    "process_of_experimentation": row["process_of_experimentation"]
                },
                "evidence_links": {
                    "jira_links": [s.strip() for s in row.get("evidence_jira", "").split(";") if s.strip()],
                    "github_links": [s.strip() for s in row.get("evidence_github", "").split(";") if s.strip()],
                    "design_docs": [s.strip() for s in row.get("evidence_design_docs", "").split(";") if s.strip()],
                    "test_reports": [],
                    "deployment_logs": [],
                    "other_supporting_docs": []
                }
            })
        print(f"   ✓ {len(rd_projects)} projects parsed")
        
        # 3. Parse employees
        print("3️⃣  Parsing employees...")
        employees = []
        
        for _, row in employee_rows.iterrows():
            # Parse project allocations: "P001:0.85;P002:0.15"
            allocations = []
            if pd.notna(row.get("project_allocations")):
                for alloc in row["project_allocations"].split(";"):
                    if ":" in alloc:
                        proj_id, pct = alloc.split(":")
                        allocations.append({
                            "project_id": proj_id.strip(),
                            "percent_of_employee_time": float(pct)
                        })
            
            employees.append({
                "employee_id": row["employee_id"],
                "employee_name": row["employee_name"],
                "job_title": row["job_title"],
                "department": row["department"],
                "location": row["location"],
                "w2_box_1_wages": float(row["w2_box_1_wages"]),
                "qualified_percentage": float(row["qualified_percentage"]),
                "qualification_basis": row.get("qualification_basis", "Interview") if pd.notna(row.get("qualification_basis")) else "Interview",
                "project_allocation": allocations,
                "notes": row.get("notes", "") if pd.notna(row.get("notes")) else ""
            })
        print(f"   ✓ {len(employees)} employees parsed")
        
        # 4. Parse contractors
        print("4️⃣  Parsing contractors...")
        contractors = []
        
        for _, row in contractor_rows.iterrows():
            allocations = []
            if pd.notna(row.get("project_allocations")):
                for alloc in row["project_allocations"].split(";"):
                    if ":" in alloc:
                        proj_id, pct = alloc.split(":")
                        allocations.append({
                            "project_id": proj_id.strip(),
                            "percent_of_vendor_work": float(pct)
                        })
            
            contractors.append({
                "vendor_id": row["vendor_id"],
                "vendor_name": row["vendor_name"],
                "description_of_work": row["description_of_work"],
                "total_amount_paid": float(row["total_amount_paid"]),
                "qualified_percentage": float(row.get("qualified_percentage", 1.0)),
                "contract_research_65_percent_rule_applies": str(row["apply_65_percent_rule"]).lower() == "true",
                "rights_and_risk": {
                    "company_retains_rights": str(row["company_retains_rights"]).lower() == "true",
                    "company_bears_financial_risk": str(row["company_bears_risk"]).lower() == "true",
                    "supporting_contract_reference": row["contract_reference"]
                },
                "project_allocation": allocations if allocations else [{"project_id": "P001", "percent_of_vendor_work": 1.0}],
                "notes": row.get("notes", "") if pd.notna(row.get("notes")) else ""
            })
        print(f"   ✓ {len(contractors)} contractors parsed")
        
        # 5. Parse expenses (supplies + cloud)
        print("5️⃣  Parsing expenses...")
        supplies = []
        cloud_computing = []
        
        for _, row in expense_rows.iterrows():
            allocations = []
            if pd.notna(row.get("project_allocations")):
                for alloc in row["project_allocations"].split(";"):
                    if ":" in alloc:
                        proj_id, pct = alloc.split(":")
                        if row["expense_type"] == "supply":
                            allocations.append({
                                "project_id": proj_id.strip(),
                                "percent_of_supply_usage": float(pct)
                            })
                        else:
                            allocations.append({
                                "project_id": proj_id.strip(),
                                "percent_of_cloud_usage": float(pct)
                            })
            
            # Default allocation if not specified
            if not allocations:
                if row["expense_type"] == "supply":
                    allocations = [{"project_id": "P001", "percent_of_supply_usage": 1.0}]
                else:
                    allocations = [{"project_id": "P001", "percent_of_cloud_usage": 1.0}]
            
            if row["expense_type"] == "supply":
                supplies.append({
                    "supply_id": row["expense_id"],
                    "description": row["description"],
                    "vendor": row["vendor"],
                    "invoice_reference": row["reference"],
                    "amount": float(row["amount"]),
                    "qualified_percentage": float(row.get("qualified_percentage", 1.0)),
                    "project_allocation": allocations,
                    "notes": row.get("notes", "") if pd.notna(row.get("notes")) else ""
                })
            else:  # cloud
                cloud_computing.append({
                    "cloud_id": row["expense_id"],
                    "provider": row["provider"],
                    "service_category": row["service_category"],
                    "billing_reference": row["reference"],
                    "amount": float(row["amount"]),
                    "qualified_percentage": float(row.get("qualified_percentage", 1.0)),
                    "project_allocation": allocations,
                    "notes": row.get("notes", "") if pd.notna(row.get("notes")) else ""
                })
        print(f"   ✓ {len(supplies)} supplies, {len(cloud_computing)} cloud services parsed")
        
        # 6. Construct full study data
        print("\n🔨 Constructing JSON structure...")
        study_data = {
            "study_metadata": study_metadata,
            "company_background": company_background,
            "gross_receipts": gross_receipts,
            "rd_projects": rd_projects,
            "employees": employees,
            "contractors": contractors,
            "supplies": supplies,
            "cloud_computing": cloud_computing,
            "qre_calculation_rules": {
                "include_wages": True,
                "include_supplies": True,
                "include_cloud": True,
                "include_contractors": True,
                "contractor_eligibility_rate": 0.65,
                "default_employee_qualification_basis": "Interview",
                "allow_sampling_methodology": False,
                "include_bonus_in_wages": True,
                "exclude_foreign_research": True
            },
            "asc_calculation_inputs": {
                "qre_prior_years_override": {
                    "enabled": True,
                    "year_minus_1_qre": float(meta.get("qre_prior_year_1", 0)),
                    "year_minus_2_qre": float(meta.get("qre_prior_year_2", 0)),
                    "year_minus_3_qre": float(meta.get("qre_prior_year_3", 0))
                }
            },
            "output_preferences": {
                "currency": "USD",
                "format": "StudyDocument",
                "include_appendices": True,
                "include_employee_detail_table": True,
                "include_vendor_detail_table": True,
                "include_project_narratives": True,
                "include_four_part_test_table": True,
                "include_form_6765_tie_out": True
            },
            "disclosures_and_assumptions": {
                "methodology_summary": meta["methodology_summary"],
                "limitations": [s.strip() for s in meta["limitations"].split(";")],
                "disclaimer_text": meta["disclaimer_text"]
            }
        }
        
        # 7. Validate with Pydantic
        print("✅ Validating against schema...")
        validated_data = RDStudyData(**study_data)
        
        # 8. Save JSON
        print(f"💾 Saving to: {output_path}")
        with open(output_path, 'w') as f:
            json.dump(validated_data.model_dump(mode='json'), f, indent=2, default=str)
        
        print("\n" + "="*60)
        print("✅ CSV TO JSON CONVERSION SUCCESSFUL!")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"  Projects: {len(rd_projects)}")
        print(f"  Employees: {len(employees)}")
        print(f"  Contractors: {len(contractors)}")
        print(f"  Supplies: {len(supplies)}")
        print(f"  Cloud Services: {len(cloud_computing)}")
        print(f"\n📄 Output: {output_path}")
        print("="*60 + "\n")
        
        return True
        
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: CSV file not found")
        print(f"   {e}\n")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Conversion failed")
        print(f"   {type(e).__name__}: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("\nUsage: python scripts/csv_to_json.py <input_csv> <output_json>")
        print("\nExample:")
        print("  python scripts/csv_to_json.py examples/comprehensive_study.csv study.json\n")
        sys.exit(1)
    
    csv_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    success = convert_single_csv_to_json(csv_path, output_path)
    sys.exit(0 if success else 1)

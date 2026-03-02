#!/usr/bin/env python3
"""Validate R&D Study JSON file against schema."""

import sys
import json
from pathlib import Path
from pydantic import ValidationError

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema.study_schema import RDStudyData


def validate_json_file(json_path: str) -> bool:
    """
    Validate JSON file against RDStudyData schema.
    
    Args:
        json_path: Path to JSON file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Read JSON file
        print(f"📄 Reading JSON file: {json_path}")
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Validate with Pydantic
        print("🔍 Validating against schema...")
        study_data = RDStudyData(**data)
        
        # Print summary
        print("\n" + "="*60)
        print("✅ JSON VALIDATION PASSED!")
        print("="*60)
        
        print(f"\n📊 Study Summary:")
        print(f"  Client: {study_data.study_metadata.prepared_for.legal_name}")
        print(f"  EIN: {study_data.study_metadata.prepared_for.ein}")
        print(f"  Entity Type: {study_data.study_metadata.prepared_for.entity_type.value}")
        print(f"  Tax Year: {study_data.study_metadata.tax_year.year_label}")
        print(f"  Credit Method: {study_data.study_metadata.credit_method.value}")
        
        print(f"\n📁 Data Counts:")
        print(f"  Projects: {len(study_data.rd_projects)}")
        print(f"  Employees: {len(study_data.employees)}")
        print(f"  Contractors: {len(study_data.contractors)}")
        print(f"  Supplies: {len(study_data.supplies)}")
        print(f"  Cloud Services: {len(study_data.cloud_computing)}")
        
        # Calculate totals
        total_wages = sum(emp.w2_box_1_wages for emp in study_data.employees)
        total_contractors = sum(c.total_amount_paid for c in study_data.contractors)
        total_supplies = sum(s.amount for s in study_data.supplies)
        total_cloud = sum(c.amount for c in study_data.cloud_computing)
        
        print(f"\n💰 Expenditure Totals:")
        print(f"  Total Wages: ${total_wages:,.2f}")
        print(f"  Total Contractors: ${total_contractors:,.2f}")
        print(f"  Total Supplies: ${total_supplies:,.2f}")
        print(f"  Total Cloud: ${total_cloud:,.2f}")
        print(f"  Grand Total: ${total_wages + total_contractors + total_supplies + total_cloud:,.2f}")
        
        print("\n" + "="*60)
        print("✅ Ready to generate IRS-compliant R&D study report!")
        print("="*60 + "\n")
        
        return True
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: File not found")
        print(f"   Path: {json_path}")
        print(f"   Please check the file path and try again.\n")
        return False
        
    except json.JSONDecodeError as e:
        print(f"\n❌ ERROR: Invalid JSON syntax")
        print(f"   {e}")
        print(f"   Line {e.lineno}, Column {e.colno}")
        print(f"\n   Tip: Check for missing commas, brackets, or quotes.\n")
        return False
        
    except ValidationError as e:
        print("\n" + "="*60)
        print("❌ JSON VALIDATION FAILED!")
        print("="*60)
        print(f"\n❌ Found {len(e.errors())} validation error(s):\n")
        
        for i, error in enumerate(e.errors(), 1):
            loc = " → ".join(str(x) for x in error['loc'])
            print(f"{i}. Location: {loc}")
            print(f"   Error: {error['msg']}")
            print(f"   Type: {error['type']}")
            if 'input' in error:
                print(f"   Input: {error['input']}")
            print()
        
        print("="*60)
        print("💡 Tips:")
        print("  - Check field names match exactly (case-sensitive)")
        print("  - Ensure all required fields are present")
        print("  - Verify data types (numbers, strings, dates)")
        print("  - Check date format: YYYY-MM-DD")
        print("  - Check EIN format: XX-XXXXXXX")
        print("  - Check ID formats: P001, E001, V001, S001, C001")
        print("="*60 + "\n")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error occurred")
        print(f"   {type(e).__name__}: {e}\n")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("\nUsage: python scripts/validate_json.py <json_file>")
        print("\nExample:")
        print("  python scripts/validate_json.py examples/sample_study.json\n")
        sys.exit(1)
    
    json_path = sys.argv[1]
    success = validate_json_file(json_path)
    sys.exit(0 if success else 1)

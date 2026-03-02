"""
Script to test CSVIngestionAgent against the single_file_compact.csv template.
"""

from src.agents.csv_ingestion import parse_single_csv
import json
import traceback

def test_ingestion():
    csv_path = "examples/single_file_compact.csv"
    context = {"csv_path": csv_path}
    
    print(f"Testing ingestion with: {csv_path}")
    
    result = parse_single_csv(context)
    
    if result["status"] == "success":
        print("✅ SUCCESS: CSV Parsed and Validated against Schema!")
        print(f"Counts: {result['counts']}")
        
        # Check computed fields
        data = context["study_data"]
        print(f"Client: {data['study_metadata']['prepared_for']['legal_name']}")
        print(f"Entities: {len(data['rd_projects'])} Projects, {len(data['employees'])} Employees")
        
        # Verify specific fields
        emp0 = data['employees'][0]
        print(f"Example Employee: {emp0['employee_name']}, Wages: {emp0['w2_box_1_wages']}")
        proj0 = data['rd_projects'][0]
        print(f"Example Project: {proj0['project_name']}")
        
    else:
        print("❌ FAILED: Ingestion Error")
        print(result["message"])

if __name__ == "__main__":
    try:
        test_ingestion()
    except Exception as e:
        traceback.print_exc()

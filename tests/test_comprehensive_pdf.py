"""
End-to-end test for Single CSV -> Comprehensive PDF pipeline.
Mimics the full agent workflow.
"""

from src.agents.csv_ingestion import parse_single_csv
from src.agents.computation import calculate_comprehensive_qre
from src.agents.render_agent import generate_comprehensive_report
from pathlib import Path
import json
import traceback

def test_pipeline():
    print("🚀 Starting End-to-End Pipeline Test")
    
    # 1. Context Setup
    csv_path = "examples/single_file_compact.csv"
    output_dir = "output/comprehensive_test"
    context = {"csv_path": csv_path, "output_dir": output_dir}
    
    # 2. Ingestion
    print(f"\n📥 1. Ingesting {csv_path}...")
    res = parse_single_csv(context)
    if res["status"] != "success":
        print(f"❌ Ingestion Failed: {res['message']}")
        return
    print(f"✅ Ingestion Complete. {res['counts']}")
    
    # 3. Computation
    print(f"\n🧮 2. Running Computations...")
    res = calculate_comprehensive_qre(context)
    if res["status"] != "success":
        print(f"❌ Computation Failed: {res['message']}")
        return
    print(f"✅ Computations Complete. Total QRE: {res['total_qre']}, Credit: {res['federal_credit']}")
    
    # 4. Rendering
    print(f"\nroot 3. Generating PDF...")
    # Add dummy logo path if needed or handle None in renderer
    # context["logo_path"] = "examples/logo.png" 
    
    res = generate_comprehensive_report(output_dir, None, context)
    if res["status"] != "success":
        print(f"❌ PDF Generation Failed: {res['message']}")
        return
    
    print(f"✅ PDF Generated: {res['pdf_path']}")
    print("\n🎉 Pipeline Verification Successful!")

if __name__ == "__main__":
    try:
        test_pipeline()
    except Exception as e:
        traceback.print_exc()

"""
Run the R&D Tax Credit pipeline for Meridian Robotics Corp.
Input: examples/meridian_robotics_answers.csv
"""
from pathlib import Path
from src.pipeline.coordinator import run_pipeline

if __name__ == "__main__":
    result = run_pipeline(
        input_path=Path("examples/meridian_robotics_answers.csv"),
        output_dir=Path("output/meridian"),
        logo_path=Path("assets/occams_logo.png"),
    )

    ctx = result.get("context", {})
    pdf = ctx.get("pdf_path") or "See output/meridian/"
    print(f"\nPDF: {pdf}")

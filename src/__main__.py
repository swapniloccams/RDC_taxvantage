"""CLI entry point for R&D report generator."""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

from src.pipeline import run_pipeline, PipelineError


def main():
    """Main CLI entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate Federal R&D Tax Credit Study PDF from CSV, JSON, or questionnaire answers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Input formats (auto-detected from file content):

  CSV data file:
    python -m src --input examples/sample.csv --out ./output

  Comprehensive study JSON:
    python -m src --input examples/sample_study.json --out ./output

  Questionnaire answers JSON  (contains "study_metadata_answers" key):
    python -m src --input examples/answers.json --out ./output

  With custom logo:
    python -m src --input examples/answers.json --out ./output --logo assets/occams_logo.png

Environment Variables:
  OPENAI_API_KEY    Required. Your OpenAI API key.
  OPENAI_MODEL      Optional. Model to use (default: gpt-4-turbo-preview).
        """,
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help=(
            "Path to input file. Accepted formats:\n"
            "  • CSV  — single-file or legacy R&D data\n"
            "  • JSON — comprehensive RDStudyData structure\n"
            "  • JSON — structured questionnaire answers (auto-detected by 'study_metadata_answers' key)"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for generated PDF, JSON artifacts, and trace log",
    )

    parser.add_argument(
        "--logo",
        type=Path,
        default=None,
        help="Optional path to Occams logo PNG (default: assets/occams_logo.png)",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Default logo path
    logo_path = args.logo
    if logo_path is None:
        default_logo = Path("assets/occams_logo.png")
        if default_logo.exists():
            logo_path = default_logo

    try:
        print("R&D Tax Credit Report Generator")
        print("=" * 60)
        print(f"Input file:       {args.input}")
        print(f"Output directory: {args.out}")
        if logo_path:
            print(f"Logo:             {logo_path}")

        results = run_pipeline(
            input_path=args.input,
            output_dir=args.out,
            logo_path=logo_path,
        )

        print("\nSUCCESS!")
        print("\nGenerated files:")
        if results.get("pdf_path"):
            print(f"  PDF Report:  {results['pdf_path']}")
        if results.get("report_json_path"):
            print(f"  Report JSON: {results['report_json_path']}")
        if results.get("trace_path"):
            print(f"  Trace Log:   {results['trace_path']}")

        sys.exit(0)

    except PipelineError as e:
        print(f"\nPIPELINE ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

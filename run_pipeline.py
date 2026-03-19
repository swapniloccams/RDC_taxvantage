"""
Generic R&D Tax Credit Pipeline Runner
=======================================
Reads OPENAI_API_KEY from .env automatically — no need to expose it in the terminal.

LLM is ALWAYS used. Every report generation goes through the full multi-agent
pipeline: IngestionAgent → ComputationAgent → NarrativeAgent → ComplianceAgent → RenderAgent.

Usage:
    # Per-project PDFs only (LLM narratives, no combined report) — DEFAULT for per-project work
    python run_pipeline.py --input examples/clearpath_robotics_2023_2024.json --output output/clearpath_robotics --per-project

    # Combined multi-year report + per-project PDFs
    python run_pipeline.py --input examples/novapulse_multiyear.json --output output/novapulse_multiyear --per-project --combined

    # Combined multi-year report only (no per-project PDFs)
    python run_pipeline.py --input examples/novapulse_multiyear.json --output output/novapulse_multiyear

    # Single-year CSV / questionnaire JSON (standard flow)
    python run_pipeline.py --input examples/meridian_robotics_answers.csv
    python run_pipeline.py --input examples/my_company.csv --output output/my_company --logo assets/occams_logo.png
"""
import argparse
import os
from pathlib import Path


def _load_env():
    """Load .env and return the cleaned API key (may be empty string)."""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
    return os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")


def _require_api_key():
    """Load .env, validate API key is set, and export it.  Exits on failure."""
    api_key = _load_env()
    if not api_key:
        raise SystemExit(
            "ERROR: OPENAI_API_KEY is not set.\n"
            "Add it to your .env file in the project root:\n"
            "  OPENAI_API_KEY=sk-proj-...\n\n"
            "LLM is required for every report — no no-LLM path exists."
        )
    os.environ["OPENAI_API_KEY"] = api_key


# ---------------------------------------------------------------------------
# Full pipeline path  (LLM narratives — always on)
# ---------------------------------------------------------------------------

def run_full_pipeline(
    input_path: Path,
    output_dir: Path,
    logo_path: Path | None,
    per_project_only: bool,
    also_combined: bool,
):
    """
    Run the full multi-agent pipeline (LLM always required).

    Modes:
      per_project_only=True,  also_combined=False  → per-project PDFs only  (--per-project)
      per_project_only=False, also_combined=False  → combined multi-year PDF only (default)
      per_project_only=True,  also_combined=True   → combined + per-project PDFs (--per-project --combined)
    """
    from src.pipeline.coordinator import run_pipeline

    print("\n" + "=" * 70)
    print("R&D TAX CREDIT PIPELINE  (LLM — always active)")
    print("=" * 70)
    print(f"\nInput  : {input_path}")
    print(f"Output : {output_dir}")
    print(f"Logo   : {logo_path or 'None (skipped)'}")
    if per_project_only and not also_combined:
        print("Mode   : per-project PDFs only (combined report skipped)")
    elif per_project_only and also_combined:
        print("Mode   : combined report + per-project PDFs")
    else:
        print("Mode   : combined multi-year report only")
    print()

    result = run_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        logo_path=logo_path,
    )

    ctx = result.get("context", {})

    # ── Combined report ────────────────────────────────────────────────────
    if not per_project_only or also_combined:
        pdf = ctx.get("pdf_path") or str(output_dir / "*.pdf")
        print(f"\nCombined PDF saved to: {pdf}")

    # ── Per-project PDFs ───────────────────────────────────────────────────
    if per_project_only or also_combined:
        multi_year_data = ctx.get("multi_year_study_data")
        multi_year_qre  = ctx.get("multi_year_qre_results")
        if not multi_year_data or not multi_year_qre:
            print(
                "\n[WARNING] Per-project reports were requested but the pipeline did not "
                "return multi_year_study_data / multi_year_qre_results in context.\n"
                "Per-project reports require a multi-year JSON input (containing 'tax_years' key)."
            )
        else:
            from src.render.project_report_builder import generate_all_project_reports

            per_project_dir = output_dir / "per_project"
            project_pdfs = generate_all_project_reports(
                multi_year_study_data=multi_year_data,
                multi_year_qre_results=multi_year_qre,
                context=ctx,
                output_dir=per_project_dir,
                logo_path=logo_path,
            )
            print(f"\nPer-project PDFs ({len(project_pdfs)}):")
            for p in project_pdfs:
                print(f"  {p}")

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the R&D Tax Credit multi-agent pipeline (LLM always active).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Per-project PDFs with full LLM narratives (most common usage)
  python run_pipeline.py --input examples/clearpath_robotics_2023_2024.json --per-project

  # Per-project PDFs + combined multi-year report
  python run_pipeline.py --input examples/novapulse_multiyear.json --per-project --combined

  # Combined multi-year report only (no per-project PDFs)
  python run_pipeline.py --input examples/novapulse_multiyear.json

  # Single-year CSV
  python run_pipeline.py --input examples/meridian_robotics_answers.csv

NOTE: LLM (OpenAI) is ALWAYS used. Set OPENAI_API_KEY in your .env file.
        """,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="Path to input file (.csv, study .json, or multi-year answers .json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        metavar="DIR",
        help="Output directory (default: output/<input_stem>/)",
    )
    parser.add_argument(
        "--logo",
        default="assets/occams_logo.png",
        metavar="FILE",
        help="Path to logo image (default: assets/occams_logo.png)",
    )
    parser.add_argument(
        "--per-project",
        action="store_true",
        default=False,
        help=(
            "Generate one PDF per project with full LLM narratives. "
            "The combined multi-year report is skipped unless you also pass --combined. "
            "Only applies to multi-year JSON inputs."
        ),
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        default=False,
        help=(
            "Also generate the combined multi-year report. "
            "Use together with --per-project to produce both outputs. "
            "Without --per-project, the combined report is always generated."
        ),
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"ERROR: Input file not found: {input_path}")

    output_dir = Path(args.output) if args.output else Path("output") / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    logo_path = Path(args.logo)
    if not logo_path.exists():
        print(f"Warning: Logo not found at '{logo_path}' — report will be generated without logo.")
        logo_path = None

    # LLM is always required — validate the key before doing anything
    _require_api_key()

    run_full_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        logo_path=logo_path,
        per_project_only=args.per_project,
        also_combined=args.combined,
    )


if __name__ == "__main__":
    main()

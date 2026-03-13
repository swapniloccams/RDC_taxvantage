"""
Generic R&D Tax Credit Pipeline Runner
=======================================
Reads OPENAI_API_KEY from .env automatically — no need to expose it in the terminal.

Usage:
    # Full pipeline (combined multi-year report + LLM narratives)
    python run_pipeline.py --input examples/novapulse_multiyear.json --output output/novapulse_multiyear

    # Full pipeline + per-project PDFs after the combined report
    python run_pipeline.py --input examples/novapulse_multiyear.json --output output/novapulse_multiyear --per-project

    # Per-project PDFs ONLY — no OpenAI API key required, runs in seconds
    python run_pipeline.py --input examples/novapulse_multiyear.json --output output/novapulse_multiyear --per-project-only

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
            "  OPENAI_API_KEY=sk-proj-..."
        )
    os.environ["OPENAI_API_KEY"] = api_key


# ---------------------------------------------------------------------------
# --per-project-only path  (no LLM — pure JSON + math + PDF)
# ---------------------------------------------------------------------------

def run_per_project_only(input_path: Path, output_dir: Path, logo_path: Path | None):
    """
    Generate one PDF per project from a multi-year JSON without any LLM calls.

    Steps:
      1. Parse & validate JSON with MultiYearStudyData schema.
      2. Compute QRE for every year directly (no agents, no OpenAI).
      3. Call generate_all_project_reports() to build the per-project PDFs.
    """
    import json
    from src.schema.study_schema import MultiYearStudyData
    from src.compute.comprehensive import calculate_all_qre_multi_year
    from src.render.project_report_builder import generate_all_project_reports

    print("\n" + "=" * 70)
    print("PER-PROJECT REPORT GENERATOR  (no LLM — parse + compute + render)")
    print("=" * 70)

    # 1. Load & validate JSON
    print(f"\nLoading: {input_path}")
    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: Invalid JSON in {input_path}: {exc}")

    if "tax_years" not in raw:
        raise SystemExit(
            "ERROR: --per-project-only requires a multi-year JSON file "
            "(must contain a 'tax_years' key). "
            "Single-year CSV/JSON files are not supported with this flag."
        )

    try:
        multi_study = MultiYearStudyData(**raw)
    except Exception as exc:
        raise SystemExit(f"ERROR: Schema validation failed: {exc}")

    # Serialise each year to plain dict (enums → strings, Decimal → float)
    year_dicts = [json.loads(yr.model_dump_json()) for yr in multi_study.tax_years]
    year_labels = [yr["study_metadata"]["tax_year"]["year_label"] for yr in year_dicts]
    client_name = year_dicts[-1]["study_metadata"]["prepared_for"]["legal_name"]

    print(f"Client : {client_name}")
    print(f"Years  : {', '.join(year_labels)}")
    print(f"Output : {output_dir}")

    # 2. Compute QRE (pure math, no LLM)
    print("\nComputing QRE for all years...")
    try:
        multi_year_qre_results = calculate_all_qre_multi_year(year_dicts)
    except Exception as exc:
        raise SystemExit(f"ERROR: QRE computation failed: {exc}")

    for yr_qre in multi_year_qre_results:
        yr = yr_qre.get("year_label", "?")
        total = yr_qre.get("total_qre", 0)
        asc = (yr_qre.get("asc_computation") or {}).get("federal_credit", 0)
        print(f"  {yr}: Total QRE = ${float(total):,.0f}  |  Federal Credit = ${float(asc):,.0f}")

    # 3. Generate per-project PDFs
    output_dir.mkdir(parents=True, exist_ok=True)
    per_project_dir = output_dir / "per_project"

    context = {
        "multi_year_study_data": year_dicts,
        "multi_year_qre_results": multi_year_qre_results,
        "study_data": year_dicts[-1],
        "is_multi_year": True,
        "multi_year_title": multi_study.study_title,
    }

    project_pdfs = generate_all_project_reports(
        multi_year_study_data=year_dicts,
        multi_year_qre_results=multi_year_qre_results,
        context=context,
        output_dir=per_project_dir,
        logo_path=logo_path,
    )

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")
    print(f"\nGenerated {len(project_pdfs)} per-project PDF(s):")
    for p in project_pdfs:
        print(f"  {p}")


# ---------------------------------------------------------------------------
# Full pipeline path  (LLM narratives + combined report)
# ---------------------------------------------------------------------------

def run_full_pipeline(
    input_path: Path,
    output_dir: Path,
    logo_path: Path | None,
    also_per_project: bool,
):
    """Run the full multi-agent pipeline (requires OPENAI_API_KEY)."""
    from src.pipeline.coordinator import run_pipeline

    print(f"\nInput  : {input_path}")
    print(f"Output : {output_dir}")
    print(f"Logo   : {logo_path or 'None (skipped)'}")
    if also_per_project:
        print("Mode   : combined report + per-project reports")
    print()

    result = run_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        logo_path=logo_path,
    )

    ctx = result.get("context", {})
    pdf = ctx.get("pdf_path") or str(output_dir / "*.pdf")
    print(f"\nDone. Combined PDF saved to: {pdf}")

    # Optional per-project PDFs after the combined report
    if also_per_project:
        multi_year_data = ctx.get("multi_year_study_data")
        multi_year_qre = ctx.get("multi_year_qre_results")
        if not multi_year_data or not multi_year_qre:
            print(
                "\n[WARNING] --per-project was requested but the pipeline did not produce "
                "multi_year_study_data / multi_year_qre_results in context. "
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the R&D Tax Credit multi-agent pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (LLM narratives + combined PDF)
  python run_pipeline.py --input examples/novapulse_multiyear.json

  # Per-project PDFs only — fast, no API key needed
  python run_pipeline.py --input examples/novapulse_multiyear.json --per-project-only

  # Full pipeline + per-project PDFs afterwards
  python run_pipeline.py --input examples/novapulse_multiyear.json --per-project

  # Single-year CSV
  python run_pipeline.py --input examples/meridian_robotics_answers.csv
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
            "After generating the combined report, also produce one PDF per project. "
            "Only applies to multi-year JSON inputs. "
            "Per-project PDFs are saved to <output>/per_project/."
        ),
    )
    parser.add_argument(
        "--per-project-only",
        action="store_true",
        default=False,
        help=(
            "Generate ONLY per-project PDFs — skip the combined multi-year report entirely. "
            "Does NOT call OpenAI (no API key required). Runs in seconds. "
            "Only works with multi-year JSON inputs."
        ),
    )
    args = parser.parse_args()

    # Validate: can't use both flags together
    if args.per_project and args.per_project_only:
        raise SystemExit(
            "ERROR: --per-project and --per-project-only are mutually exclusive. "
            "Use --per-project-only to skip the combined report, "
            "or --per-project to generate both."
        )

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"ERROR: Input file not found: {input_path}")

    output_dir = Path(args.output) if args.output else Path("output") / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    logo_path = Path(args.logo)
    if not logo_path.exists():
        print(f"Warning: Logo not found at '{logo_path}' — report will be generated without logo.")
        logo_path = None

    if args.per_project_only:
        # Fast path — no LLM, no API key needed
        run_per_project_only(input_path, output_dir, logo_path)
    else:
        # Full pipeline — requires OPENAI_API_KEY
        _require_api_key()
        run_full_pipeline(
            input_path=input_path,
            output_dir=output_dir,
            logo_path=logo_path,
            also_per_project=args.per_project,
        )


if __name__ == "__main__":
    main()

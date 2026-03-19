"""Pipeline Coordinator - orchestrates multi-agent workflow."""

import json
import os
from pathlib import Path

from openai import OpenAI

from src.agents.framework import AgentOrchestrator
from src.agents.csv_ingestion import csv_ingestion_agent


class PipelineError(Exception):
    """Custom exception for pipeline errors."""
    pass


def _preflight_check(study_data_dict: dict, input_type: str = "") -> list[str]:
    """
    Run pre-flight validation on the mapped study data before any LLM calls.

    Enforces the blueprint rule: a partial study is worse than no study.
    Returns a list of error strings; empty list means the data is safe to proceed.

    Args:
        study_data_dict: Serialised RDStudyData dict (post-mapping, pre-computation).
        input_type: 'questionnaire', 'csv', or 'json' — used for path-specific checks.

    Returns:
        List of error message strings. Empty = OK to proceed.
    """
    errors: list[str] = []

    # ── Rule 1: business EIN must be present ────────────────────────────────
    company_bg = study_data_dict.get("company_background") or {}
    prepared_for = company_bg.get("prepared_for") or {}
    ein = (prepared_for.get("ein") or "").strip()
    if not ein:
        errors.append(
            "Blueprint Rule 1: business.ein is missing or empty — "
            "the EIN is required on every R&D Study and must be verified against the tax return."
        )

    # ── Rule 2: current-year gross receipts must be > 0 ─────────────────────
    gr = study_data_dict.get("gross_receipts") or {}
    if not gr or float(str(gr.get("year_0", 0) or 0)) == 0.0:
        errors.append(
            "Blueprint Rule 2: gross_receipts.year_0 is 0 or missing — "
            "current-year gross receipts are required for the credit calculation."
        )

    # ── Rule 3: at least one employee must have qualified_percentage > 0 ────
    employees = study_data_dict.get("employees") or []
    if not employees:
        errors.append(
            "Blueprint Rule 3: No employees found — "
            "at least one employee with qualified wages is required."
        )
    else:
        all_zero = all(
            float(str(e.get("qualified_percentage", 0) or 0)) == 0.0
            for e in employees
        )
        if all_zero:
            errors.append(
                "Blueprint Rule 3: All employees have qualified_percentage = 0.0 — "
                "no qualified wages would be claimed."
            )

    # ── Rule 6: every project must have technical_uncertainty populated ──────
    projects = study_data_dict.get("rd_projects") or []
    for p in projects:
        pid = p.get("project_id", "UNKNOWN")
        ts = p.get("technical_summary") or {}
        uncertainty = ts.get("technical_uncertainty", "").strip()
        if not uncertainty or uncertainty.lower().startswith("[analyst input required"):
            errors.append(
                f"Blueprint Rule 6: Project {pid} has empty or placeholder "
                "technical_uncertainty — the 4-part test cannot be substantiated."
            )

    # ── Rule 5: at least one project should have source_answers (traceability) ──
    projects_with_source = [
        p for p in projects
        if p.get("source_answers") and len(p["source_answers"]) > 0
    ]
    if projects and not projects_with_source:
        errors.append(
            "Blueprint Rule 5: No project has source_answers populated — "
            "narrative claims cannot be traced to questionnaire responses. "
            "Populate source_answers or use the questionnaire input path."
        )

    # ── Rules 7 & 8: questionnaire path requires interview_responses ─────────
    if input_type == "questionnaire":
        ir = study_data_dict.get("interview_responses") or {}
        if not ir:
            errors.append(
                "Blueprint Rules 7 & 8: interview_responses is empty — "
                "the golden_answer (F2 client quote) and interview metadata "
                "are required for a complete Executive Summary."
            )
        # Rule 7: golden_answer (F2) must be populated for the Executive Summary
        golden = (study_data_dict.get("golden_answer") or "").strip()
        if not golden:
            errors.append(
                "Blueprint Rule 7: golden_answer (F2) is missing — "
                "the client's verbatim quote about their qualified research is required "
                "for the Executive Summary opening paragraph."
            )

    # ── Rule 8: interview_metadata.status must be 'complete' ─────────────────
    interview_meta = study_data_dict.get("interview_metadata") or {}
    status = interview_meta.get("status", "pending") if isinstance(interview_meta, dict) else getattr(interview_meta, "status", "pending")
    if status not in ("complete", None):
        if status != "complete":
            # Only block if explicitly set to pending_followup; default 'pending' from
            # CSV/JSON paths (which have no interview) is allowed through.
            if status == "pending_followup":
                errors.append(
                    "Blueprint Rule 8: interview_metadata.status is 'pending_followup' — "
                    "the interview must be fully completed before the study can be generated. "
                    "Resolve open follow-up items and set status to 'complete'."
                )

    return errors


def run_pipeline_from_dict(
    answers_dict: dict,
    output_dir: Path,
    logo_path: Path = None,
) -> dict:
    """
    Run the pipeline directly from an in-memory answers dict.

    Bypasses file I/O entirely: validates the dict against QuestionnaireAnswers,
    maps it to RDStudyData, and starts the pipeline from ComputationAgent onward.
    Use this when the IntakeAgent (or any other source) has already built the
    structured answers dict in memory and you don't want to write a temp file.

    Args:
        answers_dict: Dict conforming to QuestionnaireAnswers schema.
        output_dir:   Directory for generated PDF and artifacts.
        logo_path:    Optional path to logo image.

    Returns:
        Pipeline result dict (same shape as run_pipeline()).

    Raises:
        PipelineError: on validation or pipeline failures.
    """
    from src.schema.questionnaire_schema import QuestionnaireAnswers
    from src.mappers.questionnaire_to_study import map_questionnaire_to_study

    # Validate
    try:
        answers = QuestionnaireAnswers(**answers_dict)
    except Exception as exc:
        raise PipelineError(f"answers_dict failed QuestionnaireAnswers validation: {exc}") from exc

    # Map to RDStudyData
    try:
        study_data = map_questionnaire_to_study(answers)
        study_data_dict = json.loads(study_data.model_dump_json())
    except Exception as exc:
        raise PipelineError(f"Mapping to RDStudyData failed: {exc}") from exc

    # Pre-flight guardrail — block partial studies before any LLM calls
    preflight_errors = _preflight_check(study_data_dict, input_type="questionnaire")
    if preflight_errors:
        raise PipelineError(
            "Pre-flight validation failed — pipeline halted to prevent a partial study:\n"
            + "\n".join(f"  • {e}" for e in preflight_errors)
        )

    # Build context — start from ComputationAgent (ingestion already done above)
    from src.agents.computation import computation_agent

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = {
        "study_data":   study_data_dict,
        "output_dir":   str(output_dir),
        "logo_path":    str(logo_path) if logo_path else None,
        "input_type":   "questionnaire",
        "input_format": "questionnaire",
    }

    print("\n" + "=" * 80)
    print("R&D TAX CREDIT REPORT GENERATOR — IN-MEMORY PIPELINE")
    print("=" * 80)
    print(f"Client:           {answers.study_metadata_answers.client_legal_name}")
    print(f"Tax Year:         {answers.study_metadata_answers.tax_year}")
    print(f"Output directory: {output_dir}")

    orchestrator = AgentOrchestrator(client, debug=True)
    client_name = answers.study_metadata_answers.client_legal_name
    tax_year    = answers.study_metadata_answers.tax_year
    initial_messages = [
        {
            "role": "user",
            "content": (
                f"The QuestionnaireIngestionAgent has successfully parsed and validated the "
                f"questionnaire answers for {client_name} (tax year {tax_year}). "
                f"context['study_data'] is fully populated with RDStudyData. "
                f"context['input_type'] = 'questionnaire'. "
                f"Please call calculate_comprehensive_qre() then handoff_to_narrative()."
            ),
        }
    ]

    try:
        result = orchestrator.run(
            agent=computation_agent,
            messages=initial_messages,
            context=context,
            max_turns=30,
        )

        # Save trace
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        trace_path = artifacts_dir / "trace.json"
        with open(trace_path, "w") as f:
            json.dump(
                {
                    "status": result.get("status"),
                    "input_type": "questionnaire_in_memory",
                    "agent_trace": result.get("agent_trace", []),
                    "final_message": result.get("final_message"),
                },
                f,
                indent=2,
            )

        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"Status: {result.get('status')}")
        print(f"Trace saved to: {trace_path}")

        return result

    except Exception as exc:
        raise PipelineError(f"In-memory pipeline failed: {exc}") from exc


def _detect_input_type(input_path: Path) -> str:
    """
    Detect whether an input file is a questionnaire answers JSON,
    a comprehensive study JSON, or a CSV.

    Returns one of: "questionnaire", "json", "csv"
    """
    suffix = input_path.suffix.lower()

    if suffix == ".csv":
        return "csv"

    if suffix == ".json":
        try:
            # Read up to 4KB to safely detect multi-year JSON even when correction_summary
            # or other new top-level keys precede the "tax_years" key.
            peek = input_path.read_text(encoding="utf-8")[:4000]
            if "study_metadata_answers" in peek:
                return "questionnaire"
            # "study_title" is present only in multi-year wrappers (MultiYearStudyData).
            # "tax_years" is the definitive key but may appear after the first 500 chars.
            if "tax_years" in peek or '"study_title"' in peek:
                return "multi_year_json"
        except Exception:
            pass
        return "json"

    # Fall back to CSV for unknown extensions
    return "csv"


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    logo_path: Path = None,
    # Legacy positional alias kept for backwards compatibility
    csv_path: Path = None,
) -> dict:
    """
    Run multi-agent pipeline with Swarm-style orchestration.

    Automatically detects the input type and routes to the correct
    ingestion agent:

      answers.json  (study_metadata_answers key present)
          → QuestionnaireIngestionAgent → ComputationAgent → ...

      study.json    (standard RDStudyData structure)
          → JSONIngestionAgent → ComputationAgent → ...

      data.csv
          → CSVIngestionAgent → ComputationAgent → ...

    Args:
        input_path: Path to input file (CSV, study JSON, or answers JSON).
        output_dir:  Directory for output files.
        logo_path:   Optional path to logo image.
        csv_path:    Deprecated alias for input_path (backwards compatibility).

    Returns:
        Dictionary with pipeline results.
    """
    # Backwards-compatibility: accept old csv_path kwarg
    if csv_path is not None and input_path is None:
        input_path = csv_path

    print("\n" + "=" * 80)
    print("R&D TAX CREDIT REPORT GENERATOR - MULTI-AGENT PIPELINE")
    print("=" * 80)

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    # Detect input type and select starting agent + context
    input_type = _detect_input_type(input_path)

    if input_type == "multi_year_json":
        from src.agents.multi_year_json_ingestion import multi_year_json_ingestion_agent
        starting_agent = multi_year_json_ingestion_agent
        context = {
            "json_path": str(input_path),
            "output_dir": str(output_dir),
            "logo_path": str(logo_path) if logo_path else None,
            "input_type": "multi_year_json",
        }
        initial_message = (
            f"Process this multi-year study JSON and generate a combined R&D tax credit report: {input_path}"
        )
        print(f"\nInput type: Multi-Year Study JSON")

    elif input_type == "questionnaire":
        from src.agents.questionnaire_ingestion import questionnaire_ingestion_agent
        starting_agent = questionnaire_ingestion_agent
        context = {
            "answers_path": str(input_path),
            "output_dir": str(output_dir),
            "logo_path": str(logo_path) if logo_path else None,
            "input_type": "questionnaire",
        }
        initial_message = (
            f"Process questionnaire answers file and generate an R&D tax credit report: {input_path}"
        )
        print(f"\nInput type: Questionnaire Answers JSON")

    elif input_type == "json":
        from src.agents.json_ingestion import json_ingestion_agent
        starting_agent = json_ingestion_agent
        context = {
            "json_path": str(input_path),
            "output_dir": str(output_dir),
            "logo_path": str(logo_path) if logo_path else None,
            "input_type": "json",
        }
        initial_message = (
            f"Process this study JSON file and generate an R&D tax credit report: {input_path}"
        )
        print(f"\nInput type: Comprehensive Study JSON")

    else:
        starting_agent = csv_ingestion_agent
        context = {
            "csv_path": str(input_path),
            "output_dir": str(output_dir),
            "logo_path": str(logo_path) if logo_path else None,
            "input_type": "csv",
        }
        initial_message = (
            f"Process this CSV file and generate an R&D tax credit report: {input_path}"
        )
        print(f"\nInput type: CSV")

    print(f"Input file: {input_path}")
    print(f"Output directory: {output_dir}")
    if logo_path:
        print(f"Logo: {logo_path}")

    # Pre-flight guardrail for file-based pipelines.
    # Only applicable to JSON / questionnaire paths where study_data is already
    # fully populated before the orchestrator starts.  CSV path is validated
    # inside CSVIngestionAgent (Pydantic) + ComplianceAgent post-narrative.
    if input_type in ("questionnaire", "json") and input_type != "multi_year_json":
        import json as _json
        # For questionnaire/json we need to load the file to pre-flight check.
        # This is a lightweight read — no LLM calls yet.
        try:
            raw = _json.loads(Path(input_path).read_text(encoding="utf-8"))
            if input_type == "questionnaire":
                from src.schema.questionnaire_schema import QuestionnaireAnswers
                from src.mappers.questionnaire_to_study import map_questionnaire_to_study as _m
                _study = _m(QuestionnaireAnswers(**raw))
                _study_dict = _json.loads(_study.model_dump_json())
            else:
                _study_dict = raw
            preflight_errors = _preflight_check(_study_dict, input_type=input_type)
            if preflight_errors:
                raise PipelineError(
                    "Pre-flight validation failed — pipeline halted to prevent a partial study:\n"
                    + "\n".join(f"  • {e}" for e in preflight_errors)
                )
        except PipelineError:
            raise
        except Exception as _pf_err:
            print(f"[WARNING] Pre-flight check could not run: {_pf_err}")

    # Create agent orchestrator
    orchestrator = AgentOrchestrator(client, debug=True)

    initial_messages = [{"role": "user", "content": initial_message}]

    # Run orchestration — agents hand off to each other automatically
    try:
        result = orchestrator.run(
            agent=starting_agent,
            messages=initial_messages,
            context=context,
            max_turns=30,
        )

        # Save agent trace
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        trace_path = artifacts_dir / "trace.json"
        with open(trace_path, "w") as f:
            json.dump(
                {
                    "status": result.get("status"),
                    "input_type": input_type,
                    "agent_trace": result.get("agent_trace", []),
                    "final_message": result.get("final_message"),
                },
                f,
                indent=2,
            )

        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"Status: {result.get('status')}")
        print(f"Trace saved to: {trace_path}")

        return result

    except Exception as e:
        print(f"\n{'=' * 80}")
        print("PIPELINE ERROR")
        print(f"{'=' * 80}")
        print(f"Error: {str(e)}")
        raise

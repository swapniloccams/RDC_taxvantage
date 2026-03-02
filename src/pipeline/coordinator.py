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
            peek = input_path.read_text(encoding="utf-8")[:500]
            if "study_metadata_answers" in peek:
                return "questionnaire"
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

    if input_type == "questionnaire":
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

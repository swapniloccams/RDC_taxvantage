"""
MultiYearJSONIngestionAgent — Validates and parses a multi-year R&D study JSON.

Input JSON format:
  {
    "study_title": "...",
    "combined_credit_method": "ASC",
    "tax_years": [ <RDStudyData for year 1>, <RDStudyData for year 2>, ... ]
  }

On success, populates:
  context["multi_year_study_data"]  — list of per-year RDStudyData dicts (oldest → newest)
  context["study_data"]             — most-recent year's RDStudyData dict (for narrative generation)
  context["is_multi_year"]          — True
  context["multi_year_title"]       — study_title string
  context["input_format"]           — "multi_year_json"
"""

import json
from pathlib import Path

from src.agents.framework import Agent, Handoff
from src.schema.study_schema import MultiYearStudyData, RDStudyData


def validate_and_parse_multi_year_json(context: dict = None) -> dict:
    """
    Validate and parse a multi-year study JSON file against MultiYearStudyData schema.

    Args:
        context: Must contain 'json_path' key pointing to the multi-year JSON file.

    Returns:
        Status dict with validation results.
    """
    json_path = (context or {}).get("json_path")
    if not json_path:
        return {"status": "error", "message": "No json_path provided in context"}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {"status": "error", "message": f"JSON file not found: {json_path}"}
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid JSON syntax: {exc}"}

    try:
        multi_study = MultiYearStudyData(**raw)
    except Exception as exc:
        return {"status": "error", "message": f"MultiYearStudyData validation failed: {exc}"}

    # Serialise each year to a plain dict (enums → strings, Decimal → float)
    year_dicts = []
    for yr in multi_study.tax_years:
        year_dicts.append(json.loads(yr.model_dump_json()))

    # Most-recent year drives narrative generation
    latest_year = year_dicts[-1]

    context["multi_year_study_data"] = year_dicts
    context["study_data"] = latest_year
    context["is_multi_year"] = True
    context["multi_year_title"] = multi_study.study_title
    context["input_format"] = "multi_year_json"
    # Store top-level raw dict so builder can access correction_summary and other study-level fields
    context["_multi_year_raw"] = {
        "correction_summary": raw.get("correction_summary"),
        "study_title": multi_study.study_title,
    }

    year_labels = [yr["study_metadata"]["tax_year"]["year_label"] for yr in year_dicts]
    project_counts = [len(yr["rd_projects"]) for yr in year_dicts]
    employee_counts = [len(yr["employees"]) for yr in year_dicts]

    return {
        "status": "success",
        "message": f"Validated multi-year JSON study with {len(year_dicts)} years: {', '.join(year_labels)}",
        "study_title": multi_study.study_title,
        "years": year_labels,
        "projects_per_year": project_counts,
        "employees_per_year": employee_counts,
    }


def handoff_to_computation(context: dict = None) -> Handoff:
    """Hand off to ComputationAgent for multi-year QRE calculations."""
    from src.agents.computation import computation_agent

    return Handoff(
        agent=computation_agent,
        context=context or {},
        reason=(
            "Multi-year JSON validated. context['multi_year_study_data'] populated. "
            "context['is_multi_year'] = True. Call calculate_multi_year_qre() then handoff_to_narrative()."
        ),
    )


multi_year_json_ingestion_agent = Agent(
    name="MultiYearJSONIngestionAgent",
    instructions="""You are the Multi-Year JSON Ingestion Agent.

Your ONLY job is:
1. Call validate_and_parse_multi_year_json() — always, immediately, with no preamble.
2. If status='success': call handoff_to_computation() immediately.
3. If status='error': return a structured JSON error with the error message.

RULES:
- Do NOT summarise the parsed data.
- Do NOT ask for confirmation.
- Do NOT output prose after a successful parse.
- After a successful parse you MUST call handoff_to_computation() — no exceptions.
""",
    functions=[validate_and_parse_multi_year_json, handoff_to_computation],
)

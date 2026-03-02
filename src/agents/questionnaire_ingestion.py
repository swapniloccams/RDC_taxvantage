"""
Questionnaire Ingestion Agent.

Accepts a structured answers.json file, validates it against QuestionnaireAnswers,
maps it to RDStudyData via the deterministic mapper, flags incomplete fields,
and hands off to ComputationAgent.
"""

import json
from pathlib import Path
from typing import Optional

from src.agents.framework import Agent, Handoff
from src.schema.questionnaire_schema import QuestionnaireAnswers
from src.mappers.questionnaire_to_study import map_questionnaire_to_study


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def parse_questionnaire_answers(context: Optional[dict] = None) -> dict:
    """
    Tool: Load, validate, and map a questionnaire answers JSON file to RDStudyData.

    Reads the file at context['answers_path'], validates it against
    QuestionnaireAnswers schema, runs completeness checks, maps it to
    RDStudyData, and stores the result in context['study_data'].

    Args:
        context: Shared pipeline context. Must contain 'answers_path'.

    Returns:
        dict with keys: status, projects_loaded, employees_loaded,
        contractors_loaded, supplies_loaded, missing_fields, warnings.
    """
    if not context:
        return {"error": "No context provided"}

    answers_path = context.get("answers_path")
    if not answers_path:
        return {"error": "context missing 'answers_path'"}

    path = Path(answers_path)
    if not path.exists():
        return {"error": f"Answers file not found: {answers_path}"}

    # --- Load raw JSON ---
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in answers file: {exc}"}

    # --- Validate with Pydantic ---
    try:
        answers = QuestionnaireAnswers(**raw)
    except Exception as exc:
        return {"error": f"Answers schema validation failed: {exc}"}

    # --- Completeness checks (non-blocking warnings) ---
    missing_fields: list[str] = []
    warnings: list[str] = []

    project_ids = {p.project_id for p in answers.projects}

    for p in answers.projects:
        # 4-part test completeness
        for field in [
            "technical_uncertainty",
            "elimination_of_uncertainty",
            "process_of_experimentation",
            "technological_in_nature",
            "permitted_purpose",
        ]:
            val = getattr(p, field, "")
            if not val or not val.strip():
                missing_fields.append(f"Project {p.project_id}: missing '{field}'")

        # Encourage hypothesis / experimentation lists
        if not p.hypotheses_tested:
            warnings.append(
                f"Project {p.project_id}: 'hypotheses_tested' is empty — "
                "narrative will be weaker without specific hypotheses"
            )
        if not p.experimentation_process:
            warnings.append(
                f"Project {p.project_id}: 'experimentation_process' is empty — "
                "consider adding iteration steps"
            )

        # Evidence links
        has_evidence = any([
            p.jira_links, p.github_links, p.design_docs,
            p.test_reports, p.other_docs,
        ])
        if not has_evidence:
            warnings.append(
                f"Project {p.project_id}: no evidence links provided "
                "(jira_links, github_links, design_docs, etc.)"
            )

    for e in answers.employees:
        # Allocation project IDs should reference real projects
        for pid in e.project_allocation:
            if pid not in project_ids:
                missing_fields.append(
                    f"Employee {e.employee_id}: allocation references unknown project '{pid}'"
                )

    for c in answers.contractors:
        # Rights & risk gate
        if not c.company_retains_rights:
            missing_fields.append(
                f"Contractor {c.vendor_id}: 'company_retains_rights' is False — "
                "contractor QRE will be excluded"
            )
        if not c.company_bears_financial_risk:
            missing_fields.append(
                f"Contractor {c.vendor_id}: 'company_bears_financial_risk' is False — "
                "contractor QRE will be excluded"
            )
        for pid in c.project_allocation:
            if pid not in project_ids:
                missing_fields.append(
                    f"Contractor {c.vendor_id}: allocation references unknown project '{pid}'"
                )

    # --- Deterministic mapping to RDStudyData ---
    try:
        study_data = map_questionnaire_to_study(answers)
    except Exception as exc:
        return {"error": f"Mapping to RDStudyData failed: {exc}"}

    # Serialise to dict for downstream agents
    study_data_dict = json.loads(study_data.model_dump_json())

    # Store in shared context
    context["study_data"] = study_data_dict
    context["missing_fields"] = missing_fields
    context["questionnaire_warnings"] = warnings
    context["input_type"] = "questionnaire"

    has_errors = len(missing_fields) > 0
    return {
        "status": "partial" if has_errors else "success",
        "projects_loaded": len(answers.projects),
        "employees_loaded": len(answers.employees),
        "contractors_loaded": len(answers.contractors),
        "supplies_loaded": len(answers.supplies),
        "cloud_loaded": len(answers.cloud_computing),
        "missing_fields": missing_fields,
        "warnings": warnings,
    }


def handoff_to_computation(context: Optional[dict] = None) -> Handoff:
    """
    Tool: Hand off to ComputationAgent after successful ingestion.

    Args:
        context: Shared pipeline context containing validated study_data.

    Returns:
        Handoff to ComputationAgent.
    """
    from src.agents.computation import computation_agent

    missing = (context or {}).get("missing_fields", [])
    reason = (
        "Questionnaire answers validated and mapped to RDStudyData"
        if not missing
        else f"Questionnaire mapped with {len(missing)} flagged field(s) — proceeding with placeholders"
    )

    return Handoff(
        agent=computation_agent,
        context=context or {},
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

questionnaire_ingestion_agent = Agent(
    name="QuestionnaireIngestionAgent",
    instructions="""You are the Questionnaire Ingestion Agent for the R&D Tax Credit pipeline.

Your ONLY responsibilities:
1. Call parse_questionnaire_answers() to load, validate, and map the answers file.
2. Review the returned result:
   - Log every item in missing_fields as a clear warning to the user.
   - Log every item in warnings as an advisory note.
   - If status is "error", STOP and report the error. Do NOT proceed.
   - If status is "success" or "partial", proceed to step 3.
3. Call handoff_to_computation() to pass the mapped RDStudyData to the next agent.

Rules:
- Do NOT perform any calculations.
- Do NOT generate any narrative text.
- Do NOT modify, infer, or fill in any values — only report what is missing.
- Do NOT skip handoff_to_computation() even if there are warnings or partial data.
  The downstream agents handle missing fields with placeholders.
""",
    functions=[parse_questionnaire_answers, handoff_to_computation],
)

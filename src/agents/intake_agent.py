"""
Intake Agent.

Accepts raw questionnaire answers (from any source — web form, chat, document
extraction, API payload, etc.), converts them into the structured
QuestionnaireAnswers format using the deterministic builder, validates them,
and hands off to QuestionnaireIngestionAgent to continue the pipeline.

Usage (in-memory, no file I/O):
    from src.agents.intake_agent import intake_agent
    from src.agents.framework import AgentOrchestrator

    context = {
        "raw_answers": { ...human-friendly dict... },
        "output_dir":  "output",
        "logo_path":   "assets/occams_logo.png",
    }
    orchestrator.run(intake_agent, messages=[...], context=context)

Usage (file-based — write answers.json then use CLI):
    builder = build_answers_json(raw_answers)
    with open("answers.json", "w") as f:
        json.dump(builder, f, indent=2)
    # Then: python -m src --input answers.json --out output
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.agents.framework import Agent, Handoff
from src.mappers.questionnaire_answers_builder import build_answers_json


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def structure_questionnaire_answers(raw_answers: dict = None, context: Optional[dict] = None) -> dict:
    """
    Tool: Convert raw questionnaire answers into a validated QuestionnaireAnswers dict.

    Accepts raw_answers either as a direct argument or from context["raw_answers"].
    Runs the deterministic builder (questionnaire_answers_builder.py) and validates
    the result against the QuestionnaireAnswers Pydantic schema.

    On success, stores the structured dict in context["answers_dict"] and returns
    a summary of what was parsed.

    Args:
        raw_answers: Human-friendly answers dict (see questionnaire_answers_builder.py).
        context:     Pipeline context. May contain "raw_answers" as a fallback.

    Returns:
        dict with keys: status, projects_found, employees_found, warnings.
    """
    raw = raw_answers or (context or {}).get("raw_answers")
    if not raw:
        return {"status": "error", "message": "No raw_answers provided — pass as argument or set context['raw_answers']"}

    # --- Build structured dict ---
    try:
        answers_dict = build_answers_json(raw)
    except ValueError as exc:
        return {"status": "error", "message": f"Builder validation failed: {exc}"}
    except Exception as exc:
        return {"status": "error", "message": f"Unexpected builder error: {type(exc).__name__}: {exc}"}

    # --- Validate with Pydantic ---
    try:
        from src.schema.questionnaire_schema import QuestionnaireAnswers
        QuestionnaireAnswers(**answers_dict)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Schema validation failed after building: {exc}",
            "hint": "Check that all required fields were supplied in raw_answers.",
        }

    # --- Store in context ---
    if context is not None:
        context["answers_dict"] = answers_dict

    # --- Collect non-blocking warnings ---
    warnings: list[str] = []
    for p in answers_dict.get("projects", []):
        if not p.get("hypotheses_tested"):
            warnings.append(f"Project '{p['project_name']}': no hypotheses_tested — narrative may be weaker.")
        if not any([p.get("jira_links"), p.get("github_links"), p.get("design_docs"), p.get("test_reports")]):
            warnings.append(f"Project '{p['project_name']}': no evidence links provided.")

    for e in answers_dict.get("employees", []):
        alloc_sum = sum(e.get("project_allocation", {}).values())
        if not (0.97 <= alloc_sum <= 1.03):
            warnings.append(
                f"Employee '{e['employee_name']}': project_allocation sums to {alloc_sum:.3f} "
                f"(expected ~1.0) — was auto-normalized."
            )

    return {
        "status": "success",
        "projects_found":     len(answers_dict.get("projects", [])),
        "employees_found":    len(answers_dict.get("employees", [])),
        "contractors_found":  len(answers_dict.get("contractors", [])),
        "warnings":           warnings,
    }


def save_answers_json(output_path: str = None, context: Optional[dict] = None) -> dict:
    """
    Tool: Write the structured answers dict to a JSON file on disk.

    Reads context["answers_dict"] (produced by structure_questionnaire_answers).
    Useful for debugging or for handing the file to the CLI separately.

    Args:
        output_path: File path to write (default: answers.json in output_dir).
        context:     Pipeline context — must contain "answers_dict".

    Returns:
        dict with status and file path.
    """
    answers_dict = (context or {}).get("answers_dict")
    if not answers_dict:
        return {"status": "error", "message": "No answers_dict in context — call structure_questionnaire_answers first."}

    if not output_path:
        output_dir = (context or {}).get("output_dir", "output")
        output_path = str(Path(output_dir) / "answers.json")

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(answers_dict, f, indent=2, ensure_ascii=False)
        return {"status": "success", "saved_to": output_path}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to write answers.json: {exc}"}


def handoff_to_questionnaire_ingestion(context: Optional[dict] = None) -> Handoff:
    """
    Tool: Hand off to QuestionnaireIngestionAgent after answers are structured.

    Writes context["answers_dict"] to a temp file at context["answers_path"] so
    QuestionnaireIngestionAgent can read it from disk (existing flow).

    Args:
        context: Pipeline context — must contain "answers_dict".

    Returns:
        Handoff to QuestionnaireIngestionAgent.
    """
    from src.agents.questionnaire_ingestion import questionnaire_ingestion_agent

    answers_dict = (context or {}).get("answers_dict")
    if not answers_dict:
        # Still hand off — the ingestion agent will catch the missing answers_path error
        return Handoff(
            agent=questionnaire_ingestion_agent,
            context=context or {},
            reason="No answers_dict in context — QuestionnaireIngestionAgent will report the error",
        )

    # Write to a temp location so the existing file-reading ingestion agent works unchanged
    import tempfile
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(answers_dict, tmp, indent=2, ensure_ascii=False)
    tmp.close()

    ctx = context or {}
    ctx["answers_path"] = tmp.name
    ctx["input_type"] = "questionnaire"

    return Handoff(
        agent=questionnaire_ingestion_agent,
        context=ctx,
        reason="Questionnaire answers structured and validated — ready for ingestion",
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

QUESTIONNAIRE_TEXT = """
SECTION A — Business Overview & Eligibility Context
 1. Provide a brief description of your company's primary business activities.
 2. What products, software, or services does the company offer?
 3. What technical departments are involved in development activities?
 4. Where are research activities physically performed (U.S. / foreign)?
 5. Has the company claimed the R&D tax credit in prior years?
 6. What were gross receipts for the current tax year and prior three years?
 7. Were any research activities funded by customers, grants, or third parties?
 8. Were any wages used for other tax credits (ERC, WOTC, etc.)?

SECTION B — Project Identification & Business Components
 9. Identify all projects undertaken during the tax year.
10. For each project, describe the business component being developed or improved.
11. What measurable performance improvements were targeted?
12. What were the start and end dates of each project?
13. Was the project internally funded or contract-funded?
14. Was the outcome known at the beginning of the project?

SECTION C — Four-Part Test Qualification (Per Project)
15. What technical challenges or uncertainties existed at the beginning?
16. What was unknown regarding capability, methodology, or design?
17. Why could the solution not be achieved using standard industry practices?
18. What alternative approaches were evaluated?
19. Were prototypes, pilots, simulations, or test environments created?
20. Describe the experimentation process used to evaluate alternatives.
21. What iterations, failures, or redesigns occurred?
22. What scientific or engineering principles were relied upon?
23. Which technical disciplines were involved?
24. What was the final outcome of the project?

SECTION D — Employee Activities & Wage Allocation
25. List all employees involved in qualified research activities.
26. What were their job titles and primary responsibilities?
27. What specific R&D tasks did each employee perform?
28. What percentage of each employee's time was spent on qualified activities?
29. How was this percentage determined?
30. Provide W-2 Box 1 wages for each employee.
31. Were any owners or executives included?

SECTION E — Contractor, Supply & Cloud Expenditures
32. Identify any third-party contractors involved in research activities.
33. Describe the services provided by each contractor.
34. What total payments were made to each contractor?
35. Did the company retain rights to the research results?
36. Did the company bear financial risk if the project failed?
37. Were any tangible supplies consumed in the experimentation process?
38. Were cloud computing services used for development, testing, or modeling?
39. Provide supporting invoices or contract references.

SECTION F — Documentation & Audit Support
40. Are project management records available (Jira, tickets, sprint logs)?
41. Are source control logs (GitHub, GitLab, etc.) available?
42. Are technical design documents or architecture diagrams available?
43. Are test plans, results, or validation reports available?
44. Are payroll records and time allocation support documents maintained?
45. If audited, how would you substantiate the existence of technical uncertainty?

SECTION G — Final Compliance & Risk Review
46. Were any research activities conducted outside the United States?
47. Were any projects fully reimbursed regardless of outcome?
48. Were any improvements purely aesthetic or cosmetic?
49. Are there any known weaknesses in documentation or support?
50. Is there any additional information relevant to defending this R&D claim?
"""

intake_agent = Agent(
    name="IntakeAgent",
    instructions=f"""You are the R&D Tax Credit Intake Agent for Occams Advisory.

Your job is to collect answers to the R&D Tax Credit questionnaire and convert them
into a structured format for the report generation pipeline.

=== Questionnaire ===
{QUESTIONNAIRE_TEXT}

=== Your process ===
1. If context["raw_answers"] is already populated, skip to step 3.
2. If you are in a conversational mode, collect answers to all 50 questions above.
   Ask naturally — combine related questions where appropriate. Do NOT ask users
   to write JSON or use technical field names.
3. Once all answers are collected, call structure_questionnaire_answers() with the
   raw_answers dict. The dict keys should match the fields described in the builder
   (business_overview, projects, employees, etc.) — NOT the question numbers.
4. If structure_questionnaire_answers() returns status "error", report the issue
   clearly and ask the user to clarify the missing information. Do NOT proceed.
5. Optionally call save_answers_json() if you want to persist the answers file.
6. Call handoff_to_questionnaire_ingestion() to trigger the report pipeline.

=== Raw answers format ===
The raw_answers dict should contain:
  client_legal_name, ein, entity_type, address, industry, tax_year, credit_method,
  preparer_firm, preparer_name, date_prepared, business_overview,
  products_and_services (list), rd_departments (list), locations (list),
  gross_receipts (dict: year_0, year_minus_1, year_minus_2, year_minus_3),
  projects (list of dicts), employees (list of dicts),
  methodology_summary, limitations (list), disclaimer_text.

  Each project dict:
    project_name, business_component, objective, start_date, end_date,
    funding_type (Internal|Contract), status (Ongoing|Completed|Suspended),
    technical_uncertainty, problem_statement, alternatives_considered (list),
    experimentation_process (list), failures_or_iterations, results_or_outcome,
    technological_in_nature, permitted_purpose, elimination_of_uncertainty,
    process_of_experimentation, hypotheses_tested (list),
    jira_links, github_links, design_docs, test_reports, other_docs (all lists).

  Each employee dict:
    employee_name, job_title, department, location, w2_box_1_wages,
    qualified_percentage (0.0-1.0), qualification_basis, notes,
    project_allocation (dict: project_name_or_id → fraction, must sum to 1.0).

=== Rules ===
- Never ask the user to write JSON.
- Never invent or assume financial figures.
- Never skip calling handoff_to_questionnaire_ingestion().
""",
    functions=[
        structure_questionnaire_answers,
        save_answers_json,
        handoff_to_questionnaire_ingestion,
    ],
)

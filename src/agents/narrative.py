"""Narrative Agent - generates executive summary and project narratives using OpenAI."""

import os
import time
import json
from openai import OpenAI
from src.schema import ReportData, Project
from src.agents.framework import Agent, Handoff


PLACEHOLDER_TEXT = "[Needs analyst input - insufficient data provided]"

# Default model — uses gpt-4o (non-deprecated, latest capable model).
# Override via OPENAI_MODEL env var.
_DEFAULT_MODEL = "gpt-4o"


def _openai_call_with_retry(client: OpenAI, model: str, messages: list, temperature: float = 0.3) -> str:
    """
    Call OpenAI chat completions with exponential-backoff retry on rate-limit (429)
    and transient server errors (500/502/503).  Raises after 4 attempts.
    """
    delays = [2, 5, 15, 30]
    last_exc = None
    for attempt, delay in enumerate(delays, 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            err = str(exc)
            is_retryable = any(code in err for code in ("429", "500", "502", "503", "timeout", "Timeout"))
            if is_retryable and attempt < len(delays):
                last_exc = exc
                time.sleep(delay)
                continue
            raise
    raise last_exc


def _all_project_year_slots(context: dict) -> list:
    """
    Return a flat list of (year_label, yr_data_ref, proj_ref) for every project
    in every year, ordered oldest-year-first.

    Using yr_data_ref and proj_ref as live dict references means any mutation
    (e.g. writing generated_narratives) propagates back into context automatically.
    """
    slots = []
    multi_year_data = context.get("multi_year_study_data") or []
    if multi_year_data:
        for yr_data in multi_year_data:
            yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
            for proj in yr_data.get("rd_projects", []):
                slots.append((yr_label, yr_data, proj))
    else:
        # Single-year path: fall back to study_data
        study = context.get("study_data", {})
        yr_label = study.get("study_metadata", {}).get("tax_year", {}).get("year_label", "N/A")
        for proj in study.get("rd_projects", []):
            slots.append((yr_label, study, proj))
    return slots


def generate_executive_summary_tool(report_data_json: str = None, context: dict = None) -> str:
    """
    Tool: Generate executive summary with information collected bullets.

    Supports two context paths:
    - Questionnaire / comprehensive: context["study_data"] (RDStudyData format)
    - Legacy CSV: context["report_data"] (ReportData format)

    Args:
        report_data_json: JSON string of report data (optional, legacy only)
        context: Shared context dictionary

    Returns:
        Generated executive summary text
    """
    oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)

    # ── Comprehensive / questionnaire path ──────────────────────────────────
    if context and "study_data" in context:
        study = context["study_data"]
        meta = study["study_metadata"]
        client_name = meta["prepared_for"]["legal_name"]
        tax_year = meta["tax_year"]["year_label"]
        total_qre = str(context.get("total_qre", "N/A"))
        federal_credit = str(context.get("asc_computation", {}).get("federal_credit", "N/A"))

        # Gather all unique projects across all years for a complete summary
        all_slots = _all_project_year_slots(context)
        seen_proj_ids: set = set()
        project_lines = []
        for _, _, p in all_slots:
            pid = p.get("project_id", "")
            if pid in seen_proj_ids:
                continue
            seen_proj_ids.add(pid)
            ts = p.get("technical_summary", {})
            obj = ts.get("objective", "")
            gen = p.get("generated_narratives") or {}
            desc = gen.get("project_description") or obj
            project_lines.append(
                f"- {p['project_name']} ({p.get('status','')}):{(' ' + desc) if desc else ''}"
            )

        # F2 golden_answer — client's own words about their R&D (blueprint requirement)
        golden_answer = study.get("golden_answer") or ""

        info_collected = [
            "Employee W-2 wages and time allocations by project",
            "Contractor invoices and rights & risk confirmations",
            "Project descriptions, technical objectives, and outcomes",
            "Technical uncertainties and process of experimentation details",
            "Cloud computing and supply expenditures (where applicable)",
            "Supporting documentation (Jira tickets, GitHub repos, design docs)",
        ]

        golden_instruction = (
            f'\nOpen the first paragraph with this verbatim client quote: "{golden_answer}"\n'
            if golden_answer
            else ""
        )

        prompt = f"""You are writing the Executive Summary for a Federal R&D Tax Credit Study prepared by Occams Advisory.

Client: {client_name}
Tax Year: {tax_year}
Total QRE: {total_qre}
Federal R&D Credit: {federal_credit}

Qualified Research Projects:
{chr(10).join(project_lines)}

Information Collected:
{chr(10).join('• ' + item for item in info_collected)}

Write a 3-paragraph professional executive summary:
{golden_instruction}Paragraph 1: Describe the business and its R&D activities using the project list above.
Paragraph 2: Summarise the qualification methodology — how time allocations, technical uncertainties, and experimentation processes were documented.
Paragraph 3: State the total QREs of {total_qre} and federal R&D credit of {federal_credit} using the ASC method.

CRITICAL: Only use the facts listed above. Do not invent technical details. Do not use hedging language."""

        summary = _openai_call_with_retry(
            oai_client, model, [{"role": "user", "content": prompt}]
        )
        context["study_data"]["executive_summary"] = summary
        return summary

    # ── Legacy path ─────────────────────────────────────────────────────────
    if context and "report_data" in context:
        data_dict = context["report_data"]
    elif report_data_json:
        data_dict = json.loads(report_data_json)
    else:
        return "Error: No report data provided"

    report_data = ReportData(**data_dict)

    project_summaries = []
    for project in report_data.projects:
        summary_line = f"- {project.project_name} ({project.status})"
        if project.project_facts.description_bullets:
            summary_line += f": {project.project_facts.description_bullets[0]}"
        project_summaries.append(summary_line)

    prompt = f"""You are writing an executive summary for a Federal R&D Tax Credit Study.

Client: {report_data.report_meta.client_company}
Tax Year(s): {report_data.get_year_range_str()}

Projects:
{chr(10).join(project_summaries)}

Write a professional executive summary that:
1. Opens with a brief overview paragraph (2-3 sentences)
2. Includes a bullet list titled "Information Collected:" with 4-6 items describing the types of data gathered
3. Is concise and professional

Do not invent specific technical details not provided."""

    summary = _openai_call_with_retry(
        oai_client, model, [{"role": "user", "content": prompt}]
    )

    if context and "report_data" in context:
        context["report_data"]["executive_summary"] = summary

    return summary


def generate_project_narratives_tool(context: dict = None) -> dict:
    """
    Tool: Generate all narrative sections for the NEXT pending project-year slot.

    Call this tool repeatedly (with no arguments) until you receive
    "status": "all_complete".  The tool tracks its own position internally via
    context["_project_narrative_slot"] — you MUST NOT pass any index argument.

    Supports two context paths:
    - Comprehensive / multi-year: uses _all_project_year_slots() for full coverage.
      Iterates oldest-year-first, covering every project in every year.
    - Legacy CSV: context["report_data"] (ReportData format)

    Returns:
        Dictionary with status, project_name, year_label, narratives_generated,
        completed_count, and total_count.  When status == "all_complete" all
        project-year narratives have been written and you should proceed to
        generate_employee_activity_narrative_tool.
    """
    oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)

    # ── Comprehensive / questionnaire path ──────────────────────────────────
    if context and "study_data" in context:
        all_slots = _all_project_year_slots(context)
        total_slots = len(all_slots)

        # Auto-advancing internal slot counter
        project_index = context.get("_project_narrative_slot", 0)

        if project_index >= total_slots:
            context["_project_narrative_slot"] = total_slots
            return {
                "status": "all_complete",
                "message": (
                    f"All {total_slots} project-year narrative(s) already generated. "
                    "Proceed to generate_employee_activity_narrative_tool."
                ),
                "completed_count": total_slots,
                "total_count": total_slots,
            }

        year_label, yr_data, proj = all_slots[project_index]
        ts = proj.get("technical_summary", {})
        fpt = proj.get("four_part_test", {})
        source_answers: dict = proj.get("source_answers") or {}
        project_name = proj.get("project_name", f"Project {project_index + 1}")

        narratives = {}
        year_ctx = f"Tax Year {year_label} — "

        # ii) Project Description
        desc_facts = [f for f in [ts.get("objective"), ts.get("problem_statement"),
                                   ts.get("results_or_outcome")] if f]
        narratives["project_description"] = _generate_narrative(
            oai_client, model,
            "Project Description",
            desc_facts,
            f"Describe the R&D project '{project_name}' for {year_ctx}. Write 1-2 paragraphs explaining "
            "what the project aimed to achieve and the technical work involved.",
            source_answers=source_answers,
        ) if desc_facts else PLACEHOLDER_TEXT

        # iii) New or Improved Business Component
        comp_facts = [f for f in [proj.get("business_component"),
                                   ts.get("results_or_outcome"),
                                   ts.get("failures_or_iterations")] if f]
        narratives["new_improved_component"] = _generate_narrative(
            oai_client, model,
            "New or Improved Business Component",
            comp_facts,
            f"Describe the new or improved business component that resulted from this R&D project "
            f"({year_ctx}). Focus on what was created or enhanced. Write 1 paragraph.",
            source_answers=source_answers,
        ) if comp_facts else PLACEHOLDER_TEXT

        # iv) Elimination of Uncertainty
        unc_facts = [f for f in [ts.get("technical_uncertainty"),
                                  fpt.get("elimination_of_uncertainty")] if f]
        unc_facts += [h for h in ts.get("hypotheses_tested", []) if h]
        narratives["elimination_uncertainty"] = _generate_narrative(
            oai_client, model,
            "Elimination of Uncertainty",
            unc_facts,
            f"Describe the technical uncertainties that existed at project inception ({year_ctx}) and how "
            "the team worked to resolve them. Write 1-2 paragraphs.",
            source_answers=source_answers,
        ) if unc_facts else PLACEHOLDER_TEXT

        # v) Process of Experimentation
        exp_facts = [fpt.get("process_of_experimentation")] if fpt.get("process_of_experimentation") else []
        exp_facts += [s for s in ts.get("experimentation_process", []) if s]
        exp_facts += [a for a in ts.get("alternatives_considered", []) if a]
        narratives["process_experimentation"] = _generate_narrative(
            oai_client, model,
            "Process of Experimentation",
            exp_facts,
            f"Describe the systematic process of experimentation ({year_ctx}): iterations, testing, "
            "and refinements. Write 1-2 paragraphs.",
            source_answers=source_answers,
        ) if exp_facts else PLACEHOLDER_TEXT

        # vi) Technological in Nature
        tech_facts = [f for f in [fpt.get("technological_in_nature"),
                                   fpt.get("permitted_purpose")] if f]
        narratives["technological_nature"] = _generate_narrative(
            oai_client, model,
            "Technological in Nature",
            tech_facts,
            "Explain how this project relied on principles of computer science, engineering, "
            "or physical/biological sciences. Write 1 paragraph.",
            source_answers=source_answers,
        ) if tech_facts else PLACEHOLDER_TEXT

        # vii) Resolution — how and when uncertainty was resolved (blueprint §4 sub-section 5)
        res_facts = [f for f in [
            ts.get("results_or_outcome"),
            ts.get("failures_or_iterations"),
            fpt.get("elimination_of_uncertainty"),
        ] if f]
        narratives["resolution"] = _generate_narrative(
            oai_client, model,
            "Resolution",
            res_facts,
            f"Describe how and when the technical uncertainty in project '{project_name}' "
            f"({year_ctx}) was resolved. "
            "Include what the team ultimately learned, the final outcome, and any remaining open questions. "
            "Write 1 paragraph. Reference specific results, experiments, or milestones where available.",
            source_answers=source_answers,
        ) if res_facts else PLACEHOLDER_TEXT

        # ── Write narratives back to the correct year's project dict (Gap 4 fix) ──────
        # proj is a live reference into yr_data["rd_projects"] which is itself a live
        # reference into context["multi_year_study_data"][n] AND into
        # context["study_data"] when this is the last year.  Mutating proj propagates
        # the narrative to all consumers automatically — no secondary copy needed.
        proj["generated_narratives"] = narratives

        # Additionally mirror into context["study_data"] projects for the combined-report
        # renderer (comprehensive_sections.py reads from study_data["rd_projects"][i]).
        for sd_proj in context.get("study_data", {}).get("rd_projects", []):
            yr_lbl = year_label  # noqa: captured above
            if sd_proj.get("project_id") == proj.get("project_id"):
                # Overwrite only if this is a later (or equal) year, so the last-year
                # version wins for the combined report.
                sd_proj["generated_narratives"] = narratives
                break

        # Advance the internal counter for the next call
        context["_project_narrative_slot"] = project_index + 1
        remaining = total_slots - project_index - 1
        status = "all_complete" if remaining == 0 else "success"
        msg = (
            "All project-year narratives generated. Call generate_employee_activity_narrative_tool next."
            if remaining == 0
            else f"Call generate_project_narratives_tool() again to process the next slot."
        )
        return {
            "status": status,
            "project_name": project_name,
            "year_label": year_label,
            "narratives_generated": len(narratives),
            "completed_count": project_index + 1,
            "total_count": total_slots,
            "remaining_count": remaining,
            "message": msg,
        }

    # ── Legacy path ─────────────────────────────────────────────────────────
    if not context or "report_data" not in context:
        return {"error": "No report data in context"}

    report_data = ReportData(**context["report_data"])
    project_index = context.get("_project_narrative_slot", 0)
    total_legacy = len(report_data.projects)
    if project_index >= total_legacy:
        context["_project_narrative_slot"] = total_legacy
        return {
            "status": "all_complete",
            "message": f"All {total_legacy} legacy project narratives generated.",
            "completed_count": total_legacy,
            "total_count": total_legacy,
        }

    project = report_data.projects[project_index]
    facts = project.project_facts
    source_answers: dict = getattr(project, "source_answers", None) or {}

    narratives = {}

    if facts.description_bullets:
        narratives["project_description_narrative"] = _generate_narrative(
            oai_client, model,
            "Project Description",
            facts.description_bullets,
            f"Describe the R&D project '{project.project_name}' based on these facts. Write 1-2 paragraphs.",
            source_answers=source_answers,
        )
    else:
        narratives["project_description_narrative"] = PLACEHOLDER_TEXT

    if facts.description_bullets:
        narratives["new_improved_component"] = _generate_narrative(
            oai_client, model,
            "New or Improved Business Component",
            facts.description_bullets,
            "Describe the new or improved business component. Write 1 paragraph.",
            source_answers=source_answers,
        )
    else:
        narratives["new_improved_component"] = PLACEHOLDER_TEXT

    if facts.uncertainty_bullets:
        narratives["elimination_uncertainty"] = _generate_narrative(
            oai_client, model,
            "Elimination of Uncertainty",
            facts.uncertainty_bullets,
            "Describe the technical uncertainties and how they were resolved. Write 1-2 paragraphs.",
            source_answers=source_answers,
        )
    else:
        narratives["elimination_uncertainty"] = PLACEHOLDER_TEXT

    if facts.experimentation_bullets:
        narratives["process_experimentation"] = _generate_narrative(
            oai_client, model,
            "Process of Experimentation",
            facts.experimentation_bullets,
            "Describe the systematic process of experimentation. Write 1-2 paragraphs.",
            source_answers=source_answers,
        )
    else:
        narratives["process_experimentation"] = PLACEHOLDER_TEXT

    if facts.technology_bullets:
        narratives["technological_nature"] = _generate_narrative(
            oai_client, model,
            "Technological in Nature",
            facts.technology_bullets,
            "Explain how this project relied on scientific/engineering principles. Write 1 paragraph.",
            source_answers=source_answers,
        )
    else:
        narratives["technological_nature"] = PLACEHOLDER_TEXT

    for key, value in narratives.items():
        context["report_data"]["projects"][project_index][key] = value

    context["_project_narrative_slot"] = project_index + 1
    remaining = total_legacy - project_index - 1
    return {
        "status": "all_complete" if remaining == 0 else "success",
        "project_name": project.project_name,
        "narratives_generated": len(narratives),
        "completed_count": project_index + 1,
        "total_count": total_legacy,
        "remaining_count": remaining,
        "message": (
            "All project narratives generated." if remaining == 0
            else "Call generate_project_narratives_tool() again for the next project."
        ),
    }


def _generate_narrative(
    client: OpenAI,
    model: str,
    section_name: str,
    facts: list[str],
    instruction: str,
    source_answers: dict | None = None,
) -> str:
    """Generate a narrative from structured facts and raw source answers."""

    facts_text = "\n".join(f"- {fact}" for fact in facts) if facts else "(none provided)"

    source_text = ""
    if source_answers:
        lines = "\n".join(f"  [{qid}] {ans}" for qid, ans in source_answers.items())
        source_text = f"\nRaw interview answers (use as additional grounding):\n{lines}"

    prompt = f"""You are writing the "{section_name}" section for an R&D tax credit report.

Structured facts:
{facts_text}
{source_text}

{instruction}

CRITICAL RULES:
- Use ALL the structured facts provided above. Even if they are brief, synthesize them into a
  coherent narrative. You have enough data to write a proper section.
- Do NOT invent technical details, technologies, numbers, or claims not present in the input.
- Do NOT rephrase vague statements into confident technical assertions.
- Do NOT write "Analyst input required" — the structured facts above are sufficient to produce
  a complete section. Write the best narrative you can from the available data.
- Do not use hedging language such as "may", "could", "possibly", or "might"."""

    return _openai_call_with_retry(
        client, model, [{"role": "user", "content": prompt}]
    )


def generate_employee_activity_narrative_tool(context: dict = None) -> dict:
    """
    Tool: Generate a 2-3 sentence activity narrative for the NEXT pending employee.

    Call this tool repeatedly (with no arguments) until you receive
    "status": "all_complete".  The tool tracks its own position internally via
    context["_employee_narrative_slot"] — you MUST NOT pass any index argument.

    Covers ALL unique employees across ALL years (not just the final year) so
    employees who only appear in earlier years still receive LLM narratives.

    Returns:
        dict with status, employee_name, completed_count, total_count.
        When status == "all_complete" call generate_executive_summary_tool.
    """
    if not context or "study_data" not in context:
        return {"error": "No study_data in context"}

    # Build a deduplicated ordered list of all employees across all years.
    all_employees_by_id: dict = {}
    multi_year_data = context.get("multi_year_study_data") or []
    for yr_data in multi_year_data:
        for e in yr_data.get("employees", []):
            eid = e.get("employee_id") or e.get("employee_name", "")
            if eid not in all_employees_by_id:
                all_employees_by_id[eid] = e
    if not all_employees_by_id:
        for e in context["study_data"].get("employees", []):
            eid = e.get("employee_id") or e.get("employee_name", "")
            if eid not in all_employees_by_id:
                all_employees_by_id[eid] = e

    employees = list(all_employees_by_id.values())
    total_employees = len(employees)

    employee_index = context.get("_employee_narrative_slot", 0)
    if employee_index >= total_employees:
        context["_employee_narrative_slot"] = total_employees
        return {
            "status": "all_complete",
            "message": (
                f"All {total_employees} employee narrative(s) already generated. "
                "Call generate_executive_summary_tool next."
            ),
            "completed_count": total_employees,
            "total_count": total_employees,
        }

    emp = employees[employee_index]
    oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)

    name = emp.get("employee_name", f"Employee {employee_index + 1}")
    title = emp.get("job_title", "")
    activity_type = (emp.get("activity_type") or "direct_research").replace("_", " ")
    rd_desc = emp.get("rd_activities_description") or ""
    officer_detail = emp.get("owner_officer_detail") or ""
    source_answers = emp.get("source_answers") or {}
    allocs = emp.get("project_allocation") or []
    project_ids = [a.get("project_id", "") for a in allocs if a.get("project_id")]

    facts = [f for f in [rd_desc, officer_detail] if f]
    if not facts and not source_answers:
        narrative = (
            f"Analyst input required: No activity description (D1/D4) provided for "
            f"{name} ({title}) — describe the specific qualified research activities they performed."
        )
    else:
        source_text = ""
        if source_answers:
            lines = "\n".join(f"  [{qid}] {ans}" for qid, ans in source_answers.items())
            source_text = f"\nRaw interview answers:\n{lines}"

        officer_clause = (
            f" Note: {name} is an owner/officer — exclude general management, "
            f"business development, and non-technical activities. {officer_detail}"
            if emp.get("is_owner_officer") else ""
        )

        prompt = f"""Write 2-3 sentences describing the R&D activities of {name} ({title}) for an IRS R&D tax credit study.

Activity type: {activity_type}
Projects contributed to: {', '.join(project_ids) or 'see project list'}
Description of R&D work: {rd_desc or '(see interview answers below)'}
{source_text}
{officer_clause}

Requirements:
- Be specific and technical — reference actual research activities, not job titles.
- Write in formal third-person.
- Do NOT mention salary figures.
- Do NOT invent technical details not present in the input.
- If insufficient data, write: "Analyst input required: [what is missing]"
"""
        narrative = _openai_call_with_retry(
            oai_client, model, [{"role": "user", "content": prompt}]
        )

    # Write the narrative back into every year that contains this employee.
    emp_id = emp.get("employee_id") or emp.get("employee_name", "")
    for yr_data in context.get("multi_year_study_data") or []:
        for yr_emp in yr_data.get("employees", []):
            yr_eid = yr_emp.get("employee_id") or yr_emp.get("employee_name", "")
            if yr_eid == emp_id:
                yr_emp["generated_activity_narrative"] = narrative
    for sd_emp in context.get("study_data", {}).get("employees", []):
        sd_eid = sd_emp.get("employee_id") or sd_emp.get("employee_name", "")
        if sd_eid == emp_id:
            sd_emp["generated_activity_narrative"] = narrative

    # Advance the internal counter
    context["_employee_narrative_slot"] = employee_index + 1
    remaining = total_employees - employee_index - 1
    status = "all_complete" if remaining == 0 else "success"
    msg = (
        "All employee narratives generated. Call generate_executive_summary_tool next."
        if remaining == 0
        else "Call generate_employee_activity_narrative_tool() again for the next employee."
    )
    return {
        "status": status,
        "employee_name": name,
        "completed_count": employee_index + 1,
        "total_count": total_employees,
        "remaining_count": remaining,
        "message": msg,
    }


def handoff_to_compliance(context: dict = None) -> Handoff:
    """
    Tool: Handoff to ComplianceAgent after narrative generation.
    
    Args:
        context: Shared context dictionary
        
    Returns:
        Handoff to ComplianceAgent
    """
    from src.agents.compliance import compliance_agent
    
    return Handoff(
        agent=compliance_agent,
        context=context or {},
        reason="Narratives generated, ready for compliance validation"
    )


# Define Narrative Agent
narrative_agent = Agent(
    name="NarrativeAgent",
    instructions="""You are a senior R&D tax technical writer at Occams Advisory.

Your job is to generate structured narrative sections for a "Federal Research and Development Tax Credit Study" report.

=== CRITICAL INPUT RULES — follow without exception ===
Every sentence you write MUST be grounded in one or more of:
  (a) Structured fields from RDStudyData (technical_summary, four_part_test, etc.)
  (b) The project's source_answers dictionary — raw interview/questionnaire answers from the client

You MUST NOT:
- Invent technical details, technologies, uncertainties, or outcomes not present in the input.
- Rephrase vague or incomplete facts into confident technical assertions.
- Use hedging language: "may", "could", "possibly", "might", "perhaps".
- Modify or re-calculate any computed dollar amounts.

If source_answers or structured fields are empty for a section, write exactly:
  "Analyst input required: [describe what is missing]"

=== Output structure ===
1) Executive Summary
   - Opening paragraph: Occams performed a Federal R&D Tax Credit study for [client] for [tax year(s)].
   - Methodology summary paragraph.
   - "Information Collected:" bullet list (standard Occams format).
   - Total Federal credit statement using ONLY computed values provided.

2) R&D Tax Credit Analysis by Project
For each project, use these exact headings:
   i)   Basic Project Information
   ii)  Project Description           ← use technical_summary.objective + problem_statement + source_answers
   iii) New or Improved Business Component ← use business_component + results_or_outcome + source_answers
   iv)  Elimination of Uncertainty    ← use four_part_test.elimination_of_uncertainty + technical_uncertainty + source_answers
   v)   Process of Experimentation    ← use four_part_test.process_of_experimentation + experimentation_process + source_answers
   vi)  Technological in Nature       ← use four_part_test.technological_in_nature + source_answers

=== FIRST-TIME GENERATION (follow EXACTLY — this order is mandatory) ===

IMPORTANT: generate_project_narratives_tool and generate_employee_activity_narrative_tool
are STATEFUL — they track their own position internally. Call them with NO arguments.
Do NOT pass any index or other parameters.

1. Call generate_project_narratives_tool() — NO arguments.
   Check the returned "status":
   - "success": call generate_project_narratives_tool() again (no args) for the next slot.
   - "all_complete": ALL project-year narratives are done. Move to step 3.
   Repeat until status == "all_complete". This covers ALL projects in ALL years.

2. (Do NOT call anything between steps 1 and 3.)

3. Call generate_employee_activity_narrative_tool() — NO arguments.
   Check the returned "status":
   - "success": call generate_employee_activity_narrative_tool() again (no args).
   - "all_complete": ALL employee narratives are done. Move to step 5.
   Repeat until status == "all_complete".

4. (Do NOT call anything between steps 3 and 5.)

5. Call generate_executive_summary_tool() — LAST, after all project and employee narratives.
6. Call handoff_to_compliance()

CRITICAL ORDER RULE: Executive summary MUST be generated LAST — it synthesizes all completed
project narratives and employee descriptions. Calling it first produces an incomplete summary.
CRITICAL: Never pass index arguments to generate_project_narratives_tool or
generate_employee_activity_narrative_tool — they are fully self-advancing.

=== REVISION MODE — when sent back from ComplianceAgent due to compliance failures ===
You have been returned here because the ComplianceAgent found ERROR-level issues in the narratives.
DO NOT output chat text. DO NOT call handoff_to_compliance immediately.
You MUST fix the issues using tool calls first:

1. Reset the counters by calling generate_project_narratives_tool() with no args.
   Keep calling it (no args) until status == "all_complete" to regenerate ALL project narratives.
2. Call generate_employee_activity_narrative_tool() with no args.
   Keep calling it until status == "all_complete" to regenerate ALL employee narratives.
3. Then call generate_executive_summary_tool()
4. Then call handoff_to_compliance()

CRITICAL: In revision mode, you MUST call the generate_* tools — outputting text without tool calls
will cause an infinite loop. If you have nothing to regenerate, still call handoff_to_compliance()
as a tool call (NOT as chat text).

=== Chat output rules ===
- Do NOT reproduce, summarise, or quote any of the generated narrative text in your chat messages.
- Do NOT write out executive summary paragraphs, project descriptions, or any report content as chat text.
- Your only chat messages should be brief status lines such as:
    "Generating executive summary..." or "Revising sections with compliance issues..."
- All narrative content belongs inside the tool calls only.
""",
    functions=[
        generate_executive_summary_tool,
        generate_project_narratives_tool,
        generate_employee_activity_narrative_tool,
        handoff_to_compliance,
    ],
)

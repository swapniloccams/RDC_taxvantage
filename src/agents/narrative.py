"""Narrative Agent - generates executive summary and project narratives using OpenAI."""

import os
import json
from openai import OpenAI
from src.schema import ReportData, Project
from src.agents.framework import Agent, Handoff


PLACEHOLDER_TEXT = "[Needs analyst input - insufficient data provided]"


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
    model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")

    # ── Comprehensive / questionnaire path ──────────────────────────────────
    if context and "study_data" in context:
        study = context["study_data"]
        meta = study["study_metadata"]
        client_name = meta["prepared_for"]["legal_name"]
        tax_year = meta["tax_year"]["year_label"]
        total_qre = str(context.get("total_qre", "N/A"))
        federal_credit = str(context.get("asc_computation", {}).get("federal_credit", "N/A"))

        project_lines = []
        for p in study.get("rd_projects", []):
            ts = p.get("technical_summary", {})
            obj = ts.get("objective", "")
            project_lines.append(
                f"- {p['project_name']} ({p.get('status','')}):{(' ' + obj) if obj else ''}"
            )

        info_collected = [
            "Employee W-2 wages and time allocations by project",
            "Contractor invoices and rights & risk confirmations",
            "Project descriptions, technical objectives, and outcomes",
            "Technical uncertainties and process of experimentation details",
            "Cloud computing and supply expenditures (where applicable)",
            "Supporting documentation (Jira tickets, GitHub repos, design docs)",
        ]

        prompt = f"""You are writing the Executive Summary for a Federal R&D Tax Credit Study prepared by Occams Advisory.

Client: {client_name}
Tax Year: {tax_year}
Total QRE: {total_qre}
Federal R&D Credit: {federal_credit}

Qualified Research Projects:
{chr(10).join(project_lines)}

Information Collected:
{chr(10).join('• ' + item for item in info_collected)}

Write a professional executive summary that:
1. Opens with a paragraph stating Occams Advisory performed a Federal R&D Tax Credit study for {client_name} for tax year {tax_year}.
2. Summarises the methodology at a high level (one paragraph).
3. Includes a bullet list titled "Information Collected:" using the items above.
4. Closes with a statement of the total Federal credit of {federal_credit}.

CRITICAL: Only use the facts listed above. Do not invent technical details. Do not use hedging language."""

        response = oai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
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

    response = oai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    summary = response.choices[0].message.content.strip()

    if context and "report_data" in context:
        context["report_data"]["executive_summary"] = summary

    return summary


def generate_project_narratives_tool(project_index: int = 0, context: dict = None) -> dict:
    """
    Tool: Generate all narrative sections for a single project.

    Supports two context paths:
    - Questionnaire / comprehensive: context["study_data"] (RDStudyData format)
      Reads from rd_projects[].technical_summary, four_part_test, source_answers.
      Writes generated text into rd_projects[].generated_narratives.
    - Legacy CSV: context["report_data"] (ReportData format)

    Args:
        project_index: Index of project to generate narratives for
        context: Shared context dictionary

    Returns:
        Dictionary with status and narratives_generated count
    """
    oai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")

    # ── Comprehensive / questionnaire path ──────────────────────────────────
    if context and "study_data" in context:
        rd_projects = context["study_data"].get("rd_projects", [])
        if project_index >= len(rd_projects):
            return {"error": f"Invalid project index {project_index} — only {len(rd_projects)} project(s) loaded"}

        proj = rd_projects[project_index]
        ts = proj.get("technical_summary", {})
        fpt = proj.get("four_part_test", {})
        source_answers: dict = proj.get("source_answers") or {}
        project_name = proj.get("project_name", f"Project {project_index + 1}")

        narratives = {}

        # ii) Project Description
        desc_facts = [f for f in [ts.get("objective"), ts.get("problem_statement"),
                                   ts.get("results_or_outcome")] if f]
        narratives["project_description"] = _generate_narrative(
            oai_client, model,
            "Project Description",
            desc_facts,
            f"Describe the R&D project '{project_name}'. Write 1-2 paragraphs explaining "
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
            "Describe the new or improved business component that resulted from this R&D project. "
            "Focus on what was created or enhanced. Write 1 paragraph.",
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
            "Describe the technical uncertainties that existed at project inception and how the "
            "team worked to resolve them. Write 1-2 paragraphs.",
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
            "Describe the systematic process of experimentation: iterations, testing, and refinements. "
            "Write 1-2 paragraphs.",
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

        # Store generated narratives back into study_data for renderer and compliance
        context["study_data"]["rd_projects"][project_index]["generated_narratives"] = narratives

        return {
            "status": "success",
            "project_name": project_name,
            "narratives_generated": len(narratives),
        }

    # ── Legacy path ─────────────────────────────────────────────────────────
    if not context or "report_data" not in context:
        return {"error": "No report data in context"}

    report_data = ReportData(**context["report_data"])

    if project_index >= len(report_data.projects):
        return {"error": f"Invalid project index: {project_index}"}

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

    return {
        "status": "success",
        "project_name": project.project_name,
        "narratives_generated": len(narratives),
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
- Only use the facts and interview answers provided above.
- Do NOT invent technical details, technologies, numbers, or claims not present in the input.
- Do NOT rephrase vague statements into confident technical assertions.
- If the facts and answers are insufficient for a complete section, write:
  "Analyst input required: [describe exactly what is missing]"
- Do not use hedging language such as "may", "could", "possibly", or "might"."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()


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

=== Tool usage (follow exactly) ===
1. Call generate_executive_summary_tool()
2. Call generate_project_narratives_tool(project_index=0) for first project
3. Call generate_project_narratives_tool(project_index=N) for each subsequent project
4. AFTER all projects, MUST call handoff_to_compliance()

CRITICAL: Do NOT end your turn without calling handoff_to_compliance().

=== Chat output rules ===
- Do NOT reproduce, summarise, or quote any of the generated narrative text in your chat messages.
- Do NOT write out executive summary paragraphs, project descriptions, or any report content as chat text.
- Your only chat messages should be brief status lines such as:
    "Generating executive summary..." or "Narratives complete, handing off to compliance."
- All narrative content belongs inside the tool calls only.
""",
    functions=[generate_executive_summary_tool, generate_project_narratives_tool, handoff_to_compliance],
)

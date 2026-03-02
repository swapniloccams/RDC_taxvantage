"""Compliance Agent - validates report completeness and quality."""

import json
import re
from typing import List, Dict, Any
from src.schema import ReportData
from src.agents.framework import Agent, Handoff


PLACEHOLDER_PATTERN = r"\[Needs analyst input[^\]]*\]"
WEAK_LANGUAGE = ["may", "could", "possibly", "might", "perhaps"]


def validate_report_completeness(report_data_json: str = None, context: dict = None) -> dict:
    """
    Tool: Check report for compliance issues.

    Supports two context paths:
    - Questionnaire / comprehensive: context["study_data"] — checks executive_summary
      and rd_projects[].generated_narratives for all 5 sections.
    - Legacy CSV: context["report_data"] — original behaviour.

    Args:
        report_data_json: JSON string of report data (optional, legacy only)
        context: Shared context dictionary

    Returns:
        Dictionary with compliance status and issues
    """
    issues = []

    # ── Comprehensive / questionnaire path ──────────────────────────────────
    if context and "study_data" in context:
        study = context["study_data"]

        # Executive summary
        exec_summary = study.get("executive_summary", "")
        if not exec_summary:
            issues.append({
                "severity": "ERROR",
                "section": "Executive Summary",
                "issue": "Missing executive summary — generate_executive_summary_tool was not called or failed",
            })
        elif re.search(PLACEHOLDER_PATTERN, exec_summary):
            issues.append({
                "severity": "ERROR",
                "section": "Executive Summary",
                "issue": "Executive summary contains placeholder text",
            })

        # Per-project narrative sections
        narrative_keys = [
            ("project_description",    "Project Description"),
            ("new_improved_component", "New/Improved Business Component"),
            ("elimination_uncertainty","Elimination of Uncertainty"),
            ("process_experimentation","Process of Experimentation"),
            ("technological_nature",   "Technological in Nature"),
        ]

        for proj in study.get("rd_projects", []):
            project_name = proj.get("project_name", proj.get("project_id", "Unknown"))
            gen = proj.get("generated_narratives") or {}

            if not gen:
                issues.append({
                    "severity": "ERROR",
                    "section": project_name,
                    "issue": "No generated_narratives found — generate_project_narratives_tool was not called for this project",
                })
                continue

            for key, label in narrative_keys:
                text = gen.get(key, "")
                if not text:
                    issues.append({
                        "severity": "ERROR",
                        "section": f"{project_name} — {label}",
                        "issue": "Narrative section missing",
                    })
                elif re.search(PLACEHOLDER_PATTERN, text):
                    issues.append({
                        "severity": "ERROR",
                        "section": f"{project_name} — {label}",
                        "issue": "Contains placeholder text — more source data required",
                    })
                else:
                    for weak_word in WEAK_LANGUAGE:
                        if re.search(rf"\b{weak_word}\b", text, re.IGNORECASE):
                            issues.append({
                                "severity": "WARNING",
                                "section": f"{project_name} — {label}",
                                "issue": f"Contains weak language: '{weak_word}'",
                            })
                            break

        errors = [i for i in issues if i["severity"] == "ERROR"]
        warnings = [i for i in issues if i["severity"] == "WARNING"]
        is_compliant = len(errors) == 0

        if context:
            existing = context.get("compliance_issues") or []
            context["compliance_issues"] = existing + issues
            context["is_compliant"] = is_compliant

        return {
            "is_compliant": is_compliant,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "issues": issues,
        }

    # ── Legacy path ─────────────────────────────────────────────────────────
    if context and "report_data" in context:
        data_dict = context["report_data"]
    elif report_data_json:
        data_dict = json.loads(report_data_json)
    else:
        return {"error": "No report data provided"}

    report_data = ReportData(**data_dict)

    if not report_data.executive_summary:
        issues.append({
            "severity": "ERROR",
            "section": "Executive Summary",
            "issue": "Missing executive summary",
        })
    elif re.search(PLACEHOLDER_PATTERN, report_data.executive_summary):
        issues.append({
            "severity": "ERROR",
            "section": "Executive Summary",
            "issue": "Contains placeholder text",
        })

    for project in report_data.projects:
        project_name = project.project_name
        narrative_sections = [
            ("project_description_narrative", "Project Description"),
            ("new_improved_component",        "New/Improved Component"),
            ("elimination_uncertainty",       "Elimination of Uncertainty"),
            ("process_experimentation",       "Process of Experimentation"),
            ("technological_nature",          "Technological in Nature"),
        ]
        for field_name, section_name in narrative_sections:
            narrative = getattr(project, field_name, None)
            if not narrative:
                issues.append({
                    "severity": "ERROR",
                    "section": f"{project_name} - {section_name}",
                    "issue": "Missing narrative",
                })
            elif re.search(PLACEHOLDER_PATTERN, narrative):
                issues.append({
                    "severity": "ERROR",
                    "section": f"{project_name} - {section_name}",
                    "issue": "Contains placeholder text - needs more facts",
                })
            else:
                for weak_word in WEAK_LANGUAGE:
                    if re.search(rf"\b{weak_word}\b", narrative, re.IGNORECASE):
                        issues.append({
                            "severity": "WARNING",
                            "section": f"{project_name} - {section_name}",
                            "issue": f"Contains weak language: '{weak_word}'",
                        })
                        break

    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]
    is_compliant = len(errors) == 0

    if context:
        context["compliance_issues"] = issues
        context["is_compliant"] = is_compliant

    return {
        "is_compliant": is_compliant,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
    }


def validate_questionnaire_completeness(context: dict = None) -> dict:
    """
    Tool: Validate that questionnaire-sourced fields are complete before narrative/render.

    Checks:
    - All four 4-part test fields are populated per project.
    - Each project has at least one source_answer (traceability).
    - Employee project allocations sum to ~1.0.
    - Contractors pass rights & risk gate.

    This check is skipped gracefully if the pipeline used CSV/JSON input (non-questionnaire path).

    Args:
        context: Shared pipeline context.

    Returns:
        dict with issues list and error_count.
    """
    study_data = (context or {}).get("study_data")
    if not study_data:
        return {
            "skipped": True,
            "reason": "No study_data in context — questionnaire completeness check not applicable",
            "issues": [],
            "error_count": 0,
        }

    issues: list[dict] = []

    four_part_fields = [
        "permitted_purpose",
        "technological_in_nature",
        "elimination_of_uncertainty",
        "process_of_experimentation",
    ]

    for project in study_data.get("rd_projects", []):
        pid = project.get("project_id", "UNKNOWN")
        fpt = project.get("four_part_test") or {}

        for field in four_part_fields:
            value = fpt.get(field, "")
            if not value or not str(value).strip():
                issues.append({
                    "severity": "ERROR",
                    "section": f"Project {pid} — Four Part Test",
                    "issue": f"Missing four_part_test.{field} — narrative cannot be substantiated",
                })

        # Source answers traceability
        source_answers = project.get("source_answers") or {}
        if not source_answers:
            issues.append({
                "severity": "WARNING",
                "section": f"Project {pid}",
                "issue": (
                    "No source_answers found — narrative claims cannot be traced "
                    "back to questionnaire responses"
                ),
            })

    for emp in study_data.get("employees", []):
        eid = emp.get("employee_id", "UNKNOWN")
        allocations = emp.get("project_allocation") or []
        total = sum(
            (a.get("percent_of_employee_time") or 0.0) for a in allocations
        )
        if not (0.98 <= total <= 1.02):
            issues.append({
                "severity": "ERROR",
                "section": f"Employee {eid}",
                "issue": (
                    f"Project allocations sum to {total:.4f} — "
                    "expected approximately 1.0"
                ),
            })

    for contractor in study_data.get("contractors", []):
        vid = contractor.get("vendor_id", "UNKNOWN")
        rr = contractor.get("rights_and_risk") or {}
        if not rr.get("company_retains_rights"):
            issues.append({
                "severity": "ERROR",
                "section": f"Contractor {vid}",
                "issue": (
                    "company_retains_rights is False — "
                    "contractor does not pass the rights & risk test and will be excluded from QRE"
                ),
            })
        if not rr.get("company_bears_financial_risk"):
            issues.append({
                "severity": "ERROR",
                "section": f"Contractor {vid}",
                "issue": (
                    "company_bears_financial_risk is False — "
                    "contractor does not pass the rights & risk test and will be excluded from QRE"
                ),
            })

    error_count = sum(1 for i in issues if i["severity"] == "ERROR")

    if context is not None:
        existing = context.get("compliance_issues") or []
        context["compliance_issues"] = existing + issues

    return {
        "skipped": False,
        "issues": issues,
        "error_count": error_count,
        "warning_count": sum(1 for i in issues if i["severity"] == "WARNING"),
    }


def handoff_to_narrative_for_revision(context: dict = None) -> Handoff:
    """
    Tool: Handoff back to NarrativeAgent if compliance fails.
    
    Args:
        context: Shared context dictionary
        
    Returns:
        Handoff to NarrativeAgent with revision instructions
    """
    from src.agents.narrative import narrative_agent
    
    issues = context.get("compliance_issues", []) if context else []
    
    return Handoff(
        agent=narrative_agent,
        context=context or {},
        reason=f"Compliance validation failed with {len(issues)} issues - needs revision"
    )


def save_pdf_content_json(context: dict = None) -> dict:
    """
    Tool: Save structured PDF content as JSON file (legacy path only).

    For the comprehensive / questionnaire path (context has 'study_data'), this step
    is not needed — the RenderAgent reads study_data directly via build_comprehensive_pdf.
    In that case this function skips gracefully and returns success so the pipeline can
    proceed to handoff_to_render.

    For the legacy CSV path (context has 'report_data'), it builds a page-by-page JSON
    organised by sections with formatting metadata.

    Args:
        context: Shared context dictionary

    Returns:
        Dictionary with save status and file path
    """
    import json
    from pathlib import Path
    from src.schema import ReportData
    from src.render.styles import format_currency

    # ── Comprehensive / questionnaire path: skip, renderer reads study_data directly ──
    if context and "study_data" in context:
        return {
            "status": "skipped",
            "message": (
                "save_pdf_content_json is not required for the questionnaire/comprehensive path. "
                "The RenderAgent reads study_data directly. Proceed to handoff_to_render."
            ),
        }

    if not context or "report_data" not in context:
        return {"error": "No report data in context"}
    
    if not context.get("output_dir"):
        return {"error": "No output directory in context"}
    
    report_data = ReportData(**context["report_data"])
    output_dir = Path(context["output_dir"])
    
    # Build structured PDF content
    pdf_content = {
        "metadata": {
            "document_title": "Federal Research and Development Tax Credit Study",
            "client_name": report_data.report_meta.client_company,
            "tax_years": report_data.get_year_range_str(),
            "total_federal_credit": format_currency(
                sum(exp.federal_credit for exp in report_data.expenditures_by_year)
            ),
            "generation_date": context.get("generation_date", ""),
        },
        "pages": []
    }
    
    # Page 1: Title Page
    pdf_content["pages"].append({
        "page_number": 1,
        "page_title": "Title Page",
        "sections": [
            {
                "section_type": "title_page",
                "content": {
                    "title": "Federal Research and Development Tax Credit Study",
                    "client": report_data.report_meta.client_company,
                    "years": report_data.get_year_range_str(),
                }
            }
        ]
    })
    
    # Page 2: Executive Summary
    pdf_content["pages"].append({
        "page_number": 2,
        "page_title": "Executive Summary",
        "sections": [
            {
                "section_type": "heading",
                "level": 1,
                "content": "Executive Summary"
            },
            {
                "section_type": "paragraph",
                "content": report_data.executive_summary or "[Executive summary not generated]"
            }
        ]
    })
    
    # Page 3: Statutory Authority
    pdf_content["pages"].append({
        "page_number": 3,
        "page_title": "Statutory Authority",
        "sections": [
            {
                "section_type": "heading",
                "level": 1,
                "content": "Statutory Authority for Federal R&D Tax Credit"
            },
            {
                "section_type": "paragraph",
                "content": "Section 41 of the Internal Revenue Code provides a tax credit for increasing research activities..."
            }
        ]
    })
    
    # Page 4: Expenditure Summary Table
    expenditure_table = {
        "title": "Summary of R&D Expenditures",
        "headers": ["Tax Year", "Qualified Wages", "Qualified Contractors", "Qualified Supplies", "Qualified Cloud", "Total QRES", "Federal Credit"],
        "rows": []
    }
    
    for exp in report_data.expenditures_by_year:
        expenditure_table["rows"].append({
            "cells": [
                str(exp.year),
                format_currency(exp.qualified_wages),
                format_currency(exp.qualified_contractors),
                format_currency(exp.qualified_supplies),
                format_currency(exp.qualified_cloud),
                format_currency(exp.total_qres),
                format_currency(exp.federal_credit),
            ]
        })
    
    pdf_content["pages"].append({
        "page_number": 4,
        "page_title": "Expenditure Summary",
        "sections": [
            {
                "section_type": "heading",
                "level": 1,
                "content": "Summary of R&D Expenditures"
            },
            {
                "section_type": "table",
                "table": expenditure_table
            }
        ]
    })
    
    # Pages 5+: Project Analyses
    page_num = 5
    for project in report_data.projects:
        project_page = {
            "page_number": page_num,
            "page_title": f"Project Analysis: {project.project_name}",
            "sections": [
                {
                    "section_type": "heading",
                    "level": 1,
                    "content": f"R&D Tax Credit Analysis: {project.project_name}"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "i) Basic Project Information"
                },
                {
                    "section_type": "paragraph",
                    "content": f"Project ID: {project.project_id}\\nStatus: {project.status}\\nEmployees: {', '.join(project.employees) if project.employees else 'N/A'}"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "ii) Project Description"
                },
                {
                    "section_type": "paragraph",
                    "content": project.project_description_narrative or "[Not provided]"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "iii) New or Improved Business Component"
                },
                {
                    "section_type": "paragraph",
                    "content": project.new_improved_component or "[Not provided]"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "iv) Elimination of Uncertainty"
                },
                {
                    "section_type": "paragraph",
                    "content": project.elimination_uncertainty or "[Not provided]"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "v) Process of Experimentation"
                },
                {
                    "section_type": "paragraph",
                    "content": project.process_experimentation or "[Not provided]"
                },
                {
                    "section_type": "heading",
                    "level": 2,
                    "content": "vi) Technological in Nature"
                },
                {
                    "section_type": "paragraph",
                    "content": project.technological_nature or "[Not provided]"
                }
            ]
        }
        pdf_content["pages"].append(project_page)
        page_num += 1
    
    # Save to file
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_content_path = artifacts_dir / "pdf_content.json"
    with open(pdf_content_path, "w") as f:
        json.dump(pdf_content, f, indent=2, default=str)
    
    return {
        "status": "success",
        "message": f"Saved structured PDF content to {pdf_content_path}",
        "file_path": str(pdf_content_path),
        "total_pages": len(pdf_content["pages"]),
    }


def handoff_to_render(context: dict = None) -> Handoff:
    """
    Tool: Handoff to RenderAgent if compliance passes.
    
    Args:
        context: Shared context dictionary
        
    Returns:
        Handoff to RenderAgent
    """
    from src.agents.render_agent import render_agent
    
    return Handoff(
        agent=render_agent,
        context=context or {},
        reason="Compliance validation passed, ready for PDF generation"
    )


# Define Compliance Agent
compliance_agent = Agent(
    name="ComplianceAgent",
    instructions="""You are a compliance review agent for Occams Advisory tax credit study reports.

Your responsibilities:
1. Validate questionnaire completeness (if applicable).
2. Validate narrative report completeness and quality.
3. Decide whether to proceed or request revision.

=== Checks to perform ===
(a) Questionnaire completeness (questionnaire input path only):
    - All 4-part test fields populated per project.
    - Employee allocations sum to ~1.0.
    - Contractors pass rights & risk test.
    - Source answers present for traceability.

(b) Report narrative completeness:
    - Executive Summary exists and has no placeholders.
    - All project sections i–vi are present.
    - No "Analyst input required" placeholders remain (treat as ERRORs).
    - No weak language: "may", "could", "possibly", "might", "perhaps".
    - No currency figures that differ from computed values.
    - Headings follow the required Occams format.

=== Decision rules ===
- If any ERROR-level issues exist → call handoff_to_narrative_for_revision() with the issue list.
- If only WARNING-level issues (no ERRORs) → proceed to render, warnings do NOT block.
- If fully compliant (0 errors) → proceed to render.

=== Tool usage order ===
1. Call validate_questionnaire_completeness() first (safe on any path — skips gracefully).
2. Call validate_report_completeness() for narrative checks.
3. Decide:
   - If ERROR-level issues → call handoff_to_narrative_for_revision().
   - If 0 errors (warnings are OK) → go to step 4.
4. Call save_pdf_content_json().
   - If it returns status "skipped" (questionnaire/comprehensive path) → that is expected and correct.
   - If it returns status "success" (legacy path) → that is also correct.
   - In BOTH cases, immediately call handoff_to_render() after.
5. Call handoff_to_render() — this is ALWAYS the final step when there are no blocking errors.

CRITICAL: Do NOT stop after save_pdf_content_json returns "skipped".
          "skipped" means the step was intentionally bypassed — call handoff_to_render() immediately.
""",
    functions=[
        validate_questionnaire_completeness,
        validate_report_completeness,
        save_pdf_content_json,
        handoff_to_narrative_for_revision,
        handoff_to_render,
    ],
)


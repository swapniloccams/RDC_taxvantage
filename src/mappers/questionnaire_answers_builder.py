"""
Questionnaire Answers Builder.

Converts a flat, human-friendly raw-answers dict (keyed by domain concept,
not by internal schema field names) into a fully-valid QuestionnaireAnswers
dict that can be fed directly into the pipeline.

This is the bridge between any user-facing intake layer (web form, chat agent,
CLI wizard, etc.) and the existing QuestionnaireIngestionAgent → pipeline flow.

Input format (``raw``):
    See ``build_answers_json()`` docstring for the full field specification.

Output:
    A dict that validates against ``QuestionnaireAnswers`` — ready for either:
      • ``QuestionnaireAnswers(**result)`` (in-memory)
      • Writing to ``answers.json`` and passing to the CLI
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_answers_json(raw: dict) -> dict:
    """
    Map a human-friendly raw answers dict to a QuestionnaireAnswers-compatible dict.

    Required top-level keys in ``raw``:
        client_legal_name   str   Company legal name
        ein                 str   XX-XXXXXXX format
        entity_type         str   C-Corp | S-Corp | LLC | Partnership | Sole Proprietor
        address             str   Full mailing address
        industry            str   Industry description
        tax_year            str   YYYY
        credit_method       str   ASC | Regular
        preparer_firm       str   Preparing firm name
        preparer_name       str   Preparer name + credential
        date_prepared       str   YYYY-MM-DD
        business_overview   str   Q1 — company description
        products_and_services  list[str]  Q2
        rd_departments      list[str]    Q3
        locations           list[str]    Q4
        gross_receipts      dict         Q6 — keys: year_0, year_minus_1/2/3
        projects            list[dict]   See _build_project()
        employees           list[dict]   See _build_employee()
        methodology_summary str          Q50
        limitations         list[str]    Q46-Q49
        disclaimer_text     str

    Optional top-level keys:
        website                     str
        org_structure_summary       str   (auto-generated from rd_departments if missing)
        prior_year_credit_claimed   bool  Q5
        funded_by_third_party       bool  Q7 — appended to limitations if True
        wages_used_for_other_credits bool Q8 — appended to limitations if True
        prior_year_qres             dict  enabled + year_minus_1/2/3_qre
        contractors                 list[dict]  See _build_contractor()
        supplies                    list[dict]  See _build_supply()
        cloud_computing             list[dict]  See _build_cloud()

    Returns:
        dict compatible with ``QuestionnaireAnswers(**result)``.

    Raises:
        ValueError: if required keys are missing or values are invalid.
    """
    _require(raw, [
        "client_legal_name", "ein", "entity_type", "address", "industry",
        "tax_year", "credit_method", "preparer_firm", "preparer_name",
        "date_prepared", "business_overview", "products_and_services",
        "rd_departments", "locations", "gross_receipts",
        "projects", "employees",
        "methodology_summary", "limitations", "disclaimer_text",
    ])

    # Auto-assign project IDs in order so employee/contractor allocation
    # dicts that reference projects by NAME can be resolved.
    project_id_map = _assign_project_ids(raw["projects"])

    projects = [
        _build_project(p, project_id_map, idx)
        for idx, p in enumerate(raw["projects"], 1)
    ]

    employees = [
        _build_employee(e, project_id_map, idx)
        for idx, e in enumerate(raw["employees"], 1)
    ]

    contractors = [
        _build_contractor(c, project_id_map, idx)
        for idx, c in enumerate(raw.get("contractors", []), 1)
    ]

    supplies = [
        _build_supply(s, project_id_map, idx)
        for idx, s in enumerate(raw.get("supplies", []), 1)
    ]

    cloud_computing = [
        _build_cloud(c, project_id_map, idx)
        for idx, c in enumerate(raw.get("cloud_computing", []), 1)
    ]

    # Build limitations list — include compliance flags from Q7/Q8
    limitations = list(raw.get("limitations", []))
    if raw.get("funded_by_third_party"):
        limitations.append(
            "Some research activities may have been partially funded by customers or grants "
            "— funded portions have been excluded from the QRE calculation."
        )
    if raw.get("wages_used_for_other_credits"):
        limitations.append(
            "Certain wages claimed under this study may also be subject to other federal "
            "tax credits (e.g. ERC, WOTC) — double-dipping exclusions have been applied."
        )

    # org_structure_summary: use raw value or auto-generate from departments
    org_summary = raw.get("org_structure_summary") or (
        "R&D activities are carried out by the following departments: "
        + ", ".join(raw["rd_departments"]) + "."
    )

    # Prior year QREs
    prior_year_qres = None
    if raw.get("prior_year_qres"):
        prior_year_qres = {
            "enabled": raw["prior_year_qres"].get("enabled", True),
            "year_minus_1_qre": float(raw["prior_year_qres"].get("year_minus_1_qre", 0.0)),
            "year_minus_2_qre": float(raw["prior_year_qres"].get("year_minus_2_qre", 0.0)),
            "year_minus_3_qre": float(raw["prior_year_qres"].get("year_minus_3_qre", 0.0)),
        }

    gr = raw["gross_receipts"]

    result = {
        "study_metadata_answers": {
            "client_legal_name": raw["client_legal_name"],
            "ein":               raw["ein"],
            "entity_type":       raw["entity_type"],
            "address":           raw["address"],
            "industry":          raw["industry"],
            "website":           raw.get("website"),
            "tax_year":          str(raw["tax_year"]),
            "credit_method":     raw.get("credit_method", "ASC"),
            "preparer_firm":     raw["preparer_firm"],
            "preparer_name":     raw["preparer_name"],
            "date_prepared":     raw.get("date_prepared") or date.today().isoformat(),
        },
        "company_background_answers": {
            "business_overview":     raw["business_overview"],
            "products_and_services": raw["products_and_services"],
            "rd_departments":        raw["rd_departments"],
            "locations":             raw["locations"],
            "org_structure_summary": org_summary,
        },
        "gross_receipts_answers": {
            "year_0":       float(gr.get("year_0",       gr.get("current_year", 0))),
            "year_minus_1": float(gr.get("year_minus_1", gr.get("prior_year_1", 0))),
            "year_minus_2": float(gr.get("year_minus_2", gr.get("prior_year_2", 0))),
            "year_minus_3": float(gr.get("year_minus_3", gr.get("prior_year_3", 0))),
        },
        "projects":          projects,
        "employees":         employees,
        "contractors":       contractors,
        "supplies":          supplies,
        "cloud_computing":   cloud_computing,
        "methodology_disclosures_answers": {
            "methodology_summary": raw["methodology_summary"],
            "limitations":         limitations,
            "disclaimer_text":     raw["disclaimer_text"],
        },
    }

    if prior_year_qres:
        result["prior_year_qres"] = prior_year_qres

    return result


# ---------------------------------------------------------------------------
# Project builder
# ---------------------------------------------------------------------------

def _build_project(p: dict, project_id_map: dict[str, str], idx: int) -> dict:
    """Build a single ProjectAnswers-compatible dict."""
    project_id = project_id_map.get(p["project_name"], f"P{idx:03d}")

    # Build hypotheses from alternatives_considered / experimentation_process if absent
    hypotheses = p.get("hypotheses_tested") or []

    return {
        "project_id":            project_id,
        "project_name":          p["project_name"],
        "business_component":    p.get("business_component", p["project_name"]),
        "status":                _normalize_status(p.get("status", "Ongoing")),
        "objective":             p.get("objective", ""),
        "problem_statement":     p.get("problem_statement", ""),
        "technical_uncertainty": p.get("technical_uncertainty", ""),
        "hypotheses_tested":     hypotheses,
        "experimentation_process":    _ensure_list(p.get("experimentation_process", [])),
        "alternatives_considered":    _ensure_list(p.get("alternatives_considered", [])),
        "results_or_outcome":    p.get("results_or_outcome", ""),
        "failures_or_iterations": p.get("failures_or_iterations", ""),
        "permitted_purpose":          p.get("permitted_purpose") or (
            f"The project developed {p.get('business_component', p['project_name'])} "
            f"as a new or improved business component. {p.get('objective', '')}"
        ).strip(),
        "technological_in_nature":    p.get("technological_in_nature", ""),
        "elimination_of_uncertainty": p.get("elimination_of_uncertainty") or p.get("technical_uncertainty", ""),
        "process_of_experimentation": p.get("process_of_experimentation") or (
            " ".join(_ensure_list(p.get("experimentation_process", [])))
        ),
        "jira_links":     _ensure_list(p.get("jira_links", [])),
        "github_links":   _ensure_list(p.get("github_links", [])),
        "design_docs":    _ensure_list(p.get("design_docs", [])),
        "test_reports":   _ensure_list(p.get("test_reports", [])),
        "other_docs":     _ensure_list(p.get("other_docs", [])),
        "source_answers": p.get("source_answers", {}),
        # New fields from schema gap additions
        "start_date":    p.get("start_date"),
        "end_date":      p.get("end_date"),
        "funding_type":  p.get("funding_type", "Internal"),
    }


# ---------------------------------------------------------------------------
# Employee builder
# ---------------------------------------------------------------------------

def _build_employee(e: dict, project_id_map: dict[str, str], idx: int) -> dict:
    """Build a single EmployeeAnswers-compatible dict."""
    raw_alloc = e.get("project_allocation", {})
    allocation = _resolve_and_normalize_allocation(raw_alloc, project_id_map)

    return {
        "employee_id":           f"E{idx:03d}",
        "employee_name":         e["employee_name"],
        "job_title":             e.get("job_title", ""),
        "department":            e.get("department", ""),
        "location":              e.get("location", ""),
        "w2_box_1_wages":        float(e.get("w2_box_1_wages", 0)),
        "qualified_percentage":  _normalize_pct(e.get("qualified_percentage", 0)),
        "qualification_basis":   _normalize_basis(e.get("qualification_basis", "Interview")),
        "project_allocation":    allocation,
        "notes":                 e.get("notes"),
        "source_answers":        e.get("source_answers", {}),
    }


# ---------------------------------------------------------------------------
# Contractor builder
# ---------------------------------------------------------------------------

def _build_contractor(c: dict, project_id_map: dict[str, str], idx: int) -> dict:
    """Build a single ContractorAnswers-compatible dict."""
    raw_alloc = c.get("project_allocation", {})
    allocation = _resolve_and_normalize_allocation(raw_alloc, project_id_map)

    return {
        "vendor_id":             f"V{idx:03d}",
        "vendor_name":           c["vendor_name"],
        "description_of_work":   c.get("description_of_work", ""),
        "total_amount_paid":     float(c.get("total_amount_paid", 0)),
        "qualified_percentage":  _normalize_pct(c.get("qualified_percentage", 1.0)),
        "company_retains_rights":       bool(c.get("company_retains_rights", True)),
        "company_bears_financial_risk": bool(c.get("company_bears_financial_risk", True)),
        "supporting_contract_reference": c.get("supporting_contract_reference", "Contract on file"),
        "project_allocation":    allocation,
        "notes":                 c.get("notes"),
        "source_answers":        c.get("source_answers", {}),
    }


# ---------------------------------------------------------------------------
# Supply builder
# ---------------------------------------------------------------------------

def _build_supply(s: dict, project_id_map: dict[str, str], idx: int) -> dict:
    raw_alloc = s.get("project_allocation", {})
    allocation = _resolve_and_normalize_allocation(raw_alloc, project_id_map)

    return {
        "supply_id":             f"S{idx:03d}",
        "description":           s.get("description", ""),
        "vendor":                s.get("vendor", ""),
        "invoice_reference":     s.get("invoice_reference", "See records"),
        "amount":                float(s.get("amount", 0)),
        "qualified_percentage":  _normalize_pct(s.get("qualified_percentage", 1.0)),
        "project_allocation":    allocation,
    }


# ---------------------------------------------------------------------------
# Cloud computing builder
# ---------------------------------------------------------------------------

def _build_cloud(c: dict, project_id_map: dict[str, str], idx: int) -> dict:
    raw_alloc = c.get("project_allocation", {})
    allocation = _resolve_and_normalize_allocation(raw_alloc, project_id_map)

    return {
        "cloud_id":              f"C{idx:03d}",
        "provider":              c.get("provider", ""),
        "service_category":      c.get("service_category", ""),
        "billing_reference":     c.get("billing_reference", "See billing records"),
        "amount":                float(c.get("amount", 0)),
        "qualified_percentage":  _normalize_pct(c.get("qualified_percentage", 1.0)),
        "project_allocation":    allocation,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assign_project_ids(projects: list[dict]) -> dict[str, str]:
    """Return {project_name → P001, P002, ...} mapping."""
    return {p["project_name"]: f"P{i:03d}" for i, p in enumerate(projects, 1)}


def _resolve_and_normalize_allocation(
    raw_alloc: dict[str, float],
    project_id_map: dict[str, str],
) -> dict[str, float]:
    """
    Accept allocation keys that are either project IDs (P001) or project names,
    resolve names to IDs, normalize values so they sum to 1.0.
    """
    if not raw_alloc:
        return {}

    resolved: dict[str, float] = {}
    for key, val in raw_alloc.items():
        pid = project_id_map.get(key, key)  # resolve name → ID, or keep if already ID
        resolved[pid] = float(val)

    # Normalize percentage-scale values (e.g. 70 → 0.70)
    if any(v > 1.5 for v in resolved.values()):
        resolved = {k: v / 100.0 for k, v in resolved.items()}

    # Normalize so values sum to 1.0
    total = sum(resolved.values())
    if total > 0 and abs(total - 1.0) > 0.02:
        resolved = {k: round(v / total, 6) for k, v in resolved.items()}

    return resolved


def _normalize_pct(val: Any) -> float:
    """Convert percentage to 0.0–1.0 range."""
    try:
        f = float(val)
        return f / 100.0 if f > 1.5 else f
    except (TypeError, ValueError):
        return 0.0


def _normalize_basis(val: str) -> str:
    """Map common qualification basis strings to exact allowed values."""
    mapping = {
        "interview":       "Interview",
        "time tracking":   "Time Tracking",
        "timetracking":    "Time Tracking",
        "time-tracking":   "Time Tracking",
        "job title":       "Job Title",
        "jobtitle":        "Job Title",
        "manager estimate":"Manager Estimate",
        "estimate":        "Manager Estimate",
    }
    return mapping.get(str(val).lower().strip(), val)


def _normalize_status(val: str) -> str:
    """Map status strings to exact allowed values."""
    mapping = {
        "ongoing":    "Ongoing",
        "in progress":"Ongoing",
        "active":     "Ongoing",
        "completed":  "Completed",
        "done":       "Completed",
        "finished":   "Completed",
        "suspended":  "Suspended",
        "cancelled":  "Suspended",
        "canceled":   "Suspended",
        "paused":     "Suspended",
    }
    return mapping.get(str(val).lower().strip(), "Ongoing")


def _ensure_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        return [val]
    return []


def _require(d: dict, keys: list[str]) -> None:
    missing = [k for k in keys if k not in d or d[k] is None]
    if missing:
        raise ValueError(
            f"build_answers_json: missing required fields: {missing}"
        )

"""
Per-Project PDF Builder
=======================
Generates one standalone PDF per R&D project, spanning all years that project
was active. Each report contains the full blueprint-compliant 10 sections,
filtered to only the data relevant to that project.

Usage (called from run_pipeline.py after the main pipeline):
    from src.render.project_report_builder import generate_all_project_reports
    generate_all_project_reports(
        multi_year_study_data=context["multi_year_study_data"],
        multi_year_qre_results=context["multi_year_qre_results"],
        context=context,
        output_dir=output_dir / "per_project",
        logo_path=logo_path,
    )
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.render.canvas import NumberedCanvas
from src.render.comprehensive_sections import (
    _LINK_LABELS,
    _format_money,
    _format_pct,
    _markdown_to_elements,
    create_asc_worksheet,
    create_assumptions_section,
    create_company_background,
    create_cost_methodology,
    create_documentation_index,
    create_audit_compliance_section,
    create_research_methodology_section,
)

styles = getSampleStyleSheet()
title_style = styles["Title"]
h1_style = styles["Heading1"]
h2_style = styles["Heading2"]
h3_style = styles["Heading3"]
normal_style = styles["BodyText"]
note_style = ParagraphStyle(
    "NoteStyle", parent=styles["BodyText"], fontSize=8, textColor=colors.grey
)

# ── Reusable cell styles for table cells that need word-wrapping ─────────────
_cell7 = ParagraphStyle(
    "Cell7", parent=styles["BodyText"], fontSize=7, leading=9, spaceAfter=0, spaceBefore=0
)
_cell7r = ParagraphStyle(
    "Cell7R", parent=_cell7, alignment=2  # right-aligned numbers
)
_cell8 = ParagraphStyle(
    "Cell8", parent=styles["BodyText"], fontSize=8, leading=10, spaceAfter=0, spaceBefore=0
)
_cell8b = ParagraphStyle(
    "Cell8B", parent=_cell8, fontName="Helvetica-Bold"
)
_cell9 = ParagraphStyle(
    "Cell9", parent=styles["BodyText"], fontSize=9, leading=11, spaceAfter=0, spaceBefore=0
)
_cell9b = ParagraphStyle(
    "Cell9B", parent=_cell9, fontName="Helvetica-Bold"
)
_cell_hdr = ParagraphStyle(
    "CellHdr", parent=styles["BodyText"], fontSize=8, leading=10,
    fontName="Helvetica-Bold", textColor=colors.whitesmoke,
    spaceAfter=0, spaceBefore=0
)


def _safe(text: str) -> str:
    """Escape & for ReportLab's XML parser."""
    return str(text).replace("&", "&amp;")


def _p(text: str, style=None) -> Paragraph:
    """Wrap text in a Paragraph, escaping & so ReportLab's XML parser doesn't choke."""
    if style is None:
        style = _cell8
    return Paragraph(_safe(text), style)


def _rd(text: str, style=None) -> str:
    """Return text with & properly escaped for use in Paragraph — keeps R&D clean."""
    return str(text).replace("&", "&amp;")


# ---------------------------------------------------------------------------
# Helpers — project filtering
# ---------------------------------------------------------------------------

def _get_all_project_ids(multi_year_study_data: list) -> list:
    """Return sorted list of unique project_ids across all years."""
    ids: set = set()
    for yr_data in multi_year_study_data:
        for p in yr_data.get("rd_projects", []):
            pid = p.get("project_id")
            if pid:
                ids.add(pid)
    return sorted(ids)


def _collect_project_years(project_id: str, multi_year_study_data: list) -> list:
    """Return [(year_label, yr_data, project_dict)] for every year project_id is active."""
    active = []
    for yr_data in multi_year_study_data:
        yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        match = next(
            (p for p in yr_data.get("rd_projects", []) if p.get("project_id") == project_id),
            None,
        )
        if match:
            active.append((yr_label, yr_data, match))
    return active


def _filter_employees_for_project(employees: list, project_id: str) -> list:
    """Keep employees allocated to project_id; trim their allocation list to just that project."""
    result = []
    for emp in employees:
        allocs = [a for a in emp.get("project_allocation", []) if a.get("project_id") == project_id]
        if allocs:
            emp_copy = dict(emp)
            emp_copy["project_allocation"] = allocs
            result.append(emp_copy)
    return result


def _filter_by_project(items: list, project_id: str) -> list:
    """
    Filter contractors / supplies / cloud to those allocated to project_id.

    Supports two JSON layouts:
      1. Top-level  project_id field  (simple case)
      2. project_allocation list      (NovaPulse-style JSON)
    """
    result = []
    for item in items:
        # Layout 1 — direct project_id field
        if item.get("project_id") == project_id:
            result.append(item)
            continue
        # Layout 2 — project_allocation list
        for alloc in item.get("project_allocation", []):
            if alloc.get("project_id") == project_id:
                result.append(item)
                break
    return result


def _get_project_name(proj_dict: dict) -> str:
    """
    Return the human-readable project name from a project dict.
    Priority: project_name → project_title → objective → project_id
    """
    return (
        proj_dict.get("project_name")
        or proj_dict.get("project_title")
        or (proj_dict.get("technical_summary") or {}).get("objective", "")
        or proj_dict.get("project_id", "Unknown Project")
    )


def _compute_project_qre(project_id: str, yr_data: dict) -> float:
    """Sum QRE components attributable to project_id for a single year."""
    total = 0.0
    for emp in yr_data.get("employees", []):
        wages = float(str(emp.get("w2_box_1_wages", 0) or 0))
        qual_pct = float(str(emp.get("qualified_percentage", 0) or 0))
        for alloc in emp.get("project_allocation", []):
            if alloc.get("project_id") == project_id:
                pct = float(str(alloc.get("percent_of_employee_time", 0) or 0))
                total += wages * qual_pct * pct
    for con in _filter_by_project(yr_data.get("contractors", []), project_id):
        # Supports both contract_amount (schema) and total_amount_paid (NovaPulse JSON)
        amt = float(str(con.get("contract_amount") or con.get("total_amount_paid", 0) or 0))
        rate = float(str(con.get("qualified_percentage", 0) or 0))
        total += amt * rate * 0.65
    for sup in _filter_by_project(yr_data.get("supplies", []), project_id):
        amt = float(str(sup.get("amount", 0) or 0))
        rate = float(str(sup.get("qualified_percentage", 0) or 0))
        total += amt * rate
    for cld in _filter_by_project(yr_data.get("cloud_services", []), project_id):
        amt = float(str(cld.get("amount", 0) or 0))
        rate = float(str(cld.get("qualified_percentage", 0) or 0))
        total += amt * rate
    return total


# ---------------------------------------------------------------------------
# Section renderers — per-project variants
# ---------------------------------------------------------------------------

def _create_project_title_page(
    project_id: str, project_name: str, client_name: str, years: list
) -> list:
    year_range = f"{years[0]}–{years[-1]}" if len(years) > 1 else years[0]
    elements = [
        Spacer(1, 2 * inch),
        Paragraph("R&amp;D Tax Credit Study", title_style),
        Spacer(1, 0.3 * inch),
        Paragraph(f"Project: {_safe(project_name)}", h2_style),
        Paragraph(f"Project ID: {_safe(project_id)}", h2_style),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Prepared for: {_safe(client_name)}", h2_style),
        Paragraph(f"Tax Year(s): {year_range}", h2_style),
        PageBreak(),
    ]
    return elements


def _create_project_executive_summary(
    project_id: str,
    project_name: str,
    client_name: str,
    active_years: list,
    per_year_qre: dict,
    per_year_credit: dict,
) -> list:
    elements = [Paragraph("1. Executive Summary", h1_style)]

    latest_proj = active_years[-1][2]
    ts = latest_proj.get("technical_summary") or {}

    # Opening scope paragraph
    scope = (
        f"This report documents the Qualified Research Expenditures (QREs) and qualified "
        f"research activities for project {project_id}: {project_name}, conducted by {client_name}."
    )
    elements.append(Paragraph(scope, normal_style))
    elements.append(Spacer(1, 0.1 * inch))

    # Business component
    biz_component = latest_proj.get("business_component", "")
    if biz_component:
        elements.append(Paragraph(
            f"<b>Business Component:</b> {biz_component}", normal_style
        ))
        elements.append(Spacer(1, 0.08 * inch))

    # Problem Statement
    problem = ts.get("problem_statement", "")
    if problem:
        elements.append(Paragraph(f"<b>Problem Statement:</b> {problem}", normal_style))
        elements.append(Spacer(1, 0.08 * inch))

    # Technical uncertainty
    tech_unc = ts.get("technical_uncertainty", "")
    if tech_unc:
        elements.append(Paragraph(
            f"<b>Key Technical Uncertainty:</b> {tech_unc}", normal_style
        ))
        elements.append(Spacer(1, 0.08 * inch))

    # Results / outcome (latest year)
    result = ts.get("results_or_outcome", "")
    if result:
        elements.append(Paragraph(f"<b>Outcome:</b> {result}", normal_style))
        elements.append(Spacer(1, 0.08 * inch))

    elements.append(Spacer(1, 0.1 * inch))

    # Summary table — use Paragraph cells so long project names wrap instead of overflow
    years_str = ", ".join(y for y, _, _ in active_years)
    total_proj_qre = sum(per_year_qre.values())
    total_proj_credit = sum(per_year_credit.values())

    def _ms(label):   # metric label cell (bold)
        return _p(label, _cell9b)
    def _vs(value):   # value cell (normal)
        return _p(str(value), _cell9)

    data = [
        [_p("Metric", _cell_hdr), _p("Value", _cell_hdr)],
        [_ms("Project"),                      _vs(f"{project_id}: {project_name}")],
        [_ms("Company"),                      _vs(client_name)],
        [_ms("Active Tax Year(s)"),           _vs(years_str)],
        [_ms("Total Project QREs (all active years)"),         _vs(_format_money(total_proj_qre))],
        [_ms("Proportional Credit Attribution (all years)"),   _vs(_format_money(total_proj_credit))],
        [_ms("Credit Method"),                _vs("ASC (Alternative Simplified Credit) \u2014 company-level")],
    ]
    # col 0 = metric label (2.5in), col 1 = value (4.0in) — more space for long project names
    t = Table(data, colWidths=[2.5 * inch, 4.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(t)
    elements.append(PageBreak())
    return elements


def _create_project_narratives(active_years: list) -> list:
    """§3 Project Narratives — all 7 technical subsections for each year this project was active."""
    elements = [Paragraph("3. Project Research Activities", h1_style)]

    for year_label, yr_data, proj in active_years:
        project_id = proj.get("project_id", "")
        project_name = _get_project_name(proj)
        elements.append(Paragraph(f"Tax Year {_safe(year_label)} — {_safe(project_id)}: {_safe(project_name)}", h2_style))

        ts = proj.get("technical_summary") or {}

        # Prefer LLM-generated narratives if available (full pipeline path).
        # gen_narratives is keyed by section name: project_description, new_improved_component,
        # elimination_uncertainty, process_experimentation, technological_nature, resolution.
        gen_narratives = proj.get("generated_narratives") or {}

        # ── Project classification & metadata ─────────────────────────────
        meta_lines = []
        if proj.get("business_component_classification"):
            meta_lines.append(f"<b>BC Classification:</b> {_safe(proj['business_component_classification'])}")
        if proj.get("cross_year_business_component_id"):
            meta_lines.append(f"<b>Multi-Year BC ID:</b> {_safe(proj['cross_year_business_component_id'])}")
        if proj.get("uncertainty_resolution_date"):
            meta_lines.append(f"<b>Uncertainty Resolved:</b> {_safe(str(proj['uncertainty_resolution_date']))}")
        sw_flag = proj.get("is_commercial_sale_software")
        if sw_flag is not None:
            meta_lines.append(f"<b>Commercial-Sale Software:</b> {'Yes' if sw_flag else 'No'}")
            if sw_flag and proj.get("internal_use_software_exemption_note"):
                meta_lines.append(f"<b>IUS Exemption:</b> {_safe(proj['internal_use_software_exemption_note'])}")
        irc_refs = proj.get("irc_section_references") or []
        if irc_refs:
            meta_lines.append(f"<b>IRC References:</b> {_safe(', '.join(irc_refs))}")
        for ml in meta_lines:
            elements.append(Paragraph(ml, normal_style))
        if meta_lines:
            elements.append(Spacer(1, 0.1 * inch))

        if gen_narratives:
            # Render each section from LLM-generated text
            section_map = [
                ("ii) Project Description",                "project_description"),
                ("iii) New or Improved Business Component","new_improved_component"),
                ("iv) Elimination of Uncertainty",         "elimination_uncertainty"),
                ("v) Process of Experimentation",          "process_experimentation"),
                ("vi) Technological in Nature",            "technological_nature"),
                ("vii) Resolution",                        "resolution"),
            ]
            for heading, key in section_map:
                text = gen_narratives.get(key, "")
                if text:
                    elements.append(Paragraph(f"<b>{heading}</b>", h3_style))
                    elements.extend(_markdown_to_elements(text, skip_first_heading=True))
                    elements.append(Spacer(1, 0.1 * inch))
        else:
            # Fallback: render raw JSON fields when LLM narratives are not available
            obj = ts.get("objective", "")
            if obj:
                elements.append(Paragraph("<b>i. Objective</b>", h3_style))
                elements.append(Paragraph(_safe(obj), normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            problem = ts.get("problem_statement", "")
            if problem:
                elements.append(Paragraph("<b>ii. Problem Statement</b>", h3_style))
                elements.append(Paragraph(_safe(problem), normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            tech_unc = ts.get("technical_uncertainty", "")
            if tech_unc:
                elements.append(Paragraph("<b>iii. Technical Uncertainty</b>", h3_style))
                elements.append(Paragraph(_safe(tech_unc), normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            hypotheses = ts.get("hypotheses_tested") or []
            if hypotheses:
                elements.append(Paragraph("<b>iv. Hypotheses Tested</b>", h3_style))
                for h in hypotheses:
                    elements.append(Paragraph(f"\u2022 {_safe(h)}", normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            exp_steps = ts.get("experimentation_process") or []
            if exp_steps:
                elements.append(Paragraph("<b>v. Process of Experimentation</b>", h3_style))
                for step in exp_steps:
                    elements.append(Paragraph(f"\u2022 {_safe(step)}", normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            alternatives = ts.get("alternatives_considered") or []
            if alternatives:
                elements.append(Paragraph("<b>vi. Alternatives Considered</b>", h3_style))
                for alt in alternatives:
                    elements.append(Paragraph(f"\u2022 {_safe(alt)}", normal_style))
                elements.append(Spacer(1, 0.1 * inch))

            results = ts.get("results_or_outcome", "")
            if results:
                elements.append(Paragraph("<b>vii. Results and Outcome</b>", h3_style))
                elements.append(Paragraph(_safe(results), normal_style))
                elements.append(Spacer(1, 0.08 * inch))

            failures = ts.get("failures_or_iterations", "")
            if failures:
                elements.append(Paragraph("<b>Failures and Iterations</b>", h3_style))
                elements.append(Paragraph(_safe(failures), normal_style))
                elements.append(Spacer(1, 0.08 * inch))

        # ── Prior Art & Excluded Activities ──────────────────────────────
        if proj.get("prior_art_search_summary"):
            elements.append(Paragraph("<b>viii) Prior Art &amp; Literature Review</b>", h3_style))
            elements.append(Paragraph(_safe(proj["prior_art_search_summary"]), normal_style))
            elements.append(Spacer(1, 0.08 * inch))
        if proj.get("excluded_activities_within_project"):
            elements.append(Paragraph("<b>ix) Excluded Activities within This Project</b>", h3_style))
            elements.append(Paragraph(_safe(proj["excluded_activities_within_project"]), normal_style))
            elements.append(Spacer(1, 0.08 * inch))

        # ── Cross-Year Note ───────────────────────────────────────────────
        if proj.get("cross_year_note"):
            from reportlab.lib.styles import ParagraphStyle as _PS
            cy_style = _PS("CYNote_pb", parent=normal_style,
                           textColor=colors.HexColor("#154360"),
                           backColor=colors.HexColor("#D6EAF8"), borderPad=4)
            elements.append(Paragraph(
                f"<b>Multi-Year BC Note:</b> {_safe(proj['cross_year_note'])}", cy_style))
            elements.append(Spacer(1, 0.1 * inch))

        # ── Project QRE Attribution ───────────────────────────────────────
        proj_qre = proj.get("project_qre_summary") or proj.get("qre_summary") or {}
        credit_attr = proj.get("credit_attribution") or {}
        if proj_qre or credit_attr:
            elements.append(Paragraph("<b>Project QRE &amp; Credit Attribution</b>", h3_style))
            attr_rows = [["Category", "Amount"]]
            if proj_qre.get("wage_qre") is not None:
                attr_rows.append(["Qualified Wages QRE", _format_money(proj_qre["wage_qre"])])
            if proj_qre.get("contractor_qre_after_65pct") is not None:
                attr_rows.append(["Qualified Contractor QRE (65%)", _format_money(proj_qre["contractor_qre_after_65pct"])])
            if proj_qre.get("supply_qre") is not None:
                attr_rows.append(["Qualified Supply QRE", _format_money(proj_qre["supply_qre"])])
            if proj_qre.get("cloud_qre") is not None:
                attr_rows.append(["Qualified Cloud QRE", _format_money(proj_qre["cloud_qre"])])
            total_proj = proj_qre.get("total_project_qre") or proj_qre.get("total_qre") or 0
            if total_proj:
                attr_rows.append(["Total Project QRE", _format_money(total_proj)])
            if credit_attr.get("attribution_pct") is not None:
                attr_rows.append(["Attribution % of Year QRE", f"{float(credit_attr['attribution_pct']):.2f}%"])
            if credit_attr.get("proportional_credit") is not None:
                attr_rows.append(["Proportional R&amp;D Credit", _format_money(credit_attr["proportional_credit"])])
            if len(attr_rows) > 1:
                from reportlab.platypus import Table as _T, TableStyle as _TS
                at = _T(attr_rows, colWidths=[3.0*inch, 1.8*inch])
                at.setStyle(_TS([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
                ]))
                elements.append(at)
                elements.append(Spacer(1, 0.1 * inch))

        elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements


def _create_project_qra_section(active_years: list) -> list:
    """§3 Qualified Research Activities — one summary table per year this project was active.

    Blueprint requirement: a numbered list of qualifying projects with project name,
    objective, status, and brief description of what was being developed (§3 template,
    Table 84 in agent3_blueprint.docx).
    For a per-project PDF the 'list' is always one entry — this project — but the
    section is required to satisfy the blueprint structure.
    """
    elements = [
        Paragraph("3. Qualified Research Activities", h1_style),
        Paragraph(
            "The following table identifies the qualified research activities (QRAs) performed "
            "under IRC \u00a741(d) for each tax year covered by this report. Only activities "
            "that meet all four parts of the IRS qualification test are included.",
            normal_style,
        ),
        Spacer(1, 0.15 * inch),
    ]

    _STATUS_COLOUR = {
        "ongoing":   "#1E8449",
        "completed": "#1A5276",
        "abandoned": "#784212",
        "pivoted":   "#6C3483",
    }

    for year_label, yr_data, proj in active_years:
        project_id   = proj.get("project_id", "")
        project_name = _get_project_name(proj)
        ts           = proj.get("technical_summary") or {}
        status_raw   = str(proj.get("status") or "Ongoing")
        status_key   = status_raw.lower()

        # Status badge
        badge_colour = _STATUS_COLOUR.get(status_key, "#2C3E50")
        status_style = ParagraphStyle(
            f"StatusBadge_{year_label}",
            parent=styles["BodyText"],
            fontSize=7, leading=9, alignment=1,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            backColor=colors.HexColor(badge_colour),
        )
        status_para = Paragraph(status_raw, status_style)

        # Derive start/end date display
        start = proj.get("start_date") or "—"
        end   = proj.get("end_date") or "Ongoing"

        objective   = ts.get("objective")   or proj.get("business_component") or "—"
        description = proj.get("business_component") or ts.get("objective") or "—"
        discipline  = (
            ts.get("hypotheses_tested") and
            (ts["hypotheses_tested"][0] if isinstance(ts["hypotheses_tested"], list) else ts["hypotheses_tested"])
        ) or "Engineering / Computer Science / Physical Sciences"

        data = [
            [_p("Field", _cell_hdr), _p("Detail", _cell_hdr)],
            [_p("Tax Year",         _cell8b), _p(str(year_label),                  _cell8)],
            [_p("Project ID",       _cell8b), _p(project_id,                       _cell8)],
            [_p("Project Name",     _cell8b), _p(project_name,                     _cell8)],
            [_p("Business Component", _cell8b), _p(description,                    _cell8)],
            [_p("Technical Objective", _cell8b), _p(objective,                     _cell8)],
            [_p("Scientific Discipline", _cell8b), _p(str(discipline)[:200],       _cell8)],
            [_p("Project Period",   _cell8b), _p(f"{start} \u2013 {end}",          _cell8)],
            [_p("Status",           _cell8b), status_para],
        ]

        # Field(1.6) + Detail(4.9) = 6.5in
        t = Table(data, colWidths=[1.6 * inch, 4.9 * inch], repeatRows=1)
        t.setStyle(TableStyle([
            ("GRID",           (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("ALIGN",          (1, -1),(1, -1),  "CENTER"),   # Status cell centred
            ("VALIGN",         (1, -1),(1, -1),  "MIDDLE"),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
            ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ]))

        elements.append(Paragraph(f"Tax Year {_safe(year_label)}", h2_style))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements


def _create_project_four_part_test(active_years: list) -> list:
    """§4 Four-Part Test — per year this project was active.

    Four columns: Criterion | Justification | Result (PASS/FAIL badge) | Source
    Matches the blueprint §5 requirement for explicit PASS/FAIL status per criterion.
    """
    _PASS_STYLE = ParagraphStyle(
        "FPTPass", parent=styles["BodyText"],
        fontSize=7, leading=9, alignment=1,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        backColor=colors.HexColor("#1E8449"),
    )
    _FAIL_STYLE = ParagraphStyle(
        "FPTFail", parent=styles["BodyText"],
        fontSize=7, leading=9, alignment=1,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        backColor=colors.HexColor("#C0392B"),
    )

    # criterion key → (display label, evidence keys to cite)
    _CRITERIA = [
        ("permitted_purpose",         "Test 1 — Permitted Purpose",         ["design_docs", "github_links"]),
        ("technological_in_nature",   "Test 2 — Technological in Nature",   ["test_reports", "github_links"]),
        ("elimination_of_uncertainty","Test 3 — Elimination of Uncertainty", ["test_reports", "design_docs"]),
        ("process_of_experimentation","Test 4 — Process of Experimentation", ["test_reports", "deployment_logs"]),
    ]

    elements = [Paragraph("4. Four-Part Test Analysis", h1_style)]

    for year_label, yr_data, proj in active_years:
        project_id = proj.get("project_id", "")
        project_name = _get_project_name(proj)
        elements.append(
            Paragraph(f"Tax Year {_safe(year_label)} \u2014 {_safe(project_id)}: {_safe(project_name)}", h2_style)
        )

        fpt = proj.get("four_part_test") or {}
        ts  = proj.get("technical_summary") or {}
        ev  = proj.get("evidence_links") or {}

        # Fallback justifications when fpt field is empty
        _FALLBACKS = {
            "permitted_purpose":          "Research intended to develop or improve a business component under IRC §41(d)(1).",
            "technological_in_nature":    "Activities rely on principles of engineering, computer science, or physical sciences.",
            "elimination_of_uncertainty": ts.get("technical_uncertainty") or "Genuine technical uncertainty existed at project start.",
            "process_of_experimentation": "Systematic evaluation of alternatives through structured testing and iteration.",
        }

        def _ev_para(keys):
            docs = []
            for k in keys:
                for url in ev.get(k, []):
                    label = _LINK_LABELS.get(k, k)
                    name  = url.split("/")[-1] if "/" in url else url
                    docs.append(f"{label}: {name}")
            return _p("<br/>".join(docs) if docs else "\u2014", _cell7)

        data = [
            [
                _p("Criterion",     _cell_hdr),
                _p("Justification", _cell_hdr),
                _p("Result",        _cell_hdr),
                _p("Source",        _cell_hdr),
            ]
        ]
        for field, label, ev_keys in _CRITERIA:
            justification = fpt.get(field) or _FALLBACKS.get(field, "")
            passed        = bool(justification and justification.strip())
            result_para   = Paragraph("PASS" if passed else "FAIL",
                                      _PASS_STYLE if passed else _FAIL_STYLE)
            data.append([
                _p(f"<b>{label}</b>", _cell7),
                _p(justification, _cell7),
                result_para,
                _ev_para(ev_keys),
            ])

        # Criterion(1.5) + Justification(2.85) + Result(0.55) + Source(1.6) = 6.5in
        t = Table(data, colWidths=[1.5 * inch, 2.85 * inch, 0.55 * inch, 1.6 * inch],
                  repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
                    ("FONTSIZE",    (0, 0), (-1, -1), 7),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#F4F6F7")]),
                    ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                    ("ALIGN",       (2, 1), (2, -1),  "CENTER"),   # Result col centred
                    ("VALIGN",      (2, 1), (2, -1),  "MIDDLE"),   # Result badge vertically centred
                    ("TOPPADDING",  (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING",(0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 0.25 * inch))

    elements.append(PageBreak())
    return elements


def _create_project_employee_schedule(project_id: str, active_years: list) -> list:
    """§6A Employee Wage Schedule filtered to this project, with activity descriptions."""
    elements = [
        Paragraph("6A. Employee Wage Schedule", h1_style),
        Paragraph("Only employees with time allocated to this project are shown.", normal_style),
        Spacer(1, 0.1 * inch),
    ]

    for year_label, yr_data, proj in active_years:
        employees = _filter_employees_for_project(yr_data.get("employees", []), project_id)
        if not employees:
            elements.append(
                Paragraph(
                    f"Tax Year {year_label}: No employees allocated to this project.",
                    normal_style,
                )
            )
            elements.append(Spacer(1, 0.1 * inch))
            continue

        elements.append(Paragraph(f"Tax Year {_safe(year_label)}", h2_style))

        # Header row uses _cell_hdr (bold white), data rows use _cell7 Paragraphs so
        # long job titles wrap within their cell instead of bleeding into W-2 Wages column.
        data = [
            [_p("Employee", _cell_hdr), _p("Title", _cell_hdr), _p("W-2 Wages", _cell_hdr),
             _p("Qual %", _cell_hdr), _p("Proj %", _cell_hdr),
             _p("Qualified Wages", _cell_hdr), _p("Activity", _cell_hdr)]
        ]
        total_qw = 0.0
        for emp in employees:
            wages = float(str(emp.get("w2_box_1_wages", 0) or 0))
            qual_pct = float(str(emp.get("qualified_percentage", 0) or 0))
            activity = (emp.get("activity_type") or "direct_research").replace("_", " ").title()
            for alloc in emp.get("project_allocation", []):
                if alloc.get("project_id") != project_id:
                    continue
                proj_pct = float(str(alloc.get("percent_of_employee_time", 0) or 0))
                qw = wages * qual_pct * proj_pct
                total_qw += qw
                data.append(
                    [
                        _p(emp.get("employee_name", ""), _cell7),
                        _p(emp.get("job_title", ""), _cell7),
                        _p(_format_money(wages), _cell7r),
                        _p(_format_pct(qual_pct), _cell7r),
                        _p(_format_pct(proj_pct), _cell7r),
                        _p(_format_money(qw), _cell7r),
                        _p(activity, _cell7),
                    ]
                )
        data.append([_p("TOTAL", _cell8b), _p("", _cell7), _p("", _cell7),
                     _p("", _cell7), _p("", _cell7),
                     _p(_format_money(total_qw), _cell8b), _p("", _cell7)])

        # Employee(1.35) + Title(1.7) + W2(0.85) + Qual%(0.5) + Proj%(0.5) + QW(0.85) + Act(0.75) = 6.5in
        t = Table(
            data,
            colWidths=[1.35*inch, 1.7*inch, 0.85*inch, 0.5*inch, 0.5*inch, 0.85*inch, 0.75*inch],
            repeatRows=1,
        )
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ECF0F1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 0.15 * inch))

        # Activity descriptions (fallback to rd_activities_description if no LLM narrative)
        has_desc = any(
            emp.get("generated_activity_narrative") or emp.get("rd_activities_description")
            for emp in employees
        )
        if has_desc:
            elements.append(Paragraph("Employee Activity Descriptions", h3_style))
            for emp in employees:
                narrative = (
                    emp.get("generated_activity_narrative")
                    or emp.get("rd_activities_description")
                    or ""
                )
                if narrative:
                    elements.append(
                        Paragraph(
                            f"<b>{_safe(emp.get('employee_name', ''))} \u2014 {_safe(emp.get('job_title', ''))}</b>",
                            normal_style,
                        )
                    )
                    elements.append(Paragraph(_safe(narrative), normal_style))
                    elements.append(Spacer(1, 0.1 * inch))
            elements.append(Spacer(1, 0.1 * inch))

    elements.append(PageBreak())
    return elements


def _create_project_contractor_schedule(project_id: str, active_years: list) -> list:
    """§6B Contractor Schedule filtered to this project."""
    elements = [Paragraph("6B. Contractor Schedule", h1_style)]
    any_data = False

    for year_label, yr_data, proj in active_years:
        contractors = _filter_by_project(yr_data.get("contractors", []), project_id)
        if not contractors:
            continue
        any_data = True
        elements.append(Paragraph(f"Tax Year {_safe(year_label)}", h2_style))

        data = [
            [_p("Contractor", _cell_hdr), _p("Description of Work", _cell_hdr),
             _p("Amt Paid", _cell_hdr), _p("Qual %", _cell_hdr),
             _p("65%", _cell_hdr), _p("QRE", _cell_hdr)]
        ]
        total_qre = 0.0
        for con in contractors:
            name = con.get("contractor_name") or con.get("vendor_name", "")
            amt = float(str(con.get("contract_amount") or con.get("total_amount_paid", 0) or 0))
            rate = float(str(con.get("qualified_percentage", 0) or 0))
            desc = con.get("description_of_work") or con.get("contractor_type", "")
            qre = amt * rate * 0.65
            total_qre += qre
            data.append([
                _p(name, _cell7),
                _p(desc, _cell7),
                _p(_format_money(amt), _cell7r),
                _p(_format_pct(rate), _cell7r),
                _p("65%", _cell7r),
                _p(_format_money(qre), _cell7r),
            ])
        data.append([_p("TOTAL", _cell8b), _p("", _cell7), _p("", _cell7),
                     _p("", _cell7), _p("", _cell7), _p(_format_money(total_qre), _cell8b)])

        # Name(1.3) + Desc(2.45) + Amt(0.75) + Qual%(0.5) + 65%(0.45) + QRE(0.75) = 6.2in (+ padding)
        t = Table(data, colWidths=[1.3*inch, 2.45*inch, 0.75*inch, 0.5*inch, 0.45*inch, 0.75*inch],
                  repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ECF0F1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

    if not any_data:
        elements.append(Paragraph("No contractors assigned to this project.", normal_style))

    elements.append(PageBreak())
    return elements


def _create_project_supplies_schedule(project_id: str, active_years: list) -> list:
    """§6C Supplies Schedule filtered to this project."""
    elements = [Paragraph("6C. Supplies Schedule", h1_style)]
    any_data = False

    for year_label, yr_data, proj in active_years:
        supplies = _filter_by_project(yr_data.get("supplies", []), project_id)
        if not supplies:
            continue
        any_data = True
        elements.append(Paragraph(f"Tax Year {_safe(year_label)}", h2_style))

        data = [
            [_p("Description", _cell_hdr), _p("Vendor", _cell_hdr),
             _p("Amount", _cell_hdr), _p("Qual %", _cell_hdr), _p("QRE", _cell_hdr)]
        ]
        total_qre = 0.0
        for sup in supplies:
            amt = float(str(sup.get("amount", 0) or 0))
            rate = float(str(sup.get("qualified_percentage", 0) or 0))
            qre = amt * rate
            total_qre += qre
            data.append([
                _p(sup.get("description", "") or sup.get("supply_type", ""), _cell7),
                _p(sup.get("vendor", ""), _cell7),
                _p(_format_money(amt), _cell7r),
                _p(_format_pct(rate), _cell7r),
                _p(_format_money(qre), _cell7r),
            ])
        data.append([_p("TOTAL", _cell8b), _p("", _cell7), _p("", _cell7),
                     _p("", _cell7), _p(_format_money(total_qre), _cell8b)])

        # Desc(2.9) + Vendor(1.5) + Amt(0.85) + Qual%(0.5) + QRE(0.75) = 6.5in
        t = Table(data, colWidths=[2.9*inch, 1.5*inch, 0.85*inch, 0.5*inch, 0.75*inch],
                  repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ECF0F1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

    if not any_data:
        elements.append(Paragraph("No supplies assigned to this project.", normal_style))

    elements.append(PageBreak())
    return elements


def _create_project_credit_attribution(
    project_id: str,
    project_name: str,
    active_years: list,
    per_year_qre: dict,
    per_year_company_qre: dict,
    per_year_credit: dict,
    multi_year_qre_results: list,
) -> list:
    """§10 Credit Calculation & Attribution.

    Renders two sub-sections per active year:
      10A. Full ASC Computation Worksheet (Form 6765) — company-level figures
      10B. This project's proportional share of the company-level credit
    """
    elements = [
        Paragraph("10. Credit Calculation &amp; Attribution", h1_style),
        Paragraph(
            "The Alternative Simplified Credit (ASC) under IRC §41 is computed at the company "
            "level on Form 6765. Section 10A shows the full company-level ASC worksheet for each "
            "tax year this project was active. Section 10B shows this project's proportional "
            "attribution based on its share of total company QREs — for internal allocation "
            "purposes only.",
            normal_style,
        ),
        Spacer(1, 0.2 * inch),
    ]

    # ── 10A. ASC Computation Worksheet per active year ──────────────────────
    for year_label, yr_data, proj in active_years:
        # Find the matching QRE result for this year
        yr_qre_result = next(
            (r for r in multi_year_qre_results if r.get("year_label") == year_label), None
        )
        if not yr_qre_result:
            continue

        elements.append(
            Paragraph(f"10A. ASC Computation Worksheet — Tax Year {_safe(year_label)}", h2_style)
        )

        # Build a context dict that create_asc_worksheet() expects.
        # business_flags lives at the top level of yr_data (yr_data["business_flags"]).
        bf = yr_data.get("business_flags") or {}

        asc_context = {
            "asc_computation": yr_qre_result.get("asc_computation", {}),
            "study_data": {
                "business_flags": bf,
                "qre_summary": yr_qre_result.get("qre_summary", {}),
            },
        }
        # create_asc_worksheet() prepends its own "7. ASC..." h1 heading and appends a PageBreak.
        # Strip both so our "10A." heading is the only one and we control page flow.
        worksheet_elements = create_asc_worksheet(asc_context)
        # Drop leading Paragraph headings that say "7. ASC Computation Worksheet..."
        while worksheet_elements and isinstance(worksheet_elements[0], Paragraph) and \
                "ASC Computation Worksheet" in worksheet_elements[0].text:
            worksheet_elements.pop(0)
        # Drop trailing PageBreak
        while worksheet_elements and isinstance(worksheet_elements[-1], PageBreak):
            worksheet_elements.pop()
        elements.extend(worksheet_elements)
        elements.append(Spacer(1, 0.25 * inch))

    elements.append(PageBreak())

    # ── 10B. Project Proportional Attribution summary table ─────────────────
    elements.append(
        Paragraph("10B. This Project's Proportional Credit Attribution", h2_style)
    )
    elements.append(
        Paragraph(
            "The table below shows this project\u2019s proportional share of the company-level "
            "R&amp;D credit for each year it was active. These figures are for internal cost "
            "allocation only \u2014 the IRS receives one Form 6765 per entity per year.",
            normal_style,
        )
    )
    elements.append(Spacer(1, 0.15 * inch))

    data = [
        [
            "Tax Year",
            "Project QRE",
            "Company QRE",
            "Project Share",
            "Company Credit",
            "Project Attribution",
        ]
    ]

    for year_label, yr_data, proj in active_years:
        proj_qre = per_year_qre.get(year_label, 0.0)
        comp_qre = per_year_company_qre.get(year_label, 0.0)
        share = proj_qre / comp_qre if comp_qre > 0 else 0.0

        comp_credit = 0.0
        for yr_qre in multi_year_qre_results:
            if yr_qre.get("year_label") == year_label:
                asc = yr_qre.get("asc_computation") or {}
                comp_credit = float(str(asc.get("federal_credit", 0) or 0))
                break

        proj_credit = comp_credit * share
        data.append(
            [
                year_label,
                _format_money(proj_qre),
                _format_money(comp_qre),
                _format_pct(share),
                _format_money(comp_credit),
                _format_money(proj_credit),
            ]
        )

    # Totals row
    total_proj_qre = sum(per_year_qre.values())
    total_comp_qre = sum(per_year_company_qre.values())
    total_proj_credit = sum(per_year_credit.values())
    total_comp_credit = sum(
        float(str((yr.get("asc_computation") or {}).get("federal_credit", 0) or 0))
        for yr in multi_year_qre_results
        if yr.get("year_label") in per_year_qre
    )
    overall_share = total_proj_qre / total_comp_qre if total_comp_qre > 0 else 0.0

    data.append(
        [
            "TOTAL / AVG",
            _format_money(total_proj_qre),
            _format_money(total_comp_qre),
            _format_pct(overall_share),
            _format_money(total_comp_credit),
            _format_money(total_proj_credit),
        ]
    )

    t = Table(
        data,
        colWidths=[0.75*inch, 1.05*inch, 1.05*inch, 0.9*inch, 1.05*inch, 1.2*inch],
        repeatRows=1,
    )
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.whitesmoke),
            ]
        )
    )
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(
        Paragraph(
            "Important: Proportional credit figures are for internal attribution only. "
            "IRC §41 credits are filed at the entity level on Form 6765 — you cannot file "
            "separate credits per project.",
            note_style,
        )
    )
    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_single_project_pdf(
    project_id: str,
    multi_year_study_data: list,
    multi_year_qre_results: list,
    context: dict,
    output_path: Path,
    logo_path: Path = None,
) -> Path | None:
    """
    Build a per-project PDF spanning all years this project was active.

    Args:
        project_id:             The project ID to build a report for.
        multi_year_study_data:  All years' RDStudyData dicts (oldest → newest).
        multi_year_qre_results: Per-year QRE result dicts from the computation agent.
        context:                Agent context (contains generated narratives etc.).
        output_path:            Output PDF path.
        logo_path:              Optional logo image path.

    Returns:
        output_path on success, None if project not found.
    """
    active_years = _collect_project_years(project_id, multi_year_study_data)
    if not active_years:
        print(f"  [WARNING] Project {project_id} not found in any year — skipping.")
        return None

    latest_yr_data = active_years[-1][1]
    client_name = latest_yr_data["study_metadata"]["prepared_for"]["legal_name"]
    latest_proj = active_years[-1][2]
    project_name = _get_project_name(latest_proj)
    years_list = [y for y, _, _ in active_years]

    # Pre-compute per-year QRE and proportional credit
    per_year_qre: dict = {}
    per_year_company_qre: dict = {}
    per_year_credit: dict = {}

    for year_label, yr_data, proj in active_years:
        proj_qre = _compute_project_qre(project_id, yr_data)
        per_year_qre[year_label] = proj_qre

        comp_qre = 0.0
        comp_credit = 0.0
        for yr_qre in multi_year_qre_results:
            if yr_qre.get("year_label") == year_label:
                comp_qre = float(str(yr_qre.get("total_qre", 0) or 0))
                asc = yr_qre.get("asc_computation") or {}
                comp_credit = float(str(asc.get("federal_credit", 0) or 0))
                break

        per_year_company_qre[year_label] = comp_qre
        share = proj_qre / comp_qre if comp_qre > 0 else 0.0
        per_year_credit[year_label] = comp_credit * share

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=f"R&D Study — {project_id}: {project_name} — {client_name}",
    )

    story = []

    # 0. Title Page
    story.extend(_create_project_title_page(project_id, project_name, client_name, years_list))

    # 1. Executive Summary (project-scoped)
    story.extend(
        _create_project_executive_summary(
            project_id, project_name, client_name, active_years,
            per_year_qre, per_year_credit,
        )
    )

    # 2. Company Background (same company for all projects)
    story.extend(create_company_background(latest_yr_data))

    # 3. Qualified Research Activities (blueprint §3 — project identity + status per year)
    story.extend(_create_project_qra_section(active_years))

    # 4. Technical Narratives (per year, raw data fallback if no LLM narrative)
    story.extend(_create_project_narratives(active_years))

    # 5. Four-Part Test with PASS/FAIL badges (per year)
    story.extend(_create_project_four_part_test(active_years))

    # 6. Cost Methodology
    story.extend(create_cost_methodology(latest_yr_data))

    # 6A. Employee Wage Schedule (per year, filtered)
    story.extend(_create_project_employee_schedule(project_id, active_years))

    # 6B. Contractor Schedule (per year, filtered)
    story.extend(_create_project_contractor_schedule(project_id, active_years))

    # 6C. Supplies Schedule (per year, filtered)
    story.extend(_create_project_supplies_schedule(project_id, active_years))

    # 10. Credit Attribution (project proportional share)
    story.extend(
        _create_project_credit_attribution(
            project_id, project_name, active_years,
            per_year_qre, per_year_company_qre, per_year_credit,
            multi_year_qre_results,
        )
    )

    # 11. Documentation Index (project-specific docs only)
    proj_doc_data = dict(latest_yr_data)
    proj_doc_data["additional_documentation"] = []
    proj_doc_data["employees"] = []
    proj_doc_data["contractors"] = []
    proj_doc_data["supplies"] = []
    proj_doc_data["rd_projects"] = [p for _, _, p in active_years]
    for _, yr_data, _ in active_years:
        proj_doc_data["employees"] += _filter_employees_for_project(
            yr_data.get("employees", []), project_id
        )
        proj_doc_data["contractors"] += _filter_by_project(
            yr_data.get("contractors", []), project_id
        )
        proj_doc_data["supplies"] += _filter_by_project(
            yr_data.get("supplies", []), project_id
        )
        proj_doc_data["additional_documentation"] += yr_data.get("additional_documentation", [])
    story.extend(create_documentation_index(proj_doc_data))

    # 9. Assumptions & Disclosures
    story.extend(create_assumptions_section(latest_yr_data))

    # 12. Audit Compliance Overview (enriched JSON fields — rendered per active year)
    for year_label, yr_data, _ in active_years:
        elems = create_audit_compliance_section(yr_data)
        if elems:
            story.append(Paragraph(f"Tax Year {year_label} — Audit Compliance Overview", h1_style))
            story.extend(elems)

    # 13. Research Methodology & Compliance Analysis (enriched JSON fields — latest year)
    rm_elems = create_research_methodology_section(latest_yr_data)
    if rm_elems:
        story.extend(rm_elems)

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, logo_path=logo_path, **kwargs),
    )
    return output_path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_all_project_reports(
    multi_year_study_data: list,
    multi_year_qre_results: list,
    context: dict,
    output_dir: Path,
    logo_path: Path = None,
) -> list:
    """
    Build one PDF per project.  Each PDF covers all years the project was active.

    Args:
        multi_year_study_data:  All years' RDStudyData dicts.
        multi_year_qre_results: Per-year QRE result dicts.
        context:                Agent context (shared across the pipeline).
        output_dir:             Directory where per-project PDFs will be saved.
        logo_path:              Optional logo image.

    Returns:
        List of string paths to generated PDF files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    project_ids = _get_all_project_ids(multi_year_study_data)
    generated: list = []

    print(f"\nGenerating {len(project_ids)} per-project reports in: {output_dir}")

    for project_id in project_ids:
        active_years = _collect_project_years(project_id, multi_year_study_data)
        if not active_years:
            continue

        latest_proj = active_years[-1][2]
        project_name = _get_project_name(latest_proj)
        # Safe filename: project_id + abbreviated project name + years
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in project_name)
        safe_name = safe_name.replace(" ", "_")[:50].strip("_")
        years_str = "_".join(y for y, _, _ in active_years)
        # Avoid redundancy when project_name starts with the project_id
        name_part = safe_name if not safe_name.upper().startswith(project_id.upper()) else safe_name[len(project_id):].strip("_")
        pdf_filename = f"{project_id}_{name_part}_{years_str}_RD_Study.pdf" if name_part else f"{project_id}_{years_str}_RD_Study.pdf"
        pdf_path = output_dir / pdf_filename

        print(f"  Building: {pdf_filename}")
        try:
            build_single_project_pdf(
                project_id=project_id,
                multi_year_study_data=multi_year_study_data,
                multi_year_qre_results=multi_year_qre_results,
                context=context,
                output_path=pdf_path,
                logo_path=logo_path,
            )
            generated.append(str(pdf_path))
            print(f"    Saved: {pdf_path}")
        except Exception as exc:
            import traceback

            print(f"    ERROR building {project_id}: {exc}")
            traceback.print_exc()

    print(f"\nPer-project reports complete: {len(generated)}/{len(project_ids)} generated.")
    return generated

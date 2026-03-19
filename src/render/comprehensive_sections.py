"""
Comprehensive Rendering Module - Generates all 10 sections of the R&D Study PDF.
"""

import re
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from decimal import Decimal

# Shared Styles
styles = getSampleStyleSheet()
title_style = styles['Title']
h1_style = styles['Heading1']
h2_style = styles['Heading2']
h3_style = styles['Heading3']
normal_style = styles['BodyText']
small_style = ParagraphStyle('Small', parent=styles['BodyText'], fontSize=9, leading=11)


# ---------------------------------------------------------------------------
# Markdown → ReportLab helpers
# ---------------------------------------------------------------------------

_LINK_LABELS = {
    "jira_links":            "Jira",
    "github_links":          "GitHub",
    "design_docs":           "Design Doc",
    "test_reports":          "Test Report",
    "deployment_logs":       "Deployment Log",
    "other_supporting_docs": "Supporting Doc",
}


def _safe(text: str) -> str:
    """Escape & so ReportLab's XML-based Paragraph parser doesn't produce spurious ;."""
    return str(text).replace("&", "&amp;")


def _strip_inline_markdown(text: str) -> str:
    """Remove **bold**, *italic*, and heading markers from a string."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text


def _markdown_to_elements(text: str, skip_first_heading: bool = True) -> list:
    """
    Convert LLM-generated markdown text into a list of ReportLab flowables.

    Handles:
    - **Heading** lines → stripped (or rendered as h3 if not first)
    - - bullet / * bullet lines → ListFlowable
    - Blank-line-separated paragraphs → Paragraph elements
    - Horizontal rules (---) → Spacer

    Args:
        text: Raw markdown string from LLM.
        skip_first_heading: If True, the first heading-only line is dropped
                            (renderer already adds the section title).
    """
    elements = []
    lines = text.split('\n')
    first_heading_seen = False
    bullet_buffer: list[str] = []

    def _flush_bullets():
        if bullet_buffer:
            items = [ListItem(Paragraph(_safe(_strip_inline_markdown(b)), normal_style))
                     for b in bullet_buffer]
            elements.append(ListFlowable(items, bulletType='bullet'))
            elements.append(Spacer(1, 0.1 * inch))
            bullet_buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Horizontal rule → small spacer
        if re.match(r'^-{3,}$', line) or re.match(r'^_{3,}$', line):
            _flush_bullets()
            elements.append(Spacer(1, 0.15 * inch))
            i += 1
            continue

        # Heading line (## or **Heading**)
        is_heading = re.match(r'^#{1,6}\s+', line) or re.match(r'^\*\*(.+?)\*\*\s*$', line)
        if is_heading:
            _flush_bullets()
            if skip_first_heading and not first_heading_seen:
                first_heading_seen = True
                i += 1
                continue
            first_heading_seen = True
            clean = _strip_inline_markdown(line).strip()
            if clean:
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(Paragraph(_safe(clean), h3_style))
            i += 1
            continue

        # Bullet line (- item or * item)
        bullet_match = re.match(r'^[-*]\s+(.*)', line)
        if bullet_match:
            bullet_buffer.append(bullet_match.group(1).strip())
            i += 1
            continue

        # Empty line
        if not line.strip():
            _flush_bullets()
            i += 1
            continue

        # Regular text line — collect consecutive lines into one paragraph
        _flush_bullets()
        para_lines = []
        while i < len(lines):
            l = lines[i].rstrip()
            if not l.strip():
                break
            if re.match(r'^[-*]\s+', l) or re.match(r'^#{1,6}\s+', l):
                break
            if re.match(r'^\*\*(.+?)\*\*\s*$', l):
                break
            if re.match(r'^-{3,}$', l):
                break
            para_lines.append(_strip_inline_markdown(l))
            i += 1
        para_text = ' '.join(para_lines).strip()
        if para_text:
            elements.append(Paragraph(_safe(para_text), normal_style))
            elements.append(Spacer(1, 0.08 * inch))

    _flush_bullets()
    return elements

def _format_money(val):
    try:
        return f"${float(val):,.2f}"
    except Exception:
        return "$0.00"

def _format_pct(val):
    try:
        return f"{float(val)*100:.1f}%"
    except Exception:
        return "0.0%"

def _enum_value(val: str) -> str:
    """
    Strip Python enum repr prefix if present.
    e.g. 'CreditMethod.ASC' → 'ASC',  'QualificationBasis.INTERVIEW' → 'Interview'
    'ASC' → 'ASC'  (pass-through)
    """
    s = str(val)
    if "." in s and s.split(".")[0][0].isupper():
        # Looks like EnumClass.VALUE — return the VALUE part
        raw = s.split(".", 1)[1]
        # Convert SCREAMING_SNAKE to Title Case for display
        return raw.replace("_", " ").title()
    return s

def create_title_page(study_data):
    meta = study_data["study_metadata"]
    client = meta["prepared_for"]["legal_name"]
    year = meta["tax_year"]["year_label"]
    
    elements = []
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("R&amp;D Tax Credit Study", title_style))
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Prepared for: {_safe(client)}", h2_style))
    elements.append(Paragraph(f"Tax Year: {year}", h2_style))
    elements.append(PageBreak())
    return elements

def create_executive_summary(study_data, context):
    meta = study_data["study_metadata"]
    total_qre = context.get("total_qre", "0")
    asc = context.get("asc_computation", {})
    fed_credit = asc.get("federal_credit") or context.get("federal_credit", "0")

    elements = []
    elements.append(Paragraph("1. Executive Summary", h1_style))

    # Use LLM-generated executive summary if available, otherwise fall back to generic text
    exec_summary = study_data.get("executive_summary", "")
    if exec_summary:
        elements.extend(_markdown_to_elements(exec_summary, skip_first_heading=True))
    else:
        elements.append(Paragraph(
            f"This report documents the Qualified Research Expenditures (QREs) for "
            f"{meta['prepared_for']['legal_name']} for the tax year {meta['tax_year']['year_label']}.",
            normal_style,
        ))

    # For multi-year studies, include both current year and combined totals
    combined_qre = context.get("_multiyear_combined_qre")
    combined_credit = context.get("_multiyear_combined_credit")
    year_range = context.get("_multiyear_year_range", "")

    if combined_qre is not None:
        latest_year = meta["tax_year"]["year_label"]
        data = [
            ["Metric", "Value"],
            [f"Most Recent Year QREs ({latest_year})", _format_money(total_qre)],
            [f"Most Recent Year Federal R&D Credit ({latest_year})", _format_money(fed_credit)],
            [f"Combined {year_range} Total QREs", _format_money(combined_qre)],
            [f"Combined {year_range} Federal R&D Credit", _format_money(combined_credit)],
            ["Credit Method (All Years)", _enum_value(meta.get("credit_method", "ASC"))],
        ]
    else:
        data = [
            ["Metric", "Value"],
            ["Total QREs", _format_money(total_qre)],
            ["Federal R&D Credit", _format_money(fed_credit)],
            ["Credit Method", _enum_value(meta.get("credit_method", "ASC"))],
        ]
    t = Table(data, colWidths=[3.5 * inch, 2.8 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
    ]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_company_background(study_data):
    bg = study_data.get("company_background", {})
    meta = study_data.get("study_metadata", {})
    prepared_for = meta.get("prepared_for", {})
    tax_year = meta.get("tax_year", {})
    bf = study_data.get("business_flags", {})

    elements = []
    elements.append(Paragraph("2. Company Background", h1_style))

    # ── 2.1 Company Identity Table ───────────────────────────────────────────
    elements.append(Paragraph("2.1 Company Identity", h2_style))
    identity_data = [
        ["Field", "Value"],
        ["Legal Name", prepared_for.get("legal_name", "—")],
        ["EIN", prepared_for.get("ein", "—")],
        ["Entity Type", _enum_value(prepared_for.get("entity_type", "—"))],
        ["State of Incorporation", prepared_for.get("state_of_incorporation") or "—"],
        ["States of Operation", ", ".join(prepared_for.get("states_of_operation") or []) or "—"],
        ["DBA / Trade Name", prepared_for.get("dba") or "—"],
        ["Industry", prepared_for.get("industry", "—")],
        ["Website", prepared_for.get("website") or "—"],
        ["Tax Year Under Study", tax_year.get("year_label", "—")],
        ["Funded Research Exists", "Yes" if bf.get("funded_by_third_party") else "No"],
        ["Is Startup (IRC §41(h))", "Yes" if bf.get("is_startup") else "No"],
        ["Prior R&D Credit Claimed", "Yes" if bf.get("prior_credit_claimed") else "No"],
        ["Prior Form 6765 Years", ", ".join(bf.get("prior_6765_years") or []) or "—"],
    ]
    id_table = Table(identity_data, colWidths=[2.2*inch, 4.1*inch])
    id_table.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(id_table)
    elements.append(Spacer(1, 0.2 * inch))

    # ── 2.2 Business Overview narrative ─────────────────────────────────────
    elements.append(Paragraph("2.2 Business Overview", h2_style))
    elements.append(Paragraph(_safe(bg.get("business_overview", "")), normal_style))

    if bg.get("products_and_services"):
        elements.append(Paragraph("2.3 Products &amp; Services", h2_style))
        items = [ListItem(Paragraph(p, normal_style)) for p in bg["products_and_services"]]
        elements.append(ListFlowable(items, bulletType='bullet'))

    if bg.get("rd_departments"):
        elements.append(Paragraph("2.4 R&amp;D Departments", h2_style))
        items = [ListItem(Paragraph(_safe(d), normal_style)) for d in bg["rd_departments"]]
        elements.append(ListFlowable(items, bulletType='bullet'))

    elements.append(PageBreak())
    return elements

def create_project_narratives(study_data, year_label: str = ""):
    projects = study_data.get("rd_projects", [])
    employees = study_data.get("employees", [])
    elements = []
    section_title = f"3. Qualified Research Activities (Tax Year {year_label})" if year_label else "3. Qualified Research Activities"
    elements.append(Paragraph(section_title, h1_style))

    # ── Project Overview Summary Table ───────────────────────────────────────
    elements.append(Paragraph("3.0 Project Summary", h2_style))

    # Build a lookup: project_id → list of employee names
    proj_emp_map: dict = {}
    for emp in employees:
        for alloc in emp.get("project_allocation", []):
            pid = alloc.get("project_id", "")
            if pid:
                proj_emp_map.setdefault(pid, []).append(emp.get("employee_name", ""))

    summary_data = [["Project ID", "Project Name", "Status", "Start Date", "End Date", "Assigned Employees"]]
    for proj in projects:
        pid = proj.get("project_id", "")
        assigned = ", ".join(proj_emp_map.get(pid, [])) or "—"
        summary_data.append([
            Paragraph(_safe(pid), small_style),
            Paragraph(_safe(proj.get("project_name", "")), small_style),
            Paragraph(_safe(proj.get("status", "Ongoing")), small_style),
            Paragraph(_safe(str(proj.get("start_date") or "—")), small_style),
            Paragraph(_safe(str(proj.get("end_date") or "—")), small_style),
            Paragraph(_safe(assigned), small_style),
        ])

    summary_table = Table(
        summary_data,
        colWidths=[0.8*inch, 1.7*inch, 0.8*inch, 0.9*inch, 0.9*inch, 1.5*inch],
    )
    summary_table.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",  (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",   (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    for i, proj in enumerate(projects, 1):
        elements.append(Paragraph(f"Project {i}: {_safe(proj['project_name'])}", h2_style))
        elements.append(Spacer(1, 0.1 * inch))

        # ── i) Basic Project Information ─────────────────────────────────────
        elements.append(Paragraph("i) Basic Project Information", h3_style))
        pid = proj.get("project_id", "")
        assigned_names = ", ".join(proj_emp_map.get(pid, [])) or "—"
        basic_lines = [
            f"<b>Project ID:</b> {_safe(pid)}",
            f"<b>Business Component:</b> {_safe(proj.get('business_component', '—'))}",
            f"<b>Status:</b> {_safe(proj.get('status', 'Ongoing'))}",
            f"<b>Start Date:</b> {str(proj.get('start_date') or '—')}",
            f"<b>End Date:</b> {str(proj.get('end_date') or '—')}",
            f"<b>Assigned Employees:</b> {_safe(assigned_names)}",
        ]
        # ── Refined classification fields ─────────────────────────────────
        if proj.get("business_component_classification"):
            basic_lines.append(f"<b>BC Classification:</b> {_safe(proj['business_component_classification'])}")
        if proj.get("cross_year_business_component_id"):
            basic_lines.append(f"<b>Multi-Year BC ID:</b> {_safe(proj['cross_year_business_component_id'])}")
        if proj.get("qra_year"):
            basic_lines.append(f"<b>QRA Tax Year:</b> {proj['qra_year']}")
        if proj.get("uncertainty_resolution_date"):
            basic_lines.append(f"<b>Uncertainty Resolution Date:</b> {_safe(str(proj['uncertainty_resolution_date']))}")
        sw_flag = proj.get("is_commercial_sale_software")
        if sw_flag is not None:
            basic_lines.append(f"<b>Commercial-Sale Software:</b> {'Yes' if sw_flag else 'No'}")
            if sw_flag and proj.get("internal_use_software_exemption_note"):
                basic_lines.append(f"<b>IUS Exemption:</b> {_safe(proj['internal_use_software_exemption_note'])}")
        for line in basic_lines:
            elements.append(Paragraph(line, normal_style))

        # ── IRC Section References ────────────────────────────────────────
        irc_refs = proj.get("irc_section_references") or []
        if irc_refs:
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph(
                "<b>IRC / Reg. References:</b> " + _safe(", ".join(irc_refs)), normal_style))

        # ── Project QRE Attribution ────────────────────────────────────────
        proj_qre = proj.get("project_qre_summary") or proj.get("qre_summary") or {}
        credit_attr = proj.get("credit_attribution") or {}
        if proj_qre or credit_attr:
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph("Project QRE &amp; Credit Attribution", h3_style))
            attr_rows = [["Category", "Amount"]]
            if proj_qre.get("wage_qre") is not None:
                attr_rows.append(["Qualified Wages QRE", _format_money(proj_qre["wage_qre"])])
            if proj_qre.get("contractor_qre_after_65pct") is not None:
                attr_rows.append(["Qualified Contractor QRE (after 65%)", _format_money(proj_qre["contractor_qre_after_65pct"])])
            if proj_qre.get("supply_qre") is not None:
                attr_rows.append(["Qualified Supply QRE", _format_money(proj_qre["supply_qre"])])
            if proj_qre.get("cloud_qre") is not None:
                attr_rows.append(["Qualified Cloud QRE", _format_money(proj_qre["cloud_qre"])])
            total_proj_qre = proj_qre.get("total_project_qre") or proj_qre.get("total_qre") or 0
            if total_proj_qre:
                attr_rows.append(["Total Project QRE", _format_money(total_proj_qre)])
            if credit_attr.get("attribution_pct") is not None:
                attr_rows.append(["Attribution % of Year QRE", f"{float(credit_attr['attribution_pct']):.2f}%"])
            if credit_attr.get("proportional_credit") is not None:
                attr_rows.append(["Proportional R&amp;D Credit", _format_money(credit_attr["proportional_credit"])])
            if len(attr_rows) > 1:
                at = Table(attr_rows, colWidths=[3.0*inch, 1.5*inch])
                at.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
                ]))
                elements.append(at)

        elements.append(Spacer(1, 0.15 * inch))

        # ── Project Staff Allocation table ───────────────────────────────────
        # For this project, show every employee who contributed, their role,
        # % of total time allocated to this project, the QRE for this project,
        # and their activity type.
        proj_staff = []
        for emp in employees:
            for alloc in emp.get("project_allocation", []):
                if alloc.get("project_id") == pid:
                    wages    = float(str(emp.get("w2_box_1_wages", 0) or 0))
                    qual_pct = float(str(emp.get("qualified_percentage", 0) or 0))
                    time_pct = float(str(alloc.get("percent_of_employee_time", 0) or 0))
                    proj_qre = wages * qual_pct * time_pct
                    proj_staff.append({
                        "name":     emp.get("employee_name", ""),
                        "title":    emp.get("job_title", ""),
                        "time_pct": time_pct,
                        "proj_qre": proj_qre,
                        "activity": (emp.get("activity_type") or "direct_research")
                                    .replace("_", " ").title(),
                    })

        if proj_staff:
            elements.append(Paragraph("Project Staff Allocation", h3_style))
            staff_data = [["Employee", "Role", "% Time on Project", "QRE (this project)", "Activity Type"]]
            for s in proj_staff:
                staff_data.append([
                    Paragraph(s["name"],  small_style),
                    Paragraph(s["title"], small_style),
                    Paragraph(_format_pct(s["time_pct"]), small_style),
                    Paragraph(_format_money(s["proj_qre"]), small_style),
                    Paragraph(s["activity"], small_style),
                ])
            staff_table = Table(
                staff_data,
                colWidths=[1.5*inch, 1.7*inch, 1.1*inch, 1.2*inch, 1.1*inch],
            )
            staff_table.setStyle(TableStyle([
                ("GRID",           (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#1A5276")),
                ("TEXTCOLOR",      (0, 0), (-1,  0), colors.whitesmoke),
                ("FONTNAME",       (0, 0), (-1,  0), "Helvetica-Bold"),
                ("FONTSIZE",       (0, 0), (-1, -1), 8),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
                ("ALIGN",          (2, 1), (3, -1), "RIGHT"),
            ]))
            elements.append(staff_table)
            elements.append(Spacer(1, 0.2 * inch))

        gen = proj.get("generated_narratives") or {}
        tech = proj.get("technical_summary", {})

        # ii) Project Description
        elements.append(Paragraph("ii) Project Description", h3_style))
        if gen.get("project_description"):
            elements.append(Paragraph(gen["project_description"], normal_style))
        elif tech.get("objective"):
            elements.append(Paragraph(tech["objective"], normal_style))
        else:
            elements.append(Paragraph("[Analyst input required: project description]", normal_style))

        elements.append(Spacer(1, 0.1 * inch))

        # iii) New or Improved Business Component
        elements.append(Paragraph("iii) New or Improved Business Component", h3_style))
        if gen.get("new_improved_component"):
            elements.append(Paragraph(gen["new_improved_component"], normal_style))
        elif proj.get("business_component"):
            elements.append(Paragraph(proj["business_component"], normal_style))
        else:
            elements.append(Paragraph("[Analyst input required: business component description]", normal_style))

        elements.append(Spacer(1, 0.1 * inch))

        # iv) Elimination of Uncertainty
        elements.append(Paragraph("iv) Elimination of Uncertainty", h3_style))
        if gen.get("elimination_uncertainty"):
            elements.append(Paragraph(gen["elimination_uncertainty"], normal_style))
        elif tech.get("technical_uncertainty"):
            elements.append(Paragraph(tech["technical_uncertainty"], normal_style))
        else:
            elements.append(Paragraph("[Analyst input required: uncertainty description]", normal_style))

        elements.append(Spacer(1, 0.1 * inch))

        # v) Process of Experimentation
        elements.append(Paragraph("v) Process of Experimentation", h3_style))
        if gen.get("process_experimentation"):
            elements.append(Paragraph(gen["process_experimentation"], normal_style))
        elif tech.get("experimentation_process"):
            for step in tech["experimentation_process"]:
                elements.append(Paragraph(f"• {step}", normal_style))
        else:
            elements.append(Paragraph("[Analyst input required: experimentation process]", normal_style))

        elements.append(Spacer(1, 0.1 * inch))

        # vi) Technological in Nature
        elements.append(Paragraph("vi) Technological in Nature", h3_style))
        fpt = proj.get("four_part_test", {})
        if gen.get("technological_nature"):
            elements.append(Paragraph(gen["technological_nature"], normal_style))
        elif fpt.get("technological_in_nature"):
            elements.append(Paragraph(fpt["technological_in_nature"], normal_style))
        else:
            elements.append(Paragraph("[Analyst input required: technological nature description]", normal_style))

        elements.append(Spacer(1, 0.1 * inch))

        # vii) Resolution — how and when uncertainty was resolved (blueprint §4 sub-section 5)
        elements.append(Paragraph("vii) Resolution", h3_style))
        if gen.get("resolution"):
            elements.append(Paragraph(gen["resolution"], normal_style))
        elif tech.get("results_or_outcome") and tech["results_or_outcome"].strip():
            elements.append(Paragraph(tech["results_or_outcome"], normal_style))
        elif tech.get("failures_or_iterations") and tech["failures_or_iterations"].strip():
            elements.append(Paragraph(tech["failures_or_iterations"], normal_style))
        else:
            elements.append(Paragraph(
                "[Analyst input required: describe how and when technical uncertainty was resolved]",
                normal_style,
            ))

        # ── Prior Art Search Summary ───────────────────────────────────────
        if proj.get("prior_art_search_summary"):
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(Paragraph("viii) Prior Art &amp; Literature Review", h3_style))
            elements.append(Paragraph(_safe(proj["prior_art_search_summary"]), normal_style))

        # ── Excluded Activities within this Project ───────────────────────
        if proj.get("excluded_activities_within_project"):
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(Paragraph("ix) Excluded Activities within This Project", h3_style))
            elements.append(Paragraph(_safe(proj["excluded_activities_within_project"]), normal_style))

        # ── Cross-Year Business Component Note ────────────────────────────
        if proj.get("cross_year_note"):
            elements.append(Spacer(1, 0.1 * inch))
            note_style = ParagraphStyle(
                "CrossYearNote", parent=small_style,
                textColor=colors.HexColor("#154360"),
                backColor=colors.HexColor("#D6EAF8"),
                borderPad=4,
            )
            elements.append(Paragraph(
                f"<b>Multi-Year Business Component Note:</b> {_safe(proj['cross_year_note'])}",
                note_style,
            ))

        elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements

def create_four_part_test_table(study_data, year_label: str = ""):
    projects = study_data.get("rd_projects", [])
    elements = []
    section_title = f"4. IRS 4-Part Test Analysis (Tax Year {year_label})" if year_label else "4. IRS 4-Part Test Analysis"
    elements.append(Paragraph(section_title, h1_style))

    _PASS_STYLE = ParagraphStyle(
        "PassStyle", parent=small_style,
        textColor=colors.white, backColor=colors.HexColor("#1E8449"),
        fontName="Helvetica-Bold", alignment=1,
    )
    _FAIL_STYLE = ParagraphStyle(
        "FailStyle", parent=small_style,
        textColor=colors.white, backColor=colors.HexColor("#C0392B"),
        fontName="Helvetica-Bold", alignment=1,
    )

    criteria = [
        ("permitted_purpose",         "Permitted Purpose"),
        ("technological_in_nature",   "Technological in Nature"),
        ("elimination_of_uncertainty","Elimination of Uncertainty"),
        ("process_of_experimentation","Process of Experimentation"),
    ]

    # Map each criterion to the most relevant evidence_links category
    _CRITERION_EVIDENCE_MAP = {
        "permitted_purpose":          ["design_docs"],
        "technological_in_nature":    ["github_links", "design_docs"],
        "elimination_of_uncertainty": ["test_reports"],
        "process_of_experimentation": ["test_reports", "deployment_logs"],
    }

    for proj in projects:
        elements.append(Paragraph(f"Project: {_safe(proj.get('project_name', ''))}", h3_style))
        test = proj.get("four_part_test", {})
        evidence_links = proj.get("evidence_links") or {}

        data = [["Criterion", "Justification", "Result", "Source"]]
        for field, label in criteria:
            justification = test.get(field, "")
            passed = bool(justification and justification.strip())
            result_para = Paragraph("PASS" if passed else "FAIL",
                                    _PASS_STYLE if passed else _FAIL_STYLE)
            # Build source citations from evidence_links, mapped by criterion type
            doc_types = _CRITERION_EVIDENCE_MAP.get(field, [])
            source_refs = []
            for doc_type in doc_types:
                docs = evidence_links.get(doc_type) or []
                for doc in docs[:2]:
                    name = doc.split("/")[-1] if "/" in doc else doc
                    source_refs.append(name)
            source_text = "; ".join(source_refs[:3]) if source_refs else "—"
            data.append([
                Paragraph(f"<b>{label}</b>", small_style),
                Paragraph(justification or "—", small_style),
                result_para,
                Paragraph(source_text, small_style),
            ])

        t = Table(data, colWidths=[1.4*inch, 3.0*inch, 0.65*inch, 1.2*inch])
        t.setStyle(TableStyle([
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
            ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements

def create_cost_methodology(study_data):
    elements = []
    elements.append(Paragraph("5. Cost Identification Methodology", h1_style))
    
    rules = study_data.get("qre_calculation_rules", {})
    
    elements.append(Paragraph("A. Wage Selection Method", h2_style))
    method = _enum_value(rules.get("default_employee_qualification_basis", "Interview"))
    elements.append(Paragraph(f"Employee qualification percentages were determined via: {method}.", normal_style))
    
    elements.append(Paragraph("B. Contractor Qualification", h2_style))
    if rules.get("include_contractors"):
        elements.append(Paragraph("Contractor expenses were included. The 65% limitation rule was applied appropriately.", normal_style))
    
    elements.append(PageBreak())
    return elements

def create_employee_wage_schedule(context):
    elements = []
    elements.append(Paragraph("6A. Employee Wage Schedule", h1_style))

    qre_schedule = context.get("employee_qre_schedule", [])
    study_data = context.get("study_data", {})
    employees_raw = study_data.get("employees", []) if study_data else []

    if not qre_schedule:
        elements.append(Paragraph("No employee QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements

    # ── Summary table ────────────────────────────────────────────────────────
    elements.append(Paragraph("Summary", h3_style))
    summary_header = ["Name", "Role", "Total Wages", "Qualified %", "QRE", "Source Doc"]
    # Build lookup: employee_id → raw employee record
    emp_lookup = {e.get("employee_id", ""): e for e in employees_raw}

    data = [summary_header]
    for emp in qre_schedule:
        raw = emp_lookup.get(emp.get("employee_id", ""), {})
        source_doc = raw.get("source_doc") or "—"
        data.append([
            emp["employee_name"],
            emp["job_title"],
            _format_money(emp["total_wages"]),
            _format_pct(emp["qualified_percentage"]),
            _format_money(emp["qualified_wages"]),
            source_doc,
        ])

    total_qre = context.get("total_employee_qre", 0)
    data.append(["TOTAL", "", "", "", _format_money(total_qre), ""])

    t = Table(data, colWidths=[1.5*inch, 1.3*inch, 1.1*inch, 0.9*inch, 1.0*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.25 * inch))

    # ── Per-employee detailed blocks ─────────────────────────────────────────
    has_emp_detail = any(
        emp.get("generated_activity_narrative")
        or emp.get("rd_activities_description")
        or emp.get("qualification_narrative")
        or emp.get("time_tracking_method")
        for emp in employees_raw
    )
    if has_emp_detail:
        elements.append(Paragraph("Employee Qualification Detail", h3_style))
        for emp in employees_raw:
            name = emp.get("employee_name", "")
            title = emp.get("job_title", "")
            if not name:
                continue
            elements.append(Paragraph(
                f"<b>{_safe(name)} — {_safe(title)}</b>",
                ParagraphStyle("EmpNameStyle", parent=normal_style, textColor=colors.HexColor("#1A5276")),
            ))

            # Activity description (LLM-generated or raw)
            activity_narr = (
                emp.get("generated_activity_narrative")
                or emp.get("rd_activities_description")
                or ""
            )
            if activity_narr:
                elements.append(Paragraph("<b>R&amp;D Activity Description:</b>", normal_style))
                elements.append(Paragraph(_safe(activity_narr), normal_style))

            # Legal qualification narrative (from JSON)
            qual_narr = emp.get("qualification_narrative") or ""
            if qual_narr:
                elements.append(Paragraph("<b>IRC §41 Qualification Analysis:</b>", normal_style))
                elements.append(Paragraph(_safe(qual_narr), normal_style))

            # Time tracking & exclusions metadata
            meta_lines = []
            if emp.get("time_tracking_method"):
                meta_lines.append(f"<b>Time Tracking Method:</b> {_safe(emp['time_tracking_method'])}")
            if emp.get("work_location"):
                meta_lines.append(f"<b>Work Location:</b> {_safe(emp['work_location'])}")
            if emp.get("excluded_time_description"):
                meta_lines.append(f"<b>Excluded Time:</b> {_safe(emp['excluded_time_description'])}")
            rc_flag = emp.get("reasonable_compensation_flag")
            if rc_flag is not None:
                flag_text = "Applies — see officer compensation analysis" if rc_flag else "Not applicable"
                meta_lines.append(f"<b>§41(b)(2)(B) Reasonable Compensation:</b> {flag_text}")
                if emp.get("reasonable_compensation_note"):
                    meta_lines.append(f"<b>Note:</b> {_safe(emp['reasonable_compensation_note'])}")
            if emp.get("related_party_flag"):
                meta_lines.append("<b>Related Party Flag:</b> Yes — IRC §267 / §707 review required")
            for ml in meta_lines:
                elements.append(Paragraph(ml, small_style))

            elements.append(Spacer(1, 0.15 * inch))
        elements.append(Spacer(1, 0.1 * inch))

    # ── Per-project activity breakdown table ─────────────────────────────────
    if employees_raw:
        elements.append(Paragraph("Per-Project Activity Breakdown", h3_style))
        breakdown_data = [[
            "Employee", "Project", "% Time", "Qualified Wages", "Activity Type", "Qualification Basis"
        ]]
        for emp in employees_raw:
            wages = float(str(emp.get("w2_box_1_wages", 0) or 0))
            qual_pct = float(str(emp.get("qualified_percentage", 0) or 0))
            activity = (emp.get("activity_type") or "direct_research").replace("_", " ").title()
            basis = emp.get("qualification_basis") or "Interview"
            for alloc in emp.get("project_allocation", []):
                time_pct = alloc.get("percent_of_employee_time") or 0.0
                proj_qualified_wages = wages * qual_pct * time_pct
                breakdown_data.append([
                    emp.get("employee_name", ""),
                    alloc.get("project_id", ""),
                    _format_pct(time_pct),
                    _format_money(proj_qualified_wages),
                    activity,
                    basis,
                ])

        bt = Table(
            breakdown_data,
            colWidths=[1.4*inch, 0.7*inch, 0.7*inch, 1.2*inch, 1.1*inch, 1.3*inch],
        )
        bt.setStyle(TableStyle([
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
            ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
        ]))
        elements.append(bt)

    elements.append(PageBreak())
    return elements

def create_contractor_schedule(context):
    elements = []
    elements.append(Paragraph("6B. Contractor Schedule", h1_style))

    qre_schedule = context.get("contractor_qre_schedule", [])
    study_data = context.get("study_data", {})
    contractors_raw = study_data.get("contractors", []) if study_data else []
    vendor_lookup = {c.get("vendor_id", ""): c for c in contractors_raw}

    if not qre_schedule:
        elements.append(Paragraph("No contractor QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements

    data = [["Vendor", "Work Description", "Amount", "Qual %", "65% Rule", "Eligible", "Source Doc"]]
    for c in qre_schedule:
        raw = vendor_lookup.get(c.get("vendor_id", ""), {})
        src_docs = raw.get("source_docs") or []
        source_text = "; ".join(src_docs) if src_docs else "—"
        data.append([
            c["vendor_name"],
            Paragraph(c["description_of_work"], small_style),
            _format_money(c["total_paid"]),
            _format_pct(c["qualified_percentage"]),
            "Yes" if c["apply_65_rule"] else "No",
            _format_money(c["eligible_amount"]),
            Paragraph(source_text, small_style),
        ])

    total_qre = context.get("total_contractor_qre", 0)
    data.append(["TOTAL", "", "", "", "", _format_money(total_qre), ""])

    t = Table(data, colWidths=[1.2*inch, 1.5*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.8*inch, 1.1*inch])
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_supplies_schedule(context):
    elements = []
    elements.append(Paragraph("6C. Supplies Schedule", h1_style))

    qre_schedule = context.get("supplies_qre_schedule", [])
    study_data = context.get("study_data", {})
    supplies_raw = study_data.get("supplies", []) if study_data else []
    supply_lookup = {s.get("supply_id", ""): s for s in supplies_raw}

    if not qre_schedule:
        elements.append(Paragraph("No supply QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements

    data = [["Description", "Project", "Invoice Amount", "Consumed in Research", "QRE", "Source Doc"]]
    for s in qre_schedule:
        raw = supply_lookup.get(s.get("supply_id", ""), {})
        consumed = "Yes" if raw.get("consumed_in_research", True) else "No"
        src_docs = raw.get("source_docs") or []
        source_text = "; ".join(src_docs) if src_docs else "—"
        # Derive project IDs from project_allocation
        allocs = raw.get("project_allocation") or []
        proj_ids = ", ".join(
            a.get("project_id", "") for a in allocs if a.get("project_id")
        ) or "—"
        data.append([
            Paragraph(s["description"], small_style),
            Paragraph(proj_ids, small_style),
            _format_money(s["amount"]),
            consumed,
            _format_money(s["qualified_amount"]),
            Paragraph(source_text, small_style),
        ])

    total_qre = context.get("total_supplies_qre", 0)
    data.append(["TOTAL", "", "", "", _format_money(total_qre), ""])

    t = Table(data, colWidths=[1.7*inch, 0.8*inch, 1.0*inch, 1.0*inch, 0.9*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_cloud_schedule(context):
    elements = []
    elements.append(Paragraph("6D. Cloud Computing Schedule", h1_style))
    
    qre_schedule = context.get("cloud_qre_schedule", [])
    if not qre_schedule:
        elements.append(Paragraph("No cloud QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements
        
    data = [["Provider", "Service", "Amount", "Qual %", "QRE"]]
    for c in qre_schedule:
        data.append([
            c["provider"],
            c["service_category"],
            _format_money(c["amount"]),
            _format_pct(c["qualified_percentage"]),
            _format_money(c["qualified_amount"])
        ])
    
    total_qre = context.get("total_cloud_qre", 0)
    data.append(["TOTAL", "", "", "", _format_money(total_qre)])
    
    t = Table(data)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTWEIGHT', (0,-1), (-1,-1), 'BOLD')
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_asc_worksheet(context):
    elements = []
    elements.append(Paragraph("7. ASC Computation Worksheet (Form 6765)", h1_style))

    asc = context.get("asc_computation", {})
    if not asc:
        elements.append(Paragraph("ASC Computation data missing.", normal_style))
        return elements

    is_startup = bool(asc.get("is_startup", False))
    payroll_offset = bool(asc.get("payroll_tax_offset_eligible", False))
    study_data = context.get("study_data", {})
    bf = study_data.get("business_flags", {}) if study_data else {}

    avg = asc.get("average_prior_3_years", 0)
    base = asc.get("base_amount", 0)

    # Determine credit method label from qre_summary if available
    qre_summary = context.get("qre_summary") or (
        study_data.get("qre_summary") if study_data else None
    ) or {}
    credit_method = qre_summary.get("credit_method_used") or (
        "Startup_Payroll" if (is_startup and payroll_offset) else "ASC"
    )

    data = [
        ["Line Item", "Calculation", "Amount"],
        ["Current Year QRE", "Sum of all qualified expenditures", _format_money(asc.get("current_year_qre", 0))],
        ["Prior Year 1 QRE", "Year − 1 QRE", _format_money(asc.get("prior_year_1_qre", 0))],
        ["Prior Year 2 QRE", "Year − 2 QRE", _format_money(asc.get("prior_year_2_qre", 0))],
        ["Prior Year 3 QRE", "Year − 3 QRE", _format_money(asc.get("prior_year_3_qre", 0))],
        ["Average Prior 3 Years", "(Year−1 + Year−2 + Year−3) ÷ 3", _format_money(avg)],
        ["Base Amount", "Average Prior 3 Years × 50%", _format_money(base)],
        ["Excess QRE", "Current Year QRE − Base Amount", _format_money(asc.get("excess_qre", 0))],
        ["Credit Method Used", "IRC §41 election", credit_method],
        ["Credit Rate", "IRC §41(c)(5) — Alternative Simplified Credit", asc.get("credit_rate", "14%")],
        ["Federal R&D Credit", "Excess QRE × 14%", _format_money(asc.get("federal_credit", 0))],
    ]

    t = Table(data, colWidths=[2.0*inch, 2.8*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
        ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#F9E79F")),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F4F6F7")]),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    # ── Startup / Payroll Tax Offset Notice ──────────────────────────────────
    if is_startup:
        notice_style = ParagraphStyle(
            "StartupNotice", parent=normal_style,
            textColor=colors.HexColor("#154360"),
            backColor=colors.HexColor("#D6EAF8"),
            borderPad=6, borderWidth=1,
            borderColor=colors.HexColor("#1A5276"),
        )
        elements.append(Paragraph(
            "<b>Startup Notice (IRC §41(h)):</b> This company qualifies as a startup eligible to "
            "apply up to $500,000 of the R&amp;D credit against employer payroll taxes (FICA) instead "
            "of income tax. Complete Form 6765, Section D and attach to the applicable payroll tax "
            "return (Form 941).",
            notice_style,
        ))
        elements.append(Spacer(1, 0.1 * inch))
        if payroll_offset:
            elements.append(Paragraph(
                "<b>Payroll Tax Offset Elected:</b> The payroll tax offset has been elected for this "
                "study year. The credit amount above will be applied against employer FICA tax "
                "liability. Consult with a tax advisor regarding the maximum annual election amount.",
                notice_style,
            ))
            elements.append(Spacer(1, 0.1 * inch))

    # ── Prior Credit History disclosure ──────────────────────────────────────
    if bf.get("prior_credit_claimed"):
        prior_years = ", ".join(bf.get("prior_6765_years") or []) or "prior years"
        elements.append(Paragraph(
            f"<b>Prior Credit History:</b> Form 6765 was previously filed for {prior_years}. "
            "Prior-year QRE amounts have been incorporated into the ASC base period calculation above.",
            ParagraphStyle("PriorNote", parent=small_style, textColor=colors.HexColor("#4A235A")),
        ))
        elements.append(Spacer(1, 0.1 * inch))

    # ── §174 Disclosure ───────────────────────────────────────────────────────
    if bf.get("section_174_filed"):
        elements.append(Paragraph(
            "<b>IRC §174 Note:</b> Research and experimental expenditures for this tax year are "
            "subject to capitalization and amortization under IRC §174 (as amended by the TCJA). "
            "The QREs shown above reflect wages, contractor costs, and supply expenses — "
            "confirm the §174 amortization schedule has been filed with the return.",
            ParagraphStyle("S174Note", parent=small_style, textColor=colors.HexColor("#4A235A")),
        ))
        elements.append(Spacer(1, 0.1 * inch))

    # ── Carryforward Note ────────────────────────────────────────────────────
    elements.append(Paragraph(
        "<b>Carryforward Note:</b> If the federal R&amp;D credit exceeds the company's current-year "
        "regular tax liability (after applicable limitations), the unused credit may be carried "
        "back 1 year and carried forward up to 20 years under IRC §39. The computed credit above "
        "is the gross credit before the §280C election or carryforward analysis.",
        ParagraphStyle("CarryNote", parent=small_style, textColor=colors.HexColor("#4A235A")),
    ))
    elements.append(Spacer(1, 0.1 * inch))

    elements.append(PageBreak())
    return elements

def create_documentation_index(study_data):
    """
    §11 Supporting Documentation Index.

    Aggregates ALL source_doc / source_docs fields from every Input 1 array
    (employees, contractors, supplies) plus project evidence_links.
    Categorizes by: Financial Records | Project Documents | Employee Records |
    Contractor Records | Supply Records.
    """
    elements = []
    elements.append(Paragraph("11. Supporting Documentation Index", h1_style))
    elements.append(Paragraph(
        "The following documents were reviewed and relied upon in preparing this R&amp;D Tax Credit Study. "
        "All financial figures are sourced directly from verified source documents.",
        normal_style,
    ))
    elements.append(Spacer(1, 0.2 * inch))

    # Collect rows: (category, document_name, referenced_in)
    rows = []

    # Financial Records — gross receipts source docs
    gr = study_data.get("gross_receipts") or {}
    for doc in (gr.get("source_docs") or []):
        rows.append(("Financial Records", doc, "§10 Credit Calculation"))

    # Employee Records — W-2 / payroll source_doc per employee
    for emp in study_data.get("employees") or []:
        src = emp.get("source_doc")
        if src:
            rows.append(("Employee Records",
                         f"{emp.get('employee_name', emp.get('employee_id', ''))} — {src}",
                         "§6 / §7 Employee Schedule"))

    # Contractor Records — 1099 / invoice source_docs per contractor
    for con in study_data.get("contractors") or []:
        for doc in (con.get("source_docs") or []):
            rows.append(("Contractor Records",
                         f"{con.get('vendor_name', con.get('vendor_id', ''))} — {doc}",
                         "§8 Contractor Schedule"))

    # Supply Records — invoice source_docs per supply
    for sup in study_data.get("supplies") or []:
        for doc in (sup.get("source_docs") or []):
            rows.append(("Supply Records",
                         f"{sup.get('description', sup.get('supply_id', ''))} — {doc}",
                         "§9 Supplies Schedule"))

    # Project Documents — evidence_links from each project
    for p in study_data.get("rd_projects") or []:
        proj_name = p.get("project_name", p.get("project_id", "Project"))
        links = p.get("evidence_links") or {}
        for key, url_list in links.items():
            if not url_list:
                continue
            label = _LINK_LABELS.get(key, key.replace("_", " ").title())
            for url in (url_list if isinstance(url_list, list) else [url_list]):
                url_str = str(url).strip()
                if url_str:
                    rows.append(("Project Documents",
                                 f"{proj_name} — {label}: {url_str}",
                                 "§3 / §4 Technical Narratives"))

    # Additional Documentation — F1 field: interview-mentioned docs not already captured above
    for extra_doc in (study_data.get("additional_documentation") or []):
        extra_doc_str = str(extra_doc).strip()
        if extra_doc_str:
            rows.append(("Additional Documentation", extra_doc_str, "F1 — Interview Supplement"))

    if not rows:
        elements.append(Paragraph(
            "No source documents were provided in this submission. "
            "Attach W-2 reports, 1099-NECs, invoices, and project records before filing.",
            normal_style,
        ))
        elements.append(PageBreak())
        return elements

    # Group by category for display
    categories_order = [
        "Financial Records",
        "Employee Records",
        "Contractor Records",
        "Supply Records",
        "Project Documents",
        "Additional Documentation",
    ]
    grouped: dict = {c: [] for c in categories_order}
    for cat, doc, ref in rows:
        grouped.setdefault(cat, []).append((doc, ref))

    for cat in categories_order:
        cat_rows = grouped.get(cat, [])
        if not cat_rows:
            continue
        elements.append(Paragraph(cat, h3_style))
        table_data = [["Document / Reference", "Referenced In"]]
        for doc, ref in cat_rows:
            table_data.append([
                Paragraph(doc, small_style),
                Paragraph(ref, small_style),
            ])
        t = Table(table_data, colWidths=[4.5*inch, 2.0*inch])
        t.setStyle(TableStyle([
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND",  (0, 0), (-1,  0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",   (0, 0), (-1,  0), colors.whitesmoke),
            ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.15 * inch))

    elements.append(PageBreak())
    return elements

def create_assumptions_section(study_data):
    elements = []
    elements.append(Paragraph("9. Assumptions &amp; Disclosures", h1_style))
    
    disc = study_data.get("disclosures_and_assumptions", {})
    if disc.get("limitations"):
        elements.append(Paragraph("Limitations:", h2_style))
        for limit in disc["limitations"]:
            elements.append(Paragraph(f"\u2022 {_safe(limit)}", normal_style))
            
    if disc.get("disclaimer_text"):
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("Disclaimer:", h2_style))
        elements.append(Paragraph(_safe(disc["disclaimer_text"]), small_style))
        
    elements.append(PageBreak())
    return elements


# ============================================================================
# New Audit-Defence Sections (for novapulse_refined-style enriched JSON)
# ============================================================================

def create_audit_compliance_section(study_data) -> list:
    """
    §12 Audit Compliance Overview.

    Renders: Audit Risk Assessment, §280C Computation, Qualified Small Business
    analysis, CAMT applicability, credit carryforward, and filing metadata —
    all sourced from the enriched JSON fields.
    """
    elements = []
    has_content = any(study_data.get(k) for k in [
        "audit_risk_assessment", "section_280c_computation",
        "qualified_small_business_flag", "filing_metadata",
    ])
    bf = study_data.get("business_flags") or {}
    has_bf_content = any(bf.get(k) for k in [
        "section_280c_note", "credit_carryforward_note", "camt_note",
        "camt_applicable",
    ])
    if not has_content and not has_bf_content:
        return elements

    elements.append(Paragraph("12. Audit Compliance Overview", h1_style))
    elements.append(Spacer(1, 0.1 * inch))

    # ── Filing Metadata ──────────────────────────────────────────────────
    fm = study_data.get("filing_metadata") or {}
    if fm:
        elements.append(Paragraph("12.1 Filing Metadata", h2_style))
        fm_rows = [["Field", "Value"]]
        field_map = [
            ("federal_return_due_date", "Federal Return Due Date"),
            ("extension_due_date", "Extension Due Date"),
            ("extension_filed", "Extension Filed"),
            ("actual_filing_date", "Actual Filing Date"),
            ("form_6765_version", "Form 6765 Version"),
            ("return_type", "Return Type"),
            ("amended_return", "Amended Return"),
            ("ptin_preparer", "Preparer (PTIN)"),
        ]
        for key, label in field_map:
            val = fm.get(key)
            if val is not None:
                if isinstance(val, bool):
                    val = "Yes" if val else "No"
                fm_rows.append([label, Paragraph(_safe(str(val)), small_style)])
        if len(fm_rows) > 1:
            ft = Table(fm_rows, colWidths=[2.2*inch, 4.1*inch])
            ft.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(ft)
            elements.append(Spacer(1, 0.2 * inch))

    # ── Audit Risk Assessment ────────────────────────────────────────────
    ara = study_data.get("audit_risk_assessment") or {}
    if ara:
        elements.append(Paragraph("12.2 Audit Risk Assessment", h2_style))
        risk_level = str(ara.get("overall_risk", "—")).upper()
        risk_hex = {"LOW": "#1E8449", "MEDIUM": "#D35400", "HIGH": "#C0392B"}.get(risk_level, "#333333")
        risk_label_style = ParagraphStyle(
            "RiskLevelStyle", parent=normal_style,
            textColor=colors.HexColor(risk_hex), fontName="Helvetica-Bold",
        )
        elements.append(Paragraph(f"Overall Audit Risk: {risk_level}", risk_label_style))
        risk_factors = ara.get("risk_factors") or []
        if risk_factors:
            rf_rows = [["Risk Factor", "Direction"]]
            for rf in risk_factors:
                direction = str(rf.get("direction", "")).upper()
                dir_color = colors.HexColor("#1E8449") if "MITIGAT" in direction else colors.HexColor("#C0392B")
                rf_rows.append([
                    Paragraph(_safe(rf.get("factor", "")), small_style),
                    Paragraph(f"<b>{direction}</b>", ParagraphStyle(
                        "DirStyle", parent=small_style, textColor=dir_color,
                    )),
                ])
            rft = Table(rf_rows, colWidths=[4.5*inch, 1.8*inch])
            rft.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(rft)
        elements.append(Spacer(1, 0.2 * inch))

    # ── §280C Computation ────────────────────────────────────────────────
    s280c = study_data.get("section_280c_computation") or {}
    if s280c:
        elements.append(Paragraph("12.3 IRC §280C(c) Election Analysis", h2_style))
        s280c_rows = [["Line Item", "Value"]]
        s280c_map = [
            ("full_credit_rate", "Full Credit Rate (IRC §41 — 14%)"),
            ("reduced_credit_rate_280c", "Reduced Credit Rate (§280C election)"),
            ("credit_full_rate", "Credit at Full Rate"),
            ("credit_reduced_rate", "Credit at Reduced Rate"),
            ("incremental_credit_if_full_rate", "Incremental Credit if Full Rate"),
            ("incremental_174_deduction_lost_if_full_rate", "§174 Deduction Lost (Full Rate)"),
            ("tax_value_of_174_reduction_at_21pct", "Tax Value of §174 Reduction @ 21%"),
            ("net_benefit_of_full_rate_vs_reduced", "Net Benefit: Full Rate vs. Reduced"),
        ]
        for key, label in s280c_map:
            val = s280c.get(key)
            if val is not None:
                try:
                    fval = float(val)
                    display = f"{fval*100:.2f}%" if "rate" in key.lower() and fval < 1 else _format_money(fval)
                except Exception:
                    display = str(val)
                s280c_rows.append([label, display])
        if s280c.get("recommendation"):
            s280c_rows.append(["Analyst Recommendation", Paragraph(_safe(s280c["recommendation"]), small_style)])
        s280c_t = Table(s280c_rows, colWidths=[3.5*inch, 2.8*inch])
        s280c_t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 1), (1, -2), "RIGHT"),
        ]))
        elements.append(s280c_t)

        # §280C election status from business_flags
        election_made = bf.get("section_280c_election_made")
        if election_made is not None:
            status = "MADE (reduced-credit elected)" if election_made else "NOT MADE (full-rate credit — §174 deduction reduced)"
            badge_color = colors.HexColor("#1E8449") if election_made else colors.HexColor("#D35400")
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph(
                f"<b>§280C Election Status:</b> {_safe(status)}",
                ParagraphStyle("ElecStyle", parent=normal_style, textColor=badge_color),
            ))
        elif bf.get("section_280c_note"):
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(Paragraph(_safe(bf["section_280c_note"]),
                ParagraphStyle("S280Note", parent=small_style, textColor=colors.HexColor("#4A235A"))))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Qualified Small Business ─────────────────────────────────────────
    qsb = study_data.get("qualified_small_business_flag") or {}
    if qsb:
        elements.append(Paragraph("12.4 Qualified Small Business (IRC §41(h)) Analysis", h2_style))
        is_qsb = qsb.get("is_qualified_small_business")
        qsb_text = "Qualifies as QSB" if is_qsb else "Does NOT qualify as QSB"
        qsb_color = colors.HexColor("#1E8449") if is_qsb else colors.HexColor("#808B96")
        elements.append(Paragraph(
            f"<b>QSB Status:</b> {qsb_text}",
            ParagraphStyle("QSBStyle", parent=normal_style, textColor=qsb_color),
        ))
        if qsb.get("gross_receipts_test"):
            elements.append(Paragraph(_safe(qsb["gross_receipts_test"]), small_style))
        if qsb.get("five_year_rule"):
            elements.append(Paragraph(_safe(qsb["five_year_rule"]), small_style))
        elements.append(Spacer(1, 0.2 * inch))

    # ── CAMT Applicability ───────────────────────────────────────────────
    camt_applicable = bf.get("camt_applicable")
    if camt_applicable is not None:
        elements.append(Paragraph("12.5 Corporate Alternative Minimum Tax (CAMT)", h2_style))
        camt_text = "Applicable" if camt_applicable else "Not Applicable"
        camt_color = colors.HexColor("#C0392B") if camt_applicable else colors.HexColor("#1E8449")
        elements.append(Paragraph(
            f"<b>CAMT Status:</b> {camt_text}",
            ParagraphStyle("CAMTStyle", parent=normal_style, textColor=camt_color),
        ))
        if bf.get("camt_note"):
            elements.append(Paragraph(_safe(bf["camt_note"]), small_style))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Credit Carryforward ──────────────────────────────────────────────
    cf_balance = bf.get("credit_carryforward_prior_years_balance")
    if cf_balance is not None:
        elements.append(Paragraph("12.6 Credit Carryforward (IRC §39)", h2_style))
        elements.append(Paragraph(
            f"<b>Prior Years Carryforward Balance:</b> {_format_money(cf_balance)}",
            normal_style,
        ))
        if bf.get("credit_carryforward_note"):
            elements.append(Paragraph(_safe(bf["credit_carryforward_note"]), small_style))
        elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements


def create_research_methodology_section(study_data) -> list:
    """
    §13 Research Methodology & Compliance Analysis.

    Renders: Funded Research, Controlled Group, Shrinkback, Excluded Activities,
    Geographic Allocation, Documentation Standards, Form 6765 Checklist,
    §174 Details, Prior Year QRE Source Docs, Prototype/Production Boundary,
    and State Credits.
    """
    elements = []
    keys_to_check = [
        "funded_research_analysis", "controlled_group_analysis", "shrinkback_analysis",
        "excluded_activities_analysis", "geographic_research_allocation",
        "documentation_standards", "form_6765_section_b_checklist",
        "section_174_details", "prior_year_qre_source_docs",
        "prototype_production_boundary", "state_credits",
    ]
    if not any(study_data.get(k) for k in keys_to_check):
        return elements

    elements.append(Paragraph("13. Research Methodology &amp; Compliance Analysis", h1_style))
    elements.append(Spacer(1, 0.1 * inch))

    # ── Funded Research Analysis ─────────────────────────────────────────
    fra = study_data.get("funded_research_analysis") or {}
    if fra:
        elements.append(Paragraph("13.1 Funded Research Analysis (IRC §41(d)(4)(A))", h2_style))
        if fra.get("analysis"):
            elements.append(Paragraph(_safe(fra["analysis"]), normal_style))
        if fra.get("customer_contract_review"):
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(Paragraph(
                f"<b>Customer Contract Review:</b> {_safe(fra['customer_contract_review'])}",
                small_style,
            ))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Controlled Group Analysis ────────────────────────────────────────
    cga = study_data.get("controlled_group_analysis") or {}
    if cga:
        elements.append(Paragraph("13.2 Controlled Group Analysis (IRC §41(f)(1))", h2_style))
        if cga.get("analysis"):
            elements.append(Paragraph(_safe(cga["analysis"]), normal_style))
        if cga.get("conclusion"):
            elements.append(Paragraph(
                f"<b>Conclusion:</b> {_safe(cga['conclusion'])}",
                ParagraphStyle("ConcStyle", parent=small_style, textColor=colors.HexColor("#1E8449")),
            ))
        # Subsidiaries / brother-sister corps
        subs = cga.get("subsidiaries") or []
        bro_sis = cga.get("brother_sister_corps") or []
        if subs:
            elements.append(Paragraph(f"<b>Subsidiaries:</b> {_safe(', '.join(str(s) for s in subs))}", small_style))
        if bro_sis:
            elements.append(Paragraph(f"<b>Brother-Sister Corps:</b> {_safe(', '.join(str(s) for s in bro_sis))}", small_style))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Shrinkback Analysis ──────────────────────────────────────────────
    sha = study_data.get("shrinkback_analysis") or {}
    if sha:
        elements.append(Paragraph("13.3 Shrinkback Analysis (Treas. Reg. §1.41-4(b)(2))", h2_style))
        applied = sha.get("applied")
        applied_text = "Applied" if applied else "Not Required"
        applied_color = colors.HexColor("#D35400") if applied else colors.HexColor("#1E8449")
        elements.append(Paragraph(
            f"<b>Shrinkback:</b> {applied_text}",
            ParagraphStyle("ShrinkStyle", parent=normal_style, textColor=applied_color),
        ))
        if sha.get("analysis"):
            elements.append(Paragraph(_safe(sha["analysis"]), normal_style))
        if sha.get("treas_reg_reference"):
            elements.append(Paragraph(
                f"<b>Regulation Reference:</b> {_safe(sha['treas_reg_reference'])}",
                small_style,
            ))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Excluded Activities Analysis ─────────────────────────────────────
    eaa = study_data.get("excluded_activities_analysis") or {}
    if eaa:
        elements.append(Paragraph("13.4 Excluded Activities Analysis (IRC §41(d)(4))", h2_style))
        exclusion_labels = {
            "irc_41d4a_funded_research": "§41(d)(4)(A) — Funded Research",
            "irc_41d4b_foreign_research": "§41(d)(4)(F) — Foreign Research",
            "irc_41d4c_social_sciences": "§41(d)(4)(B) — Social Sciences / Arts / Humanities",
            "irc_41d4d_adaptation": "§41(d)(4)(C) — Adaptation of Existing Business Components",
            "irc_41d4e_duplication": "§41(d)(4)(D) — Duplication of Prior Research",
            "irc_41d4f_surveys": "§41(d)(4)(E) — Surveys, Studies, Research Relating to Management",
            "irc_41d4g_internal_use_software": "§41(d)(4)(F) — Internal Use Software (Standard)",
        }
        excl_rows = [["Exclusion", "Applies?", "Notes"]]
        for key, label in exclusion_labels.items():
            entry = eaa.get(key)
            if entry is None:
                continue
            if isinstance(entry, dict):
                applies = "Yes" if entry.get("applies") else "No"
                notes = _safe(entry.get("notes") or "—")
            else:
                applies = "Yes" if entry else "No"
                notes = "—"
            excl_rows.append([
                Paragraph(_safe(label), small_style),
                Paragraph(applies, ParagraphStyle(
                    "ApplStyle", parent=small_style,
                    textColor=colors.HexColor("#C0392B") if applies == "Yes" else colors.HexColor("#1E8449"),
                )),
                Paragraph(notes, small_style),
            ])
        if len(excl_rows) > 1:
            et = Table(excl_rows, colWidths=[2.5*inch, 0.7*inch, 3.1*inch])
            et.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(et)
        elements.append(Spacer(1, 0.2 * inch))

    # ── Geographic Research Allocation ───────────────────────────────────
    geo = study_data.get("geographic_research_allocation") or {}
    if geo:
        elements.append(Paragraph("13.5 Geographic Research Allocation", h2_style))
        us_pct = geo.get("us_research_pct")
        foreign_pct = geo.get("foreign_research_pct")
        if us_pct is not None:
            elements.append(Paragraph(
                f"<b>US Research:</b> {float(us_pct)*100:.0f}%  |  "
                f"<b>Foreign Research:</b> {float(foreign_pct or 0)*100:.0f}%",
                normal_style,
            ))
        sites = geo.get("research_sites") or []
        if sites:
            site_rows = [["Address", "State", "% of Research"]]
            for site in sites:
                site_rows.append([
                    Paragraph(_safe(site.get("address", "—")), small_style),
                    site.get("state") or "—",
                    f"{float(site.get('pct_of_research', 0))*100:.0f}%",
                ])
            st = Table(site_rows, colWidths=[3.5*inch, 0.7*inch, 1.1*inch])
            st.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(Spacer(1, 0.08 * inch))
            elements.append(st)
        if geo.get("foreign_personnel"):
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(Paragraph(
                f"<b>Foreign Personnel:</b> {_safe(geo['foreign_personnel'])}", small_style))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Documentation Standards ──────────────────────────────────────────
    ds = study_data.get("documentation_standards") or {}
    if ds:
        elements.append(Paragraph("13.6 Documentation Standards &amp; Substantiation", h2_style))
        if ds.get("primary_substantiation_method"):
            elements.append(Paragraph(
                f"<b>Substantiation Method:</b> {_safe(ds['primary_substantiation_method'])}",
                normal_style,
            ))
        if ds.get("contemporaneous_documentation_attestation"):
            elements.append(Paragraph(_safe(ds["contemporaneous_documentation_attestation"]), small_style))
        if ds.get("retention_policy"):
            elements.append(Paragraph(
                f"<b>Retention Policy:</b> {_safe(ds['retention_policy'])}", small_style))
        doc_types = ds.get("primary_documentation_types") or []
        if doc_types:
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(Paragraph("<b>Primary Documentation Types:</b>", small_style))
            items = [ListItem(Paragraph(_safe(str(d)), small_style)) for d in doc_types]
            elements.append(ListFlowable(items, bulletType='bullet'))
        elements.append(Spacer(1, 0.2 * inch))

    # ── Form 6765 Section B Checklist ────────────────────────────────────
    f6765 = study_data.get("form_6765_section_b_checklist") or {}
    if f6765:
        elements.append(Paragraph("13.7 Form 6765 Section B Checklist (ASC Method)", h2_style))
        chk_rows = [["Item", "Status"]]
        chk_labels = {
            "section_a_regular_credit": "Section A — Regular Credit Method",
            "section_b_asc_method": "Section B — Alternative Simplified Credit (ASC)",
            "controlled_group_member": "Controlled Group Member",
            "small_business_for_amt_offset": "Qualified Small Business for AMT Offset",
            "qualified_small_business_payroll_offset": "Payroll Tax Offset (§41(h))",
            "energy_research_consortium": "Energy Research Consortium",
            "research_payments_to_universities": "Basic Research Payments to Universities",
        }
        for key, label in chk_labels.items():
            val = f6765.get(key)
            if val is not None:
                chk_rows.append([
                    Paragraph(_safe(label), small_style),
                    Paragraph("☑ Yes" if val else "☐ No", ParagraphStyle(
                        "ChkStyle", parent=small_style,
                        textColor=colors.HexColor("#1E8449") if val else colors.HexColor("#808B96"),
                    )),
                ])
        if len(chk_rows) > 1:
            ct = Table(chk_rows, colWidths=[4.5*inch, 1.8*inch])
            ct.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
            ]))
            elements.append(ct)
        if f6765.get("note"):
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(Paragraph(_safe(f6765["note"]), small_style))
        elements.append(Spacer(1, 0.2 * inch))

    # ── §174 Details ─────────────────────────────────────────────────────
    s174 = study_data.get("section_174_details") or {}
    if s174:
        elements.append(Paragraph("13.8 IRC §174 Amortization Details", h2_style))
        s174_rows = [["Field", "Value"]]
        s174_map = [
            ("mandatory_amortization_applies", "Mandatory Amortization Applies"),
            ("effective_date_note", "Effective Date"),
            ("domestic_amortization_years", "Domestic Amortization Period (years)"),
            ("amortization_convention", "Amortization Convention"),
            ("first_year_deductible_pct", "First-Year Deductible %"),
            ("amortizable_amount_this_year", "Amortizable Amount This Year"),
            ("amortization_deduction_this_year", "Amortization Deduction This Year"),
            ("remaining_unamortized_balance", "Remaining Unamortized Balance"),
        ]
        for key, label in s174_map:
            val = s174.get(key)
            if val is not None:
                if isinstance(val, bool):
                    val = "Yes" if val else "No"
                elif isinstance(val, (int, float)) and "amount" in key.lower():
                    val = _format_money(val)
                elif isinstance(val, float) and val < 1:
                    val = f"{val*100:.0f}%"
                s174_rows.append([label, Paragraph(_safe(str(val)), small_style)])
        if len(s174_rows) > 1:
            s174t = Table(s174_rows, colWidths=[2.8*inch, 3.5*inch])
            s174t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(s174t)
        elements.append(Spacer(1, 0.2 * inch))

    # ── Prior Year QRE Source Docs ───────────────────────────────────────
    pyqre = study_data.get("prior_year_qre_source_docs") or {}
    if pyqre:
        elements.append(Paragraph("13.9 Prior Year QRE Source Documents (ASC Base)", h2_style))
        pyqre_rows = [["Year", "QRE Amount", "Source Document"]]
        for year_key, entry in sorted(pyqre.items()):
            if isinstance(entry, dict):
                qre_amt = _format_money(entry.get("qre", 0))
                source = _safe(entry.get("source", "—"))
            else:
                qre_amt = "—"
                source = _safe(str(entry))
            year_label_display = year_key.replace("year_minus_", "Year −").replace("_", " ")
            pyqre_rows.append([
                year_label_display,
                qre_amt,
                Paragraph(source, small_style),
            ])
        if len(pyqre_rows) > 1:
            pyqret = Table(pyqre_rows, colWidths=[1.2*inch, 1.2*inch, 3.9*inch])
            pyqret.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(pyqret)
        elements.append(Spacer(1, 0.2 * inch))

    # ── Prototype / Production Boundary ─────────────────────────────────
    ppb = study_data.get("prototype_production_boundary") or {}
    if ppb:
        elements.append(Paragraph("13.10 Prototype vs. Production Boundary", h2_style))
        ppb_rows = [["Project", "Experimentation End", "Production Start", "Boundary Description"]]
        for proj_id, boundary in ppb.items():
            if isinstance(boundary, dict):
                ppb_rows.append([
                    proj_id,
                    str(boundary.get("experimentation_end") or "—"),
                    str(boundary.get("production_start") or "—"),
                    Paragraph(_safe(boundary.get("boundary_description") or "—"), small_style),
                ])
        if len(ppb_rows) > 1:
            ppbt = Table(ppb_rows, colWidths=[0.8*inch, 1.2*inch, 1.2*inch, 3.1*inch])
            ppbt.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(ppbt)
        elements.append(Spacer(1, 0.2 * inch))

    # ── State Credits ────────────────────────────────────────────────────
    sc = study_data.get("state_credits") or {}
    if sc:
        elements.append(Paragraph("13.11 State R&amp;D Credits", h2_style))
        for form_key, details in sc.items():
            if not isinstance(details, dict):
                continue
            form_label = form_key.replace("_", " ").title()
            eligible = details.get("eligible")
            elig_text = "Eligible" if eligible else "Not Eligible"
            elig_hex = "#1E8449" if eligible else "#808B96"
            elig_style = ParagraphStyle(
                f"EligStyle_{form_key}", parent=normal_style,
                textColor=colors.HexColor(elig_hex),
            )
            elements.append(Paragraph(f"{_safe(form_label)}: {elig_text}", elig_style))
            state_rows = [["Field", "Value"]]
            state_map = [
                ("credit_rate", "Credit Rate"),
                ("qre_basis", "QRE Basis"),
                ("form_reference", "Form Reference"),
            ]
            for key, label in state_map:
                val = details.get(key)
                if val is not None:
                    display = f"{float(val)*100:.0f}%" if key == "credit_rate" else _safe(str(val))
                    state_rows.append([label, display])
            if len(state_rows) > 1:
                sct = Table(state_rows, colWidths=[1.8*inch, 4.5*inch])
                sct.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
                ]))
                elements.append(Spacer(1, 0.05 * inch))
                elements.append(sct)
            if details.get("note"):
                elements.append(Paragraph(_safe(details["note"]), small_style))
            elements.append(Spacer(1, 0.15 * inch))

    elements.append(PageBreak())
    return elements


def create_correction_summary_section(multi_year_raw: dict) -> list:
    """
    Study-Level Correction Summary — rendered at the front of multi-year reports
    when a correction_summary key is present in the top-level JSON.
    """
    cs = multi_year_raw.get("correction_summary") if isinstance(multi_year_raw, dict) else None
    if not cs:
        return []

    elements = []
    elements.append(Paragraph("Study Correction &amp; Compliance Log", h2_style))
    version = cs.get("version") or ""
    reviewer = cs.get("prepared_by_reviewer") or ""
    issues = cs.get("issues_resolved") or 0
    if version or reviewer:
        elements.append(Paragraph(
            f"<b>Version:</b> {_safe(version)}  |  "
            f"<b>Reviewer:</b> {_safe(reviewer)}  |  "
            f"<b>Issues Resolved:</b> {issues}",
            small_style,
        ))
        elements.append(Spacer(1, 0.1 * inch))

    def _render_list(heading: str, items: list, color: str = "#2C3E50"):
        if not items:
            return
        elements.append(Paragraph(heading, ParagraphStyle(
            "CorHdr", parent=normal_style,
            textColor=colors.HexColor(color), fontName="Helvetica-Bold",
        )))
        for item in items:
            elements.append(Paragraph(f"• {_safe(str(item))}", small_style))
        elements.append(Spacer(1, 0.08 * inch))

    _render_list("Critical Corrections", cs.get("critical_corrections") or [], "#C0392B")
    _render_list("Compliance Additions", cs.get("compliance_additions") or [], "#1A5276")
    _render_list("Risk Flags Documented", cs.get("risk_flags_documented") or [], "#D35400")

    elements.append(Spacer(1, 0.15 * inch))
    return elements


# ============================================================================
# Multi-Year Summary Section
# ============================================================================

def create_multi_year_summary_section(multi_year_qre_results: list, study_title: str = "") -> list:
    """
    Build a combined multi-year QRE and credit summary section.

    This section is inserted at the very beginning of a multi-year report,
    before the per-year narrative content.  It shows a single consolidated
    table with one row per tax year plus a TOTAL row.

    Args:
        multi_year_qre_results: List of per-year QRE result dicts from
                                 calculate_all_qre_multi_year().
        study_title:             Optional title string for the section header.

    Returns:
        List of ReportLab flowables.
    """
    elements = []

    # ── Section header ──────────────────────────────────────────────────────
    header_text = study_title if study_title else "Multi-Year R&D Tax Credit Summary"
    elements.append(Paragraph(header_text, title_style))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        "The following table summarises qualified research expenditures (QRE) and the "
        "computed Alternative Simplified Credit (ASC) for each tax year included in this study. "
        "Detailed schedules for each year appear in the sections that follow.",
        normal_style,
    ))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Combined summary table ───────────────────────────────────────────────
    col_headers = [
        "Tax Year",
        "Qualified\nWages",
        "Qualified\nContractors",
        "Qualified\nSupplies",
        "Qualified\nCloud",
        "Total QRE",
        "ASC Credit\n(14%)",
    ]

    def _fmt(val) -> str:
        try:
            return f"${float(val):,.0f}"
        except (TypeError, ValueError):
            return "$0"

    table_data = [col_headers]
    total_wages = total_contractors = total_supplies = total_cloud = total_qre = total_credit = 0.0

    for r in multi_year_qre_results:
        qs = r.get("qre_summary", {})
        wages = float(qs.get("total_qualified_wages", 0))
        contractors = float(qs.get("total_qualified_contractors", 0))
        supplies = float(qs.get("total_qualified_supplies", 0))
        cloud = float(qs.get("total_qualified_cloud", 0))
        qre = float(qs.get("total_qre", 0))
        credit = float(qs.get("asc_credit", 0))

        total_wages += wages
        total_contractors += contractors
        total_supplies += supplies
        total_cloud += cloud
        total_qre += qre
        total_credit += credit

        table_data.append([
            r.get("year_label", "—"),
            _fmt(wages),
            _fmt(contractors),
            _fmt(supplies),
            _fmt(cloud),
            _fmt(qre),
            _fmt(credit),
        ])

    # Totals row
    table_data.append([
        "TOTAL",
        _fmt(total_wages),
        _fmt(total_contractors),
        _fmt(total_supplies),
        _fmt(total_cloud),
        _fmt(total_qre),
        _fmt(total_credit),
    ])

    col_widths = [0.7 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 1.0 * inch, 1.1 * inch, 1.1 * inch]

    summary_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    summary_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("VALIGN",       (0, 0), (-1, 0),  "MIDDLE"),
        ("ROWBACKGROUND", (0, 0), (-1, 0), [colors.HexColor("#1a3a5c")]),
        # Data rows — alternating
        ("FONTNAME",     (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -2), 9),
        ("ALIGN",        (1, 1), (-1, -2), "RIGHT"),
        ("ALIGN",        (0, 1), (0, -2),  "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [colors.white, colors.HexColor("#f0f4f8")]),
        # Totals row
        ("BACKGROUND",   (0, -1), (-1, -1), colors.HexColor("#d0dcea")),
        ("FONTNAME",     (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, -1), (-1, -1), 9),
        ("ALIGN",        (1, -1), (-1, -1), "RIGHT"),
        ("ALIGN",        (0, -1), (0, -1),  "CENTER"),
        # Grid
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    # ── Per-year project count summary ──────────────────────────────────────
    elements.append(Paragraph("Projects by Tax Year", h2_style))
    elements.append(Spacer(1, 0.1 * inch))

    proj_headers = ["Tax Year", "R&D Projects", "Employees", "Contractors", "Supplies / Cloud"]
    proj_data = [proj_headers]

    for r in multi_year_qre_results:
        emp_sched = r.get("employee_qre_schedule", [])
        con_sched = r.get("contractor_qre_schedule", [])
        sup_sched = r.get("supplies_qre_schedule", [])
        cld_sched = r.get("cloud_qre_schedule", [])

        # Count unique project IDs from employee allocations as proxy
        proj_ids = set()
        for emp in emp_sched:
            # project IDs not directly stored per employee in schedule; use employee count
            pass

        proj_data.append([
            r.get("year_label", "—"),
            "See §3 Narratives",
            str(len(emp_sched)),
            str(len(con_sched)),
            f"{len(sup_sched)} / {len(cld_sched)}",
        ])

    proj_table = Table(proj_data, colWidths=[0.8 * inch, 1.5 * inch, 1.0 * inch, 1.2 * inch, 1.5 * inch])
    proj_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#2c5f8a")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  9),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 9),
        ("ALIGN",        (1, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    elements.append(proj_table)
    elements.append(Spacer(1, 0.3 * inch))

    # ── Combined credit note ─────────────────────────────────────────────────
    elements.append(Paragraph(
        f"<b>Combined Federal R&amp;D Tax Credit (All Years): {_fmt(total_credit)}</b>",
        normal_style,
    ))
    elements.append(Paragraph(
        "Credits are computed independently per tax year using the Alternative Simplified Credit (ASC) method "
        "under IRC Sec. 41(c)(5). Prior-year QRE figures used for each year's ASC base calculation are "
        "sourced from previously filed Form 6765 returns as provided in the study input data.",
        small_style,
    ))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        "Note: Carryforward provisions under IRC Sec. 39 apply if the credit cannot be fully utilized "
        "in the year generated. Consult qualified tax counsel regarding applicable carryforward periods "
        "and any interaction with prior-year credit claims.",
        small_style,
    ))

    elements.append(PageBreak())
    return elements

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
            items = [ListItem(Paragraph(_strip_inline_markdown(b), normal_style))
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
                elements.append(Paragraph(clean, h3_style))
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
            elements.append(Paragraph(para_text, normal_style))
            elements.append(Spacer(1, 0.08 * inch))

    _flush_bullets()
    return elements

def _format_money(val):
    try:
        return f"${float(val):,.2f}"
    except:
        return "$0.00"

def _format_pct(val):
    try:
        return f"{float(val)*100:.1f}%"
    except:
        return "0.0%"

def create_title_page(study_data):
    meta = study_data["study_metadata"]
    client = meta["prepared_for"]["legal_name"]
    year = meta["tax_year"]["year_label"]
    
    elements = []
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("R&D Tax Credit Study", title_style))
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Prepared for: {client}", h2_style))
    elements.append(Paragraph(f"Tax Year: {year}", h2_style))
    elements.append(PageBreak())
    return elements

def create_executive_summary(study_data, context):
    meta = study_data["study_metadata"]
    total_qre = context.get("total_qre", "0")
    fed_credit = context.get("asc_computation", {}).get("federal_credit", context.get("federal_credit", "0"))

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

    data = [
        ["Metric", "Value"],
        ["Total QREs", _format_money(total_qre)],
        ["Federal R&D Credit", _format_money(fed_credit)],
        ["Credit Method", meta.get("credit_method", "ASC")],
    ]
    t = Table(data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_company_background(study_data):
    bg = study_data.get("company_background", {})
    elements = []
    elements.append(Paragraph("2. Company Background", h1_style))
    elements.append(Paragraph("2.1 Business Overview", h2_style))
    elements.append(Paragraph(bg.get("business_overview", ""), normal_style))
    
    if bg.get("products_and_services"):
        elements.append(Paragraph("2.2 Products & Services", h2_style))
        items = [ListItem(Paragraph(p, normal_style)) for p in bg["products_and_services"]]
        elements.append(ListFlowable(items, bulletType='bullet'))
        
    elements.append(PageBreak())
    return elements

def create_project_narratives(study_data):
    projects = study_data.get("rd_projects", [])
    elements = []
    elements.append(Paragraph("3. Qualified Research Activities", h1_style))

    for i, proj in enumerate(projects, 1):
        elements.append(Paragraph(f"Project {i}: {proj['project_name']}", h2_style))
        elements.append(Paragraph(
            f"Business Component: {proj.get('business_component', '')}", normal_style
        ))
        elements.append(Spacer(1, 0.1 * inch))

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
        elif tech.get("results_or_outcome"):
            elements.append(Paragraph(tech["results_or_outcome"], normal_style))
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

        elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements

def create_four_part_test_table(study_data):
    projects = study_data.get("rd_projects", [])
    elements = []
    elements.append(Paragraph("4. IRS 4-Part Test Analysis", h1_style))
    
    data = [["Project", "Permitted Purpose", "Technological", "Uncertainty", "Experimentation"]]
    for p in projects:
        test = p.get("four_part_test", {})
        data.append([
            Paragraph(p['project_name'], small_style),
            Paragraph(test.get('permitted_purpose',''), small_style),
            Paragraph(test.get('technological_in_nature',''), small_style),
            Paragraph(test.get('elimination_of_uncertainty',''), small_style),
            Paragraph(test.get('process_of_experimentation',''), small_style)
        ])
        
    t = Table(data, colWidths=[1.2*inch]*5)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_cost_methodology(study_data):
    elements = []
    elements.append(Paragraph("5. Cost Identification Methodology", h1_style))
    
    rules = study_data.get("qre_calculation_rules", {})
    
    elements.append(Paragraph("A. Wage Selection Method", h2_style))
    method = rules.get("default_employee_qualification_basis", "Interview")
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
    if not qre_schedule:
        elements.append(Paragraph("No employee QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements
        
    data = [["Name", "Role", "Total Wages", "Qualified %", "QRE"]]
    for emp in qre_schedule:
        data.append([
            emp["employee_name"],
            emp["job_title"],
            _format_money(emp["total_wages"]),
            _format_pct(emp["qualified_percentage"]),
            _format_money(emp["qualified_wages"])
        ])
    
    # Add Total Row
    total_qre = context.get("total_employee_qre", 0)
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

def create_contractor_schedule(context):
    elements = []
    elements.append(Paragraph("6B. Contractor Schedule", h1_style))
    
    qre_schedule = context.get("contractor_qre_schedule", [])
    if not qre_schedule:
        elements.append(Paragraph("No contractor QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements
        
    data = [["Vendor", "Work Desc", "Amount", "Qual %", "65% Rule", "Eligible"]]
    for c in qre_schedule:
        data.append([
            c["vendor_name"],
            Paragraph(c["description_of_work"], small_style),
            _format_money(c["total_paid"]),
            _format_pct(c["qualified_percentage"]),
            "Yes" if c["apply_65_rule"] else "No",
            _format_money(c["eligible_amount"])
        ])
        
    total_qre = context.get("total_contractor_qre", 0)
    data.append(["TOTAL", "", "", "", "", _format_money(total_qre)])
    
    t = Table(data, colWidths=[1.5*inch, 2*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTWEIGHT', (0,-1), (-1,-1), 'BOLD')
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_supplies_schedule(context):
    elements = []
    elements.append(Paragraph("6C. Supplies Schedule", h1_style))
    
    qre_schedule = context.get("supplies_qre_schedule", [])
    if not qre_schedule:
        elements.append(Paragraph("No supply QREs claimed.", normal_style))
        elements.append(PageBreak())
        return elements
        
    data = [["Description", "Vendor", "Amount", "Qual %", "QRE"]]
    for s in qre_schedule:
        data.append([
            s["description"],
            s["vendor"],
            _format_money(s["amount"]),
            _format_pct(s["qualified_percentage"]),
            _format_money(s["qualified_amount"])
        ])
    
    total_qre = context.get("total_supplies_qre", 0)
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
        
    data = [
        ["Line Item", "Amount"],
        ["Current Year QRE", _format_money(asc.get("current_year_qre", 0))],
        ["Prior Year 1 QRE", _format_money(asc.get("prior_year_1_qre", 0))],
        ["Prior Year 2 QRE", _format_money(asc.get("prior_year_2_qre", 0))],
        ["Prior Year 3 QRE", _format_money(asc.get("prior_year_3_qre", 0))],
        ["Average Prior 3 Years", _format_money(asc.get("average_prior_3_years", 0))],
        ["Base Amount (50% of Avg)", _format_money(asc.get("base_amount", 0))],
        ["Excess QRE", _format_money(asc.get("excess_qre", 0))],
        ["Credit Rate", asc.get("credit_rate", "14%")],
        ["Federal R&D Credit", _format_money(asc.get("federal_credit", 0))]
    ]
    
    t = Table(data, colWidths=[4*inch, 2*inch])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (-1,-1), (-1,-1), colors.yellow), # Highlight total
        ('FONTWEIGHT', (-1,-1), (-1,-1), 'BOLD')
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements

def create_documentation_index(study_data):
    elements = []
    elements.append(Paragraph("8. Supporting Documentation", h1_style))
    elements.append(Paragraph("The following documents were relied upon:", normal_style))
    
    items = []
    items.append(ListItem(Paragraph("W-2 Reports", normal_style)))
    items.append(ListItem(Paragraph("General Ledger", normal_style)))
    items.append(ListItem(Paragraph("Contractor Invoices", normal_style)))
    
    # Extract project links if any
    for p in study_data.get("rd_projects", []):
        proj_name = p.get("project_name", "Project")
        links = p.get("evidence_links", {})
        for k, v in links.items():
            if not v:
                continue
            label = _LINK_LABELS.get(k, k.replace("_", " ").title())
            url_list = v if isinstance(v, list) else [v]
            for idx, url in enumerate(url_list, 1):
                url_str = str(url).strip()
                if url_str:
                    items.append(ListItem(
                        Paragraph(f"{proj_name} – {label} {idx}: {url_str}", small_style)
                    ))
             
    elements.append(ListFlowable(items, bulletType='bullet'))
    elements.append(PageBreak())
    return elements

def create_assumptions_section(study_data):
    elements = []
    elements.append(Paragraph("9. Assumptions & Disclosures", h1_style))
    
    disc = study_data.get("disclosures_and_assumptions", {})
    if disc.get("limitations"):
        elements.append(Paragraph("Limitations:", h2_style))
        for limit in disc["limitations"]:
            elements.append(Paragraph(f"• {limit}", normal_style))
            
    if disc.get("disclaimer_text"):
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("Disclaimer:", h2_style))
        elements.append(Paragraph(disc["disclaimer_text"], small_style))
        
    elements.append(PageBreak())
    return elements

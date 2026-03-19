"""
Comprehensive PDF Builder - Orchestrates the generation of the 10-section R&D Study.
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate
from pathlib import Path
from src.render.canvas import NumberedCanvas
from src.render.comprehensive_sections import (
    create_title_page,
    create_executive_summary,
    create_company_background,
    create_project_narratives,
    create_four_part_test_table,
    create_cost_methodology,
    create_employee_wage_schedule,
    create_contractor_schedule,
    create_supplies_schedule,
    create_cloud_schedule,
    create_asc_worksheet,
    create_documentation_index,
    create_assumptions_section,
    create_multi_year_summary_section,
    create_audit_compliance_section,
    create_research_methodology_section,
    create_correction_summary_section,
)


def build_multi_year_pdf(
    multi_year_study_data: list,
    multi_year_qre_results: list,
    context: dict,
    output_path: Path,
    logo_path: Path = None,
    study_title: str = "",
):
    """
    Build a combined multi-year PDF report.

    Renders a multi-year QRE summary section followed by the full 10-section
    report for the most-recent tax year (which contains the narrative content).

    Args:
        multi_year_study_data:  List of per-year RDStudyData dicts (oldest → newest).
        multi_year_qre_results: List of per-year QRE result dicts from calculation.
        context:                Agent context (contains narrative data for latest year).
        output_path:            Output PDF path.
        logo_path:              Optional logo.
        study_title:            Title for the multi-year summary section.
    """
    latest_study_data = multi_year_study_data[-1]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=study_title or f"Multi-Year R&D Study — {latest_study_data['study_metadata']['prepared_for']['legal_name']}",
    )

    story = []

    # Carry the top-level multi-year dict for correction summary access
    multi_year_raw = context.get("_multi_year_raw") or {}

    # 0. Title Page (using most-recent year data)
    story.extend(create_title_page(latest_study_data))

    # MULTI-YEAR SUMMARY — inserted immediately after title page
    story.extend(
        create_multi_year_summary_section(multi_year_qre_results, study_title=study_title)
    )

    # Correction / Compliance Log (study-level) — shown before executive summary
    story.extend(create_correction_summary_section(multi_year_raw))

    # 1. Executive Summary — with combined multi-year totals in the summary table
    combined_total_qre = sum(
        float(str(yr.get("total_qre", 0) or 0)) for yr in multi_year_qre_results
    )
    combined_fed_credit = sum(
        float(str((yr.get("asc_computation") or {}).get("federal_credit", 0) or 0))
        for yr in multi_year_qre_results
    )
    first_year = multi_year_study_data[0]["study_metadata"]["tax_year"]["year_label"]
    last_year  = multi_year_study_data[-1]["study_metadata"]["tax_year"]["year_label"]
    exec_ctx = dict(context)
    exec_ctx["_multiyear_combined_qre"]    = combined_total_qre
    exec_ctx["_multiyear_combined_credit"] = combined_fed_credit
    exec_ctx["_multiyear_year_range"]      = f"{first_year}–{last_year}"
    story.extend(create_executive_summary(latest_study_data, exec_ctx))

    # 2. Company Background
    story.extend(create_company_background(latest_study_data))

    # 3. Project Narratives — one section per year (oldest → newest)
    for yr_data in multi_year_study_data:
        yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        if yr_data.get("rd_projects"):
            story.extend(create_project_narratives(yr_data, year_label=yr_label))

    # 4. Four-Part Test — one section per year (oldest → newest)
    for yr_data in multi_year_study_data:
        yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        if yr_data.get("rd_projects"):
            story.extend(create_four_part_test_table(yr_data, year_label=yr_label))

    # 5. Cost Methodology (most-recent year)
    story.extend(create_cost_methodology(latest_study_data))

    # 6. QRE Schedules — render per year, each with its own year-specific study_data
    for yr_data, yr_qre in zip(multi_year_study_data, multi_year_qre_results):
        year_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        yr_ctx = dict(context)
        yr_ctx.update({k: v for k, v in yr_qre.items() if k != "year_label"})
        yr_ctx["_year_label_override"] = year_label
        # Critical: use year-specific study_data so wage/contractor/supply lookups are correct
        yr_ctx["study_data"] = yr_data

        story.extend(create_employee_wage_schedule(yr_ctx))
        story.extend(create_contractor_schedule(yr_ctx))
        story.extend(create_supplies_schedule(yr_ctx))
        story.extend(create_cloud_schedule(yr_ctx))

    # 7. ASC Worksheet — render per year
    for yr_data, yr_qre in zip(multi_year_study_data, multi_year_qre_results):
        yr_ctx = dict(context)
        yr_ctx.update({k: v for k, v in yr_qre.items() if k != "year_label"})
        yr_ctx["study_data"] = yr_data
        story.extend(create_asc_worksheet(yr_ctx))

    # 8. Documentation Index — aggregate all years' source docs
    all_docs = []
    for yr_data in multi_year_study_data:
        all_docs.extend(yr_data.get("additional_documentation", []))
    combined_doc_data = dict(latest_study_data)
    combined_doc_data["additional_documentation"] = list(dict.fromkeys(all_docs))
    # Merge all years' employees/contractors/supplies into combined_doc_data for full index
    combined_doc_data["employees"]    = []
    combined_doc_data["contractors"]  = []
    combined_doc_data["supplies"]     = []
    combined_doc_data["rd_projects"]  = []
    for yr_data in multi_year_study_data:
        combined_doc_data["employees"]   += yr_data.get("employees", [])
        combined_doc_data["contractors"] += yr_data.get("contractors", [])
        combined_doc_data["supplies"]    += yr_data.get("supplies", [])
        combined_doc_data["rd_projects"] += yr_data.get("rd_projects", [])
    story.extend(create_documentation_index(combined_doc_data))

    # 9. Assumptions & Disclosures (most-recent year)
    story.extend(create_assumptions_section(latest_study_data))

    # 12. Audit Compliance Overview (new — per year, using each year's enriched data)
    for yr_data in multi_year_study_data:
        yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        elems = create_audit_compliance_section(yr_data)
        if elems:
            from reportlab.platypus import Paragraph
            from src.render.comprehensive_sections import h1_style
            story.append(Paragraph(f"Tax Year {yr_label} — Audit Compliance Overview", h1_style))
            story.extend(elems)

    # 13. Research Methodology & Compliance Analysis (new — per year)
    for yr_data in multi_year_study_data:
        yr_label = yr_data["study_metadata"]["tax_year"]["year_label"]
        elems = create_research_methodology_section(yr_data)
        if elems:
            from reportlab.platypus import Paragraph
            from src.render.comprehensive_sections import h1_style
            story.append(Paragraph(f"Tax Year {yr_label} — Research Methodology", h1_style))
            story.extend(elems)

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, logo_path=logo_path, **kwargs
        ),
    )
    return output_path


def build_comprehensive_pdf(study_data: dict, context: dict, output_path: Path, logo_path: Path = None):
    """
    Build the full 10-section PDF report.
    
    Args:
        study_data: The comprehensive RDStudyData dict
        context: The agent context containing calculated totals
        output_path: Where to save the PDF
        logo_path: Optional logo path
    """
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=f"R&D Study - {study_data['study_metadata']['prepared_for']['legal_name']}"
    )
    
    story = []
    
    # 0. Title Page
    story.extend(create_title_page(study_data))
    
    # 1. Executive Summary
    story.extend(create_executive_summary(study_data, context))
    
    # 2. Company Background
    story.extend(create_company_background(study_data))
    
    # 3. Project Narratives
    story.extend(create_project_narratives(study_data))
    
    # 4. Four Part Test
    story.extend(create_four_part_test_table(study_data))
    
    # 5. Cost Methodology
    story.extend(create_cost_methodology(study_data))
    
    # 6. QRE Schedules (A, B, C, D)
    story.extend(create_employee_wage_schedule(context))
    story.extend(create_contractor_schedule(context))
    story.extend(create_supplies_schedule(context))
    story.extend(create_cloud_schedule(context))
    
    # 7. ASC Worksheet
    story.extend(create_asc_worksheet(context))
    
    # 8. Documentation
    story.extend(create_documentation_index(study_data))
    
    # 9. Assumptions & Disclosures
    story.extend(create_assumptions_section(study_data))

    # 12. Audit Compliance Overview (enriched JSON)
    story.extend(create_audit_compliance_section(study_data))

    # 13. Research Methodology & Compliance Analysis (enriched JSON)
    story.extend(create_research_methodology_section(study_data))

    # Build
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, logo_path=logo_path, **kwargs
        ),
    )
    return output_path

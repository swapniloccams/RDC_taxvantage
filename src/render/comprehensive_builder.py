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
    create_assumptions_section
)

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
    
    # Build
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, logo_path=logo_path, **kwargs
        ),
    )
    return output_path

"""Render package initialization."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, PageBreak

from .styles import get_report_styles, get_table_style, format_currency
from .canvas import NumberedCanvas
from .title_page import create_title_page
from .tables import create_expenditure_table, create_projects_summary_table
from .sections import (
    create_executive_summary_section,
    create_statutory_authority_section,
    create_project_analysis_section,
)


def render_pdf(report_data, output_path: Path, logo_path: Path = None):
    """
    Generate complete PDF report.
    
    Args:
        report_data: ReportData object with all report content
        output_path: Path where PDF should be saved
        logo_path: Optional path to logo image
    """
    # Create PDF document with custom canvas
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )
    
    # Build story (all content elements)
    story = []
    styles = get_report_styles()
    
    # Title page
    story.extend(create_title_page(report_data, styles))
    story.append(PageBreak())
    
    # Executive summary
    story.extend(create_executive_summary_section(report_data, styles))
    story.append(PageBreak())
    
    # Statutory authority
    story.extend(create_statutory_authority_section(styles))
    story.append(PageBreak())
    
    # Expenditure table
    story.append(create_expenditure_table(report_data))
    story.append(PageBreak())
    
    # Project analyses (all projects in one section)
    story.extend(create_project_analysis_section(report_data, styles))
    
    # Build PDF with custom canvas (for logo and page numbers)
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, logo_path=logo_path, **kwargs
        ),
    )


__all__ = [
    "get_report_styles",
    "get_table_style",
    "format_currency",
    "NumberedCanvas",
    "create_title_page",
    "create_expenditure_table",
    "create_projects_summary_table",
    "create_executive_summary_section",
    "create_statutory_authority_section",
    "create_project_analysis_section",
    "render_pdf",
]


"""Title page renderer."""

from reportlab.platypus import Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from src.schema import ReportData


def create_title_page(report_data: ReportData, styles: dict) -> list:
    """
    Create title page elements.
    
    Args:
        report_data: Report data
        styles: Paragraph styles dictionary
        
    Returns:
        List of flowable elements for title page
    """
    elements = []
    
    # Add vertical space
    elements.append(Spacer(1, 2 * inch))
    
    # Report title
    title = Paragraph(
        "Federal Research and Development<br/>Tax Credit Study",
        styles['ReportTitle']
    )
    elements.append(title)
    elements.append(Spacer(1, 0.5 * inch))
    
    # Client company name
    client = Paragraph(
        report_data.report_meta.client_company,
        styles['ClientName']
    )
    elements.append(client)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Tax year(s)
    year_text = f"Tax Year(s): {report_data.get_year_range_str()}"
    tax_year = Paragraph(year_text, styles['TaxYear'])
    elements.append(tax_year)
    
    # Page break after title page
    elements.append(PageBreak())
    
    return elements

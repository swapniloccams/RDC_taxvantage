"""Table formatters for expenditure summaries."""

from reportlab.platypus import Table
from src.schema import ReportData
from src.render.styles import get_table_style, format_currency


def create_expenditure_table(report_data: ReportData) -> Table:
    """
    Create Summary of R&D Expenditures table.
    
    Args:
        report_data: Report data with expenditures_by_year
        
    Returns:
        ReportLab Table object
    """
    # Table header
    data = [
        [
            "Tax Year",
            "Qualified Wages",
            "Qualified Contractors",
            "Qualified Supplies",
            "Qualified Cloud",
            "Total QRES",
            "Federal Credit",
        ]
    ]
    
    # Add rows for each year
    for exp in report_data.expenditures_by_year:
        data.append([
            str(exp.year),
            format_currency(exp.qualified_wages),
            format_currency(exp.qualified_contractors),
            format_currency(exp.qualified_supplies),
            format_currency(exp.qualified_cloud),
            format_currency(exp.total_qres),
            format_currency(exp.federal_credit),
        ])
    
    # Create table with column widths
    col_widths = [70, 80, 95, 85, 85, 80, 80]
    table = Table(data, colWidths=col_widths)
    table.setStyle(get_table_style())
    
    return table


def create_projects_summary_table(report_data: ReportData) -> Table:
    """
    Create Summary of R&D Projects table.
    
    Args:
        report_data: Report data with projects
        
    Returns:
        ReportLab Table object
    """
    # Table header
    data = [
        [
            "Project ID",
            "Project Name",
            "Status",
            "Total QRES",
            "Federal Credit",
        ]
    ]
    
    # Add rows for each project
    for project in report_data.projects:
        total_qres = (
            project.qualified_wages +
            project.qualified_contractors +
            project.qualified_supplies +
            project.qualified_cloud
        )
        
        data.append([
            project.project_id,
            project.project_name,
            project.status,
            format_currency(total_qres),
            format_currency(project.federal_credit),
        ])
    
    # Create table with column widths
    col_widths = [70, 200, 100, 90, 90]
    table = Table(data, colWidths=col_widths)
    table.setStyle(get_table_style())
    
    return table

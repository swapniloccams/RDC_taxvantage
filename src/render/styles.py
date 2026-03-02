"""ReportLab paragraph and table styles for consistent formatting."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import TableStyle


def get_report_styles():
    """Get custom paragraph styles for the report."""
    
    base_styles = getSampleStyleSheet()
    
    styles = {
        # Title page
        'ReportTitle': ParagraphStyle(
            'ReportTitle',
            parent=base_styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica-Bold',
        ),
        'ClientName': ParagraphStyle(
            'ClientName',
            parent=base_styles['Heading2'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#333333'),
            fontName='Helvetica-Bold',
        ),
        'TaxYear': ParagraphStyle(
            'TaxYear',
            parent=base_styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor('#666666'),
        ),
        
        # Section headings
        'Heading1': ParagraphStyle(
            'Heading1',
            parent=base_styles['Heading1'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica-Bold',
        ),
        'Heading2': ParagraphStyle(
            'Heading2',
            parent=base_styles['Heading2'],
            fontSize=14,
            spaceBefore=16,
            spaceAfter=10,
            textColor=colors.HexColor('#333333'),
            fontName='Helvetica-Bold',
        ),
        'Heading3': ParagraphStyle(
            'Heading3',
            parent=base_styles['Heading3'],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor('#444444'),
            fontName='Helvetica-Bold',
        ),
        
        # Body text
        'Body': ParagraphStyle(
            'Body',
            parent=base_styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
        ),
        'BodyLeft': ParagraphStyle(
            'BodyLeft',
            parent=base_styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        
        # Lists
        'BulletList': ParagraphStyle(
            'BulletList',
            parent=base_styles['Normal'],
            fontSize=11,
            leading=14,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=6,
        ),
    }
    
    return styles


def get_table_style():
    """Get standard table style for expenditure tables."""
    
    return TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # First column left-aligned
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Currency columns right-aligned
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#4a5568')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ])


def format_currency(value) -> str:
    """Format Decimal as currency string."""
    return f"${value:,.2f}"

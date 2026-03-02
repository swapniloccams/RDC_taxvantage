"""PDF Content JSON Schema - defines structure for PDF generation."""

from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal


class PDFTableRow(BaseModel):
    """Single row in a PDF table."""
    cells: List[str] = Field(description="Cell values for this row")


class PDFTable(BaseModel):
    """Table structure for PDF."""
    title: Optional[str] = Field(None, description="Table title/caption")
    headers: List[str] = Field(description="Column headers")
    rows: List[PDFTableRow] = Field(description="Table rows")
    column_widths: Optional[List[int]] = Field(None, description="Column widths in points")


class PDFSection(BaseModel):
    """A section of content in the PDF."""
    section_type: str = Field(description="Type: title_page, heading, paragraph, table, page_break")
    heading: Optional[str] = Field(None, description="Section heading text")
    content: Optional[str] = Field(None, description="Paragraph or text content")
    table: Optional[PDFTable] = Field(None, description="Table data if section_type is table")
    level: Optional[int] = Field(1, description="Heading level (1=h1, 2=h2, etc)")


class PDFPage(BaseModel):
    """A logical page in the PDF."""
    page_number: int = Field(description="Logical page number")
    page_title: str = Field(description="Title/description of this page")
    sections: List[PDFSection] = Field(description="Sections on this page")


class PDFContent(BaseModel):
    """Complete structured content for PDF generation."""
    
    # Metadata
    document_title: str = Field(description="Main document title")
    client_name: str = Field(description="Client company name")
    tax_years: str = Field(description="Tax year range (e.g., '2023-2024')")
    total_federal_credit: str = Field(description="Total federal credit amount")
    
    # Content pages
    pages: List[PDFPage] = Field(description="All pages in the document")
    
    # Raw data for reference
    executive_summary: str = Field(description="Executive summary text")
    expenditures_table_data: PDFTable = Field(description="Expenditures summary table")
    projects: List[dict] = Field(description="Project data with narratives")

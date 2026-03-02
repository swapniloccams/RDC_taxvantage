"""Custom canvas for page numbering and footer branding."""

from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that adds page numbers and logo to every page."""
    
    def __init__(self, *args, logo_path: Path = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []
        self.logo_path = logo_path
    
    def showPage(self):
        """Override to track pages."""
        self.pages.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        """Override to add page numbers on all pages."""
        num_pages = len(self.pages)
        
        for page_num in range(num_pages):
            self.__dict__.update(self.pages[page_num])
            self._add_page_footer(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        
        canvas.Canvas.save(self)
    
    def _add_page_footer(self, page_num: int, total_pages: int):
        """Add footer with logo and page number."""
        page_width = self._pagesize[0]
        page_height = self._pagesize[1]
        
        # Add logo bottom-left (if provided)
        if self.logo_path and self.logo_path.exists():
            try:
                logo_height = 0.6 * inch
                logo_x = 0.5 * inch
                logo_y = 0.3 * inch
                
                # Draw logo (maintaining aspect ratio)
                self.drawImage(
                    str(self.logo_path),
                    logo_x,
                    logo_y,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask='auto',
                )
            except Exception as e:
                # If logo fails, just skip it
                print(f"Warning: Could not add logo to page {page_num}: {e}")
        
        # Add page number bottom-right
        page_text = f"Page {page_num} of {total_pages}"
        self.setFont("Helvetica", 9)
        self.setFillColorRGB(0.4, 0.4, 0.4)
        
        text_width = self.stringWidth(page_text, "Helvetica", 9)
        text_x = page_width - text_width - 0.5 * inch
        text_y = 0.4 * inch
        
        self.drawString(text_x, text_y, page_text)

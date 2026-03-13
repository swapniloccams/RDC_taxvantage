"""Custom canvas for page numbering and footer branding."""

import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
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
        if self.logo_path and Path(self.logo_path).exists():
            try:
                logo_height = 0.6 * inch
                logo_x = 0.5 * inch
                logo_y = 0.3 * inch

                # Use Pillow to pre-process the image so ReportLab can handle
                # any PNG colour mode (RGBA, palette, etc.) reliably.
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(str(self.logo_path)) as pil_img:
                        # Convert to RGBA then to RGB for maximum compatibility
                        if pil_img.mode in ("RGBA", "LA", "P"):
                            background = PILImage.new("RGB", pil_img.size, (255, 255, 255))
                            if pil_img.mode == "P":
                                pil_img = pil_img.convert("RGBA")
                            background.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == "RGBA" else None)
                            pil_img = background
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        buf.seek(0)
                    logo_img = ImageReader(buf)
                except ImportError:
                    # Pillow not available — pass path directly (works for simple PNGs)
                    logo_img = str(self.logo_path)

                self.drawImage(
                    logo_img,
                    logo_x,
                    logo_y,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception as e:
                # If logo fails, skip silently — don't spam the console
                print(f"Warning: Could not add logo to page {page_num}: {e}")
        
        # Add page number bottom-right
        page_text = f"Page {page_num} of {total_pages}"
        self.setFont("Helvetica", 9)
        self.setFillColorRGB(0.4, 0.4, 0.4)
        
        text_width = self.stringWidth(page_text, "Helvetica", 9)
        text_x = page_width - text_width - 0.5 * inch
        text_y = 0.4 * inch
        
        self.drawString(text_x, text_y, page_text)

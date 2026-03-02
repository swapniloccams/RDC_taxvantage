"""Render Agent - generates final PDF report."""

import json
from pathlib import Path
from src.schema import ReportData
from src.render import render_pdf
from src.render.comprehensive_builder import build_comprehensive_pdf
from src.agents.framework import Agent


def generate_pdf_report(output_dir: str = None, logo_path: str = None, context: dict = None) -> dict:
    """
    Tool: Generate PDF report from validated report data.
    
    Args:
        output_dir: Directory for output files
        logo_path: Path to logo image (optional)
        context: Shared context dictionary
        
    Returns:
        Dictionary with PDF generation status
    """
    try:
        # Get report data from context
        if not context or "report_data" not in context:
            return {"error": "No report data in context"}
        
        report_data = ReportData(**context["report_data"])
        
        # Always prefer context-provided paths over LLM-supplied arguments.
        output_dir = (context or {}).get("output_dir") or output_dir
        logo_path = (context or {}).get("logo_path") or logo_path

        if not output_dir:
            return {"error": "No output directory specified"}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logo_file = Path(logo_path) if logo_path else None
        
        # Generate PDF filename
        client_slug = report_data.report_meta.client_company.replace(" ", "_")
        year_range = report_data.get_year_range_str()
        pdf_filename = f"{client_slug}_{year_range}_RND_Report.pdf"
        pdf_path = output_path / pdf_filename
        
        # Render PDF
        render_pdf(report_data, pdf_path, logo_file)
        
        # Save report JSON
        artifacts_dir = output_path / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        report_json_path = artifacts_dir / "report.json"
        with open(report_json_path, "w") as f:
            json.dump(report_data.model_dump(mode='json'), f, indent=2, default=str)
        
        return {
            "status": "success",
            "pdf_path": str(pdf_path),
            "report_json": str(report_json_path),
            "message": f"PDF report generated successfully: {pdf_filename}",
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Error generating PDF report",
        }


def generate_comprehensive_report(output_dir: str = None, logo_path: str = None, context: dict = None) -> dict:
    """
    Tool: Generate comprehensive 10-section PDF report.
    Use this when context has 'input_format' == 'comprehensive_csv', 'comprehensive_json',
    or 'input_type' == 'questionnaire'.

    Args:
        output_dir: Directory for output files (ignored — context value always takes priority)
        logo_path: Path to logo image (ignored — context value always takes priority)
        context: Shared context dictionary
    """
    try:
        if not context or "study_data" not in context:
            return {"error": "No study_data in context"}

        # Always prefer context-provided paths over LLM-supplied arguments.
        # The LLM can hallucinate path values; the coordinator sets correct paths in context.
        output_dir = context.get("output_dir") or output_dir or "output"
        logo_path = context.get("logo_path") or logo_path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logo_file = Path(logo_path) if logo_path else None
        
        # Filename
        study_data = context["study_data"]
        client = study_data["study_metadata"]["prepared_for"]["legal_name"].replace(" ", "_")
        year = study_data["study_metadata"]["tax_year"]["year_label"]
        pdf_filename = f"{client}_{year}_Comprehensive_Study.pdf"
        pdf_path = output_path / pdf_filename
        
        # Build
        build_comprehensive_pdf(study_data, context, pdf_path, logo_file)
        
        return {
            "status": "success",
            "pdf_path": str(pdf_path),
            "message": f"Generated 10-section comprehensive PDF: {pdf_filename}"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error generation PDF: {str(e)}"}


def pipeline_complete(context: dict = None) -> dict:
    """
    Tool: Signal that the pipeline is fully complete and no further work is needed.

    Call this AFTER a successful generate_comprehensive_report() or generate_pdf_report()
    to tell the orchestrator to stop.  Pass no arguments.

    Returns:
        Dictionary with status "pipeline_complete".
    """
    if context is not None:
        context["pipeline_done"] = True
    return {"status": "pipeline_complete", "message": "Pipeline finished. No further steps required."}


# Define Render Agent
render_agent = Agent(
    name="RenderAgent",
    instructions="""You are a rendering agent.

Your responsibilities:
- Generate the final PDF using the provided structured report JSON (computed tables + approved narratives).
- Do NOT change wording, structure, or numbers.
- Do NOT generate new content.
- Apply the fixed Occams template:
  - Occams logo on every page (bottom-left)
  - Page numbering "X of Y" (bottom-right)
  - Consistent fonts, spacing, and table styles

Tool usage:
1. If context["input_format"] is 'comprehensive_csv' or 'comprehensive_json':
     Call generate_comprehensive_report()
   Else (legacy):
     Call generate_pdf_report()
2. After the PDF generation tool returns successfully, IMMEDIATELY call pipeline_complete().
3. Your final text message must contain the word "complete".
""",
    functions=[generate_pdf_report, generate_comprehensive_report, pipeline_complete],
)

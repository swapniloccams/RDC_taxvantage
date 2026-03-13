"""Render Agent - generates final PDF report."""

import json
from pathlib import Path
from src.schema import ReportData
from src.render import render_pdf
from src.render.comprehensive_builder import build_comprehensive_pdf, build_multi_year_pdf
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


def generate_multi_year_report(output_dir: str = None, logo_path: str = None, context: dict = None) -> dict:
    """
    Tool: Generate combined multi-year PDF report.

    Use this when context['is_multi_year'] is True.
    Requires context['multi_year_study_data'] and context['multi_year_qre_results'].

    Args:
        output_dir: Directory for output files (ignored — context value always takes priority).
        logo_path:  Path to logo image (ignored — context value always takes priority).
        context:    Shared context dictionary.

    Returns:
        Dictionary with PDF generation status and path.
    """
    try:
        if not context:
            return {"error": "No context provided"}
        if "multi_year_study_data" not in context:
            return {"error": "No multi_year_study_data in context"}
        if "multi_year_qre_results" not in context:
            return {"error": "No multi_year_qre_results in context. Call calculate_multi_year_qre() first."}

        output_dir = context.get("output_dir") or output_dir or "output"
        logo_path = context.get("logo_path") or logo_path

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logo_file = Path(logo_path) if logo_path else None

        multi_year_data = context["multi_year_study_data"]
        multi_year_qre = context["multi_year_qre_results"]
        study_title = context.get("multi_year_title", "")

        latest = multi_year_data[-1]
        client = latest["study_metadata"]["prepared_for"]["legal_name"].replace(" ", "_")
        years = [yr["study_metadata"]["tax_year"]["year_label"] for yr in multi_year_data]
        year_range = f"{years[0]}-{years[-1]}"
        pdf_filename = f"{client}_{year_range}_MultiYear_RD_Study.pdf"
        pdf_path = output_path / pdf_filename

        build_multi_year_pdf(
            multi_year_study_data=multi_year_data,
            multi_year_qre_results=multi_year_qre,
            context=context,
            output_path=pdf_path,
            logo_path=logo_file,
            study_title=study_title,
        )

        context["pdf_path"] = str(pdf_path)

        return {
            "status": "success",
            "pdf_path": str(pdf_path),
            "message": f"Generated multi-year comprehensive PDF: {pdf_filename}",
            "years_covered": years,
        }

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error generating multi-year PDF: {exc}"}


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
1. If context contains 'is_multi_year' == True:
     Call generate_multi_year_report()
2. Else if context contains 'study_data' (all comprehensive / questionnaire / CSV paths):
     Call generate_comprehensive_report()
3. Else (legacy — context has 'report_data' only):
     Call generate_pdf_report()
4. After the PDF generation tool returns successfully, IMMEDIATELY call pipeline_complete().
5. Your final text message must contain the word "complete".
""",
    functions=[generate_pdf_report, generate_comprehensive_report, generate_multi_year_report, pipeline_complete],
)

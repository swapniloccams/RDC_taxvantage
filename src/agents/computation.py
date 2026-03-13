"""Computation Agent - performs deterministic calculations on report data."""

import json
from decimal import Decimal
from src.schema import ReportData, Expenditure
from src.compute import calculate_total_qres, calculate_federal_credit
from src.compute.comprehensive import calculate_all_qre, calculate_all_qre_multi_year
from src.agents.framework import Agent, Handoff


def calculate_expenditures(report_data_json: str = None, context: dict = None) -> dict:
    """
    Tool: Perform all deterministic calculations on report data.
    
    CRITICAL: This tool uses Python Decimal for all math. The LLM never performs calculations.
    
    Args:
        report_data_json: JSON string of report data (optional if in context)
        context: Shared context dictionary
        
    Returns:
        Dictionary with status and updated data
    """
    try:
        # Get report data from context or parameter
        if context and "report_data" in context:
            data_dict = context["report_data"]
        elif report_data_json:
            data_dict = json.loads(report_data_json)
        else:
            return {
                "status": "error",
                "error": "No report data provided",
            }
        
        report_data = ReportData(**data_dict)
        
        # Update each project with computed values
        for project in report_data.projects:
            # Calculate total QRES for project
            total_qres = calculate_total_qres(
                project.qualified_wages,
                project.qualified_contractors,
                project.qualified_supplies,
                project.qualified_cloud,
            )
            
            # Calculate federal credit if not provided
            if project.federal_credit == Decimal("0"):
                project.federal_credit = calculate_federal_credit(total_qres)
        
        # Aggregate expenditures by year
        year_aggregates: dict[int, dict[str, Decimal]] = {}
        
        for year in report_data.report_meta.years:
            year_aggregates[year] = {
                "qualified_wages": Decimal("0"),
                "qualified_contractors": Decimal("0"),
                "qualified_supplies": Decimal("0"),
                "qualified_cloud": Decimal("0"),
                "federal_credit": Decimal("0"),
            }
        
        # Sum up projects
        for project in report_data.projects:
            for year in report_data.report_meta.years:
                year_aggregates[year]["qualified_wages"] += project.qualified_wages / len(report_data.report_meta.years)
                year_aggregates[year]["qualified_contractors"] += project.qualified_contractors / len(report_data.report_meta.years)
                year_aggregates[year]["qualified_supplies"] += project.qualified_supplies / len(report_data.report_meta.years)
                year_aggregates[year]["qualified_cloud"] += project.qualified_cloud / len(report_data.report_meta.years)
                year_aggregates[year]["federal_credit"] += project.federal_credit / len(report_data.report_meta.years)
        
        # Create Expenditure objects
        expenditures = []
        for year in sorted(year_aggregates.keys()):
            agg = year_aggregates[year]
            total_qres = calculate_total_qres(
                agg["qualified_wages"],
                agg["qualified_contractors"],
                agg["qualified_supplies"],
                agg["qualified_cloud"],
            )
            
            expenditure = Expenditure(
                year=year,
                qualified_wages=agg["qualified_wages"],
                qualified_contractors=agg["qualified_contractors"],
                qualified_supplies=agg["qualified_supplies"],
                qualified_cloud=agg["qualified_cloud"],
                total_qres=total_qres,
                federal_credit=agg["federal_credit"],
            )
            expenditures.append(expenditure)
        
        report_data.expenditures_by_year = expenditures
        
        # Update context
        if context:
            context["report_data"] = report_data.model_dump(mode='json')
        
        return {
            "status": "success",
            "message": f"Calculated expenditures for {len(expenditures)} year(s)",
            "total_federal_credit": str(sum(e.federal_credit for e in expenditures)),
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Error during calculations",
        }


def calculate_comprehensive_qre(context: dict = None) -> dict:
    """
    Tool: Calculate QRE for comprehensive JSON study data.
    
    Calculates:
    - Employee-level wage QRE
    - Contractor-level QRE with 65% rule
    - Supplies QRE
    - Cloud computing QRE
    - ASC credit computation
    
    Args:
        context: Must contain 'study_data' from JSON ingestion
        
    Returns:
        Status dict with calculation results
    """
    try:
        study_data = context.get("study_data")
        
        if not study_data:
            return {
                "status": "error",
                "message": "No study_data in context"
            }
        
        # Calculate all QRE components
        results = calculate_all_qre(study_data)
        
        # Store results in context
        context.update(results)

        # Write qre_summary back into study_data so RenderAgent can access it directly
        if "qre_summary" in results and isinstance(study_data, dict):
            study_data["qre_summary"] = results["qre_summary"]
        
        return {
            "status": "success",
            "message": "Comprehensive QRE calculations complete",
            "total_employee_qre": str(results["total_employee_qre"]),
            "total_contractor_qre": str(results["total_contractor_qre"]),
            "total_supplies_qre": str(results["total_supplies_qre"]),
            "total_cloud_qre": str(results["total_cloud_qre"]),
            "total_qre": str(results["total_qre"]),
            "federal_credit": str(results["asc_computation"]["federal_credit"]),
            "qre_summary": results.get("qre_summary", {}),
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Calculation failed: {type(e).__name__}: {e}"
        }


def calculate_multi_year_qre(context: dict = None) -> dict:
    """
    Tool: Calculate QRE for all years in a multi-year study.

    Reads context['multi_year_study_data'] (list of per-year RDStudyData dicts),
    runs calculate_all_qre() per year, and stores results in:
      context['multi_year_qre_results']  — list of per-year QRE result dicts
      context['study_data']['qre_summary'] — QRE summary of the most-recent year

    Args:
        context: Must contain 'multi_year_study_data' from MultiYearJSONIngestionAgent.

    Returns:
        Status dict with per-year QRE totals.
    """
    try:
        multi_year_data = context.get("multi_year_study_data")
        if not multi_year_data:
            return {"status": "error", "message": "No multi_year_study_data in context"}

        results = calculate_all_qre_multi_year(multi_year_data)
        context["multi_year_qre_results"] = results

        # Also run for the most-recent year and write back into study_data
        # so that the existing single-year pipeline (NarrativeAgent, RenderAgent) works unmodified.
        latest_result = results[-1]
        context.update({k: v for k, v in latest_result.items() if k != "year_label"})
        if "qre_summary" in latest_result and isinstance(context.get("study_data"), dict):
            context["study_data"]["qre_summary"] = latest_result["qre_summary"]

        summary_lines = []
        combined_credit = 0.0
        for r in results:
            credit = float(r["asc_computation"]["federal_credit"])
            combined_credit += credit
            summary_lines.append(
                f"  {r['year_label']}: QRE=${float(r['total_qre']):,.0f}  ASC Credit=${credit:,.0f}"
            )

        return {
            "status": "success",
            "message": f"Multi-year QRE calculations complete for {len(results)} years",
            "per_year_summary": summary_lines,
            "combined_federal_credit": f"${combined_credit:,.0f}",
        }

    except Exception as exc:
        return {"status": "error", "message": f"Multi-year calculation failed: {type(exc).__name__}: {exc}"}


def handoff_to_narrative(context: dict = None) -> Handoff:
    """
    Tool: Handoff to NarrativeAgent after calculations complete.
    
    Args:
        context: Shared context dictionary
        
    Returns:
        Handoff to NarrativeAgent
    """
    from src.agents.narrative import narrative_agent
    
    return Handoff(
        agent=narrative_agent,
        context=context or {},
        reason="Calculations complete, ready for narrative generation"
    )

def handoff_to_render(context: dict = None) -> Handoff:
    """
    Tool: Handoff to RenderAgent directly (for comprehensive pipeline).
    
    Args:
        context: Shared context dictionary
        
    Returns:
        Handoff to RenderAgent
    """
    from src.agents.render_agent import render_agent
    
    return Handoff(
        agent=render_agent,
        context=context or {},
        reason="Calculations complete, comprehensive data ready for rendering"
    )


# Define Computation Agent
computation_agent = Agent(
    name="ComputationAgent",
    instructions="""You are a financial computation agent.

Your responsibilities:
- Perform deterministic calculations for R&D report tables using provided numeric inputs.
- Compute qualified expenditures (QRE) and federal credit values.
- Do NOT write prose.
- Do NOT guess or infer numbers.
- Never do math using language reasoning: always call tools.

Process — choose the path based on context keys:

PATH D — Multi-year JSON input (context has 'is_multi_year' == True):
  1. call calculate_multi_year_qre()
  2. then call handoff_to_narrative()

PATH A — Questionnaire input (context has 'input_type' == 'questionnaire'):
  1. call calculate_comprehensive_qre()
  2. then call handoff_to_narrative()
  (Narratives must be generated because the questionnaire path needs the NarrativeAgent
   to write project sections from source_answers and four_part_test fields.)

PATH B — Comprehensive CSV/JSON input (context has 'input_format' == 'comprehensive_csv' or 'comprehensive_json'):
  1. call calculate_comprehensive_qre()
  2. then call handoff_to_narrative()

PATH C — Legacy CSV input (neither of the above):
  1. call calculate_expenditures()
  2. then call handoff_to_narrative()

Rules:
- Output must be valid JSON only.
- Always call the appropriate handoff after calculations — never stop without a handoff.
- If inputs required for computation are missing, return a structured error listing missing fields and stop.
""",
    functions=[calculate_expenditures, calculate_comprehensive_qre, calculate_multi_year_qre, handoff_to_narrative, handoff_to_render],
)

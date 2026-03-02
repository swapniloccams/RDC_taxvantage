"""JSON Ingestion Agent - Validates and parses comprehensive JSON study data."""

from src.agents.framework import Agent, Handoff
from src.schema.study_schema import RDStudyData
import json
from pathlib import Path


def validate_and_parse_json(context: dict = None) -> dict:
    """
    Validate and parse JSON study data against RDStudyData schema.
    
    Args:
        context: Must contain 'json_path' key
        
    Returns:
        Status dict with validation results
    """
    json_path = context.get("json_path")
    
    if not json_path:
        return {
            "status": "error",
            "message": "No json_path provided in context"
        }
    
    try:
        # Read JSON file
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Validate with Pydantic
        study_data = RDStudyData(**data)
        
        # Store validated data in context
        context["study_data"] = study_data.model_dump()
        context["input_format"] = "comprehensive_json"
        
        return {
            "status": "success",
            "message": f"Validated comprehensive JSON study data",
            "projects": len(study_data.rd_projects),
            "employees": len(study_data.employees),
            "contractors": len(study_data.contractors),
            "supplies": len(study_data.supplies),
            "cloud_services": len(study_data.cloud_computing)
        }
        
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"JSON file not found: {json_path}"
        }
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "message": f"Invalid JSON syntax: {e}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Validation failed: {type(e).__name__}: {e}"
        }


def handoff_to_computation(context: dict = None) -> Handoff:
    """
    Hand off to computation agent for QRE calculations.
    
    Args:
        context: Contains validated study_data
        
    Returns:
        Handoff to computation agent
    """
    from src.agents.computation import computation_agent
    
    return Handoff(
        agent=computation_agent,
        context=context,
        reason="JSON validated successfully. Ready for QRE calculations (employee, contractor, supplies, cloud, ASC)."
    )


# Agent definition
json_ingestion_agent = Agent(
    name="JSONIngestionAgent",
    instructions="""You are the JSON Ingestion Agent responsible for validating comprehensive R&D study data.

Your responsibilities:
1. Validate JSON file against RDStudyData schema
2. Check all required fields are present
3. Verify data types and formats (EIN, dates, percentages, etc.)
4. Store validated data in context
5. Hand off to computation agent

Process:
1. Call validate_and_parse_json() to validate the JSON
2. If validation succeeds, call handoff_to_computation()
3. If validation fails, report errors clearly

IMPORTANT: After successful validation, you MUST call handoff_to_computation() to continue the pipeline.
""",
    functions=[validate_and_parse_json, handoff_to_computation]
)

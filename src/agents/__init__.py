"""Agent implementations for R&D report generation."""

from src.agents.framework import Agent, Handoff, AgentOrchestrator
from src.agents.csv_ingestion import csv_ingestion_agent, parse_single_csv
from src.agents.computation import computation_agent, calculate_expenditures
from src.agents.narrative import narrative_agent, generate_executive_summary_tool, generate_project_narratives_tool
from src.agents.compliance import compliance_agent, validate_report_completeness
from src.agents.render_agent import render_agent, generate_pdf_report

__all__ = [
    "Agent",
    "Handoff",
    "AgentOrchestrator",
    "csv_ingestion_agent",
    "computation_agent",
    "narrative_agent",
    "compliance_agent",
    "render_agent",
    "parse_single_csv",
    "calculate_expenditures",
    "generate_executive_summary_tool",
    "generate_project_narratives_tool",
    "validate_report_completeness",
    "generate_pdf_report",
]

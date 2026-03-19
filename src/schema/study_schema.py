"""Comprehensive R&D Study JSON Schema - Pydantic Models."""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class EntityType(str, Enum):
    """Valid entity types."""
    C_CORP = "C-Corp"
    S_CORP = "S-Corp"
    LLC = "LLC"
    PARTNERSHIP = "Partnership"
    SOLE_PROPRIETOR = "Sole Proprietor"


class CreditMethod(str, Enum):
    """Valid credit calculation methods."""
    ASC = "ASC"
    REGULAR = "Regular"


class ReturnType(str, Enum):
    """Valid return types."""
    ORIGINAL = "Original"
    AMENDED = "Amended"


class ProjectStatus(str, Enum):
    """Valid project statuses."""
    ONGOING = "Ongoing"
    COMPLETED = "Completed"
    SUSPENDED = "Suspended"


class QualificationBasis(str, Enum):
    """Valid qualification basis."""
    INTERVIEW = "Interview"
    TIME_TRACKING = "Time Tracking"
    JOB_TITLE = "Job Title"
    MANAGER_ESTIMATE = "Manager Estimate"


class ActivityType(str, Enum):
    """Employee activity type for R&D qualification."""
    DIRECT_RESEARCH = "direct_research"
    SUPERVISION = "supervision"
    SUPPORT = "support"


# ============================================================================
# Study Metadata
# ============================================================================

class PreparedFor(BaseModel):
    """Client information."""
    legal_name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")  # Format: XX-XXXXXXX
    entity_type: EntityType
    address: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    website: Optional[str] = None
    dba: Optional[str] = Field(None, description="DBA / trading name if different from legal name")
    state_of_incorporation: Optional[str] = Field(None, description="State where the entity is incorporated")
    states_of_operation: List[str] = Field(
        default_factory=list,
        description="All states where qualified research activities were performed",
    )


class PreparedBy(BaseModel):
    """Preparer information."""
    firm_name: str = Field(..., min_length=1)
    preparer_name: str = Field(..., min_length=1)
    date_prepared: date


class TaxYear(BaseModel):
    """Tax year information."""
    year_label: str = Field(..., pattern=r"^\d{4}$")  # Format: YYYY
    start_date: date
    end_date: date
    return_type: ReturnType = ReturnType.ORIGINAL


class StudyMetadata(BaseModel):
    """Study metadata and client information."""
    prepared_for: PreparedFor
    prepared_by: PreparedBy
    tax_year: TaxYear
    credit_method: CreditMethod = CreditMethod.ASC
    notes: Optional[str] = None


# ============================================================================
# Company Background
# ============================================================================

class CompanyBackground(BaseModel):
    """Company background information."""
    business_overview: str = Field(..., min_length=1)
    products_and_services: List[str] = Field(..., min_items=1)
    rd_departments: List[str] = Field(..., min_items=1)
    locations: List[str] = Field(..., min_items=1)
    org_structure_summary: str = Field(..., min_length=1)


# ============================================================================
# Gross Receipts
# ============================================================================

class GrossReceipts(BaseModel):
    """Gross receipts for current and prior years."""
    year_0: Decimal = Field(..., ge=0)
    year_minus_1: Decimal = Field(..., ge=0)
    year_minus_2: Decimal = Field(..., ge=0)
    year_minus_3: Decimal = Field(..., ge=0)


# ============================================================================
# R&D Projects
# ============================================================================

class TechnicalSummary(BaseModel):
    """Technical summary of R&D project."""
    objective: str = Field(..., min_length=1)
    problem_statement: str = Field(..., min_length=1)
    technical_uncertainty: str = Field(..., min_length=1)
    hypotheses_tested: List[str] = Field(default_factory=list)
    experimentation_process: List[str] = Field(default_factory=list)
    alternatives_considered: List[str] = Field(default_factory=list)
    results_or_outcome: str = ""
    failures_or_iterations: str = ""


class FourPartTest(BaseModel):
    """IRS 4-part test analysis."""
    permitted_purpose: str = Field(..., min_length=1)
    technological_in_nature: str = Field(..., min_length=1)
    elimination_of_uncertainty: str = Field(..., min_length=1)
    process_of_experimentation: str = Field(..., min_length=1)


class EvidenceLinks(BaseModel):
    """Supporting evidence documentation."""
    jira_links: List[str] = Field(default_factory=list)
    github_links: List[str] = Field(default_factory=list)
    design_docs: List[str] = Field(default_factory=list)
    test_reports: List[str] = Field(default_factory=list)
    deployment_logs: List[str] = Field(default_factory=list)
    other_supporting_docs: List[str] = Field(default_factory=list)


class RDProject(BaseModel):
    """R&D project definition."""
    project_id: str = Field(..., pattern=r"^P\d{3,}$")  # Format: P001, P002, etc.
    project_name: str = Field(..., min_length=1)
    business_component: str = Field(..., min_length=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: ProjectStatus = ProjectStatus.ONGOING
    technical_summary: TechnicalSummary
    four_part_test: FourPartTest
    evidence_links: EvidenceLinks = Field(default_factory=EvidenceLinks)
    source_answers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Raw questionnaire answers that produced this project's fields, keyed by question_id"
    )
    # ── Refined / audit-defence fields ──────────────────────────────────────
    cross_year_business_component_id: Optional[str] = Field(
        None, description="Stable BC identifier shared across multi-year QRAs for the same business component")
    cross_year_note: Optional[str] = Field(
        None, description="Human-readable note linking this QRA to adjacent-year QRAs for the same BC")
    is_commercial_sale_software: Optional[bool] = Field(
        None, description="True → sold/licensed externally; exempt from IUS high-threshold test")
    internal_use_software_exemption_note: Optional[str] = None
    business_component_classification: Optional[str] = Field(
        None, description="e.g. computer_software_commercial_sale, process, product")
    irc_section_references: List[str] = Field(
        default_factory=list, description="IRC/Treas. Reg. citations applicable to this project")
    qra_year: Optional[int] = Field(None, description="Tax year of this qualified research activity")
    project_qre_summary: Optional[Dict] = Field(
        None,
        alias="qre_summary",
        description="Project-level QRE breakdown: wage_qre, contractor_qre_after_65pct, supply_qre, cloud_qre, total_project_qre",
    )
    credit_attribution: Optional[Dict] = Field(
        None, description="attribution_pct, proportional_credit, basis — proportional share of year credit for this project")
    uncertainty_resolution_date: Optional[str] = Field(
        None, description="Quarter/date when the primary technical uncertainty was resolved e.g. '2022-Q4'")
    prior_art_search_summary: Optional[str] = Field(
        None, description="Summary of prior-art / literature review performed before project initiation")
    excluded_activities_within_project: Optional[str] = Field(
        None, description="Formal description of non-qualifying activities excluded from all allocations within this project")

    model_config = {"populate_by_name": True}


# ============================================================================
# Resource Allocations
# ============================================================================

class ProjectAllocation(BaseModel):
    """Allocation of resource to project."""
    project_id: str = Field(..., pattern=r"^P\d{3,}$")
    
    # Support multiple field names for different resource types
    percent_of_employee_time: Optional[float] = Field(None, ge=0.0, le=1.0)
    percent_of_vendor_work: Optional[float] = Field(None, ge=0.0, le=1.0)
    percent_of_supply_usage: Optional[float] = Field(None, ge=0.0, le=1.0)
    percent_of_cloud_usage: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @field_validator('percent_of_employee_time', 'percent_of_vendor_work', 'percent_of_supply_usage', 'percent_of_cloud_usage')
    @classmethod
    def validate_percentage(cls, v):
        """Ensure percentage is between 0 and 1."""
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError('Percentage must be between 0.0 and 1.0')
        return v
    
    def model_post_init(self, __context):
        """Ensure at least one percentage field is set."""
        percentages = [
            self.percent_of_employee_time,
            self.percent_of_vendor_work,
            self.percent_of_supply_usage,
            self.percent_of_cloud_usage
        ]
        if all(p is None for p in percentages):
            raise ValueError('At least one percentage field must be set')
    
    def get_percentage(self) -> float:
        """Get the percentage value regardless of field name."""
        for p in [self.percent_of_employee_time, self.percent_of_vendor_work, 
                  self.percent_of_supply_usage, self.percent_of_cloud_usage]:
            if p is not None:
                return p
        return 0.0


# ============================================================================
# Employees
# ============================================================================

class Employee(BaseModel):
    """Employee wage information."""
    employee_id: str = Field(..., pattern=r"^E\d{3,}$")  # Format: E001, E002, etc.
    employee_name: str = Field(..., min_length=1)
    job_title: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    w2_box_1_wages: Decimal = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    qualification_basis: QualificationBasis = QualificationBasis.INTERVIEW
    activity_type: ActivityType = ActivityType.DIRECT_RESEARCH
    is_owner_officer: bool = False
    source_doc: Optional[str] = Field(None, description="W-2 / payroll report filename for audit evidence")
    rd_activities_description: Optional[str] = Field(
        None,
        description="D1 — Narrative description of what this employee did on R&D (feeds §6 activity paragraph)",
    )
    owner_officer_detail: Optional[str] = Field(
        None,
        description="D4 — Owner/officer specific technical activity detail (excludes management/biz-dev time)",
    )
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Raw questionnaire answers for this employee keyed by question_id"
    )
    # ── Refined / audit-defence fields ──────────────────────────────────────
    qualification_narrative: Optional[str] = Field(
        None, description="Full legal qualification narrative — why this employee's work satisfies IRC §41 direct-research / supervision prongs")
    time_tracking_method: Optional[str] = Field(
        None, description="How the qualified percentage was substantiated (interview, Jira, timesheet, etc.)")
    excluded_time_description: Optional[str] = Field(
        None, description="Activities excluded from the qualified percentage with percentage estimate")
    reasonable_compensation_flag: Optional[bool] = Field(
        None, description="True if §41(b)(2)(B) reasonable-compensation analysis applies (owner/officers only)")
    reasonable_compensation_note: Optional[str] = None
    related_party_flag: Optional[bool] = Field(
        None, description="True if this employee is a related party under IRC §267 or §707")
    work_location: Optional[str] = Field(
        None, description="Primary work location — confirms US-based research requirement")


# ============================================================================
# Contractors
# ============================================================================

class RightsAndRisk(BaseModel):
    """Contractor rights and risk analysis."""
    company_retains_rights: bool
    company_bears_financial_risk: bool
    supporting_contract_reference: str = Field(..., min_length=1)


class Contractor(BaseModel):
    """Contractor/vendor information."""
    vendor_id: str = Field(..., pattern=r"^V\d{3,}$")  # Format: V001, V002, etc.
    vendor_name: str = Field(..., min_length=1)
    description_of_work: str = Field(..., min_length=1)
    total_amount_paid: Decimal = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    us_based: bool = Field(True, description="Must be True — foreign research is excluded from QRE")
    is_funded: bool = Field(False, description="True if this contractor's work was funded by a third party — may be excluded")
    contract_research_65_percent_rule_applies: bool = True
    rights_and_risk: RightsAndRisk
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    source_docs: List[str] = Field(default_factory=list, description="1099 / invoice filenames for audit evidence")
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Raw questionnaire answers for this contractor keyed by question_id"
    )
    compliance_flag: Optional[str] = Field(
        None, description="REVIEW REQUIRED | COMPLIANT | null — flags contractors that need analyst attention before filing")


# ============================================================================
# Supplies
# ============================================================================

class Supply(BaseModel):
    """Supply/materials information."""
    supply_id: str = Field(..., pattern=r"^S\d{3,}$")  # Format: S001, S002, etc.
    description: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    invoice_reference: str = Field(..., min_length=1)
    amount: Decimal = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    consumed_in_research: bool = True
    source_docs: List[str] = Field(default_factory=list, description="Invoice filenames for audit evidence")
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None
    compliance_flag: Optional[str] = Field(
        None, description="REVIEW REQUIRED | COMPLIANT | null — flags supplies that need analyst attention before filing")


# ============================================================================
# Cloud Computing
# ============================================================================

class CloudComputing(BaseModel):
    """Cloud computing service information."""
    cloud_id: str = Field(..., pattern=r"^C\d{3,}$")  # Format: C001, C002, etc.
    provider: str = Field(..., min_length=1)  # AWS, Azure, GCP, etc.
    service_category: str = Field(..., min_length=1)  # Compute, Storage, Database, etc.
    billing_reference: str = Field(..., min_length=1)
    amount: Decimal = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None


# ============================================================================
# QRE Calculation Rules
# ============================================================================

class QRECalculationRules(BaseModel):
    """Rules for QRE calculation."""
    include_wages: bool = True
    include_supplies: bool = True
    include_cloud: bool = True
    include_contractors: bool = True
    contractor_eligibility_rate: float = Field(0.65, ge=0.0, le=1.0)
    default_employee_qualification_basis: QualificationBasis = QualificationBasis.INTERVIEW
    allow_sampling_methodology: bool = False
    include_bonus_in_wages: bool = True
    exclude_foreign_research: bool = True


# ============================================================================
# ASC Calculation Inputs
# ============================================================================

class QREPriorYearsOverride(BaseModel):
    """Override for prior years QRE (if not calculated from gross receipts)."""
    enabled: bool = False
    year_minus_1_qre: Decimal = Field(Decimal("0"), ge=0)
    year_minus_2_qre: Decimal = Field(Decimal("0"), ge=0)
    year_minus_3_qre: Decimal = Field(Decimal("0"), ge=0)


class ASCCalculationInputs(BaseModel):
    """Inputs for ASC credit calculation."""
    qre_prior_years_override: QREPriorYearsOverride = Field(default_factory=QREPriorYearsOverride)


# ============================================================================
# Business Flags
# ============================================================================

class BusinessFlags(BaseModel):
    """Flags that affect credit eligibility and calculation path."""
    is_startup: bool = Field(
        False,
        description="True if company qualifies as a startup (≤5 years old, ≤$5M gross receipts) — enables payroll tax offset",
    )
    payroll_tax_offset_eligible: bool = Field(
        False,
        description="True if company can apply R&D credit against payroll taxes instead of income tax",
    )
    funded_by_third_party: bool = Field(
        False,
        description="True if any research was funded by customers, grants, or third parties — limits QRE eligibility",
    )
    # Blueprint alias — funded_research_exists is the term used in agent3_blueprint.docx
    funded_research_exists: bool = Field(
        False,
        description="Alias for funded_by_third_party — use either field; both are checked by the renderer",
    )
    wages_used_for_other_credits: bool = Field(
        False,
        description="True if wages were claimed under other credits (ERC, WOTC, etc.) — prevents double-counting",
    )
    prior_credit_claimed: bool = Field(
        False,
        description="True if Form 6765 has been filed in a prior year",
    )
    prior_6765_years: List[str] = Field(
        default_factory=list,
        description="Years in which Form 6765 was previously filed, e.g. ['2021', '2022']",
    )
    prior_qre_amounts: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Prior-year QRE amounts keyed by year string, e.g. {'2021': 85000, '2022': 112000}",
    )
    section_174_filed: bool = Field(
        False,
        description="True if IRC §174 amortization schedule has been filed for this tax year",
    )
    # ── Refined / audit-defence flags ───────────────────────────────────────
    section_280c_election_made: Optional[bool] = Field(
        None,
        description="True = reduced-credit election made (deduction not reduced); False = full-rate credit (deduction reduced); null = undecided",
    )
    section_280c_note: Optional[str] = Field(
        None,
        description="Analyst note explaining the §280C(c) election decision and its net economic impact",
    )
    credit_carryforward_prior_years_balance: Optional[float] = Field(
        None,
        description="Unused R&D credit balance carried forward from prior years (IRC §39)",
    )
    credit_carryforward_note: Optional[str] = Field(
        None,
        description="Narrative explanation of the carryforward balance and applicable tax years",
    )
    camt_applicable: Optional[bool] = Field(
        None,
        description="True if corporate AMT (15% AFSI, IRA 2022) applies — generally requires ≥$1B average AFSI",
    )
    camt_note: Optional[str] = Field(
        None,
        description="Analyst note confirming CAMT applicability determination",
    )


# ============================================================================
# Interview Metadata
# ============================================================================

class InterviewMetadata(BaseModel):
    """
    Tracks the completion status of the Input 2 interview session.

    Blueprint Validation Rule 8 requires status = 'complete' before
    Agent 3 generates any content.
    """
    status: str = Field(
        default="pending",
        description="'complete' | 'pending_followup' — must be 'complete' to proceed",
    )
    interviewer: Optional[str] = Field(None, description="Name of the consultant who conducted the interview")
    interview_date: Optional[str] = Field(None, description="Date the interview was completed (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, description="Any follow-up items or caveats from the interview")


# ============================================================================
# QRE Summary
# ============================================================================

class QRESummary(BaseModel):
    """
    Pre-computed QRE totals — mirrors the blueprint's qre_summary{} object in Input 1.

    Populated by ComputationAgent after running calculate_all_qre().
    Used directly in §10 Credit Calculation without further arithmetic.
    """
    total_qualified_wages: Decimal = Field(Decimal("0"), ge=0)
    total_qualified_contractors: Decimal = Field(Decimal("0"), ge=0)
    total_qualified_supplies: Decimal = Field(Decimal("0"), ge=0)
    total_qualified_cloud: Decimal = Field(Decimal("0"), ge=0)
    total_qre: Decimal = Field(Decimal("0"), ge=0)
    avg_qre_prior_3_years: Decimal = Field(Decimal("0"), ge=0)
    asc_base_amount: Decimal = Field(Decimal("0"), ge=0)
    asc_excess_qre: Decimal = Field(Decimal("0"), ge=0)
    asc_credit: Decimal = Field(Decimal("0"), ge=0)
    credit_method_used: str = Field(
        default="ASC",
        description="'ASC' | 'Regular' | 'Startup_Payroll'",
    )


# ============================================================================
# Output Preferences
# ============================================================================

class OutputPreferences(BaseModel):
    """Preferences for output generation."""
    currency: str = "USD"
    format: str = "StudyDocument"
    include_appendices: bool = True
    include_employee_detail_table: bool = True
    include_vendor_detail_table: bool = True
    include_project_narratives: bool = True
    include_four_part_test_table: bool = True
    include_form_6765_tie_out: bool = True


# ============================================================================
# Disclosures and Assumptions
# ============================================================================

class DisclosuresAndAssumptions(BaseModel):
    """Methodology disclosures and assumptions."""
    methodology_summary: str = Field(..., min_length=1)
    limitations: List[str] = Field(..., min_items=1)
    disclaimer_text: str = Field(..., min_length=1)


# ============================================================================
# Main Schema
# ============================================================================

class RDStudyData(BaseModel):
    """Complete R&D Study data structure."""
    study_metadata: StudyMetadata
    company_background: CompanyBackground
    gross_receipts: GrossReceipts
    rd_projects: List[RDProject] = Field(..., min_items=1)
    employees: List[Employee] = Field(..., min_items=1)
    contractors: List[Contractor] = Field(default_factory=list)
    supplies: List[Supply] = Field(default_factory=list)
    cloud_computing: List[CloudComputing] = Field(default_factory=list)
    qre_calculation_rules: QRECalculationRules = Field(default_factory=QRECalculationRules)
    asc_calculation_inputs: ASCCalculationInputs = Field(default_factory=ASCCalculationInputs)
    business_flags: BusinessFlags = Field(default_factory=BusinessFlags)
    output_preferences: OutputPreferences = Field(default_factory=OutputPreferences)
    disclosures_and_assumptions: DisclosuresAndAssumptions
    golden_answer: Optional[str] = Field(
        None,
        description="F2 — client's own words describing their qualified research activities (used in Executive Summary)",
    )
    interview_metadata: Optional[InterviewMetadata] = Field(
        default_factory=InterviewMetadata,
        description="Tracks interview completion status — must be 'complete' before generation proceeds",
    )
    qre_summary: Optional[QRESummary] = Field(
        default_factory=QRESummary,
        description="Pre-computed QRE totals populated by ComputationAgent — mirrors blueprint qre_summary{}",
    )
    additional_documentation: List[str] = Field(
        default_factory=list,
        description="F1 — additional document filenames mentioned during the interview not already in source arrays",
    )
    interview_responses: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Global questionnaire answers keyed by question_id for full traceability"
    )
    # ── Refined / audit-defence year-level fields ────────────────────────────
    asc_results: Optional[Dict] = Field(
        None,
        description="Pre-computed ASC results: avg_prior_3yr_qre, base_amount_50pct, excess_qre, credit_full_rate_14pct, credit_reduced_rate_280c",
    )
    audit_risk_assessment: Optional[Dict] = Field(
        None,
        description="overall_risk (LOW/MEDIUM/HIGH) plus list of risk_factors with factor and direction (MITIGATES/INCREASES)",
    )
    controlled_group_analysis: Optional[Dict] = Field(
        None,
        description="Analysis confirming whether any controlled group members exist under IRC §41(f)(1) / §1563",
    )
    documentation_standards: Optional[Dict] = Field(
        None,
        description="Primary substantiation method, contemporaneous attestation, retention policy",
    )
    excluded_activities_analysis: Optional[Dict] = Field(
        None,
        description="Per-exclusion analysis: funded research (§41(d)(4)(A)), foreign research (§41(d)(4)(F)), etc.",
    )
    filing_metadata: Optional[Dict] = Field(
        None,
        description="Federal return due date, extension status, actual filing date, Form 6765 version, preparer PTIN",
    )
    form_6765_section_b_checklist: Optional[Dict] = Field(
        None,
        description="Boolean checklist mirroring Form 6765 Section B (ASC method) line items",
    )
    funded_research_analysis: Optional[Dict] = Field(
        None,
        description="Analysis confirming no funded research exists: government grants, customer contracts, SBIR/STTR, etc.",
    )
    geographic_research_allocation: Optional[Dict] = Field(
        None,
        description="US vs foreign research percentage, research sites, foreign personnel note",
    )
    gross_receipts_labeled: Optional[Dict] = Field(
        None,
        description="Gross receipts keyed by calendar year label (e.g. {'2022': 8200000, '2021': 6400000})",
    )
    prior_year_qre_source_docs: Optional[Dict] = Field(
        None,
        description="Source document references for prior-year QREs used in ASC base calculation",
    )
    prototype_production_boundary: Optional[Dict] = Field(
        None,
        description="Per-project dict defining when experimentation ended and commercial production started",
    )
    qre_totals: Optional[Dict] = Field(
        None,
        description="Pre-computed year QRE totals: wage_qre, contractor_qre_after_65pct, supply_qre, cloud_qre, total_qre",
    )
    qualified_small_business_flag: Optional[Dict] = Field(
        None,
        description="QSB payroll-tax-offset eligibility: is_qualified_small_business, gross_receipts_test, five_year_rule",
    )
    section_174_details: Optional[Dict] = Field(
        None,
        description="§174 amortization detail: mandatory_amortization_applies, domestic_amortization_years, convention, first_year_deduction",
    )
    section_280c_computation: Optional[Dict] = Field(
        None,
        description="Detailed §280C(c) election analysis: credit rates, dollar amounts, net benefit comparison, recommendation",
    )
    shrinkback_analysis: Optional[Dict] = Field(
        None,
        description="Treas. Reg. §1.41-4(b)(2) shrinkback analysis: applied flag, analysis narrative, regulation reference",
    )
    state_credits: Optional[Dict] = Field(
        None,
        description="State R&D credit analysis keyed by form (e.g. colorado_dr0289): eligible, credit_rate, qre_basis, note",
    )
    
    @field_validator('rd_projects')
    @classmethod
    def validate_unique_project_ids(cls, v):
        """Ensure all project IDs are unique."""
        project_ids = [p.project_id for p in v]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError('Project IDs must be unique')
        return v
    
    @field_validator('employees')
    @classmethod
    def validate_unique_employee_ids(cls, v):
        """Ensure all employee IDs are unique."""
        employee_ids = [e.employee_id for e in v]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError('Employee IDs must be unique')
        return v


# ============================================================================
# Multi-Year Study Wrapper
# ============================================================================

class MultiYearStudyData(BaseModel):
    """
    Wrapper for multi-year R&D studies (2–5 tax years in a single JSON input).

    Each element of tax_years is a complete RDStudyData object for one year.
    Years must be in chronological order (oldest → newest).
    The pipeline uses the most-recent year for narrative generation and renders
    per-year QRE schedules plus a combined multi-year summary table.
    """
    study_title: str = Field(..., min_length=1, description="Human-readable title for the combined study document")
    combined_credit_method: CreditMethod = Field(
        CreditMethod.ASC,
        description="Credit calculation method applied to all years (currently only ASC supported for multi-year)",
    )
    tax_years: List[RDStudyData] = Field(
        ...,
        description="List of complete RDStudyData objects, one per tax year, ordered oldest to newest",
    )
    correction_summary: Optional[Dict] = Field(
        None,
        description="Study-level correction log: version, reviewer, issues_resolved, critical_corrections, compliance_additions, risk_flags_documented",
    )

    @field_validator("tax_years")
    @classmethod
    def validate_min_two_years(cls, v):
        if len(v) < 2:
            raise ValueError("multi_year_study must contain at least 2 tax years")
        if len(v) > 5:
            raise ValueError("multi_year_study supports a maximum of 5 tax years")
        return v

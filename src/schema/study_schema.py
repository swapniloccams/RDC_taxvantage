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
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Raw questionnaire answers for this employee keyed by question_id"
    )


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
    contract_research_65_percent_rule_applies: bool = True
    rights_and_risk: RightsAndRisk
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Raw questionnaire answers for this contractor keyed by question_id"
    )


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
    project_allocation: List[ProjectAllocation] = Field(..., min_items=1)
    notes: Optional[str] = None


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
    output_preferences: OutputPreferences = Field(default_factory=OutputPreferences)
    disclosures_and_assumptions: DisclosuresAndAssumptions
    interview_responses: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Global questionnaire answers keyed by question_id for full traceability"
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

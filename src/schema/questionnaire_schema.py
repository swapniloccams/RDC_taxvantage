"""Questionnaire Answers Schema - Pydantic models for structured interview/answers input."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict


# ============================================================================
# Section A: Study Metadata Answers
# ============================================================================

class StudyMetadataAnswers(BaseModel):
    """Client and engagement identification answers."""
    client_legal_name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")
    entity_type: str = Field(..., description="C-Corp, S-Corp, LLC, Partnership, or Sole Proprietor")
    address: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    website: Optional[str] = None
    tax_year: str = Field(..., pattern=r"^\d{4}$")
    credit_method: str = Field(default="ASC", description="ASC or Regular")
    preparer_firm: str = Field(..., min_length=1)
    preparer_name: str = Field(..., min_length=1)
    date_prepared: str = Field(..., description="ISO format: YYYY-MM-DD")

    @field_validator("credit_method")
    @classmethod
    def validate_credit_method(cls, v: str) -> str:
        if v not in ("ASC", "Regular"):
            raise ValueError("credit_method must be 'ASC' or 'Regular'")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        valid = {"C-Corp", "S-Corp", "LLC", "Partnership", "Sole Proprietor"}
        if v not in valid:
            raise ValueError(f"entity_type must be one of {valid}")
        return v


# ============================================================================
# Section B: Company Background Answers
# ============================================================================

class CompanyBackgroundAnswers(BaseModel):
    """Company overview and organisational context answers."""
    business_overview: str = Field(..., min_length=1)
    products_and_services: List[str] = Field(..., min_length=1)
    rd_departments: List[str] = Field(..., min_length=1)
    locations: List[str] = Field(..., min_length=1)
    org_structure_summary: str = Field(..., min_length=1)


# ============================================================================
# Section A (financial): Gross Receipts Answers
# ============================================================================

class GrossReceiptsAnswers(BaseModel):
    """Gross receipts for credit-year and three prior years."""
    year_0: float = Field(..., ge=0, description="Current tax year gross receipts")
    year_minus_1: float = Field(..., ge=0)
    year_minus_2: float = Field(..., ge=0)
    year_minus_3: float = Field(..., ge=0)


# ============================================================================
# Section C: Project Answers (one per R&D project)
# ============================================================================

class ProjectAnswers(BaseModel):
    """Per-project interview answers covering identification and 4-part test."""
    project_id: str = Field(..., pattern=r"^P\d{3,}$")
    project_name: str = Field(..., min_length=1)
    business_component: str = Field(..., min_length=1,
        description="The product, process, or software component being developed/improved")
    status: str = Field(default="Ongoing", description="Ongoing, Completed, or Suspended")

    # Technical summary fields (feed TechnicalSummary)
    objective: str = Field(..., min_length=1,
        description="What the project aimed to achieve")
    problem_statement: str = Field(..., min_length=1,
        description="The technical problem or gap being addressed")
    technical_uncertainty: str = Field(..., min_length=1,
        description="What was uncertain at the start of the project")
    hypotheses_tested: List[str] = Field(default_factory=list,
        description="Specific hypotheses or approaches that were evaluated")
    experimentation_process: List[str] = Field(default_factory=list,
        description="Steps taken to systematically test and iterate")
    alternatives_considered: List[str] = Field(default_factory=list,
        description="Alternative approaches that were evaluated")
    results_or_outcome: str = Field(default="",
        description="Final outcome or current state of the project")
    failures_or_iterations: str = Field(default="",
        description="Notable failures or pivots made during the project")

    # 4-part test fields (feed FourPartTest)
    permitted_purpose: str = Field(..., min_length=1,
        description="How this activity relates to a new/improved business component")
    technological_in_nature: str = Field(..., min_length=1,
        description="Which scientific/engineering disciplines were applied")
    elimination_of_uncertainty: str = Field(..., min_length=1,
        description="What capability/method/design uncertainty existed and how it was addressed")
    process_of_experimentation: str = Field(..., min_length=1,
        description="How the team systematically evaluated alternatives")

    # Evidence documentation
    jira_links: List[str] = Field(default_factory=list)
    github_links: List[str] = Field(default_factory=list)
    design_docs: List[str] = Field(default_factory=list)
    test_reports: List[str] = Field(default_factory=list)
    other_docs: List[str] = Field(default_factory=list)

    # Raw answer traceability: question_id → raw answer string
    source_answers: Optional[Dict[str, str]] = Field(default_factory=dict,
        description="Raw questionnaire answers keyed by question_id for traceability")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"Ongoing", "Completed", "Suspended"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}")
        return v


# ============================================================================
# Section D: Employee Time Allocation Answers
# ============================================================================

class EmployeeAnswers(BaseModel):
    """Per-employee wage and time-allocation answers."""
    employee_id: str = Field(..., pattern=r"^E\d{3,}$")
    employee_name: str = Field(..., min_length=1)
    job_title: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    w2_box_1_wages: float = Field(..., ge=0,
        description="W-2 Box 1 equivalent wages for the tax year")
    qualified_percentage: float = Field(..., ge=0.0, le=1.0,
        description="Fraction of total time spent on qualified research (0.0–1.0)")
    qualification_basis: str = Field(default="Interview",
        description="Interview, Time Tracking, Job Title, or Manager Estimate")
    project_allocation: Dict[str, float] = Field(...,
        description="Map of project_id → fraction of qualified time (values must sum to ~1.0)")
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(default_factory=dict,
        description="Raw questionnaire answers for this employee keyed by question_id")

    @field_validator("project_allocation")
    @classmethod
    def validate_allocation_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"project_allocation values must sum to approximately 1.0 (got {total:.4f})"
            )
        return v

    @field_validator("qualification_basis")
    @classmethod
    def validate_basis(cls, v: str) -> str:
        valid = {"Interview", "Time Tracking", "Job Title", "Manager Estimate"}
        if v not in valid:
            raise ValueError(f"qualification_basis must be one of {valid}")
        return v


# ============================================================================
# Section E: Contractor / Supplies / Cloud Answers
# ============================================================================

class ContractorAnswers(BaseModel):
    """Per-contractor eligibility and allocation answers."""
    vendor_id: str = Field(..., pattern=r"^V\d{3,}$")
    vendor_name: str = Field(..., min_length=1)
    description_of_work: str = Field(..., min_length=1)
    total_amount_paid: float = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    # Rights & risk (required to include contractor QRE)
    company_retains_rights: bool = Field(...,
        description="Does the company retain rights to the research?")
    company_bears_financial_risk: bool = Field(...,
        description="Does the company bear financial risk if the research fails?")
    supporting_contract_reference: str = Field(..., min_length=1,
        description="Contract or SOW reference supporting rights & risk assertion")
    project_allocation: Dict[str, float] = Field(...,
        description="Map of project_id → fraction (must sum to ~1.0)")
    notes: Optional[str] = None
    source_answers: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("project_allocation")
    @classmethod
    def validate_allocation_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"project_allocation values must sum to approximately 1.0 (got {total:.4f})"
            )
        return v


class SupplyAnswers(BaseModel):
    """Per-supply/materials eligibility and allocation answers."""
    supply_id: str = Field(..., pattern=r"^S\d{3,}$")
    description: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    invoice_reference: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    project_allocation: Dict[str, float] = Field(...)

    @field_validator("project_allocation")
    @classmethod
    def validate_allocation_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"project_allocation values must sum to approximately 1.0 (got {total:.4f})"
            )
        return v


class CloudComputingAnswers(BaseModel):
    """Per-cloud-service eligibility and allocation answers."""
    cloud_id: str = Field(..., pattern=r"^C\d{3,}$")
    provider: str = Field(..., min_length=1, description="AWS, Azure, GCP, etc.")
    service_category: str = Field(..., min_length=1, description="Compute, Storage, Database, etc.")
    billing_reference: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    qualified_percentage: float = Field(..., ge=0.0, le=1.0)
    project_allocation: Dict[str, float] = Field(...)

    @field_validator("project_allocation")
    @classmethod
    def validate_allocation_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"project_allocation values must sum to approximately 1.0 (got {total:.4f})"
            )
        return v


# ============================================================================
# Section F-0: Prior Year QRE Override (ASC method only)
# ============================================================================

class PriorYearQREAnswers(BaseModel):
    """
    Optional prior-year QRE override for the ASC credit method.

    Provide these if the client has exact QRE figures for the three prior years
    (e.g. from previously filed Form 6765).  When provided the pipeline will use
    them directly instead of deriving prior-year QREs from gross receipts.
    """
    enabled: bool = Field(
        default=True,
        description="Set False to disable the override and fall back to gross-receipts derivation",
    )
    year_minus_1_qre: float = Field(
        0.0, ge=0,
        description="Qualified Research Expenditures for credit_year − 1",
    )
    year_minus_2_qre: float = Field(
        0.0, ge=0,
        description="Qualified Research Expenditures for credit_year − 2",
    )
    year_minus_3_qre: float = Field(
        0.0, ge=0,
        description="Qualified Research Expenditures for credit_year − 3",
    )


# ============================================================================
# Section F: Methodology & Disclosures Answers
# ============================================================================

class DisclosuresAnswers(BaseModel):
    """Methodology, assumptions, and disclaimer answers."""
    methodology_summary: str = Field(..., min_length=1,
        description="How qualified percentages and cost categories were determined")
    limitations: List[str] = Field(..., min_length=1,
        description="Known limitations or assumptions in the study methodology")
    disclaimer_text: str = Field(..., min_length=1,
        description="Standard disclaimer for the report")


# ============================================================================
# Top-level Questionnaire Answers
# ============================================================================

class QuestionnaireAnswers(BaseModel):
    """
    Complete structured answers file.

    This is the top-level object for the answers.json input format.
    It covers all six sections (A–F) of the R&D tax credit questionnaire
    and maps 1:1 into RDStudyData via the questionnaire_to_study mapper.
    """
    study_metadata_answers: StudyMetadataAnswers
    company_background_answers: CompanyBackgroundAnswers
    gross_receipts_answers: GrossReceiptsAnswers
    projects: List[ProjectAnswers] = Field(..., min_length=1)
    employees: List[EmployeeAnswers] = Field(..., min_length=1)
    contractors: List[ContractorAnswers] = Field(default_factory=list)
    supplies: List[SupplyAnswers] = Field(default_factory=list)
    cloud_computing: List[CloudComputingAnswers] = Field(default_factory=list)
    prior_year_qres: Optional[PriorYearQREAnswers] = Field(
        default=None,
        description=(
            "Optional prior-year QRE figures for ASC method. "
            "Supply when exact figures from prior-year Form 6765 are available."
        ),
    )
    methodology_disclosures_answers: DisclosuresAnswers

    # Optional global question→answer map for full traceability
    interview_responses: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="All raw answers keyed by question_id across all sections"
    )

    @field_validator("projects")
    @classmethod
    def validate_unique_project_ids(cls, v: List[ProjectAnswers]) -> List[ProjectAnswers]:
        ids = [p.project_id for p in v]
        if len(ids) != len(set(ids)):
            raise ValueError("project_id values must be unique across all projects")
        return v

    @field_validator("employees")
    @classmethod
    def validate_unique_employee_ids(cls, v: List[EmployeeAnswers]) -> List[EmployeeAnswers]:
        ids = [e.employee_id for e in v]
        if len(ids) != len(set(ids)):
            raise ValueError("employee_id values must be unique")
        return v

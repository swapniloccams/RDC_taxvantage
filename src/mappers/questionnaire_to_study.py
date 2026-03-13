"""
Questionnaire → RDStudyData mapper.

Pure deterministic mapping — no LLM calls, no external I/O.
Every field is derived 1:1 from known question IDs in QuestionnaireAnswers.
"""

from decimal import Decimal
from datetime import date

from src.schema.questionnaire_schema import (
    QuestionnaireAnswers,
    ProjectAnswers,
    EmployeeAnswers,
    ContractorAnswers,
    SupplyAnswers,
    CloudComputingAnswers,
)
from src.schema.study_schema import (
    RDStudyData,
    StudyMetadata,
    PreparedFor,
    PreparedBy,
    TaxYear,
    CompanyBackground,
    GrossReceipts,
    RDProject,
    TechnicalSummary,
    FourPartTest,
    EvidenceLinks,
    Employee,
    ProjectAllocation,
    Contractor,
    RightsAndRisk,
    Supply,
    CloudComputing,
    DisclosuresAndAssumptions,
    EntityType,
    CreditMethod,
    ReturnType,
    ProjectStatus,
    QualificationBasis,
    ActivityType,
    BusinessFlags,
    QRECalculationRules,
    ASCCalculationInputs,
    QREPriorYearsOverride,
    OutputPreferences,
    InterviewMetadata,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _employee_allocations(allocation_map: dict) -> list[ProjectAllocation]:
    return [
        ProjectAllocation(project_id=pid, percent_of_employee_time=pct)
        for pid, pct in allocation_map.items()
    ]


def _vendor_allocations(allocation_map: dict) -> list[ProjectAllocation]:
    return [
        ProjectAllocation(project_id=pid, percent_of_vendor_work=pct)
        for pid, pct in allocation_map.items()
    ]


def _supply_allocations(allocation_map: dict) -> list[ProjectAllocation]:
    return [
        ProjectAllocation(project_id=pid, percent_of_supply_usage=pct)
        for pid, pct in allocation_map.items()
    ]


def _cloud_allocations(allocation_map: dict) -> list[ProjectAllocation]:
    return [
        ProjectAllocation(project_id=pid, percent_of_cloud_usage=pct)
        for pid, pct in allocation_map.items()
    ]


def _map_project(p: ProjectAnswers) -> RDProject:
    return RDProject(
        project_id=p.project_id,
        project_name=p.project_name,
        business_component=p.business_component,
        status=ProjectStatus(p.status),
        technical_summary=TechnicalSummary(
            objective=p.objective,
            problem_statement=p.problem_statement,
            technical_uncertainty=p.technical_uncertainty,
            hypotheses_tested=p.hypotheses_tested,
            experimentation_process=p.experimentation_process,
            alternatives_considered=p.alternatives_considered,
            results_or_outcome=p.results_or_outcome,
            failures_or_iterations=p.failures_or_iterations,
        ),
        four_part_test=FourPartTest(
            permitted_purpose=p.permitted_purpose,
            technological_in_nature=p.technological_in_nature,
            elimination_of_uncertainty=p.elimination_of_uncertainty,
            process_of_experimentation=p.process_of_experimentation,
        ),
        evidence_links=EvidenceLinks(
            jira_links=p.jira_links,
            github_links=p.github_links,
            design_docs=p.design_docs,
            test_reports=p.test_reports,
            other_supporting_docs=p.other_docs,
        ),
        source_answers=p.source_answers or {},
    )


def _map_employee(e: EmployeeAnswers) -> Employee:
    # Map activity_type safely — default to DIRECT_RESEARCH if not provided
    activity_raw = getattr(e, "activity_type", None) or "direct_research"
    try:
        activity = ActivityType(activity_raw)
    except ValueError:
        activity = ActivityType.DIRECT_RESEARCH

    return Employee(
        employee_id=e.employee_id,
        employee_name=e.employee_name,
        job_title=e.job_title,
        department=e.department,
        location=e.location,
        w2_box_1_wages=Decimal(str(e.w2_box_1_wages)),
        qualified_percentage=e.qualified_percentage,
        qualification_basis=QualificationBasis(e.qualification_basis),
        activity_type=activity,
        is_owner_officer=getattr(e, "is_owner_officer", False) or False,
        source_doc=getattr(e, "source_doc", None),
        rd_activities_description=getattr(e, "rd_activities_description", None),
        owner_officer_detail=getattr(e, "owner_officer_detail", None),
        project_allocation=_employee_allocations(e.project_allocation),
        notes=e.notes,
        source_answers=e.source_answers or {},
    )


def _map_contractor(c: ContractorAnswers) -> Contractor:
    return Contractor(
        vendor_id=c.vendor_id,
        vendor_name=c.vendor_name,
        description_of_work=c.description_of_work,
        total_amount_paid=Decimal(str(c.total_amount_paid)),
        qualified_percentage=c.qualified_percentage,
        us_based=getattr(c, "us_based", True),
        is_funded=getattr(c, "is_funded", False),
        contract_research_65_percent_rule_applies=True,
        rights_and_risk=RightsAndRisk(
            company_retains_rights=c.company_retains_rights,
            company_bears_financial_risk=c.company_bears_financial_risk,
            supporting_contract_reference=c.supporting_contract_reference,
        ),
        project_allocation=_vendor_allocations(c.project_allocation),
        notes=c.notes,
        source_answers=c.source_answers or {},
    )


def _map_supply(s: SupplyAnswers) -> Supply:
    return Supply(
        supply_id=s.supply_id,
        description=s.description,
        vendor=s.vendor,
        invoice_reference=s.invoice_reference,
        amount=Decimal(str(s.amount)),
        qualified_percentage=s.qualified_percentage,
        project_allocation=_supply_allocations(s.project_allocation),
    )


def _map_cloud(c: CloudComputingAnswers) -> CloudComputing:
    return CloudComputing(
        cloud_id=c.cloud_id,
        provider=c.provider,
        service_category=c.service_category,
        billing_reference=c.billing_reference,
        amount=Decimal(str(c.amount)),
        qualified_percentage=c.qualified_percentage,
        project_allocation=_cloud_allocations(c.project_allocation),
    )


# ---------------------------------------------------------------------------
# ASC helper
# ---------------------------------------------------------------------------

def _map_asc_inputs(answers: "QuestionnaireAnswers") -> ASCCalculationInputs:
    """Build ASCCalculationInputs, honouring optional prior-year QRE overrides."""
    if answers.prior_year_qres and answers.prior_year_qres.enabled:
        pq = answers.prior_year_qres
        override = QREPriorYearsOverride(
            enabled=True,
            year_minus_1_qre=Decimal(str(pq.year_minus_1_qre)),
            year_minus_2_qre=Decimal(str(pq.year_minus_2_qre)),
            year_minus_3_qre=Decimal(str(pq.year_minus_3_qre)),
        )
    else:
        override = QREPriorYearsOverride(enabled=False)
    return ASCCalculationInputs(qre_prior_years_override=override)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def map_questionnaire_to_study(answers: QuestionnaireAnswers) -> RDStudyData:
    """
    Convert QuestionnaireAnswers → RDStudyData.

    This function is the sole bridge between the questionnaire input path
    and the existing compute/narrative/render pipeline. It performs no
    calculations and generates no text — it only reshapes data.

    Args:
        answers: Validated QuestionnaireAnswers object.

    Returns:
        RDStudyData ready for ComputationAgent.
    """
    meta_a = answers.study_metadata_answers
    bg_a = answers.company_background_answers
    gr_a = answers.gross_receipts_answers
    disc_a = answers.methodology_disclosures_answers

    # --- study_metadata ---
    study_metadata = StudyMetadata(
        prepared_for=PreparedFor(
            legal_name=meta_a.client_legal_name,
            ein=meta_a.ein,
            entity_type=EntityType(meta_a.entity_type),
            address=meta_a.address,
            industry=meta_a.industry,
            website=meta_a.website,
            dba=getattr(meta_a, "dba", None),
            state_of_incorporation=getattr(meta_a, "state_of_incorporation", None),
            states_of_operation=getattr(meta_a, "states_of_operation", None) or [],
        ),
        prepared_by=PreparedBy(
            firm_name=meta_a.preparer_firm,
            preparer_name=meta_a.preparer_name,
            date_prepared=date.fromisoformat(meta_a.date_prepared),
        ),
        tax_year=TaxYear(
            year_label=meta_a.tax_year,
            start_date=date(int(meta_a.tax_year), 1, 1),
            end_date=date(int(meta_a.tax_year), 12, 31),
            return_type=ReturnType.ORIGINAL,
        ),
        credit_method=CreditMethod(meta_a.credit_method),
    )

    # --- company_background ---
    company_background = CompanyBackground(
        business_overview=bg_a.business_overview,
        products_and_services=bg_a.products_and_services,
        rd_departments=bg_a.rd_departments,
        locations=bg_a.locations,
        org_structure_summary=bg_a.org_structure_summary,
    )

    # --- gross_receipts ---
    gross_receipts = GrossReceipts(
        year_0=Decimal(str(gr_a.year_0)),
        year_minus_1=Decimal(str(gr_a.year_minus_1)),
        year_minus_2=Decimal(str(gr_a.year_minus_2)),
        year_minus_3=Decimal(str(gr_a.year_minus_3)),
    )

    # --- disclosures ---
    disclosures = DisclosuresAndAssumptions(
        methodology_summary=disc_a.methodology_summary,
        limitations=disc_a.limitations,
        disclaimer_text=disc_a.disclaimer_text,
    )

    # Build BusinessFlags from metadata answers
    prior_qre_raw = getattr(meta_a, "prior_qre_amounts", None) or {}
    prior_qre_decimal = {yr: Decimal(str(amt)) for yr, amt in prior_qre_raw.items()}

    business_flags = BusinessFlags(
        is_startup=getattr(meta_a, "is_startup", False) or False,
        payroll_tax_offset_eligible=getattr(meta_a, "payroll_tax_offset_eligible", False) or False,
        funded_by_third_party=meta_a.funded_by_third_party or False,
        wages_used_for_other_credits=meta_a.wages_used_for_other_credits or False,
        prior_credit_claimed=getattr(meta_a, "prior_credit_claimed", False) or False,
        prior_6765_years=getattr(meta_a, "prior_6765_years", None) or [],
        prior_qre_amounts=prior_qre_decimal,
        section_174_filed=getattr(meta_a, "section_174_filed", False) or False,
    )

    return RDStudyData(
        study_metadata=study_metadata,
        company_background=company_background,
        gross_receipts=gross_receipts,
        rd_projects=[_map_project(p) for p in answers.projects],
        employees=[_map_employee(e) for e in answers.employees],
        contractors=[_map_contractor(c) for c in answers.contractors],
        supplies=[_map_supply(s) for s in answers.supplies],
        cloud_computing=[_map_cloud(c) for c in answers.cloud_computing],
        qre_calculation_rules=QRECalculationRules(),
        asc_calculation_inputs=_map_asc_inputs(answers),
        business_flags=business_flags,
        output_preferences=OutputPreferences(),
        disclosures_and_assumptions=disclosures,
        golden_answer=getattr(answers, "golden_answer", None),
        interview_metadata=InterviewMetadata(
            status=getattr(answers, "interview_status", "complete") or "complete",
            interview_date=getattr(answers, "interview_date", None),
            interviewer=getattr(answers, "interviewer", None),
        ),
        additional_documentation=list(getattr(answers, "additional_documentation", None) or []),
        interview_responses=answers.interview_responses or {},
    )

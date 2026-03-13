"""
Run the R&D Tax Credit pipeline for NeuralAxis Technologies Inc.
Answers derived from Dummy_RD_Tax_Credit_Responses.docx.
"""
from pathlib import Path
from src.mappers.questionnaire_answers_builder import build_answers_json
from src.pipeline.coordinator import run_pipeline_from_dict

backend_answers = {
    # Study Metadata
    "client_legal_name": "NeuralAxis Technologies Inc.",
    "ein":               "83-1234567",
    "entity_type":       "C-Corp",
    "address":           "500 Tech Blvd, Suite 200, Austin, TX 78701",
    "industry":          "AI-driven Analytics Software / Enterprise Supply Chain",
    "website":           "https://www.neuralaxis.ai",
    "tax_year":          "2025",
    "credit_method":     "ASC",
    "preparer_firm":     "Occams Advisory",
    "preparer_name":     "Occams Advisory Team, CPA",
    "date_prepared":     "2025-12-01",

    # Q1
    "business_overview": (
        "NeuralAxis Technologies Inc. develops AI-driven analytics software for "
        "enterprise supply chain optimization. The company serves mid-market and "
        "enterprise customers across North America with predictive analytics and "
        "intelligent automation solutions."
    ),

    # Q2
    "products_and_services": [
        "Adaptive Demand Forecasting Engine",
        "Supply Chain Optimization Dashboard",
        "Real-Time Inventory Analytics API",
    ],

    # Q3
    "rd_departments": [
        "Software Engineering",
        "Data Science",
        "Cloud Infrastructure",
    ],

    # Q4
    "locations": ["Austin, TX", "Denver, CO"],

    # Q6
    "gross_receipts": {
        "year_0":        12500000,  # 2025
        "year_minus_1":   9400000,  # 2024
        "year_minus_2":   7100000,  # 2023
        "year_minus_3":   5200000,  # 2022
    },

    # Q7
    "funded_by_third_party": False,

    # Q8
    "wages_used_for_other_credits": False,

    # Q9–Q24: Projects
    "projects": [
        {
            "project_name":       "Adaptive Demand Forecasting Engine v2",
            "business_component": "Enhanced AI-based demand forecasting software platform",
            "objective": (
                "Reduce forecast error below 8% and improve scalability under "
                "volatile and high-variance datasets."
            ),
            "start_date":    "2025-01-15",
            "end_date":      "2025-11-30",
            "funding_type":  "Internal",
            "status":        "Completed",
            "technical_uncertainty": (
                "It was uncertain whether ensemble machine learning models would "
                "outperform legacy regression models. It was unknown which algorithm "
                "architecture would deliver stable, consistent performance under "
                "volatile seasonal demand patterns."
            ),
            "problem_statement": (
                "Standard industry forecasting models could not reliably handle the "
                "level of data variability present in client datasets, resulting in "
                "forecast errors that exceeded acceptable thresholds."
            ),
            "alternatives_considered": [
                "ARIMA time-series models",
                "Gradient boosting (XGBoost/LightGBM)",
                "LSTM-based neural networks",
            ],
            "experimentation_process": [
                "Built multiple prototype models in isolated sandbox environments.",
                "Conducted iterative benchmarking across historical and simulated datasets.",
                "Performed stress testing under high-variance and volatile demand scenarios.",
                "Compared ensemble configurations against individual model baselines.",
            ],
            "failures_or_iterations": (
                "Initial models overfit to training data, requiring a complete redesign "
                "of the feature engineering pipelines before acceptable generalization "
                "was achieved."
            ),
            "technological_in_nature": (
                "The project applied principles of computer science, statistics, and "
                "machine learning engineering. Software engineers and data scientists "
                "were the primary disciplines involved."
            ),
            "results_or_outcome": (
                "The final ensemble model achieved consistent performance improvement "
                "across high-variance demand categories, meeting the sub-8% forecast "
                "error target established at project inception."
            ),
            "permitted_purpose": (
                "The project developed the Adaptive Demand Forecasting Engine v2 as a "
                "new and improved business component. The objective was a measurable "
                "improvement in forecast accuracy below 8% error rate — a new "
                "functional capability not present in the prior version."
            ),
            "elimination_of_uncertainty": (
                "Technical uncertainty around algorithm architecture selection was "
                "resolved through systematic experimentation across three competing "
                "model families — ARIMA, gradient boosting, and LSTM-based networks — "
                "using controlled benchmarking on historical and simulated datasets."
            ),
            "process_of_experimentation": (
                "The team conducted iterative benchmarking and stress testing across "
                "historical and simulated datasets. Multiple prototype models were "
                "evaluated in sandbox environments, with each variant systematically "
                "compared before selecting the final ensemble approach."
            ),
            "hypotheses_tested": [
                "H1: Ensemble ML models will outperform standalone ARIMA baselines on high-variance demand categories.",
                "H2: LSTM-based architectures will generalize better than gradient boosting under volatile seasonal patterns.",
                "H3: Redesigned feature engineering pipelines will reduce overfitting observed in initial model variants.",
            ],
            "jira_links":   [],
            "github_links": [],
            "design_docs":  [],
            "test_reports": [],
            "other_docs":   [],
        }
    ],

    # Q25–Q30: Employees
    "employees": [
        {
            "employee_name":        "Samantha Lee",
            "job_title":            "Senior Software Engineer",
            "department":           "Software Engineering",
            "location":             "Austin, TX",
            "notes":                "Led backend system integration, algorithm design, and system refactoring.",
            "w2_box_1_wages":       165000,
            "qualified_percentage": 0.65,
            "qualification_basis":  "Interview",
            "project_allocation":   {"Adaptive Demand Forecasting Engine v2": 1.0},
        },
        {
            "employee_name":        "Daniel Ortega",
            "job_title":            "Data Scientist",
            "department":           "Data Science",
            "location":             "Denver, CO",
            "notes":                "Developed predictive models, conducted experiments, and performance benchmarking.",
            "w2_box_1_wages":       158000,
            "qualified_percentage": 0.70,
            "qualification_basis":  "Interview",
            "project_allocation":   {"Adaptive Demand Forecasting Engine v2": 1.0},
        },
    ],

    # Q32–Q36: Contractors
    "contractors": [
        {
            "vendor_name":                  "CloudOps AI Consulting LLC",
            "description_of_work":          "Scalability testing and infrastructure performance tuning for the forecasting engine.",
            "total_amount_paid":            85000,
            "qualified_percentage":         1.0,
            "company_retains_rights":       True,
            "company_bears_financial_risk": True,
            "supporting_contract_reference": "MSA-NA-2025-004",
            "project_allocation":           {"Adaptive Demand Forecasting Engine v2": 1.0},
        }
    ],

    # Q37: Supplies
    "supplies": [
        {
            "description":          "GPU Workstation for model training experiments",
            "vendor":               "Dell Technologies",
            "invoice_reference":    "See procurement records",
            "amount":               12500,
            "qualified_percentage": 1.0,
            "project_allocation":   {"Adaptive Demand Forecasting Engine v2": 1.0},
        }
    ],

    # Q38: Cloud Computing
    "cloud_computing": [
        {
            "provider":             "AWS",
            "service_category":     "Compute (EC2/SageMaker) — Model Training and Stress Testing",
            "billing_reference":    "AWS-NA-2025-12",
            "amount":               28000,
            "qualified_percentage": 1.0,
            "project_allocation":   {"Adaptive Demand Forecasting Engine v2": 1.0},
        }
    ],

    # Q46–Q50: Methodology & Compliance
    "methodology_summary": (
        "Employee qualified percentages were determined through structured interviews "
        "with project leads. All research activities were conducted internally in the "
        "United States and align with IRC Section 41 qualification criteria. Technical "
        "uncertainty and experimentation are substantiated through version history, "
        "benchmark comparisons, and test logs."
    ),
    "limitations": [
        "Qualified time percentages are based on structured interviews, not contemporaneous timesheets.",
        "GPU workstation cost used as reasonable estimate; final invoice should be confirmed with procurement.",
        "AWS cloud costs allocated 100% to the Forecasting Engine project based on infrastructure tagging.",
        "No activities were conducted outside the United States.",
        "No projects were fully reimbursed regardless of outcome.",
    ],
    "disclaimer_text": (
        "This study was prepared by Occams Advisory solely for the purpose of supporting "
        "NeuralAxis Technologies Inc. Federal R&D Tax Credit claim under IRC Section 41 "
        "for tax year 2025. This document should not be relied upon for any other purpose. "
        "Occams Advisory has relied upon information provided by the client and has not "
        "independently verified underlying financial records unless otherwise noted."
    ),

    # Prior year QREs — first-time claimant, no prior data
    "prior_year_qres": {
        "enabled":          False,
        "year_minus_1_qre": 0,
        "year_minus_2_qre": 0,
        "year_minus_3_qre": 0,
    },
}

if __name__ == "__main__":
    print("Building and validating answers...")
    answers_dict = build_answers_json(backend_answers)

    from src.schema.questionnaire_schema import QuestionnaireAnswers
    qa = QuestionnaireAnswers(**answers_dict)
    print(f"  Validation : PASS")
    print(f"  Projects   : {len(qa.projects)}")
    print(f"  Employees  : {len(qa.employees)}")
    print(f"  Contractors: {len(qa.contractors)}")
    print(f"  Supplies   : {len(qa.supplies)}")
    print(f"  Cloud      : {len(qa.cloud_computing)}")
    print()
    print("Starting pipeline...")

    result = run_pipeline_from_dict(
        answers_dict=answers_dict,
        output_dir=Path("output/neuralaxis"),
        logo_path=Path("assets/occams_logo.png"),
    )

    ctx = result.get("context", {})
    pdf = ctx.get("pdf_path") or "See output/neuralaxis/"
    print(f"\nPDF: {pdf}")

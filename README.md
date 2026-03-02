# R&D Tax Credit Report Generator

Production-grade Python application that transforms CSV data into professionally formatted PDF reports for Federal R&D Tax Credit studies. Uses OpenAI Agents SDK for multi-agent orchestration with specialized agents for data validation, computation, narrative generation, compliance checking, and PDF rendering.

## Features

- **Multi-Agent Architecture**: 5 specialized agents with clear handoffs
  - CSVIngestionAgent: Validates CSV schema and normalizes data
  - ComputationAgent: Deterministic calculations (no LLM math)
  - NarrativeAgent: Generates executive summary and project narratives
  - ComplianceAgent: Validates completeness and flags weak claims
  - RenderAgent: Professional PDF generation with ReportLab

- **Safety-First Design**:
  - LLM never performs currency calculations
  - Placeholders for missing data instead of hallucinations
  - Strict JSON schema validation between agents
  - Decimal precision for all financial calculations

- **Production-Quality PDF**:
  - Occams logo on every page (bottom-left)
  - Page numbering "X of Y" (bottom-right)
  - Professional styling and table formatting
  - Consistent branding throughout

## Installation

```bash
# Clone or navigate to project directory
cd taxvantage_ai

# Install dependencies
make install

# Or manually:
pip install -e ".[dev]"
```

## Configuration

Set your OpenAI API key:

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Override default model
OPENAI_MODEL=gpt-4-turbo-preview
```

## CSV Format

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `client_legal_name` | string | Legal name of client company |
| `tax_year` | integer | Tax year (e.g., 2023) |
| `project_id` | string | Unique project identifier |
| `project_name` | string | Project name |
| `project_status` | string | "Qualified" or "Non-qualified" |
| `qualified_wages` | decimal | QRE from wages |

### Optional Columns

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `qualified_contractors` | decimal | 0 | QRE from contractors |
| `qualified_supplies` | decimal | 0 | QRE from supplies |
| `qualified_cloud` | decimal | 0 | QRE from cloud computing |
| `federal_credit` | decimal | calculated | Federal credit (auto-calculated if missing) |
| `project_description_facts` | string | "" | Semicolon-separated bullets |
| `uncertainty_facts` | string | "" | Semicolon-separated bullets |
| `experimentation_facts` | string | "" | Semicolon-separated bullets |
| `technology_facts` | string | "" | Semicolon-separated bullets |
| `employees` | string | "" | Semicolon-separated employee names |
| `man_hours` | integer | null | Total man hours |

### Example CSV

See `examples/sample.csv` for a complete example with 3 projects.

**Semicolon-separated lists** are used for facts and employees:
```
"Developed ML algorithms; Implemented caching; Optimized queries"
"John Smith; Sarah Chen; Michael Rodriguez"
```

## Usage

### Basic Usage

```bash
python -m src --input examples/sample.csv --out ./output
```

### With Custom Logo

```bash
python -m src --input data.csv --out ./reports --logo path/to/logo.png
```

### Using Makefile

```bash
# Run with sample data
make run

# Run tests
make test

# Format code
make format

# Clean output
make clean
```

## Output Files

After successful execution, you'll find:

```
output/
├── Acme_Technology_Corp_2023_RND_Report.pdf  # Main PDF report
└── artifacts/
    ├── report.json                            # Final JSON data
    └── trace.json                             # Agent execution trace
```

## Architecture

### Agent Flow

```
CSVIngestionAgent
    ↓
ComputationAgent
    ↓
NarrativeAgent
    ↓
ComplianceAgent ──→ (if fails) ──→ NarrativeAgent
    ↓                                    ↑
RenderAgent                              │
                                         └─ (handoff for revision)
```

### Safety Guarantees

1. **No Hallucinated Facts**: NarrativeAgent only synthesizes provided facts
2. **No LLM Math**: ComputationAgent uses Python Decimal for all calculations
3. **Missing Data Handling**: Placeholders like `[Needs analyst input - insufficient data provided]` instead of invented content
4. **Compliance Validation**: ComplianceAgent flags weak language and missing sections

## Report Structure

Generated PDF includes:

1. **Title Page**
   - Report title: "Federal Research and Development Tax Credit Study"
   - Client company name
   - Tax year(s)

2. **Executive Summary**
   - Overview paragraph
   - "Information Collected" bullet list
   - a) Summary of R&D Expenditures (table)
   - b) Summary of R&D Projects (table)

3. **Overview of Statutory Authority**
   - Section 41 boilerplate
   - Four-part test explanation

4. **R&D Tax Credit Analysis by Project**
   - For each project:
     - i) Basic Project Data
     - ii) Project Description
     - iii) New or Improved Business Component
     - iv) Elimination of Uncertainty
     - v) Process of Experimentation
     - vi) Technological in Nature

## Development

### Running Tests

```bash
# Run all tests with coverage
make test

# Or manually
pytest tests/ -v --cov=src --cov-report=term-missing
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint
```

### Project Structure

```
src/
├── agents/          # 5 specialized agents
├── compute/         # Deterministic calculations
├── pipeline/        # Orchestration and tracing
├── render/          # PDF generation with ReportLab
├── schema/          # Pydantic models and CSV validation
└── utils/           # Utility functions
```

## Troubleshooting

### OpenAI API Key Not Set

```
Error: OpenAI API key not found
```

**Solution**: Set `OPENAI_API_KEY` in `.env` file or environment

### CSV Validation Errors

```
CSVValidationError: Missing required columns: project_name
```

**Solution**: Ensure your CSV has all required columns (see CSV Format section)

### Compliance Warnings

```
[WARNING] Project 'X': Project Description contains placeholder - needs analyst input
```

**Solution**: This is expected when CSV facts are incomplete. Provide more detailed facts in the semicolon-separated columns, or manually edit the generated narratives.

### Logo Not Appearing

**Solution**: 
1. Ensure logo file exists at `assets/occams_logo.png`
2. Or specify custom logo: `--logo path/to/logo.png`
3. Logo should be PNG format with transparent background

## Safety Notes

⚠️ **CRITICAL SAFETY FEATURES**

1. **No Hallucinated Facts**: The NarrativeAgent is instructed to ONLY use facts provided in the CSV. If facts are missing, it outputs placeholders.

2. **No LLM Math**: All currency calculations are performed by the ComputationAgent using Python's `Decimal` type. The LLM never sees or performs arithmetic.

3. **Placeholders for Missing Data**: When required information is missing, the system outputs `[Needs analyst input - insufficient data provided]` rather than inventing content.

4. **Compliance Checking**: The ComplianceAgent validates that:
   - All required sections are present
   - No placeholder text in final output (flags as warning)
   - Weak language is flagged for review
   - Narratives reference specific facts

## License

Proprietary - Occams Technology Corp

## Support

For issues or questions, contact your system administrator.

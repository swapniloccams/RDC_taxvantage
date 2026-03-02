# Quick Start Guide

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

## Configuration

```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Or create .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

## Run with Sample Data

```bash
python -m src --input examples/sample.csv --out ./output
```

## Run Tests

```bash
pytest tests/ -v
```

## CSV Format Quick Reference

### Required Columns
- `client_legal_name` - Company name
- `tax_year` - Year (e.g., 2023)
- `project_id` - Unique ID
- `project_name` - Project name
- `project_status` - "Qualified" or "Non-qualified"
- `qualified_wages` - Dollar amount

### Optional Columns (for better narratives)
- `project_description_facts` - Semicolon-separated bullets
- `uncertainty_facts` - Semicolon-separated bullets
- `experimentation_facts` - Semicolon-separated bullets
- `technology_facts` - Semicolon-separated bullets
- `employees` - Semicolon-separated names
- `qualified_contractors`, `qualified_supplies`, `qualified_cloud` - Dollar amounts

### Example Row

```csv
Acme Corp,2023,P001,ML Pipeline,Qualified,100000,25000,5000,10000,"Built ML model; Implemented API; Deployed to production","Uncertain which algorithm; Unknown scaling approach","Tested 5 models; A/B tested; Iterated design","Applied ML principles; Used statistical methods","John Doe; Jane Smith",1200
```

## Output Files

- `{client}_{year}_RND_Report.pdf` - Main PDF report
- `artifacts/report.json` - Structured data
- `artifacts/trace.json` - Agent execution log

## Troubleshooting

**Missing API Key:**
```bash
export OPENAI_API_KEY="sk-..."
```

**CSV Validation Error:**
Check that all required columns are present and `project_status` is "Qualified" or "Non-qualified"

**Placeholder Text in Output:**
Add more detailed facts in the semicolon-separated columns

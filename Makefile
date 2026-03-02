.PHONY: install test clean run format lint

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

clean:
	rm -rf output/ artifacts/ __pycache__ .pytest_cache .coverage
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	python -m src --input examples/sample.csv --out ./output

format:
	black src/ tests/
	ruff check --fix src/ tests/

lint:
	ruff check src/ tests/
	black --check src/ tests/

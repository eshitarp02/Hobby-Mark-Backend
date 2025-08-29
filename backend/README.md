# Testing & Coverage

## Setup
cd backend
pip install -r requirements-dev.txt

## Run tests (fails if coverage < 85%)
pytest

## Optional: HTML coverage
pytest --cov-report=html
# open backend/htmlcov/index.html

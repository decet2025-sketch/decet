# Certificate Management System - Makefile
# Provides easy commands for development and testing

.PHONY: help install test lint format clean setup-dev

# Default target
help:
	@echo "Certificate Management System - Available Commands"
	@echo "=================================================="
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install development dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run linting (flake8, black, isort)"
	@echo "  make format           - Format code (black, isort)"
	@echo "  make clean            - Clean up temporary files"
	@echo "  make setup-dev        - Setup development environment"
	@echo ""
	@echo "Examples:"
	@echo "  make test"
	@echo "  make format"
	@echo "  make setup-dev"

# Development commands
install:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt
	pip install appwrite pydantic requests jinja2 pyppeteer beautifulsoup4 pyjwt email-validator

test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short

lint:
	@echo "Running linting..."
	flake8 shared/ functions/ tests/ --max-line-length=100 --ignore=E203,W503
	black --check shared/ functions/ tests/
	isort --check-only shared/ functions/ tests/

format:
	@echo "Formatting code..."
	black shared/ functions/ tests/
	isort shared/ functions/ tests/

clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Setup commands
setup-dev:
	@echo "Setting up development environment..."
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements-dev.txt
	. venv/bin/activate && pip install appwrite pydantic requests jinja2 pyppeteer beautifulsoup4 pyjwt email-validator
	@echo "Development environment ready!"
	@echo "Activate with: source venv/bin/activate"

# CI/CD commands
ci-test:
	@echo "Running CI tests..."
	pytest tests/ --cov=shared --cov=functions --cov-report=xml --cov-report=html

ci-lint:
	@echo "Running CI linting..."
	flake8 shared/ functions/ tests/ --max-line-length=100 --ignore=E203,W503
	black --check shared/ functions/ tests/
	isort --check-only shared/ functions/ tests/
	mypy shared/ functions/ --ignore-missing-imports
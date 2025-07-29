# Makefile for Backend Testing & Quality

.PHONY: help test test-unit test-integration test-contract test-performance test-security test-all
.PHONY: coverage coverage-report mutation-test load-test clean install lint format typecheck
.PHONY: security-scan benchmark quality-check ci

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip3
PYTEST := pytest
COVERAGE := coverage
LOCUST := locust
K6 := k6
MUTMUT := mutmut

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${GREEN}%-20s${NC} %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install test dependencies
	@echo "${YELLOW}Installing test dependencies...${NC}"
	$(PIP) install -r requirements-test.txt
	@echo "${GREEN}✓ Dependencies installed${NC}"

# Testing targets
test: ## Run all tests
	@echo "${YELLOW}Running all tests...${NC}"
	$(PYTEST)

test-unit: ## Run unit tests only
	@echo "${YELLOW}Running unit tests...${NC}"
	$(PYTEST) -m unit tests/unit/

test-integration: ## Run integration tests
	@echo "${YELLOW}Running integration tests...${NC}"
	$(PYTEST) -m integration tests/integration/

test-contract: ## Run contract tests
	@echo "${YELLOW}Running contract tests...${NC}"
	$(PYTEST) -m contract tests/contract/

test-performance: ## Run performance tests
	@echo "${YELLOW}Running performance benchmarks...${NC}"
	$(PYTEST) -m performance tests/performance/ --benchmark-only

test-security: ## Run security tests
	@echo "${YELLOW}Running security tests...${NC}"
	$(PYTEST) -m security tests/security/

test-fast: ## Run fast tests (exclude slow tests)
	@echo "${YELLOW}Running fast tests...${NC}"
	$(PYTEST) -m "not slow"

# Coverage targets
coverage: ## Run tests with coverage
	@echo "${YELLOW}Running tests with coverage...${NC}"
	$(COVERAGE) run -m pytest
	$(COVERAGE) report

coverage-report: coverage ## Generate HTML coverage report
	@echo "${YELLOW}Generating coverage report...${NC}"
	$(COVERAGE) html
	@echo "${GREEN}✓ Coverage report generated in htmlcov/${NC}"

coverage-check: ## Check if coverage meets minimum threshold
	@echo "${YELLOW}Checking coverage threshold...${NC}"
	$(COVERAGE) report --fail-under=80

# Quality checks
lint: ## Run linting (flake8, pylint)
	@echo "${YELLOW}Running linters...${NC}"
	flake8 backend/ --max-line-length=120 --exclude=migrations,venv
	pylint backend/ --disable=C0114,C0115,C0116 || true
	@echo "${GREEN}✓ Linting complete${NC}"

format: ## Format code with black and isort
	@echo "${YELLOW}Formatting code...${NC}"
	black backend/ tests/
	isort backend/ tests/
	@echo "${GREEN}✓ Code formatted${NC}"

typecheck: ## Run type checking with mypy
	@echo "${YELLOW}Running type checks...${NC}"
	mypy backend/ --ignore-missing-imports
	@echo "${GREEN}✓ Type checking complete${NC}"

# Advanced testing
mutation-test: ## Run mutation testing
	@echo "${YELLOW}Running mutation tests...${NC}"
	cd backend && $(PYTHON) tests/mutation/test_mutations.py
	@echo "${GREEN}✓ Mutation testing complete${NC}"

load-test: ## Run load tests with Locust
	@echo "${YELLOW}Starting load test...${NC}"
	@echo "Visit http://localhost:8089 to control the test"
	$(LOCUST) -f backend/tests/load/locustfile.py --host=http://localhost:8000

load-test-k6: ## Run load tests with k6
	@echo "${YELLOW}Running k6 load test...${NC}"
	$(K6) run backend/tests/load/k6_load_test.js

benchmark: ## Run performance benchmarks
	@echo "${YELLOW}Running benchmarks...${NC}"
	$(PYTEST) tests/performance/ --benchmark-only --benchmark-autosave

benchmark-compare: ## Compare benchmark results
	@echo "${YELLOW}Comparing benchmark results...${NC}"
	$(PYTEST) tests/performance/ --benchmark-compare --benchmark-only

# Security
security-scan: ## Run security scanning
	@echo "${YELLOW}Running security scans...${NC}"
	bandit -r backend/ -f json -o security-report.json
	safety check --json
	pip-audit
	@echo "${GREEN}✓ Security scan complete${NC}"

# Quality and CI
quality-check: lint typecheck test-fast coverage-check ## Run all quality checks
	@echo "${GREEN}✓ All quality checks passed${NC}"

test-all: test-unit test-integration test-contract test-security ## Run all test suites
	@echo "${GREEN}✓ All tests completed${NC}"

ci: install quality-check test-all coverage-report ## Run full CI pipeline
	@echo "${GREEN}✓ CI pipeline complete${NC}"

# Reporting
report: ## Generate test report
	@echo "${YELLOW}Generating test report...${NC}"
	$(PYTEST) --html=test-report.html --self-contained-html
	@echo "${GREEN}✓ Test report generated${NC}"

# Cleanup
clean: ## Clean test artifacts
	@echo "${YELLOW}Cleaning test artifacts...${NC}"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".coverage" -delete
	find . -type d -name "htmlcov" -delete
	find . -type d -name ".mutmut-cache" -delete
	find . -type f -name ".coverage*" -delete
	rm -f test-report.html security-report.json
	@echo "${GREEN}✓ Cleanup complete${NC}"

# Docker testing
docker-test: ## Run tests in Docker
	@echo "${YELLOW}Running tests in Docker...${NC}"
	docker-compose -f docker-compose.test.yml up --abort-on-container-exit
	docker-compose -f docker-compose.test.yml down

# Watch mode
watch: ## Run tests in watch mode
	@echo "${YELLOW}Running tests in watch mode...${NC}"
	$(PYTEST) -f

# Test database
test-db-create: ## Create test database
	@echo "${YELLOW}Creating test database...${NC}"
	createdb agency_test
	@echo "${GREEN}✓ Test database created${NC}"

test-db-drop: ## Drop test database
	@echo "${YELLOW}Dropping test database...${NC}"
	dropdb agency_test --if-exists
	@echo "${GREEN}✓ Test database dropped${NC}"

test-db-reset: test-db-drop test-db-create ## Reset test database
	@echo "${GREEN}✓ Test database reset${NC}"

# Requirements
requirements-test: ## Generate test requirements file
	@echo "${YELLOW}Generating test requirements...${NC}"
	@echo "# Test requirements" > requirements-test.txt
	@echo "pytest>=7.0.0" >> requirements-test.txt
	@echo "pytest-asyncio>=0.21.0" >> requirements-test.txt
	@echo "pytest-cov>=4.0.0" >> requirements-test.txt
	@echo "pytest-mock>=3.10.0" >> requirements-test.txt
	@echo "pytest-benchmark>=4.0.0" >> requirements-test.txt
	@echo "pytest-html>=3.1.0" >> requirements-test.txt
	@echo "pytest-xdist>=3.0.0" >> requirements-test.txt
	@echo "pytest-timeout>=2.1.0" >> requirements-test.txt
	@echo "httpx>=0.24.0" >> requirements-test.txt
	@echo "faker>=18.0.0" >> requirements-test.txt
	@echo "factory-boy>=3.2.0" >> requirements-test.txt
	@echo "coverage>=7.0.0" >> requirements-test.txt
	@echo "black>=23.0.0" >> requirements-test.txt
	@echo "isort>=5.12.0" >> requirements-test.txt
	@echo "flake8>=6.0.0" >> requirements-test.txt
	@echo "pylint>=2.17.0" >> requirements-test.txt
	@echo "mypy>=1.0.0" >> requirements-test.txt
	@echo "bandit>=1.7.0" >> requirements-test.txt
	@echo "safety>=2.3.0" >> requirements-test.txt
	@echo "pip-audit>=2.5.0" >> requirements-test.txt
	@echo "mutmut>=2.4.0" >> requirements-test.txt
	@echo "locust>=2.15.0" >> requirements-test.txt
	@echo "memory-profiler>=0.61.0" >> requirements-test.txt
	@echo "line-profiler>=4.0.0" >> requirements-test.txt
	@echo "fakeredis[lua]>=2.10.0" >> requirements-test.txt
	@echo "pact-python>=2.0.0" >> requirements-test.txt
	@echo "${GREEN}✓ Test requirements generated${NC}"
.PHONY: help install format lint test validate build check

help:
	@echo "install   Install the project and development dependencies"
	@echo "format    Format Python source"
	@echo "lint      Run static checks"
	@echo "test      Run the test suite"
	@echo "validate  Validate public benchmark tasks"
	@echo "build     Build source and wheel distributions"
	@echo "check     Run lint, tests, validation, and build"

install:
	python -m pip install -e ".[dev]"

format:
	python -m ruff format .
	python -m ruff check --fix .

lint:
	python -m ruff check .
	python -m ruff format --check .

test:
	python -m pytest -q

validate:
	python -m agent_capability_benchmark validate tasks/public

build:
	python -m build

check: lint test validate build

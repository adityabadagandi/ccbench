.PHONY: install test lint format typecheck benchmark clean

install:
	pip install -e ".[dev,baselines]"

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	mypy compiler

benchmark:
	@echo "Full benchmark runner is not yet implemented."
	@echo "Run 'make test' for the current passing contract tests."

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

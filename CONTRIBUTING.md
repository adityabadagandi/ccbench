# Contributing to CCBench & Context Compiler

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/ansh/ccbench.git
cd ccbench
pip install -e ".[dev]"
```

## Code Quality

```bash
# Linting
ruff check .
ruff format .

# Type checking
mypy compiler

# Tests
pytest
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Code of Conduct

Be respectful and constructive in all interactions.

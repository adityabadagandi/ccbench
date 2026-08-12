"""Case loader utilities.

Loads benchmark cases from JSON files and validates against schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.schema.models import Case


def load_case(path: str | Path) -> Case:
    """Load and validate a single case JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Case.model_validate(data)


def load_cases(directory: str | Path) -> list[Case]:
    """Load and validate all case JSON files in a directory."""
    directory = Path(directory)
    cases: list[Case] = []
    for path in sorted(directory.glob("*.json")):
        cases.append(load_case(path))
    return cases

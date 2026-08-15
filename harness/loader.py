"""Case loader utilities.

Loads benchmark cases from JSON files and validates against schema 0.2.

The dev split holds full cases; the test split holds redacted ones with the
supervision withheld, so the two are loaded through different models. Loading
a redacted test case as a full :class:`Case` is a bug, not a convenience, and
will raise.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.schema.models import Case, PublicCase


def load_case(path: str | Path) -> Case:
    """Load and validate a single full case (dev split, or a private answer key)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Case.model_validate(data)


def load_cases(directory: str | Path) -> list[Case]:
    """Load and validate every full case JSON file in a directory."""
    directory = Path(directory)
    return [load_case(path) for path in sorted(directory.glob("*.json"))]


def load_public_case(path: str | Path) -> PublicCase:
    """Load a redacted test case — documents and question only."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return PublicCase.model_validate(data)


def load_public_cases(directory: str | Path) -> list[PublicCase]:
    """Load every redacted test case in a directory."""
    directory = Path(directory)
    return [load_public_case(path) for path in sorted(directory.glob("*.json"))]


def load_test_gold(path: str | Path) -> dict[str, Case]:
    """Load the private answer key for the test split.

    Args:
        path: Path to ``test_gold.private.json``.

    Returns:
        Mapping of case_id to the full validated case.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {cid: Case.model_validate(data) for cid, data in raw.items()}

"""Tests for the evaluation harness."""

from __future__ import annotations

from pathlib import Path

from harness.loader import load_case, load_cases

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_CASES_DIR = REPO_ROOT / "benchmark" / "cases" / "dev"


def test_load_single_dev_case() -> None:
    """Loader must parse and validate the first dev case."""
    case_paths = sorted(DEV_CASES_DIR.glob("*.json"))
    assert case_paths, f"No dev cases found in {DEV_CASES_DIR}"
    case = load_case(case_paths[0])
    assert case.case_id.startswith("ccbench-")
    assert case.documents.invoice is not None
    assert case.documents.erp_order is not None


def test_load_all_dev_cases() -> None:
    """Loader must parse every dev case without validation errors."""
    cases = load_cases(DEV_CASES_DIR)
    assert len(cases) >= 1
    case_ids = {c.case_id for c in cases}
    assert len(case_ids) == len(cases), "Duplicate case IDs in dev split"

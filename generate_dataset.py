"""Generate the CCBench dataset (schema 0.2).

Cases are written to ``benchmark/cases/``, which is where the loader, harness
and baselines look for them. The 0.1 pipeline wrote to a loose folder outside
the package that nothing ever read.

Run from the repository root::

    python generate_dataset.py                 # 200 cases, then validate
    python generate_dataset.py --cases 40      # a quick smoke batch
    python generate_dataset.py --no-validate

Deterministic from the master seed; the same seed reproduces the corpus
byte-for-byte. Requires Python 3.12+.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from benchmark.validate import validate_dataset  # noqa: E402
from generators.assembler import generate_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the CCBench dataset")
    parser.add_argument("--output", default=str(REPO / "benchmark" / "cases"))
    parser.add_argument("--cases", type=int, default=200)
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    out = Path(args.output)
    print(f"Generating {args.cases} cases (seed {args.seed}) -> {out}")
    manifest = generate_dataset(
        output_dir=out,
        n_cases=args.cases,
        dev_fraction=args.dev_fraction,
        seed=args.seed,
    )
    print(f"  dev:  {manifest['metadata']['dev_cases']}")
    print(f"  test: {manifest['metadata']['test_cases']} (gold withheld to test_gold.private.json)")

    if args.no_validate:
        return 0

    print("\nValidating...")
    report = validate_dataset(out)
    for key in sorted(report.stats):
        print(f"  {key:28s} {report.stats[key]}")
    if report.ok:
        print(f"\nOK — {report.checked} cases, 0 invariant violations.")
        return 0
    print(f"\nFAILED — {len(report.errors)} violation(s):")
    for err in report.errors[:40]:
        print(f"  - {err}")
    if len(report.errors) > 40:
        print(f"  ... and {len(report.errors) - 40} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

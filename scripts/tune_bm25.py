"""Dev-split grid search for the BM25 baseline — BENCHMARK_SPEC §6.

Selection objective is **Context Completeness**, not the benchmark score.

That needs justifying, because it looks like tuning on a convenient metric.
Compliance Leakage would be trivially minimised by retrieving nothing, so
optimising a baseline against it produces a deliberately crippled opponent —
the opposite of a fair comparison. Answer Correctness and Faithfulness are not
measurable without an answerer and a frozen judge rubric, neither of which
exists yet. Completeness is the one metric that measures what BM25 is actually
for: finding the right evidence inside a token budget.

The leak rate is reported alongside every configuration so the choice is
informed rather than blind, but it is not optimised.

Usage::

    python -m scripts.tune_bm25
    python -m scripts.tune_bm25 --budget 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import product
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from baselines.bm25 import BM25Retriever  # noqa: E402
from harness.loader import load_cases  # noqa: E402
from harness.runner import run  # noqa: E402

K1_GRID = (0.9, 1.2, 1.5, 2.0)
B_GRID = (0.3, 0.5, 0.75, 0.9)
# Extended past 20 deliberately: at k1=0.9/b=0.3 completeness was still rising
# at the old grid edge, and a baseline capped by an arbitrary boundary is an
# unfair baseline. It saturates at 24, where the token budget binds instead.
TOP_K_GRID = (6, 8, 10, 12, 16, 20, 24, 28)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grid search BM25 on the dev split")
    parser.add_argument("--split", default=str(REPO / "benchmark" / "cases" / "dev"))
    parser.add_argument("--budget", type=int, default=4000)
    parser.add_argument("--out", default=str(REPO / "results" / "bm25_grid_dev.json"))
    args = parser.parse_args(argv)

    cases = load_cases(args.split)
    print(
        f"Grid search over {len(K1_GRID) * len(B_GRID) * len(TOP_K_GRID)} configs, "
        f"{len(cases)} dev cases, budget {args.budget}\n"
    )

    rows: list[dict] = []
    for k1, b in product(K1_GRID, B_GRID):
        # One index per (k1, b); top_k only changes how deep we read it.
        for top_k in TOP_K_GRID:
            method = BM25Retriever(k1=k1, b=b, top_k=top_k)
            split, scores = run(method, cases, budget=args.budget)
            rows.append(
                {
                    "k1": k1,
                    "b": b,
                    "top_k": top_k,
                    "completeness": round(split.completeness, 4),
                    "leak_clean_rate": round(split.leak_clean_rate, 4),
                    "eu_leak_clean_rate": round(split.eu_leak_clean_rate, 4),
                    "mean_tokens": round(sum(s.tokens for s in scores) / len(scores), 1),
                    "over_budget": split.over_budget,
                }
            )
            print(
                f"  k1={k1:<4} b={b:<5} top_k={top_k:<3} "
                f"completeness={rows[-1]['completeness']:.4f} "
                f"leak_clean={rows[-1]['leak_clean_rate']:.3f} "
                f"tokens={rows[-1]['mean_tokens']:.0f}"
            )

    rows.sort(key=lambda r: (-r["completeness"], r["mean_tokens"]))
    best = rows[0]
    print(
        "\nBest configuration by Context Completeness "
        "(ties broken by fewer tokens — cheaper context for equal recall):"
    )
    print(f"  k1={best['k1']}  b={best['b']}  top_k={best['top_k']}")
    print(f"  completeness  {best['completeness']:.4f}")
    print(f"  leak clean    {best['leak_clean_rate']:.3f} (EU {best['eu_leak_clean_rate']:.3f})")
    print(f"  mean tokens   {best['mean_tokens']:.0f} / {args.budget}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"budget": args.budget, "best": best, "grid": rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

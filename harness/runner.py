"""Evaluation runner.

Runs a retrieval method over a split and reports the four metrics.

The harness calls ``retrieve(...)`` identically on every method — BM25, dense,
hybrid, GraphRAG, the compiler. No special-casing, no home-field advantage.

Retrieval-only by default: Context Completeness and Compliance Leakage need no
LLM, so a method can be scored today. Pass an ``answerer`` to additionally
score Answer Correctness and Faithfulness.

Usage::

    python -m harness.runner --method oracle
    python -m harness.runner --method dump-everything --budget 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from benchmark.schema.models import Case, CaseCorpus, ContextBundle, Retriever
from harness.loader import load_cases
from harness.metrics import CaseScore, Judge, SplitScore, aggregate, score_case

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = REPO_ROOT / "benchmark" / "cases" / "dev"
DEFAULT_BUDGET = 4000

Answerer = Callable[[Case, ContextBundle], str]


def run(
    method: Retriever,
    cases: list[Case],
    budget: int = DEFAULT_BUDGET,
    answerer: Answerer | None = None,
    judge: Judge | None = None,
) -> tuple[SplitScore, list[CaseScore]]:
    """Run one method over a list of cases.

    Args:
        method: Anything satisfying the Retriever protocol.
        cases: Full cases, with gold supervision.
        budget: Token budget every method must fit inside.
        answerer: Optional answer generator; without it, correctness and
            faithfulness are left unmeasured rather than scored zero.
        judge: Optional fallback judge for Answer Correctness.

    Returns:
        ``(split_score, per_case_scores)``.
    """
    corpus = CaseCorpus(cases=cases)
    scores: list[CaseScore] = []

    for case in cases:
        bundle = method.retrieve(
            question=case.question,
            corpus=corpus,
            budget=budget,
            jurisdiction=case.jurisdiction.value,
        )
        answer = answerer(case, bundle) if answerer else None
        scores.append(score_case(case, bundle, answer=answer, judge=judge))

    return aggregate(method.name, scores), scores


def format_report(split: SplitScore, scores: list[CaseScore]) -> str:
    """Render a human-readable result table."""
    lines = [
        "",
        f"  method                {split.method}",
        f"  cases                 {split.n}",
        f"  token budget          {scores[0].budget if scores else 0}",
        "",
        "  METRIC                                        VALUE",
        "  " + "-" * 54,
        f"  Context Completeness (§4.2)                   {split.completeness:.3f}",
        f"  Compliance Leakage — clean rate (§4.4)        {split.leak_clean_rate:.3f}",
        f"    of which EU cases                           {split.eu_leak_clean_rate:.3f}",
    ]
    if split.correctness is None:
        lines += [
            "  Answer Correctness (§4.1)                     not measured (no answerer)",
            "  Faithfulness (§4.3)                           not measured (no answerer)",
            "  BENCHMARK SCORE (§8)                          not measured (no answerer)",
        ]
    else:
        lines += [
            f"  Answer Correctness (§4.1)                     {split.correctness:.3f}",
            f"  Faithfulness (§4.3)                           {split.faithfulness:.3f}",
            f"  BENCHMARK SCORE (§8)                          {split.solved:.3f}",
        ]
    lines += ["", f"  over budget           {split.over_budget} case(s)", ""]

    lines += ["  Completeness by bucket", "  " + "-" * 54]
    for bucket, value in split.by_bucket.items():
        lines.append(f"    {bucket:<22} {value:.3f}")
    lines += ["", "  Completeness by gold label", "  " + "-" * 54]
    for label, value in split.by_label.items():
        lines.append(f"    {label:<22} {value:.3f}")

    leaking = [s for s in scores if not s.leak_clean]
    if leaking:
        lines += [
            "",
            f"  LEAKED on {len(leaking)} case(s). First three:",
            "  " + "-" * 54,
        ]
        for s in leaking[:3]:
            lines.append(f"    {s.case_id} [{s.jurisdiction}] leaked {s.leaked}")

    incomplete = [s for s in scores if s.completeness < 1.0]
    if incomplete:
        lines += [
            "",
            f"  Incomplete on {len(incomplete)} case(s). First three:",
            "  " + "-" * 54,
        ]
        for s in incomplete[:3]:
            lines.append(f"    {s.case_id} missing {s.missing_facts} (score {s.completeness:.2f})")

    return "\n".join(lines)


def _build_method(name: str, cases: list[Case]) -> Retriever:
    if name == "oracle":
        from baselines.calibration import OracleRetriever

        return OracleRetriever(cases)
    if name == "dump-everything":
        from baselines.calibration import DumpEverythingRetriever

        return DumpEverythingRetriever()
    if name == "bm25":
        from baselines.bm25 import BM25Retriever

        return BM25Retriever()
    raise SystemExit(
        f"unknown method {name!r}. Available: oracle, dump-everything (instruments); bm25 (method)."
    )


def gold_answerer(case: Case, bundle: ContextBundle) -> str:
    """An 'answerer' that simply emits the gold answer.

    Paired with the oracle retriever this gives the **reference upper bound**:
    perfect retrieval and a perfect answer. Whatever it fails to score is not
    a modelling problem — it is a gap no amount of retrieval or generation
    quality can close.
    """
    return case.gold_answer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a retrieval method over a CCBench split")
    parser.add_argument("--method", default="oracle")
    parser.add_argument("--split", default=str(DEFAULT_SPLIT))
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--out", default=None, help="Write per-case JSON results here")
    parser.add_argument(
        "--gold-answers",
        action="store_true",
        help="Emit the gold answer instead of generating one. With --method oracle this is "
        "the reference upper bound.",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.split)
    if not cases:
        raise SystemExit(f"no cases in {args.split}")

    method = _build_method(args.method, cases)
    split, scores = run(
        method,
        cases,
        budget=args.budget,
        answerer=gold_answerer if args.gold_answers else None,
    )
    print(format_report(split, scores))

    if args.out:
        payload = {
            "summary": split.as_dict(),
            "cases": [
                {
                    "case_id": s.case_id,
                    "bucket": s.bucket,
                    "gold_label": s.gold_label,
                    "jurisdiction": s.jurisdiction,
                    "completeness": s.completeness,
                    "missing_facts": s.missing_facts,
                    "leak_clean": s.leak_clean,
                    "leaked": s.leaked,
                    "tokens": s.tokens,
                }
                for s in scores
            ],
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {out}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

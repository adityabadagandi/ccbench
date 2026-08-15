"""Per-case and per-split scoring — spec v0.2 §8.

A case is **solved** only when all four criteria hold at once:

    correctness == 1  and  completeness >= 0.80
    and faithfulness >= 0.90  and  leakage == clean

The benchmark score is the fraction of cases solved. Reporting the four
component averages separately is useful for diagnosis, but the headline number
is the conjunction — a method that retrieves everything and leaks on every EU
case has not solved anything.

When no answerer is supplied, correctness and faithfulness are *unmeasured*
rather than zero, and ``solved`` is left as None. Reporting 0.0 for a metric
you did not run would silently understate every retrieval-only result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from benchmark.schema.models import Case, ContextBundle

from .completeness import context_completeness
from .correctness import Judge, answer_correctness
from .faithfulness import faithfulness
from .leakage import compliance_leakage, gstin_masking_respected

COMPLETENESS_THRESHOLD = 0.80
FAITHFULNESS_THRESHOLD = 0.90


@dataclass
class CaseScore:
    """Scores for a single case."""

    case_id: str
    bucket: str
    gold_label: str
    jurisdiction: str

    completeness: float
    missing_facts: list[str]
    leak_clean: bool
    leaked: list[str]

    correctness: int | None = None
    correctness_method: str | None = None
    faithful: float | None = None
    uncited: list[str] = field(default_factory=list)
    gstin_masked: bool | None = None

    tokens: int = 0
    budget: int = 0

    @property
    def scored_answer(self) -> bool:
        return self.correctness is not None

    @property
    def solved(self) -> bool | None:
        """All four criteria, or None when the answer was not scored."""
        if not self.scored_answer:
            return None
        return bool(
            self.correctness == 1
            and self.completeness >= COMPLETENESS_THRESHOLD
            and (self.faithful or 0.0) >= FAITHFULNESS_THRESHOLD
            and self.leak_clean
        )

    @property
    def over_budget(self) -> bool:
        return self.tokens > self.budget


def score_case(
    case: Case,
    bundle: ContextBundle,
    answer: str | None = None,
    judge: Judge | None = None,
) -> CaseScore:
    """Score one case against one retrieval result."""
    completeness, missing = context_completeness(case, bundle)
    clean, leaked = compliance_leakage(case, bundle, answer)

    score = CaseScore(
        case_id=case.case_id,
        bucket=case.bucket.value,
        gold_label=case.gold_label.value,
        jurisdiction=case.jurisdiction.value,
        completeness=completeness,
        missing_facts=missing,
        leak_clean=clean,
        leaked=leaked,
        tokens=bundle.tokens,
        budget=bundle.budget,
    )

    if answer is not None:
        correctness, method = answer_correctness(case, answer, bundle, judge)
        faithful, uncited = faithfulness(answer, bundle)
        score.correctness = correctness
        score.correctness_method = method
        score.faithful = faithful
        score.uncited = uncited
        score.gstin_masked = gstin_masking_respected(case, answer)

    return score


@dataclass
class SplitScore:
    """Aggregate over a split."""

    method: str
    n: int
    completeness: float
    leak_clean_rate: float
    eu_leak_clean_rate: float
    over_budget: int
    correctness: float | None
    faithfulness: float | None
    solved: float | None
    by_bucket: dict[str, float]
    by_label: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "n": self.n,
            "context_completeness": round(self.completeness, 4),
            "leak_clean_rate": round(self.leak_clean_rate, 4),
            "eu_leak_clean_rate": round(self.eu_leak_clean_rate, 4),
            "over_budget": self.over_budget,
            "answer_correctness": None if self.correctness is None else round(self.correctness, 4),
            "faithfulness": None if self.faithfulness is None else round(self.faithfulness, 4),
            "benchmark_score": None if self.solved is None else round(self.solved, 4),
            "completeness_by_bucket": {k: round(v, 4) for k, v in self.by_bucket.items()},
            "completeness_by_label": {k: round(v, 4) for k, v in self.by_label.items()},
        }


def aggregate(method: str, scores: list[CaseScore]) -> SplitScore:
    """Roll per-case scores into a split-level result."""
    if not scores:
        raise ValueError("no scores to aggregate")

    eu = [s for s in scores if s.jurisdiction == "EU"]
    answered = [s for s in scores if s.scored_answer]

    by_bucket: dict[str, float] = {}
    for bucket in sorted({s.bucket for s in scores}):
        by_bucket[bucket] = mean(s.completeness for s in scores if s.bucket == bucket)
    by_label: dict[str, float] = {}
    for label in sorted({s.gold_label for s in scores}):
        by_label[label] = mean(s.completeness for s in scores if s.gold_label == label)

    return SplitScore(
        method=method,
        n=len(scores),
        completeness=mean(s.completeness for s in scores),
        leak_clean_rate=mean(s.leak_clean for s in scores),
        eu_leak_clean_rate=mean(s.leak_clean for s in eu) if eu else 1.0,
        over_budget=sum(s.over_budget for s in scores),
        correctness=mean(s.correctness or 0 for s in answered) if answered else None,
        faithfulness=mean(s.faithful or 0.0 for s in answered) if answered else None,
        solved=mean(bool(s.solved) for s in answered) if answered else None,
        by_bucket=by_bucket,
        by_label=by_label,
    )

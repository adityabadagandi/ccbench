"""Answer Correctness — spec v0.2 §4.1.

Exact match first, LLM judge as the fallback.

The judge is an interface, not an implementation, and deliberately so. The
rubric must be **frozen before any baseline is run** or scores are not
comparable across methods — and a rubric written before you have seen where
exact match actually fails is a guess. Run the dev split with
:class:`ExactMatchJudge`, read the cases it fails, then write the rubric
against real failures and drop it in behind this interface.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from benchmark.schema.models import Case, ContextBundle

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[.,;:!?'\"()\[\]]")


def normalise(text: str) -> str:
    """Normalise for exact match: unicode form, case, punctuation, whitespace.

    NFKC matters here — Devanagari answers and the Rupee sign both have
    multiple valid encodings, and a system should not be penalised for picking
    a different one.
    """
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


class Judge(Protocol):
    """Scores an answer against the gold answer. Must return 0 or 1."""

    name: str

    def score(self, case: Case, answer: str, bundle: ContextBundle) -> int:
        """Return 1 if the answer is correct, else 0."""
        ...


class ExactMatchJudge:
    """The no-LLM fallback: normalised string equality, nothing more.

    This under-reports badly — a correct answer phrased differently scores 0 —
    so treat its number as a floor, not an estimate. Its real job is to
    surface the cases a real rubric has to adjudicate.
    """

    name = "exact-match"

    def score(self, case: Case, answer: str, bundle: ContextBundle) -> int:
        return int(normalise(answer) == normalise(case.gold_answer))


def answer_correctness(
    case: Case,
    answer: str,
    bundle: ContextBundle,
    judge: Judge | None = None,
) -> tuple[int, str]:
    """Score one answer.

    Args:
        case: The full case, carrying the gold answer.
        answer: What the system produced.
        bundle: The context it produced the answer from.
        judge: Fallback used when exact match fails. Defaults to none, in
            which case a non-exact answer scores 0.

    Returns:
        ``(score, method)`` where method records which path decided it.
    """
    if normalise(answer) == normalise(case.gold_answer):
        return 1, "exact"
    if judge is None:
        return 0, "exact-failed-no-judge"
    return judge.score(case, answer, bundle), judge.name

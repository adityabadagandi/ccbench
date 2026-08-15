"""Metric computation for CCBench (spec v0.2 §4).

Four metrics, deliberately split by what they need:

======================  ==========================  =====================
Metric                  Measured on                 Needs an answer?
======================  ==========================  =====================
Context Completeness    the retrieved context       no
Compliance Leakage      the emitted context/answer  no
Answer Correctness      the answer                  yes
Faithfulness            the answer + context        yes
======================  ==========================  =====================

The first two run against a retriever alone, so you can score a method today
without an LLM in the loop. The second two need an answering step; the runner
takes an optional ``answerer`` and reports them only when one is supplied.

Completeness and leakage are measured on *different objects* — retrieved
context versus emitted answer. A ``gold_fact`` may legitimately point at a
denied field (to answer "may I disclose the PAN?" you must first retrieve the
invoice and see one is there), while ``must_not_appear`` constrains what comes
out. A compliant system scores 1.0 on both. See BENCHMARK_SPEC §4.4.
"""

from .completeness import context_completeness
from .correctness import ExactMatchJudge, Judge, answer_correctness, normalise
from .faithfulness import faithfulness
from .leakage import compliance_leakage
from .score import CaseScore, SplitScore, aggregate, score_case

__all__ = [
    "CaseScore",
    "ExactMatchJudge",
    "Judge",
    "SplitScore",
    "aggregate",
    "answer_correctness",
    "compliance_leakage",
    "context_completeness",
    "faithfulness",
    "normalise",
    "score_case",
]

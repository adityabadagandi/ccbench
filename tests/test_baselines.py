"""Tests for retrieval baselines.

These lock the frozen configuration in ``docs/BASELINES.md`` to the code. If a
change to tokenisation, node rendering or the corpus moves BM25's dev score,
these fail — which is the point: the documented number and the reproducible
number must not drift apart silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baselines.bm25 import BM25Retriever, tokenize
from benchmark.schema.models import CaseCorpus
from harness.loader import load_cases
from harness.runner import run

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_DIR = REPO_ROOT / "benchmark" / "cases" / "dev"

pytest.importorskip("rank_bm25", reason="BM25 baseline requires the [baselines] extra")


@pytest.fixture(scope="module")
def dev_cases():
    cases = load_cases(DEV_DIR)
    assert cases, "no dev cases — run generate_dataset.py"
    return cases


@pytest.fixture(scope="module")
def bm25_run(dev_cases):
    return run(BM25Retriever(), dev_cases)


# --- tokenisation -----------------------------------------------------------


def test_compound_identifiers_are_kept_whole_and_split() -> None:
    """Ids carry the signal; leaving them opaque would cripple the baseline."""
    tokens = tokenize("invoice TAX/2026-27/69448 for CONS-RAS-PAT-260513-69448")
    assert "tax/2026-27/69448" in tokens
    assert "69448" in tokens
    assert "2026" in tokens
    assert "cons-ras-pat-260513-69448" in tokens


def test_devanagari_survives_tokenisation() -> None:
    tokens = tokenize("क्या खेप पहुँच गई?")
    assert any("ऀ" <= ch <= "ॿ" for tok in tokens for ch in tok)


# --- frozen configuration ---------------------------------------------------


def test_frozen_config_matches_documented_values() -> None:
    """docs/BASELINES.md records these; the defaults must agree."""
    method = BM25Retriever()
    assert (method.k1, method.b, method.top_k) == (0.9, 0.3, 24)


def test_bm25_reproduces_its_documented_dev_score(bm25_run) -> None:
    split, _ = bm25_run
    assert split.completeness == pytest.approx(0.965, abs=0.005)


def test_tuning_beats_library_defaults(dev_cases) -> None:
    """The 21-point gap is the reason the grid search is not optional."""
    tuned, _ = run(BM25Retriever(), dev_cases)
    stock, _ = run(BM25Retriever(k1=1.5, b=0.75, top_k=12), dev_cases)
    assert tuned.completeness > stock.completeness + 0.15


# --- behaviour --------------------------------------------------------------


def test_bm25_never_exceeds_the_budget(bm25_run) -> None:
    split, scores = bm25_run
    assert split.over_budget == 0
    assert all(s.tokens <= s.budget for s in scores)


def test_bm25_searches_the_whole_corpus_not_one_case(dev_cases) -> None:
    """It is given only the question — locating the case is part of the task."""
    method = BM25Retriever()
    method._ensure_index(CaseCorpus(cases=dev_cases))
    assert len(method._nodes) > 10 * len(dev_cases)


def test_bm25_returns_nodes_in_timeline_order(dev_cases) -> None:
    """Rank picks what is included; chronology decides how it reads."""
    corpus = CaseCorpus(cases=dev_cases)
    bundle = BM25Retriever().retrieve(dev_cases[0].question, corpus, 4000, "IN")
    stamps = [n.ts or "" for n in bundle.nodes]
    assert stamps == sorted(stamps)


def test_bm25_still_leaks_on_eu_cases(bm25_run) -> None:
    """A retrieval method cannot fix an emission problem, however well tuned."""
    split, _ = bm25_run
    assert split.eu_leak_clean_rate < 0.2


def test_cross_lingual_is_the_weakest_bucket(bm25_run) -> None:
    """The benchmark's discriminating bucket must actually discriminate."""
    split, _ = bm25_run
    worst = min(split.by_bucket, key=lambda k: split.by_bucket[k])
    assert worst == "cross-lingual"
    assert split.by_bucket["cross-lingual"] < 0.95


def test_devanagari_questions_are_where_lexical_retrieval_fails(dev_cases, bm25_run) -> None:
    """Latin-script Hinglish survives BM25; Devanagari does not.

    Guarded loosely because n=5 on dev — this asserts the mechanism exists,
    not that the exact figure is stable.
    """
    _, scores = bm25_run
    by_lang: dict[str, list[float]] = {}
    for score, case in zip(scores, dev_cases, strict=True):
        by_lang.setdefault(case.question_lang.value, []).append(score.completeness)

    devanagari = by_lang.get("hi", [])
    latin = by_lang.get("en", []) + by_lang.get("hi-en", [])
    assert devanagari, "dev split has no Devanagari questions"
    assert sum(devanagari) / len(devanagari) < sum(latin) / len(latin)

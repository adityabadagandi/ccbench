"""Tests for the evaluation harness metrics.

The calibration tests at the top are the important ones: they assert the
*known* scores of the two instrument retrievers. If they fail, the metrics are
wrong, not the method — which is the whole reason those retrievers exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baselines.calibration import DumpEverythingRetriever, OracleRetriever
from benchmark.schema.models import CaseCorpus, ContextBundle, Node
from benchmark.text import citations_in, split_claims
from harness.loader import load_cases
from harness.metrics import (
    ExactMatchJudge,
    answer_correctness,
    compliance_leakage,
    context_completeness,
    faithfulness,
    normalise,
    score_case,
)
from harness.metrics.completeness import required_node_id
from harness.nodes import case_to_nodes, estimate_tokens, render_context
from harness.runner import run

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_DIR = REPO_ROOT / "benchmark" / "cases" / "dev"


@pytest.fixture(scope="module")
def dev_cases():
    cases = load_cases(DEV_DIR)
    assert cases, "no dev cases — run generate_dataset.py"
    return cases


@pytest.fixture(scope="module")
def eu_case(dev_cases):
    return next(c for c in dev_cases if c.jurisdiction.value == "EU")


@pytest.fixture(scope="module")
def in_case(dev_cases):
    return next(c for c in dev_cases if c.jurisdiction.value == "IN")


# --- calibration ------------------------------------------------------------


def test_oracle_achieves_perfect_completeness(dev_cases) -> None:
    """The upper bound must actually be reachable, or the metric is broken."""
    split, scores = run(OracleRetriever(dev_cases), dev_cases)
    assert split.completeness == 1.0, [s.case_id for s in scores if s.completeness < 1.0]


def test_dump_everything_also_achieves_perfect_completeness(dev_cases) -> None:
    """Completeness alone is trivially maxed — that is why §8 is a conjunction."""
    split, _ = run(DumpEverythingRetriever(), dev_cases)
    assert split.completeness == 1.0


def test_reference_upper_bound_is_perfect_except_for_leakage(dev_cases) -> None:
    """Perfect retrieval plus the gold answer must max three of the four metrics.

    This is the test that says the benchmark is *solvable by its own answer
    key*. Before gold answers carried citations, faithfulness here was 0.000
    and no case could ever be solved — the bar in §8 was unreachable by
    anything, including the reference itself.

    Leakage is the deliberate exception: it stays broken until
    ``compiler/policies.py`` exists, and the size of that gap is the result
    the project is built to report.
    """
    split, _ = run(OracleRetriever(dev_cases), dev_cases, answerer=lambda c, b: c.gold_answer)
    assert split.completeness == 1.0
    assert split.correctness == 1.0
    assert split.faithfulness == 1.0
    assert split.eu_leak_clean_rate < 1.0


def test_every_gold_answer_claim_carries_a_backed_citation(dev_cases) -> None:
    """Each claim cites a node that a gold fact would actually retrieve."""
    for case in dev_cases:
        supported = {f.node_id for f in case.gold_facts}
        for claim in split_claims(case.gold_answer):
            cited = citations_in(claim)
            assert cited, f"{case.case_id}: uncited claim {claim[:60]!r}"
            assert cited & supported, f"{case.case_id}: {sorted(cited)} not backed by a gold fact"


def test_naive_retrieval_leaks_on_every_eu_case(dev_cases) -> None:
    """Perfect retrieval with no emission policy is not compliant.

    This is the gap ``compiler/policies.py`` exists to close. When it is
    implemented, a policy-aware retriever should hold completeness at 1.0 and
    take this rate to 1.0 as well.
    """
    split, scores = run(DumpEverythingRetriever(), dev_cases)
    assert split.eu_leak_clean_rate == 0.0
    eu = [s for s in scores if s.jurisdiction == "EU"]
    assert eu and all(not s.leak_clean for s in eu)


def test_in_cases_never_leak(dev_cases) -> None:
    """IN denies nothing, so IN cases pass trivially. That is correct."""
    _, scores = run(DumpEverythingRetriever(), dev_cases)
    assert all(s.leak_clean for s in scores if s.jurisdiction == "IN")


# --- completeness -----------------------------------------------------------


def test_dropping_the_cited_message_costs_recall(dev_cases) -> None:
    """A system that discards the non-English message must lose points."""
    case = next(
        c
        for c in dev_cases
        if c.bucket.value == "cross-lingual" and any(f.evidence for f in c.gold_facts)
    )
    cited = {f.evidence.ref_id for f in case.gold_facts if f.evidence}
    kept = [n for n in case_to_nodes(case) if n.id not in cited]
    bundle = _bundle_of(kept, case.jurisdiction.value)

    score, missing = context_completeness(case, bundle)
    assert score < 1.0
    assert missing


def test_empty_context_scores_zero(eu_case) -> None:
    score, missing = context_completeness(eu_case, _bundle_of([], "EU"))
    assert score == 0.0
    assert len(missing) == len(eu_case.gold_facts)


def test_every_gold_fact_maps_to_a_real_node(dev_cases) -> None:
    for case in dev_cases:
        ids = {n.id for n in case_to_nodes(case)}
        for fact in case.gold_facts:
            assert required_node_id(fact) in ids, f"{case.case_id}/{fact.fact_id}"


def test_retrieving_a_node_without_the_value_is_not_support(dev_cases) -> None:
    """Presence of the node is necessary but not sufficient."""
    case = next(c for c in dev_cases if c.bucket.value == "lookup")
    fact = case.gold_facts[0]
    nodes = case_to_nodes(case)
    for node in nodes:
        if node.id == required_node_id(fact):
            node.fields = {"invoice_no": "wiped"}
    score, missing = context_completeness(case, _bundle_of(nodes, case.jurisdiction.value))
    assert fact.fact_id in missing or score < 1.0


# --- leakage ----------------------------------------------------------------


def test_leakage_is_detected_by_substring(eu_case) -> None:
    pan = eu_case.documents.invoice.seller.pan
    bundle = _bundle_of([], "EU")
    bundle.llm_context = f"The seller's PAN is {pan}."
    clean, leaked = compliance_leakage(eu_case, bundle)
    assert not clean
    assert pan in leaked


def test_leakage_checks_the_answer_too(eu_case) -> None:
    pan = eu_case.documents.invoice.seller.pan
    clean, leaked = compliance_leakage(eu_case, _bundle_of([], "EU"), answer=f"PAN is {pan}")
    assert not clean and pan in leaked


def test_clean_output_does_not_leak(eu_case) -> None:
    clean, leaked = compliance_leakage(
        eu_case, _bundle_of([], "EU"), answer="Withheld under policy."
    )
    assert clean and not leaked


def test_in_case_has_nothing_to_leak(in_case) -> None:
    assert in_case.must_not_appear == []
    bundle = _bundle_of(case_to_nodes(in_case), "IN")
    clean, _ = compliance_leakage(in_case, bundle)
    assert clean


def test_gold_answers_are_themselves_leak_free(dev_cases) -> None:
    """The reference answer must pass the metric it defines."""
    for case in dev_cases:
        clean, leaked = compliance_leakage(
            case, _bundle_of([], case.jurisdiction.value), case.gold_answer
        )
        assert clean, f"{case.case_id} gold answer leaks {leaked}"


# --- faithfulness -----------------------------------------------------------


def test_cited_claims_are_faithful() -> None:
    bundle = _bundle_of([_node("INV")], "IN")
    score, uncited = faithfulness("The total is Rs. 100 [INV]. It was issued in May [INV].", bundle)
    assert score == 1.0 and not uncited


def test_uncited_claim_is_unfaithful() -> None:
    bundle = _bundle_of([_node("INV")], "IN")
    score, uncited = faithfulness("The total is Rs. 100 [INV]. The driver was late.", bundle)
    assert score == 0.5 and len(uncited) == 1


def test_fabricated_citation_does_not_count() -> None:
    """Citing a node that was never retrieved is worse than not citing."""
    bundle = _bundle_of([_node("INV")], "IN")
    score, _ = faithfulness("The permit says Rs. 90 [EWB].", bundle)
    assert score == 0.0


def test_devanagari_sentences_are_segmented() -> None:
    bundle = _bundle_of([_node("M-003")], "IN")
    score, _ = faithfulness("डिलीवरी हो गई [M-003]। POD साइन हुआ [M-003]।", bundle)
    assert score == 1.0


# --- correctness ------------------------------------------------------------


def test_exact_match_ignores_case_punctuation_and_spacing() -> None:
    assert normalise("Rs. 1,000.00 paid!") == normalise("rs  1,000 00 paid")


def test_correct_answer_scores_one(in_case) -> None:
    score, method = answer_correctness(in_case, in_case.gold_answer, _bundle_of([], "IN"))
    assert score == 1 and method == "exact"


def test_wrong_answer_without_a_judge_scores_zero(in_case) -> None:
    score, method = answer_correctness(in_case, "Something else entirely.", _bundle_of([], "IN"))
    assert score == 0 and method == "exact-failed-no-judge"


def test_judge_is_consulted_when_exact_match_fails(in_case) -> None:
    class AlwaysYes:
        name = "always-yes"

        def score(self, case, answer, bundle) -> int:
            return 1

    score, method = answer_correctness(in_case, "Paraphrased.", _bundle_of([], "IN"), AlwaysYes())
    assert score == 1 and method == "always-yes"


def test_exact_match_judge_is_a_floor(in_case) -> None:
    judge = ExactMatchJudge()
    assert judge.score(in_case, in_case.gold_answer, _bundle_of([], "IN")) == 1
    assert judge.score(in_case, "A correct paraphrase.", _bundle_of([], "IN")) == 0


# --- scoring ----------------------------------------------------------------


def test_unanswered_case_leaves_solved_unmeasured(in_case) -> None:
    score = score_case(in_case, _bundle_of(case_to_nodes(in_case), "IN"))
    assert score.solved is None
    assert score.correctness is None


def test_solved_requires_all_four_criteria(in_case) -> None:
    bundle = _bundle_of(case_to_nodes(in_case), "IN")
    cited = " ".join(f"[{n.id}]" for n in bundle.nodes[:1])
    score = score_case(in_case, bundle, answer=f"{in_case.gold_answer} {cited}")
    # Correct content but appended citations break exact match, so not solved.
    assert score.completeness == 1.0
    assert score.leak_clean
    assert score.solved is False


def test_node_and_context_helpers(in_case) -> None:
    nodes = case_to_nodes(in_case)
    assert {n.id for n in nodes} >= {"INV", "ERP", "TIMELINE"}
    context = render_context(nodes)
    assert "[INV]" in context
    assert estimate_tokens(context) > 0


# --- helpers ----------------------------------------------------------------


def _node(node_id: str) -> Node:
    return Node(
        id=node_id,
        type="Invoice",
        consignment_ref="CONS-1",
        fields={},
        confidence=1.0,
        ts=None,
        provenance="test",
    )


def _bundle_of(nodes: list[Node], jurisdiction: str) -> ContextBundle:
    context = render_context(nodes)
    return ContextBundle(
        query="q",
        nodes=nodes,
        llm_context=context,
        citations=[n.id for n in nodes],
        tokens=estimate_tokens(context),
        budget=4000,
        jurisdiction=jurisdiction,
    )


def test_corpus_type_accepts_cases(dev_cases) -> None:
    assert len(CaseCorpus(cases=dev_cases).cases) == len(dev_cases)

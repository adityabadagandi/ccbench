"""Calibration retrievers — not baselines, instruments.

These two exist to test the *metrics*. Their scores are known in advance, so
when they come out wrong the harness is broken, not the method. Run them
before trusting any real number.

``OracleRetriever``
    Retrieves exactly the nodes the gold facts name, and nothing else.
    Expected: **completeness 1.0 everywhere.** Anything less means the
    completeness metric or the node mapping is wrong.

    Expected: **leaks on EU cases**, because perfect retrieval with no policy
    applied puts the PAN straight into the context. This is not a defect in
    the oracle — it is the gap the emission policy exists to close, made
    visible as a number. When ``compiler/policies.py`` is implemented, a
    policy-aware retriever should hold completeness at 1.0 while taking the EU
    leak rate to zero. That delta is the contribution.

``DumpEverythingRetriever``
    Returns every node in the case, ignoring the question.
    Expected: **completeness 1.0** (it retrieved everything, so it retrieved
    the right things) and **leaks on every EU case**. It is the reminder that
    completeness alone is not a result — it is trivially maxed by a method
    with no precision and no discipline, which is why the benchmark score is
    a conjunction of all four criteria.
"""

from __future__ import annotations

from benchmark.schema.models import Case, CaseCorpus, ContextBundle, Node
from harness.metrics.completeness import required_node_id
from harness.nodes import case_to_nodes, estimate_tokens, render_context


def _bundle(question: str, nodes: list[Node], budget: int, jurisdiction: str) -> ContextBundle:
    """Pack nodes into a bundle, in timeline order, trimmed to budget."""
    ordered = sorted(nodes, key=lambda n: (n.ts or "", n.id))
    kept: list[Node] = []
    for node in ordered:
        candidate = kept + [node]
        if estimate_tokens(render_context(candidate)) > budget and kept:
            break
        kept.append(node)

    context = render_context(kept)
    return ContextBundle(
        query=question,
        nodes=kept,
        llm_context=context,
        citations=[n.id for n in kept],
        tokens=estimate_tokens(context),
        budget=budget,
        jurisdiction=jurisdiction,
    )


class OracleRetriever:
    """Upper bound on retrieval: exactly the gold nodes, nothing else.

    Requires the gold facts, so it is only meaningful on dev or against the
    private test key. It is not a method and must never be reported as one.
    """

    name = "oracle"

    def __init__(self, cases: list[Case]) -> None:
        self._by_id = {case.case_id: case for case in cases}

    def retrieve(
        self,
        question: str,
        corpus: CaseCorpus,
        budget: int,
        jurisdiction: str = "IN",
    ) -> ContextBundle:
        case = self._match(question, corpus)
        wanted = {required_node_id(fact) for fact in case.gold_facts}
        nodes = [n for n in case_to_nodes(case) if n.id in wanted]
        return _bundle(question, nodes, budget, jurisdiction)

    def _match(self, question: str, corpus: CaseCorpus) -> Case:
        for case in corpus.cases:
            if case.question == question:
                return self._by_id[case.case_id]
        raise KeyError(f"no case in corpus for question {question!r}")


class DumpEverythingRetriever:
    """Lower bound on precision: every node, question ignored."""

    name = "dump-everything"

    def retrieve(
        self,
        question: str,
        corpus: CaseCorpus,
        budget: int,
        jurisdiction: str = "IN",
    ) -> ContextBundle:
        for case in corpus.cases:
            if case.question == question:
                return _bundle(question, case_to_nodes(case), budget, jurisdiction)
        raise KeyError(f"no case in corpus for question {question!r}")

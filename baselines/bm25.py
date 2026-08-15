"""BM25 sparse retrieval baseline.

Classic Okapi BM25 over `rank_bm25`, searching **the entire corpus** — every
node of every case, roughly 1,200 nodes for the dev split. That is the honest
task: the method is given a question and must locate the right consignment
among a hundred, then the right handful of nodes within it. The calibration
retrievers in ``baselines/calibration.py`` are handed the correct case and are
therefore instruments, not peers; do not put them in the same results table
without saying so.

Tokenisation is the one place where a lazy choice would cripple this baseline
unfairly, so it is deliberate. Business identifiers carry the signal here —
``TAX/2026-27/69448``, ``CONS-RAS-PAT-260513-69448``, ``448381164242`` — and a
plain ``.split()`` would leave them as single opaque tokens that only ever
match verbatim. Every identifier is therefore emitted **both** whole and split
into its parts, so a question naming a consignment still matches an invoice
that shares only its numeric tail. Per the fairness commitment in
``docs/INTERVIEW_DEFENSE.md`` Q2, this baseline is built to win, not to lose
politely.

``k1`` and ``b`` are exposed for the dev-split grid search required by
BENCHMARK_SPEC §6. Freeze the chosen values in ``docs/BASELINES.md``.
"""

from __future__ import annotations

import re

from benchmark.schema.models import Case, CaseCorpus, ContextBundle, Node, PublicCase
from harness.nodes import case_to_nodes, estimate_tokens, render_context

# Word characters in any script, so Devanagari survives tokenisation.
_WORD = re.compile(r"\w+", re.UNICODE)
# A token worth also splitting: contains a separator between alphanumerics.
_COMPOUND = re.compile(r"[A-Za-z0-9]+(?:[/\-_.][A-Za-z0-9]+)+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, with compound identifiers kept whole *and* split.

    ``"invoice TAX/2026-27/69448"`` yields
    ``["invoice", "tax/2026-27/69448", "tax", "2026", "27", "69448"]``.
    """
    lowered = text.lower()
    tokens: list[str] = []
    for compound in _COMPOUND.findall(lowered):
        tokens.append(compound)
    tokens.extend(_WORD.findall(lowered))
    return tokens


def node_text(node: Node) -> str:
    """The searchable surface of a node: its type, provenance and field values."""
    return f"{node.type} {node.provenance}\n{render_context([node])}"


class BM25Retriever:
    """Okapi BM25 over every node in the corpus.

    Defaults are the **frozen best configuration** from the dev-split grid
    search (``scripts/tune_bm25.py``), not library defaults. The textbook
    ``k1=1.5, b=0.75`` scores 0.751 completeness here; the tuned setting
    reaches 0.965. Low ``b`` is the big lever: these nodes vary enormously in
    length — a one-line chat message against a three-page invoice — and
    penalising the long documents buries exactly the invoices and e-way bills
    that most gold facts live in.

    Args:
        k1: Term-frequency saturation. Higher rewards repeated terms more.
        b: Length normalisation. 0 ignores document length entirely.
        top_k: Hard cap on nodes considered, before the budget trim.
    """

    name = "bm25"

    def __init__(self, k1: float = 0.9, b: float = 0.3, top_k: int = 24) -> None:
        self.k1 = k1
        self.b = b
        self.top_k = top_k
        self._index: object | None = None
        self._nodes: list[Node] = []
        self._fingerprint: tuple[str, ...] = ()

    # -- indexing --------------------------------------------------------

    def _ensure_index(self, corpus: CaseCorpus) -> None:
        """Build the index once per corpus, not once per query."""
        fingerprint = tuple(case.case_id for case in corpus.cases)
        if self._index is not None and fingerprint == self._fingerprint:
            return

        from rank_bm25 import BM25Okapi

        nodes: list[Node] = []
        for case in corpus.cases:
            nodes.extend(_nodes_of(case))

        self._nodes = nodes
        self._index = BM25Okapi([tokenize(node_text(n)) for n in nodes], k1=self.k1, b=self.b)
        self._fingerprint = fingerprint

    # -- retrieval -------------------------------------------------------

    def retrieve(
        self,
        question: str,
        corpus: CaseCorpus,
        budget: int,
        jurisdiction: str = "IN",
    ) -> ContextBundle:
        self._ensure_index(corpus)
        assert self._index is not None

        scores = self._index.get_scores(tokenize(question))
        ranked = sorted(range(len(self._nodes)), key=lambda i: scores[i], reverse=True)

        kept: list[Node] = []
        for i in ranked[: self.top_k]:
            if scores[i] <= 0:
                break
            candidate = [*kept, self._nodes[i]]
            if estimate_tokens(render_context(candidate)) > budget and kept:
                break
            kept.append(self._nodes[i])

        # Emit in timeline order: rank decides *what* is included, chronology
        # decides how it reads. A temporal question is unanswerable from a
        # relevance-ordered jumble.
        kept.sort(key=lambda n: (n.ts or "", n.id))
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


def _nodes_of(case: Case | PublicCase) -> list[Node]:
    return case_to_nodes(case)

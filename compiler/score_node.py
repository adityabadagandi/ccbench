"""Seeded relevance ranking and budgeted subgraph assembly.

[YOU] Crown-jewel module — write and own this yourself.
    KIMI may write edge-case tests AFTER your contract tests pass.

[SPEC] score_node(node, query, seeds) -> float in [0,1]
       assemble_context(query, nodes, budget, jurisdiction) -> ContextBundle

Algorithm (to be implemented by YOU):
    1. score = w1·seed_match + w2·confidence + w3·type_prior + w4·recency
       where type_prior favors Flag > ErpOrder > Invoice > EWayBill
       for verdict questions.
    2. Assembly:
       - Seed from query
       - Rank by score
       - Greedily add under token budget
       - Enforce connectivity (a picked consignment brings its neighbors)
       - Temporal sort
    3. Verifiable property:
       The naive baseline over-retrieves unrelated consignments;
       your ranking must place seeded-consignment nodes above off-seed ones.

Test contracts (write THESE FIRST):
    def test_budget_respected(): ...
    def test_connectivity_preserved(): ...
    def test_seeded_nodes_rank_first(): ...
"""

from __future__ import annotations

from benchmark.schema.models import ContextBundle, Node


def score_node(node: Node, query: str, seeds: list[str]) -> float:
    """Score a single node for relevance to the query.

    [YOU] Implement this. The ranking formula is your design. Why is
    the e-way bill more relevant than the WhatsApp for a tax question?

    Args:
        node: The node to score.
        query: Natural-language query.
        seeds: Consignment references extracted from the query.

    Returns:
        Score in [0, 1].
    """
    raise NotImplementedError("Crown jewel — implement yourself. See module docstring.")


def assemble_context(
    query: str,
    nodes: list[Node],
    budget: int,
    jurisdiction: str = "IN",
) -> ContextBundle:
    """Assemble the minimal sufficient connected subgraph under budget.

    [YOU] Implement this. This is the retrieval contribution.

    Args:
        query: Natural-language query.
        nodes: Candidate nodes (already policy-filtered).
        budget: Token budget.
        jurisdiction: Target jurisdiction.

    Returns:
        ContextBundle with compiled, serialized context.
    """
    raise NotImplementedError("Crown jewel — implement yourself. See module docstring.")

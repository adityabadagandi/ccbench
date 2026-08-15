"""Faithfulness — spec v0.2 §4.3.

Fraction of claims in the answer that cite a retrieved node with an ``[ID]``
tag. A claim with no citation is unfaithful by definition — the spec is
explicit about that, and it is the right call: an uncited true statement is
indistinguishable from a lucky guess.

Claim segmentation is sentence-level and shared with the dataset validator via
``benchmark.text``, so the answer key cannot pass validation while failing the
metric it defines. It is coarse, and that is a documented limitation rather
than a hidden one: a sentence bundling two assertions behind one citation
scores as fully cited. Refining it requires an LLM and therefore a frozen
rubric, so it belongs with the judge, not here.
"""

from __future__ import annotations

from benchmark.schema.models import ContextBundle
from benchmark.text import citations_in, split_claims

__all__ = ["faithfulness", "split_claims"]


def faithfulness(answer: str, bundle: ContextBundle) -> tuple[float, list[str]]:
    """Score citation coverage of an answer.

    A claim is faithful when it carries at least one ``[ID]`` tag naming a node
    that was actually retrieved. Citing a node that is not in the bundle is a
    fabricated citation and does not count.

    Args:
        answer: What the system produced.
        bundle: The context it was given.

    Returns:
        ``(score, uncited_claims)``. An empty answer scores 0.
    """
    claims = split_claims(answer)
    if not claims:
        return 0.0, []

    retrieved = {node.id for node in bundle.nodes}
    uncited = [claim for claim in claims if not citations_in(claim) & retrieved]

    return (len(claims) - len(uncited)) / len(claims), uncited

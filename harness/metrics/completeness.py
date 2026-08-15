"""Context Completeness — spec v0.2 §4.2.

Gold-fact recall: of the facts this question needs, how many are actually
present in the retrieved context?

A fact counts as supported only if **both** hold:

1. the node carrying it was retrieved, and
2. the fact's stated value is recoverable from that node's fields.

Condition 2 matters. Retrieving the invoice node but serialising a summary
that dropped ``invoice_total`` is not support, and neither is retrieving a
chat thread while discarding the message the answer rests on. Because chat
messages are separate nodes (see ``harness/nodes.py``), a system that ignores
non-English content loses recall here rather than scoring for free.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from benchmark.schema.models import Case, ContextBundle, GoldFact, Node

_MSG_ID = re.compile(r"^M-\d{3}$")
_EVENT_ID = re.compile(r"^E-\d{3}$")
_INDEX = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\[(?P<idx>\d+)\]$")


def required_node_id(fact: GoldFact) -> str:
    """Which node must be retrieved for this fact to be supported.

    Thin alias over :attr:`GoldFact.node_id`. The mapping is owned by the
    benchmark, not the harness: the dataset validator needs it too, and one
    definition cannot drift from itself.
    """
    return fact.node_id


def context_completeness(case: Case, bundle: ContextBundle) -> tuple[float, list[str]]:
    """Score gold-fact recall for one case.

    Args:
        case: The full case, including its gold facts.
        bundle: What the retriever returned.

    Returns:
        ``(score, missing_fact_ids)`` where score is in ``[0, 1]``.
    """
    # Node ids are stable per case, not globally unique: a corpus-wide method
    # can legitimately return the invoice node of two different consignments,
    # both called "INV". Group rather than overwrite, and count a fact as
    # supported if *any* node under that id carries the stated value — which
    # also means retrieving the wrong consignment's invoice earns nothing.
    by_id: dict[str, list[Node]] = defaultdict(list)
    for node in bundle.nodes:
        by_id[node.id].append(node)

    missing: list[str] = []
    for fact in case.gold_facts:
        candidates = by_id.get(required_node_id(fact), [])
        if not any(_value_present(node.fields, fact) for node in candidates):
            missing.append(fact.fact_id)

    supported = len(case.gold_facts) - len(missing)
    return supported / len(case.gold_facts), missing


def _value_present(fields: dict[str, Any], fact: GoldFact) -> bool:
    """Is the fact's stated value recoverable from this node's fields?"""
    head, _, tail = fact.path.partition(".")

    if _EVENT_ID.match(head):
        for event in fields.get("events", []):
            if event.get("event_id") == head:
                return _walk(event, tail) is not _MISSING and str(_walk(event, tail)) == fact.value
        return False

    path = tail if _MSG_ID.match(head) else fact.path
    found = _walk(fields, path)
    return found is not _MISSING and str(found) == fact.value


class _Missing:
    """Sentinel distinguishing 'absent' from a legitimate ``None`` value."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<missing>"


_MISSING = _Missing()


def _walk(node: Any, path: str) -> Any:
    if not path:
        return node
    for part in path.split("."):
        match = _INDEX.match(part)
        try:
            node = node[match.group("name")][int(match.group("idx"))] if match else node[part]
        except (KeyError, IndexError, TypeError):
            return _MISSING
    return node

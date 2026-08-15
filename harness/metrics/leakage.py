"""Compliance Leakage — spec v0.2 §4.4.

Binary, by byte-level search: does anything the system emits contain a literal
the case's jurisdiction denies?

This is deliberately the dumbest possible check. A leakage metric that relies
on an LLM to notice a leak is a leakage metric that can be argued with. A
substring search cannot be: either the PAN is in the output or it is not.

``must_not_appear`` is populated on every EU case with both parties' PANs and
both named contacts' email addresses and phone numbers. It is empty for IN,
where the policy allows everything — so IN cases pass trivially, which is
correct, not a bug.

The GSTIN is *masked* rather than denied, so it is not in ``must_not_appear``.
Whether a system masked it correctly is an answer-quality question, checked by
:func:`gstin_masking_respected` when an answer is available.
"""

from __future__ import annotations

from benchmark.schema.models import Case, ContextBundle


def compliance_leakage(
    case: Case,
    bundle: ContextBundle,
    answer: str | None = None,
) -> tuple[bool, list[str]]:
    """Check for denied literals in everything the system emitted.

    Args:
        case: The full case, carrying ``must_not_appear``.
        bundle: The emitted context.
        answer: The emitted answer, if the method produced one.

    Returns:
        ``(clean, leaked_literals)``. ``clean`` is True when nothing leaked.
    """
    haystack = bundle.llm_context
    if answer:
        haystack = f"{haystack}\n{answer}"

    leaked = [literal for literal in case.must_not_appear if literal in haystack]
    return not leaked, leaked


def gstin_masking_respected(case: Case, answer: str) -> bool:
    """Under EU rules a GSTIN may appear only masked to its last four.

    Returns True for IN cases, where no masking is required.
    """
    if case.jurisdiction.value != "EU":
        return True
    inv = case.documents.invoice
    return all(party.gstin not in answer for party in (inv.seller, inv.buyer))

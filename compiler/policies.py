"""Jurisdictional emission policies (Π_J).

[YOU] Crown-jewel module — write and own this yourself.
    KIMI may write edge-case tests AFTER your contract tests pass.
    The 0%-leakage claim is yours to prove.

[SPEC] apply_policy(node, jurisdiction) -> Node | None
    None = deny/drop; else = masked copy.
    Applied INSIDE node loading, before assembly.

Policy table (to be finalized by YOU):
    ┌─────────┬────────┬────────┐
    │ Field   │ IN     │ EU     │
    ├─────────┼────────┼────────┤
    │ pan     │ allow  │ deny   │  <- personal tax id: never leaves India
    │ gstin   │ allow  │ mask   │  <- business tax id: shown masked
    │ …       │ …      │ …      │
    └─────────┴────────┴────────┘

Rules:
    - Deny -> the node's forbidden field is removed AND if the field is
      the node's essence, the node is dropped from the candidate set
      entirely — it is never a retrieval candidate.
    - This is a parameter of retrieval, not a post-step filter.
      Denied nodes never enter the candidate set.
      Zero-leakage is a property of the operator, provable by construction.

The one test that matters:
    assemble under jurisdiction="EU" on a case whose PAN is in
    must_not_appear; assert that PAN appears NOWHERE in
    bundle.llm_context — byte-level search.
    This test is the empirical face of the provable claim.

Test contracts (write THESE FIRST):
    def test_pan_absent_from_eu_view(): ...
    def test_gstin_masked_in_eu_view(): ...
    def test_all_fields_allowed_in_in_view(): ...
"""

from __future__ import annotations

from benchmark.schema.models import Node


POLICY = {
    # (field_name, jurisdiction) -> action
    ("pan", "EU"): "deny",     # personal tax id: never leaves India
    ("gstin", "EU"): "mask",   # business tax id: shown masked
    # IN: allow all (implicit default)
}


def apply_policy(node: Node, jurisdiction: str) -> Node | None:
    """Apply jurisdiction policy to a node.

    [YOU] Implement this. Policy design is a research decision. Why does
    EU GDPR require masking GSTIN? Which fields are deny vs mask vs allow?

    Args:
        node: The node to filter/mask.
        jurisdiction: Target jurisdiction ('IN' or 'EU').

    Returns:
        Masked copy of the node, or None if the node is denied entirely.
    """
    raise NotImplementedError("Crown jewel — implement yourself. See module docstring.")

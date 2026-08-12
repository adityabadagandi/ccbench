"""Tests for compiler modules.

.. note::

    Tests for crown-jewel modules (reconcile, score_node, policies)
    are contract tests; the implementations are intentionally left as
    stubs for the project owner to fill in.
"""

from __future__ import annotations

import pytest

import compiler
import compiler.policies
import compiler.propagate
import compiler.reconcile
import compiler.score_node
import compiler.server


def test_compiler_package_imports() -> None:
    """The compiler package and all crown-jewel modules must import."""
    assert compiler.__doc__ is not None
    assert hasattr(compiler.policies, "apply_policy")
    assert hasattr(compiler.propagate, "propagate")
    assert hasattr(compiler.reconcile, "reconcile")
    assert hasattr(compiler.score_node, "score_node")
    assert compiler.server is not None


def test_apply_policy_is_crown_jewel_stub() -> None:
    """apply_policy must be present and raise until implemented."""
    from benchmark.schema.models import Node

    node = Node(
        id="N-1",
        type="Invoice",
        consignment_ref="CONS-1",
        fields={"pan": "ABCDE1234F"},
        confidence=1.0,
        ts=None,
        provenance="test",
    )
    with pytest.raises(NotImplementedError):
        compiler.policies.apply_policy(node, "EU")


def test_reconcile_is_crown_jewel_stub() -> None:
    """reconcile must be present and raise until implemented."""
    from benchmark.schema.models import Invoice

    invoice = Invoice(invoice_no="INV-1", consignment_ref="CONS-1", value_eur=100.0)
    with pytest.raises(NotImplementedError):
        compiler.reconcile.reconcile([invoice], [], [])

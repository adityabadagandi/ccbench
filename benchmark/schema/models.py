"""Pydantic models for CCBench case validation.

These models enforce the structure of every benchmark case.

[SPEC] Frozen contract — version 1.0
    Changes to this file require a version bump because every component
    downstream (extract, harness, baselines) depends on these shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain enums (used in Case validation)
# ---------------------------------------------------------------------------


class Bucket(str, Enum):
    """Task bucket categories."""

    LOOKUP = "lookup"
    MULTI_HOP = "multi-hop"
    TEMPORAL = "temporal"
    CROSS_LINGUAL = "cross-lingual"
    COMPLIANCE = "compliance"


class Jurisdiction(str, Enum):
    """Supported jurisdictions."""

    IN = "IN"
    EU = "EU"


class GoldLabel(str, Enum):
    """Gold labels describing case challenge type."""

    CLEAN = "clean"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_EWB = "missing_ewb"
    TEMPORAL_VIOLATION = "temporal_violation"
    COMPLIANCE_CASE = "compliance_case"


# ---------------------------------------------------------------------------
# Domain types (the shapes every layer passes around)
# [SPEC] compiler/models.py — frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Invoice:
    """GST-format invoice with HSN codes and tax identifiers."""

    invoice_no: str
    consignment_ref: str
    value_eur: float
    vendor: str | None = None
    gstin: str | None = None          # business tax id (mask for EU)
    pan: str | None = None            # personal tax id (DENY for EU)
    ts: str | None = None             # ISO-8601 timestamp
    doc_ref: str | None = None        # provenance: source file/record id


@dataclass
class EWayBill:
    """Government e-way bill permit."""

    ewb_no: str
    consignment_ref: str
    declared_eur: float
    ts: str | None = None
    doc_ref: str | None = None


@dataclass
class ErpOrder:
    """Internal ERP purchase order record."""

    order_no: str
    consignment_ref: str
    expected_eur: float
    ts: str | None = None
    doc_ref: str | None = None


@dataclass
class Message:
    """WhatsApp POD / dispatch message (HI/EN code-switched)."""

    msg_id: str
    consignment_ref: str
    text: str
    lang: str                         # 'hi' | 'en' | 'hi-en'
    ts: str | None = None
    doc_ref: str | None = None


@dataclass
class Finding:
    """Produced by reconcile (L5 workflow engine).

    Attributes:
        kind: One of value_mismatch, missing_ewb, temporal_violation, ok.
        consignment_ref: Which shipment this finding belongs to.
        severity: high, med, or ok.
        confidence: 0..1 post-propagation confidence.
        detail: Numbers + provenance refs.
    """

    kind: str
    consignment_ref: str
    severity: str
    confidence: float
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Graph node & context bundle (L3 context graph → L4 output)
# [SPEC] compiler/context.py — graph and output types
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """Single node in the context graph."""

    id: str                           # e.g. 'INV-5567', 'F1'
    type: str                         # 'Invoice'|'EWayBill'|'ErpOrder'|'Message'|'Flag'
    consignment_ref: str
    fields: dict[str, Any]
    confidence: float                 # 0..1 (post-propagation)
    ts: str | None                    # for temporal ordering
    provenance: str                   # human-readable source


@dataclass
class ContextBundle:
    """Final compiled context package emitted by the compiler.

    This is the universal output format consumed by LLM prompts, MCP tools,
    REST endpoints, and human UI.
    """

    query: str
    nodes: list[Node]                 # selected connected subgraph, temporally ordered
    llm_context: str                  # serialized, [ID]-tagged, citable block
    citations: list[str]              # node ids present
    tokens: int                       # budget used
    budget: int                       # budget allowed
    jurisdiction: str                 # 'IN'|'EU'


# ---------------------------------------------------------------------------
# Universal retriever contract
# [SPEC] Every baseline and our method must satisfy this Protocol.
#        The harness calls retrieve(...) identically on all methods.
# ---------------------------------------------------------------------------


class Retriever(Protocol):
    """Universal contract for any retrieval method evaluated on CCBench.

    This Protocol makes the benchmark fair: the harness calls
    retrieve(...) identically on BM25, dense, hybrid, GraphRAG, and
    context-compiler. Any method that fits the budget and returns a
    ContextBundle can be scored. No special-casing, no home-field
    advantage.
    """

    name: str

    def retrieve(
        self,
        question: str,
        corpus: "CaseCorpus",
        budget: int,
        jurisdiction: str = "IN",
    ) -> ContextBundle:
        """Retrieve and compile context for a question.

        Args:
            question: Natural-language query.
            corpus: The case corpus to search.
            budget: Maximum token budget for the returned context.
            jurisdiction: Target jurisdiction ('IN' or 'EU').

        Returns:
            A ContextBundle containing the compiled context.
        """
        ...


# ---------------------------------------------------------------------------
# Case schema (the benchmark's atomic unit)
# [SPEC] benchmark/case.schema.json (enforced by Pydantic below)
# ---------------------------------------------------------------------------


class Documents(BaseModel):
    """Document bundle for a case.

    Attributes:
        invoice: GST-format invoice with HSN codes, GSTIN, totals.
        eway_bill: E-way bill linked by consignment reference.
        erp_order: Purchase order from ERP system.
        whatsapp_pod: Optional WhatsApp proof-of-delivery thread.
        flag: Optional compliance flag or annotation.
    """

    invoice: dict[str, Any]
    eway_bill: dict[str, Any] | None = None
    erp_order: dict[str, Any]
    whatsapp_pod: dict[str, Any] | None = None
    flag: dict[str, Any] | None = None


class Case(BaseModel):
    """Single benchmark case.

    Design invariants (enforced by validator, non-negotiable):
      * Every id in gold_facts must exist in documents.
      * All identifiers drawn from reserved synthetic ranges — never real.
      * must_not_appear populated for every compliance + EU case.
      * Timestamps internally consistent (POD after invoice, etc.).
      * No two cases share invoice_no or consignment_ref.

    Attributes:
        case_id: Unique identifier for this case.
        bucket: Task bucket category.
        jurisdiction: Legal jurisdiction (IN or EU).
        documents: Bundle of related documents.
        question: Natural-language question to answer.
        gold_answer: Ground-truth answer.
        gold_facts: List of required facts to support the answer.
        gold_label: Label describing the challenge type.
        difficulty: Optional difficulty rating.
        must_not_appear: Values that must be absent in EU view (compliance).
    """

    case_id: str
    bucket: Bucket
    jurisdiction: Jurisdiction
    documents: Documents
    question: str
    gold_answer: str
    gold_facts: list[str]
    gold_label: GoldLabel
    difficulty: str | None = None
    must_not_appear: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Post-init validation hook."""
        # TODO: move heavy validation to scripts/validate_cases.py
        pass

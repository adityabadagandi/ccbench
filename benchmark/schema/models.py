"""Pydantic models for CCBench case validation.

These models enforce the structure of every benchmark case.

[SPEC] Frozen contract — version 1.1
    Changes to this file require a version bump because every component
    downstream (extract, harness, baselines) depends on these shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Domain enums (used in Case validation)
# ---------------------------------------------------------------------------


class Bucket(StrEnum):
    """Task bucket categories."""

    LOOKUP = "lookup"
    MULTI_HOP = "multi-hop"
    TEMPORAL = "temporal"
    CROSS_LINGUAL = "cross-lingual"
    COMPLIANCE = "compliance"


class Jurisdiction(StrEnum):
    """Supported jurisdictions."""

    IN = "IN"
    EU = "EU"


class GoldLabel(StrEnum):
    """Gold labels describing case challenge type."""

    CLEAN = "clean"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_EWB = "missing_ewb"
    TEMPORAL_VIOLATION = "temporal_violation"
    COMPLIANCE_CASE = "compliance_case"


# ---------------------------------------------------------------------------
# Document sub-models (match case.schema.json and generators/*.py)
# ---------------------------------------------------------------------------


class Party(BaseModel):
    """Seller or buyer on a GST invoice."""

    name: str
    gstin: str
    address: str


class InvoiceItem(BaseModel):
    """Single line item on a GST invoice."""

    description: str
    hsn_code: str
    quantity: float
    unit: str
    rate_per_unit: float
    taxable_value: float
    cgst_rate: float
    sgst_rate: float
    cgst_amount: float
    sgst_amount: float


class InvoiceDoc(BaseModel):
    """GST-format invoice document (as stored in case JSON).

    Note: this is the *raw document* shape, not the compiler's internal
    Invoice dataclass. The extract layer maps one to the other.
    """

    invoice_no: str
    date: str
    seller: Party
    buyer: Party
    items: list[InvoiceItem]
    total_taxable_value: float
    total_cgst: float
    total_sgst: float
    invoice_total: float
    eway_bill_ref: str | None = None
    vehicle_no: str
    consignment_ref: str


class EWayItem(BaseModel):
    """Single line item on an e-way bill."""

    description: str
    hsn_code: str
    quantity: float
    unit: str


class EWayBillDoc(BaseModel):
    """Government e-way bill document."""

    ewb_no: str
    generation_date: str
    valid_until: str
    from_gstin: str
    from_address: str
    to_gstin: str
    to_address: str
    transporter: str
    vehicle_no: str
    consignment_ref: str
    items: list[EWayItem]
    total_value: float
    distance_km: float


class ErpItem(BaseModel):
    """Single line item on an ERP purchase order."""

    item_code: str
    description: str
    quantity_ordered: float
    unit: str
    unit_price: float
    total_value: float
    expected_delivery: str


class ErpOrderDoc(BaseModel):
    """ERP purchase order document."""

    po_no: str
    po_date: str
    buyer: str
    vendor_code: str
    vendor_name: str
    items: list[ErpItem]
    po_total: float
    payment_terms: str
    status: str
    invoice_refs: list[str]
    consignment_ref: str


class WhatsAppMessage(BaseModel):
    """Single message in a WhatsApp POD thread."""

    timestamp: str
    sender: str
    text: str


class WhatsAppPodDoc(BaseModel):
    """WhatsApp proof-of-delivery thread document."""

    thread_id: str
    driver_name: str
    driver_phone: str
    messages: list[WhatsAppMessage]
    delivery_confirmed: bool | None = None
    pod_signed_by: str | None = None


# ---------------------------------------------------------------------------
# Document bundle
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

    invoice: InvoiceDoc
    eway_bill: EWayBillDoc | None = None
    erp_order: ErpOrderDoc
    whatsapp_pod: WhatsAppPodDoc | None = None
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


# ---------------------------------------------------------------------------
# Domain types (the shapes every compiler layer passes around)
# [SPEC] compiler/models.py — frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Invoice:
    """GST-format invoice with HSN codes and tax identifiers."""

    invoice_no: str
    consignment_ref: str
    value_eur: float
    vendor: str | None = None
    gstin: str | None = None  # business tax id (mask for EU)
    pan: str | None = None  # personal tax id (DENY for EU)
    ts: str | None = None  # ISO-8601 timestamp
    doc_ref: str | None = None  # provenance: source file/record id


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
    lang: str  # 'hi' | 'en' | 'hi-en'
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

    id: str  # e.g. 'INV-5567', 'F1'
    type: str  # 'Invoice'|'EWayBill'|'ErpOrder'|'Message'|'Flag'
    consignment_ref: str
    fields: dict[str, Any]
    confidence: float  # 0..1 (post-propagation)
    ts: str | None  # for temporal ordering
    provenance: str  # human-readable source


@dataclass
class ContextBundle:
    """Final compiled context package emitted by the compiler.

    This is the universal output format consumed by LLM prompts, MCP tools,
    REST endpoints, and human UI.
    """

    query: str
    nodes: list[Node]  # selected connected subgraph, temporally ordered
    llm_context: str  # serialized, [ID]-tagged, citable block
    citations: list[str]  # node ids present
    tokens: int  # budget used
    budget: int  # budget allowed
    jurisdiction: str  # 'IN'|'EU'


# ---------------------------------------------------------------------------
# Corpus type (forward reference placeholder)
# [SPEC] A collection of benchmark cases passed to retrievers.
# ---------------------------------------------------------------------------


@dataclass
class CaseCorpus:
    """Collection of benchmark cases used by retrievers.

    This is intentionally a thin placeholder; the harness will later
    wrap loaded cases. It exists only to make the Retriever Protocol
    type-check cleanly.
    """

    cases: list[Case] = field(default_factory=list)


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
        corpus: CaseCorpus,
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

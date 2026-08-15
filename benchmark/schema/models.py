"""Pydantic models for CCBench case validation.

These models enforce the structure of every benchmark case.

[SPEC] Frozen contract — schema version 0.2
    Hard break from 0.1. Changes to this file require a version bump because
    every component downstream (extract, harness, baselines) depends on these
    shapes.

What 0.2 changed, and why:
    * ``Party.pan`` and ``Party.contact`` added. The 0.1 schema had no PAN
      anywhere, so ``compiler/policies.py`` keyed its deny rule on a field that
      could not exist. Compliance cases were unrepresentable.
    * ``Invoice.issued_at`` is a datetime, not a date, plus ``revision_no`` /
      ``supersedes`` / ``original_issued_at``. Same-day ordering against an
      e-way bill was undecidable in 0.1, which is precisely when it matters.
    * Case-level ``events`` timeline added, so temporal questions resolve
      against structure rather than prose.
    * ``Message`` gained ``msg_id``, ``lang``, ``reply_to``, ``attachments``.
      ``lang`` aligns the case schema with the compiler's ``Message`` dataclass,
      which always had it.
    * ``WhatsAppPod`` LOST ``delivery_confirmed`` / ``pod_signed_by``. Those
      booleans let a system answer delivery questions without reading the
      code-switched text, defeating the cross-lingual bucket.
    * ``gold_facts`` are objects with an optional ``evidence`` span, not flat
      strings. In 0.1 there were only two distinct fact signatures across 200
      cases, making Context Completeness unmeasurable.
    * ``must_not_appear`` is enforced non-empty for EU cases, not merely
      documented as an invariant and then left empty in all 200 cases.
    * ``EWayBill.total_invoice_value`` is tax-inclusive, so it is comparable to
      ``invoice_total`` like-for-like. In 0.1 the e-way bill carried the
      pre-tax value, so "clean" cases never matched and the gold answers that
      claimed they did were false.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "0.2"

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


class Difficulty(StrEnum):
    """Difficulty tiers.

    Settled as strings to match BENCHMARK_SPEC.md. ``context-compiler-golden.md``
    describes an integer 1..3; that document is the one that must change.
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Lang(StrEnum):
    """Language of a question or message."""

    EN = "en"
    HI = "hi"
    HI_EN = "hi-en"


class SupplyType(StrEnum):
    """GST supply type. Determines whether tax is CGST+SGST or IGST."""

    INTRA_STATE = "intra_state"
    INTER_STATE = "inter_state"


class EwbStatus(StrEnum):
    """E-way bill lifecycle status."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ParticipantRole(StrEnum):
    """Who is speaking in an operational chat thread."""

    DRIVER = "driver"
    DISPATCHER = "dispatcher"
    WAREHOUSE = "warehouse"
    ACCOUNTS = "accounts"
    TRANSPORTER = "transporter"
    BUYER_OPS = "buyer_ops"


class EventType(StrEnum):
    """Types on the case-level timeline."""

    PO_RAISED = "po_raised"
    PO_APPROVED = "po_approved"
    INVOICE_ISSUED = "invoice_issued"
    INVOICE_REVISED = "invoice_revised"
    EWB_GENERATED = "ewb_generated"
    EWB_EXTENDED = "ewb_extended"
    EWB_CANCELLED = "ewb_cancelled"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DELIVERED = "delivered"
    POD_SIGNED = "pod_signed"
    GRN_RECORDED = "grn_recorded"
    FLAG_RAISED = "flag_raised"
    PAYMENT_RELEASED = "payment_released"


class DocName(StrEnum):
    """Which document a gold fact lives in."""

    INVOICE = "invoice"
    EWAY_BILL = "eway_bill"
    ERP_ORDER = "erp_order"
    WHATSAPP_POD = "whatsapp_pod"
    FLAG = "flag"
    EVENTS = "events"


# ---------------------------------------------------------------------------
# Document sub-models (match case.schema.json and generators/*.py)
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    """Base for case-document models: unknown fields are an error.

    0.1 allowed extras, which is how ``must_not_appear`` and ``flag`` could be
    declared in the schema and silently absent from every case.
    """

    model_config = ConfigDict(extra="forbid")


class Address(_Strict):
    """Postal address, structured so state can be compared without parsing."""

    line1: str
    line2: str | None = None
    city: str
    state: str
    state_code: str
    pincode: str
    country: str


class Contact(_Strict):
    """A named natural person at a party.

    This is the personal data that makes EU cases real: a name, an email and a
    phone number are GDPR-relevant in a way a company GSTIN is not.
    """

    name: str
    email: str
    phone: str


class Party(_Strict):
    """Seller or buyer on a GST invoice."""

    name: str
    legal_name: str
    gstin: str
    pan: str
    address: Address
    contact: Contact

    @field_validator("gstin")
    @classmethod
    def _check_gstin(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", v):
            raise ValueError(f"malformed GSTIN: {v!r}")
        return v

    @field_validator("pan")
    @classmethod
    def _check_pan(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v):
            raise ValueError(f"malformed PAN: {v!r}")
        return v

    @model_validator(mode="after")
    def _pan_embedded_in_gstin(self) -> Party:
        """A real GSTIN embeds the holder's PAN at positions 2..12."""
        if self.gstin[2:12] != self.pan:
            raise ValueError(f"PAN {self.pan!r} not embedded in GSTIN {self.gstin!r}")
        return self


class InvoiceItem(_Strict):
    """Single line item on a GST invoice."""

    line_no: int
    description: str
    hsn_code: str
    quantity: float
    unit: str
    rate_per_unit: float
    taxable_value: float
    tax_rate: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float


class InvoiceDoc(_Strict):
    """GST-format invoice document (as stored in case JSON).

    Note: this is the *raw document* shape, not the compiler's internal
    Invoice dataclass. The extract layer maps one to the other.
    """

    invoice_no: str
    issued_at: str
    revision_no: int
    supersedes: str | None
    original_issued_at: str | None
    seller: Party
    buyer: Party
    place_of_supply: str
    supply_type: SupplyType
    items: list[InvoiceItem]
    total_taxable_value: float
    total_cgst: float
    total_sgst: float
    total_igst: float
    total_tax: float
    invoice_total: float
    currency: str
    eway_bill_ref: str | None
    vehicle_no: str
    consignment_ref: str

    @model_validator(mode="after")
    def _totals_add_up(self) -> InvoiceDoc:
        """Arithmetic must be internally consistent.

        Reconciliation questions are only meaningful if the documents are
        individually correct; a case must not be solvable by spotting that the
        invoice fails to add up on its own.
        """
        line_sum = round(sum(i.taxable_value for i in self.items), 2)
        if abs(line_sum - self.total_taxable_value) > 0.01:
            raise ValueError(
                f"line taxable values sum to {line_sum}, header says {self.total_taxable_value}"
            )
        tax = round(self.total_cgst + self.total_sgst + self.total_igst, 2)
        if abs(tax - self.total_tax) > 0.01:
            raise ValueError(f"tax components sum to {tax}, total_tax says {self.total_tax}")
        expected = round(self.total_taxable_value + self.total_tax, 2)
        if abs(expected - self.invoice_total) > 0.01:
            raise ValueError(f"taxable + tax = {expected}, invoice_total says {self.invoice_total}")
        return self

    @model_validator(mode="after")
    def _tax_matches_supply_type(self) -> InvoiceDoc:
        """Inter-state supply is IGST; intra-state is CGST+SGST. Never both."""
        if self.supply_type is SupplyType.INTER_STATE:
            if self.total_cgst or self.total_sgst:
                raise ValueError("inter-state supply must not carry CGST/SGST")
            if not self.total_igst:
                raise ValueError("inter-state supply must carry IGST")
        else:
            if self.total_igst:
                raise ValueError("intra-state supply must not carry IGST")
            if not (self.total_cgst and self.total_sgst):
                raise ValueError("intra-state supply must carry CGST and SGST")
        return self

    @model_validator(mode="after")
    def _revision_fields_coherent(self) -> InvoiceDoc:
        if self.revision_no > 0 and (self.supersedes is None or self.original_issued_at is None):
            raise ValueError("a revised invoice must record supersedes and original_issued_at")
        if self.revision_no == 0 and (self.supersedes or self.original_issued_at):
            raise ValueError("an original invoice must not record supersedes/original_issued_at")
        return self


class EWayItem(_Strict):
    """Single line item on an e-way bill."""

    description: str
    hsn_code: str
    quantity: float
    unit: str


class EwbExtension(_Strict):
    """A validity extension on an e-way bill."""

    extended_at: str
    new_valid_until: str
    reason: str


class EWayBillDoc(_Strict):
    """Government e-way bill document."""

    ewb_no: str
    generated_at: str
    valid_until: str
    status: EwbStatus
    extensions: list[EwbExtension]
    doc_type: str
    doc_no: str
    doc_date: str
    from_gstin: str
    from_address: str
    to_gstin: str
    to_address: str
    transporter_name: str
    transporter_id: str
    mode: str
    vehicle_no: str
    consignment_ref: str
    items: list[EWayItem]
    taxable_value: float
    total_invoice_value: float
    distance_km: float


class ErpItem(_Strict):
    """Single line item on an ERP purchase order."""

    item_code: str
    description: str
    quantity_ordered: float
    unit: str
    unit_price: float
    line_total: float
    expected_delivery: str


class Approval(_Strict):
    """Who signed off the PO and when."""

    approved_by: str
    approved_at: str


class GrnLine(_Strict):
    """One line of a goods receipt note."""

    item_code: str
    quantity_received: float
    condition: str


class Grn(_Strict):
    """Goods receipt note — the only structured record of physical receipt."""

    grn_no: str
    received_at: str
    received_by: str
    lines: list[GrnLine]


class ErpOrderDoc(_Strict):
    """ERP purchase order document."""

    po_no: str
    po_date: str
    buyer_entity: str
    vendor_code: str
    vendor_name: str
    vendor_gstin: str
    items: list[ErpItem]
    po_subtotal: float
    po_tax: float
    po_total: float
    currency: str
    payment_terms: str
    status: str
    approval: Approval
    invoice_refs: list[str]
    grn: Grn | None
    consignment_ref: str


class Attachment(_Strict):
    """A file shared into a chat thread."""

    type: str
    filename: str
    caption: str | None
    transcript: str | None = None


class Participant(_Strict):
    """A person in a chat thread."""

    participant_id: str
    name: str
    role: ParticipantRole
    phone: str


class WhatsAppMessage(_Strict):
    """Single message in a WhatsApp POD thread."""

    msg_id: str
    ts: str
    sender_id: str
    sender_name: str
    lang: Lang
    text: str
    reply_to: str | None
    attachments: list[Attachment]
    edited: bool


class WhatsAppPodDoc(_Strict):
    """WhatsApp proof-of-delivery thread document.

    Carries no derived ``delivery_confirmed`` flag by design: whether delivery
    happened must be read out of the code-switched message text.
    """

    thread_id: str
    thread_name: str
    participants: list[Participant]
    messages: list[WhatsAppMessage]

    @model_validator(mode="after")
    def _senders_are_participants(self) -> WhatsAppPodDoc:
        ids = {p.participant_id for p in self.participants}
        for m in self.messages:
            if m.sender_id not in ids:
                raise ValueError(f"message {m.msg_id} sent by unknown participant {m.sender_id}")
        return self

    @model_validator(mode="after")
    def _reply_targets_exist(self) -> WhatsAppPodDoc:
        seen: set[str] = set()
        for m in self.messages:
            if m.reply_to is not None and m.reply_to not in seen:
                raise ValueError(f"message {m.msg_id} replies to unseen {m.reply_to}")
            seen.add(m.msg_id)
        return self


class Flag(_Strict):
    """An exception raised by a human against this consignment."""

    flag_id: str
    raised_at: str
    raised_by: str
    kind: str
    note: str


# ---------------------------------------------------------------------------
# Document bundle, timeline, supervision
# ---------------------------------------------------------------------------


class Documents(_Strict):
    """Document bundle for a case."""

    invoice: InvoiceDoc
    eway_bill: EWayBillDoc | None = None
    erp_order: ErpOrderDoc
    whatsapp_pod: WhatsAppPodDoc | None = None
    flag: Flag | None = None


class Event(_Strict):
    """One entry on the case-level timeline."""

    event_id: str
    type: EventType
    ts: str
    actor: str
    doc_ref: str | None
    note: str | None = None


class EvidenceSpan(_Strict):
    """Points at the exact clause carrying a fact.

    Required whenever a fact rests on chat text, so a system that silently
    ignores non-English content cannot score on the cross-lingual bucket.
    """

    ref_id: str
    lang: Lang
    span: str
    gloss_en: str | None = None


class GoldFact(_Strict):
    """One unit of required evidence, derived from the question."""

    fact_id: str
    doc: DocName
    path: str
    value: str
    evidence: EvidenceSpan | None = None

    @property
    def node_id(self) -> str:
        """Which retrievable node must be present for this fact to be supported.

        Defined here rather than in the harness because it follows from the
        fact's own ``doc`` and ``path``: the benchmark decides what a fact
        points at, and the harness merely builds nodes with matching ids.
        """
        head = self.path.split(".")[0]
        if self.doc is DocName.WHATSAPP_POD and _MSG_ID_RE.match(head):
            return head
        return _DOC_NODE_ID[self.doc]


_MSG_ID_RE = re.compile(r"^M-\d{3}$")

_DOC_NODE_ID = {
    DocName.INVOICE: "INV",
    DocName.EWAY_BILL: "EWB",
    DocName.ERP_ORDER: "ERP",
    DocName.FLAG: "FLAG",
    DocName.EVENTS: "TIMELINE",
    DocName.WHATSAPP_POD: "WHATSAPP",
}


class Provenance(_Strict):
    """How this case was produced."""

    generator_version: str
    seed: int
    notes: str | None = None


class Case(_Strict):
    """Single benchmark case.

    Design invariants — all machine-enforced, by ``benchmark/validate.py``
    for the cross-document ones and by this model for the local ones:

      * Every gold_fact path resolves in documents and equals its stated value.
      * All identifiers drawn from reserved synthetic ranges — never real.
      * must_not_appear non-empty for every EU case.
      * Timestamps internally consistent and events in ascending order.
      * No two cases share invoice_no or consignment_ref.
      * gold_label is realised in the documents, not merely asserted.
    """

    schema_version: str = SCHEMA_VERSION
    case_id: str
    bucket: Bucket
    jurisdiction: Jurisdiction
    documents: Documents
    events: list[Event]
    question: str
    question_lang: Lang
    gold_answer: str
    gold_facts: list[GoldFact]
    gold_label: GoldLabel
    difficulty: Difficulty
    must_not_appear: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None

    @field_validator("schema_version")
    @classmethod
    def _version_matches(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"expected schema_version {SCHEMA_VERSION}, got {v!r}")
        return v

    @model_validator(mode="after")
    def _eu_declares_forbidden_literals(self) -> Case:
        if self.jurisdiction is Jurisdiction.EU and not self.must_not_appear:
            raise ValueError("EU cases must declare must_not_appear so leakage is scoreable")
        return self

    @model_validator(mode="after")
    def _events_ordered(self) -> Case:
        ts = [e.ts for e in self.events]
        if ts != sorted(ts):
            raise ValueError("events must be in ascending ts order")
        return self

    @model_validator(mode="after")
    def _missing_ewb_is_realised(self) -> Case:
        if self.gold_label is GoldLabel.MISSING_EWB and self.documents.eway_bill is not None:
            raise ValueError("gold_label missing_ewb but an e-way bill is present")
        return self

    @model_validator(mode="after")
    def _gold_answer_is_not_a_placeholder(self) -> Case:
        """0.1 shipped 113 of these. Never again."""
        lowered = self.gold_answer.lower()
        for marker in ("not yet implemented", "todo", "tbd", "placeholder", "fixme"):
            if marker in lowered:
                raise ValueError(f"gold_answer contains placeholder marker {marker!r}")
        return self


class PublicCase(_Strict):
    """The redacted view of a test case, as distributed.

    Bucket, difficulty and every gold field are withheld: publishing the bucket
    would let a method condition on the task type it is about to be scored on,
    and publishing ``must_not_appear`` would hand over the leakage answer key.
    The scorer holds the full :class:`Case` privately.
    """

    schema_version: str = SCHEMA_VERSION
    case_id: str
    jurisdiction: Jurisdiction
    documents: Documents
    events: list[Event]
    question: str
    question_lang: Lang
    provenance: Provenance | None = None


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
    """Collection of benchmark cases used by retrievers."""

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

"""Case assembler — turns scenarios into fully-supervised benchmark cases.

The single most important rule here, and the one 0.1 broke:

    The question comes first. The answer and the gold facts are derived from
    the question and the scenario together. Nothing is ever chosen at random
    independently of anything else.

A :class:`TaskSpec` binds a bucket, a gold label, the scenario defect that
*realises* that label, and a builder that writes the question, the answer and
the exact evidence needed. Only the (bucket, label) pairs listed in
:data:`TASKS` exist; the other 14 of the 25 combinations are illegal by
construction rather than merely improbable.

Emission policy note
--------------------
``must_not_appear`` constrains the **emitted answer**, matching
BENCHMARK_SPEC §4.4 ("does the output contain any field the policy marks as
deny"). ``gold_facts`` are *retrieval* targets and may legitimately point at a
denied field: to answer "may I disclose the PAN?" a system must first retrieve
the invoice and see that a PAN is present. Completeness and leakage are
therefore measured on different objects — retrieved context versus emitted
answer — and a compliant system scores 1.0 on both.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .identity import GENERATOR_VERSION
from .scenario import (
    Scenario,
    build_erp_order,
    build_events,
    build_eway_bill,
    build_flag,
    build_invoice,
    build_scenario,
)
from .whatsapp import build_thread

Built = dict[str, Any]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _s(value: Any) -> str:
    """Stringify a document value for a gold fact."""
    return str(value)


def _fact(idx: int, doc: str, path: str, value: Any, evidence: dict | None = None) -> dict:
    return {
        "fact_id": f"F{idx}",
        "doc": doc,
        "path": path,
        "value": _s(value),
        "evidence": evidence,
    }


def _inr(amount: float) -> str:
    return f"Rs. {amount:,.2f}"


def _mask_gstin(gstin: str) -> str:
    """EU view of a business tax id: last four characters only."""
    return f"{'X' * (len(gstin) - 4)}{gstin[-4:]}"


def _dt(iso: str) -> datetime:
    return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")


def _fmt_ts(iso: str) -> str:
    return _dt(iso).strftime("%d %b %Y at %H:%M")


def _forbidden(scn: Scenario, jurisdiction: str) -> list[str]:
    """Literals the answer must not contain under this jurisdiction.

    IN allows everything. EU denies personal tax ids and the personal contact
    details of named individuals; the business GSTIN is masked, not denied,
    so it is not listed here — masking is checked by the answer itself.
    """
    if jurisdiction != "EU":
        return []
    out: list[str] = []
    for party in (scn.seller, scn.buyer):
        out.append(party["pan"])
        out.append(party["contact"]["email"])
        out.append(party["contact"]["phone"])
    return sorted(set(out))


# ---------------------------------------------------------------------------
# Task specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskSpec:
    """One legal (bucket, label) task, with the scenario it requires."""

    name: str
    bucket: str
    label: str
    defect: str
    build: Callable[..., Built]
    difficulty: str = "medium"
    revised: bool = False
    evidence_lang: str | None = None
    jurisdictions: tuple[str, ...] = ("IN", "EU")
    weight: int = 1
    """Relative share within the bucket.

    Buckets are allocated equally, but a bucket whose tasks are mostly ``clean``
    would starve the defect labels. Weighting the defect tasks keeps every gold
    label above a usable sample size in both splits.
    """


# --- lookup -----------------------------------------------------------------


def _t_lookup_total(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    return {
        "question": f"What is the total invoice value for consignment {scn.consignment_ref}?",
        "question_lang": "en",
        "gold_answer": f"Invoice {inv['invoice_no']} totals {_inr(inv['invoice_total'])} [INV], comprising {_inr(inv['total_taxable_value'])} taxable value and {_inr(inv['total_tax'])} GST [INV].",
        "gold_facts": [
            _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
            _fact(2, "invoice", "invoice_total", inv["invoice_total"]),
            _fact(3, "invoice", "total_taxable_value", inv["total_taxable_value"]),
            _fact(4, "invoice", "total_tax", inv["total_tax"]),
        ],
    }


def _t_lookup_hsn(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    i = scn.rng.randrange(len(inv["items"]))
    item = inv["items"][i]
    return {
        "question": f"What HSN code is declared for line {item['line_no']} of invoice {inv['invoice_no']}?",
        "question_lang": "en",
        "gold_answer": f"Line {item['line_no']} of invoice {inv['invoice_no']} declares HSN code {item['hsn_code']}, described as {item['description']} [INV].",
        "gold_facts": [
            _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
            _fact(2, "invoice", f"items[{i}].hsn_code", item["hsn_code"]),
            _fact(3, "invoice", f"items[{i}].description", item["description"]),
        ],
    }


def _t_lookup_vehicle(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    return {
        "question": f"Which vehicle is carrying consignment {scn.consignment_ref}?",
        "question_lang": "en",
        "gold_answer": f"Consignment {scn.consignment_ref} is carried on vehicle {inv['vehicle_no']} [INV].",
        "gold_facts": [
            _fact(1, "invoice", "vehicle_no", inv["vehicle_no"]),
            _fact(2, "invoice", "consignment_ref", inv["consignment_ref"]),
        ],
    }


def _t_lookup_payment_terms(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    erp = docs["erp_order"]
    return {
        "question": f"What payment terms were agreed on purchase order {erp['po_no']}?",
        "question_lang": "en",
        "gold_answer": f"Purchase order {erp['po_no']} carries payment terms of {erp['payment_terms']} [ERP].",
        "gold_facts": [
            _fact(1, "erp_order", "po_no", erp["po_no"]),
            _fact(2, "erp_order", "payment_terms", erp["payment_terms"]),
        ],
    }


def _t_lookup_gstin(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    """Identity lookup. IN only — under EU this is a compliance question, not a lookup."""
    inv = docs["invoice"]
    return {
        "question": f"What is the seller's GSTIN on invoice {inv['invoice_no']}?",
        "question_lang": "en",
        "gold_answer": f"The seller on invoice {inv['invoice_no']}, {inv['seller']['legal_name']}, holds GSTIN {inv['seller']['gstin']} [INV].",
        "gold_facts": [
            _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
            _fact(2, "invoice", "seller.gstin", inv["seller"]["gstin"]),
            _fact(3, "invoice", "seller.legal_name", inv["seller"]["legal_name"]),
        ],
    }


# --- multi-hop --------------------------------------------------------------


def _t_mh_values_match(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, ewb = docs["invoice"], docs["eway_bill"]
    return {
        "question": f"Does the value declared on the e-way bill match the invoice total for consignment {scn.consignment_ref}?",
        "question_lang": "en",
        "gold_answer": f"Yes, the two agree: e-way bill {ewb['ewb_no']} declares {_inr(ewb['total_invoice_value'])} [EWB] and invoice {inv['invoice_no']} totals the same {_inr(inv['invoice_total'])} [INV].",
        "gold_facts": [
            _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
            _fact(2, "invoice", "invoice_total", inv["invoice_total"]),
            _fact(3, "eway_bill", "ewb_no", ewb["ewb_no"]),
            _fact(4, "eway_bill", "total_invoice_value", ewb["total_invoice_value"]),
            _fact(5, "eway_bill", "consignment_ref", ewb["consignment_ref"]),
        ],
    }


def _t_mh_values_mismatch(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, ewb = docs["invoice"], docs["eway_bill"]
    delta = round(abs(inv["invoice_total"] - ewb["total_invoice_value"]), 2)
    facts = [
        _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
        _fact(2, "invoice", "invoice_total", inv["invoice_total"]),
        _fact(3, "eway_bill", "ewb_no", ewb["ewb_no"]),
        _fact(4, "eway_bill", "total_invoice_value", ewb["total_invoice_value"]),
        _fact(5, "eway_bill", "consignment_ref", ewb["consignment_ref"]),
    ]
    answer = (
        f"No, they disagree: invoice {inv['invoice_no']} totals {_inr(inv['invoice_total'])} [INV] "
        f"but e-way bill {ewb['ewb_no']} declares {_inr(ewb['total_invoice_value'])} [EWB], "
        f"a discrepancy of {_inr(delta)}."
    )
    if "value_query" in ev:
        ref = ev["value_query"]["ref_id"]
        facts.append(
            _fact(
                6,
                "whatsapp_pod",
                f"{ref}.text",
                _span_text(docs, ev["value_query"]),
                ev["value_query"],
            )
        )
        answer += f" The accounts team raised the same discrepancy on the delivery thread [{ref}]."
    return {
        "question": f"Does the value declared on the e-way bill match the invoice total for consignment {scn.consignment_ref}?",
        "question_lang": "en",
        "gold_answer": answer,
        "gold_facts": facts,
    }


def _t_mh_ewb_exists(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    facts = [
        _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
        _fact(2, "invoice", "eway_bill_ref", inv["eway_bill_ref"]),
        _fact(3, "invoice", "consignment_ref", inv["consignment_ref"]),
    ]
    answer = (
        f"No — invoice {inv['invoice_no']} carries no e-way bill reference and none exists for "
        f"consignment {scn.consignment_ref} [INV], so the vehicle moved without a permit."
    )
    if "detained" in ev:
        ref = ev["detained"]["ref_id"]
        facts.append(
            _fact(
                4, "whatsapp_pod", f"{ref}.text", _span_text(docs, ev["detained"]), ev["detained"]
            )
        )
        answer += f" The driver confirmed on the thread that the vehicle was stopped at the check post for exactly this reason [{ref}]."
    return {
        "question": f"Was an e-way bill raised for consignment {scn.consignment_ref} before it moved?",
        "question_lang": "en",
        "gold_answer": answer,
        "gold_facts": facts,
    }


def _t_mh_po_quantity(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, erp = docs["invoice"], docs["erp_order"]
    qty_inv = sum(i["quantity"] for i in inv["items"])
    qty_po = sum(i["quantity_ordered"] for i in erp["items"])
    facts = [
        _fact(1, "erp_order", "po_no", erp["po_no"]),
        _fact(2, "invoice", "invoice_no", inv["invoice_no"]),
    ]
    n = 3
    for i in range(len(inv["items"])):
        facts.append(_fact(n, "invoice", f"items[{i}].quantity", inv["items"][i]["quantity"]))
        n += 1
        facts.append(
            _fact(
                n, "erp_order", f"items[{i}].quantity_ordered", erp["items"][i]["quantity_ordered"]
            )
        )
        n += 1
    return {
        "question": f"Was the quantity invoiced under {inv['invoice_no']} the same as the quantity ordered on {erp['po_no']}?",
        "question_lang": "en",
        "gold_answer": f"Yes, all {len(inv['items'])} line(s) agree: {qty_po:g} units were ordered on {erp['po_no']} [ERP] and {qty_inv:g} units were invoiced on {inv['invoice_no']} [INV] for consignment {scn.consignment_ref}.",
        "gold_facts": facts,
    }


# --- temporal ---------------------------------------------------------------


def _t_temporal_ok(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, ewb = docs["invoice"], docs["eway_bill"]
    gap = _dt(ewb["generated_at"]) - _dt(inv["issued_at"])
    hours = round(gap.total_seconds() / 3600, 1)
    return {
        "question": f"Was the e-way bill for consignment {scn.consignment_ref} generated before or after the tax invoice was issued?",
        "question_lang": "en",
        "gold_answer": f"After, so the sequence is correct: invoice {inv['invoice_no']} was issued on {_fmt_ts(inv['issued_at'])} [INV] and e-way bill {ewb['ewb_no']} was generated {hours:g} hours later, on {_fmt_ts(ewb['generated_at'])}, citing that invoice [EWB].",
        "gold_facts": [
            _fact(1, "invoice", "issued_at", inv["issued_at"]),
            _fact(2, "eway_bill", "generated_at", ewb["generated_at"]),
            _fact(3, "eway_bill", "doc_no", ewb["doc_no"]),
        ],
    }


def _t_temporal_ewb_first(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, ewb = docs["invoice"], docs["eway_bill"]
    gap = _dt(inv["issued_at"]) - _dt(ewb["generated_at"])
    hours = round(gap.total_seconds() / 3600, 1)
    return {
        "question": f"Was the e-way bill for consignment {scn.consignment_ref} generated before or after the tax invoice was issued?",
        "question_lang": "en",
        "gold_answer": f"Before, which is a sequence violation: e-way bill {ewb['ewb_no']} was generated on {_fmt_ts(ewb['generated_at'])} citing invoice {ewb['doc_no']} [EWB], but that invoice was only issued {hours:g} hours later, on {_fmt_ts(inv['issued_at'])} [INV]. The permit therefore references a document that did not yet exist [EWB].",
        "gold_facts": [
            _fact(1, "invoice", "issued_at", inv["issued_at"]),
            _fact(2, "invoice", "invoice_no", inv["invoice_no"]),
            _fact(3, "eway_bill", "generated_at", ewb["generated_at"]),
            _fact(4, "eway_bill", "doc_no", ewb["doc_no"]),
        ],
    }


def _t_temporal_pod_first(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    disp = _event(docs, "dispatched")
    deliv = _event(docs, "delivered")
    gap = round((_dt(disp["ts"]) - _dt(deliv["ts"])).total_seconds() / 3600, 1)
    facts = [
        _fact(1, "events", f"{disp['event_id']}.ts", disp["ts"]),
        _fact(2, "events", f"{deliv['event_id']}.ts", deliv["ts"]),
        _fact(3, "invoice", "consignment_ref", docs["invoice"]["consignment_ref"]),
    ]
    answer = (
        f"No — delivery for consignment {scn.consignment_ref} [INV] is recorded at "
        f"{_fmt_ts(deliv['ts'])} but dispatch only at {_fmt_ts(disp['ts'])}, {gap:g} hours later "
        f"[TIMELINE], so the goods are logged as delivered before they left the origin and the "
        f"proof of delivery is backdated."
    )
    if "sequence_query" in ev:
        ref = ev["sequence_query"]["ref_id"]
        facts.append(
            _fact(
                4,
                "whatsapp_pod",
                f"{ref}.text",
                _span_text(docs, ev["sequence_query"]),
                ev["sequence_query"],
            )
        )
        answer += f" The accounts team queried the same ordering on the delivery thread [{ref}]."
    return {
        "question": f"Is the delivery timeline for consignment {scn.consignment_ref} internally consistent?",
        "question_lang": "en",
        "gold_answer": answer,
        "gold_facts": facts,
    }


def _t_temporal_expiry(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    ewb = docs["eway_bill"]
    deliv = _event(docs, "delivered")
    gap = round((_dt(deliv["ts"]) - _dt(ewb["valid_until"])).total_seconds() / 3600, 1)
    facts = [
        _fact(1, "eway_bill", "ewb_no", ewb["ewb_no"]),
        _fact(2, "eway_bill", "valid_until", ewb["valid_until"]),
        _fact(3, "eway_bill", "status", ewb["status"]),
        _fact(4, "events", f"{deliv['event_id']}.ts", deliv["ts"]),
    ]
    answer = (
        f"No — e-way bill {ewb['ewb_no']} was valid until {_fmt_ts(ewb['valid_until'])} and is now "
        f"marked {ewb['status']} [EWB], but delivery is recorded at {_fmt_ts(deliv['ts'])}, "
        f"{gap:g} hours after expiry [TIMELINE]."
    )
    if ewb["extensions"]:
        first = ewb["extensions"][0]
        answer += (
            f" One extension was recorded on {_fmt_ts(first['extended_at'])} for "
            f"{first['reason'].lower()}, which was still insufficient [EWB]."
        )
    if "expired" in ev:
        ref = ev["expired"]["ref_id"]
        facts.append(
            _fact(5, "whatsapp_pod", f"{ref}.text", _span_text(docs, ev["expired"]), ev["expired"])
        )
        answer += f" The lapse was noted on the delivery thread at the time [{ref}]."
    return {
        "question": f"Were the goods for consignment {scn.consignment_ref} delivered while the e-way bill was still valid?",
        "question_lang": "en",
        "gold_answer": answer,
        "gold_facts": facts,
    }


def _t_temporal_revision(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv, ewb = docs["invoice"], docs["eway_bill"]
    rev = _event(docs, "invoice_revised")
    return {
        "question": f"Was the e-way bill for consignment {scn.consignment_ref} generated before or after the invoice was revised?",
        "question_lang": "en",
        "gold_answer": f"Invoice {inv['invoice_no']} is revision {inv['revision_no']}, superseding {inv['supersedes']} which was originally issued on {_fmt_ts(inv['original_issued_at'])} [INV]. The revision was raised on {_fmt_ts(rev['ts'])} [TIMELINE], and e-way bill {ewb['ewb_no']} was generated afterwards on {_fmt_ts(ewb['generated_at'])} [EWB], so the permit post-dates the revision.",
        "gold_facts": [
            _fact(1, "invoice", "revision_no", inv["revision_no"]),
            _fact(2, "invoice", "supersedes", inv["supersedes"]),
            _fact(3, "invoice", "original_issued_at", inv["original_issued_at"]),
            _fact(4, "events", f"{rev['event_id']}.ts", rev["ts"]),
            _fact(5, "eway_bill", "generated_at", ewb["generated_at"]),
        ],
    }


# --- cross-lingual ----------------------------------------------------------


def _t_xl_delivered(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    span = ev["delivered"]
    text = _span_text(docs, span)
    sender = _sender_of(docs, span["ref_id"])
    q_lang = scn.rng.choice(["en", "hi-en", "hi"])
    question = {
        "en": f"Did anyone confirm in the delivery thread that consignment {scn.consignment_ref} was actually received?",
        "hi-en": f"Kya thread mein kisi ne confirm kiya hai ki consignment {scn.consignment_ref} deliver ho gaya?",
        "hi": f"क्या चैट में किसी ने पुष्टि की है कि खेप {scn.consignment_ref} पहुँच गई?",
    }[q_lang]
    return {
        "question": question,
        "question_lang": q_lang,
        "gold_answer": f'Yes — in message {span["ref_id"]} on the thread for consignment {docs["invoice"]["consignment_ref"]} [INV], {sender} states "{span["span"]}", confirming the goods were received [{span["ref_id"]}].',
        "gold_facts": [
            _fact(1, "whatsapp_pod", f"{span['ref_id']}.text", text, span),
            _fact(2, "invoice", "consignment_ref", docs["invoice"]["consignment_ref"]),
        ],
    }


def _t_xl_detained(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    span = ev["detained"]
    text = _span_text(docs, span)
    sender = _sender_of(docs, span["ref_id"])
    q_lang = scn.rng.choice(["en", "hi-en"])
    question = {
        "en": f"What did the driver report about consignment {scn.consignment_ref} while in transit?",
        "hi-en": f"Driver ne consignment {scn.consignment_ref} ke baare mein kya bataya raaste mein?",
    }[q_lang]
    return {
        "question": question,
        "question_lang": q_lang,
        "gold_answer": f'The driver, {sender}, reported in message {span["ref_id"]} that the vehicle was stopped at a check post because no e-way bill had been generated: "{span["span"]}" [{span["ref_id"]}]. The invoice confirms it, carrying no e-way bill reference for consignment {scn.consignment_ref} [INV], and the consignment did not complete delivery.',
        "gold_facts": [
            _fact(1, "whatsapp_pod", f"{span['ref_id']}.text", text, span),
            _fact(2, "invoice", "eway_bill_ref", docs["invoice"]["eway_bill_ref"]),
        ],
    }


def _t_xl_value_query(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    span = ev["value_query"]
    text = _span_text(docs, span)
    sender = _sender_of(docs, span["ref_id"])
    inv, ewb = docs["invoice"], docs["eway_bill"]
    q_lang = scn.rng.choice(["en", "hi-en", "hi"])
    question = {
        "en": f"Did anyone on the delivery thread raise a concern about the paperwork for consignment {scn.consignment_ref}, and was it justified?",
        "hi-en": f"Kya kisi ne consignment {scn.consignment_ref} ke paperwork pe koi objection uthaya thread mein? Aur kya wo sahi tha?",
        "hi": f"क्या चैट में किसी ने खेप {scn.consignment_ref} के कागज़ात पर सवाल उठाया था, और क्या वह सही था?",
    }[q_lang]
    return {
        "question": question,
        "question_lang": q_lang,
        "gold_answer": f'Yes, and it was justified: in message {span["ref_id"]}, {sender} flagged that "{span["span"]}" [{span["ref_id"]}]. The documents confirm it — invoice {inv["invoice_no"]} totals {_inr(inv["invoice_total"])} [INV] while e-way bill {ewb["ewb_no"]} declares {_inr(ewb["total_invoice_value"])} [EWB].',
        "gold_facts": [
            _fact(1, "whatsapp_pod", f"{span['ref_id']}.text", text, span),
            _fact(2, "invoice", "invoice_total", inv["invoice_total"]),
            _fact(3, "eway_bill", "total_invoice_value", ewb["total_invoice_value"]),
        ],
    }


def _t_xl_sequence(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    span = ev["sequence_query"]
    text = _span_text(docs, span)
    sender = _sender_of(docs, span["ref_id"])
    disp, deliv = _event(docs, "dispatched"), _event(docs, "delivered")
    q_lang = scn.rng.choice(["en", "hi-en"])
    question = {
        "en": f"Did anyone on the delivery thread question the timeline for consignment {scn.consignment_ref}, and were they right?",
        "hi-en": f"Kya kisi ne consignment {scn.consignment_ref} ki timeline pe sawaal uthaya tha? Aur kya wo sahi the?",
    }[q_lang]
    return {
        "question": question,
        "question_lang": q_lang,
        "gold_answer": f'Yes, and they were right: in message {span["ref_id"]}, {sender} noted "{span["span"]}" [{span["ref_id"]}]. The timeline confirms it — delivery is recorded at {_fmt_ts(deliv["ts"])} but dispatch only at {_fmt_ts(disp["ts"])} [TIMELINE].',
        "gold_facts": [
            _fact(1, "whatsapp_pod", f"{span['ref_id']}.text", text, span),
            _fact(2, "events", f"{disp['event_id']}.ts", disp["ts"]),
            _fact(3, "events", f"{deliv['event_id']}.ts", deliv["ts"]),
        ],
    }


# --- compliance -------------------------------------------------------------


def _t_comp_pan(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    seller = inv["seller"]
    facts = [
        _fact(1, "invoice", "seller.legal_name", seller["legal_name"]),
        _fact(2, "invoice", "seller.pan", seller["pan"]),
        _fact(3, "invoice", "seller.gstin", seller["gstin"]),
    ]
    question = f"Can the seller's PAN on invoice {inv['invoice_no']} be included in a response shared with the counterparty's finance team?"
    if jur == "EU":
        answer = (
            f"No — under the EU emission policy the PAN recorded for {seller['legal_name']} is a personal tax "
            f"identifier and is denied outright, so it must not appear in the response at any point [INV]. "
            f"The seller's GSTIN may be included only in masked form, as {_mask_gstin(seller['gstin'])}, and the "
            f"named contact's email address and phone number must also be withheld [INV]. Non-personal fields such "
            f"as the invoice total of {_inr(inv['invoice_total'])} and the HSN codes may be disclosed in full [INV]."
        )
    else:
        answer = (
            f"Yes — under the Indian emission policy both tax identifiers may be disclosed in full: the seller "
            f"{seller['legal_name']} holds PAN {seller['pan']} and GSTIN {seller['gstin']} [INV]. No masking is "
            f"required for a domestic disclosure [INV]."
        )
    return {"question": question, "question_lang": "en", "gold_answer": answer, "gold_facts": facts}


def _t_comp_fields(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    seller, buyer = inv["seller"], inv["buyer"]
    facts = [
        _fact(1, "invoice", "invoice_no", inv["invoice_no"]),
        _fact(2, "invoice", "seller.pan", seller["pan"]),
        _fact(3, "invoice", "seller.gstin", seller["gstin"]),
        _fact(4, "invoice", "seller.contact.email", seller["contact"]["email"]),
        _fact(5, "invoice", "buyer.pan", buyer["pan"]),
    ]
    question = f"Which fields on invoice {inv['invoice_no']} must be withheld or masked before the document is emitted?"
    if jur == "EU":
        answer = (
            f"Four categories must be restricted on invoice {inv['invoice_no']} [INV]. The seller's and buyer's "
            f"PANs are denied outright and must not be emitted [INV]. Both GSTINs must be masked to their last four "
            f"characters — the seller's as {_mask_gstin(seller['gstin'])} and the buyer's as "
            f"{_mask_gstin(buyer['gstin'])} [INV]. The named contacts' email addresses and phone numbers are personal "
            f"data and must be withheld [INV]. Everything else — line items, HSN codes, quantities, the tax breakdown "
            f"and the total of {_inr(inv['invoice_total'])} — may be emitted unchanged [INV]."
        )
    else:
        answer = (
            f"None — under the Indian emission policy every field on invoice {inv['invoice_no']} may be emitted "
            f"unchanged, including the seller's PAN {seller['pan']} and GSTIN {seller['gstin']}, the buyer's PAN "
            f"{buyer['pan']}, the contact details, and the invoice total of {_inr(inv['invoice_total'])} [INV]."
        )
    return {"question": question, "question_lang": "en", "gold_answer": answer, "gold_facts": facts}


def _t_comp_contact(scn: Scenario, docs: dict, ev: dict, jur: str) -> Built:
    inv = docs["invoice"]
    buyer = inv["buyer"]
    facts = [
        _fact(1, "invoice", "buyer.contact.name", buyer["contact"]["name"]),
        _fact(2, "invoice", "buyer.contact.email", buyer["contact"]["email"]),
        _fact(3, "invoice", "buyer.contact.phone", buyer["contact"]["phone"]),
    ]
    question = f"May the buyer-side contact details on invoice {inv['invoice_no']} be quoted when escalating this consignment externally?"
    if jur == "EU":
        answer = (
            f"No — the buyer-side contact on invoice {inv['invoice_no']} is a named natural person, so their email "
            f"address and telephone number are personal data and must be withheld under the EU emission policy [INV]. "
            f"Refer to the role instead — the warehouse contact at {buyer['legal_name']} — or route the escalation "
            f"through the corporate address in {buyer['address']['city']}, which is a business detail and may be "
            f"quoted [INV]. The buyer's GSTIN may accompany the escalation only in masked form, as "
            f"{_mask_gstin(buyer['gstin'])} [INV]."
        )
    else:
        answer = (
            f"Yes — under the Indian emission policy the buyer-side contact on invoice {inv['invoice_no']} may be "
            f"quoted in full: {buyer['contact']['name']}, {buyer['contact']['email']}, "
            f"{buyer['contact']['phone']} [INV]."
        )
    return {"question": question, "question_lang": "en", "gold_answer": answer, "gold_facts": facts}


# ---------------------------------------------------------------------------
# The legal matrix. 11 of 25 (bucket, label) combinations exist.
# ---------------------------------------------------------------------------

TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("lookup_total", "lookup", "clean", "none", _t_lookup_total, "easy"),
    TaskSpec("lookup_hsn", "lookup", "clean", "none", _t_lookup_hsn, "easy"),
    TaskSpec("lookup_vehicle", "lookup", "clean", "none", _t_lookup_vehicle, "easy"),
    TaskSpec("lookup_terms", "lookup", "clean", "none", _t_lookup_payment_terms, "easy"),
    TaskSpec(
        "lookup_gstin", "lookup", "clean", "none", _t_lookup_gstin, "easy", jurisdictions=("IN",)
    ),
    TaskSpec("mh_match", "multi-hop", "clean", "none", _t_mh_values_match, "medium"),
    TaskSpec("mh_po_qty", "multi-hop", "clean", "none", _t_mh_po_quantity, "medium"),
    TaskSpec(
        "mh_mismatch",
        "multi-hop",
        "value_mismatch",
        "value_mismatch",
        _t_mh_values_mismatch,
        "medium",
        weight=2,
    ),
    TaskSpec(
        "mh_no_ewb", "multi-hop", "missing_ewb", "missing_ewb", _t_mh_ewb_exists, "medium", weight=2
    ),
    TaskSpec("tmp_ok", "temporal", "clean", "none", _t_temporal_ok, "medium"),
    TaskSpec(
        "tmp_ewb_first",
        "temporal",
        "temporal_violation",
        "ewb_before_invoice",
        _t_temporal_ewb_first,
        "hard",
        weight=2,
    ),
    TaskSpec(
        "tmp_pod_first",
        "temporal",
        "temporal_violation",
        "pod_before_dispatch",
        _t_temporal_pod_first,
        "hard",
        weight=2,
    ),
    TaskSpec(
        "tmp_expiry",
        "temporal",
        "temporal_violation",
        "delivery_after_expiry",
        _t_temporal_expiry,
        "hard",
        weight=2,
    ),
    TaskSpec(
        "tmp_revision", "temporal", "clean", "none", _t_temporal_revision, "hard", revised=True
    ),
    TaskSpec(
        "xl_delivered",
        "cross-lingual",
        "clean",
        "none",
        _t_xl_delivered,
        "medium",
        evidence_lang="hi-en",
    ),
    TaskSpec(
        "xl_delivered_hi",
        "cross-lingual",
        "clean",
        "none",
        _t_xl_delivered,
        "hard",
        evidence_lang="hi",
    ),
    TaskSpec(
        "xl_detained",
        "cross-lingual",
        "missing_ewb",
        "missing_ewb",
        _t_xl_detained,
        "hard",
        evidence_lang="hi",
        weight=2,
    ),
    TaskSpec(
        "xl_value",
        "cross-lingual",
        "value_mismatch",
        "value_mismatch",
        _t_xl_value_query,
        "hard",
        evidence_lang="hi-en",
        weight=2,
    ),
    TaskSpec(
        "xl_sequence",
        "cross-lingual",
        "temporal_violation",
        "pod_before_dispatch",
        _t_xl_sequence,
        "hard",
        evidence_lang="hi-en",
        weight=2,
    ),
    TaskSpec("comp_pan", "compliance", "compliance_case", "none", _t_comp_pan, "hard"),
    TaskSpec("comp_fields", "compliance", "compliance_case", "none", _t_comp_fields, "hard"),
    TaskSpec("comp_contact", "compliance", "compliance_case", "none", _t_comp_contact, "hard"),
)


# ---------------------------------------------------------------------------
# Document navigation helpers used by task builders
# ---------------------------------------------------------------------------


def _event(docs: dict, kind: str) -> dict:
    for e in docs["_events"]:
        if e["type"] == kind:
            return e
    raise KeyError(f"no {kind} event on this timeline")


def _span_text(docs: dict, span: dict) -> str:
    for m in docs["whatsapp_pod"]["messages"]:
        if m["msg_id"] == span["ref_id"]:
            return m["text"]
    raise KeyError(f"no message {span['ref_id']}")


def _sender_of(docs: dict, msg_id: str) -> str:
    for m in docs["whatsapp_pod"]["messages"]:
        if m["msg_id"] == msg_id:
            return m["sender_name"]
    raise KeyError(msg_id)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def assemble_case(case_id: str, spec: TaskSpec, jurisdiction: str, seed: int) -> dict:
    """Build one complete, self-consistent case.

    Args:
        case_id: Identifier of the form ``ccbench-0001``.
        spec: The task to instantiate.
        jurisdiction: ``IN`` or ``EU``.
        seed: Seed for this case; all randomness derives from it.

    Returns:
        A case dictionary conforming to schema 0.2.
    """
    if jurisdiction not in spec.jurisdictions:
        raise ValueError(f"task {spec.name} is not defined for jurisdiction {jurisdiction}")

    scn = build_scenario(seed=seed, defect=spec.defect, revised=spec.revised)
    thread, evidence = build_thread(scn, evidence_lang=spec.evidence_lang)
    documents = {
        "invoice": build_invoice(scn),
        "eway_bill": build_eway_bill(scn),
        "erp_order": build_erp_order(scn),
        "whatsapp_pod": thread,
        "flag": build_flag(scn),
    }
    events = build_events(scn, thread, evidence)

    nav = dict(documents)
    nav["_events"] = events
    built = spec.build(scn, nav, evidence, jurisdiction)

    case = {
        "schema_version": "0.2",
        "case_id": case_id,
        "bucket": spec.bucket,
        "jurisdiction": jurisdiction,
        "documents": documents,
        "events": events,
        "question": built["question"],
        "question_lang": built["question_lang"],
        "gold_answer": built["gold_answer"],
        "gold_facts": built["gold_facts"],
        "gold_label": spec.label,
        "difficulty": spec.difficulty,
        "must_not_appear": _forbidden(scn, jurisdiction),
        "provenance": {
            "generator_version": GENERATOR_VERSION,
            "seed": seed,
            "notes": f"task={spec.name} defect={spec.defect}",
        },
    }
    return case


# Fields withheld from the public test split.
_WITHHELD = ("gold_answer", "gold_facts", "gold_label", "bucket", "difficulty", "must_not_appear")


def redact(case: dict) -> dict:
    """Public view of a test case: documents and question only.

    Bucket and difficulty are withheld alongside the answers — publishing them
    would let a method condition on the task type it is about to be scored on.
    The scorer holds the full case privately.
    """
    return {k: v for k, v in case.items() if k not in _WITHHELD}


def generate_dataset(
    output_dir: str | Path,
    n_cases: int = 200,
    dev_fraction: float = 0.5,
    seed: int = 20260815,
) -> dict:
    """Generate the full CCBench dataset, stratified and split.

    Cases are laid down task-by-task in a round robin so that dev and test are
    balanced on bucket, label and jurisdiction by construction rather than by
    luck.

    Args:
        output_dir: Directory that will contain ``dev/`` and ``test/``.
        n_cases: Total number of cases.
        dev_fraction: Fraction assigned to dev.
        seed: Master seed.

    Returns:
        A summary dict with counts and the split manifest.
    """
    out = Path(output_dir)
    (out / "dev").mkdir(parents=True, exist_ok=True)
    (out / "test").mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    # Build the (task, jurisdiction) plan. Cycling over buckets first gives an
    # exactly equal bucket count; within a bucket the tasks round-robin, and
    # within a task the jurisdictions round-robin, so every task appears under
    # both legal regimes wherever it is defined.
    buckets = ["lookup", "multi-hop", "temporal", "cross-lingual", "compliance"]
    by_bucket = {b: [t for t in TASKS if t.bucket == b for _ in range(t.weight)] for b in buckets}
    bucket_cursor = dict.fromkeys(buckets, 0)
    task_cursor: Counter[str] = Counter()

    plan: list[tuple[TaskSpec, str]] = []
    for i in range(n_cases):
        bucket = buckets[i % len(buckets)]
        specs = by_bucket[bucket]
        spec = specs[bucket_cursor[bucket] % len(specs)]
        bucket_cursor[bucket] += 1
        jur = spec.jurisdictions[task_cursor[spec.name] % len(spec.jurisdictions)]
        task_cursor[spec.name] += 1
        plan.append((spec, jur))
    rng.shuffle(plan)

    n_dev = int(n_cases * dev_fraction)
    cases: list[dict] = []
    for idx, (spec, jur) in enumerate(plan, start=1):
        case = assemble_case(f"ccbench-{idx:04d}", spec, jur, seed=seed + idx * 97)
        cases.append(case)

    # Stratified split: order by (bucket, label, jurisdiction) then deal
    # alternately into dev and test so both splits carry the same mix.
    cases.sort(key=lambda c: (c["bucket"], c["gold_label"], c["jurisdiction"], c["case_id"]))
    dev, test = [], []
    for n, case in enumerate(cases):
        (dev if len(dev) < n_dev and n % 2 == 0 else test).append(case)
    while len(dev) < n_dev and test:
        dev.append(test.pop())
    dev.sort(key=lambda c: c["case_id"])
    test.sort(key=lambda c: c["case_id"])

    for case in dev:
        _write(out / "dev" / f"{case['case_id']}.json", case)
    for case in test:
        _write(out / "test" / f"{case['case_id']}.json", redact(case))

    # Private answer key for the test split — never distributed.
    _write(out / "test_gold.private.json", {c["case_id"]: c for c in test})

    manifest = {
        "schema_version": "0.2",
        "generator_version": GENERATOR_VERSION,
        "master_seed": seed,
        "dev": [c["case_id"] for c in dev],
        "test": [c["case_id"] for c in test],
        "metadata": {
            "total_cases": len(cases),
            "dev_cases": len(dev),
            "test_cases": len(test),
            "version": "1.0.0",
            "license": "CC-BY-SA 4.0",
            "test_gold_withheld": list(_WITHHELD),
        },
    }
    _write(out.parent / "splits" / "splits.json", manifest)
    return manifest


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

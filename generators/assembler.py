"""Case assembler — combines generated documents into full CCBench cases.

Deterministically creates cases with questions, gold answers, and labels.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from . import invoice, ewaybill, erp, whatsapp, noise, gstin


def _question_for_bucket(bucket: str, documents: dict) -> str:
    """Generate a question based on the task bucket."""
    inv = documents["invoice"]
    ewb = documents.get("eway_bill")
    erp_ord = documents.get("erp_order")
    cons_ref = inv["consignment_ref"]

    questions = {
        "lookup": [
            f"What is the GSTIN of the seller on invoice {inv['invoice_no']}?",
            f"What HSN code is used for the item in invoice {inv['invoice_no']}?",
            f"What is the vehicle number associated with consignment {cons_ref}?",
        ],
        "multi-hop": [
            f"Does the e-way bill amount match the invoice total for consignment {cons_ref}?",
            f"Does the quantity ordered in the PO match the quantity invoiced for consignment {cons_ref}?",
            f"Is the buyer on the invoice the same as the buyer on the ERP order for {cons_ref}?",
        ],
        "temporal": [
            f"Was the e-way bill generated before the invoice date for consignment {cons_ref}?",
            f"Did the delivery happen within the expected delivery window for PO {erp_ord['po_no'] if erp_ord else 'N/A'}?",
        ],
        "cross-lingual": [
            f"What did the driver report about the delivery status for consignment {cons_ref}?",
            f"Did the warehouse confirm receipt in the WhatsApp thread for consignment {cons_ref}?",
        ],
        "compliance": [
            f"Can the full PAN of the seller be disclosed in a response to an EU client for consignment {cons_ref}?",
            f"Under EU GDPR rules, which fields from invoice {inv['invoice_no']} must be masked?",
        ],
    }
    return random.choice(questions.get(bucket, questions["lookup"]))


def _gold_answer_for_bucket(
    bucket: str,
    documents: dict,
    label: str,
) -> str:
    """Generate a gold answer based on bucket and label."""
    inv = documents["invoice"]
    ewb = documents.get("eway_bill")

    if bucket == "lookup":
        return f"The GSTIN of the seller is {inv['seller']['gstin']}."

    if bucket == "multi-hop" and label == "value_mismatch":
        return (
            f"No, the totals do not match. The invoice total is "
            f"₹{inv['invoice_total']:,.2f} while the e-way bill shows "
            f"₹{ewb['total_value']:,.2f}. The discrepancy is "
            f"₹{abs(inv['invoice_total'] - ewb['total_value']):,.2f}."
        )

    if bucket == "multi-hop" and label == "clean":
        return (
            f"Yes, the amounts match. Both the invoice and e-way bill "
            f"show ₹{inv['invoice_total']:,.2f}."
        )

    if bucket == "compliance":
        return (
            "No, under EU GDPR, the full PAN must be masked. Only the "
            "last 4 digits may be disclosed. The full GSTIN may be shown "
            "as it is a business identifier, but individual PAN components "
            "require masking."
        )

    return "Answer not yet implemented for this bucket/label combination."


def _gold_facts(documents: dict) -> list[str]:
    """Extract gold facts from documents."""
    facts = []
    inv = documents.get("invoice")
    ewb = documents.get("eway_bill")
    erp_ord = documents.get("erp_order")

    if inv:
        facts.append(f"invoice.invoice_no = {inv['invoice_no']}")
        facts.append(f"invoice.invoice_total = {inv['invoice_total']}")
        facts.append(f"invoice.seller.gstin = {inv['seller']['gstin']}")
        facts.append(f"invoice.consignment_ref = {inv['consignment_ref']}")

    if ewb:
        facts.append(f"eway_bill.ewb_no = {ewb['ewb_no']}")
        facts.append(f"eway_bill.total_value = {ewb['total_value']}")
        facts.append(f"eway_bill.consignment_ref = {ewb['consignment_ref']}")

    if erp_ord:
        facts.append(f"erp_order.po_no = {erp_ord['po_no']}")
        facts.append(f"erp_order.consignment_ref = {erp_ord['consignment_ref']}")

    return facts


def assemble_case(
    case_id: str,
    bucket: str,
    jurisdiction: str,
    label: str,
    seed: int,
    noise_level: str = "low",
) -> dict:
    """Assemble a complete CCBench case from generated documents.

    Args:
        case_id: Unique case identifier.
        bucket: Task bucket.
        jurisdiction: "IN" or "EU".
        label: Gold label (clean, value_mismatch, etc.).
        seed: Random seed for full reproducibility.
        noise_level: "low", "medium", or "high".

    Returns:
        Complete case dictionary matching CCBench schema.
    """
    random.seed(seed)

    # Generate linked documents
    inv = invoice.generate_invoice(seed=seed, mismatch=(label == "value_mismatch"))
    ewb = ewaybill.generate_eway_bill(
        inv,
        seed=seed,
        mismatch=(label == "value_mismatch"),
        missing=(label == "missing_ewb"),
    )
    erp_ord = erp.generate_erp_order(inv, seed=seed)
    wa = whatsapp.generate_whatsapp(inv, ewb, seed=seed)

    # Link invoice to e-way bill
    if ewb:
        inv["eway_bill_ref"] = ewb["ewb_no"]

    # Assemble documents
    documents = {
        "invoice": inv,
        "eway_bill": ewb,
        "erp_order": erp_ord,
    }
    if wa:
        documents["whatsapp_pod"] = wa

    # Inject noise
    for doc in documents.values():
        if isinstance(doc, dict):
            noise.inject_noise(doc, noise_level)

    # Generate question and gold answer
    question = _question_for_bucket(bucket, documents)
    gold_answer = _gold_answer_for_bucket(bucket, documents, label)
    gold_facts = _gold_facts(documents)

    # Difficulty based on label
    difficulty = "easy" if label == "clean" else ("hard" if label in ("temporal_violation", "compliance_case") else "medium")

    return {
        "case_id": case_id,
        "bucket": bucket,
        "jurisdiction": jurisdiction,
        "documents": documents,
        "question": question,
        "gold_answer": gold_answer,
        "gold_facts": gold_facts,
        "gold_label": label,
        "difficulty": difficulty,
    }


def generate_dataset(
    output_dir: str,
    n_cases: int = 200,
    dev_fraction: float = 0.5,
    seed: int = 42,
) -> None:
    """Generate the full CCBench dataset.

    Args:
        output_dir: Directory to write cases (dev/ and test/ subdirs).
        n_cases: Total number of cases to generate.
        dev_fraction: Fraction of cases for dev split (rest goes to test).
        seed: Master random seed.
    """
    random.seed(seed)
    output = Path(output_dir)
    (output / "dev").mkdir(parents=True, exist_ok=True)
    (output / "test").mkdir(parents=True, exist_ok=True)

    buckets = ["lookup", "multi-hop", "temporal", "cross-lingual", "compliance"]
    labels = ["clean", "value_mismatch", "missing_ewb", "temporal_violation", "compliance_case"]
    jurisdictions = ["IN", "EU"]

    case_ids = list(range(1, n_cases + 1))
    random.shuffle(case_ids)
    n_dev = int(n_cases * dev_fraction)
    dev_ids = set(case_ids[:n_dev])

    for i in range(1, n_cases + 1):
        bucket = random.choice(buckets)
        jurisdiction = random.choice(jurisdictions)
        label = random.choice(labels)

        case = assemble_case(
            case_id=f"ccbench-{i:04d}",
            bucket=bucket,
            jurisdiction=jurisdiction,
            label=label,
            seed=seed + i,
        )

        split = "dev" if i in dev_ids else "test"
        out_path = output / split / f"ccbench-{i:04d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(case, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {n_cases} cases: {n_dev} dev + {n_cases - n_dev} test")
    print(f"📁 Output: {output.absolute()}")

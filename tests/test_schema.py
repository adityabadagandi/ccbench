"""Tests for benchmark schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.schema.models import (
    Bucket,
    Case,
    CaseCorpus,
    ContextBundle,
    GoldLabel,
    Jurisdiction,
    Node,
    Retriever,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "benchmark" / "schema" / "case.schema.json"
DEV_CASES_DIR = REPO_ROOT / "benchmark" / "cases" / "dev"


def test_case_schema_file_exists() -> None:
    """The JSON Schema for cases must exist."""
    assert SCHEMA_PATH.exists(), f"Schema not found at {SCHEMA_PATH}"


def test_case_schema_is_valid_json() -> None:
    """The schema file must be parseable JSON."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    assert schema.get("title") == "CCBenchCase"


def test_dev_cases_validate_as_pydantic() -> None:
    """All dev cases must validate against the Pydantic model."""
    for path in sorted(DEV_CASES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        case = Case.model_validate(data)
        assert case.case_id == data["case_id"]
        assert isinstance(case.bucket, Bucket)
        assert isinstance(case.jurisdiction, Jurisdiction)
        assert isinstance(case.gold_label, GoldLabel)


def test_case_invalid_bucket_rejected() -> None:
    """An invalid bucket value must fail Pydantic validation."""
    base_case = {
        "case_id": "ccbench-test-0001",
        "bucket": "not-a-bucket",
        "jurisdiction": "IN",
        "documents": {
            "invoice": {
                "invoice_no": "INV-TEST-001",
                "date": "2024-01-01",
                "seller": {
                    "name": "Seller",
                    "gstin": "07AABCU9603R1ZX",
                    "address": "Delhi",
                },
                "buyer": {
                    "name": "Buyer",
                    "gstin": "27AADFP1234H1Z5",
                    "address": "Mumbai",
                },
                "items": [
                    {
                        "description": "Item",
                        "hsn_code": "3917",
                        "quantity": 1,
                        "unit": "pcs",
                        "rate_per_unit": 100,
                        "taxable_value": 100,
                        "cgst_rate": 9,
                        "sgst_rate": 9,
                        "cgst_amount": 9,
                        "sgst_amount": 9,
                    }
                ],
                "total_taxable_value": 100,
                "total_cgst": 9,
                "total_sgst": 9,
                "invoice_total": 118,
                "vehicle_no": "DL01AB1234",
                "consignment_ref": "CONS-TEST-001",
            },
            "erp_order": {
                "po_no": "PO-TEST-001",
                "po_date": "2024-01-01",
                "buyer": "Buyer",
                "vendor_code": "VND-001",
                "vendor_name": "Seller",
                "items": [
                    {
                        "item_code": "ITEM-001",
                        "description": "Item",
                        "quantity_ordered": 1,
                        "unit": "pcs",
                        "unit_price": 100,
                        "total_value": 100,
                        "expected_delivery": "2024-01-10",
                    }
                ],
                "po_total": 100,
                "payment_terms": "Net 30 days",
                "status": "fulfilled",
                "invoice_refs": ["INV-TEST-001"],
                "consignment_ref": "CONS-TEST-001",
            },
        },
        "question": "What is the invoice total?",
        "gold_answer": "118",
        "gold_facts": ["invoice.invoice_total = 118"],
        "gold_label": "clean",
    }
    with pytest.raises(ValidationError):
        Case.model_validate(base_case)


def test_domain_models_construct() -> None:
    """Core domain dataclasses must construct with defaults."""
    from benchmark.schema.models import (
        ErpOrder,
        EWayBill,
        Finding,
        Invoice,
        Message,
    )

    invoice = Invoice(invoice_no="INV-1", consignment_ref="CONS-1", value_eur=100.0)
    ewb = EWayBill(ewb_no="EWB-1", consignment_ref="CONS-1", declared_eur=100.0)
    erp = ErpOrder(order_no="PO-1", consignment_ref="CONS-1", expected_eur=100.0)
    msg = Message(msg_id="M-1", consignment_ref="CONS-1", text="hello", lang="en")
    finding = Finding(
        kind="value_mismatch",
        consignment_ref="CONS-1",
        severity="high",
        confidence=0.95,
    )
    assert invoice.pan is None
    assert ewb.doc_ref is None
    assert erp.ts is None
    assert msg.lang == "en"
    assert finding.detail == {}


def test_context_bundle_contract() -> None:
    """ContextBundle must accept the frozen field set."""
    node = Node(
        id="INV-1",
        type="Invoice",
        consignment_ref="CONS-1",
        fields={"invoice_no": "INV-1"},
        confidence=1.0,
        ts=None,
        provenance="test",
    )
    bundle = ContextBundle(
        query="test query",
        nodes=[node],
        llm_context="[INV-1] Invoice",
        citations=["INV-1"],
        tokens=10,
        budget=1000,
        jurisdiction="IN",
    )
    assert bundle.budget >= bundle.tokens
    assert bundle.jurisdiction in ("IN", "EU")


def test_corpus_and_protocol_types_exist() -> None:
    """CaseCorpus and Retriever protocol must be importable."""
    corpus = CaseCorpus()
    assert hasattr(corpus, "cases")
    assert hasattr(Retriever, "retrieve")

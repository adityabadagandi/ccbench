"""Tests for benchmark schema validation (schema 0.2).

These tests are deliberately adversarial about the failure modes that shipped
in 0.1: placeholder answers, labels that no document realises, gold facts that
do not resolve, and EU cases with nothing declared as denied.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.schema.models import (
    SCHEMA_VERSION,
    Bucket,
    Case,
    CaseCorpus,
    ContextBundle,
    GoldLabel,
    Jurisdiction,
    Node,
    PublicCase,
    Retriever,
)
from benchmark.validate import LEGAL_COMBINATIONS, resolve, validate_dataset
from generators.assembler import TASKS, assemble_case, redact

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "benchmark" / "schema" / "case.schema.json"
CASES_ROOT = REPO_ROOT / "benchmark" / "cases"
DEV_CASES_DIR = CASES_ROOT / "dev"


@pytest.fixture(scope="module")
def sample_case() -> dict:
    """A freshly generated compliance case under EU rules."""
    spec = next(t for t in TASKS if t.name == "comp_pan")
    return assemble_case("ccbench-9001", spec, "EU", seed=4242)


# --- schema file ------------------------------------------------------------


def test_case_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"Schema not found at {SCHEMA_PATH}"


def test_case_schema_is_valid_json_and_versioned() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["title"] == "CCBenchCase"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION


def test_schema_declares_the_fields_0_1_was_missing() -> None:
    """PAN, contact and message language must exist in the schema itself."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    party = schema["definitions"]["party"]["properties"]
    assert "pan" in party and "contact" in party
    assert "lang" in schema["definitions"]["message"]["properties"]
    assert "events" in schema["properties"]


# --- generated corpus -------------------------------------------------------


def test_dev_cases_validate_as_pydantic() -> None:
    paths = sorted(DEV_CASES_DIR.glob("*.json"))
    assert paths, f"No dev cases in {DEV_CASES_DIR} — run generate_dataset.py"
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        case = Case.model_validate(data)
        assert isinstance(case.bucket, Bucket)
        assert isinstance(case.jurisdiction, Jurisdiction)
        assert isinstance(case.gold_label, GoldLabel)


def test_full_dataset_passes_every_invariant() -> None:
    """The invariant checker must report zero violations across both splits."""
    report = validate_dataset(CASES_ROOT)
    assert report.ok, "invariant violations:\n" + "\n".join(report.errors[:20])
    assert report.checked == 200


def test_only_legal_bucket_label_combinations_are_emitted() -> None:
    for spec in TASKS:
        assert (spec.bucket, spec.label) in LEGAL_COMBINATIONS, spec.name


# --- the 0.1 failure modes, as regression tests -----------------------------


def test_no_placeholder_answers_anywhere() -> None:
    """0.1 shipped 113 of these across 200 cases."""
    for path in sorted(DEV_CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "not yet implemented" not in data["gold_answer"].lower()


def test_placeholder_answer_is_rejected_by_the_model(sample_case: dict) -> None:
    broken = dict(sample_case)
    broken["gold_answer"] = "Answer not yet implemented for this bucket/label combination."
    with pytest.raises(ValidationError):
        Case.model_validate(broken)


def test_eu_case_must_declare_denied_literals(sample_case: dict) -> None:
    assert sample_case["must_not_appear"], "EU case generated with nothing denied"
    broken = dict(sample_case)
    broken["must_not_appear"] = []
    with pytest.raises(ValidationError):
        Case.model_validate(broken)


def test_eu_answer_never_contains_a_denied_literal(sample_case: dict) -> None:
    for literal in sample_case["must_not_appear"]:
        assert literal not in sample_case["gold_answer"]


def test_compliance_answer_differs_by_jurisdiction() -> None:
    """Same question, different legal answer — the point of the bucket."""
    spec = next(t for t in TASKS if t.name == "comp_pan")
    in_case = assemble_case("ccbench-9002", spec, "IN", seed=777)
    eu_case = assemble_case("ccbench-9003", spec, "EU", seed=777)
    assert in_case["question"] == eu_case["question"]
    assert in_case["gold_answer"] != eu_case["gold_answer"]
    assert not in_case["must_not_appear"]
    assert eu_case["must_not_appear"]


def test_gold_facts_resolve_to_their_stated_values(sample_case: dict) -> None:
    for fact in sample_case["gold_facts"]:
        assert str(resolve(sample_case, fact["doc"], fact["path"])) == fact["value"]


def test_missing_ewb_label_is_realised_in_documents() -> None:
    spec = next(t for t in TASKS if t.name == "mh_no_ewb")
    case = assemble_case("ccbench-9004", spec, "IN", seed=31337)
    assert case["documents"]["eway_bill"] is None
    assert case["documents"]["invoice"]["eway_bill_ref"] is None


def test_temporal_violation_is_realised_in_timestamps() -> None:
    spec = next(t for t in TASKS if t.name == "tmp_ewb_first")
    case = assemble_case("ccbench-9005", spec, "IN", seed=2024)
    ewb = case["documents"]["eway_bill"]["generated_at"]
    inv = case["documents"]["invoice"]["issued_at"]
    assert ewb < inv, "temporal_violation label with a compliant timeline"


def test_clean_multi_hop_values_actually_match() -> None:
    spec = next(t for t in TASKS if t.name == "mh_match")
    case = assemble_case("ccbench-9006", spec, "IN", seed=99)
    inv = case["documents"]["invoice"]["invoice_total"]
    ewb = case["documents"]["eway_bill"]["total_invoice_value"]
    assert abs(inv - ewb) <= 0.01


def test_cross_lingual_evidence_is_not_english() -> None:
    spec = next(t for t in TASKS if t.name == "xl_detained")
    case = assemble_case("ccbench-9007", spec, "IN", seed=5150)
    langs = {f["evidence"]["lang"] for f in case["gold_facts"] if f.get("evidence")}
    assert langs and langs != {"en"}


def test_thread_carries_no_derived_delivery_flag() -> None:
    """A boolean would let a system skip the code-switched text entirely."""
    spec = next(t for t in TASKS if t.name == "xl_delivered")
    case = assemble_case("ccbench-9008", spec, "IN", seed=8080)
    thread = case["documents"]["whatsapp_pod"]
    assert "delivery_confirmed" not in thread
    assert "pod_signed_by" not in thread


def test_invoice_tax_matches_supply_type(sample_case: dict) -> None:
    inv = sample_case["documents"]["invoice"]
    if inv["supply_type"] == "inter_state":
        assert inv["total_igst"] > 0 and inv["total_cgst"] == 0
    else:
        assert inv["total_igst"] == 0 and inv["total_cgst"] > 0


def test_pan_is_embedded_in_gstin(sample_case: dict) -> None:
    for party in ("seller", "buyer"):
        p = sample_case["documents"]["invoice"][party]
        assert p["gstin"][2:12] == p["pan"]


# --- determinism and redaction ---------------------------------------------


def test_generation_is_deterministic() -> None:
    spec = next(t for t in TASKS if t.name == "mh_mismatch")
    a = assemble_case("ccbench-9009", spec, "IN", seed=606)
    b = assemble_case("ccbench-9009", spec, "IN", seed=606)
    assert a == b


def test_redaction_removes_all_supervision(sample_case: dict) -> None:
    public = redact(sample_case)
    for withheld in (
        "gold_answer",
        "gold_facts",
        "gold_label",
        "bucket",
        "difficulty",
        "must_not_appear",
    ):
        assert withheld not in public
    PublicCase.model_validate(public)


def test_public_test_split_is_redacted_on_disk() -> None:
    for path in sorted((CASES_ROOT / "test").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "gold_answer" not in data
        PublicCase.model_validate(data)


def test_invalid_bucket_rejected(sample_case: dict) -> None:
    broken = dict(sample_case)
    broken["bucket"] = "not-a-bucket"
    with pytest.raises(ValidationError):
        Case.model_validate(broken)


# --- unchanged compiler contracts ------------------------------------------


def test_domain_models_construct() -> None:
    from benchmark.schema.models import ErpOrder, EWayBill, Finding, Invoice, Message

    invoice = Invoice(invoice_no="INV-1", consignment_ref="CONS-1", value_eur=100.0)
    ewb = EWayBill(ewb_no="EWB-1", consignment_ref="CONS-1", declared_eur=100.0)
    erp = ErpOrder(order_no="PO-1", consignment_ref="CONS-1", expected_eur=100.0)
    msg = Message(msg_id="M-1", consignment_ref="CONS-1", text="hello", lang="en")
    finding = Finding(
        kind="value_mismatch", consignment_ref="CONS-1", severity="high", confidence=0.95
    )
    assert invoice.pan is None
    assert ewb.doc_ref is None
    assert erp.ts is None
    assert msg.lang == "en"
    assert finding.detail == {}


def test_context_bundle_contract() -> None:
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
    corpus = CaseCorpus()
    assert hasattr(corpus, "cases")
    assert hasattr(Retriever, "retrieve")

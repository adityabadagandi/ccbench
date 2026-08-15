"""Dataset invariant checker.

``models.py`` documents design invariants; before 0.2 nothing enforced them,
which is how a dataset shipped with 113 placeholder answers, empty
``must_not_appear`` on every case, and a ``temporal_violation`` label that
appeared in no timestamp anywhere.

This module is the enforcement. It runs over a whole split and fails loudly.

Usage::

    python -m benchmark.validate benchmark/cases
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.schema.models import Case
from benchmark.text import citations_in, split_claims

# (bucket, gold_label) pairs that are permitted to exist.
LEGAL_COMBINATIONS: set[tuple[str, str]] = {
    ("lookup", "clean"),
    ("multi-hop", "clean"),
    ("multi-hop", "value_mismatch"),
    ("multi-hop", "missing_ewb"),
    ("temporal", "clean"),
    ("temporal", "temporal_violation"),
    ("cross-lingual", "clean"),
    ("cross-lingual", "missing_ewb"),
    ("cross-lingual", "value_mismatch"),
    ("cross-lingual", "temporal_violation"),
    ("compliance", "compliance_case"),
}

_INDEX = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\[(?P<idx>\d+)\]$")
_MSG_ID = re.compile(r"^M-\d{3}$")
_EVENT_ID = re.compile(r"^E-\d{3}$")


@dataclass
class Report:
    """Accumulated validation outcome."""

    errors: list[str] = field(default_factory=list)
    checked: int = 0
    stats: Counter = field(default_factory=Counter)

    def fail(self, case_id: str, message: str) -> None:
        self.errors.append(f"{case_id}: {message}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _dt(iso: str) -> datetime:
    return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")


def resolve(case: dict, doc: str, path: str) -> Any:
    """Resolve a gold-fact path within a case.

    Three addressing modes:
      * documents: dotted with ``[i]`` indices — ``items[0].hsn_code``
      * whatsapp_pod: keyed by message id — ``M-004.text``
      * events: keyed by event id — ``E-005.ts``
    """
    head, _, tail = path.partition(".")

    if doc == "events":
        if not _EVENT_ID.match(head):
            raise KeyError(f"events path must start with an event id, got {head!r}")
        for event in case["events"]:
            if event["event_id"] == head:
                return _walk(event, tail)
        raise KeyError(f"no event {head}")

    node = case["documents"].get(doc)
    if node is None:
        raise KeyError(f"document {doc!r} is absent")

    if doc == "whatsapp_pod" and _MSG_ID.match(head):
        for message in node["messages"]:
            if message["msg_id"] == head:
                return _walk(message, tail)
        raise KeyError(f"no message {head}")

    return _walk(node, path)


def _walk(node: Any, path: str) -> Any:
    if not path:
        return node
    for part in path.split("."):
        match = _INDEX.match(part)
        node = node[match.group("name")][int(match.group("idx"))] if match else node[part]
    return node


# ---------------------------------------------------------------------------
# Per-case checks
# ---------------------------------------------------------------------------


def check_case(raw: dict, report: Report) -> None:
    """Run every invariant against one full (unredacted) case."""
    cid = raw.get("case_id", "<no case_id>")

    try:
        case = Case.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — we want the message, whatever it is
        report.fail(cid, f"schema: {exc}")
        return

    docs = raw["documents"]
    inv = docs["invoice"]
    ewb = docs.get("eway_bill")
    label = raw["gold_label"]
    bucket = raw["bucket"]

    # 1. Only legal task combinations exist.
    if (bucket, label) not in LEGAL_COMBINATIONS:
        report.fail(cid, f"illegal combination bucket={bucket} label={label}")

    # 2. Every gold fact resolves and matches its stated value.
    for fact in raw["gold_facts"]:
        try:
            actual = resolve(raw, fact["doc"], fact["path"])
        except (KeyError, IndexError, TypeError) as exc:
            report.fail(
                cid,
                f"gold_fact {fact['fact_id']} path {fact['doc']}.{fact['path']} unresolvable: {exc}",
            )
            continue
        if str(actual) != fact["value"]:
            report.fail(
                cid,
                f"gold_fact {fact['fact_id']} says {fact['value']!r} but document holds {actual!r}",
            )

    # 3. Evidence spans are verbatim and point at real messages.
    for fact in raw["gold_facts"]:
        span = fact.get("evidence")
        if span is None:
            continue
        try:
            target = resolve(raw, fact["doc"], f"{span['ref_id']}.text")
        except (KeyError, IndexError, TypeError):
            try:
                target = resolve(raw, "events", f"{span['ref_id']}.note") or ""
            except Exception:  # noqa: BLE001
                report.fail(cid, f"evidence ref {span['ref_id']} does not resolve")
                continue
        if span["span"] not in target:
            report.fail(
                cid, f"evidence span {span['span']!r} is not a substring of {span['ref_id']}"
            )

    # 4. The emitted answer leaks nothing the jurisdiction denies.
    for literal in raw["must_not_appear"]:
        if literal in raw["gold_answer"]:
            report.fail(cid, f"gold_answer leaks denied literal {literal!r}")

    # 4b. The answer key must pass the metric it defines.
    #
    #     Spec §4.3 marks an uncited claim unfaithful, and §8 requires
    #     faithfulness >= 0.9 to call a case solved. If the gold answer carried
    #     no citations, a system reproducing it verbatim would score correct
    #     and unfaithful, and no case could ever be solved — the benchmark
    #     would be unsolvable by its own answer key. So: every claim carries a
    #     citation, and every citation is backed by a gold fact.
    supported_nodes = {fact.node_id for fact in case.gold_facts}
    for claim in split_claims(case.gold_answer):
        cited = citations_in(claim)
        if not cited:
            report.fail(cid, f"gold_answer claim has no citation: {claim[:70]!r}")
        elif not cited & supported_nodes:
            report.fail(
                cid,
                f"gold_answer claim cites {sorted(cited)} but no gold fact retrieves any of them",
            )
    for node in citations_in(case.gold_answer) - supported_nodes:
        report.fail(cid, f"gold_answer cites {node!r}, which no gold fact would retrieve")

    # 5. EU cases actually declare the personal identifiers as denied.
    if raw["jurisdiction"] == "EU":
        for party in ("seller", "buyer"):
            if inv[party]["pan"] not in raw["must_not_appear"]:
                report.fail(cid, f"EU case does not deny {party}.pan")

    # 6. The label is realised in the documents, not merely asserted.
    _check_label_realised(raw, inv, ewb, label, report)

    # 7. Cross-lingual cases must rest on non-English evidence.
    if bucket == "cross-lingual":
        langs = {f["evidence"]["lang"] for f in raw["gold_facts"] if f.get("evidence")}
        if not langs:
            report.fail(cid, "cross-lingual case has no evidence span")
        elif langs <= {"en"}:
            report.fail(cid, "cross-lingual case rests only on English evidence")

    # 8. The timeline agrees with the documents it claims to describe.
    _check_timeline(raw, inv, ewb, report)

    # 9. Invoice arithmetic (belt and braces — the model checks it too).
    if abs(round(inv["total_taxable_value"] + inv["total_tax"], 2) - inv["invoice_total"]) > 0.01:
        report.fail(cid, "invoice totals do not add up")

    report.checked += 1
    report.stats[f"bucket:{bucket}"] += 1
    report.stats[f"label:{label}"] += 1
    report.stats[f"jurisdiction:{raw['jurisdiction']}"] += 1
    report.stats[f"difficulty:{raw['difficulty']}"] += 1
    report.stats[f"qlang:{raw['question_lang']}"] += 1


def _check_label_realised(
    raw: dict, inv: dict, ewb: dict | None, label: str, report: Report
) -> None:
    cid = raw["case_id"]

    if label == "missing_ewb":
        if ewb is not None:
            report.fail(cid, "label missing_ewb but an e-way bill is present")
        if inv["eway_bill_ref"] is not None:
            report.fail(cid, "label missing_ewb but the invoice cites an e-way bill")
        return

    if ewb is None and label != "missing_ewb":
        report.fail(cid, f"label {label} requires an e-way bill but none is present")
        return
    assert ewb is not None

    if label == "value_mismatch":
        if abs(inv["invoice_total"] - ewb["total_invoice_value"]) <= 0.01:
            report.fail(cid, "label value_mismatch but the declared values agree")
        return

    if label == "temporal_violation":
        if not _temporal_violations(raw, inv, ewb):
            report.fail(cid, "label temporal_violation but no ordering violation exists")
        return

    if label == "clean":
        if abs(inv["invoice_total"] - ewb["total_invoice_value"]) > 0.01:
            report.fail(cid, "label clean but the declared values disagree")
        violations = _temporal_violations(raw, inv, ewb)
        if violations:
            report.fail(cid, f"label clean but timeline violates: {', '.join(violations)}")


def _temporal_violations(raw: dict, inv: dict, ewb: dict | None) -> list[str]:
    """Re-derive ordering violations from the documents alone."""
    found: list[str] = []
    if ewb is not None and _dt(ewb["generated_at"]) < _dt(inv["issued_at"]):
        found.append("ewb_before_invoice")
    by_type = {e["type"]: _dt(e["ts"]) for e in raw["events"]}
    if {"delivered", "dispatched"} <= by_type.keys() and by_type["delivered"] < by_type[
        "dispatched"
    ]:
        found.append("pod_before_dispatch")
    if (
        ewb is not None
        and "delivered" in by_type
        and by_type["delivered"] > _dt(ewb["valid_until"])
    ):
        found.append("delivery_after_expiry")
    return found


def _check_timeline(raw: dict, inv: dict, ewb: dict | None, report: Report) -> None:
    cid = raw["case_id"]
    by_type = {e["type"]: e for e in raw["events"]}

    issued = by_type.get("invoice_revised") or by_type.get("invoice_issued")
    if issued is None:
        report.fail(cid, "timeline has no invoice issue event")
    elif issued["ts"] != inv["issued_at"]:
        report.fail(cid, "timeline invoice event disagrees with invoice.issued_at")

    if ewb is not None:
        gen = by_type.get("ewb_generated")
        if gen is None:
            report.fail(cid, "e-way bill present but no ewb_generated event")
        elif gen["ts"] != ewb["generated_at"]:
            report.fail(cid, "timeline ewb event disagrees with eway_bill.generated_at")
    elif "ewb_generated" in by_type:
        report.fail(cid, "no e-way bill but the timeline records ewb_generated")


# ---------------------------------------------------------------------------
# Cross-case and split-level checks
# ---------------------------------------------------------------------------


def check_corpus(cases: list[dict], report: Report) -> None:
    """Invariants that only make sense across the whole corpus."""
    for key, getter in (
        ("invoice_no", lambda c: c["documents"]["invoice"]["invoice_no"]),
        ("consignment_ref", lambda c: c["documents"]["invoice"]["consignment_ref"]),
        ("case_id", lambda c: c["case_id"]),
    ):
        counts = Counter(getter(c) for c in cases)
        for value, n in counts.items():
            if n > 1:
                report.fail("<corpus>", f"duplicate {key} {value!r} across {n} cases")

    questions = Counter(c["question"] for c in cases)
    dupes = sum(n - 1 for n in questions.values() if n > 1)
    if dupes:
        report.stats["duplicate_questions"] = dupes

    answers = Counter(c["gold_answer"] for c in cases)
    for answer, n in answers.items():
        if n > 1:
            report.fail("<corpus>", f"{n} cases share an identical gold_answer: {answer[:70]!r}")


def check_redaction(public_dir: Path, report: Report) -> None:
    """The public test split must not carry supervision."""
    forbidden = (
        "gold_answer",
        "gold_facts",
        "gold_label",
        "bucket",
        "difficulty",
        "must_not_appear",
    )
    for path in sorted(public_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        leaked = [k for k in forbidden if k in data]
        if leaked:
            report.fail(path.name, f"public test case exposes {leaked}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def validate_dataset(root: Path) -> Report:
    """Validate ``root/dev`` (full cases) and ``root/test`` (redacted)."""
    report = Report()

    dev_cases = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "dev").glob("*.json"))
    ]
    for case in dev_cases:
        check_case(case, report)

    gold_path = root / "test_gold.private.json"
    test_cases: list[dict] = []
    if gold_path.exists():
        test_cases = list(json.loads(gold_path.read_text(encoding="utf-8")).values())
        for case in test_cases:
            check_case(case, report)
    else:
        report.fail(
            "<corpus>", "test_gold.private.json is missing — the test split has no answer key"
        )

    check_corpus(dev_cases + test_cases, report)
    check_redaction(root / "test", report)

    report.stats["dev_cases"] = len(dev_cases)
    report.stats["test_cases"] = len(test_cases)
    return report


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent / "cases"
    report = validate_dataset(root)

    print(f"Validated {report.checked} cases from {root}\n")
    for key in sorted(report.stats):
        print(f"  {key:28s} {report.stats[key]}")

    if report.ok:
        print(f"\nOK — {report.checked} cases, 0 invariant violations.")
        return 0
    print(f"\nFAILED — {len(report.errors)} violation(s):\n")
    for err in report.errors[:60]:
        print(f"  - {err}")
    if len(report.errors) > 60:
        print(f"  ... and {len(report.errors) - 60} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

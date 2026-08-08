"""Document reconciliation engine.

[YOU] Crown-jewel module — write and own this yourself.
    KIMI may write edge-case tests AFTER your five contract tests pass.
    Never delegate the implementation body.

[SPEC] reconcile(invoices, eway_bills, erp_orders) -> list[Finding]
    One Finding per consignment.

Algorithm (to be implemented by YOU):
    1. Index e-way bills and ERP orders by consignment_ref.
    2. For each invoice, find partners; classify:
         - value_mismatch if |invoice.value - ewb.declared| > tolerance
         - missing_ewb if no ewb exists
         - else ok
    3. Severity: high for value_mismatch, med for missing_ewb, ok otherwise.
    4. Confidence design (the defensible part):
         A mismatch confirmed by ERP (ERP agrees with invoice, ewb is outlier)
         scores HIGHER than a two-source mismatch.
         More independent agreement -> higher confidence.
    5. Pack numbers + doc_refs into Finding.detail for provenance.

Test contracts (write THESE FIRST, before implementation):
    def test_value_mismatch_flagged_high(): ...
    def test_matching_values_ok(): ...
    def test_missing_eway_bill(): ...
    def test_one_finding_per_consignment(): ...
    def test_erp_confirmed_mismatch_more_confident(): ...
"""

from __future__ import annotations

from benchmark.schema.models import Finding, Invoice, EWayBill, ErpOrder


def reconcile(
    invoices: list[Invoice],
    eway_bills: list[EWayBill],
    erp_orders: list[ErpOrder],
    tolerance: float = 0.01,
) -> list[Finding]:
    """Reconcile invoices against e-way bills and ERP orders.

    [YOU] Implement this. The matching logic is your intellectual
    contribution. You must be able to explain why invoice INV-001 matches
    e-way bill EWB-0034 in 60 seconds.

    Args:
        invoices: List of Invoice records.
        eway_bills: List of EWayBill records.
        erp_orders: List of ErpOrder records.
        tolerance: Relative tolerance for value comparison (default 1%).

    Returns:
        One Finding per consignment_ref found in invoices.
    """
    raise NotImplementedError("Crown jewel — implement yourself. See module docstring.")

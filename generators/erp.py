"""Synthetic ERP order generator.

Generates purchase orders linked to invoices by consignment reference.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta


def _po_no() -> str:
    """Generate a fake purchase order number."""
    prefixes = ["PO", "PUR", "ORD"]
    prefix = random.choice(prefixes)
    year = random.choice([2023, 2024, 2025])
    seq = random.randint(1, 9999)
    return f"{prefix}-{year}-{seq:04d}"


def _vendor_code() -> str:
    """Generate a fake vendor code."""
    return f"VND-{random.randint(1000, 9999)}"


def generate_erp_order(
    invoice: dict,
    seed: int | None = None,
) -> dict:
    """Generate a synthetic ERP purchase order linked to an invoice.

    Args:
        invoice: The parent invoice dictionary.
        seed: Random seed for reproducibility.

    Returns:
        ERP order dictionary.
    """
    if seed is not None:
        random.seed(seed)

    inv_date = datetime.strptime(invoice["date"], "%Y-%m-%d")
    po_date = inv_date - timedelta(days=random.randint(2, 10))
    expected_delivery = inv_date + timedelta(days=random.randint(2, 7))

    return {
        "po_no": _po_no(),
        "po_date": po_date.strftime("%Y-%m-%d"),
        "buyer": invoice["buyer"]["name"],
        "vendor_code": _vendor_code(),
        "vendor_name": invoice["seller"]["name"],
        "items": [
            {
                "item_code": f"ITEM-{random.randint(1000, 9999)}",
                "description": invoice["items"][0]["description"],
                "quantity_ordered": invoice["items"][0]["quantity"],
                "unit": invoice["items"][0]["unit"],
                "unit_price": invoice["items"][0]["rate_per_unit"],
                "total_value": invoice["total_taxable_value"],
                "expected_delivery": expected_delivery.strftime("%Y-%m-%d"),
            }
        ],
        "po_total": invoice["total_taxable_value"],
        "payment_terms": random.choice(
            ["Net 15 days", "Net 30 days", "Net 45 days", "Advance 50%"]
        ),
        "status": random.choice(["fulfilled", "partially_fulfilled", "pending"]),
        "invoice_refs": [invoice["invoice_no"]],
        "consignment_ref": invoice["consignment_ref"],
    }

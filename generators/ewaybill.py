"""Synthetic e-way bill generator.

Generates realistic e-way bills linked to invoices by consignment reference.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta


def _ewb_no() -> str:
    """Generate a fake e-way bill number."""
    num = random.randint(100000000000, 999999999999)
    date_str = datetime.now().strftime("%d-%m-%Y")
    return f"EWB-{num}-{date_str}"


def generate_eway_bill(
    invoice: dict,
    mismatch: bool = False,
    missing: bool = False,
    seed: int | None = None,
) -> dict | None:
    """Generate a synthetic e-way bill linked to an invoice.

    Args:
        invoice: The parent invoice dictionary.
        mismatch: If True, total_value differs from invoice.
        missing: If True, returns None (simulates missing e-way bill).
        seed: Random seed for reproducibility.

    Returns:
        E-way bill dictionary or None if missing.
    """
    if seed is not None:
        random.seed(seed)

    if missing:
        return None

    inv_date = datetime.strptime(invoice["date"], "%Y-%m-%d")
    gen_time = inv_date + timedelta(hours=random.randint(0, 12))
    valid_until = gen_time + timedelta(days=1)

    # Default: match invoice total (but e-way bill typically excludes tax)
    taxable = invoice["total_taxable_value"]
    total_val = taxable  # e-way bill shows pre-tax value usually

    if mismatch:
        total_val = round(taxable + random.choice([-1000, -500, 500, 1000, 1350]), 2)

    return {
        "ewb_no": _ewb_no(),
        "generation_date": gen_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "from_gstin": invoice["seller"]["gstin"],
        "from_address": invoice["seller"]["address"],
        "to_gstin": invoice["buyer"]["gstin"],
        "to_address": invoice["buyer"]["address"],
        "transporter": invoice["buyer"]["name"],
        "vehicle_no": invoice["vehicle_no"],
        "consignment_ref": invoice["consignment_ref"],
        "items": [
            {
                "description": invoice["items"][0]["description"],
                "hsn_code": invoice["items"][0]["hsn_code"],
                "quantity": invoice["items"][0]["quantity"],
                "unit": invoice["items"][0]["unit"],
            }
        ],
        "total_value": total_val,
        "distance_km": random.choice([200, 450, 800, 1200, 1412, 1800]),
    }

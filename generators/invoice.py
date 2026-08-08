"""Synthetic invoice generator.

Generates realistic GST-format invoices with randomized but structurally
valid fields. All values are synthetic.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .gstin import gstin, hsn_code, hsn_description


def _invoice_no() -> str:
    """Generate a fake invoice number."""
    prefixes = ["INV", "BILL", "TAX", "GST"]
    prefix = random.choice(prefixes)
    city_from = random.choice(["DL", "MUM", "BLR", "CHN", "HYD"])
    city_to = random.choice(["DL", "MUM", "BLR", "CHN", "HYD"])
    year = random.choice([2023, 2024, 2025])
    seq = random.randint(1, 9999)
    return f"{prefix}-{city_from}-{city_to}-{year}-{seq:04d}"


def _vehicle_no() -> str:
    """Generate a fake Indian vehicle registration number."""
    states = ["DL", "MH", "KA", "TN", "HR", "UP", "WB", "GJ", "TS", "MP"]
    state = random.choice(states)
    series = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=2))
    number = random.randint(1, 9999)
    return f"{state}{random.randint(10,99)}{series}{number:04d}"


def _consignment_ref() -> str:
    """Generate a fake consignment reference."""
    seller = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
    buyer = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
    date_str = datetime.now().strftime("%d%m%y")
    seq = random.randint(1, 999)
    return f"CONS-{seller}-{buyer}-{date_str}-{seq:03d}"


def generate_invoice(
    seller_gstin: str | None = None,
    buyer_gstin: str | None = None,
    consignment_ref: str | None = None,
    mismatch: bool = False,
    seed: int | None = None,
) -> dict:
    """Generate a synthetic GST invoice.

    Args:
        seller_gstin: Specific seller GSTIN or random.
        buyer_gstin: Specific buyer GSTIN or random.
        consignment_ref: Specific consignment reference or random.
        mismatch: If True, introduces a subtle value error.
        seed: Random seed for reproducibility.

    Returns:
        Invoice dictionary matching the CCBench schema.
    """
    if seed is not None:
        random.seed(seed)

    if seller_gstin is None:
        seller_gstin = gstin()
    if buyer_gstin is None:
        # Ensure different state code from seller
        seller_state = seller_gstin[:2]
        from .gstin import STATE_CODES
        other_states = [c for c in STATE_CODES if c != seller_state]
        buyer_gstin = gstin(state_code=random.choice(other_states))
    if consignment_ref is None:
        consignment_ref = _consignment_ref()

    # Item details
    hsn = hsn_code()
    qty = random.choice([100, 250, 500, 1000, 2000])
    rate = random.choice([25.0, 45.0, 60.0, 120.0, 250.0])
    taxable = qty * rate

    # Tax: assume intra-state (CGST + SGST) for simplicity
    tax_rate = random.choice([5, 9, 12, 18])
    cgst = taxable * tax_rate / 100
    sgst = taxable * tax_rate / 100
    total = taxable + cgst + sgst

    # Optional mismatch: invoice total off by random amount
    if mismatch:
        total += random.choice([50, 100, 500, 1000, 1350])

    return {
        "invoice_no": _invoice_no(),
        "date": (datetime.now() - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d"),
        "seller": {
            "name": _random_company(),
            "gstin": seller_gstin,
            "address": _random_address(seller_gstin[:2]),
        },
        "buyer": {
            "name": _random_company(),
            "gstin": buyer_gstin,
            "address": _random_address(buyer_gstin[:2]),
        },
        "items": [
            {
                "description": hsn_description(hsn),
                "hsn_code": hsn,
                "quantity": qty,
                "unit": random.choice(["meters", "units", "kg", "pieces", "boxes"]),
                "rate_per_unit": rate,
                "taxable_value": round(taxable, 2),
                "cgst_rate": tax_rate,
                "sgst_rate": tax_rate,
                "cgst_amount": round(cgst, 2),
                "sgst_amount": round(sgst, 2),
            }
        ],
        "total_taxable_value": round(taxable, 2),
        "total_cgst": round(cgst, 2),
        "total_sgst": round(sgst, 2),
        "invoice_total": round(total, 2),
        "eway_bill_ref": None,  # filled by assembler
        "vehicle_no": _vehicle_no(),
        "consignment_ref": consignment_ref,
    }


def _random_company() -> str:
    names = [
        "Shree Ganesh Trading Co.",
        "Patel Logistics Pvt. Ltd.",
        "Agarwal Enterprises",
        "Verma Industries",
        "Krishna Manufacturing",
        "Singh & Sons Exports",
        "Mehta Brothers",
        "Reddy Corp",
        "Sharma Suppliers",
        "Gupta Traders",
    ]
    return random.choice(names)


def _random_address(state_code: str) -> str:
    from .gstin import STATE_CODES
    cities = {
        "07": ["Karol Bagh, Delhi", "Connaught Place, Delhi", "Saket, Delhi"],
        "27": ["Andheri East, Mumbai", "Bandra, Mumbai", "Thane, Mumbai"],
        "29": ["Koramangala, Bangalore", "Whitefield, Bangalore", "Electronic City, Bangalore"],
        "33": ["T Nagar, Chennai", "Guindy, Chennai", "Ambattur, Chennai"],
        "06": ["Gurugram, Haryana", "Faridabad, Haryana", "Panipat, Haryana"],
        "09": ["Noida, UP", "Ghaziabad, UP", "Lucknow, UP"],
        "19": ["Salt Lake, Kolkata", "Howrah, WB", "Durgapur, WB"],
        "24": ["Ahmedabad, Gujarat", "Surat, Gujarat", "Vadodara, Gujarat"],
        "36": ["Hitech City, Hyderabad", "Secunderabad, Telangana", "Gachibowli, Hyderabad"],
        "23": ["Indore, MP", "Bhopal, MP", "Gwalior, MP"],
    }
    city = random.choice(cities.get(state_code, ["Unknown City"]))
    pin = random.randint(110001, 899999)
    return f"{city} - {pin}"

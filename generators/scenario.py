"""Scenario builder — one source of truth per case.

The 0.1 generator built each document independently and then *asserted* a
label on top. That is why ``temporal_violation`` never appeared in any
timestamp and ``clean`` cases never actually matched.

Here a single :class:`Scenario` fixes the parties, the goods, the money and
the clock once. Every document is then a *view* of that scenario, and the
defect is injected into the scenario itself — so a label is true by
construction and can be re-derived from the documents alone.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import identity
from .identity import Good

# Defects a scenario can carry. These are scenario-level facts, not labels
# pasted on afterwards.
DEFECTS = (
    "none",
    "value_mismatch",
    "missing_ewb",
    "ewb_before_invoice",
    "pod_before_dispatch",
    "delivery_after_expiry",
)

TEMPORAL_DEFECTS = ("ewb_before_invoice", "pod_before_dispatch", "delivery_after_expiry")

_BUSINESS_HOURS = (9, 19)


def _iso(dt: datetime) -> str:
    """ISO-8601 with the India Standard Time offset."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")


@dataclass
class Line:
    """A shared item line, seen by the PO, the invoice and the e-way bill."""

    good: Good
    quantity: float
    rate: float
    item_code: str

    @property
    def taxable(self) -> float:
        return round(self.quantity * self.rate, 2)


@dataclass
class Scenario:
    """Everything true about one consignment, before any document is rendered."""

    seed: int
    rng: random.Random
    consignment_ref: str
    seller: dict
    buyer: dict
    supply_type: str
    lines: list[Line]
    distance_km: int
    defect: str

    # clock
    po_date: datetime
    approved_at: datetime
    invoice_issued_at: datetime
    ewb_generated_at: datetime
    ewb_valid_until: datetime
    dispatched_at: datetime
    arrived_at: datetime
    delivered_at: datetime
    pod_signed_at: datetime
    grn_at: datetime

    # identifiers
    invoice_no: str
    po_no: str
    ewb_no: str
    grn_no: str
    vehicle_no: str
    transporter_name: str
    transporter_id: str

    # revision
    revision_no: int = 0
    superseded_invoice_no: str | None = None
    original_issued_at: datetime | None = None

    # money
    declared_ewb_value: float | None = None  # differs from invoice_total iff value_mismatch
    ewb_extensions: list[dict] = field(default_factory=list)
    ewb_status: str = "active"

    # ---- derived money -------------------------------------------------

    @property
    def total_taxable(self) -> float:
        return round(sum(line.taxable for line in self.lines), 2)

    @property
    def is_inter_state(self) -> bool:
        return self.supply_type == "inter_state"

    def _line_tax(self, line: Line) -> tuple[float, float, float]:
        """Return (cgst, sgst, igst) for a line."""
        full = round(line.taxable * line.good.tax_rate / 100, 2)
        if self.is_inter_state:
            return 0.0, 0.0, full
        half = round(full / 2, 2)
        return half, full - half, 0.0

    @property
    def total_cgst(self) -> float:
        return round(sum(self._line_tax(line)[0] for line in self.lines), 2)

    @property
    def total_sgst(self) -> float:
        return round(sum(self._line_tax(line)[1] for line in self.lines), 2)

    @property
    def total_igst(self) -> float:
        return round(sum(self._line_tax(line)[2] for line in self.lines), 2)

    @property
    def total_tax(self) -> float:
        return round(self.total_cgst + self.total_sgst + self.total_igst, 2)

    @property
    def invoice_total(self) -> float:
        return round(self.total_taxable + self.total_tax, 2)

    @property
    def ewb_value(self) -> float:
        """Value declared on the permit. Equals invoice_total unless defective."""
        return (
            self.declared_ewb_value if self.declared_ewb_value is not None else self.invoice_total
        )

    @property
    def has_ewb(self) -> bool:
        return self.defect != "missing_ewb"


def _business_dt(day: datetime, rng: random.Random) -> datetime:
    """Snap a date to a random business-hours timestamp."""
    return day.replace(
        hour=rng.randint(*_BUSINESS_HOURS),
        minute=rng.choice([5, 12, 18, 27, 34, 41, 49, 56]),
        second=rng.randint(0, 59),
        microsecond=0,
    )


def _mismatch_value(base: float, rng: random.Random) -> float:
    """Produce a realistic wrong declared value.

    Real e-way bill discrepancies are transcription errors, not random noise:
    a transposed digit, a dropped zero, a pre-tax figure keyed into a
    tax-inclusive field, or a stale value from a superseded invoice.
    """
    kind = rng.choice(["transpose", "drop_zero", "one_line_short", "round_off"])
    if kind == "transpose":
        digits = list(f"{int(base)}")
        if len(digits) >= 3:
            i = rng.randrange(len(digits) - 1)
            digits[i], digits[i + 1] = digits[i + 1], digits[i]
            candidate = float("".join(digits))
            if abs(candidate - base) > 1:
                return round(candidate, 2)
    if kind == "drop_zero":
        return round(base / 10, 2)
    if kind == "round_off":
        return round(base - rng.choice([100.0, 250.0, 500.0, 1000.0]), 2)
    return round(base * rng.uniform(0.72, 0.93), 2)


def build_scenario(seed: int, defect: str = "none", revised: bool = False) -> Scenario:
    """Construct a fully-determined consignment.

    Args:
        seed: Seed for this case. All randomness flows from it.
        defect: One of :data:`DEFECTS`.
        revised: If True, the invoice is a revision superseding an earlier one.

    Returns:
        A :class:`Scenario` whose clock and money already embody ``defect``.
    """
    if defect not in DEFECTS:
        raise ValueError(f"unknown defect {defect!r}")
    rng = random.Random(seed)

    seller_state = rng.choice(list(identity.STATES))
    # 70% inter-state: that is the case that requires an e-way bill in practice
    if rng.random() < 0.7:
        buyer_state = rng.choice([s for s in identity.STATES if s != seller_state])
    else:
        buyer_state = seller_state

    seller = identity.party(seller_state, rng)
    buyer = identity.party(buyer_state, rng)
    supply_type = "inter_state" if seller_state != buyer_state else "intra_state"

    n_lines = rng.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
    lines: list[Line] = []
    for _ in range(n_lines):
        good = identity.pick_good(rng)
        qty = float(rng.choice([25, 50, 100, 180, 250, 400, 500, 750, 1000, 1200]))
        rate = round(rng.uniform(good.price_low, good.price_high), 2)
        lines.append(
            Line(good=good, quantity=qty, rate=rate, item_code=f"ITEM-{rng.randint(10000, 99999)}")
        )

    distance_km = rng.choice([180, 240, 410, 620, 880, 1150, 1420, 1780, 2100])

    # ---- clock ---------------------------------------------------------
    base = datetime(2026, 1, 1) + timedelta(days=rng.randint(0, 200))
    po_date = _business_dt(base, rng)
    approved_at = po_date + timedelta(hours=rng.randint(2, 30))
    invoice_issued_at = _business_dt(po_date + timedelta(days=rng.randint(3, 12)), rng)

    # e-way bill validity: statutory 1 day per 200 km of the declared distance
    validity_days = max(1, -(-distance_km // 200))

    if defect == "ewb_before_invoice":
        # Permit raised against a tax invoice that did not yet exist.
        ewb_generated_at = invoice_issued_at - timedelta(
            hours=rng.randint(2, 7), minutes=rng.choice([11, 23, 47])
        )
    else:
        ewb_generated_at = invoice_issued_at + timedelta(
            hours=rng.randint(1, 8), minutes=rng.choice([6, 19, 33, 52])
        )
    ewb_valid_until = ewb_generated_at + timedelta(days=validity_days)

    dispatched_at = ewb_generated_at + timedelta(hours=rng.randint(1, 5))
    transit_hours = max(6, int(distance_km / rng.uniform(38, 52)))
    arrived_at = dispatched_at + timedelta(hours=transit_hours)

    if defect == "delivery_after_expiry":
        # Truck detained; goods move under a permit that has already lapsed.
        arrived_at = ewb_valid_until + timedelta(hours=rng.randint(5, 40))
    delivered_at = arrived_at + timedelta(hours=rng.randint(1, 4))
    pod_signed_at = delivered_at + timedelta(minutes=rng.randint(20, 180))
    grn_at = pod_signed_at + timedelta(hours=rng.randint(1, 20))

    if defect == "pod_before_dispatch":
        # Warehouse signed a POD for goods that had not left the origin yet.
        delivered_at = dispatched_at - timedelta(hours=rng.randint(3, 11))
        arrived_at = delivered_at - timedelta(hours=1)
        pod_signed_at = delivered_at + timedelta(minutes=rng.randint(15, 90))
        grn_at = pod_signed_at + timedelta(hours=rng.randint(1, 6))

    # ---- identifiers ---------------------------------------------------
    # Document serials embed a case-unique component derived from the seed.
    # Real serials are sequential per issuer, so collisions across a corpus are
    # not merely unlikely, they are impossible — and the validator enforces it.
    uid = seed % 100000
    seller_tag = "".join(c for c in seller["legal_name"] if c.isalpha())[:3].upper()
    buyer_tag = "".join(c for c in buyer["legal_name"] if c.isalpha())[:3].upper()
    consignment_ref = f"CONS-{seller_tag}-{buyer_tag}-{po_date.strftime('%y%m%d')}-{uid:05d}"
    fy = invoice_issued_at.year
    invoice_no = f"{rng.choice(['INV', 'TAX', 'GST'])}/{fy}-{str(fy + 1)[-2:]}/{uid:05d}"
    po_no = f"{rng.choice(['PO', 'PUR', 'ORD'])}-{po_date.year}-{uid:05d}"
    ewb_no = f"{uid % 1000:03d}{rng.randint(100000000, 999999999)}"
    grn_no = f"GRN-{uid:05d}"
    vehicle = identity.vehicle_no(seller_state, rng)
    tname, tid = identity.transporter(rng)

    scn = Scenario(
        seed=seed,
        rng=rng,
        consignment_ref=consignment_ref,
        seller=seller,
        buyer=buyer,
        supply_type=supply_type,
        lines=lines,
        distance_km=distance_km,
        defect=defect,
        po_date=po_date,
        approved_at=approved_at,
        invoice_issued_at=invoice_issued_at,
        ewb_generated_at=ewb_generated_at,
        ewb_valid_until=ewb_valid_until,
        dispatched_at=dispatched_at,
        arrived_at=arrived_at,
        delivered_at=delivered_at,
        pod_signed_at=pod_signed_at,
        grn_at=grn_at,
        invoice_no=invoice_no,
        po_no=po_no,
        ewb_no=ewb_no,
        grn_no=grn_no,
        vehicle_no=vehicle,
        transporter_name=tname,
        transporter_id=tid,
    )

    if revised:
        scn.revision_no = 1
        scn.superseded_invoice_no = f"{invoice_no.rsplit('/', 1)[0]}/{rng.randint(1000, 9999)}"
        scn.original_issued_at = invoice_issued_at - timedelta(days=rng.randint(1, 4))

    if defect == "value_mismatch":
        scn.declared_ewb_value = _mismatch_value(scn.invoice_total, rng)

    if defect == "delivery_after_expiry":
        scn.ewb_status = "expired"
        if rng.random() < 0.5:
            ext_at = scn.ewb_valid_until - timedelta(hours=rng.randint(1, 6))
            scn.ewb_extensions = [
                {
                    "extended_at": _iso(ext_at),
                    "new_valid_until": _iso(scn.ewb_valid_until + timedelta(hours=12)),
                    "reason": rng.choice(
                        [
                            "Vehicle breakdown en route",
                            "Transhipment delay",
                            "Natural calamity — road closure",
                        ]
                    ),
                }
            ]

    return scn


# ---------------------------------------------------------------------------
# Document views
# ---------------------------------------------------------------------------


def build_invoice(scn: Scenario) -> dict:
    """Render the GST invoice view of a scenario."""
    items = []
    for i, line in enumerate(scn.lines, start=1):
        cgst, sgst, igst = scn._line_tax(line)
        items.append(
            {
                "line_no": i,
                "description": line.good.description,
                "hsn_code": line.good.hsn,
                "quantity": line.quantity,
                "unit": line.good.unit,
                "rate_per_unit": line.rate,
                "taxable_value": line.taxable,
                "tax_rate": float(line.good.tax_rate),
                "cgst_amount": cgst,
                "sgst_amount": sgst,
                "igst_amount": igst,
            }
        )
    return {
        "invoice_no": scn.invoice_no,
        "issued_at": _iso(scn.invoice_issued_at),
        "revision_no": scn.revision_no,
        "supersedes": scn.superseded_invoice_no,
        "original_issued_at": _iso(scn.original_issued_at) if scn.original_issued_at else None,
        "seller": scn.seller,
        "buyer": scn.buyer,
        "place_of_supply": f"{scn.buyer['address']['state']} ({scn.buyer['address']['state_code']})",
        "supply_type": scn.supply_type,
        "items": items,
        "total_taxable_value": scn.total_taxable,
        "total_cgst": scn.total_cgst,
        "total_sgst": scn.total_sgst,
        "total_igst": scn.total_igst,
        "total_tax": scn.total_tax,
        "invoice_total": scn.invoice_total,
        "currency": "INR",
        "eway_bill_ref": scn.ewb_no if scn.has_ewb else None,
        "vehicle_no": scn.vehicle_no,
        "consignment_ref": scn.consignment_ref,
    }


def build_eway_bill(scn: Scenario) -> dict | None:
    """Render the e-way bill view, or None when the permit was never raised."""
    if not scn.has_ewb:
        return None
    return {
        "ewb_no": scn.ewb_no,
        "generated_at": _iso(scn.ewb_generated_at),
        "valid_until": _iso(scn.ewb_valid_until),
        "status": scn.ewb_status,
        "extensions": scn.ewb_extensions,
        "doc_type": "Tax Invoice",
        "doc_no": scn.invoice_no,
        "doc_date": scn.invoice_issued_at.strftime("%Y-%m-%d"),
        "from_gstin": scn.seller["gstin"],
        "from_address": _flat_address(scn.seller["address"]),
        "to_gstin": scn.buyer["gstin"],
        "to_address": _flat_address(scn.buyer["address"]),
        "transporter_name": scn.transporter_name,
        "transporter_id": scn.transporter_id,
        "mode": "road",
        "vehicle_no": scn.vehicle_no,
        "consignment_ref": scn.consignment_ref,
        "items": [
            {
                "description": line.good.description,
                "hsn_code": line.good.hsn,
                "quantity": line.quantity,
                "unit": line.good.unit,
            }
            for line in scn.lines
        ],
        "taxable_value": scn.total_taxable,
        "total_invoice_value": scn.ewb_value,
        "distance_km": float(scn.distance_km),
    }


def build_erp_order(scn: Scenario) -> dict:
    """Render the ERP purchase-order view, including goods receipt."""
    rng = scn.rng
    items = [
        {
            "item_code": line.item_code,
            "description": line.good.description,
            "quantity_ordered": line.quantity,
            "unit": line.good.unit,
            "unit_price": line.rate,
            "line_total": line.taxable,
            "expected_delivery": (
                scn.invoice_issued_at + timedelta(days=rng.randint(2, 9))
            ).strftime("%Y-%m-%d"),
        }
        for line in scn.lines
    ]
    # A GRN exists only once goods were actually booked in.
    grn = {
        "grn_no": scn.grn_no,
        "received_at": _iso(scn.grn_at),
        "received_by": scn.buyer["contact"]["name"],
        "lines": [
            {
                "item_code": line.item_code,
                "quantity_received": line.quantity,
                "condition": "ok",
            }
            for line in scn.lines
        ],
    }
    if scn.defect == "missing_ewb":
        grn = None  # goods held at the check post; nothing booked in
    return {
        "po_no": scn.po_no,
        "po_date": scn.po_date.strftime("%Y-%m-%d"),
        "buyer_entity": scn.buyer["legal_name"],
        "vendor_code": f"VND-{scn.rng.randint(1000, 9999)}",
        "vendor_name": scn.seller["name"],
        "vendor_gstin": scn.seller["gstin"],
        "items": items,
        "po_subtotal": scn.total_taxable,
        "po_tax": scn.total_tax,
        "po_total": scn.invoice_total,
        "currency": "INR",
        "payment_terms": rng.choice(["Net 15 days", "Net 30 days", "Net 45 days", "Advance 50%"]),
        "status": "pending" if grn is None else rng.choice(["fulfilled", "partially_fulfilled"]),
        "approval": {
            "approved_by": scn.buyer["contact"]["name"],
            "approved_at": _iso(scn.approved_at),
        },
        "invoice_refs": [scn.invoice_no],
        "grn": grn,
        "consignment_ref": scn.consignment_ref,
    }


def build_flag(scn: Scenario) -> dict | None:
    """Raise a human exception flag when the scenario warrants one."""
    rng = scn.rng
    kinds = {
        "value_mismatch": (
            "value_query",
            "Declared value on the permit does not tie to the tax invoice. Held for accounts review.",
        ),
        "missing_ewb": (
            "docs_pending",
            "Consignment moved without an e-way bill. Detained at check post pending documentation.",
        ),
        "delivery_after_expiry": (
            "compliance_hold",
            "Goods delivered against a lapsed e-way bill. Compliance sign-off required.",
        ),
        "ewb_before_invoice": (
            "compliance_hold",
            "Permit generated ahead of the tax invoice it cites. Sequence under review.",
        ),
        "pod_before_dispatch": (
            "value_query",
            "Proof of delivery timestamped before dispatch. Suspected backdated entry.",
        ),
    }
    if scn.defect not in kinds:
        return None
    if rng.random() < 0.35:
        return None  # not every problem gets flagged by a human — that is the point
    kind, note = kinds[scn.defect]
    return {
        "flag_id": f"FLG-{rng.randint(10000, 99999)}",
        "raised_at": _iso(scn.grn_at + timedelta(hours=rng.randint(1, 12))),
        "raised_by": scn.buyer["contact"]["name"],
        "kind": kind,
        "note": note,
    }


def build_events(scn: Scenario, thread: dict | None, evidence: dict | None = None) -> list[dict]:
    """Assemble the case timeline from the scenario clock.

    The timeline is the structural counterpart of the chat thread: temporal
    questions resolve against it instead of against prose.

    Args:
        scn: The scenario supplying the clock.
        thread: The chat thread, if one exists.
        evidence: The thread's evidence index, used to point the ``pod_signed``
            event at the message that actually carries the POD. Taking the
            thread's *last* message instead is wrong whenever a later beat —
            an accounts query, a correction — follows the POD.
    """
    ev: list[tuple[datetime, str, str, str | None, str | None]] = [
        (scn.po_date, "po_raised", scn.buyer["legal_name"], scn.po_no, None),
        (scn.approved_at, "po_approved", scn.buyer["contact"]["name"], scn.po_no, None),
    ]
    if scn.revision_no > 0 and scn.original_issued_at is not None:
        ev.append(
            (
                scn.original_issued_at,
                "invoice_issued",
                scn.seller["legal_name"],
                scn.superseded_invoice_no,
                "original issue",
            )
        )
        ev.append(
            (
                scn.invoice_issued_at,
                "invoice_revised",
                scn.seller["legal_name"],
                scn.invoice_no,
                f"supersedes {scn.superseded_invoice_no}",
            )
        )
    else:
        ev.append(
            (
                scn.invoice_issued_at,
                "invoice_issued",
                scn.seller["legal_name"],
                scn.invoice_no,
                None,
            )
        )

    if scn.has_ewb:
        ev.append(
            (scn.ewb_generated_at, "ewb_generated", scn.seller["legal_name"], scn.ewb_no, None)
        )
        for ext in scn.ewb_extensions:
            ev.append(
                (
                    datetime.strptime(ext["extended_at"][:19], "%Y-%m-%dT%H:%M:%S"),
                    "ewb_extended",
                    scn.transporter_name,
                    scn.ewb_no,
                    ext["reason"],
                )
            )
    ev.append((scn.dispatched_at, "dispatched", scn.transporter_name, scn.vehicle_no, None))
    ev.append((scn.arrived_at, "arrived", scn.transporter_name, scn.vehicle_no, None))
    ev.append((scn.delivered_at, "delivered", scn.transporter_name, scn.consignment_ref, None))
    pod_ref = (evidence or {}).get("pod_signed", {}).get("ref_id")
    ev.append((scn.pod_signed_at, "pod_signed", scn.buyer["contact"]["name"], pod_ref, None))
    if scn.defect != "missing_ewb":
        ev.append((scn.grn_at, "grn_recorded", scn.buyer["contact"]["name"], scn.grn_no, None))

    ev.sort(key=lambda row: row[0])
    return [
        {
            "event_id": f"E-{i:03d}",
            "type": kind,
            "ts": _iso(ts),
            "actor": actor,
            "doc_ref": ref,
            "note": note,
        }
        for i, (ts, kind, actor, ref, note) in enumerate(ev, start=1)
    ]


def _flat_address(addr: dict) -> str:
    """One-line rendering, as the government portal prints it."""
    parts = [
        addr["line1"],
        addr.get("line2"),
        f"{addr['city']}, {addr['state']} - {addr['pincode']}",
    ]
    return ", ".join(p for p in parts if p)

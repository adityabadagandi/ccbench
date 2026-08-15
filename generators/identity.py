"""Synthetic identity primitives: tax ids, parties, people, goods.

Everything here is fake by construction. PANs are drawn from letter
combinations that no real allottee series uses, and GSTINs are built *from*
the PAN so the two are internally consistent — a real GSTIN embeds the
holder's PAN at positions 2..12, and the schema validator enforces it.

All functions take an explicit ``rng`` so a case is reproducible from its seed
alone, independent of module import order or how many draws happened earlier.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

GENERATOR_VERSION = "0.2.0"

# State code -> (state name, place-of-supply label, cities)
STATES: dict[str, tuple[str, list[str]]] = {
    "07": ("Delhi", ["Karol Bagh", "Connaught Place", "Saket", "Okhla Phase II"]),
    "27": ("Maharashtra", ["Andheri East", "Bhiwandi", "Thane", "Chakan"]),
    "29": ("Karnataka", ["Peenya", "Whitefield", "Electronic City", "Nelamangala"]),
    "33": ("Tamil Nadu", ["Ambattur", "Guindy", "Sriperumbudur", "Hosur Road"]),
    "06": ("Haryana", ["Manesar", "Faridabad", "Panipat", "Bahadurgarh"]),
    "09": ("Uttar Pradesh", ["Noida Sector 63", "Ghaziabad", "Kanpur", "Lucknow"]),
    "19": ("West Bengal", ["Salt Lake", "Howrah", "Durgapur", "Dankuni"]),
    "24": ("Gujarat", ["Vatva, Ahmedabad", "Sachin, Surat", "Vadodara", "Rajkot"]),
    "36": ("Telangana", ["Jeedimetla", "Gachibowli", "Medchal", "Patancheru"]),
    "23": ("Madhya Pradesh", ["Pithampur", "Govindpura, Bhopal", "Dewas", "Mandideep"]),
}

# HSN -> (description, unit, plausible per-unit price band, GST rate)
GOODS: dict[str, tuple[str, str, tuple[float, float], int]] = {
    "39173100": ("Flexible tubes and hoses of plastics", "MTR", (18.0, 95.0), 18),
    "73043900": ("Seamless tubes of iron or non-alloy steel", "KGS", (62.0, 140.0), 18),
    "84714110": ("Automatic data processing machines", "NOS", (18500.0, 62000.0), 18),
    "85176290": ("Machines for reception/transmission of data", "NOS", (2400.0, 9800.0), 18),
    "94033000": ("Wooden furniture of a kind used in offices", "NOS", (3200.0, 14500.0), 18),
    "48192010": ("Folding cartons and boxes of paperboard", "KGS", (48.0, 120.0), 12),
    "39231090": ("Plastic boxes and crates for conveyance of goods", "NOS", (85.0, 340.0), 18),
    "76109010": ("Aluminium structures and parts", "KGS", (210.0, 480.0), 18),
    "73181500": ("Threaded screws and bolts of iron or steel", "KGS", (95.0, 260.0), 18),
    "85444999": ("Insulated electric conductors", "MTR", (32.0, 118.0), 18),
    "40111000": ("Pneumatic tyres of rubber, for motor cars", "NOS", (3400.0, 9200.0), 28),
    "52081290": ("Woven cotton fabrics, plain weave", "MTR", (75.0, 210.0), 5),
}

_COMPANY_STEMS = [
    "Shree Ganesh",
    "Patel",
    "Agarwal",
    "Verma",
    "Krishna",
    "Singh & Sons",
    "Mehta Brothers",
    "Reddy",
    "Sharma",
    "Gupta",
    "Iyer",
    "Chatterjee",
    "Nair",
    "Deshmukh",
    "Bhatia",
    "Kulkarni",
    "Rastogi",
    "Pillai",
]
_COMPANY_TAILS = [
    "Trading Co.",
    "Logistics Pvt. Ltd.",
    "Enterprises",
    "Industries",
    "Manufacturing Pvt. Ltd.",
    "Exports",
    "Supply Chain Pvt. Ltd.",
    "Polymers Ltd.",
    "Engineering Works",
    "Distributors",
]
_COMPANY_SUFFIX_DRIFT = {
    "Pvt. Ltd.": ["Pvt Ltd", "Private Limited", "P Ltd"],
    "Co.": ["Company", "Co", "& Co."],
    "Ltd.": ["Limited", "Ltd"],
}

_FIRST_NAMES = [
    "Ramesh",
    "Suresh",
    "Ajay",
    "Vijay",
    "Rajesh",
    "Mahesh",
    "Dinesh",
    "Priya",
    "Anita",
    "Kavita",
    "Sunita",
    "Meena",
    "Deepa",
    "Rekha",
    "Imran",
    "Farhan",
    "Zoya",
    "Sameer",
    "Nikhil",
    "Arjun",
    "Lakshmi",
]
_LAST_NAMES = [
    "Kumar",
    "Yadav",
    "Singh",
    "Patel",
    "Sharma",
    "Gupta",
    "Reddy",
    "Nair",
    "Desai",
    "Joshi",
    "Iyer",
    "Khan",
    "Mishra",
    "Rao",
    "Banerjee",
]

_TRANSPORTERS = [
    "Gati Roadlines",
    "VRL Carriers",
    "Blue Dart Surface",
    "TCI Freight",
    "Safexpress Logistics",
    "Rivigo Movers",
    "Delhivery Surface",
]


@dataclass(frozen=True)
class Good:
    """A tradeable line-item type."""

    hsn: str
    description: str
    unit: str
    price_low: float
    price_high: float
    tax_rate: int


def pick_good(rng: random.Random) -> Good:
    """Pick a random good from the catalogue."""
    hsn = rng.choice(list(GOODS))
    desc, unit, (lo, hi), rate = GOODS[hsn]
    return Good(hsn=hsn, description=desc, unit=unit, price_low=lo, price_high=hi, tax_rate=rate)


def pan(rng: random.Random) -> str:
    """Generate a fake PAN: AAAAB1234C.

    The 4th character encodes holder type; 'C' (company) and 'P' (person) are
    the realistic ones for our parties. The first three letters are drawn from
    a reserved 'QQ'/'ZZ' prefix space that the real allottee series does not
    use, so no generated PAN can collide with a live one.
    """
    reserved = rng.choice(["QQ", "ZZ", "XQ"])
    third = rng.choice(string.ascii_uppercase)
    holder = rng.choice("CP")
    fifth = rng.choice(string.ascii_uppercase)
    digits = f"{rng.randint(0, 9999):04d}"
    check = rng.choice(string.ascii_uppercase)
    return f"{reserved}{third}{holder}{fifth}{digits}{check}"


def gstin_for(pan_str: str, state_code: str, rng: random.Random) -> str:
    """Build a GSTIN around a PAN.

    Format: 2-digit state + 10-char PAN + entity digit + 'Z' + checksum char.
    """
    entity = rng.choice("123456789")
    check = rng.choice(string.ascii_uppercase + string.digits)
    return f"{state_code}{pan_str}{entity}Z{check}"


def company_name(rng: random.Random) -> tuple[str, str]:
    """Return (trading_name, legal_name).

    The trading name may drift from the legal name — 'Patel Logistics Pvt Ltd'
    on the PO versus 'Patel Logistics Pvt. Ltd.' on the invoice. Entity
    resolution across documents is part of the task, so this drift is
    deliberate, but the legal name stays canonical.
    """
    legal = f"{rng.choice(_COMPANY_STEMS)} {rng.choice(_COMPANY_TAILS)}"
    trading = legal
    for suffix, variants in _COMPANY_SUFFIX_DRIFT.items():
        if legal.endswith(suffix) and rng.random() < 0.45:
            trading = legal[: -len(suffix)] + rng.choice(variants)
            break
    return trading, legal


def person_name(rng: random.Random) -> str:
    """Return a full personal name."""
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def email_for(person: str, company_legal: str, rng: random.Random) -> str:
    """Build a plausible work email from a person and company name."""
    first = person.split()[0].lower()
    last = person.split()[-1].lower()
    stem = "".join(ch for ch in company_legal.split()[0].lower() if ch.isalpha()) or "corp"
    pattern = rng.choice([f"{first}.{last}", f"{first}{last[0]}", f"{first[0]}{last}"])
    tld = rng.choice(["co.in", "com", "in"])
    return f"{pattern}@{stem}.{tld}"


def phone(rng: random.Random) -> str:
    """Indian mobile number in a reserved test range."""
    return (
        f"+91-{rng.choice(['70', '80', '90'])}{rng.randint(100, 999)}-{rng.randint(10000, 99999)}"
    )


def address_for(state_code: str, rng: random.Random) -> dict:
    """Build a structured address inside a given state."""
    state, cities = STATES[state_code]
    city = rng.choice(cities)
    unit = rng.choice(["Plot", "Unit", "Godown", "Shed", "Warehouse"])
    return {
        "line1": f"{unit} {rng.randint(1, 240)}, {rng.choice(['Industrial Area', 'Phase II', 'MIDC', 'Export Zone', 'Logistics Park'])}",
        "line2": city,
        "city": city.split(",")[-1].strip(),
        "state": state,
        "state_code": state_code,
        "pincode": f"{rng.randint(1, 8)}{rng.randint(10000, 99999)}",
        "country": "India",
    }


def party(state_code: str, rng: random.Random) -> dict:
    """Build a complete counterparty with tax ids, address and a human contact."""
    trading, legal = company_name(rng)
    pan_str = pan(rng)
    contact_person = person_name(rng)
    return {
        "name": trading,
        "legal_name": legal,
        "gstin": gstin_for(pan_str, state_code, rng),
        "pan": pan_str,
        "address": address_for(state_code, rng),
        "contact": {
            "name": contact_person,
            "email": email_for(contact_person, legal, rng),
            "phone": phone(rng),
        },
    }


def vehicle_no(state_code: str, rng: random.Random) -> str:
    """Indian commercial vehicle registration, plated to the dispatch state."""
    state_alpha = {
        "07": "DL",
        "27": "MH",
        "29": "KA",
        "33": "TN",
        "06": "HR",
        "09": "UP",
        "19": "WB",
        "24": "GJ",
        "36": "TS",
        "23": "MP",
    }[state_code]
    series = "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=2))
    return f"{state_alpha}{rng.randint(10, 99)}{series}{rng.randint(1000, 9999)}"


def transporter(rng: random.Random) -> tuple[str, str]:
    """Return (transporter_name, transporter_id)."""
    name = rng.choice(_TRANSPORTERS)
    tid = f"{rng.choice(list(STATES))}{''.join(rng.choices(string.ascii_uppercase, k=5))}{rng.randint(1000, 9999)}{rng.choice(string.ascii_uppercase)}1ZT"
    return name, tid

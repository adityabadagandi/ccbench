"""Synthetic Indian tax identifier generators.

Produces valid-format but entirely fake GSTINs, PANs, and HSN codes.
No real business or personal identifiers are ever used.
"""

from __future__ import annotations

import random
import string


# State codes under Indian GST (first 2 digits of GSTIN)
STATE_CODES = {
    "07": "Delhi",
    "27": "Maharashtra",
    "29": "Karnataka",
    "33": "Tamil Nadu",
    "06": "Haryana",
    "09": "Uttar Pradesh",
    "19": "West Bengal",
    "24": "Gujarat",
    "36": "Telangana",
    "23": "Madhya Pradesh",
}

# Common HSN codes for logistics/manufacturing
HSN_CODES = {
    "3917": "Tubes, pipes and hoses of plastics",
    "7304": "Tubes, pipes of iron/steel",
    "8471": "Automatic data processing machines",
    "8517": "Telephone sets",
    "8704": "Motor vehicles for goods transport",
    "9403": "Furniture and parts",
    "4802": "Paper and paperboard",
    "3923": "Articles for packaging of plastics",
    "7610": "Aluminum structures",
    "7318": "Screws, bolts, nuts of iron/steel",
}


def _pan() -> str:
    """Generate a fake PAN-like 10-char string: AAAAB1234C."""
    letters = "".join(random.choices(string.ascii_uppercase, k=5))
    digits = "".join(random.choices(string.digits, k=4))
    last = random.choice(string.ascii_uppercase)
    return f"{letters}{digits}{last}"


def gstin(state_code: str | None = None) -> str:
    """Generate a valid-format fake GSTIN.

    Format: 2-digit state + 10-char PAN + 1 entity + Z + 1 checksum
    Example: 07AABCU9603R1ZX

    Args:
        state_code: Specific state code, or random if None.

    Returns:
        A fake GSTIN string.
    """
    if state_code is None:
        state_code = random.choice(list(STATE_CODES.keys()))
    pan = _pan()
    entity = random.choice(string.digits)
    return f"{state_code}{pan}{entity}Z{random.choice(string.digits)}"


def pan() -> str:
    """Generate a fake PAN.

    Format: AAAAB1234C
    """
    return _pan()


def hsn_code() -> str:
    """Return a random HSN code from the predefined set."""
    return random.choice(list(HSN_CODES.keys()))


def hsn_description(code: str) -> str:
    """Return description for an HSN code."""
    return HSN_CODES.get(code, "Miscellaneous manufactured articles")


def state_from_gstin(gstin_str: str) -> str:
    """Extract state name from a GSTIN's first 2 digits."""
    code = gstin_str[:2]
    return STATE_CODES.get(code, "Unknown")

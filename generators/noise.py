"""Noise injector for synthetic documents.

Introduces realistic imperfections: OCR typos, format variance,
near-duplicate names, date format changes.
"""

from __future__ import annotations

import random
import string


def _ocr_typo(text: str, probability: float = 0.05) -> str:
    """Randomly introduce OCR-style character substitutions."""
    ocr_map = {
        "0": "O",
        "O": "0",
        "1": "I",
        "I": "1",
        "5": "S",
        "S": "5",
        "8": "B",
        "B": "8",
        "rn": "m",
        "m": "rn",
    }
    result = []
    for ch in text:
        if random.random() < probability and ch in ocr_map:
            result.append(ocr_map[ch])
        else:
            result.append(ch)
    return "".join(result)


def _date_format_variance(date_str: str) -> str:
    """Change date format randomly."""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    return dt.strftime(random.choice(formats))


def _currency_variance(amount: float) -> str:
    """Format amount with different currency notations."""
    formats = [
        f"₹{amount:,.2f}",
        f"Rs. {amount:,.2f}",
        f"INR {amount:,.2f}",
        f"{amount:,.2f}",
    ]
    return random.choice(formats)


def _near_duplicate(name: str) -> str:
    """Create a near-duplicate company name."""
    variants = {
        "Shree Ganesh Trading Co.": ["Sri Ganesh Trading Co.", "Shree Ganesh Traders", "Shree Ganesh Trading"],
        "Patel Logistics Pvt. Ltd.": ["Patel Logistics Ltd.", "Patel Logistic Pvt Ltd", "Petal Logistics Pvt. Ltd."],
    }
    if name in variants:
        return random.choice(variants[name] + [name])
    return name


def inject_noise(document: dict, noise_level: str = "medium") -> dict:
    """Apply noise to a document dictionary.

    Args:
        document: The document to mutate.
        noise_level: "low", "medium", or "high".

    Returns:
        Mutated document (modified in place).
    """
    prob = {"low": 0.02, "medium": 0.05, "high": 0.10}[noise_level]

    # OCR typos in string fields
    for key, val in document.items():
        if isinstance(val, str) and key not in ("gstin", "pan"):
            if random.random() < prob:
                document[key] = _ocr_typo(val, probability=prob)
        elif isinstance(val, dict):
            inject_noise(val, noise_level)

    return document

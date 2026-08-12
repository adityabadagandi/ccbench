"""Synthetic WhatsApp POD thread generator.

Generates Hindi/English code-switched delivery confirmation threads.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

# Common Hindi phrases mixed with English (logistics context)
HINDI_PHRASES = {
    "departed": [
        "Sir, truck {vehicle} nikli {from_city} se. E-way bill check kar liya.",
        "{vehicle} chal padi. Loading complete.",
        "Dispatch ho gaya sir. {from_city} se nikle hain.",
    ],
    "transit": [
        "Highway pe hain. Traffic thoda hai par time pe pahunchenge.",
        "Toll plaza cross kar liya. Sab smooth chal raha hai.",
    ],
    "arrived": [
        "{to_city} warehouse pahunch gaya. Samaan unload ho raha hai.",
        "Delivery ho gayi sir. {to_city} mein warehouse par pahunche.",
        "Sab sahi salamat pahunch gaya. Unloading almost complete.",
    ],
    "pod_request": [
        "OK {driver_name} bhai. POD sign karwa ke bhejo.",
        "Photo bhejo delivery ka. Invoice match kar rahe hain.",
        "POD chahiye urgently. Sign karwa ke WhatsApp karo.",
    ],
    "pod_done": [
        "POD sign ho gaya. Yahan photo bhej raha hoon.",
        "Sab done sir. Sign karwa liye hain warehouse se.",
    ],
}

DRIVER_NAMES = [
    "Ramesh Kumar",
    "Suresh Yadav",
    "Ajay Singh",
    "Vijay Patel",
    "Rajesh Sharma",
    "Mahesh Gupta",
    "Dinesh Reddy",
]


def _format_message(template: str, **kwargs) -> str:
    """Format a Hindi/English template with given values."""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def generate_whatsapp(
    invoice: dict,
    eway_bill: dict | None,
    seed: int | None = None,
) -> dict | None:
    """Generate a synthetic WhatsApp POD thread.

    Args:
        invoice: Parent invoice (for vehicle, cities).
        eway_bill: Parent e-way bill (for timestamps) or None.
        seed: Random seed.

    Returns:
        WhatsApp thread dictionary or None if not applicable.
    """
    if seed is not None:
        random.seed(seed)

    driver = random.choice(DRIVER_NAMES)
    vehicle = invoice.get("vehicle_no", "UNKNOWN")

    # Extract city names from addresses (rough)
    from_addr = invoice["seller"]["address"]
    to_addr = invoice["buyer"]["address"]
    from_city = from_addr.split(",")[0].strip() if "," in from_addr else "Delhi"
    to_city = to_addr.split(",")[0].strip() if "," in to_addr else "Mumbai"

    # Base timestamps from invoice date
    inv_date = datetime.strptime(invoice["date"], "%Y-%m-%d")

    messages = []

    # Message 1: Departure
    msg1_time = inv_date + timedelta(hours=6)
    messages.append(
        {
            "timestamp": msg1_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "sender": driver,
            "text": _format_message(
                random.choice(HINDI_PHRASES["departed"]),
                vehicle=vehicle,
                from_city=from_city,
            ),
        }
    )

    # Message 2: Arrival (only if e-way bill exists)
    if eway_bill:
        ewb_gen = datetime.fromisoformat(eway_bill["generation_date"].replace("+05:30", ""))
        msg2_time = ewb_gen + timedelta(hours=random.randint(18, 30))
        messages.append(
            {
                "timestamp": msg2_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                "sender": driver,
                "text": _format_message(
                    random.choice(HINDI_PHRASES["arrived"]),
                    to_city=to_city,
                ),
            }
        )

        # Message 3: POD request from warehouse
        msg3_time = msg2_time + timedelta(hours=2)
        messages.append(
            {
                "timestamp": msg3_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                "sender": f"{invoice['buyer']['name']} - Warehouse",
                "text": _format_message(
                    random.choice(HINDI_PHRASES["pod_request"]),
                    driver_name=driver.split()[0],
                ),
            }
        )

        # Message 4: POD done
        msg4_time = msg3_time + timedelta(minutes=random.randint(30, 90))
        messages.append(
            {
                "timestamp": msg4_time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                "sender": driver,
                "text": random.choice(HINDI_PHRASES["pod_done"]),
            }
        )

    return {
        "thread_id": f"WA-{random.randint(1000, 9999)}",
        "driver_name": driver,
        "driver_phone": f"+91-{random.randint(70000, 99999)}-{random.randint(10000, 99999)}",
        "messages": messages,
        "delivery_confirmed": len(messages) >= 3,
        "pod_signed_by": f"Warehouse In-charge, {to_city}",
    }

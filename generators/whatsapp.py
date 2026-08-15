"""Operational chat thread generator.

Threads are built as a sequence of *beats* driven by the scenario, not as a
fixed four-message script. A beat may or may not fire, may carry an
attachment, may be replied to, may be corrected later, and is written in
English, romanised Hinglish, or Devanagari Hindi depending on who is speaking.

Two decisions matter for the benchmark:

1. The thread carries no ``delivery_confirmed`` boolean. Whether the goods
   arrived is stated only in the message text — often in the non-English
   part. A system that drops non-English content cannot recover it.
2. Every beat that a question may rest on returns an *evidence span*: the
   msg_id, its language, and the verbatim clause. That is what makes
   cross-lingual answers scoreable instead of merely plausible.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from .scenario import Scenario, _iso

# ---------------------------------------------------------------------------
# Phrase banks. Each entry is (lang, template, span_template, gloss).
# ``span_template`` must format to a verbatim substring of the rendered text.
# ---------------------------------------------------------------------------

# Dispatch beats that assert the paperwork is in order. Never used on a
# missing_ewb scenario — a driver claiming the permit is in the cab and then
# reporting it was never generated is a contradiction the case does not intend.
DISPATCH = [
    (
        "hi-en",
        "Sir {vehicle} loading complete, nikal rahe hain abhi. E-way bill gaadi mein hai.",
        "nikal rahe hain abhi",
        "we are leaving now",
    ),
    (
        "hi",
        "सर {vehicle} की लोडिंग पूरी हो गई है, गाड़ी निकल रही है। ई-वे बिल साथ में है।",
        "गाड़ी निकल रही है",
        "the vehicle is departing",
    ),
    (
        "hi-en",
        "{vehicle} dispatch ho gayi {from_city} se. Driver nikal chuka hai.",
        "dispatch ho gayi",
        "has been dispatched",
    ),
    (
        "en",
        "Vehicle {vehicle} dispatched from {from_city}. Documents handed to driver.",
        "dispatched from",
        "dispatched from",
    ),
]

# Dispatch beats that stay silent about the permit.
DISPATCH_NO_DOCS = [
    (
        "hi-en",
        "{vehicle} loading complete sir, nikal rahe hain {from_city} se.",
        "nikal rahe hain",
        "we are leaving",
    ),
    (
        "hi",
        "सर {vehicle} की लोडिंग पूरी हो गई है, गाड़ी निकल रही है।",
        "गाड़ी निकल रही है",
        "the vehicle is departing",
    ),
    (
        "hi-en",
        "{vehicle} dispatch ho gayi {from_city} se. Driver nikal chuka hai.",
        "dispatch ho gayi",
        "has been dispatched",
    ),
    ("en", "Vehicle {vehicle} has left {from_city}.", "has left", "has left"),
]

# What the office actually says once a vehicle is detained: chase the permit,
# not a proof of delivery that cannot exist yet.
DOCS_CHASE = [
    (
        "hi-en",
        "Ruko wahin. Main abhi portal se e-way bill generate karwata hoon.",
        "Main abhi portal se e-way bill generate karwata hoon",
        "I will get the e-way bill generated from the portal now",
    ),
    (
        "en",
        "Hold the vehicle there. We are raising the e-way bill on the portal now.",
        "raising the e-way bill on the portal",
        "raising the e-way bill on the portal",
    ),
    (
        "hi",
        "गाड़ी वहीं रोको। हम पोर्टल से ई-वे बिल बनवा रहे हैं।",
        "ई-वे बिल बनवा रहे हैं",
        "we are getting the e-way bill generated",
    ),
]

TRANSIT = [
    (
        "hi-en",
        "Highway pe hain sir. Thoda traffic mila par time pe pahunch jayenge.",
        "time pe pahunch jayenge",
        "will arrive on time",
    ),
    ("hi", "अभी रास्ते में हैं। टोल पार कर लिया है।", "अभी रास्ते में हैं", "currently en route"),
    (
        "hi-en",
        "Toll cross kar liya. Raat tak {to_city} pahunch jayenge.",
        "Raat tak {to_city} pahunch jayenge",
        "will reach {to_city} by night",
    ),
    (
        "en",
        "Crossed the state border checkpost. On schedule for {to_city}.",
        "On schedule for",
        "on schedule for",
    ),
]

ARRIVED = [
    (
        "hi-en",
        "{to_city} warehouse pahunch gaye sir. Unloading start ho rahi hai.",
        "pahunch gaye",
        "have arrived",
    ),
    ("hi", "गाड़ी {to_city} गोदाम पहुँच गई है। माल उतारा जा रहा है।", "पहुँच गई है", "has arrived"),
    (
        "hi-en",
        "Gaadi gate pe lag gayi hai. Unloading shuru.",
        "Unloading shuru",
        "unloading has begun",
    ),
]

DELIVERED = [
    (
        "hi-en",
        "Delivery ho gayi sir. Poora maal utar gaya, kuch damage nahi hai.",
        "Delivery ho gayi",
        "delivery has been completed",
    ),
    (
        "hi",
        "डिलीवरी हो गई है सर। पूरा माल सही सलामत उतर गया।",
        "डिलीवरी हो गई है",
        "the delivery has been completed",
    ),
    (
        "hi-en",
        "Sab maal receive kar liya humne. Delivery complete hai.",
        "Delivery complete hai",
        "delivery is complete",
    ),
    (
        "en",
        "Consignment received in full at our {to_city} warehouse. Delivery complete.",
        "Delivery complete",
        "delivery complete",
    ),
]

POD_REQUEST = [
    (
        "hi-en",
        "{driver_first} bhai POD sign karwa ke photo bhej do please.",
        "POD sign karwa ke photo bhej do",
        "get the POD signed and send a photo",
    ),
    (
        "en",
        "Please share the signed POD before end of day.",
        "share the signed POD",
        "share the signed POD",
    ),
    (
        "hi",
        "कृपया साइन किया हुआ POD भेज दीजिए।",
        "साइन किया हुआ POD भेज दीजिए",
        "please send the signed POD",
    ),
]

POD_DONE = [
    (
        "hi-en",
        "POD sign ho gaya sir, photo attach kar raha hoon.",
        "POD sign ho gaya",
        "the POD has been signed",
    ),
    ("hi", "POD पर हस्ताक्षर हो गए हैं, फोटो भेज रहा हूँ।", "हस्ताक्षर हो गए हैं", "has been signed"),
    (
        "en",
        "Signed POD attached. Received by warehouse in-charge.",
        "Signed POD attached",
        "signed POD attached",
    ),
]

DETAINED = [
    (
        "hi-en",
        "Sir gaadi check post pe rok di hai. E-way bill nahi bana tha, ab problem ho rahi hai.",
        "E-way bill nahi bana tha",
        "the e-way bill was never generated",
    ),
    (
        "hi",
        "सर गाड़ी चेक पोस्ट पर रोक दी गई है। ई-वे बिल बना ही नहीं था।",
        "ई-वे बिल बना ही नहीं था",
        "the e-way bill was never generated at all",
    ),
    (
        "hi-en",
        "Inspector ne gaadi rok li. Bol rahe hain e-way bill ke bina aage nahi ja sakti.",
        "e-way bill ke bina aage nahi ja sakti",
        "cannot proceed without the e-way bill",
    ),
]

VALUE_QUERY = [
    (
        "hi-en",
        "Accounts se query aayi hai — e-way bill pe value {ewb_val} likhi hai par invoice {inv_val} ka hai.",
        "e-way bill pe value {ewb_val} likhi hai par invoice {inv_val} ka hai",
        "the e-way bill states {ewb_val} but the invoice is for {inv_val}",
    ),
    (
        "en",
        "Flagging a mismatch: permit declares {ewb_val} against an invoice of {inv_val}. Please confirm which is correct.",
        "permit declares {ewb_val} against an invoice of {inv_val}",
        "permit declares {ewb_val} against an invoice of {inv_val}",
    ),
]

EXPIRY_QUERY = [
    (
        "hi-en",
        "Sir e-way bill ki validity {valid_until} ko khatam ho gayi thi, gaadi uske baad pahunchi.",
        "validity {valid_until} ko khatam ho gayi thi",
        "validity expired on {valid_until}",
    ),
    (
        "en",
        "Note: the permit lapsed on {valid_until} and the vehicle reached after that.",
        "the permit lapsed on {valid_until}",
        "the permit lapsed on {valid_until}",
    ),
]

SEQUENCE_QUERY = [
    (
        "hi-en",
        "Ek gadbad hai — POD ka time dispatch se pehle ka lag raha hai. Check karo.",
        "POD ka time dispatch se pehle ka lag raha hai",
        "the POD time appears to precede dispatch",
    ),
    (
        "en",
        "The POD timestamp precedes the dispatch timestamp. Please verify the entry.",
        "POD timestamp precedes the dispatch timestamp",
        "POD timestamp precedes the dispatch timestamp",
    ),
]

# Off-topic noise, split by who would plausibly send it. A driver does not
# add someone to the group or announce warehouse holidays.
DRIVER_CHATTER = [
    ("hi-en", "Bhai khana kha liya? Dhaba aa raha hai aage.", None, None),
    ("hi-en", "Diesel bhar liya hai, paisa account mein daal dena.", None, None),
    ("hi", "कल की गाड़ी का क्या हुआ?", None, None),
    ("hi-en", "Network issue tha subah, ab theek hai.", None, None),
    ("hi-en", "Tyre change karwana padega wapsi mein.", None, None),
]

OFFICE_CHATTER = [
    ("en", "Adding accounts to this group for the billing follow-up.", None, None),
    ("hi-en", "Sunday ko warehouse band rahega, plan kar lena.", None, None),
    ("hi-en", "Next month se naya vendor portal use karna hai.", None, None),
    ("hi", "बाकी गाड़ियों की लिस्ट कल भेज दूँगा।", None, None),
    ("en", "Reminder: submit the fuel bills before the 5th.", None, None),
]

CORRECTION = [
    ("hi-en", "Sorry sir galat likh diya tha, sahi number {correct} hai.", None, None),
    ("en", "Correction to my earlier message — please read {correct}.", None, None),
]

_TYPOS = {
    "hai": "hain",
    "gaya": "gya",
    "nahi": "nhi",
    "karo": "kro",
    "please": "pls",
    "warehouse": "warehse",
    "sir": "sr",
}


def _typo(text: str, rng: random.Random, protected: str | None) -> tuple[str, bool]:
    """Introduce one chat-style abbreviation, never inside the evidence span.

    Noise is applied at write time and only outside protected spans, so gold
    evidence stays a verbatim substring. The 0.1 pipeline mutated documents
    *after* extracting facts, which is a different and more dangerous thing.
    """
    if rng.random() > 0.18:
        return text, False
    for src, dst in _TYPOS.items():
        if src in text and (protected is None or src not in protected):
            return text.replace(src, dst, 1), True
    return text, False


class _ThreadBuilder:
    """Accumulates messages and the evidence index for one thread."""

    def __init__(self, scn: Scenario, rng: random.Random) -> None:
        self.scn = scn
        self.rng = rng
        self.messages: list[dict[str, Any]] = []
        self.evidence: dict[str, dict[str, str]] = {}
        self._n = 0
        self._last_id: str | None = None

    def add(
        self,
        bank: list[tuple[str, str, str | None, str | None]],
        sender: dict[str, str],
        ts: datetime,
        *,
        key: str | None = None,
        fmt: dict[str, Any] | None = None,
        attachments: list[dict] | None = None,
        reply: bool = False,
        force_lang: str | None = None,
    ) -> str:
        """Render one beat and append it. Returns the new msg_id."""
        choices = bank
        if force_lang is not None:
            filtered = [row for row in bank if row[0] == force_lang]
            if filtered:
                choices = filtered
        lang, template, span_tpl, gloss = self.rng.choice(choices)
        fmt = fmt or {}
        text = template.format(**fmt)
        span = span_tpl.format(**fmt) if span_tpl else None
        text, edited = _typo(text, self.rng, span)

        self._n += 1
        msg_id = f"M-{self._n:03d}"
        self.messages.append(
            {
                "msg_id": msg_id,
                "ts": _iso(ts),
                "sender_id": sender["participant_id"],
                "sender_name": sender["name"],
                "lang": lang,
                "text": text,
                "reply_to": self._last_id if (reply and self._last_id) else None,
                "attachments": attachments or [],
                "edited": edited,
            }
        )
        self._last_id = msg_id
        if key and span:
            assert span in text, f"evidence span {span!r} not verbatim in {text!r}"
            self.evidence[key] = {
                "ref_id": msg_id,
                "lang": lang,
                "span": span,
                "gloss_en": gloss.format(**fmt) if gloss else None,
            }
        return msg_id


def build_thread(scn: Scenario, evidence_lang: str | None = None) -> tuple[dict, dict]:
    """Build an operational chat thread for a scenario.

    Args:
        scn: The scenario to narrate.
        evidence_lang: If given ('hi' or 'hi-en'), force the key delivery and
            defect beats into that language. Used by the cross-lingual bucket
            so the answer genuinely cannot be recovered from English alone.

    Returns:
        ``(thread, evidence_index)``. The index maps a semantic key such as
        ``'delivered'`` or ``'detained'`` to an evidence-span dict ready to
        drop into a ``gold_fact``.
    """
    rng = scn.rng
    from_city = scn.seller["address"]["city"]
    to_city = scn.buyer["address"]["city"]

    driver_name = _driver_name(rng)
    participants = [
        {
            "participant_id": "P1",
            "name": driver_name,
            "role": "driver",
            "phone": scn.seller["contact"]["phone"],
        },
        {
            "participant_id": "P2",
            "name": scn.seller["contact"]["name"],
            "role": "dispatcher",
            "phone": scn.seller["contact"]["phone"],
        },
        {
            "participant_id": "P3",
            "name": scn.buyer["contact"]["name"],
            "role": "warehouse",
            "phone": scn.buyer["contact"]["phone"],
        },
    ]
    if rng.random() < 0.55:
        participants.append(
            {
                "participant_id": "P4",
                "name": _person(rng),
                "role": "accounts",
                "phone": scn.buyer["contact"]["phone"],
            }
        )
    driver, dispatcher, warehouse = participants[0], participants[1], participants[2]
    accounts = participants[3] if len(participants) > 3 else dispatcher

    b = _ThreadBuilder(scn, rng)
    base_fmt = {
        "vehicle": scn.vehicle_no,
        "from_city": from_city,
        "to_city": to_city,
        "driver_first": driver_name.split()[0],
    }

    # --- dispatch -------------------------------------------------------
    dispatch_bank = DISPATCH_NO_DOCS if scn.defect == "missing_ewb" else DISPATCH
    b.add(dispatch_bank, driver, scn.dispatched_at, key="dispatched", fmt=base_fmt)

    if rng.random() < 0.4:
        b.add(
            DRIVER_CHATTER,
            driver,
            scn.dispatched_at + timedelta(minutes=rng.randint(20, 90)),
            fmt=base_fmt,
        )

    # --- detention short-circuits the journey ---------------------------
    if scn.defect == "missing_ewb":
        b.add(
            DETAINED,
            driver,
            scn.dispatched_at + timedelta(hours=rng.randint(2, 9)),
            key="detained",
            fmt=base_fmt,
            force_lang=evidence_lang,
        )
        b.add(
            DOCS_CHASE,
            dispatcher,
            scn.dispatched_at + timedelta(hours=rng.randint(10, 14)),
            fmt=base_fmt,
            reply=True,
        )
        if rng.random() < 0.35:
            b.add(
                OFFICE_CHATTER,
                accounts,
                scn.dispatched_at + timedelta(hours=rng.randint(15, 22)),
                fmt=base_fmt,
            )
        thread = _finish(scn, participants, b, rng)
        return thread, b.evidence

    # --- transit --------------------------------------------------------
    n_transit = rng.choices([0, 1, 2], weights=[20, 50, 30])[0]
    for i in range(n_transit):
        ts = scn.dispatched_at + (scn.arrived_at - scn.dispatched_at) * ((i + 1) / (n_transit + 1))
        attach = None
        if rng.random() < 0.25:
            attach = [
                {
                    "type": "location",
                    "filename": f"location_{rng.randint(100, 999)}.json",
                    "caption": None,
                }
            ]
        b.add(TRANSIT, driver, ts, fmt=base_fmt, attachments=attach)

    # --- expiry note ----------------------------------------------------
    if scn.defect == "delivery_after_expiry":
        b.add(
            EXPIRY_QUERY,
            accounts,
            scn.arrived_at - timedelta(hours=1),
            key="expired",
            fmt={**base_fmt, "valid_until": scn.ewb_valid_until.strftime("%d %b %Y")},
            force_lang=evidence_lang,
        )

    # --- arrival & delivery ---------------------------------------------
    b.add(ARRIVED, driver, scn.arrived_at, key="arrived", fmt=base_fmt, force_lang=evidence_lang)

    if rng.random() < 0.3:
        b.add(
            OFFICE_CHATTER,
            warehouse,
            scn.arrived_at + timedelta(minutes=rng.randint(5, 40)),
            fmt=base_fmt,
        )

    b.add(
        DELIVERED,
        warehouse if rng.random() < 0.5 else driver,
        scn.delivered_at,
        key="delivered",
        fmt=base_fmt,
        force_lang=evidence_lang,
    )

    # --- POD ------------------------------------------------------------
    b.add(
        POD_REQUEST,
        warehouse,
        scn.delivered_at + timedelta(minutes=rng.randint(10, 45)),
        fmt=base_fmt,
        reply=True,
    )
    pod_attachment = [
        {
            "type": "image",
            "filename": f"POD_{scn.consignment_ref}_{rng.randint(10, 99)}.jpg",
            "caption": rng.choice([None, "POD signed copy", "Signed challan"]),
        }
    ]
    if rng.random() < 0.2:
        pod_attachment.append(
            {
                "type": "voice_note",
                "filename": f"AUD-{rng.randint(1000, 9999)}.opus",
                "caption": None,
                "transcript": "Sir POD sign ho gaya hai, warehouse in-charge ne receive kiya.",
            }
        )
    b.add(
        POD_DONE,
        driver,
        scn.pod_signed_at,
        key="pod_signed",
        fmt=base_fmt,
        attachments=pod_attachment,
        reply=True,
        force_lang=evidence_lang,
    )

    # --- defect-specific accounts follow-up -----------------------------
    if scn.defect == "value_mismatch":
        b.add(
            VALUE_QUERY,
            accounts,
            scn.grn_at + timedelta(hours=rng.randint(1, 8)),
            key="value_query",
            fmt={
                **base_fmt,
                "ewb_val": f"Rs. {scn.ewb_value:,.2f}",
                "inv_val": f"Rs. {scn.invoice_total:,.2f}",
            },
            force_lang=evidence_lang,
        )
    if scn.defect == "pod_before_dispatch":
        b.add(
            SEQUENCE_QUERY,
            accounts,
            scn.grn_at + timedelta(hours=rng.randint(1, 6)),
            key="sequence_query",
            fmt=base_fmt,
            force_lang=evidence_lang,
        )

    if rng.random() < 0.25:
        b.add(
            CORRECTION,
            accounts,
            scn.grn_at + timedelta(hours=rng.randint(9, 20)),
            fmt={**base_fmt, "correct": scn.invoice_no},
            reply=True,
        )

    thread = _finish(scn, participants, b, rng)
    return thread, b.evidence


def _finish(scn: Scenario, participants: list[dict], b: _ThreadBuilder, rng: random.Random) -> dict:
    """Seal the thread, sorting messages into true chronological order."""
    msgs = sorted(b.messages, key=lambda m: m["ts"])
    seen: set[str] = set()
    for m in msgs:
        # A reply cannot point forward in time once messages are ordered.
        if m["reply_to"] is not None and m["reply_to"] not in seen:
            m["reply_to"] = None
        seen.add(m["msg_id"])
    return {
        "thread_id": f"WA-{rng.randint(10000, 99999)}",
        "thread_name": f"{scn.consignment_ref} — Dispatch",
        "participants": participants,
        "messages": msgs,
    }


_DRIVER_FIRST = [
    "Ramesh",
    "Suresh",
    "Ajay",
    "Vijay",
    "Rajesh",
    "Mahesh",
    "Dinesh",
    "Balwinder",
    "Imran",
]
_DRIVER_LAST = ["Kumar", "Yadav", "Singh", "Patel", "Sharma", "Gupta", "Reddy", "Khan"]


def _driver_name(rng: random.Random) -> str:
    return f"{rng.choice(_DRIVER_FIRST)} {rng.choice(_DRIVER_LAST)}"


def _person(rng: random.Random) -> str:
    from .identity import person_name

    return person_name(rng)

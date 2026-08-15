"""Shared text handling for claims and citations.

Lives in ``benchmark`` rather than ``harness`` on purpose: both the dataset
validator and the faithfulness metric segment answers the same way, and if
they ever drifted apart the answer key could pass validation while failing the
metric it is supposed to define.
"""

from __future__ import annotations

import re

CITATION = re.compile(r"\[([A-Za-z0-9\-]+)\]")

# Abbreviations whose trailing period does not end a sentence. "Rs." is the
# one that matters: it appears in nearly every monetary answer, and splitting
# on it shreds a two-claim answer into five fragments and silently deflates
# every faithfulness score.
#
# "No." is deliberately absent — across all gold answers it opens a sentence
# as the negative verdict and never abbreviates "number", so guarding it would
# merge the verdict into the evidence claim that follows.
ABBREVIATIONS = ("Rs.", "Ltd.", "Pvt.", "Co.", "Mr.", "Mrs.", "Dr.", "Inc.")
_GUARD = "".join(rf"(?<!\b{re.escape(a)})" for a in ABBREVIATIONS)

# A sentence ends at . ! ? or the Devanagari danda, but only when what follows
# opens a new one: a capital, a Devanagari letter, or an opening bracket or
# quote. This also protects decimals — "1,000.00 and" never splits.
SENTENCE = re.compile(rf"(?<=[.!?।]){_GUARD}\s+(?=[A-Zऀ-ॿ\"'(\[])")


def split_claims(answer: str) -> list[str]:
    """Segment an answer into claims. One sentence, one claim."""
    return [part.strip() for part in SENTENCE.split(answer.strip()) if part.strip()]


def citations_in(text: str) -> set[str]:
    """Every ``[ID]`` tag appearing in a piece of text."""
    return set(CITATION.findall(text))

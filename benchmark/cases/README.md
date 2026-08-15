# CCBench cases — schema 0.2

200 cases: 100 dev (full supervision) + 100 test (redacted).

```
benchmark/cases/
├── dev/                       100 full cases — gold_answer, gold_facts, gold_label visible
├── test/                      100 redacted cases — documents and question only
└── test_gold.private.json     answer key for the test split (gitignored, never distributed)
```

Regenerate with `python generate_dataset.py`. The master seed is `20260815`;
the same seed reproduces the corpus byte-for-byte.

## What a case contains

| Field | Notes |
|---|---|
| `documents.invoice` | GST invoice, 1–4 lines, IGST for inter-state and CGST+SGST for intra-state, timestamped to the minute, optionally a revision superseding an earlier invoice |
| `documents.eway_bill` | Permit with `status`, `extensions[]`, statutory validity of one day per 200 km. `null` on `missing_ewb` cases |
| `documents.erp_order` | PO with approval trail and a goods receipt note (`grn`) — the only structured record of physical receipt |
| `documents.whatsapp_pod` | 3–10 messages, 3–4 participants, English / romanised Hinglish / Devanagari, with replies, image PODs, voice-note transcripts and location pins |
| `documents.flag` | A human-raised exception. Present on ~2/3 of defective cases — deliberately not all of them |
| `events` | 7–10 entry timeline: `po_raised` → `grn_recorded`. Temporal questions resolve against this, not against prose |
| `gold_facts` | Objects: `{fact_id, doc, path, value, evidence?}`. `evidence` pins the exact message id, language and verbatim clause |
| `must_not_appear` | Literals the answer must not emit. Non-empty on every EU case, enforced by the schema |

## Splits

Both splits are identical in shape: 20 cases per bucket, 37 `clean`, 20
`compliance_case`, 20 `temporal_violation`, 12 `value_mismatch`, 11
`missing_ewb`.

The test split is redacted of `gold_answer`, `gold_facts`, `gold_label`,
`bucket`, `difficulty` and `must_not_appear`. Bucket and difficulty are
withheld alongside the answers because publishing them would let a method
condition on the task type it is about to be scored on.

**Tune on dev only.** Re-tuning on test invalidates the result.

## Validating

```bash
cd ccbench && python -m benchmark.validate benchmark/cases
```

Checks, across all 200 cases:

- every `gold_fact` path resolves and equals its stated value
- every evidence span is a verbatim substring of the message it cites
- no `must_not_appear` literal occurs in the `gold_answer`
- every EU case denies both parties' PANs
- the gold label is **re-derived from the documents**, not trusted: a
  `value_mismatch` case must actually disagree, a `temporal_violation` must
  actually violate an ordering, a `clean` case must do neither
- cross-lingual cases rest on at least one non-English evidence span
- the timeline agrees with the documents it describes
- no duplicate `case_id`, `invoice_no`, `consignment_ref` or `gold_answer`
- the public test split carries no supervision

## Provenance

All identifiers are synthetic. PANs are drawn from `QQ`/`ZZ`/`XQ` prefixes that
the real allottee series does not use, and each GSTIN is built around its
holder's PAN so the two are internally consistent. No real business, person,
invoice or consignment is represented.

Requires Python 3.12+ (`requires-python = ">=3.12"`; the models use `StrEnum`).
Note that `python` on this machine resolves to 3.10, which cannot import
`StrEnum` — invoke `py -3.13` (or any 3.12+) explicitly.

License: CC-BY-SA 4.0.

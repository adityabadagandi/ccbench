# CCBench dataset v0 — DEPRECATED, DO NOT USE

Archived 2026-08-15. **Nothing in the pipeline may read from this directory.**
Kept only for provenance and for before/after comparison in the paper.

Superseded by schema **v0.2** and the dataset in `ccbench/benchmark/cases/`.

## Contents

| Path | What it was |
|---|---|
| `cases-json/` | The former `ccbench-dataset/` — 100 dev + 100 test JSON cases |
| `multiformat/` | The former `ccbench-dataset-multiformat/` — derived txt/csv/json export |
| `*.zip` | Stale snapshots of the two above |

## Why it was retired

An audit on 2026-08-15 found the data structurally valid but semantically
unusable. Every `gold_fact` resolved correctly against its documents, there were
no duplicate document sets, and all 200 cases passed Pydantic validation — but
the supervision was wrong:

1. **56% of gold answers were a placeholder string** (113/200) —
   `"Answer not yet implemented for this bucket/label combination."`
   The `temporal` and `cross-lingual` buckets had no answer templates at all.
2. **Bucket, jurisdiction, and label were drawn independently at random**, so
   21 `IN`-jurisdiction cases asked a question premised on EU GDPR and were
   graded against a GDPR answer.
3. **26 of 34 `lookup` cases asked about HSN code or vehicle number** but were
   graded against an answer that always returned the seller's GSTIN.
4. **`clean` was not clean.** The e-way bill carried the pre-tax value, so it
   never equalled `invoice_total`; the 7 `multi-hop` + `clean` gold answers
   asserted "the amounts match" when they demonstrably did not.
5. **`temporal_violation` was never realised in the documents** — 0 of 160
   e-way bills preceded their invoice, and no WhatsApp thread was out of order.
6. **`cross-lingual` contained no Devanagari** and every case had an identical
   4-message thread drawn from 5 template slots.
7. **No `pan` field existed anywhere**, though the policy table and 38 gold
   answers turned on PAN masking.
8. **`must_not_appear` and `documents.flag` were populated in 0 of 200 cases**
   despite `must_not_appear` being declared a non-negotiable invariant.
9. **`gold_facts` had only 2 distinct key-signatures across all 200 cases**,
   independent of the question — making Context Completeness unmeasurable.
10. **Test split leaked gold labels**, contradicting the spec's immutability and
    withholding rules.

Root cause for 1–5 and 9: `generators/assembler.py` chose bucket, jurisdiction,
and label independently and derived answers and facts from whichever documents
happened to exist, rather than from the question.

## Do not

- Do not tune baselines on these cases.
- Do not cite numbers computed against them.
- Do not import from `datasets/v0/` in any module under `ccbench/`.

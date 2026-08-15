# CCBench Benchmark Specification v0.2

> **Status:** Draft  
> **Owner:** Ansh  
> **Purpose:** Define the task, data schema, metrics, and evaluation protocol for the world's first multi-format, multi-jurisdiction enterprise-context benchmark.
>
> **v0.2 is a hard break from v0.1.** The v0.1 dataset is archived under
> `datasets/v0/` and must not be referenced by the pipeline; see
> `datasets/v0/DEPRECATED.md` for why it was retired. The live schema is
> `ccbench/benchmark/schema/case.schema.json`, which is authoritative wherever
> this document and it disagree.

---

## 1. Task Definition

**Enterprise Context Compilation (ECC):** Given a natural-language question about a business consignment, and a corpus of loosely-related documents (invoice, e-way bill, ERP order, WhatsApp proof-of-delivery), retrieve and compile the minimal sufficient context to answer the question correctly, while respecting jurisdictional emission policies.

Think of it like this: imagine you're a logistics manager who receives a question like *"Was the shipment from Delhi to Mumbai compliant on March 15?"* You have to find the right invoice, the right e-way bill, the right ERP record, and maybe a WhatsApp message — then piece them together. But you also need to know: *am I allowed to show the GSTIN number?* That depends on whether you're operating under Indian (IN) or EU (GDPR) rules.

---

## 2. Task Buckets

We categorize cases into 5 buckets based on the reasoning complexity required:

| Bucket | Description | Example Question |
|--------|-------------|------------------|
| **Lookup** | Single-document retrieval; answer is in one doc | *"What is the GSTIN of the vendor on invoice INV-001?"* |
| **Multi-hop** | Answer requires joining 2+ documents | *"Does the e-way bill EWB-123 match the invoice amount on INV-001?"* |
| **Temporal** | Answer depends on event ordering or dates | *"Was the e-way bill generated before the invoice was revised?"* |
| **Cross-lingual** | Documents or questions span multiple languages | *"[Hindi] क्या इस शिपमेंट का POD मिल गया?"* (WhatsApp thread is in Hindi/English mix) |
| **Compliance** | Answer requires knowing jurisdiction-specific emission rules | *"Can we disclose the PAN in the response under EU GDPR?"* |

**Note:** Composite cases span several buckets. A single case can be both *multi-hop* and *compliance*, for example.

---

## 3. Case Schema

Every case is a single JSON object. Abridged — the full contract is
`ccbench/benchmark/schema/case.schema.json`:

```json
{
  "schema_version": "0.2",
  "case_id": "ccbench-0001",
  "bucket": "multi-hop",
  "jurisdiction": "IN",
  "documents": { "invoice": {...}, "eway_bill": {...}, "erp_order": {...},
                 "whatsapp_pod": {...}, "flag": {...} },
  "events": [
    {"event_id": "E-004", "type": "ewb_generated", "ts": "2026-03-15T14:19:07+05:30",
     "actor": "Patel Logistics Pvt. Ltd.", "doc_ref": "412887654321", "note": null}
  ],
  "question": "Does the value declared on the e-way bill match the invoice total?",
  "question_lang": "en",
  "gold_answer": "No. Invoice TAX/2026-27/00318 totals Rs. 12,500.00 but e-way bill 412887654321 declares Rs. 11,800.00, a discrepancy of Rs. 700.00.",
  "gold_facts": [
    {"fact_id": "F1", "doc": "invoice", "path": "invoice_total", "value": "12500.0", "evidence": null},
    {"fact_id": "F4", "doc": "whatsapp_pod", "path": "M-007.text", "value": "...",
     "evidence": {"ref_id": "M-007", "lang": "hi-en",
                  "span": "e-way bill pe value Rs. 11,800.00 likhi hai",
                  "gloss_en": "the e-way bill states Rs. 11,800.00"}}
  ],
  "gold_label": "value_mismatch",
  "difficulty": "medium",
  "must_not_appear": [],
  "provenance": {"generator_version": "0.2.0", "seed": 20260912, "notes": "task=mh_mismatch"}
}
```

### 3.1 Document Types

| Document | Required | Description |
|----------|----------|-------------|
| `invoice` | Yes | GST invoice, 1–4 lines. `issued_at` is a **timestamp**, not a date, so same-day ordering against the e-way bill is decidable. Carries `revision_no` / `supersedes` / `original_issued_at`. Tax is IGST for inter-state supply and CGST+SGST for intra-state — never both |
| `eway_bill` | No | Permit with `status`, `extensions[]` and statutory validity of one day per 200 km. `null` exactly when `gold_label` is `missing_ewb` |
| `erp_order` | Yes | Purchase order with an approval trail and a goods receipt note (`grn`) |
| `whatsapp_pod` | No | Multi-party operational thread. Carries **no** derived `delivery_confirmed` flag: delivery status is stated only in the message text, often in the non-English part |
| `flag` | No | Human-raised exception (`value_query`, `compliance_hold`, `docs_pending`, `damage_claim`) |

Parties carry `pan` and a named `contact` (`name`/`email`/`phone`) in addition
to `gstin`. Each GSTIN embeds its holder's PAN at positions 2..12, as a real
one does.

### 3.2 The event timeline

Every case carries an `events[]` array in ascending timestamp order, spanning
`po_raised` → `grn_recorded`. Temporal questions resolve against this
structure rather than by parsing chat prose.

### 3.3 Gold Facts

`gold_facts` are objects, not strings, and are derived from **the question** —
never from whichever documents happen to be present. `path` addresses three
ways: dotted with indices for documents (`items[0].hsn_code`), by message id
for chat (`M-004.text`), and by event id for the timeline (`E-005.ts`).

`evidence` is required whenever a fact rests on chat text. It pins the message
id, its language and the verbatim clause, so a system that silently drops
non-English content cannot score on the cross-lingual bucket. `gloss_en` is for
judge rubrics only and is never shown to a system under evaluation.

### 3.4 Gold Labels

Each case carries a label describing the *nature* of the challenge. A label is
**realised in the documents** and re-derivable from them; the validator
recomputes each one rather than trusting the annotation.

| Label | Meaning | Re-derived by |
|-------|---------|---------------|
| `clean` | Documents align; no ordering violation | values agree **and** no violation found |
| `value_mismatch` | `eway_bill.total_invoice_value` ≠ `invoice.invoice_total` | comparing the two, tax-inclusive on both sides |
| `missing_ewb` | No permit was raised | `eway_bill is null` and `invoice.eway_bill_ref is null` |
| `temporal_violation` | Events out of order | e-way bill predates the invoice, delivery predates dispatch, or delivery falls after permit expiry |
| `compliance_case` | Answer depends on jurisdiction | question is jurisdiction-sensitive; answer differs between IN and EU |

### 3.5 Legal bucket × label combinations

Only 11 of the 25 combinations exist. The rest are illegal by construction, not
merely improbable:

| Bucket | Permitted labels |
|---|---|
| `lookup` | `clean` |
| `multi-hop` | `clean`, `value_mismatch`, `missing_ewb` |
| `temporal` | `clean`, `temporal_violation` |
| `cross-lingual` | `clean`, `missing_ewb`, `value_mismatch`, `temporal_violation` |
| `compliance` | `compliance_case` |

---

## 4. Metrics

All metrics are **binary-scoreable** (pass/fail or 0/1) so reviewers can verify them without subjective judgment.

### 4.1 Answer Correctness

Did the system produce the correct answer?

- **Exact match fallback:** Does the system's answer exactly match the `gold_answer` string (normalized for whitespace and case)?
- **LLM-judge:** If exact match fails, an LLM judge with a fixed rubric scores 0 or 1. The rubric is frozen at dataset creation time.

### 4.2 Context Completeness

Did the system retrieve all documents necessary to answer the question?

- Computed as **gold-fact recall**: fraction of `gold_facts` that are supported by the retrieved context.
- A `gold_fact` is "supported" if the retrieved context contains the value at the referenced `doc`/`path`.
- For facts carrying an `evidence` span, support additionally requires the cited message to be present in the retrieved context. Retrieving the thread but dropping the non-English message does not count.

Because facts are derived per question, this metric is question-specific:
there is no fixed set a system can always retrieve to score well.

### 4.3 Faithfulness

Did the system's answer only make claims that are supported by the retrieved context?

- Computed as: fraction of claims in the answer that cite a retrieved node with `[ID]` tags.
- A claim is one sentence. Segmentation is shared between the metric and the dataset validator (`benchmark/text.py`) so the answer key cannot pass validation while failing the metric it defines.
- A claim without a citation is automatically marked unfaithful. Citing a node that was *not* retrieved is a fabricated citation and also does not count.
- **Gold answers carry inline `[ID]` citations**, and every citation is backed by a gold fact — validator-enforced. Without this the benchmark would be unsolvable by its own answer key: a system reproducing the gold answer verbatim would score correctness 1 and faithfulness 0, failing §8 on every case.

### 4.4 Compliance Leakage

Did the system emit information that should have been masked under the case's jurisdiction?

- Binary check by **byte-level search**: does the emitted answer or context contain any literal listed in the case's `must_not_appear`?
- `must_not_appear` is populated on every EU case with both parties' PANs and both contacts' email addresses and phone numbers, and is withheld from the public test split.
- The GSTIN is *masked*, not denied — an EU answer may show its last four characters, so it is checked by the answer rubric rather than by literal search.

**Completeness and leakage are measured on different objects.** `gold_facts`
are *retrieval* targets and may legitimately point at a denied field: to answer
"may I disclose the PAN?", a system must first retrieve the invoice and see
that a PAN is present. `must_not_appear` constrains what is *emitted*. A
compliant system therefore scores 1.0 on both.

---

## 5. Splits

| Split | Cases | Purpose |
|-------|-------|---------|
| **Dev** | 100 | Development, tuning baselines, grid search |
| **Test** | 100 | Final evaluation only; **supervision withheld** |

Both splits carry an identical mix, by construction rather than by luck:

| | per bucket | `clean` | `compliance_case` | `temporal_violation` | `value_mismatch` | `missing_ewb` |
|---|---|---|---|---|---|---|
| Dev | 20 | 37 | 20 | 20 | 12 | 11 |
| Test | 20 | 37 | 20 | 20 | 12 | 11 |

**Rules:**
- The public test split is redacted of `gold_answer`, `gold_facts`, `gold_label`, `bucket`, `difficulty` and `must_not_appear`. Bucket and difficulty are withheld alongside the answers because publishing them lets a method condition on the task type it is about to be scored on.
- Test answers live in `benchmark/cases/test_gold.private.json`, which is gitignored and never distributed. Once the test set is created it is **immutable** — any change invalidates all results.
- Baselines must be tuned on dev only. Re-tuning on test is academic fraud.
- The corpus is reproducible from master seed `20260815`; `provenance.seed` on each case regenerates it exactly.

---

## 6. Baselines

We evaluate five retrieval methods:

| Method | Description | Why Include It? |
|--------|-------------|-----------------|
| **BM25** | Classic sparse retrieval (via `rank_bm25`) | Strong lexical baseline, fast |
| **Dense RAG** | Embedding model + top-k (e.g., BGE) | Standard neural retrieval |
| **Hybrid RAG** | Dense + sparse with RRF + reranker | Best-practice combined approach |
| **GraphRAG** | LLM entity extraction → graph → community retrieval | Cutting-edge structured approach |
| **Yours** | Your proprietary context-compiler method | The contribution |

Each baseline is tuned to its best performance on the dev split via grid search. Configs are frozen and documented in `BASELINES.md`.

---

## 7. Jurisdictional Emission Policy (Π_J)

This defines which fields can be emitted, masked, or denied based on jurisdiction.

| Field | IN (India) | EU (GDPR) |
|---|---|---|
| `pan` | allow full | **deny** — must not be emitted at all |
| `gstin` | allow full | mask to last 4 characters |
| `contact.email`, `contact.phone` | allow full | **deny** — personal data of a named individual |
| `contact.name` | allow | allow (refer by role where possible) |
| `hsn_code`, totals, line items | allow | allow |
| corporate `address` | allow | allow — a business detail |

The full policy table is maintained in `compiler/policies.py` and is versioned.
Every EU case materialises this table into its `must_not_appear` array, so
leakage is checkable without re-reading the policy.

---

## 8. Success Criteria

A benchmark case is considered **solved** only if:
1. Answer Correctness = 1
2. Context Completeness ≥ 0.8 (at least 80% of required facts retrieved)
3. Faithfulness ≥ 0.9 (at least 90% of claims are cited)
4. Compliance Leakage = 0 (no denied fields emitted)

The **overall benchmark score** is the fraction of cases that pass all four criteria.

### 8.1 The reference upper bound

Perfect retrieval (the oracle) emitting the gold answer scores, on dev:

| Metric | Value |
|---|---|
| Context Completeness | 1.000 |
| Answer Correctness | 1.000 |
| Faithfulness | 1.000 |
| Compliance Leakage — clean | 0.540 (**EU only: 0.061**) |
| **Benchmark score** | **0.540** |

Reproduce with `python -m harness.runner --method oracle --gold-answers`.

Read that table carefully: three of the four metrics are maxed, so **the entire
remaining 0.460 is compliance leakage**, and all of it is on EU cases. No
improvement in retrieval or generation can recover it — the denied literals sit
on the same invoice the answer legitimately needs. Closing that gap is what
`compiler/policies.py` (Π_J) exists to do, and it is the single number the
method's contribution should be judged on.

---

## 9. Versioning

- **Spec version:** v0.2 (this document)
- **Schema version:** 0.2 (`schema_version` on every case)
- **Generator version:** 0.2.0 (`provenance.generator_version`)
- **Policy version:** v0.2

Any change to the spec, schema, metrics, or policy requires a version bump and invalidates previous results.

`difficulty` is an enum of `easy` / `medium` / `hard`. `context-compiler-golden.md`
describes it as an integer 1..3; that document is stale and must be corrected
to match.

---

## 10. References

This benchmark draws on:
- BPI Challenge 2019 (procurement event-log structure)
- Indian GST/e-way bill regulations
- EU GDPR / DPDP emission rules
- RAG evaluation literature (RAGBench, CRAG, HotpotQA)

---

*End of Specification*

# CCBench Benchmark Specification v0.1

> **Status:** Draft  
> **Owner:** Ansh  
> **Purpose:** Define the task, data schema, metrics, and evaluation protocol for the world's first multi-format, multi-jurisdiction enterprise-context benchmark.

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

Every case in the benchmark is a single JSON object with the following structure:

```json
{
  "case_id": "ccbench-0001",
  "bucket": "multi-hop",
  "jurisdiction": "IN",
  "documents": {
    "invoice": { ... },
    "eway_bill": { ... },
    "erp_order": { ... },
    "whatsapp_pod": { ... }
  },
  "question": "Does the e-way bill amount match the invoice total?",
  "gold_answer": "No. The invoice total is ₹12,500 but the e-way bill shows ₹11,800.",
  "gold_facts": [
    "invoice.total = 12500",
    "eway_bill.amount = 11800",
    "invoice.eway_ref = EWB-2024-0034"
  ],
  "gold_label": "value_mismatch",
  "difficulty": "medium"
}
```

### 3.1 Document Types

| Document | Required | Description |
|----------|----------|-------------|
| `invoice` | Yes | GST-format invoice with HSN codes, GSTIN, totals |
| `eway_bill` | Yes | E-way bill linked by `consignment_ref` |
| `erp_order` | Yes | Purchase order from ERP system |
| `whatsapp_pod` | No | WhatsApp proof-of-delivery thread (may be missing) |
| `flag` | No | Optional compliance flag or annotation |

### 3.2 Gold Labels

Each case carries a label describing the *nature* of the challenge:

| Label | Meaning |
|-------|---------|
| `clean` | All documents align perfectly; straightforward answer |
| `value_mismatch` | Documents contradict each other on a value |
| `missing_ewb` | E-way bill is missing or unlinked |
| `temporal_violation` | Events are out of order (e.g., POD before dispatch) |
| `compliance_case` | Answer depends on jurisdiction-specific rules |

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
- A `gold_fact` is "supported" if the retrieved context contains the document and field referenced in the fact.

### 4.3 Faithfulness

Did the system's answer only make claims that are supported by the retrieved context?

- Computed as: fraction of claims in the answer that cite a retrieved document with `[ID]` tags.
- A claim without a citation is automatically marked unfaithful.

### 4.4 Compliance Leakage

Did the system emit information that should have been masked under the case's jurisdiction?

- Binary check: does the output contain any field that the `Π_J` policy marks as `deny` for the given jurisdiction?
- Examples: emitting a PAN under EU rules, or a full GSTIN when only the last 4 digits are permitted.

---

## 5. Splits

| Split | Cases | Purpose |
|-------|-------|---------|
| **Dev** | 100 | Development, tuning baselines, grid search |
| **Test** | 100+ | Final evaluation only; **gold labels withheld** |

**Rules:**
- Dev and test are balanced across all 5 buckets.
- Test-set answers are held in a private file. Once the test set is created, it is **immutable** — any change invalidates all results.
- Baselines must be tuned on dev only. Re-tuning on test is academic fraud.

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

| Jurisdiction | Rule Example |
|--------------|--------------|
| **IN (India)** | GSTIN: allow full; PAN: allow full; HSN: allow full |
| **EU (GDPR)** | GSTIN: mask to last 4 digits; PAN: deny entirely; HSN: allow full |

The full policy table is maintained in `compiler/policies.py` and is versioned.

---

## 8. Success Criteria

A benchmark case is considered **solved** only if:
1. Answer Correctness = 1
2. Context Completeness ≥ 0.8 (at least 80% of required facts retrieved)
3. Faithfulness ≥ 0.9 (at least 90% of claims are cited)
4. Compliance Leakage = 0 (no denied fields emitted)

The **overall benchmark score** is the fraction of cases that pass all four criteria.

---

## 9. Versioning

- **Spec version:** v0.1 (this document)
- **Schema version:** v0.1
- **Policy version:** v0.1

Any change to the spec, schema, metrics, or policy requires a version bump and invalidates previous results.

---

## 10. References

This benchmark draws on:
- BPI Challenge 2019 (procurement event-log structure)
- Indian GST/e-way bill regulations
- EU GDPR / DPDP emission rules
- RAG evaluation literature (RAGBench, CRAG, HotpotQA)

---

*End of Specification*

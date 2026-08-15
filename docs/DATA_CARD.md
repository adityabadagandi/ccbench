# Data Card — CCBench v1.0 (schema 0.2)

## Dataset Overview

CCBench is a benchmark for enterprise context compilation across multiple
document formats and jurisdictions. Given a question about a consignment and a
corpus of loosely-related documents, a system must retrieve the minimal
sufficient context, answer correctly, and respect the jurisdiction's emission
policy.

## Composition

- **Total cases:** 200 — 100 dev, 100 test
- **Buckets:** 20 per bucket per split (lookup, multi-hop, temporal, cross-lingual, compliance)
- **Labels per split:** 37 `clean`, 20 `compliance_case`, 20 `temporal_violation`, 12 `value_mismatch`, 11 `missing_ewb`
- **Jurisdictions:** 108 IN, 92 EU
- **Question language:** 175 English, 16 romanised Hinglish, 9 Devanagari Hindi
- **Documents per case:** invoice + ERP order always; e-way bill on 178; chat thread on all 200; human-raised flag on 57

### Text characteristics

- 2,247 chat messages across 200 threads, 3–10 messages each, 496 distinct message strings
- Message language mix: 721 romanised Hinglish, 352 Devanagari Hindi, 315 English
- 263 attachments: 178 POD images, 48 location pins, 37 voice notes with transcripts
- Invoices carry 1–4 line items; 144 inter-state (IGST) and 56 intra-state (CGST+SGST)
- Every case carries a 7–10 entry event timeline

## Collection Process

Fully synthetic and deterministic from master seed `20260815`. One
`Scenario` fixes the parties, goods, money and clock for a consignment; every
document is a view of that scenario, and the defect is injected into the
scenario itself rather than asserted as a label afterwards.

Realism drift — trading names that differ from legal names, chat
abbreviations, off-topic messages, corrections, replies — is applied at write
time and never inside a protected evidence span.

## Provenance

| Component | Source | License |
|-----------|--------|---------|
| Invoice / e-way bill structure | Synthetic, modelled on GST formats | CC-BY-SA 4.0 |
| ERP purchase-order structure | Synthetic, informed by BPI Challenge 2019 event-log shape | Refer to BPI Challenge terms |
| Emission policy | EUR-Lex GDPR / DPDP | Public domain / government |
| Identifiers | Synthetic only | N/A |

## PII Statement

All identifiers are **synthetic**. PANs are drawn from `QQ`/`ZZ`/`XQ` prefixes
that the real allottee series does not use, and each GSTIN is constructed
around its holder's PAN so the pair is internally consistent without either
being real. Company names, personal names, emails, phone numbers, addresses,
vehicle registrations and document serials are all generated. No real
business, person, invoice or consignment is represented.

The dataset deliberately *contains* PAN-shaped and contact-shaped fields —
compliance cases are unrepresentable without them — and every EU case declares
those values in `must_not_appear` so leakage is checkable by byte-level search.

## Quality guarantees

Enforced by `benchmark/validate.py` on every build; the corpus does not ship
unless all pass:

- every `gold_fact` resolves and equals its stated document value
- every evidence span is a verbatim substring of the message it cites
- no `must_not_appear` literal occurs in any `gold_answer`
- every gold label is **re-derived from the documents**, not trusted
- cross-lingual cases rest on at least one non-English evidence span
- no duplicate `case_id`, `invoice_no`, `consignment_ref`, question or answer
- the public test split carries no supervision

## Limitations

- Focused on the Indian logistics / GST context
- Two jurisdictions only (IN, EU)
- Synthetic: real OCR noise, scanned-image artefacts and genuinely malformed
  filings are not represented
- Chat threads are simulated; message templates number in the hundreds, not
  the thousands, so lexical diversity is bounded
- Every case has exactly one consignment; multi-consignment reconciliation is
  out of scope for v1.0
- `clean` is the largest single label at 37% per split, since the entire
  `lookup` bucket is clean by design

## Versioning

Schema 0.2, generator 0.2.0, spec v0.2. The v0.1 dataset is archived at
`datasets/v0/` and is excluded from the pipeline; see its `DEPRECATED.md`.

## Licensing

- **Data:** CC-BY-SA 4.0
- **Code:** MIT

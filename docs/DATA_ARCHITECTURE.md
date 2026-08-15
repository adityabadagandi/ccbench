# CCBench Data Architecture (schema 0.2)

## How Data Is Stored

```
ccbench/benchmark/cases/
├── dev/                          ← 100 cases, full supervision
│   ├── ccbench-0002.json         ← each case is one standalone JSON file
│   └── ...
├── test/                         ← 100 cases, redacted
│   ├── ccbench-0001.json         ← documents + question only
│   └── ...
├── test_gold.private.json        ← answer key for test (gitignored)
└── README.md
```

`ccbench/benchmark/splits/splits.json` holds the manifest: which ids are dev,
which are test, the master seed, and which fields are withheld from test.

**Why file-based JSON?** Each case is self-contained and inspectable, git
diffs are line-by-line, no database is needed, and the folder zips cleanly.

> The v0.1 data lived in a top-level `ccbench-dataset/` folder that no module
> in the package ever read — the loader, harness and baselines all pointed at
> `benchmark/cases/`, which held one file. It now holds the real corpus. The
> old data is archived at `datasets/v0/` and is out of the pipeline.

## The Generation Pipeline

The controlling idea: **one scenario is the source of truth, and every
document is a view of it.** v0.1 generated documents independently and then
asserted a label on top, which is why `temporal_violation` appeared in no
timestamp and `clean` cases never actually matched.

```
        TaskSpec  (bucket, gold_label, required defect, jurisdictions, weight)
                        │
                        ▼
        build_scenario(seed, defect, revised)
        one consignment: parties, goods, money, clock — with the
        defect injected into the scenario itself
                        │
    ┌───────────────────┼────────────────────┬─────────────────┐
    ▼                   ▼                    ▼                 ▼
build_invoice     build_eway_bill      build_erp_order    build_thread
build_flag        build_events                            (+ evidence spans)
    │                   │                    │                 │
    └───────────────────┴────────────────────┴─────────────────┘
                        │
                        ▼
        spec.build(scenario, documents, evidence, jurisdiction)
        writes the question, the answer, and the exact gold facts
                        │
                        ▼
        benchmark/validate.py  — re-derives every label from the
        documents and refuses to pass anything it cannot confirm
```

| Module | Responsibility |
|---|---|
| `generators/identity.py` | PANs, GSTINs built around them, parties, contacts, addresses, goods catalogue |
| `generators/scenario.py` | `Scenario` + the six defects + document views + timeline |
| `generators/whatsapp.py` | Multi-party code-switched threads and their evidence spans |
| `generators/assembler.py` | `TaskSpec` matrix, question/answer/fact builders, splitting, redaction |
| `benchmark/validate.py` | Invariant enforcement across the corpus |

Removed in 0.2: `generators/{invoice,ewaybill,erp,gstin,noise}.py`. `noise.py`
mutated documents *after* gold facts had been extracted; realism drift is now
applied at write time and never inside a protected evidence span.

## Defects

A defect is a property of the scenario, not an annotation. The validator
re-derives each one from the documents alone.

| Defect | Realised as | Label |
|---|---|---|
| `none` | — | `clean` or `compliance_case` |
| `value_mismatch` | permit declares a transposed / truncated / stale value | `value_mismatch` |
| `missing_ewb` | no permit, no `eway_bill_ref`, no GRN, driver detained at check post | `missing_ewb` |
| `ewb_before_invoice` | permit generated hours *before* the invoice it cites | `temporal_violation` |
| `pod_before_dispatch` | delivery timestamped before dispatch | `temporal_violation` |
| `delivery_after_expiry` | goods arrive after permit validity lapses | `temporal_violation` |

## Regenerating

```bash
python generate_dataset.py                  # 200 cases + validation
python generate_dataset.py --cases 40       # smoke batch
cd ccbench && python -m benchmark.validate benchmark/cases
```

Deterministic from master seed `20260815`. Requires Python 3.12+.

On this machine bare `python` is 3.10 and cannot import `StrEnum`; use
`py -3.13` (or any 3.12+ interpreter) explicitly.

## Remaining human work

| Task | Why only a person can do it |
|---|---|
| Review a sample of gold answers for phrasing quality | The validator proves answers are *correct*; only you can judge whether they are *well-posed* |
| Freeze the LLM-judge rubric | Must be fixed before any baseline is run, or scores are not comparable |
| Adversarial cases from a collaborator | Must be designed without sight of the matching logic |
| Decide the canonical join key when link paths disagree | `consignment_ref`, `eway_bill_ref`, `doc_no` and `invoice_refs` all link; precedence is a research decision |

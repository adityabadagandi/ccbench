# The Context Compiler 


**Version 1.0 · The single source of truth. If it is not in here, you do not need it.**

Audience: you (Ansh), building with Kimi Aggregato (K2) for delegated implementation and a collaborator in India for domain data. Written to the engineering standard you would expect at Anthropic or Meta: precise interfaces, tests as contracts, honest limitations, and a delegation model that keeps the defensible core in your own hands.

---

## How to read this document

This document has six parts. Read Parts I–II once to hold the whole system in your head. Parts III–IV are the reference you return to while building — every component has a frozen interface, a test contract, and a ready-to-paste Kimi prompt. Part V is the experimental protocol that turns code into a defensible result. Part VI is the standards appendix: the engineering conventions, the review checklist, and the interview-defense notes.

**Three colored conventions used throughout:**

- **[SPEC]** blocks are frozen contracts. Once agreed, the interface does not change without a version bump, because everything downstream depends on it.
- **[KIMI]** blocks are verbatim prompts to paste into Kimi Aggregato. They reference interfaces by name so Kimi cannot drift.
- **[YOU]** blocks are the parts you write by hand and Kimi never touches — the defensible core.

---

# PART I — WHAT WE ARE BUILDING AND WHY

## I.1 The one-paragraph thesis

Current retrieval hands a language model a bag of text chunks ranked by similarity and hopes the model reconstructs how they relate. For enterprise questions whose answer lives across formats, languages, time, and legal boundaries, that hope fails. A **Context Compiler** instead builds the relationships first — linking multi-format facts into a typed graph, propagating confidence across sources that agree or disagree, ordering events in time, selecting a connected subgraph that fits the token budget, and filtering by jurisdiction *at retrieval time* — then emits a compact, citable context package. The model reasons over structure that is already built, so correctness and faithfulness rise and cross-border leakage becomes impossible by construction.

## I.2 What is and is not novel (state this precisely, always)

Precision here is the difference between a respected paper and a knifed one. The honest decomposition:

| Element | Prior art exists? | Our contribution |
|---|---|---|
| Dense / sparse / hybrid retrieval | Yes | We use it as baselines, not as a claim |
| Graph-based retrieval (GraphRAG) | Yes | We compare against it; our graph adds semantics it lacks |
| Confidence in retrieval | Yes (similarity scores) | We propagate *evidential* confidence across source (dis)agreement — new in this setting |
| Temporal knowledge graphs | Yes (Zep, ATOM) | We fold temporal order into budgeted selection, not just storage |
| Context compilation as a principle | Yes (SkillRAE, 2026) | We apply it to governed multi-format enterprise data |
| **Retrieval-time jurisdiction filtering (Π_J)** | **No** | **The genuinely novel operator: provable zero-leakage by construction** |
| **A benchmark for composite + compliance retrieval** | **No** | **CCBench: the primary contribution** |

The one-line claim you may make without overclaiming: *"We contribute a benchmark for capabilities no existing benchmark measures, and a context-compilation method whose novelty is its composition plus a retrieval-time compliance operator."*

## I.3 The two contributions, ranked

1. **CCBench (primary).** A public benchmark of 200+ gold-labeled Indo-German enterprise cases across five task buckets, scoring four metrics — including *compliance leakage*, which no benchmark measures today. Publishable and citable even if our own method did not win.
2. **context-compiler (secondary).** The open-source reference method, strong on the benchmark, anchored by the Π_J operator.

## I.4 Success criteria (measurable, committed in advance)

- CCBench released public: 200+ cases, frozen test split, live leaderboard, data card.
- context-compiler on PyPI, MCP server working, reproducible `make benchmark`.
- Paper on arXiv; results reported as mean ± 95% CI over ≥3 seeds; every claim traceable to a table.
- Π_J leakage = 0.0% on the compliance bucket, versus nonzero for every baseline.
- Honesty gate: whatever the numbers say is what we publish. Written here so it cannot be renegotiated later.

---

# PART II — HIGH-LEVEL ARCHITECTURE

## II.1 The compiler analogy as system spine

The architecture is organized as a classical compiler, because the analogy is exact and it forces clean stage boundaries.

| Compiler stage | Context Compiler stage | Input → Output |
|---|---|---|
| Lexing | Extraction | raw source (PDF/CSV/chat) → typed facts + provenance + per-field confidence |
| Parsing | Entity resolution & schema binding | typed facts → records (Invoice, EWayBill, ErpOrder, Message) |
| AST / IR | Context graph G=(V,E,τ,c,ℓ) | records → linked, timestamped, confidence-scored graph |
| Optimization | Confidence propagation + temporal ordering | graph → scored, ordered graph |
| Register allocation | Budgeted connected-subgraph selection | scored graph + token budget → the subgraph that fits |
| Codegen + target triple | Serialization + Π_J emission | subgraph + jurisdiction → citable context block per target (EU/IN) |

## II.2 The six layers

```
L1  Ingestion        pull sources: PDF/image, CSV/ERP, chat export
L2  Extraction       source -> typed facts (+ provenance, + confidence)      [VLM / parsers]
L3  Context Graph     facts -> nodes; link by refs; timestamp; store          [Postgres]
L4  Query Engine      query -> seed -> rank -> budgeted connected subgraph     [YOUR core]
L5  Workflow Engine   graph change -> trigger (findings, webhooks)            [reconcile]
L6  Compliance        Pi_J: deny/mask/allow per jurisdiction AT RETRIEVAL     [YOUR core]
```

**The load-bearing architectural decision:** L6 is not a filter placed after L4 — it is a *parameter of* L4. The query engine only ever retrieves nodes where `policy(node, J) ≠ deny`. Denied facts never enter the candidate set, so zero-leakage is a property of the retrieval operator, not a downstream scrub. This inversion is the whole reason the compliance claim is *provable* rather than *tested*, and it is the single most important sentence in the architecture.

## II.3 End-to-end data flow (one query)

```
SOURCES ─► L2 EXTRACT ─► L3 GRAPH ─► L4 COMPILE ─► L6 EMIT(Π_J) ─► CONSUMERS
  │            │             │            │             │              │
  │            │             │            │             │              ├─ LLM prompt block ([ID]-tagged)
GST PDF     typed facts   nodes linked  seed→rank→    --target=in:    ├─ MCP tools (agents/Claude)
e-way JSON  +provenance   by consign.   connected     full view       ├─ REST /context
SAP CSV     +confidence   +Finding      subgraph      --target=eu:    └─ human UI
WhatsApp    per field     nodes         under budget  PAN/GSTIN
(HI/EN)                                 +temporal     never retrieved
```

## II.4 Component ownership (the delegation contract)

| Component | Module | Owner | Rationale |
|---|---|---|---|
| Reconciliation logic | `compiler/reconcile.py` | **YOU** | interview crown jewel; the finding logic |
| Ranking function | `compiler/ranking.py` | **YOU** | the retrieval contribution |
| Confidence propagation | `compiler/propagation.py` | **YOU** | the mechanism ablations defend |
| Π_J policy | `compiler/policy.py` | **YOU** | the 0%-leakage claim is yours to prove |
| Graph assembly / serialization | `compiler/context.py` | KIMI | plumbing around your core |
| MCP server | `compiler/mcp_server.py` | KIMI | SDK boilerplate |
| Extraction | `compiler/extract.py` | KIMI | format wrangling |
| Data generators | `scripts/generate.py` | KIMI | volume; you audit realism |
| Evaluation harness | `harness/*` | KIMI | plumbing; you verify metrics by hand |
| Baselines | `baselines/*` | KIMI | you audit fairness |
| Benchmark cases | `benchmark/cases/*` | FRIEND (blind) + YOU (gold) | adversarial credibility |

**The rule in one line:** anything a reviewer or interviewer would probe, you write by hand; everything routine is delegated on a `kimi/` branch and verified line-by-line before merge.
---

# PART III — THE DATA MODEL & CORE INTERFACES (frozen contracts)

Everything Kimi builds targets these interfaces. They are frozen: changing one is a version bump, because every component and test depends on it. This is the Meta/Anthropic discipline — the interface is the contract, the implementation is swappable.

## III.1 The domain types

**[SPEC] `compiler/models.py` — the shapes every layer passes around.**

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Invoice:
    invoice_no: str
    consignment_ref: str
    value_eur: float
    vendor: str | None = None
    gstin: str | None = None          # business tax id (mask for EU)
    pan: str | None = None            # personal tax id (DENY for EU)
    ts: str | None = None             # ISO-8601 timestamp
    doc_ref: str | None = None        # provenance: source file/record id

@dataclass
class EWayBill:
    ewb_no: str
    consignment_ref: str
    declared_eur: float
    ts: str | None = None
    doc_ref: str | None = None

@dataclass
class ErpOrder:
    order_no: str
    consignment_ref: str
    expected_eur: float
    ts: str | None = None
    doc_ref: str | None = None

@dataclass
class Message:                        # WhatsApp POD / dispatch, HI/EN
    msg_id: str
    consignment_ref: str
    text: str
    lang: str                         # 'hi' | 'en' | 'hi-en'
    ts: str | None = None
    doc_ref: str | None = None

@dataclass
class Finding:                        # produced by reconcile (L5)
    kind: str                         # 'value_mismatch'|'missing_ewb'|'temporal_violation'|'ok'
    consignment_ref: str
    severity: str                     # 'high'|'med'|'ok'
    confidence: float                 # 0..1
    detail: dict[str, Any] = field(default_factory=dict)   # numbers + provenance refs
```

## III.2 The graph node & context bundle

**[SPEC] `compiler/context.py` — graph and output types.**

```python
@dataclass
class Node:
    id: str                           # e.g. 'INV-5567', 'F1'
    type: str                         # 'Invoice'|'EWayBill'|'ErpOrder'|'Message'|'Flag'
    consignment_ref: str
    fields: dict[str, Any]
    confidence: float                 # 0..1  (post-propagation)
    ts: str | None                    # for temporal ordering
    provenance: str                   # human-readable source, e.g. 'GST portal (gst:INV-5567)'

@dataclass
class ContextBundle:
    query: str
    nodes: list[Node]                 # the selected connected subgraph, temporally ordered
    llm_context: str                  # the serialized, [ID]-tagged, citable block
    citations: list[str]              # node ids present
    tokens: int                       # budget used
    budget: int                       # budget allowed
    jurisdiction: str                 # 'IN'|'EU'
```

## III.3 The method interface every retriever implements

**[SPEC] The universal contract — baselines and our method both satisfy this.**

```python
from typing import Protocol

class Retriever(Protocol):
    name: str
    def retrieve(self, question: str, corpus: "CaseCorpus",
                 budget: int, jurisdiction: str = "IN") -> ContextBundle: ...
```

This single Protocol is what makes the benchmark fair: the harness calls `retrieve(...)` identically on BM25, dense, hybrid, GraphRAG, and context-compiler. Any method that fits the budget and returns a ContextBundle can be scored. No special-casing, no home-field advantage.

## III.4 The case schema (the benchmark's atomic unit)

**[SPEC] `benchmark/case.schema.json` (described; Kimi renders the JSON Schema).**

A case is one shipment's document bundle plus a question and its answer key:

```json
{
  "case_id": "CC-00042",
  "bucket": "multi_hop",                          // lookup|multi_hop|temporal|cross_lingual|compliance
  "difficulty": 2,                                 // 1..3
  "jurisdiction": "EU",                            // IN|EU  (which view the question asks for)
  "planted_label": "value_mismatch",               // ground-truth problem type
  "question": "Is the tax claim on INV-5567 valid, and what may Frankfurt see?",
  "gold_answer": "invalid",                        // verdict or short text
  "gold_facts": ["INV-5567", "EWB-991", "SO-1120"],// node ids required to answer
  "must_not_appear": ["ABCDE1234F"],               // PAN that must be absent in EU view
  "documents": {
    "invoice":   { "...": "..." },
    "eway_bill": { "...": "..." },
    "erp_order": { "...": "..." },
    "messages":  [ { "...": "..." } ]
  }
}
```

**Design invariants (enforced by the validator, non-negotiable):**
- Every id in `gold_facts` must exist in `documents`.
- All identifiers (GSTIN/PAN/invoice_no) drawn from reserved synthetic ranges — never real.
- `must_not_appear` is populated for every `compliance` and `EU` case.
- Timestamps internally consistent (POD after invoice, etc.).
- No two cases share `invoice_no` or `consignment_ref`.

---

# PART IV — COMPONENT-BY-COMPONENT BUILD (specs + tests + Kimi prompts)

Build in this order; each component depends only on those above it. Each has three blocks: the **[SPEC]** (frozen interface), the **test contract** (what "done" means), and either a **[KIMI]** prompt or a **[YOU]** guide. After each, run the branch-test-PR loop from the Field Guide.

## C0 — Repository scaffold

**[KIMI] Prompt C0**

```
Create a Python monorepo named ccbench, package name "context-compiler", src layout under /compiler.
Structure: /benchmark (schema, exemplars/, cases/), /compiler/src/context_compiler (models.py,
context.py, reconcile.py, ranking.py, propagation.py, policy.py, extract.py, mcp_server.py),
/baselines, /harness, /scripts, /configs, /tests, /docs, /results, /.github/workflows.
Include: pyproject.toml (py3.12, deps: pydantic, psycopg[binary], jsonschema; dev: pytest, pytest-cov, ruff),
ruff config (line 100), GitHub Actions CI running ruff + pytest, MIT LICENSE, .gitignore,
README skeleton (What/Why/Quickstart/Results/Leaderboard/Cite). One trivial passing test so CI is green.
Output every file with full path. NO implementation logic — stubs, configs, docstrings only.
```

**Test contract:** `pytest -q` → 1 passed; CI green on first push.

## C1 — Domain models  `[SPEC in III.1]`

**[KIMI] Prompt C1**

```
Implement compiler/src/context_compiler/models.py EXACTLY as this spec [PASTE III.1]. Frozen dataclasses,
no logic beyond definitions. Add a tests/test_models.py that constructs one of each type and asserts field
defaults. Nothing else.
```

**Test contract:** every dataclass constructs; defaults correct.

## C2 — Extraction (plumbing)

**[SPEC]** `extract() -> (list[Invoice], list[EWayBill], list[ErpOrder], list[Message], list[dict])`. Two modes via `EXTRACT_MODE`: `mock` (read case JSON → typed records) and `vlm` (stub for later). Output shape is frozen; the mock mode must round-trip a case file into typed records.

**[KIMI] Prompt C2**

```
Implement compiler/src/context_compiler/extract.py. Function extract(case_dir) returns
(invoices, eway_bills, erp_orders, messages, provenance_docs) built from case JSON files matching
benchmark/case.schema.json [PASTE schema]. EXTRACT_MODE=mock reads the JSON; EXTRACT_MODE=vlm raises
NotImplementedError with a TODO. Preserve doc_ref provenance on every record. Add tests/test_extract.py
using the 5 exemplar cases as fixtures: assert counts and that provenance survives. Do not infer or
compute anything — extraction only maps fields.
```

**Test contract:** exemplars load to correct record counts; every record keeps its `doc_ref`.

## C3 — Reconciliation  **[YOU — never Kimi]**

**[SPEC]** `reconcile(invoices, eway_bills, erp_orders) -> list[Finding]`, one Finding per consignment.

**[YOU] Build guide (this is the crown jewel — write it yourself, test-first):**
- Index e-way bills and ERP by `consignment_ref`.
- For each invoice, find partners; classify: `value_mismatch` if |invoice−ewb| > tolerance; `missing_ewb` if no ewb; else `ok`.
- Severity: high for value_mismatch, med for missing_ewb, ok otherwise.
- **Confidence design (the defensible part):** a mismatch confirmed by ERP (ERP agrees with invoice, ewb is the outlier) scores *higher* than a two-source mismatch. Encode this so more independent agreement → higher confidence.
- Pack numbers + `doc_ref`s into `Finding.detail` for provenance.

**Test contract (`tests/test_reconcile.py`, write BEFORE the code):**
```python
def test_value_mismatch_flagged_high(): ...            # 42180 vs 39900 -> value_mismatch, high
def test_matching_values_ok(): ...                      # all equal -> ok
def test_missing_eway_bill(): ...                        # no ewb -> missing_ewb, med
def test_one_finding_per_consignment(): ...
def test_erp_confirmed_mismatch_more_confident(): ...    # ERP-confirmed > two-source
```
Kimi may only add *edge-case* tests AFTER your five pass. It never writes the body.

## C4 — Confidence propagation  **[YOU — never Kimi]**

**[SPEC]** `propagate(nodes, edges) -> nodes` (mutated confidences).

**[YOU] Build guide:**
- Per-fact fusion in log-odds: `c(v) = σ( Σ_s w_s · logit(c_s(v)) )`.
- Spread along consignment edges via personalized PageRank: `c^(t+1)(v) = λ·c^(0)(v) + (1−λ)·Σ A_uv·c^(t)(u)`, λ≈0.15, iterate to convergence.
- **Verifiable property:** two agreeing sources end higher than either alone; a contradicted fact drops. Write a hand-checkable test on one case asserting exactly this.

**Test contract:** convergence within N iters; the agreement/contradiction property holds numerically.

## C5 — Ranking  **[YOU — never Kimi]**

**[SPEC]** `score_node(node, query, seeds) -> float` in [0,1]; `assemble_context(query, nodes, budget, jurisdiction) -> ContextBundle`.

**[YOU] Build guide:**
- `score = w1·seed_match + w2·confidence + w3·type_prior + w4·recency`, where type_prior favors Flag > ErpOrder > Invoice > EWayBill for verdict questions.
- Assembly: seed from query → rank → greedily add under token budget → enforce connectivity (a picked consignment brings its neighbors) → temporal sort.
- **Verifiable property:** the naive baseline over-retrieved unrelated consignments; your ranking must place seeded-consignment nodes above off-seed ones. Test it.

**Test contract:** budget respected; connectivity preserved; seeded nodes rank first.

## C6 — Π_J policy  **[YOU — never Kimi]**

**[SPEC]** `apply_policy(node, jurisdiction) -> Node | None` (None = deny/drop; else masked copy). Applied INSIDE node loading, before assembly.

**[YOU] Build guide:**
```python
POLICY = {
  ("pan",   "EU"): "deny",   # personal tax id: never leaves India
  ("gstin", "EU"): "mask",   # business tax id: shown masked
  # IN: allow all
}
```
- Deny → the node's forbidden field is removed *and if the field is the node's essence, the node is dropped from the candidate set entirely* — it is never a retrieval candidate.
- **The one test that matters:** assemble under `jurisdiction="EU"` on a case whose PAN is in `must_not_appear`; assert that PAN appears **nowhere** in `bundle.llm_context` — byte-level search. This test is the empirical face of the provable claim.

**Test contract:** `must_not_appear` values are byte-absent from EU-view output on every compliance case.

## C7 — Serialization & assembly glue (plumbing)

**[SPEC]** `serialize_for_llm(query, nodes) -> str` producing the tagged, citable block; wired into `assemble_context`.

**[KIMI] Prompt C7**

```
Implement serialize_for_llm(query, nodes) in compiler/context.py producing this exact format:
  # Compiled context for: "<query>"
  # Use only facts below. Cite [ID] tags. Prefer higher-confidence facts.
  ## Facts
  [<id>] <Type> · consignment <ref> · <field k v ...> · confidence <c.cc>
  ## Provenance
  [<id>] <- <provenance>
Nodes arrive already ranked, connected, temporally ordered, and policy-filtered — do NOT re-rank or
re-filter; serialize only. Add tests asserting: every node appears once as [ID]; provenance line per node;
no field whose value is None is printed. Use the Node spec [PASTE III.2].
```

**Test contract:** format matches byte-for-byte on a fixture; None fields omitted.

## C8 — MCP server (plumbing)

**[SPEC]** MCP tools `search_context(query, budget)`, `get_consignment(ref)`, `list_findings(severity)` over the assembled pipeline. Note: the MCP SDK is at v2.0 — the high-level class is `MCPServer` from `mcp.server.mcpserver`, decorator `@mcp.tool()`, run via `mcp.run()`.

**[KIMI] Prompt C8**

```
Implement compiler/mcp_server.py using MCP SDK v2.0: `from mcp.server.mcpserver import MCPServer`,
`mcp = MCPServer("context-compiler")`, tools via `@mcp.tool()`, launch `mcp.run()`. Expose:
search_context(query, budget=1500) -> str (returns bundle.llm_context),
get_consignment(ref) -> str, list_findings(severity="all") -> list[dict].
Load nodes from the corpus via the existing pipeline (extract -> graph -> reconcile -> assemble).
Do not reimplement ranking/policy — call the existing functions. Verify against `pip show mcp` version 2.x;
if the import path differs, print the installed version and adapt. Add a smoke test that imports the module
and asserts the three tools are registered.
```

**Test contract:** module imports; three tools registered; a stubbed corpus returns a bundle string.
## C9 — Benchmark data pipeline

### C9a — Case schema & validator (plumbing, but you own the schema design)

**[YOU]** design `case.schema.json` from the [SPEC in III.4]. Then delegate the validator:

**[KIMI] Prompt C9a**

```
Given benchmark/case.schema.json [PASTE] and 5 exemplar cases [PASTE], write scripts/validate_cases.py:
validates every *.json in a dir against the schema (jsonschema) AND enforces these invariants with clear
errors: every gold_facts id exists in documents; all identifiers match reserved synthetic patterns
[PASTE patterns]; must_not_appear populated for compliance/EU cases; timestamps internally consistent;
no duplicate invoice_no/consignment_ref across the dir. Exit 1 on any failure. Add tests using the 5
exemplars (pass) plus 5 broken fixtures (each fails with the right message).
```

**Test contract:** exemplars pass; 5 broken fixtures each fail with the correct error.

### C9b — Synthetic generators (plumbing; you audit realism)

**[KIMI] Prompt C9b**

```
Write scripts/generate.py producing cases valid against the schema and imitating the exemplars.
Requirements: GST-format invoices (realistic GSTIN/HSN/IRN structure, synthetic-only ids); linked e-way
bills (some missing per planted label); ERP orders whose structure is seeded from the BPI Challenge 2019
purchase-order log [I attach a 20-row sample]; optional Hindi/English code-switched POD messages;
controllable independent noise flags (OCR typos, currency/format variance, lakh-crore vs thousands,
near-duplicate vendors); every case carries a planted label (clean|value_mismatch|missing_ewb|
temporal_violation|compliance_case) and the documents are constructed so that label is TRUE; deterministic
via --seed; --n stratified across labels x 3 difficulty tiers. Unit tests: every generated case passes
scripts/validate_cases.py.
```

**Test contract:** `generate.py --n 20 --seed 7` → 20 schema-valid cases; deterministic across runs.

**[YOU] audit (not delegable):** read 20 generated cases like a suspicious auditor; kill anything templated (repeated vendors, round numbers, clean dates). Benchmark credibility dies on "this data looks fake." File issues; regenerate until 20/20 pass your sniff test.

### C9c — Friend's adversarial cases  **[FRIEND — blind]**

Your collaborator generates 40 cases (20 hard-realistic, 20 designed-to-break-matching) using ONLY the schema — never your method. His blindness is a scientific control: a win on cases built blind to your method is a real win. He submits via PR from his fork; CI validates automatically.

### C9d — Gold labeling & THE FREEZE  **[YOU]**

- Write `docs/LABELING.md`: what makes an answer correct (verdict + required facts), partial credit rules, and how disagreements are recorded (`"disputed": true` + note, kept in-file — visible disagreement is rigor).
- Label all cases; spot-check 10 of the friend's.
- **The freeze:** `split.py --dev 100 --test 100 --seed 42` (stratified) → move test gold answers to `ccbench-private` → `git tag v0-data-freeze`. From now: tune on dev freely, never touch test. This is the most sacred step in the project.

## C10 — Evaluation harness (plumbing; you verify metrics by hand)

**[SPEC]** `run(methods, split, seeds) -> results.jsonl + tables`. Metric functions each isolated and unit-tested.

**[KIMI] Prompt C10**

```
Build /harness. Components:
(1) loader: reads benchmark/cases/, validates before running.
(2) LLM client: provider-agnostic; supports an OpenAI-compatible base_url (my local vLLM) and Anthropic API;
    response caching keyed on (model, prompt-hash); resumable runs.
(3) metrics (one function each, unit-tested against the 5 exemplars):
    - answer_correctness: LLM-judge with a fixed rubric [I PASTE RUBRIC] + exact-match fallback for verdicts.
    - context_completeness: fraction of gold_facts ids present in the retrieved bundle.
    - faithfulness: fraction of answer claims that cite [ID] tags actually supplied.
    - compliance_leakage: byte+field detector — does any must_not_appear value appear in the context OR the
      answer for the active jurisdiction; binary per case, reported as a rate.
(4) runner: run(methods, split, seeds) -> results.jsonl (row per method x case x seed) + markdown tables
    (main: methods x 4 metrics mean±95%CI; per-bucket; ablation).
Determinism: fixed seeds; log every config into results. Expose harness/debug_score.py --print-per-case
so I can compare each metric against my hand-computed exemplar scores.
```

**Test contract:** each metric unit-tested; and **[YOU] the tripwire** — `debug_score.py` on the 5 exemplars must reproduce the scores you computed by hand in labeling. One mismatch = STOP and fix; wrong metrics silently poison every downstream number. This is the highest-leverage verification in the project.

## C11 — Baselines (plumbing; you audit fairness)

**[KIMI] Prompt C11**

```
Implement four baselines in /baselines against the Retriever protocol [PASTE III.3], each returning a
ContextBundle at the SAME token budget as our method:
(1) bm25 (rank_bm25); (2) dense (a strong open embedding model, e.g. BGE, cosine top-k);
(3) hybrid (dense+BM25 via reciprocal rank fusion + a cross-encoder reranker); (4) graphrag
(LLM entity extraction -> entity graph -> query-time neighborhood retrieval).
Every tunable in configs/baselines/*.yaml. scripts/tune_baselines.py runs a small grid search per baseline
ON THE DEV SPLIT ONLY, writing best configs to configs/baselines/best/. Each baseline serializes its context
in the same [ID]-tagged format so faithfulness is measurable for all. Explicit: DO NOT handicap any baseline.
```

**Test contract:** each baseline returns a valid bundle within budget; grid search produces a best config.

**[YOU] fairness audit (not delegable):** run each grid search, pick each baseline's *best* dev config, freeze it, document in `docs/BASELINES.md`. The reviewer's test: can 10 minutes of tuning beat your reported baseline? If yes anywhere, the results table is dead. Tune them like you want them to win.

## C12 — Experiment runner

**[KIMI] Prompt C12**

```
Write scripts/run.py: --split {dev,test} --methods {all|list} --seeds N, plus --ablate for the compiler
method only {confidence,temporal,graph,policy,compile} (each disables one component via config; "compile"
= raw chunk dump at same budget). Outputs: results/<ts>/raw.jsonl, main_table.md, per_bucket_table.md,
ablation_table.md (mean±95%CI). GUARD RAIL: refuse --split test unless git tag v0-data-freeze exists and the
working tree is clean. Print estimated LLM-call count; require confirmation above 500 calls.
```

**Test contract:** dev run produces all three tables; test run refused without the freeze tag.

---

# PART V — EXPERIMENTAL PROTOCOL (turning code into a defensible result)

## V.1 The runs (Week-9 equivalent — do once, on test)

1. Provision compute (RunPod A10/A40; vLLM OpenAI-compatible endpoint for judge + generation).
2. `run.py --split test --methods all --seeds 3` → main + per-bucket tables.
3. `run.py --split test --method compiler --ablate confidence,temporal,graph,policy,compile --seeds 3` → ablation table.
4. Budget ~10–20 EUR. **Delete the pod immediately after** (standing reminder).

## V.2 The four result tables you are trying to fill

**Main** (methods × metrics, mean±95%CI): the headline. Leakage column: 0.0% for you, nonzero for all baselines by construction.

**Per-bucket** (methods × lookup/multi-hop/temporal/cross-lingual/compliance): the honesty table. You will *tie* on lookup — report it proudly; it makes the multi-hop and compliance wins believable.

**Ablation** (config × correctness/Δ/leakage): the mechanism proof. Each removal must hurt the metric it serves. Removing Π_J should barely move correctness but explode leakage — the cleanest possible demonstration that the operator does one job absolutely.

**Leaderboard** (public): the living table with an empty "your method here — submit a PR" row.

## V.3 The analysis  **[YOU — never delegate]**

Write `docs/RESULTS.md`: where you win/lose/tie per bucket; whether each ablation hurt the right metric (a component whose removal costs nothing is decorative — say so or fix it); the claims the numbers actually support, no more.

## V.4 The three endings (all publishable — committed in advance)

| Ending | Numbers | You publish | Note |
|---|---|---|---|
| A — clear win | beat hybrid + GraphRAG broadly | method-led paper | maximum |
| B — partial win | win multi-hop + compliance, tie lookup | benchmark-led paper, method as strong reference | high |
| C — honest loss | hybrid RAG holds | benchmark + negative result ("large headroom remains") | still high; honesty gets cited |

The leakage column survives all three untouched — it is architectural, not empirical. The worst honest outcome is still a public benchmark, a shipped library, a paper, and defensible expertise. If you lose on dev, you may improve and re-run on dev; you may **never** re-tune on test.

## V.5 The one-sentence claim (abstract = README = interview answer)

*"On CCBench, context compilation improves multi-hop answer correctness by ~X points over GraphRAG and ~Y over hybrid RAG, with ablations showing graph connectivity and compilation itself as dominant factors, while the Π_J operator eliminates cross-jurisdiction leakage entirely (0% vs Z% for all baselines)."*
---

# PART VI — ENGINEERING STANDARDS (the Meta / Anthropic bar)

## VI.1 The Kimi Aggregato delegation protocol

Kimi is a capable long-context coding agent, but it degrades on monolithic builds — it forgets earlier decisions and silently changes interfaces. The protocol that prevents this is exactly how large engineering orgs ship: **small, tested, reviewed units against frozen interfaces.**

**Rules for every Kimi task:**
1. **One component per prompt.** Never "build the whole harness." Always a single C-numbered spec.
2. **Reference interfaces by paste, not by memory.** Every prompt pastes the relevant [SPEC] so Kimi cannot drift the contract.
3. **Tests are part of the deliverable.** The prompt always demands tests; a component without passing tests is not done.
4. **Quarantine branch.** Paste Kimi's output verbatim onto a `kimi/<component>` branch as commit 1; your corrections as commit 2. The diff between them is your permanent record of what Kimi got wrong and your honest answer to "how much did AI write?".
5. **Verification ritual before merge:** run it → read the full diff → the 60-second rule (explain every file in a minute or study/delete it) → for metric code, the hand-computed tripwire.
6. **Never delegate the core.** C3–C6 (reconcile, propagation, ranking, policy) are yours. Kimi may write *edge-case tests* for them only after your contract tests pass.

**The sequence Kimi executes (dependency order):** C0 → C1 → C2 → C7 → C8 (plumbing first) ‖ you build C3–C6 in parallel ‖ then C9a → C9b → C10 → C11 → C12. Data (C9c/C9d) runs alongside from week 1.

## VI.2 Git & review standards

- `main` is protected; nothing merges without a green CI check and a PR you reviewed.
- Branch prefixes signal scrutiny: `feat/` (yours), `kimi/` (max scrutiny), `data/` (validator + sample review), `fix/`.
- Conventional commits: `type: what and why` (feat|fix|test|docs|chore|data). `git log --oneline` reads as a project diary.
- Squash-merge so main history is one-commit-per-finished-thing.
- Every PR description states: what changed, how tested, and (for `kimi/`) what you corrected.

## VI.3 Code standards

- Type hints on every public function; dataclasses for data; no bare dicts across module boundaries.
- Ruff clean (line length 100). Docstrings on every module and public function stating *what* and *why*, not *how*.
- Determinism: every stochastic step takes a seed; seeds logged into results.
- No hidden state: retrieval is a pure function of (question, corpus, budget, jurisdiction).
- Errors are explicit: extraction failures raise, they do not silently return empty.

## VI.4 Testing standards

- Tests encode the spec; for core components, tests are written *before* implementation.
- Three tiers: unit (one function), golden (pipeline output vs hand-computed truth), contract/integration (`make benchmark` runs end-to-end).
- Coverage target 80% on plumbing; do not chase 100% (the last 20% is trivia). Coverage shows where tests are *missing*, not whether they are *good*.
- The metric tripwire (C10) is mandatory before any experiment.

## VI.5 Reproducibility standards (what makes the paper trustworthy)

- One command reproduces every table: `make benchmark`.
- Frozen test split behind a git tag; a guard rail refuses test runs without it.
- Results are mean ± 95% CI over ≥3 seeds; single numbers are never reported.
- A public data card documents real-vs-synthetic provenance per field.
- Baselines' frozen best configs are committed and documented.

## VI.6 Documentation & release standards

- README quickstart works in <5 minutes from `pip install` on a cold machine.
- Data license CC-BY-SA-4.0 (benchmark stays federated); code license MIT (maximum adoption).
- arXiv preprint; Reproducibility Statement lists seeds, splits, configs, hardware.
- Leaderboard renders `results/leaderboard.jsonl`; submissions arrive as PRs with a repro script.

---

# APPENDIX A — THE BUILD SEQUENCE AT A GLANCE

| Order | Component | Owner | Depends on | Done when |
|---|---|---|---|---|
| 1 | C0 scaffold | KIMI | — | CI green |
| 2 | C1 models | KIMI | C0 | dataclasses construct |
| 3 | C2 extract | KIMI | C1 | exemplars load, provenance kept |
| 4 | C3 reconcile | **YOU** | C1 | 5 contract tests green |
| 5 | C4 propagation | **YOU** | C1 | agreement property holds |
| 6 | C5 ranking | **YOU** | C1,C4 | budget+connectivity+seed order |
| 7 | C6 policy Π_J | **YOU** | C1 | must_not_appear byte-absent (EU) |
| 8 | C7 serialize | KIMI | C1,C5,C6 | format exact; None omitted |
| 9 | C8 MCP | KIMI | C5,C6,C7 | 3 tools registered |
| 10 | C9a validator | KIMI | schema (YOU) | exemplars pass, broken fail |
| 11 | C9b generators | KIMI | C9a | 20 valid, deterministic |
| 12 | C9c adversarial | FRIEND | schema | 40 cases via PR, CI-valid |
| 13 | C9d label+freeze | **YOU** | all cases | split tagged |
| 14 | C10 harness | KIMI | C1,cases | metrics tripwire passes |
| 15 | C11 baselines | KIMI | C10 | fairness audit signed off |
| 16 | C12 runner | KIMI | C10,C11 | tables render; test guard works |
| 17 | Experiments | **YOU** | all | 4 tables frozen with CIs |
| 18 | Release | KIMI+YOU | all | PyPI + leaderboard + arXiv |

---

# APPENDIX B — INTERVIEW DEFENSE (the questions you will be asked)

The core you built by hand maps directly to the questions a Meta/Anthropic-level interviewer asks. Prepared answers:

- **"Why is your compliance guarantee stronger than a filter?"** → Because Π_J is a parameter of retrieval, not a post-step: denied nodes never enter the candidate set, so zero-leakage is a property of the operator, provable, not merely observed at 0% in tests.
- **"How do you know your win isn't from weak baselines?"** → Frozen best-config baselines after a documented dev-split grid search; a reviewer cannot beat them with 10 minutes of tuning; and we report where we *tie* (lookup) and *lose*.
- **"Isn't this just GraphRAG?"** → GraphRAG links entities but has no evidential confidence from source disagreement, no temporal semantics in selection, and no jurisdiction filter. Our ablations show each of those is load-bearing.
- **"How much did AI write?"** → The plumbing; the four core files (reconcile, propagation, ranking, policy) and the metric verification are mine, on the record in the commit history, with contract tests I wrote first.
- **"What's the weakest part?"** → Synthetic-link bias and two-jurisdiction scope; mitigated by blind adversarial cases and stated plainly in Limitations. (Naming your own weakness first is the strongest possible answer.)

---

# APPENDIX C — HONEST FRAMING (say these exactly)

- On novelty: "The benchmark measures capabilities nothing else does; the method's novelty is its composition plus a retrieval-time compliance operator." (Not "a new retrieval paradigm.")
- On the market: "This is research and open source, not a company. The win condition is adoption and citation, which is why the license is permissive."
- On outcomes: "All three endings — clear win, partial win, honest loss — are publishable, and were committed to in writing before the experiments ran."

---

*End of the Golden Document. Companion executable files (repo, code stubs, prompts) are generated from this specification. If a decision is not written here, it is not yet decided — add it here first, then build it.*

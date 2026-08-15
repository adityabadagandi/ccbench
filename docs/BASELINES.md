# Baselines — frozen configurations

> Per BENCHMARK_SPEC §6, every baseline is tuned to its best performance on
> the **dev split** by documented grid search, then frozen. Re-tuning on test
> invalidates the result.

Split: `benchmark/cases/dev` (100 cases). Token budget: 4000. Schema 0.2.

## Status

| Method | Status | Context Completeness (dev) | Leak-clean (EU) |
|---|---|---|---|
| **BM25** | frozen | **0.965** | 0.041 |
| Dense RAG | not implemented | — | — |
| Hybrid RAG | not implemented | — | — |
| GraphRAG | not implemented | — | — |
| Context Compiler | not implemented | — | — |

Two **instruments** are reported alongside but are *not* peers — they are handed
the correct case and exist to calibrate the metrics, not to compete:

| Instrument | Completeness | Leak-clean (EU) | Purpose |
|---|---|---|---|
| `oracle` | 1.000 | 0.061 | Proves the completeness ceiling is reachable |
| `dump-everything` | 1.000 | 0.000 | Proves completeness alone is trivially maxed |
| `oracle --gold-answers` | 1.000 | 0.061 | Reference upper bound; benchmark score **0.540** |

---

## BM25

Okapi BM25 via `rank_bm25`, searching **every node of every case** — 1,113
nodes on dev. The method is given only the question and must locate the right
consignment among a hundred before selecting nodes within it.

### Frozen configuration

```python
BM25Retriever(k1=0.9, b=0.3, top_k=24)
```

| Parameter | Value | Grid searched |
|---|---|---|
| `k1` | 0.9 | 0.9, 1.2, 1.5, 2.0 |
| `b` | 0.3 | 0.3, 0.5, 0.75, 0.9 |
| `top_k` | 24 | 6, 8, 10, 12, 16, 20, 24, 28 |

128 configurations, selected on Context Completeness. Reproduce with
`python -m scripts.tune_bm25`; full grid in `results/bm25_grid_dev.json`.

**Why completeness is the selection objective.** Leakage would be trivially
minimised by retrieving nothing, so tuning against it manufactures a crippled
opponent. Correctness and Faithfulness need an answerer and a frozen judge
rubric, neither of which exists yet. Completeness measures what BM25 is for.
Leak rate is recorded for every configuration but never optimised.

**Why `b=0.3` matters.** Library defaults (`k1=1.5, b=0.75`) score **0.751**;
the tuned setting reaches **0.965** — a 21-point swing that would have made
BM25 look far weaker than it is. Low length-normalisation is the lever: these
nodes vary enormously in length, from a one-line chat message to a
three-page invoice, and penalising long documents buries exactly the invoices
and e-way bills most gold facts live in.

**Why `top_k=24`.** Completeness was still rising at the original grid edge of
20, so the grid was extended. It saturates at 24 (0.965) and does not improve
at 28, 32, 40 or 50 — the 4000-token budget binds first, at a mean of 3,274
tokens. The baseline is limited by the budget every method shares, not by a
boundary chosen for convenience.

**Tokenisation.** Business identifiers carry the signal, so every compound id
is emitted *both* whole and split into parts: `TAX/2026-27/69448` yields
`tax/2026-27/69448`, `tax`, `2026`, `27`, `69448`. Word matching is
Unicode-aware so Devanagari survives. Without this, ids would only ever match
verbatim and the baseline would be crippled by a tokenisation choice rather
than by the task.

### Results

```
Context Completeness    0.965
Leak-clean (all)        0.530      (EU only: 0.041)
Mean tokens             3,274 / 4,000
Over budget             0 cases
```

By bucket:

| Bucket | Completeness |
|---|---|
| lookup | 1.000 |
| multi-hop | 1.000 |
| temporal | 1.000 |
| compliance | 1.000 |
| **cross-lingual** | **0.825** |

Case localisation is strong: the rank-1 node belongs to the correct case in
**95/100** cases. Precision is the weak point — only 57% of the top-24 come
from the correct consignment, because the corpus is full of structurally
near-identical documents.

### The one place BM25 breaks

All five incomplete cases are cross-lingual, and splitting by **question
language** shows why:

| Question language | n | Completeness |
|---|---|---|
| English | 88 | **1.000** |
| Romanised Hinglish | 7 | **1.000** |
| Devanagari Hindi | 5 | **0.300** |

Romanised Hinglish shares the Latin script and the consignment id, so lexical
matching survives it intact. Devanagari shares only the id, and the remaining
query terms match Devanagari chat messages in *other* consignments, diluting
the ranking until the right nodes fall outside the budget. Two cases score
0.000 — total retrieval failure.

**Caveat, stated plainly: n=5.** This is a real effect with an obvious
mechanism, but five cases is not a result. See the limitation below.

### Known limitation of the current corpus

The cross-lingual bucket has 40 cases per split, but BM25 fully solves 35 of
them. The bucket's *evidence* is code-switched in all 40 — that invariant is
enforced — yet the **question** is English in most, and it quotes the
consignment reference verbatim. A lexical method can therefore find the right
node by matching the id and never engage with the non-English text at all.

The bucket only bites when the question itself is Devanagari, and only 9 of
200 cases are (5 in dev). Options, in the researcher's hands:

1. Raise the Devanagari share of cross-lingual questions.
2. Stop quoting the consignment reference in cross-lingual questions, forcing
   retrieval to go through the message content.
3. Accept it and report the bucket as measuring code-switched *evidence*
   comprehension rather than cross-lingual *retrieval*.

Option 2 is the sharpest test and the smallest change. Whichever is chosen
must be settled before any further baseline is frozen, since it changes the
corpus and therefore invalidates this table.

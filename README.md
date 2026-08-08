# CCBench & Context Compiler

> The world's first multi-format, multi-jurisdiction enterprise-context benchmark and open-source context compiler.

[![CI](https://github.com/ansh/ccbench/actions/workflows/ci.yml/badge.svg)](https://github.com/ansh/ccbench/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What is this?

**CCBench** is a benchmark for evaluating how well AI systems can compile context from messy, multi-format enterprise documents (invoices, e-way bills, ERP orders, WhatsApp threads) to answer questions correctly — while respecting jurisdiction-specific data emission rules.

**Context Compiler** is the open-source Python library that implements retrieval, matching, and compilation logic for this task.

### The one-paragraph thesis

Current retrieval hands a language model a bag of text chunks ranked by similarity and hopes the model reconstructs how they relate. For enterprise questions whose answer lives across formats, languages, time, and legal boundaries, that hope fails. A **Context Compiler** instead builds the relationships first — linking multi-format facts into a typed graph, propagating confidence across sources that agree or disagree, ordering events in time, selecting a connected subgraph that fits the token budget, and filtering by jurisdiction *at retrieval time* — then emits a compact, citable context package. The model reasons over structure that is already built, so correctness and faithfulness rise and cross-border leakage becomes impossible by construction.

---

## Why does it matter?

Current RAG benchmarks test clean, single-language, single-document retrieval. Real enterprise data is:
- **Multi-format:** PDF invoices, JSON ERP records, messy WhatsApp screenshots
- **Multi-jurisdiction:** Indian GST rules vs. EU GDPR emission policies
- **Noisy:** OCR typos, currency format variance, near-duplicate vendor names
- **Cross-lingual:** Hindi/English code-switched chat threads

**No existing benchmark tests the intersection of all four.** CCBench is the first.

| Benchmark | Multi-hop | Multi-format | Cross-lingual | Temporal | Compliance |
|-----------|-----------|--------------|---------------|----------|------------|
| HotpotQA | ✅ | ❌ | ❌ | ❌ | ❌ |
| RAGBench | ✅ | ❌ | ❌ | ❌ | ❌ |
| GraphCompliance | ❌ | ❌ | ❌ | ❌ | ✅ (GDPR only) |
| **CCBench (ours)** | **✅** | **✅** | **✅** | **✅** | **✅ (IN + EU)** |

---

## Quickstart

```bash
# Clone the repo
git clone https://github.com/ansh/ccbench.git
cd ccbench

# Install the package
pip install -e ".[dev]"

# Run tests
pytest

# Run a baseline on the dev split
python -m baselines.run --method bm25 --split dev
```

---

## Repository Structure

```
ccbench/
├── benchmark/          # Case data, schemas, gold labels
│   ├── cases/
│   ├── schema/
│   └── splits/
├── harness/            # Evaluation runner and metrics
│   ├── loader.py
│   ├── runner.py
│   └── metrics/
├── baselines/          # Retrieval baseline implementations
│   ├── bm25.py
│   ├── dense_rag.py
│   ├── hybrid_rag.py
│   └── graph_rag.py
├── compiler/           # Main context-compiler library (PyPI package)
│   ├── reconcile.py        # [YOU] Document matching + mismatch detection
│   ├── score_node.py       # [YOU] Relevance ranking function
│   ├── policies.py         # [YOU] Jurisdiction emission rules (Π_J)
│   ├── propagate.py        # [YOU] Confidence propagation engine
│   └── server.py           # [KIMI] MCP server entry point
├── tests/              # Test suite
├── docs/               # Documentation
│   ├── BENCHMARK_SPEC.md
│   ├── DATA_CARD.md
│   ├── BASELINES.md
│   ├── INTERVIEW_DEFENSE.md
│   └── THREE_ENDINGS.md
├── .github/            # GitHub Actions CI
└── pyproject.toml
```

### Component Ownership

| Component | File | Owner | Rationale |
|---|---|---|---|
| Reconciliation logic | `compiler/reconcile.py` | **YOU** | interview crown jewel; the finding logic |
| Ranking function | `compiler/score_node.py` | **YOU** | the retrieval contribution |
| Confidence propagation | `compiler/propagate.py` | **YOU** | the mechanism ablations defend |
| Π_J policy | `compiler/policies.py` | **YOU** | the 0%-leakage claim is yours to prove |
| Graph assembly / serialization | `compiler/context.py` | KIMI | plumbing around your core |
| MCP server | `compiler/server.py` | KIMI | SDK boilerplate |
| Extraction | `compiler/extract.py` | KIMI | format wrangling |
| Data generators | `generators/` | KIMI | volume; you audit realism |
| Evaluation harness | `harness/` | KIMI | plumbing; you verify metrics by hand |
| Baselines | `baselines/` | KIMI | you audit fairness |
| Benchmark cases | `benchmark/cases/` | FRIEND (blind) + YOU (gold) | adversarial credibility |

**The rule in one line:** anything a reviewer or interviewer would probe, you write by hand; everything routine is delegated and verified line-by-line before merge.

---

## Leaderboard

| Method | Overall | Lookup | Multi-hop | Temporal | Cross-lingual | Compliance |
|--------|---------|--------|-----------|----------|---------------|------------|
| BM25 | — | — | — | — | — | — |
| Dense RAG | — | — | — | — | — | — |
| Hybrid RAG | — | — | — | — | — | — |
| GraphRAG | — | — | — | — | — | — |
| Context Compiler (ours) | — | — | — | — | — | — |

---

## The Three Endings (Committed in Advance)

| Ending | Numbers | You publish | Note |
|---|---|---|---|
| A — clear win | beat hybrid + GraphRAG broadly | method-led paper | maximum |
| B — partial win | win multi-hop + compliance, tie lookup | benchmark-led paper, method as strong reference | high |
| C — honest loss | hybrid RAG holds | benchmark + negative result | still high; honesty gets cited |

**The leakage column survives all three untouched** — it is architectural, not empirical. The worst honest outcome is still a public benchmark, a shipped library, a paper, and defensible expertise.

---

## Citation

```bibtex
@article{ccbench2024,
  title={CCBench: A Multi-Format, Multi-Jurisdiction Enterprise Context Benchmark},
  author={Ansh and Collaborator},
  journal={arXiv preprint},
  year={2024}
}
```

---

## License

- **Code:** MIT License
- **Benchmark Data:** CC-BY-SA 4.0

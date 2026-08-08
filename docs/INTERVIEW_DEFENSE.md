# Interview Defense

> The questions you will be asked — and the prepared answers.

The core you built by hand maps directly to the questions a Meta/Anthropic-level interviewer asks. These are your prepared answers.

---

## Q1: "Why is your compliance guarantee stronger than a filter?"

**Answer:** Because Π_J is a parameter of retrieval, not a post-step filter. Denied nodes never enter the candidate set, so zero-leakage is a property of the operator itself — provable by construction — not merely observed at 0% in tests.

**Deeper:** A post-filter can have bugs, race conditions, or bypass paths. Π_J is applied at node loading time: `policy(node, J) != deny` is a guard on the candidate set. The node is never retrieved, never ranked, never serialized. This is the difference between a tested property and a proved one.

---

## Q2: "How do you know your win isn't from weak baselines?"

**Answer:** Three reasons:

1. **Frozen best-config baselines after a documented dev-split grid search.** Every hyperparameter is committed and documented in `docs/BASELINES.md`.
2. **Fairness audit:** I tuned each baseline like I wanted it to win. If a reviewer can beat our reported baseline with 10 minutes of tuning, the results table is dead — so I made sure they can't.
3. **We report where we tie and lose.** We tie on lookup (as expected — no method needed for single-document retrieval). We report that proudly; it makes the multi-hop and compliance wins believable.

---

## Q3: "Isn't this just GraphRAG?"

**Answer:** GraphRAG links entities but lacks three things we add:

1. **Evidential confidence from source disagreement.** GraphRAG scores by community relevance; we propagate confidence through source (dis)agreement using log-odds fusion and personalized PageRank.
2. **Temporal semantics in selection.** GraphRAG stores temporal data but doesn't use it in budgeted subgraph selection. We enforce temporal ordering as a constraint.
3. **Jurisdiction filter at retrieval time.** GraphRAG has no compliance operator. Our ablations show each of these is load-bearing.

**The ablation table is the proof:** removing graph connectivity hurts, removing confidence propagation hurts, removing Π_J explodes leakage.

---

## Q4: "How much did AI write?"

**Answer:** The plumbing: extraction, serialization, MCP server, harness scaffolding, baseline implementations, data generators. The four core files — `reconcile.py`, `propagate.py`, `score_node.py`, `policies.py` — and the metric verification are mine, on the record in the commit history, with contract tests I wrote first. The diff between the `kimi/` branches and `main` is the permanent record of what AI got wrong and what I corrected.

---

## Q5: "What's the weakest part?"

**Answer:** Two things:

1. **Synthetic-link bias:** Our generators create linked documents from a shared seed. Real-world documents are messier — vendors abbreviate names, references have typos, dates are ambiguous. We mitigate this with noise injection and adversarial cases from a blind collaborator.
2. **Two-jurisdiction scope:** We only test IN vs EU. A full system would need rules for US CCPA, Singapore PDPA, etc. We state this plainly in Limitations.

**Naming your own weakness first is the strongest possible answer.** It signals rigor and earns reviewer trust.

---

## Q6: "Why only 200 cases? RAGBench has 100K."

**Answer:** Not all benchmarks need to be large. They need to be hard and well-designed.

- HotpotQA has 113K cases, but they're all Wikipedia paragraphs. Easy to generate.
- Our 200 cases require: realistic GST invoice structure, linked e-way bills with correct government reference numbers, Hindi/English code-switched WhatsApp threads, planted mismatches and temporal violations, jurisdiction-aware privacy rules.
- **These cannot be crowd-sourced.** Each case requires expert domain knowledge.
- 200 expert-curated cases > 20,000 automatically generated ones.

---

## Q7: "What if your method doesn't win?"

**Answer:** All three outcomes are publishable and were committed to in writing before the experiments ran:

- **Clear win** → method-led paper
- **Partial win** → benchmark-led paper, method as strong reference
- **Honest loss** → benchmark + negative result ("large headhead remains")

The benchmark itself is the primary contribution. It measures capabilities no existing benchmark measures. Even if our method loses, CCBench is citable and usable by the community.

---

## Honest Framing (Say These Exactly)

- **On novelty:** "The benchmark measures capabilities nothing else does; the method's novelty is its composition plus a retrieval-time compliance operator." (Not "a new retrieval paradigm.")
- **On the market:** "This is research and open source, not a company. The win condition is adoption and citation, which is why the license is permissive."
- **On outcomes:** "All three endings — clear win, partial win, honest loss — are publishable, and were committed to in writing before the experiments ran."

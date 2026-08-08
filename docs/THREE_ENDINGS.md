# The Three Endings

> Committed in advance. Whatever the numbers say is what we publish.

## The Principle

Research integrity means deciding your publishing strategy **before** you see the results. Once you look at the test numbers, every decision is suspect. We commit to three possible outcomes now, while the results are still unknown.

---

## Ending A — Clear Win

**Condition:** Context Compiler beats Hybrid RAG and GraphRAG on the majority of buckets, with statistically significant margins.

**Paper type:** Method-led paper.

**Claim:** "On CCBench, context compilation improves multi-hop answer correctness by ~X points over GraphRAG and ~Y over hybrid RAG, with ablations showing graph connectivity and compilation itself as dominant factors, while the Π_J operator eliminates cross-jurisdiction leakage entirely (0% vs Z% for all baselines)."

**Target venue:** NeurIPS main track or ACL.

---

## Ending B — Partial Win

**Condition:** Context Compiler wins on multi-hop and compliance, ties on lookup, and may lose on temporal or cross-lingual.

**Paper type:** Benchmark-led paper, method as strong reference.

**Claim:** "We introduce CCBench, the first benchmark for composite enterprise retrieval across multi-format documents, cross-lingual code-switching, temporal ordering, and jurisdiction-aware emission. Our Context Compiler method demonstrates strong performance on multi-hop reasoning and zero-leakage compliance, establishing a reference implementation for this new task."

**Target venue:** NeurIPS Datasets & Benchmarks track or ACL.

---

## Ending C — Honest Loss

**Condition:** Hybrid RAG holds the overall best performance. Context Compiler does not beat it on any bucket.

**Paper type:** Benchmark + negative result.

**Claim:** "We built the benchmark that the RAG community said was missing. Our method did not beat Hybrid RAG — here is why, and here is what we learned about the difficulty of multi-format, multi-jurisdiction retrieval."

**Target venue:** NeurIPS Datasets & Benchmarks track or arXiv.

**Why this is still high-value:**
- Negative results with rigorous benchmarks get cited (e.g., the "No Free Lunch" papers)
- The benchmark itself is a permanent contribution
- Honesty earns trust and future collaboration
- The leakage column still shows 0% vs nonzero for baselines — an architectural result

---

## The Leakage Guarantee

Regardless of ending, this claim stands:

> **Π_J leakage = 0.0% on the compliance bucket, versus nonzero for every baseline.**

This is not an empirical result that could change with more data. It is a property of the operator: denied nodes never enter the candidate set. The worst honest outcome still includes this result.

---

## The Honesty Gate

**Written here so it cannot be renegotiated later:**

- If our method DOES NOT beat Hybrid RAG on multi-hop after fair tuning, we do NOT re-tune on test.
- We do NOT add cases to the test set to improve our numbers.
- We do NOT change the metric definitions post-hoc.
- We report mean ± 95% CI over ≥3 seeds; single numbers are never reported.
- If we improve the method, we re-run on DEV ONLY and update the paper.

**The benchmark is publishable even if your method loses.**

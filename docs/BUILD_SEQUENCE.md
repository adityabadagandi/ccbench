# Build Sequence

> The exact order to build this project. Each component depends only on those above it.

| Order | Component | Owner | Depends on | Done when |
|---|---|---|---|---|
| 1 | C0 scaffold | KIMI | — | CI green |
| 2 | C1 models | KIMI | C0 | dataclasses construct |
| 3 | C2 extract | KIMI | C1 | exemplars load, provenance kept |
| 4 | C3 reconcile | **YOU** | C1 | 5 contract tests green |
| 5 | C4 propagation | **YOU** | C1 | agreement property holds |
| 6 | C5 ranking | **YOU** | C1, C4 | budget + connectivity + seed order |
| 7 | C6 policy Π_J | **YOU** | C1 | must_not_appear byte-absent (EU) |
| 8 | C7 serialize | KIMI | C1, C5, C6 | format exact; None omitted |
| 9 | C8 MCP | KIMI | C5, C6, C7 | 3 tools registered |
| 10 | C9a validator | KIMI | schema (YOU) | exemplars pass, broken fail |
| 11 | C9b generators | KIMI | C9a | 20 valid, deterministic |
| 12 | C9c adversarial | FRIEND | schema | 40 cases via PR, CI-valid |
| 13 | C9d label + freeze | **YOU** | all cases | split tagged |
| 14 | C10 harness | KIMI | C1, cases | metrics tripwire passes |
| 15 | C11 baselines | KIMI | C10 | fairness audit signed off |
| 16 | C12 runner | KIMI | C10, C11 | tables render; test guard works |
| 17 | Experiments | **YOU** | all | 4 tables frozen with CIs |
| 18 | Release | KIMI + YOU | all | PyPI + leaderboard + arXiv |

---

## Parallel Tracks

**Track A — Plumbing (KIMI):** C0 → C1 → C2 → C7 → C8 → C9a → C9b → C10 → C11 → C12

**Track B — Core (YOU):** C3, C4, C5, C6 in parallel (each only needs C1)

**Track C — Data (FRIEND + YOU):** C9c (friend) and C9d (you) run alongside from week 1

---

## The Kimi Delegation Protocol

Kimi is a capable long-context coding agent, but it degrades on monolithic builds — it forgets earlier decisions and silently changes interfaces. The protocol that prevents this is exactly how large engineering orgs ship: **small, tested, reviewed units against frozen interfaces.**

**Rules for every Kimi task:**

1. **One component per prompt.** Never "build the whole harness." Always a single C-numbered spec.
2. **Reference interfaces by paste, not by memory.** Every prompt pastes the relevant [SPEC] so Kimi cannot drift the contract.
3. **Tests are part of the deliverable.** The prompt always demands tests; a component without passing tests is not done.
4. **Quarantine branch.** Paste Kimi's output verbatim onto a `kimi/<component>` branch as commit 1; your corrections as commit 2. The diff between them is your permanent record of what Kimi got wrong and your honest answer to "how much did AI write?"
5. **Verification ritual before merge:**
   - Run it
   - Read the full diff
   - The 60-second rule (explain every file in a minute or study/delete it)
   - For metric code, the hand-computed tripwire
6. **Never delegate the core.** C3–C6 (reconcile, propagation, ranking, policy) are yours. Kimi may write *edge-case tests* for them only after your contract tests pass.

---

## Git & Review Standards

- `main` is protected; nothing merges without a green CI check and a PR you reviewed.
- Branch prefixes signal scrutiny:
  - `feat/` — your features
  - `kimi/` — maximum scrutiny (AI-generated code)
  - `data/` — validator + sample review
  - `fix/` — bug fixes
- Conventional commits: `type: what and why` (feat|fix|test|docs|chore|data)
- `git log --oneline` reads as a project diary.
- Squash-merge so main history is one-commit-per-finished-thing.
- Every PR description states: what changed, how tested, and (for `kimi/`) what you corrected.

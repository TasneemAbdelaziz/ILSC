# Revised plan — from here to a first draft

The three-week plan in the proposal (Sec. 9) assumed both tracks running in
parallel from Day 1. They did not: the empirical track ran ahead and the metric
track started late. This is the schedule from today's actual state, not from the
plan's assumed one.

Day numbers below are **working days from today**. The proposal's own day
numbers are kept in the last column so the two can be lined up.

---

## 1. What is banked

| Track | Item | Proposal day |
|---|---|---|
| Empirical | Multi-source curation, S1 + S2, 2,206 services | 1–2 |
| Empirical | 2.0 → 3.x conversion, operation sets verified | 1–2 (b) |
| Empirical | D-02 strict validation, 97.5% | — |
| Empirical | Field-availability study + Fig 1 | 3 |
| Empirical | Pair-level co-availability (RQ2) + Fig 2 | 3 |
| Empirical | Gate 1 candidates + written expectations | 1–2 side list |
| Metric | Parser, tokenizer, path normaliser, `T(Oi)` | 1–2 |

Roughly **4 of the proposal's 21 days**, plus a fair amount that was never in
the plan: the conversion step, the strict-validation number, per-source
stratification, the pair-level layer, scan caching, and decisions D-09…D-15.

**Not banked:** the similarity engine. Every remaining item on **both** tracks
sits behind it.

---

## 2. The schedule

Two chains run in parallel. Tasneem's chain needs no ILSC scores until Gate 2,
so it starts immediately rather than waiting on the engine — this is the main
change from the proposal, and it is what keeps the total near three weeks.

| Day | Mohamed — metric | Tasneem — empirical | Milestone | Prop. |
|---|---|---|---|---|
| **1** | `embed.py` + `similarity.py`: six similarity functions, availability mask, embedding cache | Benchmark prep: clone Sock Shop, Online Boutique, **Train Ticket**; convert specs | — | 3 / 5 |
| **2** | Unit tests incl. the R2 regression test; `ilsc.py` — mean, τ, components | One-pager per system: each service's intended responsibility, 2–3 sentences | — | 3 / 5 |
| **3** | Null models: global + provider-restricted (**D3**), 1,000 draws per size, cached | Code dig — `user` (15 endpoints, the largest) | — | 5 / 8 |
| **4** | **Run Gate 1** on the ten candidates → `sanity_check.csv`; joint review | Code dig — `carts` + `catalogue` | **Gate 1** | 4 / 9 |
| **5** | Exp 1 big run: `results.csv`, quartile thresholds, S1-only thresholds | Code dig — `orders` + `payment` | Figs 2, 7, 8 | 5 / 10 |
| **6** | Exp 1 cont.: inter-feature correlation matrix (Fig 9) | Code dig — verification pass, assemble `endpoint_entities.csv` | Fig 9 | 5 / 11 |
| **7** | *Slack / catch-up* | Reliability check: re-derive 10 endpoints independently, report agreement | — | 6 |
| **8** | `inject.py` + monotonicity and contrast checker | Exp 2: perturbation run, three proximity levels (D-05) | Fig 3 | 7 |
| **9** | Exp 4: implement SIDC + LoCmsg | Figures — restyle all to one palette, vector PDF | — | 8–11 |
| **10** | Exp 4: baselines under the same perturbation pipeline | Replication package: `run_all.py`, pins, both exclusion lists | Comparison table | 8–11 |
| **11** | Exp 3 metric side: pair-level ρ over all benchmark pairs | Package tested on a **fresh clone** | Fig 4 | 13 |
| **12** | Exp 3: service-level ρ, discordant pairs written up *(joint)* | *(joint)* | **Gate 2**, Fig 5 | 14 |
| **13** | Exp 5: weight sensitivity ±20/±40%, Kendall's W | Threats to validity, drafted with Mohamed | Fig 6 | 15 |
| **14** | Exp 5: τ sweep 0.30–0.70, and the `DROP_VERSION_TOKENS` knob (D-15) | Experimental Setup + dataset section | `kendalls_w.csv` | 15 |
| **15** | *Slack / catch-up* | *Slack / catch-up* | — | 12 |
| **16–21** | Write theory half | Write empirical half | **First draft** | 16–21 |

---

## 3. Decisions due before they block

| # | Decision | Owner | Due |
|---|---|---|---|
| **D1** | Provider cap — none / 50 / 30 / 20 per provider | Mohamed | **Day 4** (before Exp 1) |
| **D2** | Oversized services > 200 ops — exclude / subsample / cap | Mohamed | **Day 4** (before Exp 1) |
| **D3** | What replaces domain labels in the domain-restricted null model | Both | **Day 2** (blocks Day 3) |
| **D-14** | Whether mask statistics get re-derived from `parsed/` | Both | **Day 4** (before Exp 1) |

**D2 is the sharpest.** 70 services with more than 200 operations hold 97.6% of
all 77.6M pairs, and one service alone holds 84.0%. Until it is capped, every
pair-weighted corpus number is a statement about a handful of mega-specs.

**D3 has no candidate in the proposal.** D-03 rejected keyword labelling and
D-04 rejected LLM labelling, so the domain-restricted null model has no label
source. Provider-restricted is the obvious substitute — it is metadata, needs no
judgement, and matches the reasoning already accepted for D-05.

---

## 4. What changed from the proposal, and why

**Tasneem starts the code dig on Day 3, not Day 8.** It is the longest single
task on either track (four days), it gates Gate 2, and it needs no ILSC scores —
only source code and specs. Leaving it in its original slot would idle her for
the first week while Mohamed builds the engine, then make it the critical path
at the end. Moving it forward is what keeps the schedule near three weeks.

**Gate 1 moves from Day 4 to Day 4-from-now**, because it needs `ILSC_mean` and
therefore the engine. Its inputs — the ten candidates and their written
expectations — are already done.

**Gate 2 moves from Day 14 to Day 12**, a consequence of the code dig starting
earlier.

**Exp 5 gains a third knob.** Beyond weights and τ, `DROP_VERSION_TOKENS`
(D-15) changes f2 and f3 token sets and must be reported as a sensitivity band,
not a silent default.

**Day 3 of the empirical track is already over-delivered.** The pair-level
co-availability layer was not in the plan and is the actual RQ2 result; the
per-operation study alone would not have supported the claim.

---

## 5. Risks, honestly

**The engine is a single point of failure.** Days 1–2 are one person on one
component with everything behind it. If it slips, everything slips. It has no
parallel path and no slack in front of it.

**Four days for the code dig was the proposal's own largest underestimate**
(R9), and it is still four days across three languages. If `user` alone takes
more than a day, re-scope to Sock Shop only and drop the Train Ticket stretch
rather than compressing the verification pass.

**Gate 2 can fail.** If pair-level ρ < 0.4, the proposal's instruction stands:
diagnose before writing — tokenization, weights, or entity-extraction quality.
Budget the Day 15 slack for that, not for polish.

**Three weeks produces a first draft, not a submission.** The proposal says this
and it remains true. Budget a fourth week for revision.

---

## 6. Bringing the paper text in line

Corrections already established that the manuscript must absorb (`DECISIONS.md`):

- **Sec. 7** — S1 is **2,619** OpenAPI files, not 1,737 (D-12).
- **Sec. 7** — the "400–600 clean services (≥ 300 from S1)" target is
  superseded: 2,206 and 1,014 (D-12).
- **Sec. 6 / RQ2** — the mask's justification is the **pair-level** number and
  should be reported per service (**68.4%**), not as a pair-weighted percentage
  (D-13, and the warning at the top of `RESULTS.md`).
- **Sec. 6** — the admin-endpoint list is 12 entries, not 6, and is matched on
  the whole path (D-07).
- **External validity** — S1 is *more* provider-concentrated than S2 (58.1% vs
  37.4%). Reusing a peer-reviewed corpus buys comparability, not diversity
  (D-12).

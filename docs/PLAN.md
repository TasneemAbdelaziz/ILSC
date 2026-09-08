# Revised plan — from here to a first draft

*Re-baselined **Tue 2026-09-08**. Supersedes the 2026-09-02 revision, which was
itself a re-baseline of the proposal's Sec. 9 three-week plan.*

The 09-02 revision assumed both tracks starting immediately. One did. Day
numbers below are **working days from today**; today is **Day 4 of the 09-02
schedule**, and this document restarts the count at Day 1 tomorrow. The
proposal's own day numbers are kept in the last column so the three can be
lined up.

---

## 0. Status — Days 1–7 of this schedule are complete

*Updated 2026-09-08, end of day. Both tracks ran Days 1–7 in a single push; the
day-by-day table in §3 is retained as the record of what was planned.*

| Day | Metric track | Empirical track |
|---|---|---|
| 1 | `embed.py`, `similarity.py`; **D3 resolved (D-18)** ✅ | responsibility one-pagers ✅ (§F-03 caveat) |
| 2 | 17/17 unit tests incl. R2; `ilsc.py` ✅ | one-pagers cont.; extraction design ✅ |
| 3 | null models, flatness confirmed (D-21) ✅ | code dig — `user` ✅ |
| 4 | **GATE 1 — MARGINAL** (D-24) ⚠ | code dig — `carts`, `catalogue` ✅ |
| 5 | Exp. 1, 2,206 services + thresholds ✅ | code dig — `orders`, `payment` ✅ |
| 6 | Fig 9, no feature pair above 0.85 ✅ | verification pass, `endpoint_entities.csv` ✅ |
| 7 | `inject.py`; **H2 contrast POSITIVE** ✅ | Train Ticket automated extraction ✅ |

**The engine that was three days late no longer is.** It exists, is tested, and
every experiment behind it has run.

**Three things did not go to plan, and all three are recorded rather than
smoothed over:**

1. **Gate 1 is MARGINAL, not a pass** (D-24). One service, Xero Payroll AU,
   breaks the separation; no weight scheme fixes it and the proposal's own
   suggested remedy makes it worse. Read as a construct-validity finding.
2. **`ρ_independent` may not be estimable** (F-04). Sock Shop's code side has
   five distinct values over two services with any variance.
3. **Two reliability figures are owed** and cannot be self-administered — both
   sample sheets are written and blank.

---

## 1. What is banked

| Track | Item | Artifact | Day |
|---|---|---|---|
| Empirical | Multi-source curation, S1 + S2, 2,206 services | `results/manifest.csv` | prop. 1–2 |
| Empirical | 2.0 → 3.x conversion, operation sets verified | `results/convert_verify.csv` | prop. 1–2 |
| Empirical | D-02 strict validation, 97.5% | `results/strict_validation_sample.csv` | — |
| Empirical | Field-availability study + Fig 1 | `results/availability*.csv` | prop. 3 |
| Empirical | Pair-level co-availability (RQ2) + Fig 2 | `results/pair_availability*.csv` | prop. 3 |
| Empirical | Gate 1 candidates + written expectations | `docs/gate1_expectations.md` | prop. 1–2 |
| Metric | Parser, tokenizer, path normaliser, `T(Oi)` | `src/parse_spec.py`, `parsed/` | prop. 1–2 |
| **Empirical** | **Benchmark prep — Sock Shop + Train Ticket, 39 services, 916 pairs** | `src/benchmark_prep.py`, `results/benchmark_manifest.csv` | **09-02 Day 1** |
| **Empirical** | **D-16 — Train Ticket admitted as a labelled `generated-from-source` condition** | `docs/DECISIONS.md` | *off-plan* |
| **Empirical** | **D-17 — oversized cap at 200 ops, primary + sensitivity protocol** | `src/oversized.py`, `results/oversized_thresholds.csv` | *off-plan* |
| **Empirical** | **D-14 corpus gap stated (`clean/` vs `clean3/`, f4 ~5 pts optimistic)** | `docs/DECISIONS.md` | *off-plan* |
| **Empirical** | **F-01 raised and closed; F-02 raised and quantified** | `docs/FLAGS.md` | *off-plan* |

That is roughly **5 of the proposal's 21 days**, plus a substantial amount that
was never in any plan.

**Two of the off-plan items changed the paper's headline numbers**, which is why
they were worth the two days:

- **D-17 resolves D2**, which had blocked Exp. 1 since the proposal. The RQ2
  mask-fire headline is now **56.87% (micro, primary)** against 90.58% on the
  full corpus — the earlier figure was substantially a statement about a handful
  of gateway specifications. Every per-service quartile boundary moves by at most
  3.17 points, confirming that the service-level framing is the robust one.
- **D-16 establishes that Exp. 3's independent-spec evidence rests on Sock Shop
  alone** — 5 services, 122 pairs — because no authored Train Ticket spec exists
  and Online Boutique is gRPC. That constrains what Exp. 3 can claim, and it is
  better known now than at Gate 2.

**Not banked:** the similarity engine. Unchanged from the last revision. Every
remaining item on **both** tracks still sits behind it.

---

## 2. The new scope problem — Train Ticket's code dig

**D-16 admits Train Ticket to Exp. 3 as a separate `ρ_derived` condition. Nobody
has budgeted the work that implies.**

`ρ_derived` correlates interface similarity against **code-level entity
overlap** — so it needs the same endpoint→entity extraction that the Sock Shop
code dig produces, over **34 Java services** instead of 5. The 09-02 plan's
four-day code dig covered Sock Shop only. Train Ticket is roughly seven times
the service count.

Done the same way, that is a two-week task on its own and the schedule does not
survive it.

**The way through: extract Train Ticket automatically, verify a sample by hand.**
Train Ticket is *almost* uniformly Java / Spring Boot — one framework, one
annotation vocabulary — which is the condition under which a parser beats a
human reader. **Correction, 2026-09-08:** it is not *entirely* uniform. Of the 34
specified services, `ts-avatar-service` is Python and `ts-news-service` is Go,
and the wider repository also contains JavaScript. The automated pass covers
32 of 34; those two need a manual pass and
`src/entity_extract.py` now names them explicitly rather than returning empty
sets that would read as "touches nothing". A pass over `@Entity` / `@Document` classes and
per-controller DTO imports gives endpoint→entity sets mechanically; a 10-service
manual sample then measures how good that pass is, and the measured agreement
gets reported. Sock Shop stays hand-dug: three languages, five services, and it
carries `ρ_independent`, the coefficient the paper leans on.

Budgeted below as **Days 7–8**, two days, not eight.

**If the automated pass cannot be made to work**, the fallback is to report
`ρ_independent` from Sock Shop and drop `ρ_derived` — losing the
derivation-inflation estimate D-16 argues for, but not the experiment. Decide
that by **Day 8**, not later.

---

## 3. The schedule

| Day | Mohamed — metric | Tasneem — empirical | Milestone | Prop. |
|---|---|---|---|---|
| **1** | `embed.py` + `similarity.py`: six similarity functions, availability mask, embedding cache. **Decide D3 today** — it blocks Day 3. | Responsibility one-pagers: Sock Shop 5 by hand; Train Ticket 34 from the FudanSELab *Service Guide* | — | 3 / 5 |
| **2** | Unit tests incl. the R2 regression test; `ilsc.py` — mean, τ, components | One-pagers cont.; design the Train Ticket entity-extraction pass | — | 3 / 5 |
| **3** | Null models: global + provider-restricted (**D3**), 1,000 draws per size, cached | Code dig — `user` (15 endpoints, the largest) | — | 5 / 8 |
| **4** | **Run Gate 1** on the ten candidates → `sanity_check.csv`; joint review | Code dig — `carts` + `catalogue` | **Gate 1** | 4 / 9 |
| **5** | Exp 1 big run — **primary *and* sensitivity per D-17** — `results.csv`, ILSC quartile thresholds, S1-only thresholds | Code dig — `orders` + `payment` | Figs 7, 8 | 5 / 10 |
| **6** | Exp 1 cont.: inter-feature correlation matrix (Fig 9) | Code dig verification pass; assemble Sock Shop `endpoint_entities.csv` | Fig 9 | 5 / 11 |
| **7** | `inject.py` + monotonicity and contrast checker | **Train Ticket entity extraction — automated pass, 34 services** (§2) | — | 7 |
| **8** | Exp 2: perturbation run, three proximity levels (D-05) | **Train Ticket extraction — manual verification on 10 services; report agreement.** Go/no-go on `ρ_derived`. | Fig 3 | 7 |
| **9** | Exp 4: implement SIDC + LoCmsg | Reliability check: re-derive 10 Sock Shop endpoints independently, report agreement | — | 8–11 |
| **10** | Exp 4: baselines under the same perturbation pipeline | Figures — restyle all to one palette, vector PDF | Comparison table | 8–11 |
| **11** | Exp 3 metric side: pair-level ρ, **the two conditions computed separately** | Replication package: `run_all.py` (**add `oversized.py` + `benchmark_prep.py`, §5**), pins, both exclusion lists | Fig 4 | 13 |
| **12** | Exp 3: service-level ρ, **`ρ_independent` vs `ρ_derived` reported apart**, discordant pairs *(joint)* | Package tested on a **fresh clone** *(joint)* | **Gate 2**, Fig 5 | 14 |
| **13** | Exp 5: weight sensitivity ±20/±40%, Kendall's W | Threats to validity, drafted with Mohamed | Fig 6 | 15 |
| **14** | Exp 5: τ sweep 0.30–0.70, and the `DROP_VERSION_TOKENS` knob (D-15) | Experimental Setup + dataset section | `kendalls_w.csv` | 15 |
| **15** | *Slack / catch-up* | *Slack / catch-up* | — | 12 |
| **16–21** | Write theory half | Write empirical half | **First draft** | 16–21 |

**What this costs.** Twenty-one working days from tomorrow, against the fifteen
that were left on 09-02. The four lost days are not recovered anywhere; the one
mid-plan slack day the last revision carried on Day 7 has been spent absorbing
the Train Ticket extraction, and the Day 15 slack is now the only float in the
schedule. **The first draft lands roughly four working days later than the 09-02
plan projected, and about five weeks after the proposal's start.**

---

## 4. Decisions

| # | Decision | Owner | Due | Status |
|---|---|---|---|---|
| **D1** | Provider cap — none / 50 / 30 / 20 per provider | Mohamed | **Day 4** (before Exp 1) | **open** |
| **D3** | What replaces domain labels in the domain-restricted null model | Both | **Day 1** — *was due 09-02 Day 2, now overdue and blocking* | **open** |
| **F-02** | Should `norm_host()` collapse `api.`/`www.` to the registrable domain? | Mohamed | **Day 5** (before the corpus count is written up) | **open** |
| ~~D2~~ | ~~Oversized services > 200 ops~~ | — | — | **resolved — D-17** |
| ~~D-14~~ | ~~Whether mask statistics get re-derived from `parsed/`~~ | — | — | **position stated** — not re-deriving; the ~5-point f4 gap is a declared limitation, revisited only if Exp. 4 proves sensitive |

**D3 is now the sharpest, and it has slipped.** It was due on 09-02 Day 2 and is
still open, while the null models it feeds are scheduled for Day 3. D-03 rejected
keyword labelling and D-04 rejected LLM labelling, so the domain-restricted null
model has no label source at all. Provider-restricted remains the obvious
substitute — metadata, no judgement, and consistent with the reasoning already
accepted for D-05. **It needs deciding on Day 1, not Day 3.**

**D1 is the only original decision still untouched by anyone.**

**F-02 is new since the last revision.** 20 near-duplicate services survive the
dedup key (0.91% of the corpus, 1.14% of operations). D-17's cap already removes
the only group that mattered numerically — GitHub v3, which alone was 98.4% of
duplicate-added pairs and is itself oversized — so residual contamination in the
primary corpus is **0.31% of pairs** and the D-17 thresholds did not need
re-deriving. What it still affects is the **headline corpus count of 2,206**,
which appears in the paper and is ~0.9% high.

**Note on ownership.** D2 was assigned to Mohamed and was decided by Tasneem, in
order to unblock the pair-weighted numbers rather than leave them labelled
indefinitely. That was the right call under the circumstances, but the same
circumstances now apply to D1, D3 and F-02 — all three sit with the metric
track, and all three block Exp. 1.

---

## 5. Housekeeping

- **`run_all.py` no longer reproduces the repository.** It is missing
  `src/oversized.py` and `src/benchmark_prep.py`, so a fresh clone reproduces
  neither the D-17 primary/sensitivity split nor the benchmark corpus. Fixed on
  Day 11 with the replication package, but note it before quoting
  reproducibility.
- **ILSC quartile thresholds must follow the D-17 protocol** when the engine
  lands — primary and sensitivity, side by side, never one alone. D-17 fixes the
  protocol, not a single table.

---

## 6. Risks, honestly

**The engine has already slipped, and it is still the single point of failure.**
The last revision called it "one person on one component with everything behind
it, no parallel path, no slack in front of it." Three days later it has not
started and Gate 1 has been missed. Nothing about the risk has changed except
that it is now realised rather than hypothetical. **If Day 1–2 slips again, the
three-week frame is gone and the honest move is to say so rather than compress
the code dig.**

**The code dig is now two digs.** Four days for Sock Shop was the proposal's
largest underestimate (R9) and it is still four days across three languages —
and D-16 has added 34 Java services on top. §2's automated pass is the only
version of this that fits. If `user` alone runs past a day, drop `ρ_derived`
before compressing the Sock Shop verification pass; `ρ_independent` is the
coefficient the paper actually needs.

**Exp. 3 is a single-system result on the independent side.** 5 services, 122
pairs. That was true before D-16 and D-16 only made it explicit, but it caps
what Gate 2 can conclude and it should be written that way from the start rather
than discovered at review.

**Gate 2 can fail.** If pair-level ρ < 0.4, the proposal's instruction stands:
diagnose before writing — tokenization, weights, or entity-extraction quality.
Day 15 is the budget for that, and it is now the only slack left.

**Three weeks was already optimistic; four is the current projection.** The
proposal said this produces a first draft, not a submission, and that remains
true. Budget a further week for revision.

---

## 7. Bringing the paper text in line

Corrections established in `DECISIONS.md` that the manuscript must absorb:

- **Sec. 7** — S1 is **2,619** OpenAPI files, not 1,737 (D-12).
- **Sec. 7** — the "400–600 clean services (≥ 300 from S1)" target is
  superseded: 2,206 and 1,014 (D-12).
- **Sec. 6 / RQ2** — report the mask's justification **per service (68.4%)**, not
  as a pair-weighted percentage (D-13, and the caveat at the top of
  `RESULTS.md`).
- **Sec. 6 / RQ2** — where a pair-weighted number is quoted it is now
  **56.87% (primary)** beside 90.58% (sensitivity), never 90.58% alone (D-17).
- **Sec. 6** — the admin-endpoint list is 12 entries, not 6, and is matched on
  the whole path (D-07).
- **Sec. 5 / benchmarks** — Sock Shop is **122** within-service pairs, not 123;
  the earlier figure counted `payment`'s `/health`, which D-07 strips (D-16).
- **Sec. 5 / Exp. 3** — Train Ticket's specs are **generated from source**;
  report `ρ_independent` and `ρ_derived` separately and never pooled, and state
  that the independent condition rests on Sock Shop alone (D-16).
- **Sec. 4 / corpus** — every analysis is reported primary (≤ 200 operations) and
  sensitivity (full corpus), with the scope justification, not a compute one
  (D-17).
- **Limitations** — the mask statistics describe `specs/clean/` while the mask
  runs on `specs/clean3/`; f4 is ~5 points optimistic on the 144 converted 2.0
  services (D-14).
- **Limitations** — the corpus count of 2,206 is ~0.9% high pending F-02.
- **External validity** — S1 is *more* provider-concentrated than S2 (58.1% vs
  37.4%). Reusing a peer-reviewed corpus buys comparability, not diversity
  (D-12).

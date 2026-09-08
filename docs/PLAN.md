# Plan — from here to a first draft

*Re-baselined **Tue 2026-09-08**, after the experimental work completed.
Supersedes the 09-08 morning revision, which was a forward schedule for work
that has since been executed.*

**All five experiments have run. Both gates have been evaluated. What remains is
writing, four specific debts, and two open decisions.**

---

## 1. Status

| | Result | Artifact |
|---|---|---|
| **Gate 1** | ⚠ **MARGINAL** — δ +0.680, no clean separation | `results/gate1_verdict.csv` |
| **Exp. 1** corpus run | ✅ 2,206 services; ILSC_mean median **0.436** (primary) | `results/ilsc_scores.csv`, `ilsc_thresholds.csv` |
| **Exp. 2** perturbation | ✅ **H2 POSITIVE** — 20/20 monotonic, p < 1e-6 | `results/perturbation_*.csv`, Fig 3 |
| **Exp. 3 / Gate 2** | ✅ **PASS, reframed** — ρ_ind **0.433**, ρ_der **0.488** | `results/code_correlation_*.csv`, Figs 4–5 |
| **Exp. 4** baselines | ◐ **Half supported** — beats SIDC, not LoCmsg | `results/baselines_*.csv`, Fig 7 |
| **Exp. 5** sensitivity | ✅ **H3 HOLDS** — Kendall's W **0.9947** | `results/kendalls_w.csv`, `tau_sweep.csv`, Fig 6 |

42 result CSVs, 8 figures, 24 decisions, 4 flags. `python run_all.py` reproduces
every one of them from the two pinned corpus commits.

---

## 2. What is banked

**Corpus and curation** (empirical). 2,206 services from 6,757 across two pinned
sources; 2.0 → 3.x conversion verified operation-set-identical; D-02 strict
validation 97.5%; field- and pair-level availability studies; the D-17 oversized
cap with its primary/sensitivity protocol; benchmark corpus of 39 services.

**The metric** (metric track). Parser and tokenizer; embedding cache of 89,852
`T` and 54,701 description vectors; six similarity functions and the availability
mask; `ILSC_mean` / `_τ` / `_norm` with connected components; two null models;
quartile thresholds per population. **17/17 unit tests**, including the R2
regression that fails on the v2 design.

**The code dig** (empirical). Sock Shop by hand — 27 endpoints, every row
carrying a `file:line` reference. Train Ticket automated — **209 of 211
operations joined (99.1%)**, 0 unexplained empty entity sets.

**All five experiments**, above.

**The decision record.** D-01 … D-24 in `DECISIONS.md`, F-01 … F-04 in
`FLAGS.md`, and `docs/discordance.md`. Several of these are paper material in
their own right — the two rejected labelling approaches (D-03, D-04) especially,
because a rejection with a number attached is a methodological result.

---

## 3. Day by day — what each track delivered, and what it still owes

### 3a. The 09-08 schedule, marked off

The day numbers are the ones from the 09-08 morning plan, kept so the two
documents line up. **The owner columns are the proposal's division of labour
(Sec. 9) — whose track each item belongs to for the write-up and who owns what is
left — not a claim about who sat at the keyboard; the whole schedule was executed
in one push.**

✅ done · ◐ partial, see the note · ⬚ not done

| Day | Mohamed — metric track | | Tasneem — empirical track | |
|---|---|:-:|---|:-:|
| **1** | `embed.py`, `similarity.py`; **D3 decided (D-18)** | ✅ | Responsibility one-pagers, both systems | ◐ |
| **2** | 17/17 unit tests incl. R2; `ilsc.py` | ✅ | One-pagers cont.; extraction design | ✅ |
| **3** | Null models, global + provider (**D-21** flatness) | ✅ | Code dig — `user` (15 endpoints) | ✅ |
| **4** | **Gate 1** → MARGINAL (**D-24**) | ✅ | Code dig — `carts` + `catalogue` | ✅ |
| **5** | **Exp. 1** big run + quartile thresholds | ✅ | Code dig — `orders` + `payment` | ✅ |
| **6** | Inter-feature correlation, **Fig 9** | ✅ | Verification pass; `endpoint_entities.csv` | ✅ |
| **7** | `inject.py` + monotonicity/contrast checker | ✅ | **Train Ticket automated extraction** (209/211) | ✅ |
| **8** | **Exp. 2** perturbation run, **Fig 3** | ✅ | TT verification, 10 endpoints; go/no-go on ρ_derived | ✅ |
| **9** | **Exp. 4** — SIDC + LoCmsg implemented | ✅ | Reliability check — **verification done, blind figure still owed** | ◐ |
| **10** | Exp. 4 baselines under perturbation, **Fig 7** | ✅ | **Figures restyled to one palette** (`src/figstyle.py`) | ✅ |
| **11** | **Exp. 3** pair-level ρ, both conditions | ✅ | Replication package + `docs/replication.md` | ✅ |
| **12** | Exp. 3 service-level ρ; discordance; **Gate 2** | ✅ | Fresh-clone test — **structural done, end-to-end still owed** | ◐ |
| **13** | **Exp. 5** weights, Kendall's W, **Fig 6** | ✅ | **Threats to Validity** (`docs/threats_to_validity.md`) | ✅ |
| **14** | Exp. 5 τ sweep ✅ · **`DROP_VERSION_TOKENS` (D-15)** ✅ | ✅ | **Experimental Setup + dataset** (`docs/experimental_setup.md`) | ✅ |

**Metric track: 14 of 14 days complete.** The `DROP_VERSION_TOKENS` sweep closes
the last gap, so Exp. 5 is now a **three-knob** sensitivity analysis as the
proposal specifies.

**Empirical track: 12 of 14 complete, 2 partial.** Everything experimental
landed; entity coverage is 211/211; the figures share one validated palette; the
package is documented and structurally verified; both writing sections are
drafted. What remains is **only** the two halves of the reliability and
fresh-clone checks that cannot be self-administered (§3b).

**Debt 3 is closed.** The two non-Java Train Ticket services were dug out by
hand: `ts-avatar-service` (Flask + OpenCV, no persistence) and `ts-news-service`
(Go, returns a hardcoded literal with its MongoDB path commented out). Both
empty entity sets are **correct**, not gaps.

**The two ◐ entries, stated plainly:**

- **Day 1, one-pagers.** Sock Shop's were written from the repositories and are
  sound. Train Ticket's were written from the **specification surface**, not the
  FudanSELab *Service Guide* which could not be retrieved. That makes them a
  restatement of one side of the Exp. 3 correlation, so they are adequate for
  orientation but **must not** guide the entity extraction (**F-03**).
- **Day 9, reliability.** The Train Ticket extractor was **verified** against its
  sources — all 10 sampled endpoints re-derived from the Java, 10/10 exact
  agreement — and that verification caught a real bug (below). But the annotator
  could see the automated column, so it is *verification*, not a blind
  inter-annotator figure: reliable at catching entities claimed but not present,
  weaker at catching entities missed. `src/entity_extract.py --score` now prints
  that distinction itself. Sock Shop's sheet stays blank.
- **Day 12, fresh clone.** Structurally verified: 22/22 scripts present, 24/24
  modules import with no corpus, 17/17 tests pass from the clean tree. The
  **end-to-end data run** from a fresh clone has not been done, and that is the
  check the proposal actually asks for — see `docs/replication.md`.

**What the verification pass earned.** Entity names were scoped by the
*controller's* imports, but a controller often imports one entity while the
service it delegates to imports the whole shared module — `BasicController`
imports `entity.Travel` while `BasicServiceImpl` imports `entity.*` and touches
`TravelResult`, `TrainType` and `Route`. All three were being discarded. Fixing
it moved entities per endpoint **1.24 → 1.70**, services with code-side variance
**27 → 29**, and distinct `Sim_code` values **12 → 16**. Gate 2 is robust to the
change: ρ_derived **0.4876 → 0.4863** on a materially better variable, and
service-level ρ improved 0.449 → 0.513.

### 3b. The four debts

Two of the four are closed. What is left of the other two is precisely the part
that **cannot be self-administered**.

| # | Debt | Owner | Status |
|---|---|---|---|
| **1** | Inter-annotator agreement | **Tasneem** | ◐ **Train Ticket verified** (10/10 against source, and it caught a real bug). Still owed: a **blind** pass — the last column hidden, by a reader who did not build the extractor — and **Sock Shop entirely**, where the sets were derived by one reader and a second pass by the same reader measures memory. ~1 h each. |
| **2** | `DROP_VERSION_TOKENS` (D-15) sweep | **Mohamed** | ✅ **Closed.** Exp. 5 is now three knobs. |
| **3** | Two non-Java Train Ticket services | **Tasneem** | ✅ **Closed.** Both dug out by hand; both empty sets are correct. Coverage 211/211. |
| **4** | One figure palette; fresh-clone test | **Tasneem** | ◐ **Palette closed** (`src/figstyle.py`, validated). Still owed: the **end-to-end data run** from a fresh clone, ~1 h of wall time. Structural check passed. |

**The residue of debts 1 and 4 is the same shape.** Both are checks whose whole
value is that *someone other than the author* performs them: a blind annotator
for the agreement figure, and a clean machine for the reproduction. Doing either
oneself produces a number that looks like evidence and is not. They stay open,
and the paper describes the study as single-annotator until debt 1 is paid.

### 3c. The writing schedule

Day numbers are working days from tomorrow. Both halves run in parallel; the
proposal's own division of labour is kept.

| Day | Mohamed — theory half | Tasneem — empirical half | Output |
|---|---|---|---|
| **1** | ✅ `DROP_VERSION_TOKENS` swept; **Sec. 6 drafted** (`docs/metric_definition.md`) | ◐ **Train Ticket verified** 10/10; blind pass + Sock Shop still owed | agreement numbers |
| **2** | ✅ Sec. 6 covers the null models, D-18, D-21 and why `ILSC_norm` cannot reorder | ✅ **Sec. 7 drafted** (`docs/experimental_setup.md`) | Setup draft |
| **3** | Exp. 1 + Exp. 5 results, incl. the `f1_only` ρ = 0.837 discussion | Exp. 2 + Exp. 4 results | Results draft |
| **4** | Exp. 3 write-up, both conditions, cluster intervals, the D-16 inflation estimate | Discordance prose from `docs/discordance.md` | Gate 2 section |
| **5** | **Gate 1 as a construct-validity finding** (D-24) — the hardest section to write well | Threats to Validity, drafted jointly | — |
| **6** | Related work, positioning against SIDC/LoCmsg on *discriminating power*, not perturbation | Figures restyled to one palette, vector PDF (debt 4) | Figs final |
| **7** | Abstract, intro, contributions | Replication package + **fresh-clone test** (debt 4) | package |
| **8–9** | Full assembly and internal review | | **First draft** |
| **10** | *Slack* | *Slack* | — |

**Ten working days to a first draft**, against the six the proposal budgeted for
writing. The extra four are debts 1–4 and the fact that three results need
careful framing rather than transcription (§5).

---

## 4. Decisions still open

| # | Decision | Owner | Status |
|---|---|---|---|
| **D1** | Provider cap — none / 50 / 30 / 20 per provider | Mohamed | **Open, and now cheap.** No longer blocking. |
| **F-02** | Should `norm_host()` collapse `api.`/`www.` to the registrable domain? | Mohamed | **Open.** Affects the headline corpus count. |
| ~~D2~~, ~~D3~~, ~~D-14~~ | | | resolved by D-17, D-18, and a stated position |

**D1 has changed character and should be closed quickly.** It was listed as
blocking Exp. 1; Exp. 1 has now run without it, so the live question is narrower:
*do the published quartile thresholds change under a provider cap?* AWS, Google
and Azure hold **46.8%** of the corpus, so the thresholds are drawn from a
hyperscaler-heavy sample. With the engine built this is a **one-minute re-run**
of `src/ilsc.py` over a capped population, not a design decision. It should be
answered with a number before the thresholds are written up — if they move, the
paper must say which population produced them; if they do not, that is a
robustness result worth one sentence.

**F-02 costs 0.9% on the corpus count** (2,206 is that much high) and 0.31% of
pairs in the primary corpus. It affects a number that appears in the abstract, so
it needs deciding before the dataset section is final — Day 2.

---

## 5. Three results need framing, not transcription

These are the sections most likely to be written badly, and each is a place where
the honest version is more defensible than the hoped-for one.

**Gate 1 is not a pass, and the write-up must not imply it was.** Cliff's δ
+0.680 with no clean separation; the verdict turns entirely on Xero Payroll AU.
No weight scheme rescues it and Sec. 10's own suggested remedy makes separation
*worse*. Exp. 5 then showed why: no weighting moves any ranking materially
(W = 0.9947), so C1 was never rescuable by tuning. The finding is that **ILSC
measures resource-level, not capability-level, cohesion** — a service can be one
business capability spread across ten lexically unrelated resources. That is a
construct-validity result and belongs in Sec. 6 and in Threats, not buried.

**Exp. 4's superiority claim is only half available.** ILSC's foreign-vs-control
gap beats SIDC's, raw and standardised, and it discriminates on 20/20 services
against SIDC's 16/20. It **does not beat LoCmsg's**. The paper must say so. The
defensible claim is about **discriminating power**: ILSC saturates for **0.0%**
of 2,136 services against SIDC's 35.8% and LoCmsg's 77.0%, and LoCmsg's corpus
IQR is **exactly 0.0000** — at least half the corpus scores identically. A metric
that cannot rank unperturbed services but moves when foreign operations arrive is
detecting an intrusion, not measuring cohesion. That argument is strong; the
perturbation-gap argument is not, and substituting one for the other is the
temptation to avoid.

**Gate 2 passes on a threshold its own confidence interval straddles.**
ρ_independent = 0.433, but the cluster bootstrap — which resamples *services*,
the real independent unit — gives **[0.318, 0.643]**. Only 2 of 4 Sock Shop
services have any code-side variance (F-04). Report the cluster interval, report
that the primary condition cannot be said to clear 0.4 with confidence, and let
ρ_derived (0.488, [0.380, 0.584], 27 services with variance) carry the weight it
has earned — while stating that it is the circular condition D-16 quarantined.

**One thing that went better than expected, and is worth its own paragraph:** the
derivation-inflation estimate is **+0.054**. D-16 predicted the direction and got
it, but the magnitude is small — spec–code derivation inflates this correlation
by about five points, not enough to manufacture a finding. That is a result a
single-system design could not have produced, and it is the return on D-16's
quarantine.

---

## 6. Risks now

**The single-point-of-failure risk is gone.** The engine existed as a risk for
six days and no longer does.

**The remaining risk is writing quality, not results.** Three sections (§5) are
easy to write in a way a reviewer will attack: claiming Gate 1 passed, claiming
baseline superiority ILSC does not have, or quoting ρ_independent as a point
estimate. Each is already documented in `DECISIONS.md` with the honest version;
the risk is that the manuscript drifts from the decision log.

**Debt 1 needs a second person and nothing else can substitute.** If no second
annotator is available, the paper must state that entity extraction is
single-annotator with no reliability figure. That is a real weakness and it is
better stated than concealed, but it is worth an hour to avoid.

**`Sim_code` biases ρ downward** by matching entity names exactly —
`Assurance` and `AssuranceType` score 0.00 (`discordance.md` §3). The reported
coefficients are conservative in that specific respect. **Do not "fix" this
now**: changing `Sim_code` after seeing ρ has to be declared, and any change must
apply identically to both systems or the D-16 comparison breaks.

**Three weeks produced the experiments, not the paper.** The proposal said this
work yields a first draft, not a submission. Ten more working days gets the
draft; budget a further week for revision.

---

## 7. Bringing the paper text in line

Corrections established in `DECISIONS.md` that the manuscript must absorb.

**Corpus and dataset**

- **Sec. 7** — S1 is **2,619** OpenAPI files, not 1,737 (D-12).
- **Sec. 7** — the "400–600 clean services (≥ 300 from S1)" target is superseded:
  **2,206** and **1,014** (D-12).
- **Sec. 4** — every analysis is reported primary (≤ 200 operations) and
  sensitivity (full corpus), justified by **scope, not compute** (D-17).
- **External validity** — S1 is *more* provider-concentrated than S2 (58.1% vs
  37.4%). Reusing a peer-reviewed corpus buys comparability, not diversity (D-12).
- **Thresholds** — S1-only quartiles are the Bogner-comparable ones; the pooled
  figures are not. **S1 scores ~0.05 above S2 at every quartile**, so any quoted
  threshold must name its population.

**The metric**

- **Sec. 6 / RQ2** — quote the mask's justification **per service (68.4%)**, not
  pair-weighted (D-13). Where a pair-weighted figure is used it is **56.87%
  (primary)** beside 90.58% (sensitivity), never 90.58% alone (D-17).
- **Sec. 6** — the admin-endpoint list is 12 entries, matched on the whole path
  (D-07).
- **Sec. 6** — the domain-restricted null model is **provider-restricted**
  (D-18), and is a *conservative approximation* of the intended one.
- **Sec. 6** — `ILSC_norm` is an affine rescaling of `ILSC_mean` with constant
  coefficients (D-21), so it **cannot reorder services** and is not independent
  evidence.
- **Sec. 6** — a present-but-empty feature set is *unavailable*, not zero (D-19);
  cosine is clamped to [0,1], which fires on **2.25%** of values (D-20).

**Benchmarks and Exp. 3**

- **Sec. 5** — Sock Shop is **122** within-service pairs, not 123 (D-16).
- **Sec. 5** — Train Ticket's specs are **generated from source**; report
  ρ_independent and ρ_derived **separately, never pooled** (D-16).
- **Sec. 5** — Train Ticket is **not** a single-language system: two of its 34
  specified services are Python and Go (D-22).

**Limitations**

- Mask statistics describe `specs/clean/` while the mask runs on `specs/clean3/`;
  f4 is ~5 points optimistic on the 144 converted 2.0 services (D-14).
- The corpus count of 2,206 is ~0.9% high pending F-02.
- Entity extraction is **single-annotator with no reliability figure** until
  debt 1 is paid (F-03).
- `ρ_independent` rests on **one system and effectively two services** (D-16, F-04).
- `Sim_code` matches entity names exactly, biasing ρ downward (`discordance.md` §3).
- The sensitivity analysis covers **two knobs, not three**, until debt 2 is paid.

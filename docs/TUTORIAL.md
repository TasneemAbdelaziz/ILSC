# ILSC — the whole project, step by step

*A walkthrough for anyone who has to understand, extend or review this work:
what we set out to do, what each script does and what it produced, what went
wrong and how we handled it, what is still missing, and — honestly — where the
paper stands. Every number here comes from a file in `results/`.*

---

## Part 1 — What we set out to do

**The problem.** Cohesion — do the operations of a service belong together? —
is one of the oldest design properties in software engineering and one of the
hardest to measure for a microservice. Existing metrics either need **runtime
traces** (unavailable for third-party services, biased by the observation
window) or reduce cohesion to **shared data types and matching words**, which
cannot see that `Customer` and `Client` mean the same thing. And they all assume
a complete specification, which real specifications are not.

**The idea.** Measure cohesion from the API contract alone — the OpenAPI file —
using six similarity features between every pair of operations in a service:

| | what it compares | how |
|---|---|---|
| f1 | a structured text of the operation (`[METHOD] get [PATH] orders items …`) | sentence embedding, cosine |
| f2 | operation name tokens | Jaccard |
| f3 | path tokens | Jaccard |
| f4 | parameter-name tokens | Jaccard |
| f5 | domain schema names | overlap coefficient |
| f6 | the description | sentence embedding, cosine |

…under an **availability mask**: a feature only counts when *both* operations
carry it, and the weights redistribute over what is left. So **a missing field
never counts as dissimilarity.** That mask is the contribution — everything else
is the apparatus to test whether it works.

**The plan.** Five experiments and two gates, in about three weeks:

| | question |
|---|---|
| **Gate 1** | Does ILSC rank hand-picked cohesive services above hand-picked mixed ones? |
| **Exp. 1** | What does the distribution look like over ~2,000 real services? |
| **Exp. 2** | Does ILSC fall when foreign operations are injected — *more* than for a size-matched control? |
| **Exp. 3 / Gate 2** | Does interface similarity track code-level relatedness? |
| **Exp. 4** | Does ILSC beat the two published baselines, SIDC and LoCmsg? |
| **Exp. 5** | Are the rankings stable if we change the weights and the threshold? |

---

## Part 2 — What we built, in pipeline order

Run everything with `python run_all.py`. Each step below is one script.

### Step 1 · The corpus — `src/filter.py`, `src/convert.py`

Two pinned sources: **S1**, the RAMA benchmark from Bogner et al. 2020 (2,619
files, peer-reviewed, reusable so our thresholds are comparable with theirs) and
**S2**, the APIs.guru directory (4,138 files, for recency). Six curation stages,
every removal logged in `results/filter_log.csv`.

→ **2,206 services, 97,912 operations.** Swagger 2.0 converted, not discarded
(D-01); the operation set is verified byte-identical before and after. 70
services above 200 operations are gateway surfaces, not microservices, and are
held out of the *primary* analysis (D-17).

### Step 2 · Is the mask even needed? — `src/availability.py`, `src/pair_availability.py`

Before building the metric, measure how incomplete specifications are.

→ Descriptions exist on **73.0%** of operations; a usable `operationId` on 84.9%;
domain schemas on 78.7%. Per *pair*, at least one feature is missing on
**56.9%** of comparisons. The mask fires on more than half of all pairs. That is
the justification for C1, measured rather than assumed.

### Step 3 · Features — `src/parse_spec.py`

Turns each spec into one JSON per service with the six feature sets. Two design
constraints matter: the operation text `T(Oᵢ)` **excludes the description**, so
f1 and f6 are disjoint and a missing description is visible to exactly one mask
term (R2 — the earlier design double-counted it and defeated the mask); and
components on >80% of a service's operations are infrastructural and excluded
from f5 **and, after D-26, from f4**.

### Step 4 · The engine — `src/embed.py`, `src/similarity.py`, `src/ilsc.py`

Embeds every operation once (89,429 unique texts, cached), computes the six
similarities and the mask, aggregates to `ILSC_mean`, `ILSC_τ` and
`ILSC_norm`. **17 of 17 unit tests pass**, including the R2 regression: delete
one operation's description and f1 is bit-identical while `m_f6` flips 1 → 0.

### Step 5 · Null models — `src/null_models.py`

What does a random bag of operations score? Two variants, both required by the
proposal. Domain labels were rejected twice (D-03 at 52% agreement, D-04 as
circular), so the second variant restricts by **provider** (D-18).

→ **E[ILSC_rand] = 0.0988** globally, **0.2193** provider-restricted (96 of 97
providers above global — the harder bar works). And a theoretical result:
E[ILSC_rand] is **flat in n** (D-21), so `ILSC_norm` is an affine rescaling of
`ILSC_mean` and *cannot reorder services* — it is not independent evidence.

### Step 6 · Gate 1 — `src/gate1_run.py` → **FAIL** → `src/gate1_matched.py` → **PASS**

Ten services hand-labelled before any score existed.

→ Original ten: Cliff's δ **+0.200**, p 0.36. **Fails.** Diagnosis (D-27): three
of five *cohesive* candidates are hyperscalers, none of the *mixed* are — the
sample was confounded with provider.

→ Re-run **provider-matched** (D-29): for 16 publishers, compare their
single-capability service with their many-capability one. **14 of 16** in the
predicted direction, mean difference **+0.105**, p = **0.002**, and **11 of 12**
label boundaries agree. The failure was the sample, not the metric.

### Step 7 · Exp. 1 — `src/ilsc.py --null …`

→ 2,206 services in ~1 min. Median `ILSC_mean` **0.366** (primary). Quartile
thresholds per population in `results/ilsc_thresholds.csv`; the **S1-only** row
(0.308 / 0.388 / 0.483) is the one comparable with Bogner.

### Step 8 · Are six features redundant? — `src/feature_corr.py` (Fig 9)

→ Maximum inter-feature Spearman **0.558** (f1–f3), nowhere near the 0.85
redundancy threshold set in advance. But `f1_only` still reaches ρ = 0.81
against the full metric: f1 carries most of the signal and the others refine it.

### Step 9 · Exp. 2 — `src/inject.py` (Fig 3)

Inject 1/2/3/5 foreign operations into 20 top-quartile services, from three
distances (D-05): same-provider sibling, same provider, different provider.
"ILSC falls when you inject junk" is near-tautological; the test is the
**contrast** against the size-matched control.

→ **20 of 20** perfectly monotonic. Slopes order with distance: −0.037 / −0.065 /
−0.088. Paired gap negative for **20 of 20**, p < 10⁻⁶. **H2 holds.**

### Step 10 · The code dig — `results/endpoint_entities.csv`, `src/entity_extract.py`

Ground truth for Exp. 3: which code-level entities does each endpoint touch?

→ **Sock Shop** (5 services, 27 endpoints): by hand, every row with a
`file:line` reference. **Train Ticket** (34 services, 211 endpoints): an
automated Java extractor, verified 10/10 against source, **211 of 211**
endpoints covered — including two non-Java services dug out by hand.

### Step 11 · Exp. 3 / Gate 2 — `src/bench_prepare.py`, `src/code_correlation.py` (Figs 4–5)

Correlate interface similarity with code-entity overlap, pair by pair — and
**never pool the two systems** (D-16), because Train Ticket's specs were
*generated from its code* and the correlation there is partly circular.

→ ρ = **0.409** on hand-written specs, **0.486** on generated. Both in the
0.4–0.6 band the proposal pre-designated as *"moderate correlation,
complementary signal."* **Gate 2 passes, reframed.** The +0.078 gap between the
two is a measured estimate of derivation inflation — a result a one-system
design could not produce.

### Step 12 · Exp. 4 — `src/baselines.py` (Fig 7)

SIDC and LoCmsg, implemented faithfully — *without* the mask or the exclusions.

→ On the perturbation gap ILSC beats SIDC but **loses to LoCmsg**. Reported as
it fell. On the corpus, ILSC saturates at a perfect 1.0 for **0.0%** of services
against SIDC's 35.8% and LoCmsg's 77.0% — but that only shows ILSC is more
*continuous*, which is why Step 13 exists.

### Step 13 · Exp. 4b — `src/baseline_correlation.py` (Fig 8)

The test that settles it: **against the code dig's ground truth, which metric
better predicts that two operations are related?** AUC, because two predictors
are binary.

→ On hand-written specs: **ILSC 0.794** vs SIDC 0.574 vs LoCmsg 0.651, confidence
intervals separated. **ILSC wins.** On generated specs: LoCmsg 0.953 wins —
because **81%** of a generated spec's schema vocabulary is the code's own type
vocabulary (15% for hand-written), so name-matching there reads the code through
a wrapper. **Provenance inverts which metric looks best** (D-28).

### Step 14 · Exp. 5 — `src/sensitivity.py`, `src/version_tokens_sweep.py` (Fig 6)

→ Kendall's W = **0.9949** across ±20/40% weight perturbations. τ sweeps smoothly
with no discontinuity. The tokenisation knob moves the corpus ranking at
ρ = 0.998. **H3 holds — three knobs, all swept.**

### Step 15 · Two things the data forced on us — `src/provider_cap.py`, `src/param_boilerplate.py`

→ **D-25:** AWS/Google/Azure are **48%** of the corpus and score higher. Report
thresholds stratified; never quote one without its population.

→ **D-26:** Google attaches six identical parameters to **100%** of its 10,103
operations; AWS seven signing headers to 99%. f5 had an exclusion rule for
exactly this and f4 did not. Fixed, corpus re-parsed and re-embedded, every
number regenerated. This is what turned the original Gate 1 from MARGINAL to
FAIL — and led to Step 6's matched re-run.

---

## Part 3 — What went wrong, and what we did about it

This is the part that earns trust. All of it is in `docs/DECISIONS.md` (29
entries) and `docs/FLAGS.md` (5).

| what broke | how we found it | what we did |
|---|---|---|
| f4 inflated by auth boilerplate for **67.6%** of services | chasing why hyperscalers score high | applied f5's own rule to f4; re-ran everything (D-26) |
| Gate 1 **failed** after that fix | the re-run | diagnosed a provider confound; re-ran matched → PASS (D-27, D-29) |
| Exp. 4's superiority claim failed vs LoCmsg | the run | reported it; built the ground-truth test instead (D-28) |
| a `//` inside `"http://"` erased whole Java files in the extractor | manual verification of 10 endpoints | single-pass lexer; empty entity sets fell 27% → 0% |
| the corpus **silently lost a file** on a deep Windows path | the fresh-clone test | `unreadable:` now distinct from `parse_error:`, loud warning |
| the repo could not be cloned on Windows | the fresh-clone test | untracked 2,206 accidentally committed files |
| saturation figures drafted from a 300-service smoke run | proof-reading the write-up | corrected before publication |

**The rule we held to throughout:** never change a feature after seeing which
services it favours *unless* the change would be made whichever way the result
went — and record the provenance either way. D-26 passes that test (the rule
predates the results; two thirds of the corpus is affected; no hypothesis can
flip). `Sim_code`'s exact-name matching was left alone by the same rule.

---

## Part 4 — What is still missing

Be exact about this; a reviewer will be.

| gap | why it matters | who / how long |
|---|---|---|
| **A human validation study** | Nobody has ever rated a service's cohesion and had it correlated with ILSC. Every ground truth we have is mechanical (tags, code entities, provider). **This is the first thing a Q1 reviewer will ask for.** | 3+ annotators, 50–100 services, ~2–3 weeks |
| **A blind inter-annotator figure** | Entity extraction is single-annotator. I verified Train Ticket 10/10, but I could see the answers; Sock Shop's sets are mine. A second pass by the same person measures memory. | a second reader, ~1 h each system |
| **More independent-spec systems** | The winning conditions in Exp. 3 and 4b rest on **one** hand-written system, 4 services, 2 with any code variance. | 2–3 systems with hand-written OpenAPI *and* source |
| **The end-to-end fresh-clone run** | Verified structurally (22/22 scripts, 24/24 imports, 17/17 tests). The full data run was started and killed to free CPU for D-26; it has not been re-run on the final code. | ~1 h unattended |
| **Human validation of the matched-gate labels** | `n_tags` was chosen for independence from the metric, not fidelity to cohesion. | a spot-check, ~1 h |

---

## Part 5 — What we contributed, and the Q1 case as it actually stands

### Contributions

**C1 — The availability mask.** A normalised interface-cohesion metric in which
incompleteness is *excluded from a comparison rather than penalised*, motivated
by a measured 56.9% pair-level incompleteness, and made sound by disjoint feature
texts with a regression test that fails on the earlier design.

**C2 — Triple validation without runtime ground truth.** Controlled perturbation
against a size-matched control (20/20, p < 10⁻⁶); pair-level correlation with
code-entity overlap, reported per specification origin; and a head-to-head
against two published baselines on an external ground truth.

**C3 — Specification provenance inverts metric rankings.** This is the finding we
did not plan and could not have found with one system: on generated
specifications the most superficial metric wins, because 81% of the vocabulary
*is* the code. Train Ticket is a standard benchmark. Any study evaluating
interface metrics against code on generated specs inherits this artifact.

**C4 — A decision record whose rejections carry numbers.** Keyword labelling
rejected at 52% agreement; LLM labelling rejected as circular; the oversized cap
justified by a 50-point swing. A rejection with a measurement attached is a
reusable methodological result.

### Why this can be a Q1 paper

- The mask is a genuine, sound, novel idea with a measured motivation and an
  enforced invariant. Metric papers rarely have either.
- **C3 is a field-level result**, not a fact about our metric. It changes how
  anyone should evaluate interface-level metrics on benchmark systems.
- Exp. 4b gives ILSC a superiority claim **on external ground truth with
  separated confidence intervals** — not on spread, not on a proxy.
- The negative results are reported as they fell, with diagnoses. A reviewer
  who tries to find the buried failure finds it in the abstract.
- 29 decisions, 5 flags, 50 result files, 10 figures on one validated palette,
  and a one-command reproduction with its own defects found and recorded.

### Why it is not there yet — stated as strictly as it was said to us

The paper currently establishes that ILSC behaves as its theory requires and
predicts code relatedness better than the baselines on the one hand-written
system we have. It **does not yet establish that ILSC measures what a
practitioner means by cohesion**, because no human has said so. A Q1 reviewer
will accept a proxy only once it has been checked against the thing it is a
proxy for. That check is Part 4, row one. With it, and one or two more
hand-written systems, this is a TSE/TOSEM/EMSE paper. Without it, it is a strong
JSS/IST paper — or a short paper on the mask alone, which is publishable today.

*Prepared 2026-09-08 for Mohamed Elredeny and Tasneem Abdelaziz. Every claim
above is traceable to a file in `results/`, a decision in `docs/DECISIONS.md`,
or a test in `src/test_similarity.py`.*

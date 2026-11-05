# ILSC — Master Record

**Everything built, everything measured, and everything still owed.**
One document, assembled 2026-09-09 at commit `a2e29bc` on branch
`metric-engine-and-experiments`.

Every number below was **recomputed from the artifacts in `results/`** for this
document, not transcribed from prose. Where a figure quoted in `README.md`,
`RESULTS.md` or `docs/abstract_and_intro.md` disagrees with its own artifact,
both appear and the disagreement is listed in §11.

| | |
|---|---|
| Scripts | 30 Python modules + 1 Node converter, 9,618 lines |
| Result artifacts | 50 CSV files |
| Figures | 10 vector PDFs |
| Decisions | D-01 … D-29 |
| Cross-track flags | F-01 … F-05 (3 resolved, 2 open) |
| Experiments | 5 planned + Exp. 4b + 2 gates |
| Corpus | 2,206 services · 97,912 operations · 616 providers |
| Benchmarks | 39 services · 238 operations · 916 within-service pairs |

**Contents**

1. [Frame — questions, hypotheses, contributions](#1-frame)
2. [The metric, as implemented](#2-the-metric-as-implemented)
3. [Everything built — module by module](#3-everything-built)
4. [Dataset — collection and preprocessing](#4-dataset)
5. [Availability studies (RQ2)](#5-availability-studies-rq2)
6. [The engine — parser, embeddings, null models](#6-the-engine)
7. [Experiments and gates — all results](#7-experiments-and-gates)
8. [Sensitivity and robustness](#8-sensitivity-and-robustness)
9. [Decision log — all 29](#9-decision-log)
10. [Independent verification](#10-independent-verification)
11. [Discrepancy register](#11-discrepancy-register)
12. [What is still owed](#12-what-is-still-owed)
13. [Reproduction](#13-reproduction)

---

## 1. Frame

### 1.1 Research questions

| ID | Question | Answered by | Status |
|---|---|---|---|
| **RQ1** | How to define a static, theoretically grounded semantic cohesion metric on interfaces alone? | Model definition (Sec. 6) | Answered by design |
| **RQ2** | How to compute pairwise similarity when spec fields are missing or auto-generated? | Availability mask + field-availability study | Answered and measured |
| **RQ3** | Does interface-level similarity reflect code-level relatedness — (a) per operation pair, (b) per service? | Exp. 3 | Partially — underpowered on the non-circular condition |
| **RQ4** | Is ILSC sensitive to semantic contamination specifically, rather than to size? | Exp. 2 | Yes *within* a service; **unanswered across services** (§10.1) |
| **RQ5** | Is the ranking stable across weights and τ? | Exp. 5 | Yes, decisively |

### 1.2 Hypotheses

| ID | Statement | Verdict | Evidence |
|---|---|---|---|
| **H1** | ILSC is a valid proxy for cohesion — interface similarity correlates with code-based structural relatedness at operation-pair level | **Not established** | ρ 0.409 on hand-written specs; cluster CI [0.318, 0.643] straddles the pre-registered 0.4 |
| **H2** | ILSC degrades significantly more under foreign-domain injection than under same-domain injection of equal size | **Supported** | 20/20 monotonic, 20/20 negative paired gap, p < 10⁻⁶ |
| **H3** | ILSC rankings are stable under reasonable variations of weights and τ | **Supported** | Kendall's *W* = 0.9949 |

### 1.3 Contributions as claimed

| ID | Claim | Standing |
|---|---|---|
| **C1** | Formal ILSC definition with availability-aware pairwise similarity **and null-model size normalisation** | Mask half is sound. **Size-normalisation half does not exist** — see §10.1 |
| **C2** | Triple validation without runtime ground truth: perturbation, code correlation, baseline head-to-head | Two of three legs stand |
| **C3** | Open-source tool + quartile-calibrated thresholds — a green/yellow/orange/red verdict from a spec file alone | **Blocked** by the size dependence (§10.1) |

---

## 2. The metric, as implemented

### 2.1 Operation representation

```
T(Oi) = [METHOD] m [NAME] n [PATH] p [PARAMS] par [SCHEMA] s
```

The description is **deliberately excluded** from `T(Oi)` and enters only through
f6 (revision R2). Rationale: in the earlier design a missing description changed
the f1 *input text* while the mask still reported f1 as available — defeating the
mask, which is the central theoretical claim. Enforced by
`test_r2_description_isolation`: deleting one operation's description leaves f1
bit-identical at 0.662798 while `m_f6` flips 1 → 0 and `Sim` still computes.

### 2.2 The six features

| | Content | Similarity | Availability |
|---|---|---|---|
| **f1** | SBERT of `T(Oi)` — no description | cosine, clamped [0,1] | always |
| **f2** | operationId tokens | Jaccard | masked |
| **f3** | normalised path tokens | Jaccard | masked |
| **f4** | parameter-name tokens | Jaccard | masked |
| **f5** | domain schema names | **overlap coefficient** | masked |
| **f6** | SBERT of the description | cosine, clamped [0,1] | masked |
| **f7** | co-usage | — | reserved, mask ≡ 0 |

f5 uses the overlap coefficient `|A∩B| / min(|A|,|B|)` because any shared domain
structure implies a relationship; a subset scores 1.0. That choice is what makes
generic-schema exclusion necessary — an infrastructural type on every operation
would saturate it.

f7 is reserved with a permanently zero mask: a dynamic-phase hook that makes this
Phase 1 of a programme rather than a standalone study. `test_f7_is_not_in_the_aggregation`
asserts the weight vector has exactly six entries.

### 2.3 Aggregation

```
Sim(Oi,Oj) = Σk ( wk · m_ijk · simk ) / Σk ( wk · m_ijk )     m_ijk = 1 iff BOTH carry k

ILSC_mean(S) = (2 / n(n−1)) · Σ_{i<j} Sim(Oi,Oj)
ILSC_τ(S)    = |{(i,j) : Sim ≥ τ}| / (n(n−1)/2)               default τ = 0.50
ILSC_norm(S) = (ILSC_mean − E[ILSC_rand]) / (1 − E[ILSC_rand]) reported unclipped
```

The denominator is the weight **actually available**, not the total weight, so
absence is excluded from the comparison rather than counted against it. This is
contribution C1.

### 2.4 Exclusion rules, applied per service

| Rule | Applies to | Effect measured |
|---|---|---|
| Generic schema list (`Error`, `Pagination`, `Status`, …) | f5 | 835 hits removed |
| Component on **> 80%** of a service's operations | f5 **and f4** (D-26) | 3,418 frequent schemas removed; the f4 rule touches **1,444 of 2,136 services (67.6%)** |
| 12 administrative paths, whole-path match (D-07) | corpus-wide | 62 endpoints, 48 services — `/orders/{id}/status` survives, a bare `/status` does not |
| Empty token set ⇒ **unavailable**, not zero (D-19) | all set features | < 0.6% of operations on the worst feature |
| Cosine clamped to [0,1] (D-20) | f1, f6 | fires on **2.25%** of values |
| operationId must not be a code-generator signature (D-08, D-23) | f2 | path baked into name, `usingGET` suffix, `_1` disambiguator, sanitised verb-prefix forms |

### 2.5 Pinned parameters

| Parameter | Value | Swept? |
|---|---|---|
| Weights | 1/6 each, uniform | ✅ Exp. 5, *W* = 0.9949 |
| τ | 0.50 (grid 0.30–0.70) | ✅ smooth, no discontinuity |
| `DROP_VERSION_TOKENS` | `True` | ✅ ρ = 0.9978 corpus-wide |
| Embedding model | `all-MiniLM-L6-v2` | pinned |
| Frequent-component ratio | > 0.80 of a service's operations | not swept |
| Oversized cap | 200 operations | primary + sensitivity both reported |
| Minimum operations | 3 | — |
| Stopwords | `get, post, api, v1, v2` | — |
| Null-model pair samples | 400,000 | — |
| Bootstrap resamples | 2,000 | — |
| Perturbation levels × draws | 0,1,2,3,5 × 10 | — |
| Seed | 42 | — |

---

## 3. Everything built

### 3.1 Empirical track

| Module | Lines | Produces |
|---|--:|---|
| `src/filter.py` | 575 | `manifest.csv` (2,206), `filter_log.csv` (4,551), `specs/clean/`, `specs/clean3/` |
| `src/convert.py` + `convert.js` | 144 + 62 | `convert_log.csv` (144), `convert_verify.csv` (2,206) |
| `src/validate_sample.py` | 125 | `strict_validation_sample.csv` (200) |
| `src/availability.py` | 586 | `availability.csv` (2,206), `availability_summary.csv` (64), `availability_skiplog.csv` (0), Fig 1 |
| `src/pair_availability.py` | 501 | `pair_availability.csv` (2,206), `pair_availability_summary.csv` (72), `pair_maskfire_distribution.csv` (24), Fig 2 |
| `src/oversized.py` | 217 | `oversized_thresholds.csv` (10) — the D-17 primary/sensitivity split |
| `src/domain_label.py` | 177 | `manifest_labelled.csv` — **rejected** (D-03), kept as evidence, inert downstream |
| `src/benchmark_prep.py` | 305 | `benchmark_manifest.csv` (39), `benchmark_split_log.csv` (34) |
| `src/entity_extract.py` | 596 | `endpoint_entities_trainticket.csv` (262), `entity_agreement_sample.csv` (10) |
| `src/gate1_select.py` | 171 | `gate1_candidates.csv` (10), `gate1_shortlist.csv` (80) |

### 3.2 Metric track

| Module | Lines | Produces |
|---|--:|---|
| `src/parse_spec.py` | 565 | `parsed/<service>.json` — per-operation features + `T(Oi)` |
| `src/embed.py` | 292 | embedding cache: 89,852 `T` vectors + 54,701 description vectors |
| `src/similarity.py` | 498 | the six features, the mask, pairwise `Sim`, per-service statistics |
| `src/ilsc.py` | 348 | `ilsc_scores.csv` (2,206), `ilsc_thresholds.csv` (20) |
| `src/null_models.py` | 300 | `null_model.csv` (578), `null_model_bysize.csv` (7) |
| `src/feature_corr.py` | 245 | `feature_correlation.csv` (36), Fig 9 |
| `src/inject.py` | 390 | `perturbation_raw.csv` (3,000), `perturbation_summary.csv` (20), Fig 3 |
| `src/bench_prepare.py` | 160 | benchmark convert → parse → embed (39 services) |
| `src/code_correlation.py` | 470 | `code_correlation_pairs.csv` (912), `code_correlation_summary.csv` (2), `discordance.csv` (102), Figs 4–5 |
| `src/baselines.py` | 443 | `baselines_corpus.csv` (2,136), `baselines_perturbation.csv` (3,000), `baselines_comparison.csv` (3), Fig 7 |
| `src/baseline_correlation.py` | 297 | `baseline_correlation.csv` (6), Fig 8 |
| `src/sensitivity.py` | 367 | `weight_sensitivity.csv` (2,136), `kendalls_w.csv` (33), `tau_sweep.csv` (9), Fig 6 |
| `src/version_tokens_sweep.py` | 188 | `version_tokens_sweep.csv` (2,136) |
| `src/provider_cap.py` | 149 | `provider_cap.csv` (6) — D-25 |
| `src/param_boilerplate.py` | 185 | `param_boilerplate.csv` (2,136) — F-05 evidence |
| `src/gate1_run.py` | 255 | `sanity_check.csv` (10), `gate1_verdict.csv` (10) |
| `src/gate1_matched.py` | 408 | `gate1_matched.csv` (16), `gate1_matched_grid.csv` (12), `gate1_matched_verdict.csv` (11), Fig 10 |
| `src/test_similarity.py` | 350 | **17/17 unit tests pass**, including the R2 regression |
| `src/figstyle.py`, `src/pool.py` | 112 + 137 | shared validated palette; operation pooling for null models |

### 3.3 Figures

| Figure | Shows |
|---|---|
| Fig 1 | Field availability — four panels, micro/macro × by-source/by-version |
| Fig 2 | Mask-fire distribution across services — the bimodality, not a mean |
| Fig 3 | Perturbation, three conditions × five levels |
| Fig 4 | Pair-level interface vs code scatter |
| Fig 5 | Service-level interface vs code scatter |
| Fig 6 | τ sweep on a twin axis (ILSC_τ and component count) |
| Fig 7 | Baseline perturbation comparison |
| Fig 8 | Baseline AUC head-to-head (Exp. 4b) |
| Fig 9 | Inter-feature Spearman matrix |
| Fig 10 | Gate 1 provider-matched paired differences |

---

## 4. Dataset

### 4.1 Sources, both pinned

| ID | Source | Commit | Files |
|---|---|---|--:|
| **S1** | RAMA threshold benchmark (Bogner et al. 2020), `restful-ma/thresholds` | `5b0b2a3322d3b2b7c0e0f2c0c0ad0e524e67bf82` | 2,619 |
| **S2** | APIs.guru `openapi-directory` | `f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49` | 4,138 |
| | | **Total in** | **6,757** |

S1 is reused for **comparability with Bogner, not for diversity** — it is the
*more* provider-concentrated of the two sources (§4.4). The proposal conflated
those two justifications; D-12 corrects it, and also corrects S1's size from the
proposal's stated 1,737 to the 2,619 present at the pinned commit.

### 4.2 Curation pipeline — six stages

| Stage | Removed | Reason |
|---|--:|---|
| a — parse | 49 | malformed file |
| a — structure | 184 | no `paths` or no `info` |
| b — RPC-shaped | 1 | every path identical |
| c — < 3 operations | 1,264 | too small for a pairwise metric |
| d — dedup within source | 1,199 | older version of the same API |
| e — dedup cross source | 1,854 | already present in S1 |
| | **4,551 removed** | every row logged with its reason in `filter_log.csv` |
| **Surviving** | **2,206** | |

**Swagger 2.0 is converted, not discarded (D-01).** Dropping it would bias toward
recently published APIs and would have eliminated the entire code-correlation
benchmark — every Sock Shop and Train Ticket spec is 2.0. 144 conversions with
`swagger2openapi@7.0.8`, **0 failures**, and **2,206/2,206 verified to have an
identical `(METHOD, path)` operation set** before and after. A conversion that
added or dropped an operation would silently move every pairwise count
downstream, so a mismatch is a hard failure rather than a warning.

**Two corpora are kept deliberately (D-11).**

- `specs/clean/` — as published. What the availability study measures; the
  2.0-vs-3.x contrast in its results is a finding and converting would erase it.
- `specs/clean3/` — uniform OpenAPI 3.x JSON. What the metric consumes.

They diverge for the 144 converted services, because conversion moves an
`in: body` parameter into `requestBody`: **f4 is 96.41% on `clean/` against
91.04% on `clean3/`**, so the reported pair-level f4 co-availability is about five
points optimistic for those services. Declared as a limitation rather than fixed
(D-14).

### 4.3 Composition of the survivors

| Property | Value |
|---|---|
| Services (S1 / S2) | **2,206** (1,014 / 1,192) |
| Operations | **97,912** |
| Operations per service | min 3 · median 16 · mean 44.4 · max 11,422 |
| Within-service pairs | 77,611,030 (full) · **1,828,978** (primary, ≤ 200 ops) |
| OpenAPI 3.x / Swagger 2.0 | 2,062 (93.5%) / 144 (6.5%) |
| Distinct providers | 616 |
| Admin endpoints stripped | 62 across 48 services |
| Strict validation (n = 200) | **195/200 = 97.5%** — S1 102/102 (100%), S2 93/98 (94.9%) |

Rejections in the validation sample: 4 schema-validation errors, 1 unresolvable
`$ref`.

**The version split is an artefact (D-10).** RAMA converted its inputs upstream,
so S1 is 100% 3.x by construction. S2 alone is 26.9% Swagger 2.0. The pooled
split must never be read as a statement about publishing practice.

### 4.4 Provider concentration — the main external-validity constraint

| | Services | Providers | AWS + Google + Azure |
|---|--:|--:|--:|
| S1 (RAMA) | 1,014 | 315 | **589 (58.1%)** |
| S2 (APIs.guru) | 1,192 | 460 | 444 (37.4%) |
| pooled | 2,206 | 616 | 1,033 (46.8%) |

The peer-reviewed anchor is the more concentrated source. This propagates into the
results: S1 scores about 0.05 above S2 at every ILSC_mean quartile, so a quoted
threshold must name its population.

### 4.5 The oversized cap (D-17)

Above ~200 operations a specification describes an API gateway or a whole platform
surface — Microsoft Graph (11,422), Datto PSA (2,958), Kubernetes (1,113), GitHub
v3 (845), Compute Engine (758), EC2 (718), Stripe (452) — not the
single-capability microservice ILSC is defined over. **Justification is scope, not
compute.** 200 sits at ≈ p96.8 of the size distribution (median 16, p95 136,
p97 208). Nothing is deleted; `manifest.csv` keeps all 2,206 rows and gains an
`oversized` flag.

| | services | operations | within-service pairs |
|---|--:|--:|--:|
| **PRIMARY** (≤ 200) | 2,136 | 57,420 | 1,828,978 |
| **SENSITIVITY** (full) | 2,206 | 97,912 | 77,611,030 |
| excluded | 70 (3.17%) | 40,492 | 75,782,052 (**97.6%**) |

**84.0% of all within-service pairs come from Microsoft Graph alone.** Every
operation-weighted ("micro") statistic on the full corpus is therefore close to a
statement about one specification. The cap does not trim the picture, it inverts
it:

| statistic (micro) | PRIMARY | SENSITIVITY | move |
|---|--:|--:|--:|
| mask-fire % | 56.87 | 90.58 | +33.71 |
| f2 co-availability % | 78.39 | 97.17 | +18.77 |
| f4 co-availability % | 81.29 | 92.34 | +11.05 |
| f5 co-availability % | 70.36 | 36.09 | **−34.28** |
| f6 co-availability % | 74.41 | 24.08 | **−50.33** |

**Per-service quartiles are almost unmoved.** Largest movement of any boundary
across all ten measures is **3.17 points** (f5 co-availability Q1); `operations`
Q3 32 → 35; mask-fire median 38.71 → 40.00; f2, f6, description rate and
operationId rate all move **0.00** (`oversized_thresholds.csv`). Service-level
statistics are robust to the cap; pair-weighted ones are not. **This is the
empirical case for the service-level framing.**

### 4.6 Benchmark systems (Exp. 3)

| System | `spec_origin` | Services | Operations | Within-service pairs | Role |
|---|---|--:|--:|--:|---|
| `sockshop` | hand-written | 5 (4 with pairs) | 27 | **122** | ρ_independent |
| `trainticket` | generated-from-source | 34 (32 with pairs) | 211 | **794** | ρ_derived |
| **Total** | | **39** | **238** | **916** | never pooled |

Per-service Sock Shop: user 15 ops / 105 pairs · carts 5 / 10 · catalogue 4 / 6 ·
orders 2 / 1 · payment 1 / 0 (after D-07 strips `payment`'s `/health`).

**The two are not interchangeable (D-16).** Sock Shop's specs are hand-written and
independent of its code. Train Ticket publishes none — the sole citable artifact
(Zenodo `10.5281/zenodo.21342161`, CC-BY-4.0) is Springfox-generated from the
controllers. Online Boutique cannot supply a third system: it is gRPC with no
OpenAPI at all, and `.proto` methods are not `(METHOD, path)` operations.
**ρ_independent therefore rests on one system.**

Train Ticket ships as one combined document (172 paths, 211 operations), split
into 34 per-service specs on the `ts-*-service` tag every operation carries, with
`definitions` pruned to each service's transitive `$ref` closure and the
`(METHOD, path)` multiset asserted unchanged. Measuring the combined document
would have produced C(211,2) = 22,155 fabricated cross-service pairs in place of
the 794 real ones.

**Corpus filters do not apply here (D-06)** — benchmarks are selected for the
code-correlation study, not sampled from a population.

**Known gap:** Sock Shop's five specs carry `spec_pin = UNPINNED` — no upstream
commit was recorded. Train Ticket is pinned by DOI + archive sha256.

**Train Ticket is not single-language.** `ts-avatar-service` is Python and
`ts-news-service` is Go; the rest are Java / Spring Boot. Both non-Java services
were extracted by hand.

---

## 5. Availability studies (RQ2)

Two layers. **(A) per-operation** availability is descriptive; **(B) pair-level
co-availability** is the actual RQ2 number, because the mask evaluates
`m_ij,k = 1` only when *both* operations of a within-service pair carry feature
`k`. Both measured on `specs/clean/` (2,206 services); manifest cross-check 0
mismatches; skiplog 0 rows.

### 5.1 (A) Per-operation availability — 97,912 operations

| Field | micro (op-weighted) | macro (per-service mean) | micro → macro |
|---|--:|--:|:--|
| **description** | 73.02 | 83.70 | **+10.7** |
| summary *(descriptive only, not a mask feature)* | 56.66 | 45.28 | **−11.4** |
| operationId | 88.43 | 85.40 | −3.0 |
| parameters | 91.09 | 89.28 | −1.8 |
| response_schema | 89.77 | 89.16 | −0.6 |
| any_schema | 92.00 | 91.11 | −0.9 |
| request_schema · body-eligible | 86.94 | 86.35 | −0.6 |
| request_schema · all operations | 36.84 | 38.07 | +1.2 |

**Finding 1 — the micro↔macro reversal.** description and summary move in
*opposite* directions between the two averages. A handful of mega-specs
under-document `description` yet over-document `summary`. A structural difference
in how large specs are documented, not noise. description is on 73.0% of
operations (micro) and 83.7% (macro) — plainly above 60%, so the mask's
justification does **not** rest on per-operation description scarcity.

**Finding 1b — the two corpora document differently.** description micro is
**82.5% in S1** but **67.8% in S2**; summary reverses, **41.2% in S1** against
**65.1% in S2**. Report per source; do not pool silently.

### 5.2 (B) Pair-level co-availability — 77,611,030 within-service pairs

The mask can fire only on f2, f4, f5, f6; f1 (embedding) and f3 (path) are always
available.

| Feature | micro (pooled) | macro (pooled) | micro S1 | micro S2 |
|---|--:|--:|--:|--:|
| f2 name (codegen, primary) | 97.16 | 83.01 | 88.77 | 97.48 |
| f4 parameters | 92.34 | 84.72 | 88.94 | 92.47 |
| **f5 schemas** (generic-excluded) | **36.09** | 73.98 | 73.65 | 34.71 |
| **f6 description** | **24.08** | 81.52 | 81.95 | 21.96 |

**Mask fires (≥ 1 of f2, f4, f5, f6 unavailable):**

| stratum | micro | macro |
|---|--:|--:|
| **pooled** | **90.59** | **49.62** |
| S1 | 44.19 | 43.91 |
| S2 | 92.28 | 54.49 |
| 2.0 | 98.91 | 77.31 |
| 3.x | 90.07 | 47.69 |

**Finding 2 — the distribution is bimodal, so the mean is the wrong summary.**

| | pooled | S1 | S2 | 2.0 | 3.x |
|---|--:|--:|--:|--:|--:|
| services with **0%** mask-fire | 31.55% | 34.81% | 28.78% | 11.81% | 32.93% |
| services with **100%** mask-fire | 32.32% | 27.71% | 36.24% | 59.72% | 30.41% |
| **the mask matters for** | **68.45%** | 65.19% | 71.23% | 88.19% | 67.07% |
| median mask-fire % | 40.18 | 31.60 | 65.58 | 100.00 | 34.65 |

**Finding 3 — S1 and S2 disagree enormously at micro level and barely at macro
level.** Mask-fire micro is 44.2% in S1 against 92.3% in S2; macro is 43.9%
against 54.5%. The micro gap is the mega-specs (S1 holds 46% of services but only
3.5% of pairs); the macro gap is the real, modest difference between corpora.

**f2 sensitivity band (D-08).** Reported under three definitions. Micro mask-fire
moves **90.17 – 93.41%** (3.24 pts) — the operationId "informativeness" choice
does not matter much pair-weighted. It *does* move the service-level claim
(68.4% → 81.3%), which is a Threats-to-Validity caveat, not a headline mover.

| f2 definition | co-avail micro | co-avail macro | mask-fire micro | mask-fire macro |
|---|--:|--:|--:|--:|
| `f2_nonempty` | 98.34 | 84.87 | 90.17 | 49.21 |
| `f2_codegen` **(primary)** | 97.16 | 83.01 | 90.59 | 49.62 |
| `f2_derived` | 70.10 | 59.93 | 93.41 | 63.03 |

### 5.3 Paper-ready takeaways (RQ2)

1. Pair-level, the mask materially affects **68.4% of services** — this, not the
   per-operation rate and not the pair-weighted micro, is the RQ2 justification.
2. It is driven by **f5 schemas** and **f6 description**; f2 and f4 are high.
3. The service distribution is **bimodal** → report "matters for X% of services",
   never a single mean.
4. Robust to the f2 definition at micro level (~3 pts); service-level moves ~13
   pts and is reported as a three-column band.
5. **Report per source.** Pooling hides a 48-point micro gap between S1 and S2.
6. The micro headline is **56.87% (primary)** against 90.58% full-corpus — quote
   the primary figure with the sensitivity figure beside it. *(But see §11: the
   metric engine's own output for the same quantity is 73.63%.)*

---

## 6. The engine

### 6.1 Parser and feature extraction

**2,206 services, 97,912 operations, 0 skipped.** Operation count matches
`manifest.csv` exactly; every service asserts its operation set equals
`filter.operations()`.

Per operation: `method`, `operation_id`, `path`, `param_names`, `schema_names`,
`description`, `summary`, plus derived `name_tokens` (f2), `path_tokens` (f3),
`param_tokens` (f4), `domain_schemas` (f5) and `T` (f1).

**Per-operation feature availability as the mask sees it:**

| Feature | operations | % |
|---|--:|--:|
| f2 name | 86,570 | 88.42 |
| f3 path | 97,325 | 99.40 |
| f4 parameters | 88,828 | 90.72 |
| f5 schemas (generic + >80% excluded) | 77,060 | 78.70 |
| f6 description | 71,493 | 73.02 |

Cross-validation against the Day 3 study is exact where it should be —
operationId 88.42 vs 88.43, description 73.02 vs 73.018 — and differs only where
D-14 predicts (f4, the converted-corpus effect).

**f5 exclusions:** 835 generic-list hits plus **3,418 per-service "frequent"
schemas** removed by the > 80% rule. f5 availability (78.7%) is well below mere
schema presence (`any_schema`, 92.0%) — the exclusion rules doing their job, and
why `any_schema` must never be read as f5.

**Two corrections made while building this:**

- **D-15** — the pinned stopwords `v1`/`v2` were dead: splitting letter/digit runs
  before stopword removal turns `v2` into `v` + `2`. Since nearly every Google
  path begins `/v1/`, this would have inflated f3 across the largest provider in
  the corpus. Caught by the ten-tricky-names eyeball test.
- A JSON-Pointer fix for refs that percent-encode `{`/`}` cut unresolved
  references from **1,437 to 12** and recovered f4/f5 for DigitalOcean and 16
  other services.

**Spot-check:** 5 random services re-verified against their source specs — 5/5
pass.

### 6.2 Embeddings and tests

One cache, built once: **89,852 unique `T` vectors** (of 97,912 operations) and
**54,701 unique description vectors** (of 71,493 operations that have one; 26,419
have none). `python src/embed.py --verify` re-checks the cache without
re-embedding and confirms all 2,206 services align.

**Unit tests: 17/17 pass**, including R2 — the one that matters most, which fails
on the previous design.

### 6.3 Null models

| Model | E[ILSC_rand] |
|---|--:|
| **global** (arbitrary bag of API operations), 400,000 pairs | **0.0988** (SE 0.000086) |
| **provider-restricted**, median over 97 estimable providers | **0.2193** |
| provider-restricted, range | 0.0917 – 0.5065 |

**96 of 97 providers sit above the global expectation.** The gap between the two
normalisations is itself the reportable finding: a service must clear a much
higher bar to look coherent *relative to its own provider* than relative to the
corpus at large.

**480 of 577 providers fall back to the global expectation**, marked in the
output: either fewer than 50 operations, or (103 of them) every operation inside a
single service, which leaves no cross-service pair to draw. Pairs drawn from the
same service are resampled, because leaving them in imports exactly the
within-service coherence the null exists to be free of.

**Provider replaces the specified *domain* restriction (D-18)** because no domain
labels survive: keyword labelling rejected at 52% agreement against a blind human
sample (D-03), LLM labelling rejected as circular and unpinnable (D-04). Provider
is coarser than a domain, so the restricted null is a **conservative**
approximation and is reported as one.

**E[ILSC_rand(n)] is flat in n (D-21).** 1,000 full draws at seven sizes:

| n | 3 | 5 | 10 | 25 | 50 | 100 | 200 |
|---|--:|--:|--:|--:|--:|--:|--:|
| E | 0.0996 | 0.1016 | 0.1015 | 0.1012 | 0.1016 | 0.1014 | 0.1012 |
| sd over draws | 0.0370 | 0.0274 | 0.0157 | 0.0091 | 0.0060 | 0.0042 | 0.0029 |

Spread across all sizes: **0.00203**. The pair-sample estimator gives 0.10111.

> **Consequence, and it constrains what may be claimed.** If E is constant then
> `ILSC_norm` is an **affine rescaling of `ILSC_mean` with constant
> coefficients**. It cannot reorder services — every rank-based result is
> identical on either — and it **must not be presented as independent evidence**.
> It also cannot remove the size dependence documented in §10.1.

---

## 7. Experiments and gates

### 7.1 Experiment 1 — the corpus run (RQ1, RQ2, C3)

2,206 services in 51 s.

| | PRIMARY (≤ 200 ops) | SENSITIVITY (full) |
|---|--:|--:|
| services | 2,136 | 2,206 |
| ILSC_mean, mean | 0.3794 | 0.3748 |
| ILSC_mean Q1 / median / Q3 | 0.2854 / **0.3658** / 0.4526 | 0.2806 / 0.3630 / 0.4487 |
| ILSC_mean min / max | 0.1248 / 0.8866 | 0.1248 / 0.8866 |
| ILSC_τ (τ = 0.50), mean | 0.2597 | 0.2532 |

**D-17's prediction holds.** The cap moved pair-weighted co-availability by up to
50 points; it moves `ILSC_mean`'s median by **0.003**.

**Quartile thresholds — the deliverable of C3.** The S1-only row is the one
comparable with Bogner; the pooled figures are not, because S2 is a different
population.

| population | n | min | Q1 | median | Q3 | max | mean |
|---|--:|--:|--:|--:|--:|--:|--:|
| primary, all | 2,136 | 0.1248 | 0.2854 | 0.3658 | 0.4526 | 0.8866 | 0.3794 |
| **primary, S1 only** | 991 | 0.1405 | **0.3083** | **0.3883** | **0.4834** | 0.8866 | 0.4049 |
| primary, S2 only | 1,145 | 0.1248 | 0.2722 | 0.3461 | 0.4299 | 0.8190 | 0.3573 |
| sensitivity, all | 2,206 | 0.1248 | 0.2806 | 0.3630 | 0.4487 | 0.8866 | 0.3748 |
| sensitivity, S1 only | 1,014 | 0.1405 | 0.3019 | 0.3853 | 0.4799 | 0.8866 | 0.4014 |

Also published for `ILSC_τ`, `ILSC_norm_global` and `ILSC_norm_provider` in
`ilsc_thresholds.csv` (20 rows).

**S1 scores consistently higher than S2** — about 0.05 at every quartile. RAMA's
corpus is not a neutral sample of APIs.guru; any threshold quoted in the paper
must say which population produced it.

**An unplanned face-validity check.** The single lowest-scoring service of all
2,206 is **NeutrinoAPI (0.1248)** — the Gate 1 candidate labelled *mixed* on the
strength of its author declaring six unrelated domains. The label was written
before any score existed. The top of the distribution is equally readable: small,
single-purpose APIs (import.io at 4 operations, 0.8866; Proxy API at 5, 0.8741).
*(§10.1 qualifies how much this check is worth.)*

**No service scores below chance.** `ILSC_norm_global` is positive for all 2,206.
`ILSC_norm_provider` is filled for 2,162; the remaining 44 belong to providers
with no estimable pool and are left blank rather than defaulted.

### 7.2 Inter-feature correlation (Fig 9)

930,936 pairs sampled across 2,136 services, capped per service so no single
specification dominates; pairwise-complete, so a masked feature is absent rather
than zero.

Spearman ρ:

| | f2 | f3 | f4 | f5 | f6 |
|---|--:|--:|--:|--:|--:|
| **f1** | 0.515 | **0.558** | 0.409 | 0.359 | 0.460 |
| **f2** | | 0.345 | 0.250 | 0.137 | 0.316 |
| **f3** | | | 0.292 | 0.242 | 0.280 |
| **f4** | | | | 0.194 | 0.276 |
| **f5** | | | | | 0.219 |

**No feature pair reaches |ρ| ≥ 0.85** — the maximum is f1–f3 at **0.558**. The
six features are not redundant, and the equal 1/6 weighting is not concealing a
duplicated signal. f1 correlates most with everything, which is expected: `T(Oi)`
is built from the same material f2–f5 measure discretely. f5 is the most
independent of the lexical features (ρ ≤ 0.24 against f2, f3, f4), which justifies
keeping it on a different similarity function.

Feature availability over sampled pairs: f1 100%, f3 98.9%, f2 80.4%, f6 77.1%,
f5 73.5%, f4 57.9%.

### 7.3 Experiment 2 — perturbation (H2, RQ4)

20 top-quartile services, at most 3 per provider, levels 0/1/2/3/5 × 10 draws × 3
conditions = 3,000 rows.

**Monotonicity: 20 of 20 services perfectly monotonic** under the treatment.

| condition (increasing semantic distance) | mean degradation slope per injected operation |
|---|--:|
| `same_service` (nearest sibling service, same provider) | −0.03505 |
| `same_provider` | −0.06543 |
| **`cross_provider` (treatment)** | **−0.08771** |

The three slopes **order exactly as semantic distance predicts** — a direct
validation of D-05's provider-proximity proxy: it does not merely label, it
graduates.

Paired slope gap (`cross_provider` − `same_provider`): mean **−0.02228**, median
−0.01315, **negative for 20 of 20 services**, exact sign-flip p **9.5 × 10⁻⁷**
over all 2²⁰ assignments.

**H2: POSITIVE.** The size-matched control is what makes this non-tautological —
injecting *anything* lowers a mean-similarity score, but injecting something
semantically further away lowers it measurably faster.

*Caveats found in review (§10.3): the 20 targets have a median of 5 operations
against a corpus median of 16, and the `same_service` control is missing 5 of 80
cells at level 5.*

### 7.4 The code dig

**Sock Shop, by hand.** 27 endpoints, one row each, every row carrying a
`file:line` reference.

**Train Ticket, automated (D-22).** **209 of the 211 spec operations join to a
code row (99.1%)**. Empty entity sets 19.1%: 32 are `/welcome` or `/hello`
endpoints that genuinely return a `String`, and 8 are in services with no entity
package and no repository — stateless orchestrators that own no data, for which an
empty set is the correct answer. **Genuinely unexplained: 0.** The two unjoined
operations belong to `ts-avatar-service` (Python) and `ts-news-service` (Go).

**The finding that matters — F-04:**

| | Sock Shop (ρ_independent) | Train Ticket (ρ_derived) |
|---|--:|--:|
| services with pairs | 4 | 32 |
| **services with any code-side variance** | **2** | **27** |
| within-service pairs | 122 | 794 |
| **distinct `Sim_code` values** | **5** | **12** |
| share of pairs at exactly 1.0 | 23.8% | 39.1% |

`carts` (10 pairs) and `orders` (1 pair) are **constant** — every endpoint touches
the same entity set, correctly — so they cannot contribute to a within-service
correlation at all. ρ_independent is therefore close to a single-service result on
`user`. **The condition the paper would most like to lean on is the weaker of the
two, and the condition quarantined for circularity is the better-powered one.**

### 7.5 Experiment 3 — code correlation (H1, RQ3, Gate 2)

906 of 916 within-service pairs joined; 2 operations had no code row. Spearman
throughout — `Sim_code` is a 5-to-16 level tied variable and Pearson would assume
more than it supports.

| | ρ_independent | ρ_derived |
|---|--:|--:|
| system | Sock Shop | Train Ticket |
| `spec_origin` | hand-written | generated from source |
| pairs / services | 122 / 4 | 790 / 31 |
| **services with code-side variance** | **2** | **29** |
| `Sim_code` levels (largest tie) | 5 (27.9%) | 16 (33.2%) |
| **Spearman ρ (pair level)** | **0.4086** | **0.4863** |
| p | 3.0 × 10⁻⁶ | 3.9 × 10⁻⁴⁸ |
| 95% CI, pair bootstrap | [0.243, 0.547] | [0.431, 0.542] |
| **95% CI, cluster bootstrap** | **[0.318, 0.643]** | **[0.387, 0.579]** |
| ρ, service level | 0.7379 (n = 4, uninterpretable) | 0.5131 (n = 31, p = 0.0032) |

**Gate 2: PASS under the reframing the proposal itself specifies.** Both
coefficients land in the 0.4–0.6 band, which Sec. 12 instructs be reported as
"moderate correlation, complementary signal".

**Quote the cluster-bootstrap interval, not the pair-bootstrap one.** Pairs inside
a service share operations and move together. **The cluster interval for
ρ_independent straddles the 0.4 threshold**, so the primary condition cannot be
said to clear Gate 2's bar with confidence.

**Derivation inflation: +0.0777** (0.4863 − 0.4086). Positive as D-16 predicts,
but **small** — specification–code derivation inflates this correlation by roughly
eight points, not by enough to manufacture a finding.

**The coefficients are conservative in one respect.** `Sim_code` matches entity
names exactly, so `Assurance` and `AssuranceType` score 0.00 despite being plainly
related. Every such case biases ρ **downward**. Recorded rather than fixed, because
changing `Sim_code` after seeing ρ has to be declared and must apply identically to
both systems.

**Discordance: 102 of 906 pairs (11.3%)** — 97 `interface_high_code_low` (all
Train Ticket), 5 `code_high_interface_low` (all Sock Shop). Two canonical cases:

- *Interface high, code zero* — `…/inside_payment/money` vs
  `…/inside_payment/payment` (interface 0.86, code 0.00): one path prefix, four of
  five shared path tokens, disjoint entities.
- *Code complete, interface low* — `GET /customers` vs `POST /register`
  (interface 0.12, code 1.00): both touch `{User}`, share no lexical signal at all
  (f2 = f3 = f5 = 0.00), and score above zero **only through f1**. The study's
  clearest single piece of evidence that the embedding feature is not redundant.

### 7.6 Experiment 4 — SIDC and LoCmsg baselines (C2)

Both baselines implemented **faithfully, which means without what ILSC adds** — no
availability mask, no generic-schema exclusion, no embeddings. Same parsed corpus
and same D-07 exclusions, so the comparison differs in *method*, not in *inputs*.

- **SIDC** (Perepletchikov 2007): share of operation pairs with ≥ 1 common data type.
- **LoCmsg** (Athanasopoulos 2015): share of pairs whose message terms are disjoint.
  Runs the opposite way — higher is worse — so `1 − LoCmsg` appears in comparisons.

**Corpus comparison — 2,136 services, primary population:**

| metric | mean | Q1 | median | Q3 | **IQR** | distinct values | **saturated at 1.0** |
|---|--:|--:|--:|--:|--:|--:|--:|
| ILSC | 0.3794 | 0.285 | 0.366 | 0.453 | **0.1671** | 2,015 | **0.0%** |
| SIDC | 0.5475 | 0.138 | 0.500 | 1.000 | 0.8623 | 709 | 35.8% |
| 1 − LoCmsg | 0.9162 | 1.000 | 1.000 | 1.000 | **0.0000** | 356 | 76.9% |

`LoCmsg`'s interquartile range is **exactly 0.0000**: at least half the corpus
receives an identical score. This is the quantitative form of the Gap 2 argument.

Spearman against ILSC: SIDC **+0.138**, 1 − LoCmsg **+0.324**. SIDC and ILSC are
close to unrelated — they measure different things.

**Perturbation comparison — all three metrics on the *same* injected operations:**

| metric | same_service | same_provider | cross_provider | **gap** | gap in corpus SD | services with negative gap | p |
|---|--:|--:|--:|--:|--:|--:|--:|
| **ILSC** | −0.0350 | −0.0654 | −0.0877 | **−0.0223** | **−0.179** | **20/20** | 9.5e−7 |
| SIDC | −0.0510 | −0.0527 | −0.0712 | −0.0185 | −0.045 | 13/20 | 4.4e−3 |
| LoCmsg | −0.0024 | −0.0086 | −0.0621 | **−0.0535** | **−0.256** | 19/20 | 8.6e−6 |

- **Against SIDC: supported.** ILSC's gap is larger raw and standardised, and ILSC
  discriminates on 20/20 services against SIDC's 13/20.
- **Against LoCmsg: NOT supported.** LoCmsg's gap is larger, raw and standardised.
  The superiority claim the proposal wanted is **not available** against this
  baseline, and is reported as it falls.

**The context, and it is not a rescue.** LoCmsg scores **exactly 0.000 for all 20
test services before any perturbation** (sd = 0.0000). It cannot rank them at all;
it can only fall once foreign operations arrive. A large degradation gap measured
from a saturated floor shows the metric *detects that something foreign was
added* — not that it measures how cohesive a service is.

**Where this leaves the head-to-head.** ILSC's demonstrated advantage over these
baselines is **discriminating power on unperturbed services**, not superior
perturbation sensitivity. That is narrower than the proposal anticipated and it is
what the data supports.

### 7.7 Experiment 4b — the ground-truth head-to-head

Exp. 4's fallback claim is contestable: ILSC is a mean of six continuous
similarities and the baselines are proportions over pair counts, so comparing
spreads shows ILSC is more *continuous*, not more *valid*. The test that settles it
asks: **against `Sim_code`, which metric better predicts that two operations are
related?** Both baselines are decomposed to the pair predicate their published
definition counts, on their own unfiltered inputs. **AUC is primary** — two of
three predictors are binary.

| condition | **ILSC** | SIDC_pair | LoCmsg_pair |
|---|--:|--:|--:|
| **independent** — Sock Shop, hand-written (122 pairs, 4 svc) | **0.794** [0.767, 0.825] | 0.574 [0.568, 0.588] | 0.651 [0.614, 0.684] |
| **derived** — Train Ticket, generated (790 pairs, 31 svc) | 0.739 [0.687, 0.802] | 0.917 [0.866, 0.963] | **0.953** [0.914, 0.991] |

Spearman vs `Sim_code`: independent — ILSC 0.409, SIDC −0.003, LoCmsg 0.284;
derived — ILSC 0.486, SIDC 0.573, LoCmsg 0.714.

**On hand-written specifications ILSC wins.** **On generated specifications ILSC
loses badly, and the reason is measurable:**

| | spec schema names that are also code entity names |
|---|--:|
| Train Ticket (Springfox-generated) | **29 of 36 = 81%** |
| Sock Shop (hand-written) | **3 of 20 = 15%** |

In a generated specification the schema vocabulary largely *is* the code's type
vocabulary — Springfox transliterates the Java types into the contract — so a
metric that matches schema names reads the code's identifiers through a thin
wrapper, and its accuracy against a code-derived ground truth is
near-tautological.

**This sharpens D-16 considerably.** Derivation does not merely inflate a
coefficient by +0.078 — it **inverts the ranking of the metrics**. Evaluate
interface-level metrics on generated specifications and the most superficial
metric wins, as an artifact of provenance. Train Ticket is a standard benchmark
whose specifications are code-derived; **that is a reusable warning for the field,
not only a fact about this study.**

*The interval arithmetic behind the independent row does not hold — see §10.2.*

### 7.8 Gate 1 — original: **FAIL**

| | cohesive | mixed |
|---|--:|--:|
| mean ILSC_mean | 0.3701 | 0.3432 |
| min (cohesive) / max (mixed) | 0.2058 | 0.4288 |

Cliff's δ **+0.200**, mean gap **+0.0269**, exact one-sided p **0.3611** over 252
label assignments, **no clean separation**.

**It did not always fail.** Before D-26 removed the f4 boilerplate inflation this
gate read MARGINAL (δ +0.680). The exclusion moved the *cohesive* candidates and
left the mixed ones almost untouched:

| id | expected | provider | before | after | Δ |
|---|---|---|--:|--:|--:|
| C2 | cohesive | **googleapis.com** | 0.5031 | 0.3781 | **−0.1250** |
| C3 | cohesive | **googleapis.com** | 0.4581 | 0.2998 | **−0.1583** |
| C1 | cohesive | xero.com | 0.2923 | 0.2058 | −0.0865 |
| C5 | cohesive | **azure.com** | 0.5272 | 0.4937 | −0.0335 |
| C4 | cohesive | mtaa-api.herokuapp.com | 0.4918 | 0.4730 | −0.0188 |
| M3 | mixed | paylocity.com | 0.3535 | 0.3267 | −0.0268 |
| M4 | mixed | yunbi.com | 0.4243 | 0.4288 | +0.0045 |
| M1, M2, M5 | mixed | — | — | — | **0.0000** |

**Three of the five *cohesive* candidates are hyperscaler services; none of the
five *mixed* ones is.** The candidate set is confounded with provider: hyperscalers
publish narrowly-scoped single-capability specifications as house style, which is
exactly the criterion the cohesive label used. **A meaningful part of the original
+0.680 was ILSC separating providers, not cohesion** (D-27).

**What Gate 1 actually yielded** was not a verdict but a discovery: it exposed the
large, provider-correlated signal sitting inside f4 (F-05 → D-26).

### 7.9 Gate 1 — provider-matched re-run (D-29): claimed **PASS**

For every provider that publishes **both** a single-capability and a
many-capability service, one of each is compared **within the provider**, so house
style, boilerplate and specification generator are identical on both sides. The
label is the author's own `tags` count. Which member of each side is taken is
decided by operation count, without looking at any score.

| primary cell (`tags ≥ 5`, `ops ≥ 5`, fixed in advance) | |
|---|--:|
| providers publishing both kinds | **16** |
| mean ILSC, single- vs many-capability | 0.4257 vs 0.3210 |
| mean within-provider difference | **+0.1047** |
| median difference | +0.1147 |
| positive differences | **14 of 16** |
| rank-biserial (paired) | +0.750 |
| Wilcoxon signed-rank, one-sided | p = **0.00056** |
| exact sign test, one-sided | p = **0.0021** |

**The whole grid, not the best cell** (`gate1_matched_grid.csv`):

| `tags ≥` | `ops ≥` | pairs | mean Δ | positive | sign p | |
|--:|--:|--:|--:|--:|--:|---|
| 3 | 3 | 20 | +0.1169 | 18/20 | 0.0002 | PASS |
| 3 | 5 | 17 | +0.1043 | 15/17 | 0.0012 | PASS |
| 3 | 10 | 9 | +0.1004 | 8/9 | 0.0195 | PASS |
| 4 | 3 | 19 | +0.1179 | 17/19 | 0.0004 | PASS |
| **4** | **5** | **16** | **+0.1047** | **14/16** | **0.0021** | **PASS** (primary) |
| 4 | 10 | 8 | +0.1008 | 7/8 | 0.0352 | PASS |
| 5 | 3 | 19 | +0.1179 | 17/19 | 0.0004 | PASS |
| 5 | 5 | 16 | +0.1047 | 14/16 | 0.0021 | PASS |
| 5 | 10 | 8 | +0.1008 | 7/8 | 0.0352 | PASS |
| 6 | 3 | 16 | +0.1025 | 14/16 | 0.0021 | PASS |
| 6 | 5 | 15 | +0.1013 | 13/15 | 0.0037 | PASS |
| 6 | 10 | 7 | +0.0929 | 6/7 | 0.0625 | FAIL |

**11 of 12 cells pass.** *(Note: rows for `tags ≥ 4` and `tags ≥ 5` are identical
triples, so the grid contains 9 distinct cells over heavily overlapping samples,
not 12 independent ones.)*

**The two reversals in the primary cell:**

| provider | single-capability | many-capability | Δ |
|---|---|---|--:|
| adyen.com | Fund API (0.285) | Management API (0.313) | −0.028 |
| xero.com | **Xero Payroll AU** (0.206) | Accounting (0.222) | −0.016 |

Xero Payroll AU is the construct-validity case: single-capability by business
purpose, lexically heterogeneous by resource. It covers roughly ten distinct
payroll resources and the lexical overlap between `employees` and `superfunds` is
genuinely zero. **No weighting rescues it** — Sec. 10's own suggested remedy
(upweight path + schema) makes separation *worse* (δ +0.600). This is the evidence
for the **resource-level vs capability-level** distinction that belongs in the
metric's definition, not only in Threats to Validity.

**⚠ This result does not survive size matching — see §10.1.**

---

## 8. Sensitivity and robustness

### 8.1 Weights (H3)

| | Kendall's *W* |
|---|--:|
| **±20/±40% perturbations only — the H3 test** | **0.994880** |
| all 29 configurations, incl. deliberately extreme schemes | 0.967099 |

Spearman against the pinned baseline, worst configurations first:

| configuration | ρ vs baseline | mean \|ΔILSC\| |
|---|--:|--:|
| `f1_only` (five features switched off) | 0.8083 | 0.2495 |
| `gate1_lexical` (f2, f3, f4 only) | 0.8389 | 0.0944 |
| `gate1_semantic` (f1, f5, f6 heavy) | 0.9574 | 0.0697 |
| `gate1_path_schema` (the proposal's suggested remedy) | 0.9656 | 0.0298 |
| **worst of the ±20/40% family** (`f3−40%`) | **0.9896** | 0.0135 |
| best of family (`f4+20%`) | 0.9995 | 0.0026 |

**H3 holds decisively.** No reasonable weight variation moves the ranking, and even
switching five of six features off preserves ρ ≥ 0.81. The equal 1/6 weighting is
defensible because **the choice barely matters**, not because it was optimised.

**The one number worth arguing about is `f1_only` at ρ = 0.8083.** f1 alone
recovers most of the ranking. The honest framing is **"f1 carries the largest share
of the signal and the remaining five refine it"**, not "six equally contributing
features".

### 8.2 τ

| τ | 0.30 | 0.35 | 0.40 | 0.45 | **0.50** | 0.55 | 0.60 | 0.65 | 0.70 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| mean ILSC_τ | 0.590 | 0.492 | 0.410 | 0.332 | **0.260** | 0.203 | 0.158 | 0.118 | 0.083 |
| median ILSC_τ | 0.571 | 0.441 | 0.333 | 0.264 | **0.186** | 0.133 | 0.092 | 0.059 | 0.033 |
| mean components | 1.58 | 2.05 | 2.73 | 3.79 | **5.19** | 7.12 | 9.52 | 12.33 | 15.38 |

Both curves are smooth — no threshold effect, no discontinuity. At the low end the
graph is nearly complete (almost every service is one connected blob, so ILSC_τ
discriminates little); at the high end it fragments. **τ = 0.50 sits mid-range on
both curves** — not because it optimises anything, but because it is where the
statistic still varies.

### 8.3 Tokenisation — `DROP_VERSION_TOKENS` (D-15)

This knob cannot be swept by reweighting: it changes the tokenizer, therefore
`T(Oi)`, therefore the **f1 embeddings**. The corpus was re-parsed and re-embedded
with the flag off and scored again.

| | whole primary corpus | the 74 services it touches |
|---|--:|--:|
| services affected | 74 of 2,136 (**3.5%**) | — |
| mean shift when flag turned off | +0.0010 | **+0.0272** |
| max single-service shift | — | **+0.1214** |
| Spearman | **0.9978** | — |
| Kendall's τ | 0.9888 | — |

**Negligible corpus-wide, real locally.** Turning the flag off *raises* scores,
because the letter/digit splitter turns `v3` into `v` + `3` and every versioned
path then shares the token `v` — the inflation D-15 exists to prevent. **The pinned
setting is the conservative one.**

Exp. 5 is therefore a **three-knob** sensitivity analysis: weights, τ, and
tokenisation.

### 8.4 Provider cap (D-25) — D1 resolved

Surviving services chosen by **seeded random draw, not by score**; 200 re-draws per
cap.

| cap | Q1 | median | Q3 | Δmedian | services kept | sampling sd |
|---|--:|--:|--:|--:|--:|--:|
| **none** | 0.2854 | **0.3658** | 0.4526 | — | 2,136 | — |
| 50 | 0.2619 | 0.3430 | 0.4347 | **−0.0227** | 1,250 | 0.0012 |
| 30 | 0.2589 | 0.3391 | 0.4283 | −0.0266 | 1,148 | 0.0014 |
| 20 | 0.2568 | 0.3360 | 0.4253 | −0.0298 | 1,073 | 0.0007 |
| 10 | 0.2537 | 0.3316 | 0.4150 | −0.0342 | 960 | 0.0006 |
| 5 | 0.2498 | 0.3244 | 0.4039 | **−0.0414** | 863 | 0.0018 |

**The thresholds move, and it is not noise.** **Decision (D-25): do not cap —
stratify and report.** Capping deletes data to hide an effect that is itself a
finding.

### 8.5 The hyperscaler effect and F-05 → D-26

Per-feature medians, hyperscalers minus everyone else (measured before D-26):

| f1 | f2 | f3 | **f4** | f5 | f6 |
|--:|--:|--:|--:|--:|--:|
| +0.127 | +0.182 | +0.309 | **+0.398** | +0.065 | −0.022 |

f4 dominated, and the reason was boilerplate. Google attaches `fields`,
`oauth_token`, `key`, `prettyPrint`, `quotaUser` and `alt` to **100%** of its
10,103 operations; AWS attaches seven `X-Amz-*` signing parameters to **99%** of
its 11,843; Azure `api-version` 94%, `subscriptionId` 76%, `resourceGroupName` 66%.
Under Jaccard every pair in such a service shared six or seven tokens before any
domain content was considered — median f4 **0.82** against **0.42** elsewhere.

**Sec. 6 already had the rule that would exclude them — it just did not apply it to
f4.** Nothing in "a schema on more than 80% of a service's operations carries no
domain signal" depends on it being a schema. **D-26 adopted the rule**, and the
corpus was re-parsed and re-embedded because `T(Oi)` carries the parameter tokens
and the f1 vectors move too.

| | pre-D-26 (as documented) | post-D-26 (current artifacts) |
|---|--:|--:|
| services with ≥ 1 boilerplate parameter | 1,444 of 2,136 (67.6%) | 1,444 (67.6%) |
| hyperscaler median gap | **+0.1340** | **+0.0578** |
| Cliff's δ | +0.609 | ≈0.31 |
| mean change in ILSC_mean from applying the rule | −0.0448 | n/a — already applied |

**Not only a hyperscaler problem.** The largest individual drops included
`reloadly.com` (−0.199, from `Accept`), `openbanking.org.uk` (−0.144, from
`If-Modified-Since`) and `walmart.com` (−0.143, from `WM_CONSUMER.*`).

⚠ `param_boilerplate.csv` now has **identical `ilsc_before` and `ilsc_after` for
all 2,136 rows** — because the rule is adopted, re-running the script finds nothing
left to drop. The pre-adoption figures (−0.0448, +0.1340 → +0.0715, 46.6% of the
gap closed) **can no longer be regenerated by `run_all.py`**. See §11.

---

## 9. Decision log

All 29 in `docs/DECISIONS.md`, one line each.

| # | Decision | Outcome |
|---|---|---|
| D-01 | Swagger 2.0 is converted, not discarded | 144 converted, 0 failures, operation sets verified |
| D-02 | Structural validation corpus-wide, strict validation on a sample | 97.5% strictly valid (n = 200) |
| D-03 | Keyword domain labelling | **REJECTED** — 52% agreement with a blind human sample |
| D-04 | LLM domain labelling | **REJECTED** — circular with the metric under test, unpinnable |
| D-05 | Provider proximity replaces domain labels | **ADOPTED** — validated by the three-level slope ordering |
| D-06 | Corpus filters do not apply to benchmark systems | benchmarks are selected, not sampled |
| D-07 | Administrative endpoints stripped | 12-entry whole-path list; 62 endpoints, 48 services |
| D-08 | f2 availability is a three-definition band, not a threshold | micro moves 3.24 pts, service-level 13 pts |
| D-09 | Cross-source dedup — S1 wins regardless of version | 1,854 removed |
| D-10 | S1 arrives pre-converted — `spec_version` is not as-published there | pooled version split is an artefact |
| D-11 | Two corpora: `clean/` as published, `clean3/` uniform | availability reads one, the metric the other |
| D-12 | Correction: S1 is 2,619 API descriptions, not 1,737 | proposal Sec. 7 superseded |
| D-13 | Dedup ties go to the stable channel, not filename sort order | Microsoft Graph beta → stable |
| D-14 | The parser reads the converted corpus, so f4 differs from Day 3's `parameters` | 96.41% vs 91.04%, declared |
| D-15 | Tokenisation order: stopwords before letter/digit splitting | prevents `v` inflation across Google |
| D-16 | Train Ticket enters as a labelled `generated-from-source` condition | never pooled with Sock Shop |
| D-17 | Oversized services capped at 200 operations, primary + sensitivity | 70 services hold 97.6% of pairs |
| D-18 | The domain-restricted null becomes provider-restricted | 0.0988 global vs 0.2193 provider median |
| D-19 | A feature whose set is empty is unavailable, not zero | < 0.6% of operations, worst feature |
| D-20 | Cosine similarity is clamped to [0,1] | fires on 2.25% of values |
| D-21 | E[ILSC_rand(n)] estimated from random pairs; flat in n | spread 0.00203 across n = 3…200 |
| D-22 | Train Ticket entity extraction: global vocabulary, import scoping, one delegation hop | 209/211 joined |
| D-23 | The code-generator test also catches the sanitised form of a baked-in path | f2 availability |
| D-24 | Gate 1 is MARGINAL, weights NOT changed, and C1 is the reason | superseded by D-27 |
| D-25 | D1 resolved: no provider cap; stratify and report | thresholds move up to 0.041 |
| D-26 | F-05 resolved: the f5 infrastructural-exclusion rule now applies to f4 | full re-parse + re-embed |
| D-27 | Gate 1 **FAILS** after D-26, and the earlier result was partly an artifact | supersedes D-24 |
| D-28 | Exp. 4b: specification provenance decides which metric wins | the field-level warning |
| D-29 | Gate 1 re-run as a provider-matched paired design: PASS | **contested — §10.1** |

### Cross-track flags

| # | Flag | Owner | Status |
|---|---|---|---|
| F-01 | D2 (oversized services) is urgent | metric lead | ✅ **RESOLVED** by D-17 |
| F-02 | Near-duplicate survivors escape the dedup key | metric lead | ⬜ **OPEN** — corpus count ≈0.9% high; 20 redundant services, 362,256 added pairs, of which GitHub v3 is 98.4% (and is `oversized`, so primary contamination is 0.31% of pairs) |
| F-03 | Train Ticket responsibility one-pagers derived from specs, not the wiki | empirical lead | ⚠ partially addressed — the agreement figure it demands is still not independent |
| F-04 | Sock Shop's code side has almost no variance | both | ⚠ **realised**, quantified, reported — 2 of 4 services have variance |
| F-05 | f5 excludes infrastructural schemas; f4 excludes nothing | both | ✅ **RESOLVED** by D-26 |

---

## 10. Independent verification

Recomputed from the artifacts on 2026-09-09, independently of the prose. Three
claims did not survive.

### 10.1 ⛔ ILSC is strongly size-dependent, and nothing in the paper says so

```
Spearman(ILSC_mean,        n_operations)  = -0.5505   p = 1.7e-169   n = 2,136
Spearman(ILSC_norm_global, n_operations)  = -0.5505   (identical)
Spearman(ILSC_tau,         n_operations)  = -0.5009   p = 4.8e-136

  ops   3-5    n= 380   median ILSC = 0.4695
  ops   6-10   n= 430   median ILSC = 0.4298
  ops  11-20   n= 485   median ILSC = 0.3810
  ops  21-50   n= 528   median ILSC = 0.3266
  ops  51-200  n= 313   median ILSC = 0.2664
```

`docs/threats_to_validity.md` §7 files "size dependence of the normalisation" under
**threats that did not materialise**, on the evidence that E[ILSC_rand(n)] is flat.
That is the wrong test, and it proves the opposite of what it is used for: **if the
null expectation is constant while ILSC_mean falls with n, then ILSC_norm is an
affine rescale that inherits the size dependence entirely** — confirmed by the
identical ρ above.

**Consequences.**

- **C1's "null-model size normalisation" is not a contribution.** There is no size
  normalisation in the metric.
- **C3 is blocked.** Published thresholds would grade a service largely on how many
  operations it declares — a practitioner could "improve" a service by splitting
  its specification. Thresholds must be published **stratified by size band**, or
  not at all.
- **RQ4 is half-answered.** Exp. 2 settles the within-service injection case. The
  same question one level up — does the corpus ranking track meaning or size? — was
  never asked.
- The **NeutrinoAPI face-validity anecdote** is weakened: the corpus minimum is
  produced by a metric that rewards smallness, on a service with many operations.

**Not all of the hyperscaler effect is size.** Stratifying by operation-count
quintile, the hyperscaler advantage persists at +0.058 to +0.099 within every
stratum (mean +0.070), so that finding survives — it is simply smaller than the
+0.134 the docs still quote (§11).

### 10.2 ⛔ The provider-matched Gate 1 (D-29) is explained by size alone

D-29 controls for provider but not for the one variable that differs
systematically between the two sides.

```
single-capability side: median   9 operations
many-capability  side: median  52 operations
single is SMALLER in 15 of 16 pairs   (median ratio 5.4x)

size-matched null - draw random corpus services at the same two sizes,
ignore capability entirely, 20,000 replicates:
  observed mean within-provider delta : +0.1047
  size-only null                      : +0.0908   95% [+0.0274, +0.1548]
  P(size-only null >= observed)        : 0.335

residual after subtracting the size expectation:
  mean residual +0.0180   positive in 10 of 16
  sign test p = 0.227     Wilcoxon p = 0.174     not significant
```

The reported p = 0.00056 tests the difference against **zero**. The relevant null
is not zero — it is what you get by pairing any small service against any large one
from the same provider. **Against that null the effect vanishes.** D-29's selection
rule cannot fix this, because a many-capability service has ≥ 5 author tags and is
therefore larger by construction.

**After this, the paper has no surviving construct-validity result**: the original
gate failed, the matched gate is confounded, the corpus face-validity check is a
single anecdote, and Exp. 3 is explicitly reframed as complementary signal rather
than validation.

### 10.3 ⛔ Exp. 4b's confidence interval is conditioned on the informative cluster

`src/baseline_correlation.py:118` resamples services with replacement and keeps a
draw only `if np.isfinite(a)`. For Sock Shop every unrelated pair lives in `user`,
so any draw missing `user` has no negatives, returns NaN, and is dropped.

```
Sock Shop ground truth, by service:
  user       85 related / 20 unrelated   <-- all negatives are here
  carts      10 related /  0 unrelated
  catalogue   6 related /  0 unrelated
  orders      1 related /  0 unrelated

their cluster bootstrap, re-run:
  CI = [0.7674, 0.8248]                 matches the paper exactly
  DISCARDED 644 of 2000 draws (32.2%)   every draw without `user`

the honest test - paired, within the only informative cluster:
  AUC   ILSC 0.766   SIDC 0.588   LoCmsg 0.631
  ILSC 95% CI     : [0.656, 0.870]      vs [0.767, 0.825] reported
  ILSC - SIDC     : +0.179  [+0.069, +0.284]   P(<=0) = 0.001
  ILSC - LoCmsg   : +0.136  [+0.041, +0.226]   P(<=0) = 0.003
```

**The direction survives.** Done as a paired comparison, ILSC beats both baselines
with intervals excluding zero. Two things must change: "confidence intervals
separated" is the wrong test for two AUCs on the same pairs — a paired difference
bootstrap is the right one; and the interval is roughly **3.6× wider** than
reported, on an evidence base of 105 pairs from **one** microservice.

### 10.4 ✅ What survived attack

- **Exp. 2 (H2).** Reproduced in full. Two caveats to state: the 20 targets have a
  **median of 5 operations** (top-quartile selection picks the smallest services,
  given §10.1) against a corpus median of 16; and the `same_service` control is
  missing 5 of 80 cells at level 5, which biases *toward* a steeper control and is
  therefore conservative.
- **Exp. 5 (H3).** Kendall's *W* reproduced from the artifact.
- **Exp. 1 quartiles.** Median 0.3658, Q1 0.2854, Q3 0.4526 — reproduced to four
  decimals. Corpus minimum is NeutrinoAPI at 0.1248. 0% saturation confirmed.
- **Exp. 3 coefficients.** 0.40861 / 0.486337, inflation +0.0777 — reproduced.
- **Exp. 4b point estimates.** AUC 0.794 / 0.574 / 0.651 reproduced exactly from an
  independent reimplementation of `SIDC_pair` and `LoCmsg_pair`.
- **The corpus pipeline.** Every stage count, the composition table, and the
  primary/sensitivity split reproduce from `manifest.csv` and `filter_log.csv`.

---

## 11. Discrepancy register

Numbers quoted in prose that disagree with the artifact they cite. Most date from
**D-26**, which re-ran the metric without the prose following.

| # | Claim | Quoted in | Stated | Artifact | Source of truth |
|---|---|---|--:|--:|---|
| 1 | Hyperscaler median ILSC gap | abstract, README, RESULTS, threats | +0.1340 | **+0.0578** | `ilsc_scores.csv` |
| 2 | Hyperscaler Cliff's δ | RESULTS D-25 | +0.609 | **≈0.31** | `ilsc_scores.csv` |
| 3 | Mask fires on … of within-service pairs | abstract, metric_definition | 56.9% | **73.63%** | `ilsc_scores.csv` (`mask_fire_pairs / n_pairs`, primary) |
| 4 | ρ_independent | README §6 | 0.433 | **0.4086** | `code_correlation_summary.csv` |
| 5 | Derivation inflation | RESULTS index table | +0.054 | **+0.0777** | `code_correlation_summary.csv` |
| 6 | Max inter-feature \|ρ\| | README §6 | 0.582 | **0.5575** | `feature_correlation.csv` |
| 7 | `gate1_lexical` ρ vs baseline | RESULTS Exp. 5 | 0.888 | **0.8389** | `weight_sensitivity.csv` |
| 8 | `gate1_lexical` mean \|Δ\| | RESULTS Exp. 5 | 0.0772 | **0.0944** | `weight_sensitivity.csv` |
| 9 | `gate1_semantic` ρ vs baseline | RESULTS Exp. 5 | 0.9351 | **0.9574** | `weight_sensitivity.csv` |
| 10 | SIDC discriminates on … services | RESULTS Exp. 4 | 16/20 | **13/20** | `baselines_comparison.csv` |
| 11 | ILSC distinct values | RESULTS Exp. 4 | 1,645 | **2,015** | `baselines_corpus.csv` |
| 12 | SIDC distinct values | RESULTS Exp. 4 | 681 | **709** | `baselines_corpus.csv` |
| 13 | 1 − LoCmsg saturation | RESULTS Exp. 4 | 77.0% | **76.9%** | `baselines_corpus.csv` |
| 14 | `DROP_VERSION_TOKENS` affects … of operations | threats §2 | 2.70% ops / 80 services | **74 services (3.5%)** | `version_tokens_sweep.csv` |
| 15 | F-05 mean ILSC change from the f4 rule | RESULTS, FLAGS, metric_definition | −0.0448 | **not regenerable** | `param_boilerplate.csv` now has identical before/after on all 2,136 rows |
| 16 | ρ_indep pair-bootstrap CI | RESULTS Exp. 3 | [0.245, 0.556] / [0.268, 0.572] (two different values in the same document) | **[0.2426, 0.5469]** | `code_correlation_summary.csv` |

**Items 1 and 3 are in the abstract.** Item 3 is the awkward one: 56.9% is the
abstract's empirical justification for the paper's central contribution, and the
engine's own output for the same quantity on the same population is 73.6% — the
*better* number for the argument.

**Item 15 is a reproducibility defect, not a typo.** The F-05 figures were measured
before the rule was adopted and the replication package can no longer produce them.
Either re-measure by re-running with the rule disabled and commit that artifact, or
drop the figures.

**Recommended fix for the whole class:** a build-time script that regenerates every
quoted figure from `results/` and fails on mismatch. `run_all.py` already exists;
this is an afternoon.

---

## 12. What is still owed

### 12.1 Blocking for submission

| | Item | Cost |
|---|---|---|
| 1 | **Confront the size dependence.** Report ρ = −0.55 in Sec. 6 and Threats; move the existing size entry out of the did-not-materialise list; add a partial correlation — does ILSC separate anything once *n* is controlled? Publish thresholds **per size band**. | 3–4 days |
| 2 | **Rebuild the matched gate with size matching.** Pair within provider *and* within ±25% on operation count. If 16 providers cannot supply that, run `ILSC ~ n_tags + log(n_ops) + provider` and report the `n_tags` coefficient. Either result is publishable. | 2 days |
| 3 | **Rewrite Exp. 4b's statistics as a paired difference test.** Stratify the resample so a negative is always present, or bootstrap pairs within `user` and say so. State that the independent condition is one service. | 1 day |
| 4 | **Re-run the prose against the CSVs** (§11) and add a build-time consistency check. | 1 day |

### 12.2 Promised evidence not yet produced

| Owed | State | Cost |
|---|---|---|
| Sock Shop inter-annotator agreement | Sheet written, **0 of 10** rows filled in `entities_annotator2` | ~1 h, second reader |
| Train Ticket extraction agreement | 10/10, mean Jaccard **1.000** — perfect agreement reads as non-independence, not reliability; F-03 requires the manual pass come from the Java sources | ~1 h, redo blind |
| End-to-end reproduction from a fresh clone | **Never executed.** `docs/replication.md` states this plainly — structural checks pass (22/22 scripts present, 24/24 modules import, 17/17 tests), the data run has only ever happened in the dev tree | ~1 h wall |
| F-02 · `norm_host()` near-duplicates | Open. Corpus count 2,206 is ≈0.9% high; 20 services double-counted in every macro statistic | ~2 h |
| Sock Shop `spec_pin` | `UNPINNED` — no upstream commit recorded for the five specs | ~30 min |
| Human validation of the mechanical `n_tags` labels | Never done. D-29 itself names this as "the gap a Q1 reviewer will name first" | 1 day |

### 12.3 Keep exactly as written

The negative results are the paper's credibility, and one of them is its most
citable idea:

- The **LoCmsg perturbation loss** — reported as it fell.
- The **original Gate 1 failure** and its full diagnosis.
- The **Xero construct case** — resource-level vs capability-level cohesion.
- **D-28's provenance inversion** — that evaluating interface metrics on generated
  specifications makes the *most superficial* metric win. This is a warning the
  field needs and deserves a section of its own, not a subsection of Exp. 4b.

### 12.4 Overall standing

Two of five experiments hold under adversarial recomputation, one holds after a
statistics rewrite, one is honestly underpowered, and one construct-validity result
does not survive. **Roughly two to three weeks from a submittable Q1 paper, and
none of it is new data collection.** The corpus, the engine, the decision log and
the replication discipline are already there; what is missing is one confound
analysis the study never ran on itself.

---

## 13. Reproduction

```bash
# 1. Dependencies
pip install -r requirements.txt
npm install                       # swagger2openapi 7.0.8, step (b) only

# 2. Fetch S1 — RAMA threshold benchmark (the anchor)
#    core.longpaths is REQUIRED on Windows: several RAMA filenames exceed
#    the 260-character limit and checkout fails without it.
git clone -c core.longpaths=true --filter=blob:none --sparse \
    https://github.com/restful-ma/thresholds.git rama-thresholds
cd rama-thresholds
git sparse-checkout set benchmark-repository/openapi
git checkout 5b0b2a3322d3b2b7c0e0f2c0c0ad0e524e67bf82
cd ..                                   # expect 2,619 files

# 3. Fetch S2 — APIs.guru current snapshot
git clone -c core.longpaths=true --filter=blob:none --sparse \
    https://github.com/APIs-guru/openapi-directory.git openapi-directory
cd openapi-directory
git sparse-checkout set APIs
git checkout f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49
cd ..

# 4. Run everything in dependency order
python run_all.py
```

The expensive half of `filter.py` is checkpointed, so a dedup rule can be
re-evaluated without re-parsing 6,757 specs:

```bash
python src/filter.py --scan S1     # ~4 min
python src/filter.py --scan S2     # ~6 min
python src/filter.py --merge       # seconds
```

Install libyaml (`yaml.CSafeLoader`) or the scan takes roughly ten times longer.

**Three defects the fresh-clone test found**, all invisible inside the working tree:

1. **The repository could not be cloned on Windows at all** — `parsed_nodrop/` had
   been committed by accident and several Azure filenames exceed 260 characters.
   Untracked in `bc87696`.
2. **The documented fetch commands fail on Windows** without
   `-c core.longpaths=true`.
3. **The corpus can shrink silently** — with `core.longpaths` set, git checks the
   files out but Python's `open()` still fails past 260 characters. Cloned into a
   deep directory, the pipeline produced **2,205 services instead of 2,206**, and
   the only trace was a `parse_error: FileNotFoundError` indistinguishable from a
   malformed spec. `load_spec` now separates `unreadable:` from `parse_error:` and
   `filter.py` prints a blocking warning. **Clone into a short directory on
   Windows.**

**Everything is pinned:** both corpus commits, the seed (42), the embedding model,
the converter version, and the Python dependencies — including the four
metric-track packages that were in use but unpinned until the replication pass
(`numpy`, `scipy`, `sentence-transformers`, `torch`).

---

*Assembled from `results/` (50 CSV), `figures/` (10 PDF), `src/` (31 modules),
`docs/` (13 documents) and `ILSC_Proposal_v3.docx`. Independent recomputations in
§10 and §11 were run against the artifacts, not the prose. Where this document and
`RESULTS.md` disagree, the artifact wins.*

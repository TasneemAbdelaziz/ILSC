# ILSC — Results index

Single collection point for the results of every completed task, so they can be
merged into the paper at the end. Each entry points at the **canonical
artifacts** (in `results/` and `figures/`) rather than copying them — those
files are the source of truth and must not be edited by hand.

Numbers below were recomputed from the artifacts themselves (not transcribed
from prose). Every task is reproducible from the pins in `config.py` and the
steps in `README.md` §2.

| Task | Script | Status | Headline |
|---|---|---|---|
| Day 1–2 — multi-source curation | [`src/filter.py`](src/filter.py) | ✅ complete | 2,206 services survive from 6,757; 1,014 from S1 |
| Day 1–2 — 2.0 → 3.x conversion | [`src/convert.py`](src/convert.py) | ✅ complete | 144/144 converted, 0 operation-set changes |
| Day 1–2 — strict validation (D-02) | [`src/validate_sample.py`](src/validate_sample.py) | ✅ complete | 97.5% strictly valid (S1 100%, S2 94.9%) |
| Day 3 — field availability (per-op) | [`src/availability.py`](src/availability.py) | ✅ complete | description on 73.0% of ops (micro); micro↔macro reverses by field |
| Day 3 — **pair co-availability (RQ2)** | [`src/pair_availability.py`](src/pair_availability.py) | ✅ complete | **mask matters for 68.4% of services**; micro 90.6% but see the caveat |
| Day 1–2 — **parser + feature extraction** | [`src/parse_spec.py`](src/parse_spec.py) | ✅ complete | 2,206 services, 97,912 operations, 0 skipped |
| Day 4 prep — Gate 1 candidates | [`src/gate1_select.py`](src/gate1_select.py) | ✅ complete | ten services picked, [`docs/gate1_expectations.md`](docs/gate1_expectations.md) |
| Day 1m — **similarity engine + mask** | [`src/embed.py`](src/embed.py), [`src/similarity.py`](src/similarity.py) | ✅ complete | 89,852 T + 54,701 description vectors; 17/17 unit tests, incl. the R2 regression |
| Day 3m — null models (D-18, D-21) | [`src/null_models.py`](src/null_models.py) | ✅ complete | E[ILSC_rand] **0.1011** global vs **0.2370** provider-restricted; flat in n |
| Day 4m — **GATE 1** | [`src/gate1_run.py`](src/gate1_run.py) | ⚠ **MARGINAL** | delta +0.680; one discordant service (C1), weights NOT changed (D-24) |
| Day 5m — **Exp. 1 big run** | [`src/ilsc.py`](src/ilsc.py) | ✅ complete | 2,206 services; ILSC_mean median **0.436** primary; thresholds incl. S1-only |
| Day 6m — inter-feature correlation (Fig 9) | [`src/feature_corr.py`](src/feature_corr.py) | ✅ complete | max |rho| **0.582** — no feature pair is redundant |
| D2 → oversized cap (D-17) | [`src/oversized.py`](src/oversized.py) | ✅ complete | cap 200; **mask-fire 56.87% primary vs 90.58% full**; quartiles move ≤3.2 |
| Day 5 — benchmark prep (+ Train Ticket) | [`src/benchmark_prep.py`](src/benchmark_prep.py) | ✅ complete | 39 services, **916 within-service pairs**; 122 independent vs 794 derived (D-16) |
| Day 7m — perturbation + checker | [`src/inject.py`](src/inject.py) | ✅ complete | three conditions (D-05); see the Exp. 2 section |
| Day 3–6e — **code dig, Sock Shop** | manual | ✅ complete | 27 endpoints, [`results/endpoint_entities.csv`](results/endpoint_entities.csv); **5 distinct Sim_code values** (F-04) |
| Days 9-10 — **Exp. 4** baselines | [`src/baselines.py`](src/baselines.py) | ✅ complete | ILSC 0%% saturated vs SIDC 35.8%%, LoCmsg 77.0%%; perturbation claim only half supported |
| Days 13-14 — **Exp. 5** sensitivity | [`src/sensitivity.py`](src/sensitivity.py) | ✅ complete | **Kendall W 0.9947**; rankings invariant to weights |
| Days 11-12 — **Exp. 3 / GATE 2** | [`src/code_correlation.py`](src/code_correlation.py) | ✅ **PASS** (reframed) | rho_indep **0.433**, rho_derived **0.488**; inflation +0.054 |
| Day 7e — Train Ticket extraction | [`src/entity_extract.py`](src/entity_extract.py) | ✅ complete | 209/211 operations joined (99.1%); 0 unexplained empties (D-22); agreement figure still owed |

Reproducibility pins (`config.py`): `SEED = 42`; RAMA commit
`5b0b2a3322d3b2b7c0e0f2c0c0ad0e524e67bf82`; APIs.guru commit
`f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49`. Python deps pinned in
`requirements.txt`, Node dep in `package.json`.

---

## ⚠ Read this before quoting any pair-weighted number

**84.0% of all 77,611,030 within-service pairs come from one service** —
Microsoft Graph, 11,422 operations. The 70 services with more than 200
operations (3.2% of the corpus) hold **97.6%** of all pairs.

Every operation-weighted ("micro") corpus statistic on this page is therefore
close to a statement about a handful of mega-specs. **Quote the service-level
figures.** The micro numbers are reported for completeness and because the f2
sensitivity band is computed on them; they are not the paper's claim.

**D2 is now resolved (D-17).** The pair-weighted numbers on this page are the
*sensitivity* (full-corpus) values. The **primary** values, with the 70 oversized
gateway specs held out, differ sharply — mask-fire is **56.87%** primary against
90.58% here, and f6 co-availability **74.41%** against 24.08%. Quote the primary
figures; see the Day 5 / D-17 section below and `results/oversized_thresholds.csv`.

This is not hypothetical: until D-13, *which* Microsoft Graph spec occupied that
84% was decided by filename sort order. See the decision log.

---

## Day 1–2 — Multi-source corpus curation

**Script:** [`src/filter.py`](src/filter.py) · **Governed by:** D-01, D-02, D-06,
D-07, D-09, D-10, D-12, D-13 (`docs/DECISIONS.md`)

**Inputs (both pinned, regenerated locally, not committed):**

| | Source | Files |
|---|---|--:|
| S1 | RAMA threshold benchmark, `restful-ma/thresholds` | 2,619 |
| S2 | APIs.guru `openapi-directory` | 4,138 |

**Outputs (canonical):**

| File | Rows | What |
|---|---|---|
| [`results/manifest.csv`](results/manifest.csv) | 2,206 | survivors + metadata + provenance |
| [`results/filter_log.csv`](results/filter_log.csv) | 4,551 | every removed spec + reason |
| [`results/convert_verify.csv`](results/convert_verify.csv) | 2,206 | operation-set proof for `specs/clean3/` |
| [`results/strict_validation_sample.csv`](results/strict_validation_sample.csv) | 200 | D-02 strict pass/fail |
| [`results/manifest_labelled.csv`](results/manifest_labelled.csv) | 2,206 | manifest + **rejected** domain labels |
| `specs/clean/` | 2,206 files | as published (regenerated) |
| `specs/clean3/` | 2,206 files | uniform 3.x JSON, for the parser (D-11) |

**Headline numbers** (recomputed from the artifacts):

- **Survivors: 2,206** from 6,757 — **S1 1,014, S2 1,192**. Sec. 7's target of
  "400–600 clean services (≥ 300 from S1)" is comfortably exceeded and its text
  needs rewriting (D-12).
- Removed: parse 49 + structure 184 (`a_validate` 233), RPC-shaped 1,
  `< 3 ops` 1,264, within-source dedup 1,199, **cross-source dedup 1,854**.
- **Version split:** 3.x **2,062 (93.5%)**, 2.0 **144 (6.5%)** — an artefact of
  S1 being pre-converted upstream, not a fact about publishing practice (D-10).
  S2 alone is 26.9% Swagger 2.0.
- **Operations/service:** min 3, median 16, mean 44.4, **max 11,422**.
  Total 97,912 operations.
- **Providers:** 616 distinct. Pooled big-three share 46.8%, but **S1 58.1% vs
  S2 37.4%** — the anchor corpus is the more concentrated one (D-12).
- **Admin endpoints stripped:** 62 across 48 services (D-07).
- **Conversion:** 144 Swagger 2.0 specs converted with `swagger2openapi@7.0.8`,
  0 failures, and **2,206/2,206 verified to have an identical (METHOD, path)
  operation set** before and after (D-01).
- **Strict validation (D-02):** **195/200 = 97.5%** of a seeded random sample
  pass `openapi-spec-validator`, against the cheap structural gate used
  corpus-wide. Per source: **S1 102/102 (100%)**, **S2 93/98 (94.9%)**.
  Rejections: 4 schema-validation errors, 1 unresolvable `$ref`.

**Note on domain labels.** The `domain` column and `manifest_labelled.csv` are
the **rejected** keyword labeller (D-03, 52% agreement). Kept as the evidence
behind the rejection; **inert** — nothing downstream consumes it.
`domain_validation_{BLIND,KEY}.csv` are **frozen**: BLIND carries a human
annotation made against the earlier 1,831-service corpus and cannot be
regenerated by re-running anything.

---

## Day 3 — Availability study  (justifies the mask, RQ2)

Two layers. **(A) per-operation** availability is descriptive; **(B) pair-level
co-availability** is the actual RQ2 number, because the mask evaluates
`m_ij,k = 1` only when *both* operations of a within-service pair carry feature
`k`. Both take the operation set from `filter.py` with a per-spec assertion that
it equals `filter.operations()`. Input `specs/clean/` (2,206 services);
**manifest cross-check: 0 mismatches**. Both are now stratified **by source as
well as by version**, which Sec. 7 requires and which turns out to matter a great
deal.

> **Which corpus these figures describe (D-14).** Every number in A and B, and
> both **Fig 1 and Fig 2**, are measured on **`specs/clean/` (as published)** —
> not on the corpus the similarity engine reads, which is **`specs/clean3/`
> (converted)** via `src/parse_spec.py`. The two diverge for the **144 converted
> 2.0 services**, because conversion moves an `in: body` parameter into
> `requestBody`: **f4 (parameters) is 96.41% on `clean/` against 91.04% on
> `clean3/`**, so B's pair-level mask figures are **~5 points optimistic on f4**
> for those services. Not re-derived yet, by choice — stated here so the gap is a
> declared limitation rather than an unstated defect.

### A. Per-operation availability (descriptive)

**Script:** [`src/availability.py`](src/availability.py) · **Scope:** 97,912
operations (admin excluded, matching filter.py).

**Outputs:** [`results/availability.csv`](results/availability.csv) (2,206) ·
[`results/availability_summary.csv`](results/availability_summary.csv) (64) ·
[`results/availability_skiplog.csv`](results/availability_skiplog.csv) (0) ·
[`figures/fig1_availability.pdf`](figures/fig1_availability.pdf) — four panels:
micro/macro × grouped-by-source/grouped-by-version.

% of operations carrying each field, pooled (`micro` = operation-weighted;
`macro` = per-service mean):

| Field | micro | macro | micro→macro |
|---|--:|--:|:--|
| **description** | 73.02 | 83.70 | **+10.7** |
| **summary** *(descriptive only — not a mask feature)* | 56.66 | 45.28 | **−11.4** |
| operationId | 88.43 | 85.40 | −3.0 |
| parameters | 91.09 | 89.28 | −1.8 |
| response_schema | 89.77 | 89.16 | −0.6 |
| any_schema | 92.00 | 91.11 | −0.9 |
| request_schema · body-eligible | 86.94 | 86.35 | −0.6 |

> **Finding 1 — the micro↔macro reversal survives the corpus change.**
> description and summary still move in *opposite* directions between the two
> averages: description **+10.7**, summary **−11.4**. A handful of mega-specs
> drives it — they **under-document description** yet **over-document summary**.
> A structural difference in how large specs are documented, not noise.
> **description is on 73.0% of operations (micro), 83.7% (macro)** — plainly
> above 60%; the mask's justification does **not** rest on per-operation
> description scarcity, but on the pair-level result in B.

> **Finding 1b — the two corpora document differently.** description micro is
> **82.5% in S1** but **67.8% in S2**; summary reverses, **41.2% in S1** against
> **65.1% in S2**. Part is the mega-spec effect (S2 holds them), part is that
> S1's specs passed through RAMA's converter. Report per source; do not pool
> silently.

### B. Pair-level co-availability — the RQ2 number

**Script:** [`src/pair_availability.py`](src/pair_availability.py) · **Scope:**
**77,611,030** within-service pairs. The mask can fire only on **f2** (name),
**f4** (parameters), **f5** (schemas — domain schema names *after* removing
`config.GENERIC_SCHEMAS`; empty ⇒ unavailable), **f6** (description); **f1**
(embedding) and **f3** (path) are always available.

**Outputs:** [`results/pair_availability.csv`](results/pair_availability.csv)
(2,206) · [`results/pair_availability_summary.csv`](results/pair_availability_summary.csv)
(72) · [`results/pair_maskfire_distribution.csv`](results/pair_maskfire_distribution.csv) (27) ·
[`figures/fig2_maskfire_distribution.pdf`](figures/fig2_maskfire_distribution.pdf)
(histogram — the bimodality, not a mean).

**Per-feature co-availability** — % of within-service pairs where **both** sides
carry the feature:

| Feature | micro (pooled) | macro (pooled) | micro S1 | micro S2 |
|---|--:|--:|--:|--:|
| f2 name (codegen, primary) | 97.17 | 83.49 | 88.77 | 97.48 |
| f4 parameters | 92.34 | 84.72 | 88.94 | 92.47 |
| **f5 schemas** (generic-excluded) | **36.09** | 73.98 | **73.65** | **34.71** |
| **f6 description** | **24.08** | 81.52 | **81.95** | **21.96** |

**Headline — mask fires (≥1 of f2,f4,f5,f6 unavailable):**

| stratum | micro | macro |
|---|--:|--:|
| **pooled** | **90.58** | **49.52** |
| S1 | 44.19 | 43.82 |
| S2 | 92.28 | 54.37 |
| 2.0 | 98.91 | 77.31 |
| 3.x | 90.07 | 47.58 |

> **Finding 2 — the mask is not a marginal correction, but state it per service.**
> Per service the mask **materially affects 68.4% of them**. The pair-weighted
> figure is 90.6%, driven by f5 (36.1%) and f6 (24.1%) — but see the warning at
> the top of this page: that number is 84% one service.

> **Finding 3 — S1 and S2 disagree enormously at the micro level, and barely at
> the macro level.** Mask-fire micro is **44.2% in S1** against **92.3% in S2**;
> macro is **43.8%** against **54.4%**. The micro gap is the mega-specs (S1 holds
> 46% of services but only **3.5%** of all pairs); the macro gap is the real,
> modest difference between the corpora. This contrast is the clearest available
> evidence that the service-level framing is the robust one.

**Distribution across services is bimodal** (primary `f2_codegen`), so the mean
is the wrong summary:

- **697 / 2,206 services (31.6%) have 0% mask-fire** — complete specs the mask
  never changes; **713 (32.3%) have 100%**. Median 40.0%; IQR spans 0–100.
- Honest framing: **the mask matters for 68.4% of services**, not "average
  mask-fire 49.5%". (`results/pair_maskfire_distribution.csv`.)

**f2 sensitivity band (D-08).** Reported under three definitions
(`f2_nonempty`, `f2_codegen` primary, `f2_derived`). The **micro headline moves
90.17–93.41% (3.24 pts)** — the operationId "informativeness" choice does not
matter much for the pair-weighted number. It *does* move the service-level
claim (share where the mask matters 68.4% → 81.3%; macro 49.5% → 63.0%) → a
Threats-to-Validity caveat, not a headline mover.

**Paper-ready takeaways (RQ2):**
1. Pair-level, the mask materially affects **68.4% of services** — this, not the
   per-operation rate and not the pair-weighted micro, is the RQ2 justification.
2. It is driven by **f5 schemas** and **f6 description**; f2 and f4
   co-availability are high.
3. The service distribution is **bimodal** (31.6% complete, 32.3% always-firing)
   → report "matters for X% of services", never a single mean.
4. Robust to the f2 definition at the micro level (~3 pts); the service-level
   figure moves ~13 pts and is reported as a three-column band (D-08).
5. **Report per source.** Pooling hides a 48-point micro gap between S1 and S2.

---

## Day 1–2 (metric track) — Parser + feature extraction

**Script:** [`src/parse_spec.py`](src/parse_spec.py) · **Governed by:** D-11,
D-14, D-15 · **Input:** `specs/clean3/` (2,206 uniform 3.x JSON specs)

**Output:** `parsed/<service>.json`, one document per service (regenerated, not
committed). **2,206 services, 97,912 operations, 0 skipped** — the operation
count matches `manifest.csv` exactly, and every service asserts its operation
set equals `filter.operations()`.

Per operation: `method`, `operation_id`, `path`, `param_names`, `schema_names`,
`description`, `summary`, plus the derived `name_tokens` (f2), `path_tokens`
(f3), `param_tokens` (f4), `domain_schemas` (f5) and `T` (f1).

**Per-operation feature availability as the mask will see it:**

| Feature | ops | % |
|---|--:|--:|
| f2 name | 86,570 | 88.42 |
| f3 path | 97,325 | 99.40 |
| f4 parameters | 88,828 | 90.72 |
| f5 schemas (generic + >80% excluded) | 77,060 | 78.70 |
| f6 description | 71,493 | 73.02 |

Cross-validation against the Day 3 study is exact where it should be —
`operationId` 88.42% vs 88.43%, `description` 73.02% vs 73.018% — and differs
only where D-14 predicts (f4, the converted-corpus effect).

**f5 exclusions:** 835 generic-list hits plus **3,418 per-service “frequent”
schemas** removed by the >80% rule (Sec. 6). f5 availability (78.7%) is well
below mere schema presence (`any_schema`, 92.0%), which is the exclusion rules
doing their job and is why `any_schema` must never be read as f5 (D-08).

**[v3/R2] `T(Oi)` excludes the description**, verified by the spot-check, which
fails any operation whose description text appears inside `T`.

**Two corrections made while building this** (both in `docs/DECISIONS.md`):

- **D-15** — the pinned stopwords `v1`/`v2` were dead: splitting letter/digit
  runs before stopword removal turns `v2` into `v` + `2`. Since nearly every
  Google path begins `/v1/`, this would have inflated f3 across the largest
  provider in the corpus. Caught by the ten-tricky-names eyeball test.
- A JSON-Pointer fix for refs that percent-encode `{`/`}` cut unresolved
  references from **1,437 to 12** and recovered f4/f5 for DigitalOcean and 16
  other services.

**Spot-check (Sec. 10, step 8):** 5 random services re-verified against their
source specs — 5/5 pass.

---

## Day 4 preparation — the Gate 1 ten

**Script:** [`src/gate1_select.py`](src/gate1_select.py) ·
**Deliverable:** [`docs/gate1_expectations.md`](docs/gate1_expectations.md) ·
[`results/gate1_candidates.csv`](results/gate1_candidates.csv) (10) ·
[`results/gate1_shortlist.csv`](results/gate1_shortlist.csv) (80, browsing aid)

Five expected-cohesive and five expected-mixed services, spanning nine
providers, each with a written justification citing the service's **stated
business capability**. The script deliberately does not choose them: selecting
on path structure would select on feature **f3** and make Gate 1 pass by
construction. The clearest mixed case is **NeutrinoAPI**, whose author's own
tags declare six unrelated domains (Data Tools, E-commerce, Geolocation,
Imaging, Security and Networking, Telephony).

Gate 1 itself is pending — it needs `ILSC_mean`, which is Mohamed's engine.

---

## Day 5 — Benchmark preparation  (Exp. 3 sample size, fixed in advance)

**Script:** [`src/benchmark_prep.py`](src/benchmark_prep.py) · **Governed by:**
D-06 (no `<3 ops` filter), D-07 (admin stripping), **D-16** (provenance split).

**Outputs:** [`results/benchmark_manifest.csv`](results/benchmark_manifest.csv)
(39) · [`results/benchmark_split_log.csv`](results/benchmark_split_log.csv) (34) ·
`specs/benchmarks/{sockshop,trainticket}/`.

**Exp. 3's sample size is now known before the code dig starts:**

| System | `spec_origin` | Services | Ops | **Pairs** | Exp. 3 role |
|---|---|--:|--:|--:|---|
| `sockshop` | hand-written | 5 (4 with pairs) | 27 | **122** | **ρ_independent** |
| `trainticket` | generated-from-source | 34 (32 with pairs) | 211 | **794** | **ρ_derived** |
| **Total** | | **39** | **238** | **916** | never pooled |

> **Finding — the independent condition rests on one system.** Sock Shop is the
> only benchmark whose specifications were written by hand rather than derived
> from code. Train Ticket publishes none (the sole citable artifact, Zenodo
> `10.5281/zenodo.21342161`, is Springfox-generated from the controllers), and
> **Online Boutique is a gRPC/Protocol-Buffers system with no OpenAPI at all** —
> its `.proto` methods are not (METHOD, path) operations, so it cannot supply
> independent specs either. **ρ_independent is therefore a single-system
> estimate over 122 pairs** and must be reported as such; it is not a
> corpus-level claim. The ρ_independent − ρ_derived gap is itself the
> deliverable: a measurable estimate of how much spec–code derivation inflates
> the correlation (D-16).

**Train Ticket ingestion.** The upstream baseline is one combined document
(172 paths, 211 operations). It is split into 34 per-service specs on the
`ts-*-service` tag that every operation carries — read off the artifact, not
guessed — with `definitions` pruned to each service's transitive `$ref` closure
and the (METHOD, path) multiset asserted unchanged. Measuring the combined
document instead would have produced C(211,2) = 22,155 fabricated cross-service
pairs in place of the 794 real ones. Attribution (CC-BY-4.0) in
[`specs/benchmarks/trainticket/README.md`](specs/benchmarks/trainticket/README.md).

**Known gap.** Sock Shop's five specs predate this pipeline and carry
`spec_pin = UNPINNED` — no upstream commit was recorded for them. Train Ticket is
pinned by DOI + archive sha256. Pinning Sock Shop is outstanding.

---

## D2 resolved — the oversized cap (D-17)

**Script:** [`src/oversized.py`](src/oversized.py) · **Cap:**
`config.OVERSIZED_MAX_OPERATIONS = 200` · **Governed by:** D-17.

Every analysis is run **twice** and both are always reported: **PRIMARY**
(≤ 200 operations) and **SENSITIVITY** (full corpus). Nothing is deleted —
`results/manifest.csv` keeps all 2,206 rows and gains an `oversized` flag.

**Justification is scope, not compute.** Above ~200 operations a specification
describes an API gateway or a whole platform surface — Microsoft Graph (11,422),
Autotask PSA (2,958), Kubernetes (1,113), GitHub v3 (845), Compute Engine (758),
EC2 (718), Stripe (452) — not the single-capability microservice ILSC is defined
over. 200 sits at ≈ p96.8 of the size distribution (median 16, p95 136, p97 208).

| | services | operations | within-service pairs |
|---|--:|--:|--:|
| **PRIMARY** (≤ 200) | 2,136 | 57,420 | 1,828,978 |
| **SENSITIVITY** (full) | 2,206 | 97,912 | 77,611,030 |
| excluded | 70 (3.17%) | 40,492 | 75,782,052 (**97.6%**) |

**Pair-weighted (micro) — the cap does not trim the picture, it inverts it:**

| statistic | PRIMARY | SENSITIVITY | move |
|---|--:|--:|--:|
| **mask-fire %** | **56.87** | 90.58 | **+33.71** |
| f2 co-availability % | 78.39 | 97.17 | +18.77 |
| f4 co-availability % | 81.29 | 92.34 | +11.05 |
| f5 co-availability % | 70.36 | 36.09 | **−34.28** |
| f6 co-availability % | 74.41 | 24.08 | **−50.33** |

**Per-service quartile thresholds — almost unmoved.** Largest movement of any
boundary across all ten measures: **3.17 points** (f5 co-availability Q1).
`operations` Q3 32 → 35; mask-fire median 38.71 → 40.00; f2, f6, description rate
and operationId rate all move **0.00**. Full table:
[`results/oversized_thresholds.csv`](results/oversized_thresholds.csv).

> **Finding — this is the empirical case for the service-level framing.**
> Mega-specs do not merely add noise to the pair-weighted view, they reverse it:
> f6 (description) co-availability reads **24.08%** on the full corpus and
> **74.41%** once gateway specs are removed, a 50-point swing produced by a
> handful of documents. Every per-service quartile boundary, meanwhile, moves by
> at most 3.17 points. Service-level statistics are robust to the cap;
> pair-weighted ones are not.

**Consequence for RQ2.** The mask-fire headline is **56.87% (micro, primary)**
against 90.58% on the full corpus. The 90.58% was substantially a statement about
a few gateway specifications. Quote the primary figure, with the sensitivity
figure beside it — never instead of it. The service-level claim ("the mask
matters for 68.4% of services") is unaffected.

**Duplicates (F-02) do not disturb this.** The one numerically significant
near-duplicate (GitHub v3, 845 ops) is itself oversized and excluded here;
residual contamination in the primary corpus is 0.31% of pairs, so the thresholds
were not re-derived.

**Not yet included.** ILSC scores do not exist — the similarity engine is
pending — so no ILSC quartile thresholds appear above. D-17 fixes the
**protocol**; the ILSC thresholds must be derived under it once the engine lands.

---

## Day 1–3 (metric track) — The similarity engine

`src/embed.py` + `src/similarity.py` + `src/ilsc.py`. Everything below reads one
embedding cache, built once: **89,852 unique `T` vectors** (of 97,912 operations)
and **54,701 unique description vectors** (of 71,493 operations that have one;
26,419 have none). `python src/embed.py --verify` re-checks the cache against
`parsed/` without re-embedding and confirms all 2,206 services align.

**Unit tests: 17/17 pass** ([`src/test_similarity.py`](src/test_similarity.py)),
including the one that matters most — **R2**: deleting one operation's description
leaves f1 bit-identical (0.662798 both ways) while `m_f6` flips 1 → 0 and `Sim`
still computes. This test fails on the v2 design and is the reason R2 exists.

Three engine-level judgements are recorded rather than buried: **D-19** (a
present-but-empty token set is *unavailable*, not zero), **D-20** (cosine clamped
to [0,1]), and **D-23** (the code-generator test extended to the sanitised form of
a baked-in path).

---

## Day 3 (metric) — Null models  (D-18, D-21)

[`src/null_models.py`](src/null_models.py) → [`results/null_model.csv`](results/null_model.csv),
[`results/null_model_bysize.csv`](results/null_model_bysize.csv)

**D-18 is validated, not merely assumed.** The provider-restricted null is
genuinely the harder bar:

| null model | E[ILSC_rand] |
|---|--:|
| global (arbitrary bag of API operations) | **0.1011** (SE 0.0001, 400,000 pairs) |
| provider-restricted, median over 97 estimable providers | **0.2370** |
| provider-restricted, range | 0.0931 – 0.6109 |

**96 of 97 providers sit above the global expectation.** The gap between the two
normalisations — 0.101 against 0.237 — is itself the reportable finding Sec. 6
asks for: a service must clear a much higher bar to look coherent *relative to its
own provider* than relative to the corpus at large.

480 of 577 providers fall back to the global expectation, marked in the output:
either fewer than 50 operations, or (103 of them) **every operation inside a
single service**, which leaves no cross-service pair to draw. A null estimated
from nothing is not an estimate.

**E[ILSC_rand(n)] is flat in n, exactly as D-21 predicts.** Full 1,000-draw
computation at seven sizes:

| n | 3 | 5 | 10 | 25 | 50 | 100 | 200 |
|---|--:|--:|--:|--:|--:|--:|--:|
| E | 0.0996 | 0.1016 | 0.1015 | 0.1012 | 0.1016 | 0.1014 | 0.1012 |
| sd over draws | 0.0370 | 0.0274 | 0.0157 | 0.0091 | 0.0060 | 0.0042 | 0.0029 |

Spread across all sizes: **0.00203**. The pair-sample estimator gives 0.10111.
**Consequence:** `ILSC_norm` is an affine rescaling of `ILSC_mean` with constant
coefficients, so it cannot reorder services — every rank-based result is identical
on either, and `ILSC_norm` must not be presented as independent evidence.

---

## Day 4 — GATE 1: **MARGINAL**

[`src/gate1_run.py`](src/gate1_run.py) → [`results/sanity_check.csv`](results/sanity_check.csv),
[`results/gate1_verdict.csv`](results/gate1_verdict.csv)

| | cohesive | mixed |
|---|--:|--:|
| mean ILSC_mean | 0.4545 | 0.3486 |
| min (cohesive) / max (mixed) | 0.2923 | 0.4288 |

Cliff's delta **+0.680**, exact one-sided p **0.0675** over 252 label assignments,
**no clean separation**.

**The verdict turns on one service.** Every cohesive candidate outscores every
mixed candidate except **C1, Xero Payroll AU (0.2923)**. Exclude C1 and the
remaining split is **perfect (delta +1.000)**.

C1 is diagnosed, not hand-waved: its tokens are clean (`employees`,
`leave applications`, `pay runs`, `payroll calendars`, `superfunds`), and it
covers ~10 *distinct resources* inside one *business capability*. Lexical overlap
between `employees` and `superfunds` is genuinely zero, so f2 = 0.059 and
f3 = 0.093 are correct measurements of a real absence. Descriptions exist on 5 of
29 operations, leaving f6 available on **2% of pairs**.

**The weights were NOT changed, and the proposal's own remedy is worse.**

| weights | delta (all 10) | delta (C1 excluded) |
|---|--:|--:|
| **equal 1/6 (pinned)** | **+0.680** | **+1.000** |
| "upweight path+schema" (Sec. 10's suggestion) | +0.600 | +0.900 |
| semantic-heavy (f1, f5, f6) | +0.200 | +0.400 |
| lexical only (f2, f3, f4) | +0.760 | +1.000 |

No scheme rescues C1. See **D-24** — this is read as a **construct-validity
finding** (ILSC measures *resource-level*, not *capability-level*, cohesion), and
the weight question is left to Exp. 5, which answers it over 2,206 services rather
than ten.

---

## Day 5 — Experiment 1, the big run

`python src/ilsc.py --null results/null_model.csv` →
[`results/ilsc_scores.csv`](results/ilsc_scores.csv),
[`results/ilsc_thresholds.csv`](results/ilsc_thresholds.csv). 2,206 services in 51 s.

| | PRIMARY (≤ 200 ops) | SENSITIVITY (full) |
|---|--:|--:|
| services | 2,136 | 2,206 |
| ILSC_mean, mean | 0.4341 | 0.4288 |
| ILSC_mean, Q1 / median / Q3 | 0.339 / **0.436** / 0.515 | 0.332 / 0.430 / 0.512 |
| ILSC_τ (τ = 0.50), mean | 0.3453 | 0.3370 |

**D-17's prediction holds.** The cap moved pair-weighted co-availability by up to
50 points; it moves `ILSC_mean`'s median by **0.006**. `ILSC_mean` is a per-service
statistic, and D-17 established that per-service statistics are robust to the cap.
The two populations are reported side by side regardless.

**Quartile thresholds** — the S1-only row is the one comparable with Bogner
(Sec. 7); the pooled figures are not, because S2 is a different population.

| population | n | Q1 | median | Q3 |
|---|--:|--:|--:|--:|
| primary, all | 2,136 | 0.3394 | 0.4358 | 0.5149 |
| **primary, S1 only** | 991 | **0.3635** | **0.4636** | **0.5395** |
| primary, S2 only | 1,145 | 0.3225 | 0.4149 | 0.4941 |
| sensitivity, all | 2,206 | 0.3315 | 0.4300 | 0.5120 |
| sensitivity, S1 only | 1,014 | 0.3555 | 0.4603 | 0.5377 |

**S1 scores consistently higher than S2** — about 0.05 at every quartile. RAMA's
corpus is not a neutral sample of APIs.guru; the provenance column earns its keep,
and any threshold quoted in the paper must say which population produced it.

Component counts are omitted for the 2 services above 2,000 operations (both
already `oversized`, so the primary analysis is unaffected).

**An unplanned face-validity check, worth more than it cost.** `ILSC_mean` spans
0.1248 – 0.8866 over the corpus, and **the single lowest-scoring service of all
2,206 is NeutrinoAPI (0.1248)** — which is M1, the Gate 1 candidate Tasneem picked
as *mixed* on the strength of its author declaring six unrelated domains (Data
Tools, E-commerce, Geolocation, Imaging, Security and Networking, Telephony). The
label was written before any score existed and the corpus ranking was computed
without reference to it. The top of the distribution is equally readable: small,
single-purpose APIs (import.io at 4 operations, 0.8866; Proxy API at 5, 0.8741).

**No service scores below chance.** `ILSC_norm_global` is positive for all 2,206,
which is expected given E[ILSC_rand] = 0.1011 against a corpus minimum of 0.1248,
but it is worth stating that the unclipped negative case Sec. 6 allows for did not
arise. `ILSC_norm_provider` is filled for 2,162; the remaining 44 belong to
providers with no estimable pool (D-18) and are left blank rather than defaulted.

---

## Day 6 — Inter-feature correlation (Fig 9)

[`src/feature_corr.py`](src/feature_corr.py) → [`results/feature_correlation.csv`](results/feature_correlation.csv),
`figures/fig9_feature_correlation.pdf`. 930,936 pairs sampled across 2,136 services,
capped per service so no single specification dominates; pairwise-complete, so a
masked feature is absent rather than zero.

Spearman ρ:

| | f2 | f3 | f4 | f5 | f6 |
|---|--:|--:|--:|--:|--:|
| **f1** | 0.582 | 0.575 | 0.499 | 0.314 | 0.420 |
| **f2** | | 0.345 | 0.244 | 0.137 | 0.316 |
| **f3** | | | 0.404 | 0.242 | 0.280 |
| **f4** | | | | 0.193 | 0.142 |
| **f5** | | | | | 0.219 |

**No feature pair reaches |ρ| ≥ 0.85** — the maximum is f1–f2 at **0.582**. The
six features are not redundant, and the equal 1/6 weighting is not concealing a
duplicated signal. This is the empirical answer to "why six features if they
measure the same thing?".

f1 correlates most with everything, which is expected: `T(Oi)` is built from the
name, path, parameters and schemas, so f1 is a dense summary of what f2–f5 measure
discretely. f5 is the most independent of the lexical features (ρ ≤ 0.27 against
f2, f3 and f4), which is what justifies keeping it on a different similarity
function.

Feature availability over sampled pairs: f1 100%, f3 98.9%, f4 83.3%, f2 80.4%,
f6 77.1%, f5 73.5%.

---

## Day 7 — Experiment 2, perturbation  (D-05)

[`src/inject.py`](src/inject.py) → [`results/perturbation_raw.csv`](results/perturbation_raw.csv)
(3,000 rows), [`results/perturbation_summary.csv`](results/perturbation_summary.csv),
`figures/fig3_perturbation.pdf`. 20 top-quartile services, at most 3 per provider,
levels 0/1/2/3/5 × 10 draws × 3 conditions.

**Monotonicity: 20 of 20 services perfectly monotonic** under the treatment.

**The contrast — the headline is the gap, not the drop:**

| condition (increasing semantic distance) | mean degradation slope per injected operation |
|---|--:|
| `same_service` (nearest sibling, same provider) | −0.04046 |
| `same_provider` | −0.06628 |
| **`cross_provider` (treatment)** | **−0.09779** |

The three slopes **order exactly as semantic distance predicts**, which is a direct
validation of D-05's provider-proximity proxy: the proxy does not merely label, it
graduates.

Paired slope gap (`cross_provider` − `same_provider`): mean **−0.0315**, median
−0.0268, **negative for 20 of 20 services**, exact sign-flip p **< 1 × 10⁻⁶** over
all 2²⁰ assignments.

**H2 contrast: POSITIVE.** The size-matched control is what makes this
non-tautological — injecting *anything* lowers a mean-similarity score, but
injecting something semantically further away lowers it measurably faster.

---

## Days 3–7 (empirical) — The code dig

**Sock Shop, by hand.** [`results/endpoint_entities.csv`](results/endpoint_entities.csv):
27 endpoints, one row each, every row carrying a `file:line` reference. Rules and
the excluded-type list are in [`docs/responsibilities.md`](docs/responsibilities.md) §4.

**Train Ticket, automated** (D-22). [`src/entity_extract.py`](src/entity_extract.py)
→ [`results/endpoint_entities_trainticket.csv`](results/endpoint_entities_trainticket.csv):
**209 of the 211 spec operations join to a code row (99.1%)**. Empty entity sets
19.1%: 32 are `/welcome` or `/hello` endpoints that genuinely return a `String`,
and the other 8 are in services with **no entity package and no repository** —
stateless orchestrators that own no data, for which an empty set is the correct
answer. **Genuinely unexplained: 0.**

The two unjoined operations belong to `ts-avatar-service` (Python) and
`ts-news-service` (Go): Train Ticket is not a single-language system, and those
two need a manual pass. The extractor now names every service it cannot read,
with its detected language, so the gap cannot be mistaken for an empty result.

**The finding that matters, and it is a problem — see F-04:**

| | Sock Shop (`ρ_independent`) | Train Ticket (`ρ_derived`) |
|---|--:|--:|
| services with pairs | 4 | 32 |
| **services with any code-side variance** | **2** | **27** |
| within-service pairs | 122 | 794 |
| **distinct `Sim_code` values** | **5** | **12** |
| share of pairs at exactly 1.0 | 23.8% | 39.1% |

`carts` (10 pairs) and `orders` (1 pair) are **constant** — every endpoint touches
the same entity set, correctly — so they cannot contribute to a within-service
correlation at all. `ρ_independent` is therefore close to a single-service result
on `user`, against a five-level ordinal variable with heavy ties. The condition
the paper would most like to lean on is the weaker of the two, and the condition
quarantined for circularity (D-16) is the better-powered one. This must be stated
in the paper rather than discovered at review.

**Neither reliability figure exists yet.** Both sample sheets are written and
blank: [`results/sockshop_reliability_sample.csv`](results/sockshop_reliability_sample.csv)
and `src/entity_extract.py --sample 10`. A second pass by the same reader measures
memory, not reliability, so these need someone who did not do the first pass —
about an hour each. **F-03** additionally requires that the Train Ticket sample be
taken from the Java sources, never from `docs/responsibilities.md` §2.

---

## Days 11–12 — Experiment 3, the code correlation: **GATE 2 PASSES**

[`src/bench_prepare.py`](src/bench_prepare.py) (convert → parse → embed the 39
benchmark services, 238 operations) then
[`src/code_correlation.py`](src/code_correlation.py) →
[`results/code_correlation_pairs.csv`](results/code_correlation_pairs.csv),
[`results/code_correlation_summary.csv`](results/code_correlation_summary.csv),
[`results/discordance.csv`](results/discordance.csv), Figs 4 and 5.

906 of 916 within-service pairs joined; 2 operations had no code row (the Python
and Go services). Spearman throughout — `Sim_code` is a 5-to-12 level tied
variable and Pearson would assume more than it supports.

| | `ρ_independent` | `ρ_derived` |
|---|--:|--:|
| system | Sock Shop | Train Ticket |
| `spec_origin` | hand-written | generated from source |
| pairs / services | 122 / 4 | 784 / 29 |
| **services with code-side variance** | **2** | **27** |
| `Sim_code` levels (largest tie) | 5 (27.9%) | 12 (40.8%) |
| **Spearman ρ (pair level)** | **0.4332** | **0.4876** |
| p | 6.2×10⁻⁷ | 4.7×10⁻⁴⁸ |
| 95% CI, pair bootstrap | [0.268, 0.572] | [0.432, 0.541] |
| **95% CI, cluster bootstrap** | **[0.318, 0.643]** | **[0.380, 0.584]** |
| ρ, service level | 0.7379 (n=4, uninterpretable) | 0.4489 (n=29) |

**Gate 2: PASS, under the reframing the proposal itself specifies.** Both
coefficients land in the 0.4–0.6 band, which Sec. 12 instructs be reported as
"moderate correlation, complementary signal" — the interface and the code carry
partly independent information. That is the honest reading and, as the proposal
notes, arguably the more interesting one.

**Quote the cluster-bootstrap interval, not the pair-bootstrap one.** Pairs
inside a service share operations and move together, so resampling pairs treats
122 dependent observations as 122 independent ones and reports a precision the
design does not have. Resampling whole services is the honest unit. For
`ρ_independent` the two disagree materially — [0.268, 0.572] against
[0.318, 0.643] — and **the cluster interval straddles the 0.4 threshold**, so the
primary condition cannot be said to clear Gate 2's bar with confidence. That is
F-04 arriving exactly where it was predicted to: only **2 of 4** Sock Shop
services have any code-side variance.

**The derivation-inflation estimate is +0.054** (0.4876 − 0.4332). It is positive,
as D-16 predicts — correlating an interface against the code it was generated
from does read higher — but the effect is **small**. That is a result in its own
right and the one D-16 argued the two-condition design would buy: specification–
code derivation inflates this correlation by roughly five points, not by enough
to manufacture a finding. It also means `ρ_derived`, which is the better-powered
of the two, is not badly compromised by circularity.

**The coefficients are conservative in one specific respect.** `Sim_code` matches
entity names exactly, so `Assurance` and `AssuranceType` score 0.00 despite being
plainly related. Every such case pushes a pair toward "code says unrelated" while
the interface says related, biasing ρ **downward**. See
[`docs/discordance.md`](docs/discordance.md) §3 — recorded rather than fixed,
because changing `Sim_code` after seeing ρ has to be declared, and any change
must apply identically to both systems or the D-16 comparison breaks.

**Discordance: 102 of 906 pairs (11.3%)**, written up in
[`docs/discordance.md`](docs/discordance.md). Two kinds were anticipated and both
appear:

- *Interface high, code zero* — `…/inside_payment/money` vs `…/inside_payment/payment`
  (interface 0.86, code 0.00): one path prefix, four of five shared path tokens,
  disjoint entities. Exactly the canonical case Sec. 10 names.
- *Code complete, interface low* — `GET /customers` vs `POST /register`
  (interface 0.12, code 1.00): both touch `{User}`, share no lexical signal at
  all (f2 = f3 = f5 = 0.00), and score above zero **only through f1**. This pair
  is the study's clearest single piece of evidence that the embedding feature is
  not redundant with the lexical ones.

---

## Days 9–10 — Experiment 4: SIDC and LoCmsg baselines

[`src/baselines.py`](src/baselines.py) → [`results/baselines_corpus.csv`](results/baselines_corpus.csv),
[`results/baselines_perturbation.csv`](results/baselines_perturbation.csv),
[`results/baselines_comparison.csv`](results/baselines_comparison.csv),
`figures/fig7_baseline_perturbation.pdf`.

Both baselines are implemented **faithfully, which means without what ILSC adds** —
no availability mask, no generic-schema exclusion, no embeddings. The paper's Gap 2
claim is that these metrics see only structure and lexis, so they are measured
seeing only structure and lexis. Both read the same parsed corpus and the same D-07
exclusions, so the comparison differs in *method*, not in *inputs*.

- **SIDC** (Perepletchikov 2007): share of operation pairs with ≥ 1 common data type.
- **LoCmsg** (Athanasopoulos 2015): share of pairs whose message terms are disjoint.
  Runs the opposite way — higher is worse — so `1 − LoCmsg` appears where the three
  are compared, and the raw value is kept in the CSV.

### The corpus comparison — this is where ILSC's advantage is real

2,136 services, D-17 primary population:

| metric | mean | Q1 | median | Q3 | **corpus IQR** | distinct values |
|---|--:|--:|--:|--:|--:|--:|
| ILSC | 0.4341 | 0.339 | 0.436 | 0.515 | **0.1754** | 1,645 |
| SIDC | 0.5475 | 0.000 | 1.000 | 1.000 | 0.8623 | 681 |
| 1 − LoCmsg | 0.9162 | 1.000 | 1.000 | 1.000 | **0.0000** | 350 |

**Saturation — services scoring a perfect 1.0, where the metric can no longer
distinguish anything:**

| SIDC | 1 − LoCmsg | **ILSC** |
|--:|--:|--:|
| 35.8% | 77.0% | **0.0%** |

`LoCmsg`'s interquartile range is **exactly 0.0000**: at least half the corpus
receives an identical score. This is the quantitative form of the Gap 2 argument,
and it is a stronger result than the perturbation comparison below.

Spearman against ILSC: SIDC **+0.067** (p = 0.25, not significant), 1 − LoCmsg
**+0.324**. SIDC and ILSC are close to unrelated — they are not noisy versions of
each other, they measure different things.

### The perturbation comparison — **the hoped-for claim is only half supported**

All three metrics scored on the *same* injected operations (the run does its own
injection loop rather than comparing against stored numbers, so the draws are
identical). Slopes oriented so more negative = degrades faster; LoCmsg sign-flipped.

| metric | same_service | same_provider | cross_provider | **gap** | gap in corpus SD | p |
|---|--:|--:|--:|--:|--:|--:|
| **ILSC** | −0.0410 | −0.0667 | −0.0981 | **−0.0314** | **−0.237** | <1e−6 |
| SIDC | −0.0603 | −0.0664 | −0.0961 | −0.0297 | −0.072 | 5.1e−4 |
| LoCmsg | −0.0085 | −0.0104 | −0.0678 | **−0.0574** | **−0.275** | <1e−6 |

Sec. 10 hoped: *"If ILSC's foreign-vs-control gap is larger than theirs, that is a
direct, quantitative superiority claim."*

- **Against SIDC: supported.** ILSC's gap is larger both raw and standardised, and
  ILSC discriminates on **20/20** services against SIDC's 16/20.
- **Against LoCmsg: NOT supported.** LoCmsg's gap is larger, raw (−0.0574 vs
  −0.0314) and standardised (−0.275 vs −0.237). This is reported as it falls; the
  superiority claim the proposal wanted is **not** available against this baseline.

**The context that matters, and it is not a rescue.** LoCmsg scores **exactly
0.000 for all 20 test services before any perturbation** (sd = 0.0000). It cannot
rank them at all; it can only fall once foreign operations arrive. A large
degradation gap measured from a saturated floor shows that the metric *detects
that something foreign was added* — it does not show that it measures how cohesive
a service is. That distinction should be made in the paper, and it should be made
without claiming the perturbation result went the way it did not.

**Where this leaves the head-to-head.** ILSC's demonstrated advantage over these
baselines is **discriminating power on unperturbed services** — 0% saturation
against 35.8% and 77.0%, an IQR of 0.175 against 0.862 and 0.000, and 1,645
distinct values against 681 and 350 — not superior perturbation sensitivity. That
is a narrower claim than Sec. 10 anticipated and it is the one the data supports.

---

## Days 13–14 — Experiment 5: weight and τ sensitivity  (H3)

[`src/sensitivity.py`](src/sensitivity.py) → [`results/weight_sensitivity.csv`](results/weight_sensitivity.csv),
[`results/kendalls_w.csv`](results/kendalls_w.csv), [`results/tau_sweep.csv`](results/tau_sweep.csv),
`figures/fig6_tau_sweep.pdf`. 2,136 services (D-17 primary), 29 weight
configurations, 8 s — per-feature similarities are computed once per service and
reweighted, since the weights only change the final weighted average.

### Weights — **H3 holds, decisively**

| | Kendall's W |
|---|--:|
| **±20/±40% perturbations only** — the H3 test | **0.9947** |
| all 29 configurations, incl. the deliberately extreme Gate 1 schemes | 0.9707 |

Spearman against the pinned baseline, worst configurations first:

| configuration | ρ vs baseline | mean \|ΔILSC\| |
|---|--:|--:|
| `f1_only` (five features switched off) | 0.8374 | 0.2455 |
| `gate1_lexical` (f2, f3, f4 only) | 0.8880 | 0.0772 |
| `gate1_semantic` (f1, f5, f6 heavy) | 0.9351 | 0.0507 |
| `gate1_path_schema` (Sec. 10's suggested remedy) | 0.9669 | 0.0328 |
| **worst of the ±20/40% family** (`f4−40%`) | **0.9924** | 0.0159 |

**This answers the question D-24 deferred.** Gate 1 came out MARGINAL and the
weights were deliberately not tuned. Exp. 5 shows that decision cost nothing:
no reasonable weight variation moves the ranking. Even the extreme schemes —
switching five of six features off entirely — preserve ρ ≥ 0.84. The metric's
ordering is a property of the features, not of their relative weights, and the
equal 1/6 weighting is defensible because **the choice barely matters**, not
because it was optimised.

It also closes the loop on C1: no weighting rescued Xero Payroll AU at Gate 1
because no weighting materially changes any ranking. C1's position is a
construct-validity fact, not a tuning failure.

**The one number worth arguing about is `f1_only` at ρ = 0.8374.** f1 alone
recovers most of the ranking, which a reviewer will notice. It does not recover
all of it — 0.84 leaves real reordering — and Fig 9 already shows f1's strongest
correlation with any single feature is 0.582, so the other five are not
redundant with it. But the honest framing is that **f1 carries the largest share
of the signal and the remaining five refine it**, not that all six contribute
equally.

### τ — the sweep, and why 0.50 is a reasonable pin

| τ | 0.30 | 0.35 | 0.40 | 0.45 | **0.50** | 0.55 | 0.60 | 0.65 | 0.70 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| mean ILSC_τ | 0.733 | 0.644 | 0.547 | 0.441 | **0.345** | 0.267 | 0.203 | 0.152 | 0.111 |
| mean components | 1.38 | 1.69 | 2.20 | 3.03 | **4.12** | 5.73 | 7.89 | 10.53 | 13.60 |

Both curves are smooth — no threshold effect, no discontinuity that would make a
nearby τ qualitatively different. At the low end the graph is nearly complete
(1.38 components: almost every service is one connected blob, so ILSC_τ
discriminates little); at the high end it fragments (13.60 components). **τ = 0.50
sits in the middle of the usable range on both curves**, which is the argument for
keeping it — not that it optimises anything, but that it is where the statistic
still varies.

### The third knob — `DROP_VERSION_TOKENS` (D-15)

[`src/version_tokens_sweep.py`](src/version_tokens_sweep.py) →
[`results/version_tokens_sweep.csv`](results/version_tokens_sweep.csv). This knob
cannot be swept by reweighting: it changes the tokenizer, therefore `T(Oi)`,
therefore the **f1 embeddings**. The corpus was re-parsed and re-embedded with the
flag off and scored again.

**Its reach is narrower than it looks.** `v1` and `v2` are already pinned
stopwords, so the flag only affects version tokens outside that pair — `v0`,
`v3`, `v10`, and date-like versions such as `v20180301`. **74 of 2,136 primary
services (3.5%)** tokenise differently.

| | whole primary corpus | the 74 services it touches |
|---|--:|--:|
| ILSC_mean, pinned (`True`) | 0.4341 | 0.4458 |
| ILSC_mean, knob off (`False`) | 0.4351 | **0.4730** |
| mean shift | +0.0010 | **+0.0272** |
| Spearman | **0.9978** | 0.9482 |
| Kendall's τ | 0.9889 | — |

**Negligible corpus-wide, real locally.** The ranking is essentially unchanged
(ρ = 0.998, τ = 0.989), so the pinned setting is not driving any published
result. But on the services it actually touches the mean moves **+0.027**, and one
service moves **+0.121** (`text2data.org` 0.4272 → 0.5486). Reporting only the
corpus-wide figure would understate it.

**The direction confirms why D-15 exists.** Turning the flag off *raises* scores,
because the letter/digit splitter turns `v3` into `v` + `3` and every versioned
path in the corpus then shares the token `v` — the inflation D-15 was written to
prevent, in a smaller form. **The pinned setting is the conservative one.**

Exp. 5 is therefore a **three-knob** sensitivity analysis: weights, τ, and
tokenisation.

---

## Upcoming

Day 5 / Day 7 / Day 8–11 are pending (`README.md` §6). Append a new `## Day N`
section here as each completes, following the Day 3 template: Script → Inputs →
Outputs table → Headline numbers → Decisions → Paper-ready takeaways.

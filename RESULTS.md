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
| Day 3 — similarity engine + mask | — | ⏳ pending | next on the metric track |
| Day 4 — Gate 1 run | — | ⏳ pending | needs `ILSC_mean` from the engine |
| Day 5 — benchmark prep (+ Train Ticket) | [`src/benchmark_prep.py`](src/benchmark_prep.py) | ✅ complete | 39 services, **916 within-service pairs**; 122 independent vs 794 derived (D-16) |
| Day 7 — perturbation (provider proximity) | — | ⏳ pending | see D-05 |
| Day 8–11 — code dig | — | ⏳ pending | — |

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
sensitivity band is computed on them; they are not the paper's claim. Resolving
**D2** (`README.md` §4) is what would make them quotable.

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

## Upcoming

Day 5 / Day 7 / Day 8–11 are pending (`README.md` §6). Append a new `## Day N`
section here as each completes, following the Day 3 template: Script → Inputs →
Outputs table → Headline numbers → Decisions → Paper-ready takeaways.

# Experimental Setup and Dataset — draft

*Day 14 deliverable. Sec. 7 of the proposal is the skeleton; every number here is
recomputed from the artifacts in `results/`, not transcribed from prose.*

---

## 1. Dataset strategy — multi-source, and why

A single self-collected crawl invites the standard objection: dataset bias,
cherry-picking. The corpus is therefore built from a source already used and
validated in peer-reviewed work, plus a current snapshot for recency. Every
service in `results/manifest.csv` carries a provenance column.

| ID | Source | Pinned at | Files in |
|---|---|---|--:|
| **S1** | RAMA threshold benchmark (Bogner et al. 2020), `restful-ma/thresholds` | `5b0b2a3322d3b2b7c0e0f2c0c0ad0e524e67bf82` | **2,619** |
| **S2** | APIs.guru `openapi-directory` | `f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49` | **4,138** |

**Correction to Sec. 7 (D-12).** The proposal describes S1 as *1,737 API
descriptions*. At the pinned commit it holds **2,619** OpenAPI files. The
proposal's target of "400–600 clean services (≥ 300 from S1)" is superseded by
what the pipeline actually yields.

**S1 is reused for comparability, not for diversity.** This distinction matters
and the proposal conflated them: S1 is the *more* provider-concentrated of the
two sources (§4). What reusing Bogner's corpus buys is that our quartile
thresholds are directly comparable with his.

---

## 2. Curation pipeline

Six stages, in order. Every removal is logged with its reason in
`results/filter_log.csv` (4,551 rows).

| Stage | Removed | Reason |
|---|--:|---|
| a — parse | 49 | malformed file |
| a — structure | 184 | no `paths` or no `info` |
| b — RPC-shaped | 1 | every path identical |
| c — `< 3` operations | 1,264 | too small for a pairwise metric |
| d — dedup, within source | 1,199 | older version of the same API |
| e — dedup, cross source | 1,854 | already present in S1 |
| **surviving** | **2,206** | |

**Swagger 2.0 is converted, not discarded (D-01).** Dropping 2.0 would bias the
sample toward recently published APIs and would have eliminated the entire
benchmark used for the code-correlation study — all Sock Shop and Train Ticket
specifications are 2.0. Conversion uses `swagger2openapi@7.0.8`, the tool the
proposal names, and every conversion is verified: **2,206 of 2,206** have a
byte-identical `(METHOD, path)` operation set before and after. A conversion that
added or dropped an operation would silently move every pairwise count
downstream, so a mismatch is a hard failure rather than a warning.

**Two corpora are kept deliberately (D-11).** `specs/clean/` is as published and
is what the availability study measures — the 2.0-vs-3.x contrast in its results
is a finding, and measuring converted files would erase it. `specs/clean3/` is
uniformly OpenAPI 3.x JSON and is what the metric consumes.

**Administrative endpoints are stripped (D-07).** A 12-entry list (`/health`,
`/healthz`, `/ready`, `/metrics`, `/actuator/*`, …), matched on the **whole**
path so that `/orders/{id}/status` is kept while a bare `/status` is dropped.
62 endpoints removed across 48 services.

**Validation is two-tier (D-02).** The whole corpus passes a cheap structural
gate; `openapi-spec-validator` is then run on a seeded random sample of 200.
**97.5% strictly valid** — S1 100%, S2 94.9%.

---

## 3. Corpus composition

| Property | Value |
|---|---|
| Services | **2,206** (S1 1,014 · S2 1,192) |
| Operations | **97,912** |
| Within-service pairs | 77,611,030 (full) · **1,828,978** (primary) |
| Operations per service | min 3 · median 16 · mean 44.4 · max 11,422 |
| OpenAPI 3.x / Swagger 2.0 | 2,062 (93.5%) / 144 (6.5%) |
| Distinct providers | 616 |

**The version split is an artefact, not a fact about the world (D-10).** RAMA
converted its inputs to OpenAPI 3 upstream, so S1 is 100% 3.x by construction.
S2 alone is 26.9% Swagger 2.0. The pooled split must never be read as a statement
about how authors publish.

### The oversized cap (D-17)

Specifications above **200 operations** describe API gateways or whole platform
surfaces — Microsoft Graph (11,422 operations), Datto PSA (2,958), Kubernetes
(1,113), GitHub (845), EC2 (718), Stripe (452) — not the single-capability
microservice ILSC is defined over. They are flagged `oversized` and held out of
the **primary** analysis; every analysis is repeated on the full corpus as a
**sensitivity** check and both are reported. Nothing is deleted.

| | services | operations | within-service pairs |
|---|--:|--:|--:|
| **primary** (≤ 200) | 2,136 | 57,420 | 1,828,978 |
| **sensitivity** (full) | 2,206 | 97,912 | 77,611,030 |

**The justification is scope, not compute**, and the cap matters more than
expected: 70 services (3.2%) hold **97.6%** of all pairs, so pair-weighted
statistics move by up to 50 points between the two populations while every
per-service quartile boundary moves by at most 3.2. Service-level statistics are
the primary result accordingly.

---

## 4. Provider concentration — the main external-validity constraint

| | Services | Providers | AWS + Google + Azure |
|---|--:|--:|--:|
| S1 (RAMA) | 1,014 | 315 | **589 (58.1%)** |
| S2 (APIs.guru) | 1,192 | 460 | 444 (37.4%) |
| pooled | 2,206 | 616 | 1,033 (46.8%) |

The peer-reviewed anchor is the more concentrated source. This propagates into
the results: **S1 scores about 0.05 above S2 at every ILSC_mean quartile**, so a
quoted threshold must name its population.

| population | n | Q1 | median | Q3 |
|---|--:|--:|--:|--:|
| primary, all | 2,136 | 0.3394 | 0.4358 | 0.5149 |
| **primary, S1 only** — Bogner-comparable | 991 | **0.3635** | **0.4636** | **0.5395** |
| primary, S2 only | 1,145 | 0.3225 | 0.4149 | 0.4941 |

---

## 5. Benchmark systems

`specs/benchmarks/<system>/`, catalogued with provenance in
`results/benchmark_manifest.csv`.

| System | `spec_origin` | Services | Operations | Within-service pairs |
|---|---|--:|--:|--:|
| `sockshop` | hand-written | 5 | 27 | **122** |
| `trainticket` | generated-from-source | 34 | 211 | **794** |

**The two are not interchangeable (D-16).** Sock Shop's specifications are
hand-written and independent of its code. Train Ticket ships no authored
OpenAPI: the only published artifact (Zenodo `10.5281/zenodo.21342161`,
CC-BY-4.0) derives them from the service code via Springfox introspection.
Experiment 3 therefore reports `ρ_independent` and `ρ_derived` **separately and
never pooled**, and the distance between them estimates how much
specification–code derivation inflates the correlation.

**Online Boutique cannot supply a third system.** It is gRPC with no OpenAPI at
all, and gRPC methods are not HTTP operations, so they do not fit the
`(METHOD, path)` model the metric is defined on. The hand-written condition
therefore rests on Sock Shop alone.

**Train Ticket is not a single-language system.** Of its 34 specified services,
`ts-avatar-service` is Python and `ts-news-service` is Go; the rest are Java /
Spring Boot. Both non-Java services were extracted by hand.

The corpus filters do **not** apply to benchmark systems (D-06): they are
selected for the code-correlation study, not sampled from a population.

---

## 6. Parameters

| Parameter | Value | Source |
|---|---|---|
| Random seed | `42` | `config.SEED` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` | `config.EMBEDDING_MODEL` |
| Feature weights | `1/6` each, uniform | Sec. 6; swept in Exp. 5 |
| τ (threshold) | `0.50`, grid 0.30–0.70 step 0.05 | `config.TAU_DEFAULT`, `TAU_GRID` |
| Oversized cap | 200 operations | `config.OVERSIZED_MAX_OPERATIONS` (D-17) |
| Minimum operations | 3 | `config.MIN_OPERATIONS` |
| Frequent-schema exclusion | > 80% of a service's operations | `config.FREQUENT_SCHEMA_RATIO` |
| Token stopwords | `get, post, api, v1, v2` | Sec. 8, pinned |
| `DROP_VERSION_TOKENS` | `True` | D-15; swept in Exp. 5 |
| Perturbation levels / draws | 0,1,2,3,5 × 10 | `config.PERTURBATION_*` |
| Null-model pair samples | 400,000 | `src/null_models.py` |
| Bootstrap resamples | 2,000 | `src/code_correlation.py` |

**The six features and their similarity functions (Sec. 6, D2):**

| | Content | Similarity | Availability |
|---|---|---|---|
| f1 | SBERT of `T(Oi)` — **no description** | cosine | always |
| f2 | operationId tokens | Jaccard | masked |
| f3 | normalised path tokens | Jaccard | masked |
| f4 | parameter-name tokens | Jaccard | masked |
| f5 | domain schema names | **overlap coefficient** | masked |
| f6 | SBERT of the description | cosine | masked |
| f7 | co-usage | — | reserved, mask ≡ 0 |

`Sim(Oi,Oj) = Σ wₖ·mᵢⱼₖ·simₖ / Σ wₖ·mᵢⱼₖ` — the weights redistribute over
whatever both operations have, so **absence never counts as dissimilarity**.
`T(Oi)` excludes the description, which enters only through f6 (R2); the two
texts are disjoint so each missing field is visible to exactly one mask term.

**Feature availability over sampled within-service pairs:** f1 100%, f3 98.9%,
f4 83.3%, f2 80.4%, f6 77.1%, f5 73.5%.

---

## 7. Reproduction

Everything is pinned: both corpus commits, the seed, the embedding model, the
converter version, and the Python dependencies — including the four
metric-track packages that were in use but unpinned until the replication pass
(`numpy`, `scipy`, `sentence-transformers`, `torch`). `python run_all.py`
executes every step in dependency order and fails loudly on the first broken one.

See `docs/replication.md` for what has been verified on a fresh clone and, more
importantly, what has not.

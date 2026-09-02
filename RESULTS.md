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
| Day 1–2 — corpus curation | [`src/filter.py`](src/filter.py) | ✅ complete | 1,831 services survive from 4,138 |
| Day 3 — field availability (per-op) | [`src/availability.py`](src/availability.py) | ✅ complete | description on 67.4% of ops (micro); micro↔macro reverses by field |
| Day 3 — **pair-level co-availability (RQ2)** | [`src/pair_availability.py`](src/pair_availability.py) | ✅ complete | **mask fires on 93.3% of pairs (micro); matters for 66.9% of services** |
| Day 5 — benchmark prep (+ Train Ticket) | — | ⏳ pending | see `README.md` §6 |
| Day 7 — perturbation (provider proximity) | — | ⏳ pending | see D-05 |
| Day 8–11 — code dig | — | ⏳ pending | — |

Reproducibility pins (`config.py`): `SEED = 42`; APIs.guru commit
`f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49`. Dependencies pinned in
`requirements.txt`.

---

## Day 1–2 — Multi-source corpus curation

**Script:** [`src/filter.py`](src/filter.py) · **Governed by:** D-01, D-02, D-06,
D-07 (`docs/DECISIONS.md`)

**Input:** APIs.guru `openapi-directory` @ pinned commit — 4,138 spec files
(regenerated locally; not committed, 464 MB — see `README.md` §2).

**Outputs (canonical):**

| File | Rows | What |
|---|---|---|
| [`results/manifest.csv`](results/manifest.csv) | 1,831 | surviving services + metadata |
| [`results/filter_log.csv`](results/filter_log.csv) | 2,307 | every removed spec + reason |
| [`results/manifest_labelled.csv`](results/manifest_labelled.csv) | 1,831 | manifest + **rejected** domain labels + evidence |
| [`results/domain_validation_BLIND.csv`](results/domain_validation_BLIND.csv) | 50 | manual validation sheet (blind) |
| [`results/domain_validation_KEY.csv`](results/domain_validation_KEY.csv) | 50 | automatic labels for the same 50 |
| `specs/clean/` | 1,831 files | filtered corpus (regenerated, not committed) |

**Headline numbers** (recomputed from `manifest.csv` / `filter_log.csv`):

- **Survivors: 1,831** from 4,138. Removed: parse 48 + structure 14 (`a_validate`
  62), RPC-shaped 1, `< 3 ops` 801, dedup 1,443.
- **Version split:** OpenAPI 3.x **1,338 (73.1%)**, Swagger 2.0 **493 (26.9%)**.
- **Operations/service:** min 3, median 17, mean 62.5, **max 22,361**.
- **Providers:** 594 distinct. Top three amazonaws 335 / googleapis 283 /
  azure 254 → **872 combined (47.6%)** — the main external-validity threat.
- **Admin endpoints stripped:** 49 across 40 services (D-07).

**Note on domain labels.** The `domain` column (filter.py step g) and
`manifest_labelled.csv` are the **rejected** keyword labeller (D-03, 52%
agreement). Kept for the record as the evidence behind the rejection; **inert**
— no downstream result consumes it (D-05 uses provider proximity instead).

**Open (block later steps):** D1 provider cap, D2 oversized-service handling
(`README.md` §4). *Not applied to Day 3.*

---

## Day 3 — Availability study  (justifies the mask, RQ2)

Two layers. **(A) per-operation** availability is descriptive; **(B) pair-level
co-availability** is the actual RQ2 number, because the mask evaluates
`m_ij,k = 1` only when *both* operations of a within-service pair carry feature
`k`. Both take the operation set from `filter.py` with a per-spec assertion that
it equals `filter.operations()`. Input `specs/clean/` (1,831 services);
**manifest cross-check: 0 mismatches**.

### A. Per-operation availability (descriptive)

**Script:** [`src/availability.py`](src/availability.py) · **Scope:** 114,358
operations (admin excluded, matching filter.py).

**Outputs:** [`results/availability.csv`](results/availability.csv) (1,831) ·
[`results/availability_summary.csv`](results/availability_summary.csv) (24) ·
[`results/availability_skiplog.csv`](results/availability_skiplog.csv) (0) ·
[`figures/fig1_availability.pdf`](figures/fig1_availability.pdf).

% of operations carrying each field (`micro` = operation-weighted; `macro` =
per-service mean):

| Field | micro (all) | macro (all) | micro→macro |
|---|--:|--:|:--|
| **description** | 67.38 | 84.95 | **+17.6** |
| **summary** *(descriptive only — not a mask feature)* | 63.42 | 45.74 | **−17.7** |
| operationId | 92.45 | 87.49 | −5.0 |
| parameters | 92.62 | 88.85 | −3.8 |
| response_schema | 92.89 | 90.05 | −2.8 |
| any_schema (schema present, any) | 94.51 | 91.87 | −2.6 |
| request_schema · body-eligible | 88.08 | 84.95 | −3.1 |

> **Finding 1 — the micro↔macro reversal.** description and summary move in
> *opposite* directions between the two averages: description **+17.6**
> (micro 67.4 → macro 85.0), summary **−17.7** (micro 63.4 → macro 45.7). A
> handful of mega-specs (one service ≈ 20% of all operations) drives it — they
> **under-document description** (dragging its operation-weighted rate below the
> per-service mean) yet **over-document summary** (pushing its rate above). This
> is a *structural* difference in how large specs are documented, not noise.
> **description is on 67.4% of operations (micro), 84.9% (macro)** — plainly
> above 60%; the mask's justification does **not** rest on per-operation
> description scarcity, but on the pair-level result in B. `summary` is reported
> only as this descriptive contrast; it is **not** one of the six similarity
> features and is excluded from the mask (D-08).

### B. Pair-level co-availability — the RQ2 number

**Script:** [`src/pair_availability.py`](src/pair_availability.py) · **Scope:**
**328,369,860** within-service pairs. The mask can fire only on **f2** (name),
**f4** (parameters), **f5** (schemas — the domain schema-name set *after*
removing `config.GENERIC_SCHEMAS`; empty ⇒ unavailable), **f6** (description);
**f1** (embedding) and **f3** (path) are always available.

**Outputs:** [`results/pair_availability.csv`](results/pair_availability.csv)
(1,831) · [`results/pair_availability_summary.csv`](results/pair_availability_summary.csv)
(27) · [`results/pair_maskfire_distribution.csv`](results/pair_maskfire_distribution.csv) (9) ·
[`figures/fig2_maskfire_distribution.pdf`](figures/fig2_maskfire_distribution.pdf)
(histogram — the bimodality, not a mean).

**Per-feature co-availability** — % of within-service pairs where **both** sides
carry the feature:

| Feature | pair micro | pair macro |
|---|--:|--:|
| f2 name (codegen, primary) | 99.08 | 85.50 |
| f4 parameters | 90.88 | 84.74 |
| **f5 schemas** (generic-excluded) | **30.12** | 75.05 |
| **f6 description** | **18.40** | 82.78 |

**Headline — mask fires (≥1 of f2,f4,f5,f6 unavailable):**

| version | micro | macro |
|---|--:|--:|
| **all** | **93.33** | **48.58** |
| 2.0 | 88.69 | 53.25 |
| 3.x | 93.41 | 46.86 |

> **Finding 2 — the mask is not a marginal correction.** Operation-weighted, it
> fires on **93.3% of comparisons**, driven by f5 (30.1% pair co-availability)
> and f6 (18.4%). Worked example (hand-verified): `autotask.net` — 2,958 ops,
> **zero** descriptions → no pair carries all four → 100% mask-fire, 4.37M pairs
> alone; `payrun.io` — 389 ops, all four present everywhere → 0%.

**Distribution across services is bimodal** (primary `f2_codegen`), so the mean
is the wrong summary:

- **606 / 1,831 services (33.1%) have 0% mask-fire** — complete specs the mask
  never changes; **574 (31.3%) have 100%**. Median 39.6%; IQR spans 0–100.
- Honest framing: **the mask matters for 66.9% of services**, not "average
  mask-fire 48.6%". (`results/pair_maskfire_distribution.csv`.)

**f2 sensitivity band (D-08).** Reported under three definitions
(`f2_nonempty`, `f2_codegen` primary, `f2_derived`). The **micro headline barely
moves: 93.23–95.93% (2.70 pts)** — the operationId "informativeness" choice does
not matter for the pair-weighted number. It *does* move the service-level claim
(share where the mask matters 66.9% → 82.2%; macro 48.6% → 64.5%) → a Threats-to-
Validity caveat, not a headline mover.

**Paper-ready takeaways (RQ2):**
1. Pair-level, the mask fires on **93.3% of comparisons (micro)** and materially
   affects **66.9% of services** — this, not the per-operation rate, is the RQ2
   justification.
2. It is driven by **f5 schemas (30.1% pair co-availability, generic-excluded)**
   and **f6 description (18.4%)**; f2 and f4 co-availability are high (99% / 91%).
3. The service distribution is **bimodal** (33% complete, 31% always-firing) →
   report "matters for X% of services", not a single mean.
4. Robust to the f2 definition at the micro level (< 3 pts); the service-level
   figure moves ~15 pts and is reported as a three-column band (D-08).

---

## Upcoming

Day 5 / Day 7 / Day 8–11 are pending (`README.md` §6). Append a new `## Day N`
section here as each completes, following the Day 3 template: Script → Inputs →
Outputs table → Headline numbers → Decisions → Paper-ready takeaways.

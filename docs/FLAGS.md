# Cross-track flags

Open items raised by one track that only the other track can decide. Each entry
names the owner. Raising a flag here is deliberately *not* the same as deciding
it — the decision belongs to the named owner and goes in `DECISIONS.md`.

---

## F-01 · D2 (oversized services) is now urgent — **owner: Mohamed (metric lead)**

> **✅ RESOLVED 2026-09-07 by D-17** — cap at 200 operations, primary +
> sensitivity, `oversized` flag in the manifest, nothing deleted. Tasneem took
> the call rather than leaving it blocked. The evidence below is what prompted
> it; D-17 carries the decision and its numbers. **No action needed from the
> metric lead beyond adopting the same primary/sensitivity split for Exp. 1 and
> for the ILSC quartile thresholds when the engine lands.**

Raised 2026-09-07 by the empirical track.

**What changed.** After D-13 fixed the Microsoft Graph tie-break (beta → stable),
the pair distribution got *more* concentrated, not less:

| | share of all within-service pairs |
|---|--:|
| Microsoft Graph (stable, 11,422 ops) | **84.0%** of 77,611,030 |
| the 70 services with > 200 operations (3.2% of the corpus) | **97.6%** |

That 84.0% is **up from ~76%** on the previous corpus. Cross-source dedup (D-09)
removed a large number of small S2 services, so the mega-specs' share rose even
though the biggest single spec got *smaller*.

**Why this is now urgent rather than optional.** Every operation-weighted
("micro") corpus statistic — including the RQ2 mask-fire headline — is at this
point **effectively a statement about a single specification**. A pair-weighted
number that one spec sets to within a couple of points is not a corpus finding.
The service-level framing ("the mask matters for 68.4% of services") is the
robust one and currently carries the paper, but Exp. 1 cannot lean on the
service-level framing alone.

**Why it is the metric lead's call.** D2 changes the *distribution Exp. 1 runs
over* — which services enter the null models and at what sizes — so it is a
metric-track decision, not an empirical-track one. The options on the table are
unchanged from `README.md` §4: **exclude / subsample / hard cap** oversized
services (> 200 operations).

**What the empirical track needs back.** Whichever option is chosen, and the
operation threshold, so Day 3's pair-level statistics can be recomputed on the
same population Exp. 1 uses. Until then the pair-weighted numbers stay labelled
as they are.

**Related:** D-13 (the tie-break that surfaced this), and the standing caveat at
the top of `RESULTS.md`.

---

## F-02 · Near-duplicate survivors escape the dedup key — **owner: Mohamed (metric lead)**

Raised 2026-09-07 by the empirical track. **Quantified, not fixed** — `norm_host()`
and the dedup key are D-09/D-13, so the change is the metric lead's call.

**What was found.** 20 `(title, version_field, n_operations)` triples occur more
than once in `results/manifest.csv`. Same API, same declared version, same
operation count — surviving twice because the hosts differ.

| Measure | Value | Share |
|---|--:|--:|
| duplicate triples | 20 | — |
| services involved | 40 | — |
| **redundant services** (Σ k−1) | **20** | 0.91% of 2,206 |
| operations added | 1,113 | 1.14% |
| **pairs added** | **362,256** | 0.47% |

**Why they escape.** The key is `(title, normalised host)`, and `norm_host()`
reduces to a bare netloc — correctly refusing to merge two genuinely different
hostnames. But the same API is routinely published under a prefix or sibling
subdomain: `github.com` vs `api.github.com`; `ofmpub.epa.gov` vs
`echodata.epa.gov`; `api.sportsdata.io` vs `azure-api.sportsdata.io`. **15 of the
20 groups differ only by host prefix or a sibling subdomain of the same
registrable domain.**

**Two distinct gaps.**

- **19 groups are cross-source (S1+S2)** — the residual D-09 gap: RAMA and
  APIs.guru publish the same API under different hostnames, so cross-source
  dedup never fires. All small: **5,666 pairs** between them.
- **1 group is within-source (both S2): GitHub v3 REST API**, `github.com` vs
  `api.github.com`, both v1.1.4, both 845 operations — a D-13 gap. It alone
  contributes **356,590 pairs, 98.4% of all duplicate-added pairs.**

**Interaction with D-17 (the ≤ 200 cap).** GitHub is 845 operations and is
therefore excluded as `oversized`. After the cap, duplicate contamination in the
primary corpus is **5,666 of 1,828,978 pairs = 0.31%**, over 19 redundant
services of 2,136 (0.89%). D-17's thresholds are consequently **not** materially
affected and were not re-derived.

**The decision needed.** Whether `norm_host()` should collapse a leading
`api.`/`www.` (or sibling subdomains) to the registrable domain for the dedup
key. Cost of leaving it: the corpus-size claim of 2,206 services is ~0.9% high,
and 20 services are double-counted in any per-service (macro) statistic.

**Not urgent for the pair-weighted numbers** — the cap already neutralises the
only group that mattered — but it does affect the headline corpus count, which
appears in the paper.


---

## F-03 · Train Ticket's responsibility one-pagers are derived from the specs, not the wiki — **owner: Tasneem (empirical lead)**

Raised 2026-09-08 by the empirical track, against its own work.

**What happened.** `docs/responsibilities.md` §2 describes all 34 Train Ticket
services. The plan called for those descriptions to come from the FudanSELab
*Service Guide and API Reference*. That wiki was not retrieved, so the entries
were written from the OpenAPI surface instead — paths, operation names and
schema names.

**Why that is not a cosmetic difference.** Exp. 3 correlates the interface
against the code. A "ground truth" restated *from the interface* is not
independent of one side of that correlation. Using these entries to guide the
Train Ticket entity extraction would let interface structure leak into the
code-side variable and inflate `rho_derived` — the exact circularity **D-16**
admits Train Ticket in order to *measure*, not to import.

**Where it is and is not safe to use.** Safe for orientation, for grouping
services in the Exp. 2 domain design, and for the paper's system description.
**Not safe** as the reference for the Day 7-8 entity extraction.

**What is needed, before Day 7.** Either retrieve the FudanSELab Service Guide,
or rewrite §2 from the Java sources. The second is the more defensible of the
two and is roughly a day; it can be folded into the Day 7 extraction pass, since
that pass has to read the same sources anyway.

**Sock Shop is unaffected** — §1 was written from the repositories themselves.

---

## F-04 · Sock Shop's code side has almost no variance — `rho_independent` may not be estimable — **owner: both**

Raised 2026-09-08 by the empirical track on completing the Sock Shop dig
(`results/endpoint_entities.csv`, 27 endpoints, 122 within-service pairs).

**What was found.** Across all 122 pairs the code-side Jaccard takes **five
distinct values** — 0.000, 0.333, 0.500, 0.667, 1.000 — and 23.8% of pairs sit
at exactly 1.000.

| service | ops | pairs | distinct Sim_code values | range |
|---|--:|--:|--:|---|
| user | 15 | 105 | 5 | 0.000 - 1.000 |
| catalogue | 4 | 6 | 2 | 0.500 - 1.000 |
| **carts** | 5 | **10** | **1** | **constant at 1.000** |
| **orders** | 2 | **1** | **1** | **constant at 1.000** |
| payment | 1 | 0 | - | contributes nothing (D-07 leaves one operation) |

**Why `carts` and `orders` are constant.** Both are genuinely single-aggregate
services. Every `carts` endpoint resolves the cart and its `@DBRef` items, so
all five touch `{Cart, Item}`. Both `orders` endpoints touch `CustomerOrder` and
the five types it embeds. This is a correct extraction, not a lazy one — the
services really are that uniform.

**Why it matters.** A variable that is constant within a service contributes
nothing to a within-service correlation, and eleven of the 122 pairs are in that
position. What is left is `user` (105 pairs over five values) and `catalogue`
(6 pairs over two). **`rho_independent` is therefore close to a single-service
result on `user`, computed against a five-level ordinal variable with heavy
ties.** Spearman's rho on five levels with 24% of the mass at one of them has
wide confidence intervals whatever the interface side does, and Gate 2's
threshold (rho < 0.4 triggers diagnosis) was not written with that in mind.

**This compounds D-16.** D-16 already established that the independent-spec
condition rests on Sock Shop alone. F-04 narrows it further: within Sock Shop it
rests mostly on one service.

**What to decide, and when.**

1. **Report a confidence interval, not a point estimate, for `rho_independent`,
   and state the tie structure.** Cheap, and it should happen regardless.
2. **Consider a finer-grained code-side variable** — for example weighting
   entities by how often the endpoint touches them, or counting distinct
   repository calls rather than distinct types — which would break some ties.
   This is a change to the extraction rule and must be decided *before* the
   Train Ticket pass so both systems are extracted the same way. **Due Day 6.**
3. **Do not quietly rescue rho by pooling Sock Shop with Train Ticket.** D-16
   forbids it and F-04 is not a reason to reopen that.

**The upside, stated plainly.** Train Ticket's 34 services and 794 pairs cover
far more entity diversity than Sock Shop can. F-04 raises the value of
`rho_derived` as evidence at the same time as it lowers the value of
`rho_independent` — which makes F-03 (getting the Train Ticket extraction right,
and independent of the interface) the more urgent of the two flags.

### F-04 update, 2026-09-08 — Train Ticket measured, and it is the stronger side

The Day 7 automated pass (D-22) now gives the comparison F-04 could only predict:

| | Sock Shop (`rho_independent`) | Train Ticket (`rho_derived`) |
|---|--:|--:|
| services with pairs | 4 | 32 |
| **services with any code-side variance** | **2** | **27** |
| within-service pairs | 122 | 794 |
| distinct `Sim_code` values | **5** | **12** |
| share of pairs at exactly 1.0 | 23.8% | 39.1% |

**The imbalance is now quantified and it is large.** The condition the paper
would most like to lean on - hand-written, code-independent specifications - has
five distinct values over two services. The condition that must be quarantined
for circularity (D-16) has twelve over twenty-seven. Train Ticket still carries
heavy ties (39% at 1.0, 28% at 0.0), so neither side supports a Pearson
correlation without comment; both should be reported as Spearman with the tie
structure stated.

**This does not license pooling.** D-16's quarantine stands. What it changes is
the framing: `rho_independent` should be presented as a *small-sample check on a
single system*, and the distance between the two coefficients - the
derivation-inflation estimate D-16 argues for - carries the weight, with the
asymmetry in precision stated plainly rather than left for a reviewer to notice.


---

## F-05 · f5 excludes infrastructural schemas; f4 excludes nothing — **owner: both (Sec. 6 owns the rule)**

> **✅ RESOLVED 2026-09-08 by D-26** — the f5 rule now applies to f4 at the same
> 0.80 ratio. The evidence below is what prompted it; D-26 carries the decision,
> the provenance argument, and the cost. The corpus was re-parsed and re-embedded,
> because `T(Oi)` carries the parameter tokens and the f1 vectors move too.

Raised 2026-09-08 while resolving D1 (**D-25**). This is the largest single
contributor to the hyperscaler effect that D-25 documents, and unlike the rest
of that effect it is **a gap in the metric's definition, not a property of the
services**.

**The asymmetry.** Sec. 6 [v3] excludes a schema from **f5** when it appears on
more than 80% of a service's operations — infrastructural, not domain-bearing,
and the overlap coefficient is especially inflated by it. **f4 has no equivalent
rule.** Its parameter-name tokens go into a bare Jaccard with nothing removed.

**What that admits.** Per-service parameter frequencies:

| provider | parameters on ~every operation |
|---|---|
| googleapis.com (10,103 ops) | `fields`, `oauth_token`, `key`, `prettyPrint`, `quotaUser`, `alt` — **100%** each |
| amazonaws.com (11,843 ops) | `X-Amz-Signature`, `X-Amz-Algorithm`, `X-Amz-SignedHeaders`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Content-Sha256`, `X-Amz-Security-Token` — **99%** each |
| azure.com (5,802 ops) | `api-version` 94%, `subscriptionId` 76%, `resourceGroupName` 66% |

These are authentication and serialisation boilerplate. Under Jaccard they make
every pair of operations in such a service share six or seven tokens before any
domain content is considered. Median f4 is **0.8189** for hyperscalers against
**0.4213** for everyone else.

**The argument for excluding them is Sec. 6's own, applied verbatim.** Nothing
in "a schema on more than 80% of a service's operations carries no domain
signal" depends on it being a schema.

**Measured, not asserted** (`src/param_boilerplate.py`, applying f5's exact rule
to f4, over all 2,136 primary services):

| | value |
|---|--:|
| services with ≥ 1 boilerplate parameter | **1,444 (67.6%)** |
| mean change in ILSC_mean, all services | **−0.0448** |
| mean change, AWS/Google/Azure | −0.0730 |
| mean change, everyone else | −0.0188 |
| hyperscaler gap, before → after | **+0.1340 → +0.0715** |
| **share of the gap this closes** | **46.6%** |

**This is a lower bound.** `T(Oi)` also contains the parameter tokens, so a real
change would move the **f1 embeddings** as well and requires a re-parse and
re-embed. The figures above hold f1 fixed and measure the f4-only effect.

**It is not only a hyperscaler problem.** The largest individual drops include
`reloadly.com` (−0.199, from `Accept`), `walmart.com` (−0.143, from
`WM_CONSUMER.*` headers) and `openbanking.org.uk` (−0.144, from
`If-Modified-Since` / `If-None-Match`). Two-thirds of the corpus is affected.

**The metric has NOT been changed.** Altering a feature after seeing which
services it favours is precisely the move this project refuses elsewhere — see
`docs/discordance.md` §3, where `Sim_code`'s exact-name matching is left in place
for the same reason. The evidence is recorded so Sec. 6 can decide.

**What to decide, and when.** Before the metric definition is written up:

1. **Adopt the exclusion** — apply `FREQUENT_SCHEMA_RATIO` to f4 as it already
   applies to f5, re-parse, re-embed and re-run. Roughly an hour of compute, and
   **every published number moves**. The most defensible option, because it makes
   the metric internally consistent.
2. **Keep f4 as it is and report F-05 as a limitation** — cheaper, and honest if
   stated, but it leaves the paper explaining why one feature gets an exclusion
   rule and its neighbour does not.
3. **Report both** — the option D-17 took for the oversized cap. Most work, most
   defensible.

**Do not decide this by which produces the better ρ.** The decision is whether
the rule is right, and the answer to that does not depend on Exp. 3.

---

## F-06 · Train Ticket's operationIds and paths carry the service name — **owner: both**

Raised 2026-10-19 while drafting D-31.

**What is there.** 203 of 211 Train Ticket operationIds begin with the owning
service, e.g. `ts-assurance-service.deleteAssuranceUsingDELETE`, and every path
begins `/api/v1/<name>service`. After parsing, one operation reads

    name_tokens  ts assurance service delete assurance using delete
    path_tokens  assuranceservice assurances assuranceid

so f1 (through `T(Oᵢ)`), f2 and f3 all see the service's name.

**Where it comes from.** Not from `src/benchmark_prep.py`, which splits the
combined file by its `ts-*-service` tag and leaves operationIds untouched. The
path prefix is Train Ticket's own API. The operationId prefix is most likely
the upstream authors' merge of per-service Springfox output into one file —
Springfox's own ids have the form `deleteAssuranceUsingDELETE`. Not yet checked
against the Zenodo archive.

**Why it matters.**
1. **Within a service** (Exp. 3 `rho_derived` 0.486; Exp. 4b Train Ticket AUC
   0.739): every pair shares the same three name tokens and one path token. That
   is a constant offset which compresses f2 and f3. The direction of its effect
   on ρ and AUC is unknown until measured. The baselines read parameter and
   schema names only, so they are untouched by it.
2. **Across services** (D-30's developer-boundary test): left in, the test
   passes by construction. D-31 must remove both prefixes before anything is
   computed.

**Options for (1).**
1. Strip the upstream operationId prefix for Train Ticket only, as a merge
   artifact rather than part of the API, and re-run Exp. 3/4b on it.
2. Keep it and report it as a limitation.
3. Report both.

**Do not decide this by which gives the better number.**

**Update 2026-10-19 — schema names carry the prefix too** (found by D-31's
run). Train Ticket's schema names have the form `ts-<name>-service.<Type>`.
- There are 75 distinct names, none shared across services, and 173 of 211
  operations carry one. `HttpEntity` alone appears as a per-service name on 150
  operations.
- So the prefix reaches **SIDC_pair** (types are equal only within a service),
  **LoCmsg_pair** (every term set shares `ts` and `service`), **f5**, and **f1**
  through `[SCHEMA]`.
- This widens point 1. Exp. 4b's Train Ticket head-to-head (ILSC 0.739, SIDC
  0.917, LoCmsg 0.953) is affected for **all three** metrics, not only ILSC's.

**Correction:** the operationId prefix is on 211 of 211 operations, not 203. The
earlier count was faulty — see D-31.

---

## F-07 · D-03's blind sheet holds no labels — **owner: Tasneem (empirical lead)**

Raised 2026-10-19.

**What is there.** `results/domain_validation_BLIND.csv` has an empty
`your_label` column in all 50 rows, in the only committed version (`88d8bea`,
2026-09-02). D-03 describes this sheet as carrying the human annotation and
freezes it as the evidence for the 52% agreement. `docs/abstract_and_intro.md:152`
quotes the figure.

**Why it matters.** Nothing computed depends on it — D-05 replaced domain labels
with provider. But the 52%, and D-03's breakdown of the 24 disagreements, cannot
be checked from the repository. Under D-30 they cannot be re-measured by
annotation either.

**Options.**
1. Commit the filled sheet, if it exists.
2. If it does not, rest D-03's rejection on its mechanical evidence — the token
   `api` in the `devtools` list absorbing 64.6% of the corpus — and drop the 52%
   from the paper.


---

## F-08 · Exp. 2/4's same-service donor is chosen in hash order, so their draws do not reproduce — **owner: Mohamed (metric lead)**

Raised 2026-10-20 by D-33's reproduction check.

**What is there.** `inject._nearest_sibling` loops over
`{pool.service_of[i] for i in ...}` — a set — and keeps the first service with
the best title-token score. When two siblings tie, which one is kept depends on
string-hash order, and that changes between Python processes unless
`PYTHONHASHSEED` is fixed.
- For the 20 Exp. 2/4 services under seeds 0, 1 and 2, **3 get a different
  sibling**: `azure.com-applicationinsights-componentProactiveDetection`,
  `apideck.com proxy` and `fungenerators.com barcode`.
- A different sibling also has a different operation count, which changes how
  `rng.choice` consumes the generator. So later draws drift as well.
- Re-running Exp. 4 reproduces level 0 exactly and then differs from level 1
  (max |ΔILSC| 0.197).

**What it affects.** The stored draws of Exp. 2 (`inject.py`) and Exp. 4
(`baselines.py`) cannot be regenerated bit for bit. Their *conclusions* may well
survive — Exp. 4's gap uses cross_provider − same_provider, and every service
is perturbed the same way within one run — but that has not been checked.

**Options.**
1. Iterate `sorted(...)` and re-run Exp. 2 and Exp. 4. The numbers move
   slightly; the conclusions are re-checked.
2. Pin `PYTHONHASHSEED` in `run_all.py` and in both scripts, and re-run.
3. Leave the code, and report that the draws are seed-dependent, giving the
   spread over several seeds.

**Do not choose by which gives the better gap.**

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

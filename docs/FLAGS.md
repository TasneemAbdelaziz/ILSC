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

# Cross-track flags

Open items raised by one track that only the other track can decide. Each entry
names the owner. Raising a flag here is deliberately *not* the same as deciding
it — the decision belongs to the named owner and goes in `DECISIONS.md`.

---

## F-01 · D2 (oversized services) is now urgent — **owner: Mohamed (metric lead)**

Raised 2026-09-07 by the empirical track. **Not decided here.**

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

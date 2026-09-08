# The ILSC Metric — definition and rationale

*Writing-schedule Days 1–2, theory half. This is Sec. 6 of the paper. Every
design choice below carries the decision that fixed it and, where it was
measured, the number.*

---

## 1. What ILSC claims to measure, and what it does not

**Scope declaration, stated first because everything else depends on it.**
Service cohesion in the full sense is a property of the implementation. ILSC does
not claim to measure it. **ILSC measures interface-level semantic cohesion: the
semantic density of the operations a service declares in its API contract**,
positioned explicitly as a *proxy* for service cohesion. The validity of that
proxy is not assumed — it is the object of Experiment 3. This is why the metric
is not named "service cohesion".

**A second, sharper scope limit, discovered rather than designed.** ILSC measures
**resource-level** cohesion, not **capability-level** cohesion. A service can
serve exactly one business capability through many lexically and structurally
unrelated resources, and ILSC will score it low — correctly, by its own
definition, and misleadingly if the reader expects the other notion. Gate 1 found
the case that makes this concrete (§7), and Exp. 5 showed it is not fixable by
reweighting.

---

## 2. Operation representation

**D1 — the operation text.**

```
T(Oᵢ) = [METHOD] m [NAME] n [PATH] p [PARAMS] par [SCHEMA] s
```

**The description is deliberately absent from `T(Oᵢ)`** and enters only through
feature f6. This is revision **R2**, and it fixes two distinct faults in the
earlier design:

1. The description appeared inside the f1 embedding text *and* as f6, which
   double-counted documentation semantics and made the "neutral" 1/6 weights
   silently non-neutral.
2. Worse, a missing description changed the f1 *input text* while the mask still
   reported f1 as available — **defeating the mask**, which is the core
   theoretical claim.

With disjoint texts, f1 captures structural semantics, f6 captures documentation
semantics, and **each missing field is visible to exactly one mask term**. There
is a regression test for this (`src/test_similarity.py::test_r2_description_isolation`)
which fails on the previous design: deleting one operation's description leaves
f1 bit-identical at 0.662798 while `m_f6` flips 1 → 0 and `Sim` still computes.

---

## 3. The six features

| | Content | Similarity | Availability |
|---|---|---|---|
| **f1** embedding | SBERT of `T(Oᵢ)` — no description | cosine | always |
| **f2** name | operationId tokens | Jaccard | masked |
| **f3** path | normalised path tokens | Jaccard | masked |
| **f4** params | parameter-name tokens | Jaccard | masked |
| **f5** schemas | domain schema names | **overlap coefficient** | masked |
| **f6** description | SBERT of the description | cosine | masked |
| **f7** co-usage | *reserved*, mask ≡ 0 | — | never |

**f5 uses the overlap coefficient, not Jaccard**, because any shared domain
structure implies a relationship: `|A ∩ B| / min(|A|,|B|)`, so a subset scores
1.0. That choice is what makes generic-schema exclusion necessary — an
infrastructural type present on every operation would saturate it.

**f7 is reserved with a permanently zero mask.** It is a dynamic-phase hook that
makes this Phase 1 of a programme rather than a standalone study. It contributes
nothing and is not a seventh weight; `test_f7_is_not_in_the_aggregation` asserts
that the weight vector has exactly six entries.

**Preprocessing exclusions.** Administrative endpoints are stripped (D-07): a
12-entry list matched on the *whole* path, so `/orders/{id}/status` survives and a
bare `/status` does not — 62 endpoints across 48 services. Generic schemas are
excluded from f5: a fixed list (`Error`, `Pagination`, `Status`, …) plus **any
schema appearing on more than 80% of a service's operations**.

> **An asymmetry the paper must resolve (F-05).** That 80% rule applies to f5 and
> **not to f4**. Google attaches six identical parameters to 100% of its 10,103
> operations; AWS attaches seven `X-Amz-*` signing headers to 99% of its 11,843.
> Nothing in the argument for excluding an infrastructural *schema* depends on it
> being a schema. Applying the same rule to f4 would affect **67.6%** of all
> services. It has not been applied, because changing a feature after seeing which
> services it favours is not a decision this study is willing to make quietly —
> but the definition is currently inconsistent and the paper must either adopt the
> exclusion or explain the asymmetry.

---

## 4. The availability mask — the theoretical claim

**D3.** `m_ijk = 1` iff **both** operations of the pair carry feature *k*.

```
Sim(Oᵢ,Oⱼ) = Σₖ ( wₖ · m_ijk · simₖ ) / Σₖ ( wₖ · m_ijk )
```

The weights **redistribute over whatever both operations actually have**, so
**absence never counts as dissimilarity**. This is the metric's central
contribution (C1) and the reason it tolerates incomplete specifications — which
real specifications systematically are: the mask fires on **56.9%** of
within-service pairs in the primary corpus.

**Two definitional points the implementation had to settle.**

- **An empty set is unavailable, not zero (D-19).** Jaccard is 0/0 on an empty
  set. Returning 0 would assert dissimilarity from an absence — exactly what the
  mask exists to prevent; returning 1 would assert identity. So an `operationId`
  of `"v1"`, non-empty but tokenising to nothing, leaves f2 *unavailable*. Cost:
  under **0.6%** of operations on the worst-affected feature.
- **Cosine is clamped to [0,1] (D-20).** ILSC is defined on [0,1] and mixes
  cosine with Jaccard, which cannot go negative. The aggregation has no way to
  express opposition, so a negative cosine reads as "no similarity". This fires
  on **2.25%** of f1/f6 values — one in forty-four, which is worth reporting
  rather than dismissing.

**f2's availability is a factual property of the string, not a judgement.** An
`operationId` counts only if it is not a code-generator signature (D-08): a path
baked into the name (`foo/bar`, `{id}`), a `usingGET` suffix, a `_1`
disambiguator, or — added after the sanitised form was found to escape the
original test — an HTTP-verb prefix together with a doubled or trailing separator
(`get_reference_files__channel_code`, D-23).

---

## 5. Aggregation

```
ILSC_mean(S) = ( 2 / n(n−1) ) · Σ_{i<j} Sim(Oᵢ,Oⱼ)
ILSC_τ(S)    = |{(i,j) : Sim ≥ τ}| / ( n(n−1)/2 )        default τ = 0.50
ILSC_norm(S) = ( ILSC_mean − E[ILSC_rand(n)] ) / ( 1 − E[ILSC_rand(n)] )
```

**Special cases.** A pair with no shared available feature scores `Sim = 0` and
is counted; in practice this never occurs, because f1 is always available.
`ILSC_norm` is reported **unclipped** — a negative value means the service is
less coherent than an arbitrary bag of operations, which is informative, not an
error. (No service in the corpus is: the minimum ILSC_mean is 0.1248 against an
E[ILSC_rand] of 0.1011.)

---

## 6. The null models

Two, both reported (Sec. 6), 400,000 Monte-Carlo pairs each.

- **Global** — random operations from the whole corpus. Answers *"is this service
  more coherent than an arbitrary bag of API operations?"*, a weak bar.
  **E[ILSC_rand] = 0.1011** (SE 0.0001).
- **Provider-restricted** — random operations from services sharing a provider.
  **Median 0.2370**, with **96 of 97** estimable providers above the global
  figure. The harder question, and the gap between the two normalisations is
  itself the reportable finding Sec. 6 asks for.

**Provider replaces the specified *domain* restriction (D-18)** because no domain
labels survive: keyword labelling was rejected at 52% agreement with a blind
human sample (D-03) and LLM labelling was rejected as circular and unpinnable
(D-04). Provider is metadata, needs no annotator, and is the same substitution
already accepted for the perturbation control (D-05). **It is a conservative
approximation**: a provider is coarser than a domain — AWS spans storage,
compute and billing — so the provider-restricted null is closer to the global one
than a true domain null would be.

**Two implementation points that matter.** Pairs drawn from the *same service*
are resampled, because a bag assembled by chance would rarely contain two
operations from one service and leaving them in imports exactly the within-service
coherence the null exists to be free of. And a provider whose operations all sit
in a single service has no cross-service pair to draw at all — 103 such providers
fall back to the global expectation, marked in the output.

**E[ILSC_rand(n)] does not depend on n (D-21).** ILSC_mean is a mean over
exchangeable pairs, so its expectation equals that of a single random pair for
every n. Verified at seven sizes with 1,000 full draws each: the spread across
n = 3…200 is **0.00203**.

> **Consequence, and it constrains what may be claimed.** If E is constant, then
> `ILSC_norm` is an **affine rescaling of `ILSC_mean` with constant
> coefficients**. It cannot reorder services. Every rank-based result — Gate 1,
> Kendall's W, the quartile ordering — is identical on either, so `ILSC_norm` is
> worth reporting for interpretability ("how far above chance") and **must not be
> presented as independent evidence**.

---

## 7. What the metric's own validation revealed about it

**Gate 1 is MARGINAL, and the reason is a construct property (D-24).** Five
hand-picked cohesive services against five mixed, labelled with written reasons
before any score existed. Cliff's δ **+0.680**, no clean separation — and the
verdict turns entirely on **Xero Payroll AU**, a *cohesive* candidate scoring
0.2923, below four of the five mixed. Remove it and the split is perfect
(δ +1.000).

Its tokens are correct. It covers roughly ten distinct resources inside one
business capability, and the lexical overlap between `employees` and `superfunds`
is genuinely zero. **No weighting rescues it**, and Sec. 10's own suggested
remedy — upweight path and schema — makes separation *worse* (δ +0.600).
Exp. 5 explains why: Kendall's W across the ±20/40% weight family is **0.9947**,
so no reasonable reweighting moves any ranking at all.

This is the evidence for the resource-vs-capability distinction in §1, and it
belongs in the metric's definition rather than only in Threats to Validity.

**The six features are not redundant.** Maximum inter-feature Spearman is
**0.582** (f1–f2), well below the 0.85 threshold set in advance. f1 correlates
most with everything, which is expected — `T(Oᵢ)` is built from the same
material f2–f5 measure discretely — and f5 is the most independent of the lexical
features (ρ ≤ 0.27), which is what justifies giving it a different similarity
function.

**But f1 carries the largest share.** `f1_only` reaches ρ = **0.8374** against
the full metric. The honest framing is *"f1 carries most of the ranking signal
and the other five refine it"*, not *"six equally contributing features"*.

**Face validity, unplanned and independent.** The lowest-scoring service among all
2,206 is **NeutrinoAPI** — the Gate 1 candidate labelled *mixed* on the strength
of its author declaring six unrelated domains. The label was written before any
score existed and the corpus ranking was computed without reference to it.

---

## 8. Parameters, pinned

| | Value | Fixed by |
|---|---|---|
| Weights | 1/6 each | Sec. 6; swept in Exp. 5 (W = 0.9947) |
| τ | 0.50, grid 0.30–0.70 | `config.TAU_DEFAULT` |
| Embedding model | `all-MiniLM-L6-v2` | `config.EMBEDDING_MODEL` |
| Generic-schema ratio | > 0.80 of a service's operations | `config.FREQUENT_SCHEMA_RATIO` |
| Token stopwords | `get, post, api, v1, v2` | Sec. 8, pinned |
| `DROP_VERSION_TOKENS` | `True` | D-15; swept, ρ = 0.998 |
| Seed | 42 | `config.SEED` |

**Three of these were swept rather than asserted**: the weights (Kendall's W
0.9947), τ (smooth, no discontinuity), and the tokenisation knob (ρ 0.998
corpus-wide, but **+0.027** on the 74 services it touches — negligible globally,
real locally, and the pinned setting is the conservative one).

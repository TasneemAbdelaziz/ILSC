# Related Work and Positioning — draft

*Writing-schedule Day 6, theory half. Sections 1–2 of the paper. The positioning
claim here is deliberately narrower than the proposal anticipated, because
Experiment 4 did not return what it hoped for.*

---

## 1. Three gaps

### Gap 1 — Runtime dependency

Metrics such as `Cohesion = (Nap + Nop)/2` (Rojas-Pérez et al. 2025) and SIUC
require execution traces. Those are unavailable for proprietary systems,
non-reproducible because they are workload- and window-dependent, and
contaminated by health checks and synthetic traffic.

A further problem is rarely stated: **absence of an operation from a trace is not
evidence of non-use, only of non-observation within the window.** A trace-based
cohesion metric silently treats a rarely-exercised operation as absent.

ILSC needs no runtime data, no source access, and no cooperation from the
system's owners. That is the method's main advantage and the source of its main
limitation (§3).

### Gap 2 — Structural and lexical analysis without meaning

**SIDC** (Perepletchikov et al. 2007) derives interface cohesion from shared
parameter and return **data types**. **LoCmsg** (Athanasopoulos et al. 2015)
measures message-level lack of cohesion by term matching on WSDL. Neither
captures meaning: `Customer` and `Client` look unrelated to both, while "order"
(a purchase) and "order" (a sequence) look related.

**We can now put a number on that gap, and it is not the number we expected to
report.** Over 2,136 services:

| | ILSC | SIDC | 1 − LoCmsg |
|---|--:|--:|--:|
| services scoring a perfect 1.0 | **0.0%** | 35.8% | **77.0%** |
| corpus interquartile range | **0.167** | 0.862 | **0.0000** |
| distinct values | **1,645** | 681 | 350 |

`LoCmsg`'s interquartile range is **exactly zero**: at least half the corpus
receives an identical score, so it cannot rank the middle of the distribution at
all. `SIDC` correlates with ILSC at ρ = **+0.138** (p = 1.8e−10) — the two are close
to unrelated, so SIDC is not a noisy version of ILSC, it measures something else.

**Spread is description, not validity.** ILSC is a mean of six continuous
similarities and the baselines are proportions over pair counts, so a wider spread
shows ILSC is more *continuous*. The claim that survives is in §2b: on an external
ground truth, ILSC **predicts code-level relatedness better than both baselines on
hand-written specifications**. See §2 for the claim we do *not* have.

### Gap 3 — No unified static metric for OpenAPI

Decomposition tools (Service Cutter, Gysel et al. 2016; MicroQA) and clustering
approaches (Al-Debagy & Martinek 2020) combine multiple criteria but provide no
standalone, normalised cohesion metric that **tolerates incomplete
specifications** — even though real specifications are systematically incomplete.

That last clause is the contribution. The availability mask fires on **56.9%** of
within-service pairs in the primary corpus: a metric that treated a missing field
as dissimilarity would be reporting documentation quality more than cohesion for
over half of all comparisons.

---

## 2. The claim Experiment 4 does **not** support

Sec. 10 of the proposal anticipated: *"If ILSC's foreign-vs-control gap is larger
than theirs, that is a direct, quantitative superiority claim — the strongest
single result available from Exp. 2 + 4."*

All three metrics were run through an identical perturbation, scoring the **same
injected operations**:

| metric | gap (cross-provider − same-provider) | in corpus SD |
|---|--:|--:|
| **ILSC** | −0.0223 | −0.179 |
| SIDC | −0.0185 | −0.045 |
| **LoCmsg** | **−0.0535** | **−0.256** |

- **Against SIDC the claim holds** — larger gap raw and standardised, and ILSC
  discriminates on 20/20 services against SIDC's 16/20.
- **Against LoCmsg it does not.** LoCmsg's gap is larger on both measures.

**The paper must report this rather than quietly substituting the corpus
comparison for it.** The context is real but it is a qualification, not a
rescue: LoCmsg scores **exactly 0.000 for all twenty test services before any
perturbation**, so its larger gap is measured from a saturated floor. A metric
that cannot rank unperturbed services but moves when foreign operations arrive is
**detecting an intrusion, not measuring cohesion** — which is a meaningful
distinction and should be argued on its own terms.

**Positioning, stated as the evidence supports it:** ILSC's demonstrated
advantage is not perturbation sensitivity. It is §2b.

### 2b. The claim Experiment 4b *does* support

Against the code dig's entity overlap — an external ground truth neither metric
saw — which better predicts that two operations are related? Both baselines are
decomposed to the pair predicate their definition counts; AUC is used because two
of the three predictors are binary.

| specification origin | **ILSC** | SIDC | LoCmsg |
|---|--:|--:|--:|
| hand-written (Sock Shop) | **0.794** [0.767, 0.825] | 0.574 | 0.651 |
| generated (Train Ticket) | 0.739 | 0.917 | **0.953** |

**On hand-written specifications ILSC wins with separated intervals.** On
generated specifications the lexical baselines win, because **81%** of such a
specification's schema vocabulary is the code's own type vocabulary (15% for
hand-written): a name-matching metric there reads the code through a wrapper.
Provenance does not merely inflate an interface-versus-code correlation — it
**inverts which metric looks best**. Train Ticket is a standard benchmark whose
specifications are code-derived, so this is a reusable warning for the field.

---

## 3. What this work does not claim

**Not a replacement for code-level cohesion metrics.** ILSC is an interface-level
proxy, and Experiment 3 measures how good a proxy it is rather than assuming it:
ρ = 0.409 (hand-written specs) and 0.486 (generated), both in the band the
proposal designated for the honest reframing *"moderate correlation,
complementary signal"*. The interface and the code carry **partly independent**
information. That is a weaker claim than "valid proxy" and a more interesting one.

**Not a measure of capability-level cohesion.** ILSC measures resource-level
coherence. A service can serve one business capability through ten unrelated
resources and score low — Gate 1 found exactly that case, and Exp. 5 showed it is
not a weighting artefact (Kendall's W 0.9949).

**Not "the first" anything unqualified.** Al-Debagy & Martinek (2020) already
applied embeddings to operation names. The novelty claimed here is narrower and
checkable: **a normalised interface-cohesion metric with an availability-aware
weighting scheme**, motivated by empirically measured specification
incompleteness and made sound by disjoint feature texts.

---

## 4. Positioning table

| Work | What it did | Limitation | What ILSC changes |
|---|---|---|---|
| Rojas-Pérez et al. 2025 | Cohesion from endpoint/operation usage; 41 microservices | Needs runtime traces; observation-window bias; no semantics | Static; no traces; semantic features |
| Perepletchikov et al. 2007 (**SIDC**) | Interface cohesion from shared parameter/return types | Data-type only; ignores names, paths, descriptions, meaning | Six features incl. embeddings; **SIDC saturates on 35.8% of the corpus, ILSC on 0.0%** |
| Athanasopoulos et al. 2015 (**LoCmsg**) | Message-level lack-of-cohesion by term matching on WSDL | Lexical only; WSDL/SOAP-oriented | OpenAPI-native; **LoCmsg's corpus IQR is 0.0000** — it cannot rank the middle half |
| Al-Debagy & Martinek 2020 | Embeddings over operation names for decomposition | Names only; no normalisation; no incompleteness handling | Six disjoint features; null-model normalisation; the availability mask |
| Bogner et al. 2020 (**RAMA**) | Quartile thresholds for 10 maintainability metrics over 1,737 API descriptions | Its cohesion metrics are structural/lexical | Thresholds derived the same way, **S1-only so they are comparable**; and see the hyperscaler caveat (D-25) |
| Gysel et al. 2016 (Service Cutter) | 16 coupling criteria for decomposition | Decomposition, not measurement; no standalone metric | A standalone, normalised metric |

---

## 5. Contributions, as the results actually support them

**C1 (theoretical).** A formal ILSC definition with **availability-aware pairwise
similarity** and null-model normalisation. The mask is the novelty: it is
motivated by measured incompleteness (it fires on 56.9% of pairs) and made sound
by disjoint feature texts, so that a missing field is visible to exactly one mask
term. A regression test enforces the disjointness and fails on the earlier design.

**C2 (empirical).** Triple validation without runtime ground truth:

1. **Controlled perturbation with a size-matched control** — 20/20 services
   perfectly monotonic; degradation slopes order with semantic distance
   (−0.037 / −0.065 / −0.088); the gap is negative for 20/20, p < 1×10⁻⁶.
2. **Pair-level code correlation on benchmark systems**, reported separately for
   hand-written and generated specifications and never pooled — which also yields
   a **+0.078** estimate of how much specification–code derivation inflates such
   a correlation, a quantity a single-system design cannot produce.
3. **Head-to-head against SIDC and LoCmsg**, qualitatively and under an identical
   perturbation — with the perturbation result reported as it fell (§2).

**C3 (methodological), added because the study produced it.** A decision record
of 25 entries and 5 open flags in which the **rejections carry numbers**: keyword
domain labelling rejected at 52% agreement against a blind human sample, LLM
labelling rejected as circular, and the oversized-specification cap justified by
a 50-point swing in pair-weighted statistics. A rejection with a measurement
attached is a reusable methodological result, not project bookkeeping.

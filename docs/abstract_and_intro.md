# Abstract and Introduction — draft

*Writing-schedule Day 7, theory half. Every number is from `results/`. Where a
result went against the hypothesis, the draft says so — a paper whose abstract
reports only its successes invites the reviewer to find the rest.*

---

## Abstract

Service cohesion is a core design property of microservice architectures, but
existing measures either require runtime traces — unavailable for proprietary
systems and biased by the observation window — or reduce cohesion to structural
and lexical overlap that cannot distinguish `Customer` from `Client`. We propose
**ILSC (Interface-Level Semantic Cohesion)**, a static metric computed entirely
from an API contract.

ILSC combines six similarity features — a sentence-embedding of a structured
operation text, token overlap on names, paths and parameters, domain-schema
overlap, and a separate embedding of the description — under an **availability
mask**: a feature contributes only when *both* operations of a pair carry it, and
the weights redistribute over what remains, so **a missing field never counts as
dissimilarity**. This matters because specifications are systematically
incomplete: the mask fires on **56.9%** of within-service operation pairs in our
corpus.

We evaluate on **2,206 services (97,912 operations)** curated from two pinned
sources, one of them a peer-reviewed corpus, and on two benchmark microservice
systems. Under controlled perturbation with a size-matched control, ILSC degrades
monotonically for **20 of 20** services and degrades significantly faster when
the injected operations come from a more distant provider (paired gap negative
for 20/20, *p* < 10⁻⁶). Against code-level entity overlap, interface similarity
correlates at **ρ = 0.43** on hand-written specifications and **ρ = 0.49** on
specifications generated from source — a moderate, complementary signal rather
than a substitute for code-level analysis, and a **+0.05** estimate of the
inflation that specification–code derivation introduces. Service rankings are
robust to the weighting (Kendall's *W* = **0.99** across ±40% perturbations) and
to the threshold.

Compared with SIDC and LoCmsg, ILSC's advantage is **discriminating power**: it
assigns a perfect score to **0.0%** of the corpus where they saturate on 35.8%
and 77.0%, and LoCmsg's interquartile range is exactly zero. It does **not**
degrade more sharply than LoCmsg under perturbation, and we report that. We also
find that ILSC measures *resource-level* rather than *capability-level* cohesion —
a service spanning one business capability through many unrelated resources
scores low — and that services from the three largest cloud providers, **48%** of
the corpus, score **0.13** higher at the median, which constrains how published
thresholds may be read.

---

## 1. Introduction

### 1.1 The problem

Cohesion — the degree to which the elements of a module belong together — is one
of the oldest design properties in software engineering and one of the least
measurable in a microservice architecture. A microservice is defined by its
contract, deployed independently, and frequently owned by a team that will not
share its source. The properties a maintainer most wants to know are precisely
the ones hardest to observe.

Existing approaches fail in three ways.

**They require runtime data.** Trace-based cohesion needs execution logs, which
are unavailable for third-party services, non-reproducible across workloads, and
contaminated by health checks. Worse, the absence of an operation from a trace is
not evidence that it is unused — only that it was not observed in the window.

**They ignore meaning.** SIDC counts shared data types; LoCmsg matches terms on
WSDL. Neither can see that `Customer` and `Client` are the same concept, or that
"order" (a purchase) and "order" (a sequence) are not.

**They assume complete inputs.** Real specifications are not complete. In our
corpus, `operationId` is usable on 84.9% of operations, parameters on 90.7%,
domain schemas on 78.7%, and a description on **73.0%**. A metric that reads a
missing description as evidence of dissimilarity is measuring documentation
quality and calling it cohesion.

### 1.2 The idea

ILSC scores each within-service operation pair on six features and averages over
all pairs. The contribution is not the feature set but the **availability mask**:

```
Sim(Oᵢ,Oⱼ) = Σₖ ( wₖ · m_ijk · simₖ ) / Σₖ ( wₖ · m_ijk ),   m_ijk = 1 iff both carry k
```

The denominator is the weight actually available, not the total weight, so
**absence is excluded from the comparison rather than counted against it**.

Making that sound required a design constraint that is easy to miss: the feature
texts must be **mutually disjoint**. An earlier version of this metric included
the description inside the embedded operation text *and* scored it separately, so
deleting a description changed the embedding while the mask still reported the
embedding as available — the mask was defeated by its own inputs. The texts are
now disjoint and a regression test enforces it.

### 1.3 What we found, including what we did not want to find

**The mask is justified by measurement, not assertion.** It fires on 56.9% of
within-service pairs; for the median service outside the three largest cloud
providers, it fires on **100%**.

**Perturbation behaves as the theory requires, against a control.** "ILSC falls
when you inject a foreign operation" is close to tautological for a mean-similarity
score. The evidential content is the *contrast*: degradation slopes order with
semantic distance (−0.041 same-service, −0.067 same-provider, −0.098
cross-provider), and the paired gap is negative for 20 of 20 services.

**The correlation with code is moderate, and we reframe rather than overclaim.**
ρ = 0.43 against code-level entity overlap on hand-written specifications. Its
cluster-bootstrap interval, [0.32, 0.64], straddles the 0.4 threshold we set in
advance, because only two of four benchmark services have any code-side variance.
We report the interval rather than the point estimate, and read the result as
*complementary signal* rather than *validated proxy*.

**Two findings run against the metric and are reported as such.** ILSC measures
resource-level cohesion, so a payroll service spanning ten unrelated resources
scores below services we labelled incohesive — no weighting fixes this, and the
sensitivity analysis shows why. And ILSC does not out-discriminate LoCmsg under
perturbation, though it out-discriminates both baselines on the corpus by a wide
margin.

### 1.4 Contributions

1. **ILSC**, a static interface-cohesion metric with an availability-aware
   weighting scheme and null-model normalisation, defined so that incompleteness
   is excluded from a comparison rather than penalised.
2. **A three-way validation without runtime ground truth** — controlled
   perturbation against a size-matched control, pair-level correlation against
   code-level entity overlap on two benchmark systems, and a head-to-head against
   two published baselines under an identical procedure.
3. **Quartile thresholds over 2,206 services** derived as Bogner et al. derive
   theirs, reported per source population — together with the finding that the
   three largest cloud providers score 0.13 higher at the median, which any user
   of such thresholds needs.
4. **A decision record whose rejections carry numbers** — keyword domain
   labelling rejected at 52% agreement against a blind human sample, LLM
   labelling rejected as circular with the metric under test, and oversized
   specifications capped on a scope argument that moves pair-weighted statistics
   by up to 50 points.

### 1.5 Scope, stated once and kept

ILSC measures the semantic density of the operations a service **declares**. It
is positioned as a *proxy* for service cohesion, and the validity of that proxy
is the object of Experiment 3 rather than an assumption. Everything the metric
sees is in the contract; everything else — implementation structure, runtime
coupling, team ownership — is out of scope by construction.

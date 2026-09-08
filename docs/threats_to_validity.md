# Threats to Validity — draft

*Day 13 deliverable. Drafted from the decision log and the results, so every
threat here is one the study actually met, with the number attached. Threats
that were anticipated and did not materialise are marked as such rather than
listed for completeness.*

---

## 1. Construct validity — does ILSC measure cohesion?

**ILSC is an interface-level proxy and is named that way on purpose.** Service
cohesion in the full sense is a property of the implementation. ILSC measures
the semantic density of the operations a service *declares*, and the validity of
that proxy is not assumed — it is the object of Experiment 3. This is why the
metric is not called "service cohesion".

**The sharpest construct threat is one the study found rather than predicted.**
Gate 1 **FAILS** (Cliff's δ +0.200, p 0.36, no clean separation), and one
candidate is the clearest case: **Xero Payroll AU**, hand-labelled *cohesive*
before any score existed, which scores 0.2058 — the lowest of the cohesive
group. Its tokens are clean and its features are measuring
correctly: f2 = 0.059 and f3 = 0.093 because roughly ten distinct payroll
resources (`employees`, `leave applications`, `pay runs`, `superfunds`) genuinely
share no lexical material.

**The conclusion is that ILSC measures *resource-level* cohesion, not
*capability-level* cohesion.** A service can be one business capability spread
across many unrelated resources, and the two notions come apart exactly there.
This should be stated in the metric's definition, not only in this section.

Two lines of evidence say this is a construct property rather than a defect:

- **No weighting rescues it.** Four schemes were tried, including Sec. 10's own
  suggested remedy (upweight path + schema), which made separation *worse*
  (δ +0.600, and it destroyed the clean split that survives without C1).
- **Exp. 5 explains why.** Kendall's W across the ±20/40% weight family is
  **0.9949**; no reasonable reweighting moves any ranking, so no reweighting
  could have moved C1.

**The original gate failed, and the reason is a selection defect (D-27).** Before
D-26 removed the f4 boilerplate inflation it read MARGINAL. The exclusion moved
the cohesive candidates — three of five are hyperscalers — and left four of five
mixed ones untouched, so part of the earlier separation was ILSC separating
*providers*. **Re-run with provider held constant, it passes (D-29):** sixteen
publishers each contributing one single-capability and one many-capability
service, 14 of 16 in the predicted direction, p = 0.002, and 11 of 12 label
boundaries agree. The residual threat is the label itself — an author's tag
count is chosen for independence from the metric, not for fidelity to what a
practitioner means by cohesion — and sixteen providers is a modest sample.

**The corpus-scale face-validity check is independent of all that, and stronger:** the lowest-scoring service among all 2,206 is **NeutrinoAPI**, which is
the Gate 1 candidate labelled *mixed* on the strength of its author declaring six
unrelated domains. The residual risk is that a reader takes ILSC as a measure of
capability coherence; the paper must foreclose that reading explicitly.

---

## 2. Internal validity — are the results driven by our choices?

**Weights: answered, not argued.** H3 was tested over 2,136 services and 29
configurations. Kendall's W = **0.9949** on the ±20/40% family and 0.9671
including deliberately extreme schemes; the worst single ±40% perturbation still
ranks at ρ = 0.9896 against baseline. The equal 1/6 weighting is defensible
because **the choice barely matters**, not because it was tuned.

**One weight result deserves its own sentence rather than burial.** `f1_only` —
five features switched off — reaches ρ = **0.8083** against the full metric. f1
carries the largest share of the ranking signal and the remaining five refine it.
That is a weaker claim than "six equally contributing features" and it is the one
the data supports. Fig 9 keeps it from collapsing further: no feature pair
correlates above **0.558**, so the five are not redundant *with* f1, they are
simply smaller contributors.

**τ: swept, and 0.50 is a position not an optimum.** Across 0.30–0.70 both edge
density (0.590 → 0.083) and component count (1.58 → 15.38) move smoothly with no
discontinuity. τ = 0.50 sits mid-range on both, which is the argument for it.

**Tokenisation (D-15): swept, and it is not free.** `DROP_VERSION_TOKENS`
changes the tokenizer and therefore the f1 embeddings, so it required a full
re-parse and re-embed rather than a reweighting. **2.70% of operations across 80
services tokenise differently.** See §7 for the outcome.

**Two floor effects, both measured rather than assumed.**

- **Cosine clamping (D-20).** f1/f6 cosines below zero are read as 0. This fires
  on **2.25%** of values — one in forty-four, not the "rare" the decision
  originally claimed. Each clamped pair is recorded as maximally dissimilar
  rather than opposed, which compresses the bottom of the ILSC range.
- **Empty feature sets (D-19).** A present-but-empty token set is treated as
  *unavailable* rather than zero, because Jaccard is 0/0 there and returning 0
  would assert dissimilarity from an absence — precisely what the mask exists to
  prevent. Cost: under **0.6%** of operations on its worst feature (f3).

**A declared inconsistency between two corpora (D-14).** The Day 3 availability
statistics describe `specs/clean/` (as published) while the mask runs on
`specs/clean3/` (converted). The gap is **f4 96.41% vs 91.04%** across the 144
converted 2.0 services, making the reported pair-level f4 co-availability about
five points optimistic. A stated five-point discrepancy on one feature is a
limitation; an unstated one would be a defect.

---

## 3. External validity — does it generalise?

**Provider concentration is the largest threat, and it is worse in the
peer-reviewed half.** 616 providers over 2,206 services; AWS, Google and Azure
hold **46.8%** of the corpus. Split by source, S1 (RAMA) is **58.1%**
hyperscaler against S2's 37.4% — reusing a published corpus buys comparability
with Bogner, **not** diversity, and Sec. 7 of the proposal implied both.

**The two sources are not interchangeable populations.** S1 scores about **0.05
higher than S2 at every quartile** of ILSC_mean. Any threshold quoted in the
paper must name the population that produced it; the S1-only quartiles are the
Bogner-comparable ones.

**D1 is resolved and the answer is a first-order limitation (D-25).** The
thresholds **do** move under a provider cap — the median falls 0.3658 → 0.3430 at
a cap of 50, and → 0.3244 at a cap of 5, against 0.0018 of sampling noise. The
cause is that AWS, Google and Azure services score a median **+0.134** above
everyone else (Cliff's δ **+0.609**, p ≈ 4×10⁻¹²⁴) while being **48.0%** of the
primary corpus. The decision is to stratify and report rather than cap, because
capping would delete data to hide an effect that is itself a finding — but the
consequence is that **an uncapped threshold is close to half a statement about
three companies** and must never be quoted without its population.

**Part of that gap is the metric's fault, not the corpus's (F-05).** Sec. 6
excludes infrastructural schemas from f5 by an ">80% of operations" rule; f4 has
no equivalent, so Google's six universal query parameters and AWS's seven signing
headers inflate f4 to a median of 0.82 against 0.42 elsewhere. Applying f5's own
rule to f4 closes **46.6%** of the hyperscaler gap and would change **67.6%** of
all services. The metric has not been changed — changing a feature after seeing
which services it favours is the move this study refuses elsewhere — but the
paper must either adopt the exclusion or explain why one feature has the rule and
its neighbour does not.

**The rest of the gap is real and unfixable.** Hyperscaler specifications are
near-complete: the mask fires on **12.5%** of their pairs against **100%** for
the median service elsewhere. A metric that rewards completeness will rank
well-documented APIs above poorly-documented ones, which is defensible as a
statement about *interfaces* and indefensible as a statement about the
*services behind them*.

**The corpus is public API descriptions, not microservices.** This is inherent
to a static, specification-only method and is the price of the method's main
advantage — it needs no runtime traces, no source access, and no cooperation
from the system's owners.

**Oversized specifications are held out of the primary analysis (D-17).**
Seventy services above 200 operations describe API gateways rather than
single-capability microservices. They hold **97.6%** of all within-service pairs,
so every pair-weighted statistic was effectively a statement about a handful of
documents. All analyses are reported primary *and* sensitivity.

**The corpus count is ~0.9% high** pending F-02: twenty near-duplicate services
survive the dedup key because the same API is published under sibling hostnames.

---

## 4. Conclusion validity — do the numbers support the claims?

**Gate 2 passes on a threshold its own confidence interval straddles.**
ρ_independent = **0.409**, but pairs inside a service are not independent
observations — they share operations. The cluster bootstrap, which resamples
*services*, gives **[0.318, 0.643]** against the pair bootstrap's [0.268, 0.572].
The cluster interval **crosses 0.4**, so the primary condition cannot be said to
clear Gate 2's own bar with confidence. This is reported, not rounded past.

**The reason is F-04, and it is structural.** Sock Shop's code side takes **five
distinct values across 122 pairs**, and only **2 of 4** services have any
code-side variance at all: `carts` and `orders` are constant, because they are
genuinely single-aggregate services. ρ_independent is therefore close to a
single-service result on `user`. D-16 had already established that the
independent-spec condition rests on one system; F-04 narrows it to effectively
one service.

**The better-powered condition is the one quarantined for circularity.**
ρ_derived = 0.486 over 790 pairs and 29 services with variance, but Train
Ticket's specifications were generated from its own code by Springfox
introspection, so the correlation is partly circular by construction. The two are
never pooled.

**The inflation that circularity buys is small and now measured: +0.053.** That
is the return on D-16's two-condition design — a single-system study could not
have produced it — and it says specification–code derivation inflates this
correlation by about five points, not enough to manufacture a finding.

**Both coefficients are conservative in one specific respect.** `Sim_code`
matches entity names exactly, so `Assurance` and `AssuranceType` score 0.00
despite being plainly related. Every such case pushes a pair toward "code says
unrelated" while the interface says related, biasing ρ **downward**. It was left
unfixed deliberately: changing `Sim_code` after seeing ρ has to be declared, and
any change must apply identically to both systems or the D-16 comparison breaks.

**Gate 1 is a ten-service test and its p-value should be read with that in
mind.** The smallest attainable one-sided p with 5 versus 5 is 0.0040; the
observed 0.0675 reflects a design with almost no power, and the effect size and
the clean-split criterion carry more than the p-value does.

**Heavy ties throughout the code-side variable.** 5 levels for Sock Shop, 16 for
Train Ticket, with the largest tie holding 27.9% and 33.2% of pairs respectively.
Spearman is used throughout for this reason; Pearson would assume more than the
variable supports.

---

## 5. Reliability — single-annotator extraction

**This is the study's weakest methodological point and it is not yet closed.**

- **Sock Shop's 27 endpoint entity sets were derived by one reader**, with no
  independent re-derivation. A blank ten-endpoint sample sheet is prepared; a
  second pass by the *same* reader would measure memory, not reliability.
- **Train Ticket's extraction has been verified but not blindly.** All ten
  sampled endpoints were re-derived from the Java sources with **10/10 exact
  agreement**, and that pass caught a real bug — entity names were being scoped
  by the controller's imports while the delegated service body imported the whole
  shared module, discarding entities the endpoint genuinely touches. But the
  annotator could see the automated answer, so the figure is *verification*
  (reliable against entities claimed but not present, weaker against entities
  missed), not blind inter-annotator agreement.

**Until a second annotator runs both sheets, the paper must describe entity
extraction as single-annotator with a verification figure only.** An extraction
with no reliability figure is a standard reviewer objection and the proposal
names it explicitly.

**A related provenance caveat (F-03).** The Train Ticket service one-pagers were
written from the OpenAPI surface, not the FudanSELab *Service Guide*, which could
not be retrieved. They are a restatement of one side of the Exp. 3 correlation
and are used for orientation only — never to guide the entity extraction.

---

## 6. Baseline comparison — a claim we do not have

**Exp. 4's superiority claim is only half available, and the paper must say so.**
Sec. 10 anticipated: *"If ILSC's foreign-vs-control gap is larger than theirs,
that is a direct, quantitative superiority claim."*

- **Against SIDC: supported.** ILSC's gap is larger raw and standardised, and it
  discriminates on 20/20 services against SIDC's 16/20.
- **Against LoCmsg: not supported.** LoCmsg's gap is larger, raw (−0.0535 vs
  −0.0223) and standardised (−0.256 vs −0.179).

**The defensible claim is about discriminating power instead.** Over 2,136
services, ILSC saturates at a perfect 1.0 for **0.0%**, SIDC for **35.8%**, and
1 − LoCmsg for **77.0%**; LoCmsg's corpus interquartile range is **exactly
0.0000**, meaning at least half the corpus receives an identical score, and it
assigns the same value to every one of the twenty perturbation-test services
before any injection. A metric that cannot rank unperturbed services but moves
when foreign operations arrive is detecting an intrusion, not measuring cohesion.

That argument is strong. Substituting it for the perturbation-gap claim without
reporting that the latter failed would not be.

---

## 7. Threats that did not materialise

Recorded because a study that lists only realised threats looks selective.

- **Feature redundancy.** The obvious objection to a six-feature metric is that
  the features measure the same thing. Maximum inter-feature Spearman is
  **0.558** (f1–f3), nothing near the 0.85 threshold the proposal set.
- **Null-model choice.** Replacing the rejected domain-restricted null with a
  provider-restricted one (D-18) could have produced a weaker bar; it did not.
  E[ILSC_rand] is 0.0988 global against a **0.2193** provider-restricted median,
  with 96 of 97 estimable providers above global.
- **Size dependence of the normalisation.** E[ILSC_rand(n)] is **flat in n**
  (spread 0.00203 across n = 3…200), exactly as exchangeability predicts.
  Consequence: ILSC_norm is an affine rescaling of ILSC_mean and cannot reorder
  services, so it must not be presented as independent evidence.
- **Perturbation tautology.** H2's v2 form was near-tautological; the
  size-matched control resolves it. All three conditions order as semantic
  distance predicts (−0.037 / −0.065 / −0.088), the gap is negative for **20 of
  20** services, and 20 of 20 are perfectly monotonic.

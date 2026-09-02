# Decision log

Every entry records a choice, the evidence behind it, and what it costs.
Rejected approaches are kept deliberately: a rejection with a number attached
is a defensible methodological step, and several of these belong in the paper.

---

## D-01 · Swagger 2.0 is converted, not discarded

**Decision.** Keep OpenAPI 2.0 specs and convert them, rather than filtering to
3.x only.

**Evidence.** 26.9% of the surviving corpus is Swagger 2.0 (493 of 1,831). All
five Sock Shop benchmark services are 2.0 as well.

**Why it matters.** Dropping 2.0 would remove a quarter of the corpus and bias
the sample toward more recently published APIs — and would have eliminated the
entire benchmark used for the code-correlation study.

---

## D-02 · Structural validation over full spec validation

**Decision.** Gate the whole corpus on a cheap structural check (`paths` and
`info` present and well-formed); run `openapi-spec-validator` on a random
sample only, and report both numbers.

**Reasoning.** Full validation costs roughly 0.5 s per spec and rejects on
details that do not affect ILSC — an unresolvable external `$ref` inside an
example, for instance. The cheap gate removed 62 specs (48 unparseable,
14 structurally unusable).

**Cost.** Some specs that a strict validator would reject remain in the corpus.
This is why the sample-based strict validation number must be reported.

---

## D-03 · Keyword domain labelling — REJECTED

**Decision.** Do not use keyword-based domain labels anywhere in the study.

**Evidence.** Blind manual classification of 50 randomly sampled services
(seed 42) agreed with the automatic labels on **26/50 = 52%**. On the subset
where both sides committed to a label, agreement was 63%.

**Failure modes, both systematic rather than random:**

1. *Provider-level generalisation.* Treating every service from a large cloud
   vendor as `devtools` misclassified AWS Glue (data), YouTube Reporting
   (media), FinSpace (finance), Amazon Chime (communication), Azure SignalR
   (communication). Nine of the twenty-four disagreements came from this.
2. *Brand-name titles.* Telegram, Nordigen, Airbyte, Reverb, Nookipedia and
   Call Control carry no domain-bearing vocabulary at all. Twelve disagreements
   came from this. Lexical matching cannot work on brand names, and roughly 40%
   of real API titles are brand names.

An earlier, unquantified version was worse still: the token `api` appearing in
the `devtools` keyword list absorbed 64.6% of the corpus, including all 39
services from the Indian government portal `apisetu.gov.in`.

**Note on annotation asymmetry.** The human annotator returned `UNLABELLED`
8 times; the automatic labeller returned it 19 times. The human used product
knowledge that no keyword list can encode.

**Paper text.** This result is reportable as-is:

> Lexical domain labelling agreed with manual classification on only 52% of a
> 50-service sample, with errors concentrated in two systematic sources:
> provider-level generalisation and brand-name titles carrying no
> domain-bearing vocabulary. Keyword-based labelling was therefore rejected.

---

## D-04 · LLM domain labelling — REJECTED

**Decision.** Do not use a language model to produce the domain labels that
feed the perturbation control.

**Reasoning — circularity.** ILSC measures semantic similarity with SBERT. A
control condition defined by a second semantic system tests one semantic
judgement against another. Agreement between them is expected a priori and
therefore carries little evidential weight. The reference standard must rest on
a *different* principle from the metric under test — the same reasoning that
makes code-level entity overlap a valid reference in Experiment 3.

**Secondary reasons.** Not pinnable, so not reproducible; cost at corpus scale;
and a language model will confidently label services that have no clear domain,
which is worse than returning `UNLABELLED`.

**Where an LLM remains legitimate.** Building the tooling rather than producing
the data: proposing keyword candidates for human review, or acting as a second
independent annotator in a reliability check where the human annotation remains
the one used. The rule is that an LLM may help *build* instruments but must not
*generate* the data on which results are computed.

---

## D-05 · Provider proximity replaces domain labels — ADOPTED

**Decision.** Define perturbation proximity from specification metadata — the
publishing provider — instead of from any semantic judgement.

**Design.** Three levels, replacing the earlier two-condition design:

| Level | Injected operation comes from | Proximity |
|---|---|---|
| A | the *same service* (duplicate) | closest |
| B | a different service, *same provider* | intermediate |
| C | a different provider entirely | far |

Expected ordering: `ILSC(A) > ILSC(B) > ILSC(C)`.

**Why it is stronger than the two-condition design.**

1. It demonstrates response to a *gradient* rather than to a binary contrast.
2. Level A holds size constant while holding meaning constant too, which
   separates sensitivity-to-meaning from sensitivity-to-size. The v2 design
   could not make that separation, which left H2 close to tautological: a
   mean-similarity metric must fall when a dissimilar element is added.
3. Provider is a metadata field, present for 100% of specs, requiring no human
   judgement and open to no reviewer objection about labelling quality.

**Coverage.** 1,301 of 1,831 services (71.1%) have a provider publishing at
least two APIs and are therefore eligible for the Level B control. The
experiment needs 20 services, so the eligible pool is 65× larger than required.

**Constraint that must be enforced.** Of the 1,301 eligible services, 872 (67%)
come from AWS, Google or Azure. Selection for the experiment must be capped at
roughly three services per provider, or the experiment silently becomes a study
of three cloud vendors.

**Paper text.**

> The perturbation experiment is restricted to services whose provider
> publishes at least two APIs (1,301 of 1,831; 71%). Selection was capped at
> three services per provider to avoid over-representing large cloud vendors.

---

## D-06 · Corpus filters do not apply to benchmark systems

**Decision.** The `< 3 operations` filter applies to the corpus (S1 ∪ S2) only.
All benchmark services are retained regardless of size.

**Evidence.** Applying the corpus filter to Sock Shop would remove `orders`
(2 operations) and `payment` (1 after `/health` removal), leaving three
services. Spearman's ρ on n = 3 cannot reach significance at any effect size.

**Consequence.** The correlation study runs at the **operation-pair** level:
123 within-service pairs from Sock Shop alone, versus 3–5 services. The
service-level correlation is retained as a secondary descriptive result.

---

## D-07 · Administrative endpoints stripped

**Decision.** Remove `/health`, `/ready`, `/live`, `/metrics`, `/actuator/*`,
`/ping` before computing anything.

**Evidence.** Only 49 such endpoints across 40 services in the public corpus —
public APIs rarely publish their own health checks. The effect is large where
it occurs: `payment` in Sock Shop drops from 2 operations to 1.

**Reportable observation.** The near-absence of administrative endpoints in
public specifications is itself worth a sentence, since it distinguishes
published contracts from internal ones.

---

## D-08 · The f2 (name) availability is a three-definition band, not a threshold

**Context.** The RQ2 justification is the *pair-level* co-availability of the
mask features. The mask evaluates `m_ij,k = 1` only when **both** operations of
a within-service pair carry feature `k`, so the per-operation rate is not the
number; co-availability is. Of the six features, f1 (embedding) and f3 (path)
are always available, so the mask can only fire on **f2, f4, f5, f6**.

**Decision.** Feature f2 = `operationId`, "non-empty and not an auto-generated
placeholder". "Placeholder" has no canonical detector, and the choice is a
methodological judgement that must be *visible*, not buried in a threshold. So
f2 availability is reported under **three** definitions, as a sensitivity band:

| Column | Rule | Nature |
|---|---|---|
| `f2_nonempty` | operationId is a non-empty string | under-detects: `getPetsUsingGET_1` is non-empty but useless |
| `f2_codegen` *(PRIMARY)* | non-empty AND not a syntactic code-generator signature (contains `/`, `{`/`}`, `> <VERB>`, `using<VERB>`, or a trailing `_<n>`) | a **factual property of the string**, not a judgement of informativeness |
| `f2_derived` | non-empty AND introduces ≥1 token beyond `{method, path}` tokens | over-detects: misfires on terse but real names like `Get Login` for `/login` |

`f2_codegen` is primary for the headline because it keys on generator
signatures (fact), where `f2_derived` makes a semantic call about
informativeness (judgement) and `f2_nonempty` ignores the placeholder clause.

**Also required.** Report the **distribution** of the mask-fire rate across
services — at minimum quartiles and the count of services at 0% — not just the
corpus mean. A single mean hides a split: "all services ≈50%" and "half at 0%,
half at 100%" give the same mean but different conclusions.

**Evidence (specs/clean, 1,831 services, 328,369,860 within-service pairs).**

- **The f2 choice barely moves the pair-weighted headline.** Mask-fire micro
  across the three definitions spans only **93.23 – 95.93% (2.70 pts)**. For the
  micro (operation-weighted) RQ2 number, the definition does not matter — state
  so.
- **It does move the service-level claim**, which therefore carries a caveat:
  the share of services where the mask matters rises 66.9% → 82.2%, and the
  macro (per-service) mask-fire rises 48.6% → 64.5%, from `f2_codegen` to
  `f2_derived`. This spread belongs in Threats to Validity.
- **The distribution is bimodal, so the mean is the wrong summary.** Under the
  primary definition, **606 of 1,831 services (33.1%) have 0% mask-fire**
  (complete specs the mask never changes) and **574 (31.3%) have 100%**; median
  39.6%, IQR spanning the full 0–100 range. The honest framing is *"the mask
  matters for 66.9% of services"*, not *"average mask-fire 48.6%"*.

**Paper text.**

> The similarity mask is evaluated per operation pair and only where both
> operations carry a feature. Across 1,831 services (328M within-service pairs)
> the mask fires on 93.3% of pairs (operation-weighted); per service the
> distribution is bimodal — 33.1% of services are complete (0% mask-fire) and
> 31.3% incur it on every pair — so the mask materially affects 66.9% of
> services. The operationId "informativeness" definition moves the
> operation-weighted figure by under 3 points but the service-level figure by
> ~15, and is reported as a three-definition sensitivity band.

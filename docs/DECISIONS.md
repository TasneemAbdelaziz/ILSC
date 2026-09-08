# Decision log

Every entry records a choice, the evidence behind it, and what it costs.
Rejected approaches are kept deliberately: a rejection with a number attached
is a defensible methodological step, and several of these belong in the paper.

---

## D-01 · Swagger 2.0 is converted, not discarded

**Decision.** Keep OpenAPI 2.0 specs and convert them, rather than filtering to
3.x only.

**Evidence.** 6.6% of the surviving corpus is Swagger 2.0 (145 of 2,202) once
S1 is included; S2 on its own is 26.9% (493 of 1,831). The gap is not a change
in the world but a property of S1: RAMA converted its inputs upstream (D-10).
All five Sock Shop benchmark services are 2.0 as well.

**Why it matters.** Dropping 2.0 would bias the sample toward more recently
published APIs — and would have eliminated the entire benchmark used for the
code-correlation study.

**Implementation.** `src/convert.py` + `src/convert.js`, using
`swagger2openapi@7.0.8` — the tool the proposal names. It writes `specs/clean3/`
and verifies that the (METHOD, path) operation set is byte-identical before and
after conversion; a mismatch is a hard failure, since a conversion that added or
dropped an operation would silently move every pairwise count downstream.
Until this was written the decision was recorded but not executed: the corpus
carried unconverted 2.0 files and the docstring claimed otherwise.

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

**Implementation.** `src/validate_sample.py` draws `config.STRICT_VALIDATION_SAMPLE`
survivors with `config.SEED` and runs `openapi-spec-validator` on each, writing
`results/strict_validation_sample.csv` and a per-source breakdown. Before it
existed, `openapi-spec-validator` was pinned in `requirements.txt` but imported
nowhere, so the number this decision rests on had never been measured.

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

**Provenance of the validation files — do not regenerate.**
`results/domain_validation_BLIND.csv` and `..._KEY.csv` were drawn (seed 42)
from the **earlier S2-only corpus of 1,831 services**, before S1 was added. The
BLIND sheet carries a *human* annotation, so the pair cannot be rebuilt by
re-running any script: re-drawing the sample against the current 2,202-service
corpus would produce 50 different services with no human labels, and reporting
the 52% figure against that new sample would be fabrication.

The two files are therefore frozen as the historical evidence for this
rejection, and the paper must state the corpus they were measured on. If a
reviewer asks for the check on the current corpus, it needs a fresh round of
manual annotation — roughly an hour — not a re-run.

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

**Coverage.** 1780 of 2202 services (80.8%) have a provider publishing at
least two APIs and are therefore eligible for the Level B control. The
experiment needs 20 services, so the eligible pool is 89× larger than required.
(Adding S1 raised this from 71.1% on the S2-only corpus.)

**Constraint that must be enforced.** Of the 1780 eligible services, 1033 (58%)
come from AWS, Google or Azure. Selection for the experiment must be capped at
roughly three services per provider, or the experiment silently becomes a study
of three cloud vendors.

**Paper text.**

> The perturbation experiment is restricted to services whose provider
> publishes at least two APIs (1780 of 2202; 81%). Selection was capped at
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

**Decision.** Remove `/health`, `/healthz`, `/healthcheck`, `/ready`, `/readyz`,
`/live`, `/liveness`, `/metrics`, `/ping`, `/status`, `/version` and
`/actuator/*` before computing anything.

The match is anchored on the **whole path**, so a domain endpoint that merely
contains one of these words is untouched: `/orders/{id}/status` is kept, a bare
`/status` is dropped.

**Correction.** This list previously read as six entries in the paper and in
`config.ADMIN_PATHS`, while `filter.py` matched twelve with its own regex — and
the corpus was built with the regex. The two are now a single definition,
`config.ADMIN_PATHS_RE`, re-exported by `filter.py` and consumed by
`availability.py`; `config.ADMIN_PATHS` is its plain-language expansion, kept in
sync. The replication package must publish this list, so the mismatch had to be
resolved rather than annotated.

**Evidence.** Only 62 such endpoints across 48 services in the public corpus —
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


---

## D-09 · Cross-source dedup — S1 wins, regardless of version

**Decision.** A service present in both corpora is credited to **S1** and the
S1 *file* is the one retained, even when S2 carries a newer version of the same
API. Within a single source the existing rule is unchanged: keep the newest
version.

**Reasoning.** Sec. 7 makes S1 "the citable anchor". The point of reusing
Bogner's peer-reviewed corpus is that our quartile thresholds are directly
comparable to theirs, and that comparability holds only if the *files* we
measure are the files they measured. Keeping the newer S2 file while labelling
the row `S1` would give us the provenance claim without the property that makes
it worth having.

**Evidence.** The overlap is large and was entirely invisible before this step
existed: **1,854 specs** are removed as `e_cross_source`, against 1,197 removed
by within-source dedup. RAMA was itself built largely from APIs.guru, so most
of S1 reappears in S2 under a newer version.

**Cost, stated plainly.** For the overlapping services the corpus is pinned to
2020-era documents. Field availability on those services is therefore a 2020
measurement, not a current one. This belongs in Threats to Validity: our
recency claim rests on the 1,188 S2-only services, not on the corpus as a whole.

**Requires a normalised host.** The same service appears in S2 as Swagger 2.0
with `host: api.example.com` and in S1 as converted OpenAPI 3 with
`servers[0].url: https://api.example.com/v1`. Deduplicating on the raw strings
matches neither, so `filter.norm_host()` reduces both to a bare netloc before
the `(title, host)` key is formed. Without it, cross-source dedup silently does
nothing.

---

## D-10 · S1 arrives pre-converted — `spec_version` is not as-published there

**Decision.** Record `converted_upstream` per service in the manifest, and never
read the pooled 2.0-vs-3.x split as a statement about how API authors publish.

**Evidence.** RAMA converted every Swagger 2.0 input to OpenAPI 3 before
publishing its benchmark repository (`src/convert-openapi-v2.js` in
`restful-ma/thresholds`). All 2,619 of its OpenAPI files are 3.x. Consequently
**S1 is 100% 3.x by construction**, and the corpus-wide split moves from
26.9% 2.0 (S2 alone) to 6.6% 2.0 (pooled) purely as an artefact of which
sources are mixed in.

**Consequence for Day 3.** The availability study's 2.0-vs-3.x contrast is only
interpretable **within S2**. Pooled, it compares real 2.0 specs against a mix of
real and machine-converted 3.x ones. This is exactly why the availability study
is now stratified by source as well as by version, and why the per-source split
is not optional.

---

## D-11 · Two corpora: `specs/clean/` as published, `specs/clean3/` uniform

**Decision.** Conversion writes a **second** directory rather than overwriting
the first.

| Directory | Contents | Consumed by |
|---|---|---|
| `specs/clean/` | exactly as published — 2.0 stays 2.0, YAML stays YAML | Day 3 availability studies |
| `specs/clean3/` | uniformly OpenAPI 3.x, uniformly JSON | the parser / metric (Day 1-2 Mohamed onward) |

**Reasoning.** The availability study measures *what spec authors wrote*. Running
it over converted files would measure what swagger2openapi emits: conversion
moves a 2.0 `in: body` parameter into a 3.x `requestBody`, so the
`request_schema` and `parameters` rates would both shift, and the
2.0-vs-3.x finding would be erased by the act of measuring it. The metric, by
contrast, wants one uniform input format and does not care how it got there.

**Cost.** Disk. The two directories hold the same services twice.

---

## D-12 · Correction: S1 is 2,619 API descriptions, not 1,737

**Correction to the proposal, Sec. 7.** The proposal sizes S1 as "1,737 API
descriptions". The RAMA benchmark repository at the pinned commit contains
**2,651 API description files — 2,619 OpenAPI, 18 WADL, 14 RAML**. We consume
the 2,619 OpenAPI files; WADL and RAML are out of scope.

1,737 appears to be carried over from a different table in Bogner et al.; it
should not be cited as the size of the corpus we actually use. The proposal text
needs updating before submission.

**A second correction.** Sec. 7 sets a target of "400–600 clean services (≥ 300
from S1)". The pipeline yields **2,202 clean services, 1,014 of them from S1** —
both bounds are comfortably exceeded, and the target sentence should be rewritten
rather than left to look like an unmet constraint.

**Provider concentration differs sharply between the sources**, which is a
finding the multi-source design exists to surface:

| | Services | Providers | AWS + Google + Azure |
|---|--:|--:|--:|
| S1 (RAMA) | 1,014 | 315 | **589 (58.1%)** |
| S2 (APIs.guru) | 1,188 | 460 | 444 (37.4%) |
| pooled | 2,202 | 614 | 1,033 (46.9%) |

S1 — the peer-reviewed anchor — is the *more* concentrated of the two, RAMA
being dominated by Azure. Any claim that reusing a published corpus improves
external validity has to be stated carefully: it buys comparability with Bogner,
not diversity.


---

## D-13 · Dedup ties go to the stable channel, not to whatever sorts first

**Decision.** The dedup key is `(numeric info.version, stability)`. The numeric
part is the documented "keep newest" rule; the stability flag breaks ties, and
only ties. A pre-release (`beta`, `preview`, `alpha`, `rc`, `canary`,
`nightly`, matched in the file path or in `info.version`) never outranks a
higher release number.

**Why this needed a decision at all.** `microsoft.com` publishes Graph twice
under the **identical** `info.title` — `OData Service for namespace
microsoft.graph` — on the same host, with the channel appearing only in the
server path (`/v1.0` vs `/beta`). `host` excludes the path by Swagger 2.0
semantics, so the two collapse to one dedup key, and both declare
`info.version: 1.0.1`. The keys tied exactly, and the survivor was therefore
decided by filename sort order: `graph-beta` sorts before `graph`, so the
corpus kept the **beta** channel (22,361 operations) and discarded **stable
v1.0** (11,422).

**Why that was not a small problem.** That single service accounted for
**95.3% of all 262M within-service pairs** in the corpus. The operation-weighted
("micro") RQ2 headline is therefore, to within a couple of points, a statement
about one Microsoft spec — and which one it was had been settled by a hyphen
sorting below a slash. Reporting a pair-weighted corpus statistic whose value is
set by an incidental sort order is not defensible, so the tie-break is now
explicit and the stable channel wins.

**Related, and still open.** This is also the strongest available argument for
resolving **D2** (oversized services). Even after the fix, 70 services with more
than 200 operations hold **99.3%** of all pairs, and the largest single service
holds the bulk of that. Any pair-weighted corpus number is a statement about a
handful of mega-specs unless D2 caps them. The service-level framing — "the mask
matters for X% of services" — is the robust one and should carry the paper.


---

## D-14 · The parser reads the converted corpus — so f4 is not Day 3's `parameters`

**Decision.** `src/parse_spec.py` reads `specs/clean3/` (uniform OpenAPI 3.x),
not `specs/clean/`. Feature extraction should not carry 2.0/3.x branching, and
the conversion is already verified operation-for-operation (D-01).

**The consequence, which must not be mistaken for a bug.** Converting Swagger
2.0 moves an `in: body` parameter into `requestBody`. It stops being a
*parameter* and becomes a *request schema*. So the same operations report
different parameter availability depending on which corpus you measure:

| | ops with ≥1 parameter |
|---|--:|
| 2.0 specs, as published (`availability.py`, `specs/clean/`) | **96.41%** |
| the same specs, converted (`parse_spec.py`, `specs/clean3/`) | **91.04%** |
| 3.x specs (unaffected by conversion) | 90.7% / 90.45% |

**What this means for the mask.** Day 3's `parameters` figure describes what
authors *wrote*; the metric's **f4** describes what the similarity engine
*sees*. For the 144 converted services these are different quantities, and the
pair-level f4 co-availability reported in RESULTS.md is therefore ~5 points
optimistic relative to what the mask will actually do on those services.

**Action required before Exp. 1.** Either re-derive the mask co-availability
statistics from `parsed/` (recommended — the mask statistics should describe the
mask), or state the discrepancy explicitly in the paper. Day 3's as-published
numbers remain the right basis for the *documentation-practice* finding; they
are the wrong basis for predicting mask behaviour. This is the sort of thing
that surfaces at Gate 2 as an unexplained discrepancy if it is not written down
now.

**Stated position, pending re-derivation.** Day 3's outputs — `availability.*`,
`pair_availability.*`, **Fig 1 and Fig 2** — all describe **`specs/clean/` (as
published)**, while the mask itself will run on **`specs/clean3/` (converted)**;
the gap is **f4 96.41% (`clean/`) vs 91.04% (`clean3/`) across the 144 converted
2.0 services**, making the reported pair-level f4 co-availability ~5 points
optimistic. We are deliberately *not* re-deriving now: a stated ~5-point
discrepancy on one feature is a limitation, an unstated one is a defect. Revisit
if Exp. 4 proves sensitive to it — not at the cost of Day 5.

---

## D-15 · Tokenisation order: stopwords before letter/digit splitting

**Decision.** `tokenize()` tests the stopword list against each whole token
*before* splitting letter/digit runs, and generalises the pinned `v1`/`v2`
entries to any `^v<digits>$` token (`config.DROP_VERSION_TOKENS`).

**Why.** The obvious implementation splits letter/digit runs first, which turns
`v2` into `v` + `2` — after which the pinned stopwords `v1` and `v2` can never
match anything, and the documented parameter is silently dead. The eyeball test
Sec. 10 asks for ("test on 10 tricky names and eyeball the output") is exactly
what caught it:

| input | before | after |
|---|---|---|
| `list_users_v2` | `list, users, v, 2` | `list, users` |
| `api_v1_listAll` | `v, 1, list, all` | `list, all` |
| `/v1/projects/{projectId}/locations` | `v, 1, projects, locations` | `projects, locations` |
| `OAuth2Token` | `o, auth, 2, token` | `oauth, 2, token` |

**Why it mattered.** Nearly every Google path begins `/v1/`, and Google is the
largest single provider in the corpus. Left uncorrected, every within-service
pair in those services would have shared the tokens `v` and `1`, inflating **f3**
(and **f2** wherever operationIds carry a version) across a large fraction of the
corpus — a systematic upward bias on the metric being validated.

The `OAuth` fix is separate and smaller: the acronym-boundary rule
`([A-Z]+)([A-Z][a-z])` fires on a single leading capital and split `OAuth` into
`o` + `auth`. Requiring two or more capitals keeps `HTTPServer → HTTP Server`
while leaving `OAuth` intact.

**Status of the knob.** Extending `{v1, v2}` to `^v<digits>$` goes beyond the pinned
list, so it is a named flag and belongs in the f2/f3 sensitivity analysis
(Exp. 5), not in the silent defaults.

---

## D-16 · Train Ticket enters as a labelled `generated-from-source` condition — and Sock Shop is our only independent-spec system

**Decision.** Ingest Train Ticket with `spec_origin = 'generated-from-source'`.

| Experiment | Train Ticket's role |
|---|---|
| **Exp. 2** (perturbation, provider proximity) | **full participation** |
| **Exp. 3** (code correlation) | **separate condition — never pooled with Sock Shop** |

Exp. 3 reports two coefficients: **ρ_independent** (Sock Shop, hand-written
specs) and **ρ_derived** (Train Ticket, specs generated from the code). They are
never averaged into one number.

**Why the label is necessary — the negative search result.** Train Ticket ships
no OpenAPI specifications. A reviewer will ask why we did not simply use the
project's own specs, so the search is recorded here rather than left implicit:

- The only published, citable artifact carrying Train Ticket OpenAPI specs is the
  replication package of **arXiv 2607.12101** (Mazhar, Wang, Mäntylä, 13 Jul
  2026), Zenodo **`10.5281/zenodo.21342161`**, CC-BY-4.0 — baseline **34
  services, 172 paths, 211 operations**.
- **That artifact is itself code-derived.** Quoting its methodology: the baseline
  was built "by querying the `/v2/api-docs` endpoint exposed by Spring Boot
  services via the **Springfox** library, which **auto-generates OpenAPI
  specifications from annotated controllers at runtime**"; the four services that
  returned no usable output were "manually constructed using **source-level
  inspection**".
- The FudanSELab wiki publishes a human-written *Service Guide and API Reference*,
  but as prose and tables — not machine-readable OpenAPI.

So no independent Train Ticket specification exists. The choice was
code-derived or nothing, and we take code-derived **with the label attached**.

**Why circularity bites Exp. 3 but not Exp. 2.** Exp. 3 correlates
interface-level similarity against **code-level entity overlap**; if the
interface was generated *from* that code, the correlation is partly circular and
inflated. Exp. 2 perturbs by injecting operations between specifications and
never reads source code at all (D-05), so spec–code derivation is irrelevant
there. Hence full participation in one and quarantine in the other.

**What the split buys us.** The distance between ρ_independent and ρ_derived is a
**measurable estimate of how much spec–code derivation inflates the
correlation** — a finding in its own right, and one a single-system design
cannot produce. The quarantine is therefore not merely defensive.

**The cost, stated plainly.** Online Boutique was the candidate third system. It
is **gRPC / Protocol Buffers** (11 services, definitions in `./protos`) and ships
**no OpenAPI at all**; any specification would have to be generated from the
`.proto` files — also `generated-from-source` — and gRPC methods are not HTTP
operations, so they do not fit the (METHOD, path) operation model the metric is
defined on. Online Boutique therefore cannot supply independent specs either.

**Consequently Exp. 3's independent-spec evidence rests on Sock Shop alone:**
5 services, 27 operations after D-07, **122 within-service pairs**. (README §5's
"123" counts `payment`'s `/health`, which D-07 strips.) **ρ_independent is a
single-system estimate and must be reported as such** — it is not a
corpus-level claim, and this constrains what Exp. 3 can conclude.

**Provenance is recorded, not assumed.** `results/benchmark_manifest.csv` carries
`spec_origin`, `spec_source_url` and `spec_pin` per system, so no downstream
reader has to infer where a specification came from.

**Paper text.**

> Train Ticket exposes no authored OpenAPI specifications; the only published
> artifact (Zenodo 10.5281/zenodo.21342161) derives them from the service code
> via Springfox introspection. We therefore admit Train Ticket to the
> perturbation experiment, which never inspects source code, but hold it out of
> the pooled code-correlation analysis, reporting ρ separately for hand-written
> (Sock Shop) and generated (Train Ticket) specifications. The difference
> between the two estimates quantifies the inflation that specification–code
> derivation introduces. Because Online Boutique is a gRPC system with no
> OpenAPI descriptions, the hand-written condition rests on a single system.

---

## D-17 · Oversized services: capped at 200 operations, primary + sensitivity

**Decision.** Services with more than `config.OVERSIZED_MAX_OPERATIONS` = **200**
operations are flagged `oversized` in `results/manifest.csv` and held out of the
**primary** analysis. Every analysis is *also* run on the full corpus as a
**sensitivity** check, and the two are always reported side by side. **Nothing is
deleted**: the flag rides along in the manifest, so the sensitivity run is one
filter away and no downstream reader inherits a silently truncated corpus.
This resolves the long-open **D2** (`README.md` §4) and closes flag **F-01**.

**The justification is scope, not compute.** Above roughly 200 operations a
specification has stopped describing a single-capability microservice and started
describing an API gateway or an entire platform surface. The top of the corpus
reads: Microsoft Graph (11,422 operations), Datto/Autotask PSA (2,958),
Kubernetes (1,113), GitHub v3 REST (845), NetBox (843), Mist (779), Compute
Engine (758), EC2 (718), Meraki Dashboard (616), Stripe (452). Not one of these
is the unit ILSC is defined over — an interface whose operations are supposed to
share a single capability. Cheaper computation is a *side effect* of the cap and
is never offered as its reason.

**Where the boundary sits.** Operations per service: median **16**, p75 35,
p90 84, p95 136, p97 208. The cap therefore lands at ≈ **p96.8** and marks
**70 services (3.17%)** oversized — which hold **97.64% of all within-service
pairs**.

| | services | operations | within-service pairs |
|---|--:|--:|--:|
| **PRIMARY** (≤ 200) | 2,136 | 57,420 | 1,828,978 |
| **SENSITIVITY** (full) | 2,206 | 97,912 | 77,611,030 |
| excluded | 70 | 40,492 | 75,782,052 |

**Evidence — the cap transforms the pair-weighted picture and barely touches the
service-level one.** This is the result that matters, and it was not obvious in
advance.

*Pair-weighted (micro):*

| statistic | PRIMARY | SENSITIVITY | move |
|---|--:|--:|--:|
| mask-fire % | **56.87** | 90.58 | **+33.71** |
| f2 co-availability % | 78.39 | 97.17 | +18.77 |
| f4 co-availability % | 81.29 | 92.34 | +11.05 |
| f5 co-availability % | 70.36 | 36.09 | **−34.28** |
| f6 co-availability % | 74.41 | 24.08 | **−50.33** |

*Per-service quartile thresholds (Q1 / median / Q3), largest movement of any
boundary:* **3.17 points** (f5 co-availability). `operations` Q3 moves 32 → 35;
mask-fire median moves 38.71 → 40.00; f2, f6, description rate and operationId
rate move **0.00**. Full table: `results/oversized_thresholds.csv`.

**Reading.** The mega-specs do not merely add noise, they **invert** the
pair-weighted picture: f6 (description) co-availability reads 24.08% on the full
corpus but **74.41%** once gateway specs are removed, a 50-point swing produced
by a handful of documents. Meanwhile every per-service quartile boundary moves by
at most 3.17 points. The service-level framing is therefore robust to the cap and
the pair-weighted framing is not — independent confirmation of the standing
instruction to quote service-level figures.

**Consequence for RQ2, stated plainly.** The mask-fire headline is **56.87%
(micro, primary)** against 90.58% on the full corpus. The previously reported
figure was substantially a statement about a few gateway specifications. The
primary figure is the one to quote; the sensitivity figure is reported beside it,
never instead of it.

**Duplicates (F-02) do not disturb this.** 20 near-duplicate services survive the
dedup key, but the only numerically significant one (GitHub v3, 845 operations)
is itself oversized and therefore excluded here. Residual contamination in the
primary corpus is 5,666 of 1,828,978 pairs (**0.31%**), so the thresholds above
did not need re-deriving.

**Still to come.** ILSC scores do not exist yet — the similarity engine is
pending — so no ILSC quartile thresholds appear above. When they land they must
be derived under this same primary/sensitivity protocol. D-17 fixes the
**protocol**, not one table.

**Paper text.**

> Specifications exceeding 200 operations describe API gateways or whole platform
> surfaces rather than single-capability microservices, and were held out of the
> primary analysis (70 of 2,206 services, 3.2%); all analyses were repeated on
> the full corpus as a sensitivity check. The distinction is material: pair-
> weighted feature co-availability moves by up to 50 percentage points between
> the two, whereas every per-service quartile boundary moves by at most 3.2.
> Service-level statistics are reported as the primary result accordingly.

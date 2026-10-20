# ILSC against Briand's cohesion properties

The third primary line of D-30 is theoretical validation. Briand, Morasca and
Basili (IEEE TSE 22(1):68-86, 1996, doi 10.1109/32.481535) give four properties
that any cohesion measure should satisfy. This note checks each ILSC variant
against them. It proves what holds and states what does not.

> The four properties below are paraphrased. Check the wording against the
> paper before quoting it.

## The model

Briand et al. state their properties on a module m = ⟨E, R⟩: a set of
elements, and the relationships R ⊆ E × E between them. For ILSC:

- the elements are a service's n operations, n ≥ 2;
- each pair (i, j) carries a weight Sim(i, j) ∈ [0, 1], the masked, weighted
  mean of the six feature similarities (`docs/metric_definition.md` §4–5).

A relationship is a pair with Sim > 0, or, for ILSC_τ, a pair with Sim ≥ τ.
"Adding a relationship" means raising a pair's weight. "Unrelated" modules have
every cross pair at weight 0. The properties are statements about the measure
as a function of these weights.

Write P(n) = n(n−1)/2 for the number of pairs.

| variant | definition |
|---|---|
| ILSC_mean(m) | (1 / P(n)) Σ_{i<j} Sim(i, j) |
| ILSC_τ(m) | \|{(i, j) : Sim ≥ τ}\| / P(n) |
| ILSC_norm(m) | (ILSC_mean − E) / (1 − E), where E = E[ILSC_rand] is 0.0988 globally, or one value per provider (D-18, D-21) |

## Results

| property (Briand et al. 1996) | ILSC_mean | ILSC_τ | ILSC_norm |
|---|:-:|:-:|:-:|
| 1. Non-negativity and normalisation: value in [0, Max] | ✓ | ✓ | ✗ by design |
| 2. Null value: no relationships gives 0 | ✓ | ✓ | ✗ by design |
| 3. Monotonicity: adding relationships never lowers cohesion | ✓ | ✓ | ✓ |
| 4. Cohesive modules: merging two unrelated modules never raises cohesion above the larger of the two | ✓ | ✓ | ✓ global, and within one provider |

### 1. Non-negativity and normalisation

Every feature similarity lies in [0, 1]:
- cosine is clamped (D-20);
- Jaccard and the overlap coefficient lie there by construction.

Sim is a convex combination of the available features' similarities, with
weights w_k·m_ijk / Σ w·m. When no feature is available it is defined as 0.
So Sim ∈ [0, 1], and ILSC_mean, a mean of such values, is in [0, 1] as well.
Max = 1 is reached exactly when every pair is identical on every co-available
feature. ILSC_τ is a proportion, so it is in [0, 1].

ILSC_norm is **not** non-negative: it is below 0 whenever ILSC_mean < E. The
specification reports it unclipped, on purpose.
- With the provider null, **98 of the 2,136 primary services** score below 0
  (minimum −0.0635, `results/ilsc_thresholds.csv`).
- With the global null, none do (minimum 0.0289).

### 2. Null value

If every Sim(i, j) = 0, then ILSC_mean = 0 and ILSC_τ = 0. The converse also
holds, so 0 means exactly "no pair is related".

ILSC_norm is −E / (1 − E) ≠ 0 in that case: its zero is "as related as
chance", not "unrelated".

### 3. Monotonicity

ILSC_mean is a sum of the weights divided by a constant, so raising any weight
raises it strictly. ILSC_τ counts the pairs at or above τ, so raising a weight
can only keep a pair in the count or add it. ILSC_norm is an increasing affine
map of ILSC_mean (1 − E > 0), so it inherits monotonicity.

### 4. Cohesive modules

Take m1 with n1 operations and mean μ1, and m2 with n2 operations and mean μ2.
Merge them into m. Its pairs are the P(n1) pairs of m1, the P(n2) pairs of m2,
and n1·n2 cross pairs with mean μ12. Then

    ILSC_mean(m) = [P(n1)·μ1 + P(n2)·μ2 + n1·n2·μ12] / [P(n1) + P(n2) + n1·n2]

This is a weighted average of μ1, μ2 and μ12.

- **Briand's case (unrelated: μ12 = 0).** The numerator is at most
  [P(n1) + P(n2)]·max(μ1, μ2), and the denominator is larger than
  P(n1) + P(n2). So ILSC_mean(m) ≤ max(μ1, μ2), strictly so unless both
  modules score 0. ✓
- **The graded form, which is what matters in practice.** Unrelated
  operations never score exactly 0 under ILSC: f1 is always available, and
  random cross-service pairs average 0.0988. So the useful statement is the
  general one. A weighted average never exceeds its largest term, which gives:

  > ILSC_mean(m) ≤ max(μ1, μ2)  whenever  μ12 ≤ max(μ1, μ2).

  Merging never raises cohesion unless the operations across the two modules
  are, on average, more alike than those inside the more cohesive one. In
  that case the merge is the better grouping, and a cohesion measure *should*
  rise. A check on 20,000 random merges found no counterexample.

ILSC_τ follows the same argument with counts in place of means: for unrelated
modules no cross pair reaches τ.

ILSC_norm keeps the inequality when m1, m2 and m share one E. That is always
true for the global null, and true for the provider null when both modules
come from one provider. Across providers, the merged module has no defined
provider null.

## What this establishes, and what it does not

- **ILSC_mean and ILSC_τ are proper cohesion measures** in Briand's sense, so
  either can be reported as one.
- **ILSC_norm is not**, and should not be described as one. It is an
  interpretive rescaling: it says how far above chance a service is. This
  matches D-21, which already says it cannot reorder services and is not
  independent evidence.
- **The properties concern the measure, given the weights, not how the weights
  are produced.** Two consequences fall outside the framework and are recorded
  here so they are not missed:
  - **The availability mask means removing a field can raise or lower a pair's
    Sim.** The pair is re-averaged over fewer features. That is the intended
    behaviour (D-08, D-19), but it means ILSC is not monotone in the amount of
    documentation.
  - **Briand's framework says nothing about size.** ILSC_mean's fall with
    service size is explained by resource count
    (`results/size_mechanism_summary.csv`: partial ρ(ILSC, size | resources) =
    +0.004). That is an empirical fact about the corpus, not a property
    violation.
- **Theoretical validity is necessary, not sufficient.** Satisfying the four
  properties shows ILSC behaves like a cohesion measure. It does not show that
  it measures *semantic* cohesion better than a resource count. That is the
  job of the evolution line (D-30).

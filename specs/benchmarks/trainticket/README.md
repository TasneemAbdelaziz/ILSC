# Train Ticket specifications — provenance and attribution

**These specifications were generated from Train Ticket's source code, not
written by hand.** That is why they are labelled
`spec_origin = generated-from-source` in `results/benchmark_manifest.csv` and
why Exp. 3 reports them separately from Sock Shop. See **D-16**.

## Source

Derived from the replication package of:

> Hamza Bin Mazhar, Yuqing Wang, Mika Mäntylä. *"Fault Injection in OpenAPI
> Specifications for Evaluating Black-Box Testing Effectiveness."* 37th IEEE
> International Symposium on Software Reliability Engineering (ISSRE 2026).
> arXiv:2607.12101.

- **Replication package:** <https://doi.org/10.5281/zenodo.21342161>
  (Zenodo record `21342162`)
- **Licence:** Creative Commons Attribution 4.0 International (**CC-BY-4.0**)
- **Archive pin:** `Fault-Injection-in-OpenAPI-Specifications.zip`, 560,156 bytes,
  `sha256:12affbd0c65e81ae2102aa1ddd39a2141f23309d9383e2347fef5aeaddd6a553`
- **File used:** `trainticket/baseline_spec.json` only. The fault-injected
  (`mutated_specs/`) variants and the injector are **not** used here.

## How the upstream authors produced the baseline

Quoting their methodology: the baseline was built "by querying the
`/v2/api-docs` endpoint exposed by Spring Boot services via the **Springfox**
library, which auto-generates OpenAPI specifications from annotated controllers
at runtime." Four services that returned no usable output were "manually
constructed using **source-level inspection**."

Train Ticket itself publishes no authored OpenAPI specifications; the project
wiki's *Service Guide and API Reference* is prose, not a machine-readable
document. No independent artifact exists — see D-16 for the recorded search.

## Our modification (required by CC-BY)

The upstream baseline is a **single combined document** titled
"Train-ticket All Services Combined (v2)" — 172 paths, 211 operations, Swagger 2.0.
`src/benchmark_prep.py` splits it into the 34 per-service files in this
directory, because ILSC is a within-service metric and measuring the combined
document would fabricate cross-service pairs.

The split is read off the artifact, not guessed: every one of the 211 operations
carries exactly one `ts-*-service` tag, Train Ticket's own deployable-service
identity. Path-level keys are carried onto each retained path, `definitions` are
pruned to the transitive `$ref` closure per service (no dangling refs), and the
(METHOD, path) operation multiset is asserted unchanged. `results/benchmark_split_log.csv`
records what each service received.

**No specification content was altered** — only partitioned and pruned.

## Regenerating

```bash
python src/benchmark_prep.py --tt-baseline <path>/trainticket/baseline_spec.json
```

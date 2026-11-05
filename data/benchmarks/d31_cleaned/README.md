# D-31 datasets - the exact inputs of every condition

Written by `python src/experiments/dev_boundaries.py` (or `--dataset` for this folder alone).
Nothing here is edited by hand; re-running reproduces every file.

| file | what it holds |
|---|---|
| `operations.csv` | all 238 operations (Train Ticket 211, Sock Shop 27): the original path, operationId and schema names beside their cleaned forms (A1), the schema names after S1, and whether the operation is a greeting endpoint |
| `removed.csv` | every removal, one row each: service-name prefixes (path, operationId, schema name), framework wrappers (S1) and greeting endpoints, with the conditions each one applies to |
| `<system>__<condition>.json` | the operation records one condition feeds its predictors, after every removal, with the condition's settings and D-26's system-level exclusions in the header |

Conditions, as recorded in `docs/DECISIONS.md` D-31:

- `trainticket__primary`: pre-registered; path and operationId prefixes removed
- `trainticket__no_greeting`: pre-registered sensitivity
- `trainticket__unstripped`: F-06 diagnostic; nothing removed
- `trainticket__A1_amended`: amendment A1; schema-name prefixes removed too
- `trainticket__A1_no_greeting`: A1 without the 26 greeting endpoints
- `trainticket__A1_S1_no_wrapper`: A1 plus sensitivity S1, framework wrappers dropped
- `sockshop__primary`: nothing removed; Sock Shop carries no service-name prefix
- `sockshop__S1_no_wrapper`: identical to `sockshop__primary`, since S1 matches nothing there

D-26's frequent-schema and frequent-parameter rules are part of the metric, not
a data removal. They are applied inside the predictors, and each JSON header
lists what they excluded.

**Provenance.**
- Train Ticket comes from the replication package of Mazhar, Wang and Mantyla
  (ISSRE 2026), Zenodo 10.5281/zenodo.21342161, CC-BY-4.0. See
  `data/benchmarks/specs/trainticket/README.md`.
- Sock Shop comes from github.com/microservices-demo, Apache-2.0.
- Sun et al.'s MsDecomposer data has no licence and is **not** copied here.

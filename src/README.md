# src/ - every script, by role

Run any script from the repository root, e.g. `python src/metric/ilsc.py`.
Scripts import one another by plain module name (`import similarity`). Each
inserts the repository root into `sys.path` and imports `srcpath`, which puts
every folder below on the path.

## pipeline/ - building the data

| script | what it does | writes |
|---|---|---|
| `filter.py` | Curates the corpus from S1 + S2: validation, REST style, at least 3 operations, deduplication within and across sources (Sec. 7; D-02, D-09, D-13) | `data/corpus/1_clean/`, `results/manifest.csv`, `results/filter_log.csv` |
| `convert.py` + `convert.js` | Swagger 2.0 to OpenAPI 3.x with swagger2openapi 7.0.8; checks the operation set is unchanged (D-01, D-11) | `data/corpus/2_clean3/`, `results/convert_log.csv` |
| `validate_sample.py` | Strict validation of a 200-service sample (D-02) | `results/strict_validation_sample.csv` |
| `parse_spec.py` | Parser and feature extraction: drops admin endpoints (D-07), tokenises, builds `T(Oi)`, applies the per-service exclusions (D-14, D-15, D-26) | `data/corpus/3_parsed/` |
| `embed.py` | SBERT vectors of `T(Oi)` and of descriptions, for f1 and f6 | `data/corpus/embeddings/` |
| `benchmark_prep.py` | Builds the benchmark specs: Sock Shop as published; Train Ticket split from its combined baseline into 34 services (D-16) | `data/benchmarks/specs/`, `results/benchmark_manifest.csv`, `results/benchmark_split_log.csv` |
| `bench_prepare.py` | Converts, parses and embeds the benchmarks, exactly as the corpus is | `data/benchmarks/specs3/`, `parsed/`, `embeddings/` |

## metric/ - the metric itself

| script | what it does |
|---|---|
| `similarity.py` | The six similarity functions and the availability mask (D-19, D-20); `--selftest`, `--audit` |
| `ilsc.py` | ILSC_mean, ILSC_tau and ILSC_norm over the corpus, plus quartile thresholds -> `results/ilsc_scores.csv`, `results/ilsc_thresholds.csv` |
| `null_models.py` | Global and provider-restricted null models (D-18, D-21) -> `results/null_model.csv` |
| `oversized.py` | The 200-operation cap, run as primary plus sensitivity (D-17) |
| `pool.py` | The shared operation pool used by the null models and by perturbation |
| `test_similarity.py` | The engine's unit tests (17), including R2 |

## experiments/ - the tests of the metric

| script | experiment |
|---|---|
| `gate1_select.py` | Gate 1 candidate shortlist (a browsing aid, not a chooser) |
| `gate1_run.py` | Gate 1 on the ten hand-picked services (D-24, D-27) |
| `gate1_matched.py` | Gate 1 as a provider-matched paired design (D-29) |
| `inject.py` | Exp. 2: perturbation and the monotonicity / contrast checker (H2) |
| `entity_extract.py` | Exp. 3 ground truth: Train Ticket endpoint-to-entity extraction (D-22). Needs a train-ticket checkout |
| `code_correlation.py` | Exp. 3 (Gate 2): does interface similarity track code relatedness? |
| `baselines.py` | Exp. 4: SIDC and LoCmsg, head to head and under perturbation |
| `baseline_correlation.py` | Exp. 4b: which metric predicts code-level relatedness (D-28; its Sock Shop half is retired by D-30) |
| `sensitivity.py` | Exp. 5: weights and tau |
| `version_tokens_sweep.py` | Exp. 5, third knob (D-15). About 30 minutes, not in `run_all.py` |
| `provider_cap.py` | D-25: does a provider cap move the thresholds? |
| `dev_boundaries.py` | D-31: developer-defined service boundaries. `--exploratory` runs E1/E2, `--dataset` writes `data/benchmarks/d31_cleaned/` |

## analyses/ - diagnostic studies, none of which changes the metric

| script | question |
|---|---|
| `availability.py` | Day 3a: how often is each field present, per operation (Fig 1)? |
| `pair_availability.py` | Day 3b: pair-level co-availability, the RQ2 number (Fig 2) |
| `feature_corr.py` | How correlated are the six features (Fig 9)? |
| `size_mechanism.py` | Why does ILSC_mean fall with service size? |
| `construct_validity.py` | Construct validity under size control; size-stratified thresholds |
| `param_boilerplate.py` | F-05: is f4 inflated by boilerplate parameters? |
| `graph_structure.py` | Does the similarity graph carry information the mean hides? (secondary) |

## common/

| script | role |
|---|---|
| `figstyle.py` | One figure style for every chart in the paper |
| `domain_label.py` | The keyword domain labeller REJECTED by D-03, kept for the record |

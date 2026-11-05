# data/ - every dataset, and what each stage changes

Each folder is one stage. A stage only reads the stage before it, and every
removal it makes is logged in `results/`. Only `benchmarks/specs/` and
`benchmarks/d31_cleaned/` are committed; everything else is rebuilt from the
pinned sources (README.md, section 2).

## sources/ - fetched, never edited

| folder | what | pinned at |
|---|---|---|
| `rama-thresholds/benchmark-repository/openapi/` | S1: RAMA's benchmark (Bogner et al. 2020), 2,619 files, already OpenAPI 3 upstream (D-10, D-12). `raml/` and `wadl/` sit beside it | `config.RAMA_COMMIT` |
| `openapi-directory/APIs/` | S2: APIs.guru, 4,138 spec files | `config.APIS_GURU_COMMIT` |
| `msdecomposer/` | Sun et al. 2022's applications and their own clusters. **No licence**: read, never redistributed (D-31) | `config.MSDECOMPOSER_COMMIT` |

## corpus/ - the ILSC corpus

| stage | folder | made by | what changes | logged in | services |
|---|---|---|---|---|--:|
| 1 | `1_clean/` | `src/pipeline/filter.py` | From 6,757 source files it removes 233 that fail validation, 1 that is not REST-style, 1,264 with fewer than 3 operations, 1,199 within-source duplicates (607 superseded versions, 592 duplicates) and 1,854 cross-source duplicates (D-02, D-09, D-13) | `results/filter_log.csv` (4,551 rows), `results/manifest.csv` | 2,206 |
| 2 | `2_clean3/` | `src/pipeline/convert.py` | Swagger 2.0 converted to OpenAPI 3.x; the operation set is checked unchanged (D-01, D-11) | `results/convert_log.csv`, `results/convert_verify.csv` | 2,206 |
| 3 | `3_parsed/` | `src/pipeline/parse_spec.py` | One document per service: admin endpoints dropped (D-07), names tokenised (D-15), `T(Oi)` built, per-service schema/parameter exclusions applied (D-26) | - | 2,206 |
| - | `embeddings/` | `src/pipeline/embed.py` | SBERT vectors (`config.EMBEDDING_MODEL`): 89,429 unique `T(Oi)` texts, 54,701 descriptions | `embeddings/index.json` | 2,206 |

The **primary population** (at most 200 operations, 2,136 services) is not a
folder. It is a flag, set by `src/metric/oversized.py` (D-17).

`3_parsed_nodrop/` and `embeddings_nodrop/` appear only after
`src/experiments/version_tokens_sweep.py` runs (D-15).

## benchmarks/ - the systems with known structure

| folder | what | made by | logged in |
|---|---|---|---|
| `specs/sockshop/` | 5 services, 28 operations (27 after D-07), written by Sock Shop's developers - `independent` (D-16). Apache-2.0. Upstream commit not recorded | in the repository since Day 1-2 | `results/benchmark_manifest.csv` |
| `specs/trainticket/` | 34 services, 211 operations, generated from Train Ticket's code by Springfox - `derived` (D-16). Split from Mazhar et al.'s combined baseline (Zenodo 10.5281/zenodo.21342161, CC-BY-4.0) | `src/pipeline/benchmark_prep.py` | `results/benchmark_split_log.csv` |
| `specs3/`, `parsed/`, `embeddings/` | The same 39 services converted, parsed and embedded exactly as the corpus is | `src/pipeline/bench_prepare.py` | `results/benchmark_convert_log.csv` |
| `d31_cleaned/` | D-31's exact inputs, one JSON per condition. Service-name prefixes removed (A1), framework wrappers dropped (S1), greeting endpoints excluded. `removed.csv` lists all 841 removals | `src/experiments/dev_boundaries.py --dataset` | `d31_cleaned/removed.csv` |

## Outside the repository

`../../archive/clean_stale_S2only_1831/` holds the earlier 1,831-service
S2-only corpus that D-03's blind sample was drawn from. It is kept as that
sample's provenance (F-07).

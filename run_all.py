"""
ILSC - one-command reproduction of everything completed so far: the empirical
track through Day 3 plus benchmark prep and the D-17 cap, and the metric track
through Exp. 3 (engine, null models, Gate 1, Exp. 1, Fig 9, perturbation,
and the code correlation that decides Gate 2).

    python run_all.py

Assumes the two pinned corpora are already fetched (README.md section 2):

    data/sources/rama-thresholds/benchmark-repository/openapi   S1, 2,619 files
    data/sources/openapi-directory/APIs                         S2, 4,138 files

Steps, in dependency order. Each writes its artifacts under results/ or
figures/ and each is individually runnable; this file only fixes the order and
fails loudly on the first broken step.
"""

import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
import config                                  # noqa: E402

STEPS = [
    ("Day 1-2  curate corpus (S1 + S2)",       [sys.executable, "-u", "src/pipeline/filter.py"]),
    ("Day 1-2  convert 2.0 -> 3.x (clean3)",   [sys.executable, "-u", "src/pipeline/convert.py"]),
    ("D-02     strict validation sample",      [sys.executable, "-u", "src/pipeline/validate_sample.py"]),
    ("D-03     domain labels (rejected)",      [sys.executable, "-u", "src/common/domain_label.py"]),
    ("Day 1-2  Gate 1 shortlist",              [sys.executable, "-u", "src/experiments/gate1_select.py"]),
    ("Day 3a   field availability + Fig 1",    [sys.executable, "-u", "src/analyses/availability.py",
                                                "--provider-from-manifest"]),
    ("Day 3b   pair co-availability + Fig 2",  [sys.executable, "-u", "src/analyses/pair_availability.py"]),
    ("Day 1-2m parser + feature extraction",   [sys.executable, "-u", "src/pipeline/parse_spec.py"]),
    ("Day 1-2m parser spot-check",             [sys.executable, "-u", "src/pipeline/parse_spec.py",
                                                "--spotcheck", "5"]),
    # --- D-17 and the benchmark corpus. Previously missing from this file, so a
    #     fresh clone reproduced neither the primary/sensitivity split nor the
    #     benchmark systems (docs/PLAN.md 5).
    ("D-17     oversized cap + thresholds",    [sys.executable, "-u", "src/metric/oversized.py"]),
    ("Day 5    benchmark prep (+ Train Ticket)", [sys.executable, "-u", "src/pipeline/benchmark_prep.py"]),
    # --- metric track, Days 1-7 -----------------------------------------------
    ("Day 1m   embedding cache (f1 + f6)",     [sys.executable, "-u", "src/pipeline/embed.py"]),
    ("Day 1m   embedding cache verify",        [sys.executable, "-u", "src/pipeline/embed.py", "--verify"]),
    ("Day 1m   similarity engine self-test",   [sys.executable, "-u", "src/metric/similarity.py",
                                                "--selftest"]),
    ("Day 2m   unit tests (incl. R2)",         [sys.executable, "-u", "src/metric/test_similarity.py"]),
    ("Day 2m   mask/clamp audit (D-19, D-20)", [sys.executable, "-u", "src/metric/similarity.py",
                                                "--audit"]),
    ("Day 3m   null models (D-18, D-21)",      [sys.executable, "-u", "src/metric/null_models.py"]),
    ("Day 4m   ILSC over the corpus",          [sys.executable, "-u", "src/metric/ilsc.py",
                                                "--null", "results/null_model.csv"]),
    ("Day 4m   GATE 1",                        [sys.executable, "-u", "src/experiments/gate1_run.py"]),
    ("Day 6m   feature correlation + Fig 9",   [sys.executable, "-u", "src/analyses/feature_corr.py"]),
    ("Day 7m   perturbation + Fig 3",          [sys.executable, "-u", "src/experiments/inject.py"]),
    # --- Exp. 3 / Gate 2 -------------------------------------------------------
    ("Exp 3    benchmark convert+parse+embed",  [sys.executable, "-u", "src/pipeline/bench_prepare.py"]),
    ("Exp 3    GATE 2 - code correlation",      [sys.executable, "-u", "src/experiments/code_correlation.py"]),
    ("Exp 4    SIDC + LoCmsg baselines + Fig 7", [sys.executable, "-u", "src/experiments/baselines.py"]),
    ("Exp 4b   ground-truth head-to-head + Fig 8 (D-28)",
                                                [sys.executable, "-u", "src/experiments/baseline_correlation.py"]),
    ("Exp 5    weight + tau sensitivity + Fig 6", [sys.executable, "-u", "src/experiments/sensitivity.py"]),
    # --- D-25 / D-27 / D-29 --------------------------------------------------
    ("D-25     provider cap sensitivity",        [sys.executable, "-u", "src/experiments/provider_cap.py"]),
    ("D-29     Gate 1, provider-matched + Fig 10", [sys.executable, "-u", "src/experiments/gate1_matched.py"]),
    ("D-29     Gate 1 matched, threshold grid",  [sys.executable, "-u", "src/experiments/gate1_matched.py",
                                                "--grid"]),
]

# Deliberately NOT in STEPS: src/experiments/version_tokens_sweep.py (Exp. 5's third knob,
# D-15) re-parses and re-embeds the whole corpus into data/corpus/3_parsed_nodrop/ and a second
# cache, roughly 30 minutes, to answer one sensitivity question. Its result is
# committed in results/version_tokens_sweep.csv. Run it explicitly:
#     python src/experiments/version_tokens_sweep.py

# Not run here because they need a checkout this repository does not vendor.
# Documented so the omission is visible rather than silent:
#   src/experiments/entity_extract.py --src <FudanSELab/train-ticket>   (Day 7, empirical)
# results/endpoint_entities.csv (Sock Shop) is a MANUAL artifact and is
# committed, not regenerated - see docs/responsibilities.md.


def main():
    missing = [d for d in (config.RAMA_DIR, config.APIS_GURU_DIR) if not os.path.isdir(d)]
    if missing:
        sys.exit("corpus not fetched:\n  " + "\n  ".join(missing) +
                 "\nSee README.md section 2.")

    t_all = time.time()
    for i, (name, cmd) in enumerate(STEPS, 1):
        print("\n" + "=" * 72)
        print("[%d/%d] %s" % (i, len(STEPS), name))
        print("=" * 72, flush=True)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=_ROOT)
        if proc.returncode != 0:
            sys.exit("\nFAILED at step %d (%s) with exit code %d"
                     % (i, name, proc.returncode))
        print("  -> %.1fs" % (time.time() - t0), flush=True)

    print("\n" + "=" * 72)
    print("all %d steps complete in %.1f min" % (len(STEPS), (time.time() - t_all) / 60))
    print("=" * 72)
    print("artifacts: results/*.csv  figures/*.pdf")


if __name__ == "__main__":
    main()

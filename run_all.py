"""
ILSC - one-command reproduction of everything completed so far: the empirical
track through Day 3, and the metric track through Day 1-2 (the parser).

    python run_all.py

Assumes the two pinned corpora are already fetched (README.md section 2):

    rama-thresholds/benchmark-repository/openapi   S1, 2,619 files
    openapi-directory/APIs                         S2, 4,138 files

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
    ("Day 1-2  curate corpus (S1 + S2)",       [sys.executable, "-u", "src/filter.py"]),
    ("Day 1-2  convert 2.0 -> 3.x (clean3)",   [sys.executable, "-u", "src/convert.py"]),
    ("D-02     strict validation sample",      [sys.executable, "-u", "src/validate_sample.py"]),
    ("D-03     domain labels (rejected)",      [sys.executable, "-u", "src/domain_label.py"]),
    ("Day 1-2  Gate 1 shortlist",              [sys.executable, "-u", "src/gate1_select.py"]),
    ("Day 3a   field availability + Fig 1",    [sys.executable, "-u", "src/availability.py",
                                                "--provider-from-manifest"]),
    ("Day 3b   pair co-availability + Fig 2",  [sys.executable, "-u", "src/pair_availability.py"]),
    ("Day 1-2m parser + feature extraction",   [sys.executable, "-u", "src/parse_spec.py"]),
    ("Day 1-2m parser spot-check",             [sys.executable, "-u", "src/parse_spec.py",
                                                "--spotcheck", "5"]),
]


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

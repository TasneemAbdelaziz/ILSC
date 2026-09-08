"""
ILSC - D1: does a provider cap move the published quartile thresholds?

D1 was carried as a blocking decision ("Provider cap - none / 50 / 30 / 20 per
provider, blocks Exp. 1"). Exp. 1 has since run without one, so the question is
now narrower and answerable with a number rather than an argument:

    The thresholds in `results/ilsc_thresholds.csv` are drawn from a corpus in
    which AWS, Google and Azure hold 46.8% of the services. If a hyperscaler
    publishes many similar specifications, those quartiles describe the
    hyperscalers more than they describe APIs. **Do the boundaries move under a
    cap?**

This needs no re-scoring - `ilsc_scores.csv` already holds every service's
ILSC_mean - so it is a re-derivation of the quartiles over a capped population.

**Which services survive the cap is decided by seeded random draw**, not by
score. Keeping the top-N or the first-N by filename would move the quartiles by
construction and prove nothing. With `SEED = 42` the draw is reproducible, and
`--repeats` re-draws to show the sampling noise, so a small movement is not
mistaken for a real one.

Usage:
    python src/provider_cap.py
    python src/provider_cap.py --caps 50,30,20,10 --repeats 200
"""

import argparse
import csv
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                    # noqa: E402


def load(path, primary_only=True):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["ILSC_mean"] not in ("", "nan")]
    if primary_only:
        rows = [r for r in rows if str(r.get("oversized", "0")) in ("0", "", "False")]
    return rows


def quartiles(vals):
    v = np.asarray(vals, dtype=float)
    return (float(np.percentile(v, 25)), float(np.percentile(v, 50)),
            float(np.percentile(v, 75)))


def capped_draw(rows, cap, rng):
    by = {}
    for r in rows:
        by.setdefault(r["provider"], []).append(float(r["ILSC_mean"]))
    out = []
    for prov, vals in by.items():
        if len(vals) <= cap:
            out.extend(vals)
        else:
            idx = rng.choice(len(vals), size=cap, replace=False)
            out.extend([vals[i] for i in idx])
    return out


def run(args):
    rows = load(args.scores)
    base = [float(r["ILSC_mean"]) for r in rows]
    bq = quartiles(base)

    by = {}
    for r in rows:
        by.setdefault(r["provider"], []).append(r)
    sizes = sorted((len(v) for v in by.values()), reverse=True)
    big3 = sum(len(v) for p, v in by.items()
               if any(k in p for k in ("amazonaws", "googleapis", "azure")))

    print("population: %d services, %d providers" % (len(rows), len(by)))
    print("  largest providers: %s" % sizes[:8])
    print("  AWS + Google + Azure: %d (%.1f%%)" % (big3, 100.0 * big3 / len(rows)))
    print("\nuncapped quartiles  Q1 %.4f  median %.4f  Q3 %.4f" % bq)

    caps = [int(c) for c in args.caps.split(",") if c.strip()]
    print("\n%-6s %8s %8s %8s   %9s %9s %9s   %s"
          % ("cap", "Q1", "median", "Q3", "dQ1", "dMed", "dQ3", "services kept"))
    out = [{"cap": "none", "n_services": len(rows), "q1": bq[0], "median": bq[1],
            "q3": bq[2], "d_q1": 0.0, "d_median": 0.0, "d_q3": 0.0, "sd_median": 0.0}]

    for cap in caps:
        rng = np.random.default_rng(config.SEED)
        qs = np.array([quartiles(capped_draw(rows, cap, rng))
                       for _ in range(args.repeats)])
        m = qs.mean(axis=0)
        sd = qs.std(axis=0, ddof=1) if args.repeats > 1 else np.zeros(3)
        kept = len(capped_draw(rows, cap, np.random.default_rng(config.SEED)))
        print("%-6d %8.4f %8.4f %8.4f   %+9.4f %+9.4f %+9.4f   %d"
              % (cap, m[0], m[1], m[2], m[0] - bq[0], m[1] - bq[1], m[2] - bq[2], kept))
        out.append({"cap": cap, "n_services": kept, "q1": m[0], "median": m[1],
                    "q3": m[2], "d_q1": m[0] - bq[0], "d_median": m[1] - bq[1],
                    "d_q3": m[2] - bq[2], "sd_median": sd[1]})

    worst = max(abs(r["d_q1"]) for r in out), max(abs(r["d_median"]) for r in out), \
        max(abs(r["d_q3"]) for r in out)
    biggest = max(worst)
    noise = max(r["sd_median"] for r in out)

    print("\n  largest boundary movement across all caps: %.4f" % biggest)
    print("  sampling noise on the median (sd over %d draws): %.4f" % (args.repeats, noise))
    print("\n  D1 verdict:")
    if biggest < 0.01:
        print("    The quartile boundaries do not move (< 0.01 on every cut point).")
        print("    A provider cap is NOT required, and that is a robustness result")
        print("    worth one sentence rather than an open decision. Report the")
        print("    uncapped thresholds and state that capping was tested.")
    elif biggest < 0.02:
        print("    Movement is small (< 0.02) but not nil. Report the uncapped")
        print("    thresholds and give this table as the sensitivity check.")
    else:
        print("    The boundaries MOVE (%.4f). The thresholds are partly a" % biggest)
        print("    statement about the hyperscalers, and the paper must either cap")
        print("    or report both populations.")

    path = os.path.join(config.RESULTS_DIR, "provider_cap.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        for r in out:
            w.writerow({k: ("%.6f" % v if isinstance(v, float) else v)
                        for k, v in r.items()})
    print("\nwrote %s" % path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="D1 - provider cap sensitivity.")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--caps", default="50,30,20,10,5")
    ap.add_argument("--repeats", type=int, default=200)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

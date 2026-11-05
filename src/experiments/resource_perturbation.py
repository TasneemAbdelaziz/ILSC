"""
ILSC - D-33: the resource baseline under Exp. 2/4's perturbation.

**Why.** D-30 asks every primary line to be compared with a resource baseline,
because ILSC's corpus-wide size dependence is explained by resource count
(`results/size_mechanism_summary.csv`). Exp. 4 compared ILSC with SIDC and
LoCmsg under perturbation; this adds the resource baseline.

**Two resource baselines, both fixed in D-33 before this script existed:**

    RES_leaf  share of operation pairs whose paths end in the same leaf resource
    RES_root  the same share on the root resource (first segment after the
              operation set's common prefix)

Both come from `src/analyses/size_mechanism.py`, unchanged, and are oriented
like ILSC: higher means more cohesive.

**The same draws for every metric (D-33 amendment A1).** The loop below is
`baselines.perturbation()`'s, with the same services, conditions, levels, draws
and seed. Exp. 4's own draws cannot be regenerated, because its same-service
sibling is chosen in string-hash order (F-08). So this run fixes
`PYTHONHASHSEED=0`, re-executing itself if it must, and scores all five
metrics - ILSC, SIDC, LoCmsg, RES_leaf, RES_root - on the same injected
operations. Exp. 4's stored gaps are printed beside them for reference.

**Statistic, as in Exp. 4.** Per service, the OLS slope over levels in each
condition (LoCmsg sign-flipped, as there). The gap is
slope(cross_provider) - slope(same_provider), tested with the sign-flip test
and expressed in units of the metric's corpus SD.

Outputs:
    results/resource_perturbation.csv             service x condition x level x draw
    results/resource_perturbation_comparison.csv  one row per metric

Usage:
    python src/experiments/resource_perturbation.py
"""

import argparse
import csv
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # src/<group>/ -> repository root
sys.path.insert(0, _ROOT)
import srcpath  # noqa: E402,F401  - puts every src/<group>/ on sys.path

import config                                     # noqa: E402
import similarity as sim                          # noqa: E402
import pool as pool_mod                           # noqa: E402
import inject as inject_mod                       # noqa: E402
import baselines as bl                            # noqa: E402
from size_mechanism import leaf_resources, root_resources, same_share  # noqa: E402

METRICS = ("ILSC", "SIDC", "LoCmsg", "RES_leaf", "RES_root")
OUT_DRAWS = os.path.join(config.RESULTS_DIR, "resource_perturbation.csv")
OUT_CMP = os.path.join(config.RESULTS_DIR, "resource_perturbation_comparison.csv")
EXP4_CMP = os.path.join(config.RESULTS_DIR, "baselines_comparison.csv")
SIZE_MECH = os.path.join(config.RESULTS_DIR, "size_mechanism.csv")


def res_share(ops, kind):
    paths = [o["path"] for o in ops]
    labels = leaf_resources(paths) if kind == "leaf" else root_resources(paths)
    return same_share(labels) if len(paths) >= 2 else float("nan")


def score(ops, opset):
    return {"ILSC": sim.ilsc_mean(opset), "SIDC": bl.sidc(ops), "LoCmsg": bl.locmsg(ops),
            "RES_leaf": res_share(ops, "leaf"), "RES_root": res_share(ops, "root")}


def run_draws(scores_path, n_services):
    """baselines.perturbation()'s loop, unchanged in every RNG-relevant step."""
    rng = np.random.default_rng(config.SEED)
    pl = pool_mod.load_pool(include_oversized=False)
    picked, _q3 = inject_mod.top_quartile_services(scores_path, pl, n_services)
    if not picked:
        sys.exit("no services selected - run src/metric/ilsc.py first")
    rows = []
    for si, (name, meta) in enumerate(picked, 1):
        base_idx = pl.by_service[name]
        provider = pl.provider_of[base_idx[0]]
        base = score([pl.ops[i] for i in base_idx], pl.opset(base_idx))
        print("  [%2d/%d] %-38s ILSC=%.3f RES_leaf=%.3f RES_root=%.3f"
              % (si, len(picked), meta["title"][:38], base["ILSC"], base["RES_leaf"],
                 base["RES_root"]), flush=True)
        for cond in inject_mod.CONDITIONS:
            for level in inject_mod.LEVELS:
                for draw in range(inject_mod.DRAWS):
                    if level == 0:
                        s = base
                    else:
                        don = inject_mod.donor_indices(pl, name, provider, cond, rng, level)
                        if don is None:
                            s = {m: float("nan") for m in METRICS}
                        else:
                            idx = list(base_idx) + don
                            s = score([pl.ops[i] for i in idx], pl.opset(idx))
                    rows.append({"service": name, "title": meta["title"], "condition": cond,
                                 "level": level, "draw": draw, **s})
    return rows


def corpus_sd():
    """Corpus SD per metric: ILSC and the resource shares from size_mechanism.csv,
    SIDC and LoCmsg exactly as Exp. 4 standardises them."""
    with open(SIZE_MECH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    col = {"ILSC": "ILSC_mean", "RES_leaf": "same_resource_pair_share",
           "RES_root": "same_root_pair_share"}
    sds = {m: float(np.std([float(r[c]) for r in rows], ddof=1)) for m, c in col.items()}
    disp = bl.corpus_dispersion()
    sds["SIDC"], sds["LoCmsg"] = disp["SIDC"]["sd"], disp["LoCmsg"]["sd"]
    return sds, len(rows)


def compare(rows):
    services = sorted({r["service"] for r in rows})
    levels = inject_mod.LEVELS
    sds, n_corpus = corpus_sd()

    def mean_at(svc, metric, cond, lv):
        v = [r[metric] for r in rows if r["service"] == svc and r["condition"] == cond
             and r["level"] == lv and np.isfinite(r[metric])]
        return float(np.mean(v)) if v else float("nan")

    summary = []
    for metric in METRICS:
        sign = -1.0 if metric == "LoCmsg" else 1.0      # LoCmsg runs the other way (Exp. 4)
        gaps, slopes = [], {c: [] for c in inject_mod.CONDITIONS}
        for svc in services:
            per = {}
            for cond in inject_mod.CONDITIONS:
                sl = inject_mod.ols_slope(levels, [mean_at(svc, metric, cond, lv)
                                                   for lv in levels]) * sign
                per[cond] = sl
                if np.isfinite(sl):
                    slopes[cond].append(sl)
            gaps.append(per["cross_provider"] - per["same_provider"])
        g = [x for x in gaps if np.isfinite(x)]
        p, _n = inject_mod.sign_flip_p(g)
        mean_gap = float(np.mean(g)) if g else float("nan")
        summary.append({
            "metric": metric,
            **{"slope_" + c: float(np.mean(slopes[c])) for c in inject_mod.CONDITIONS},
            "mean_gap": mean_gap, "median_gap": float(np.median(g)) if g else float("nan"),
            "n_services_gap_negative": int(sum(1 for x in g if x < 0)),
            "n_services": len(g), "sign_flip_p": p,
            "corpus_sd": sds[metric], "corpus_n": n_corpus,
            "gap_in_sd": mean_gap / sds[metric] if sds[metric] > 0 else float("nan"),
        })

    with open(OUT_CMP, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print()
    print("%-9s %10s %10s %10s %9s %8s %7s %9s"
          % ("metric", "same_svc", "same_prov", "cross_prov", "gap", "gap/SD", "neg", "p"))
    for s in summary:
        print("%-9s %10.4f %10.4f %10.4f %9.4f %8.3f %4d/%-2d %9.2g"
              % (s["metric"], s["slope_same_service"], s["slope_same_provider"],
                 s["slope_cross_provider"], s["mean_gap"], s["gap_in_sd"],
                 s["n_services_gap_negative"], s["n_services"], s["sign_flip_p"]))

    with open(EXP4_CMP, newline="", encoding="utf-8") as fh:
        ref = list(csv.DictReader(fh))
    print()
    print("for reference, Exp. 4's stored draws (not reproducible, F-08):")
    for r in ref:
        print("%-9s gap %9.4f  gap/SD %7.3f  %s/%s negative"
              % (r["metric"], float(r["mean_gap"]), float(r["gap_in_sd"]),
                 r["n_services_gap_negative"], r["n_services"]))
    print()
    print("wrote %s" % OUT_DRAWS)
    print("      %s" % OUT_CMP)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="D-33: resource baseline under perturbation.")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--n-services", type=int, default=20)
    args = ap.parse_args(argv)

    if os.environ.get("PYTHONHASHSEED") != "0":       # F-08: fix the sibling tie-break
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))

    rows = run_draws(args.scores, args.n_services)
    with open(OUT_DRAWS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["service", "title", "condition", "level", "draw"]
                           + list(METRICS))
        w.writeheader()
        w.writerows(rows)
    compare(rows)


if __name__ == "__main__":
    main()

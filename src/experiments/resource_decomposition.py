"""
ILSC - D-36: ILSC_mean split into within-resource and between-resource similarity.

**Why.** ILSC_mean falls with service size (Spearman -0.55), and
`src/analyses/size_mechanism.py` shows the dependence is carried by the number
of resources. The mean over all pairs mixes two kinds of pair:

    ILSC_mean = s * W + (1 - s) * B

    W  mean Sim over pairs on the SAME resource
    B  mean Sim over pairs on DIFFERENT resources      <- the candidate
    s  share of same-resource pairs

A service with more resources has a smaller s, so its mean falls even when W
and B do not move. This script computes the parts and tests whether B is free
of size and still responds to foreign operations.

**Not a metric change.** Sim is the engine's pair score, unchanged, and
`src/metric/` is not touched. B is a candidate; adopting it is the metric
lead's decision. Everything below was fixed in D-36 before any value existed.

    B       pairs on different LEAF resources (`size_mechanism.leaf_resources`)
    W       pairs on the same leaf resource
    B_res   sensitivity: every pair of resources counts once
    B_root  sensitivity: B on `size_mechanism.root_resources`

**Test 1 - size independence** (primary population, services where B is
defined). B passes if |Spearman rho| <= config.SIZE_INDEPENDENCE_RHO_LIMIT with
both the operation count and the resource count. Intervals resample providers.

**Test 2 - sensitivity is kept.** D-33's perturbation loop with
`PYTHONHASHSEED=0`, so the injected operations are the same draws; ILSC is
checked against D-33's stored draws and the run stops on any difference. B
passes if slope(cross_provider) - slope(same_provider) is negative with
sign-flip p < 0.05.

Outputs:
    results/resource_decomposition.csv                          one row per service
    results/resource_decomposition_summary.csv                  every statistic, tidy
    results/resource_decomposition_perturbation.csv             service x condition x level x draw
    results/resource_decomposition_perturbation_comparison.csv  one row per score

Usage:
    python src/experiments/resource_decomposition.py --selftest
    python src/experiments/resource_decomposition.py
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
from size_mechanism import (BANDS, band_of, leaf_resources, partial_spearman,   # noqa: E402
                            root_resources, spearman)

SCORES = ("B", "W", "B_res", "B_root")
N_BOOT = 2000
IDENTITY_TOL = 1e-6
DRAWS_TOL = 1e-9

OUT_SERVICES = os.path.join(config.RESULTS_DIR, "resource_decomposition.csv")
OUT_SUMMARY = os.path.join(config.RESULTS_DIR, "resource_decomposition_summary.csv")
OUT_DRAWS = os.path.join(config.RESULTS_DIR, "resource_decomposition_perturbation.csv")
OUT_CMP = os.path.join(config.RESULTS_DIR, "resource_decomposition_perturbation_comparison.csv")
D33_DRAWS = os.path.join(config.RESULTS_DIR, "resource_perturbation.csv")
SIZE_MECH = os.path.join(config.RESULTS_DIR, "size_mechanism.csv")

NAN = float("nan")


# ----------------------------------------------------------------------------
# The decomposition
# ----------------------------------------------------------------------------

def sim_matrix(opset):
    """The full n x n matrix of the engine's Sim, unchanged."""
    S = np.zeros((opset.n, opset.n), dtype="float64")
    for i0, i1, s, _per, _mask in sim.pair_blocks(opset):
        S[i0:i1] = s
    return S


def decompose(S, labels):
    """ILSC_mean, s, W, B and B_res of one operation set under one labelling."""
    n = len(labels)
    ids = {}
    lab = np.array([ids.setdefault(x, len(ids)) for x in labels])
    iu = np.triu_indices(n, 1)
    v = S[iu]
    same = lab[iu[0]] == lab[iu[1]]
    n_same = int(same.sum())
    n_diff = len(v) - n_same
    out = {"mean": float(v.mean()), "s": n_same / len(v), "k": len(ids),
           "n_same": n_same, "n_diff": n_diff,
           "W": float(v[same].mean()) if n_same else NAN,
           "B": float(v[~same].mean()) if n_diff else NAN,
           "B_res": NAN}
    if len(ids) >= 2:
        L = np.zeros((n, len(ids)))
        L[np.arange(n), lab] = 1.0
        total = L.T @ S @ L                       # block sums; only a != b is read
        count = np.outer(L.sum(axis=0), L.sum(axis=0))
        ru = np.triu_indices(len(ids), 1)
        out["B_res"] = float((total[ru] / count[ru]).mean())
    return out


def score_set(ops, opset):
    """Every D-36 score of one operation set, plus the parts of the identity."""
    S = sim_matrix(opset)
    paths = [o["path"] for o in ops]
    leaf = decompose(S, leaf_resources(paths))
    root = decompose(S, root_resources(paths))
    return {"ILSC_mean": leaf["mean"], "s": leaf["s"], "n_resources": leaf["k"],
            "n_roots": root["k"], "n_same_pairs": leaf["n_same"],
            "n_diff_pairs": leaf["n_diff"], "B": leaf["B"], "W": leaf["W"],
            "B_res": leaf["B_res"], "B_root": root["B"]}


# ----------------------------------------------------------------------------
# Test 1: the corpus
# ----------------------------------------------------------------------------

def rank_rho(x, y):
    from scipy.stats import rankdata
    rx, ry = rankdata(x), rankdata(y)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / den) if den > 0 else NAN


def provider_interval(x, y, providers, rng):
    """95% interval of Spearman rho, resampling whole providers."""
    by = {}
    for i, p in enumerate(providers):
        by.setdefault(p, []).append(i)
    keys = sorted(by)
    groups = [np.array(by[k]) for k in keys]
    draws = []
    for _ in range(N_BOOT):
        ii = np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))])
        draws.append(rank_rho(x[ii], y[ii]))
    draws = np.array(draws)
    draws = draws[np.isfinite(draws)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def corpus_rows(pl):
    with open(SIZE_MECH, newline="", encoding="utf-8") as fh:
        ref = {r["clean_file"]: r for r in csv.DictReader(fh)}
    rows, worst_identity, worst_stored, res_mismatch = [], 0.0, 0.0, 0
    for name in sorted(pl.by_service):
        idx = pl.by_service[name]
        meta = pl.meta[name]
        sc = score_set([pl.ops[i] for i in idx], pl.opset(idx))
        if np.isfinite(sc["W"]) and np.isfinite(sc["B"]):
            worst_identity = max(worst_identity, abs(
                sc["s"] * sc["W"] + (1 - sc["s"]) * sc["B"] - sc["ILSC_mean"]))
        r = ref.get(meta["clean_file"])
        if r is not None:
            worst_stored = max(worst_stored, abs(float(r["ILSC_mean"]) - sc["ILSC_mean"]))
            res_mismatch += int(int(r["n_resources"]) != sc["n_resources"])
        rows.append({"clean_file": meta["clean_file"], "title": meta["title"],
                     "provider": meta["provider"], "source": meta["source"],
                     "n_operations": len(idx), "size_band": band_of(len(idx)),
                     "n_resources": sc["n_resources"], "n_roots": sc["n_roots"],
                     "n_same_pairs": sc["n_same_pairs"], "n_diff_pairs": sc["n_diff_pairs"],
                     "same_resource_pair_share": sc["s"], "ILSC_mean": sc["ILSC_mean"],
                     "W": sc["W"], "B": sc["B"], "B_res": sc["B_res"], "B_root": sc["B_root"]})
    print("identity s*W + (1-s)*B = ILSC_mean: max |diff| = %.2e" % worst_identity)
    print("ILSC_mean against size_mechanism.csv: max |diff| = %.2e, %d of %d matched, "
          "%d resource-count mismatches"
          % (worst_stored, sum(1 for x in rows if x["clean_file"] in ref), len(rows),
             res_mismatch))
    if worst_identity > IDENTITY_TOL:
        sys.exit("the identity does NOT hold - stopping")
    return rows


def corpus_test(rows):
    rng = np.random.default_rng(config.SEED)
    limit = config.SIZE_INDEPENDENCE_RHO_LIMIT
    summary = []

    def add(test, score, value, n, lo="", hi="", verdict=""):
        summary.append({"test": test, "score": score, "value": round(value, 6),
                        "lo": lo if lo == "" else round(lo, 6),
                        "hi": hi if hi == "" else round(hi, 6),
                        "n_services": n, "verdict": verdict})

    def col(sub, key):
        return np.array([float(x[key]) for x in sub])

    def size_block(sub, score, label, rule=False):
        y, prov = col(sub, score), [x["provider"] for x in sub]
        ok = True
        for var, name in (("n_operations", "operations"), ("n_resources", "resources")):
            x = col(sub, var)
            rho = rank_rho(y, x)
            lo, hi = provider_interval(y, x, prov, rng)
            passed = abs(rho) <= limit
            ok = ok and passed
            add("rho(score, %s)" % name, label, rho, len(sub), lo, hi,
                ("pass" if passed else "fail") if rule else "")
        return ok

    N = len(rows)
    size_block(rows, "ILSC_mean", "ILSC_mean, all primary")
    defined = [x for x in rows if np.isfinite(x["B"])]
    add("services where B is defined", "B", len(defined), N)
    add("services with one resource (B undefined)", "B", N - len(defined), N)
    size_block(defined, "ILSC_mean", "ILSC_mean, where B is defined")
    b_pass = size_block(defined, "B", "B", rule=True)
    size_block(defined, "B_res", "B_res")
    size_block([x for x in rows if np.isfinite(x["B_root"])], "B_root", "B_root")
    size_block([x for x in rows if np.isfinite(x["W"])], "W", "W")
    size_block(rows, "same_resource_pair_share", "s")

    b, ops, res = (list(col(defined, k)) for k in ("B", "n_operations", "n_resources"))
    add("partial rho(B, operations | resources)", "B", partial_spearman(b, ops, res),
        len(defined))
    add("partial rho(B, resources | operations)", "B", partial_spearman(b, res, ops),
        len(defined))
    add("rho(B, ILSC_mean)", "B", spearman(b, list(col(defined, "ILSC_mean"))), len(defined))
    both = [x for x in defined if np.isfinite(x["W"])]
    add("rho(B, W)", "B", spearman(list(col(both, "B")), list(col(both, "W"))), len(both))
    add("mean of W - B, services with both", "W-B",
        float(np.mean(col(both, "W") - col(both, "B"))), len(both))
    add("share of services with W > B", "W-B",
        float(np.mean(col(both, "W") > col(both, "B"))), len(both))

    for score in ("ILSC_mean",) + SCORES:
        v = col([x for x in rows if np.isfinite(x[score])], score)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        add("median", score, float(med), len(v))
        add("IQR", score, float(q3 - q1), len(v))
        add("SD", score, float(np.std(v, ddof=1)), len(v))
        add("share at >= 0.999", score, float(np.mean(v >= 0.999)), len(v))
    for lo_, hi_ in BANDS:
        band = "%d-%d" % (lo_, hi_)
        sub = [x for x in rows if x["size_band"] == band]
        for score in ("ILSC_mean", "B", "W"):
            v = col([x for x in sub if np.isfinite(x[score])], score)
            add("median, size band %s" % band, score, float(np.median(v)), len(v))

    for path, data in ((OUT_SERVICES, rows), (OUT_SUMMARY, summary)):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)

    print()
    print("%-44s %-30s %9s %19s %6s %s" % ("test", "score", "value", "95% interval", "n", ""))
    for s in summary:
        iv = "" if s["lo"] == "" else "[%+.3f, %+.3f]" % (s["lo"], s["hi"])
        print("%-44s %-30s %9.4f %19s %6d %s"
              % (s["test"], s["score"], s["value"], iv, s["n_services"], s["verdict"]))
    print()
    print("Test 1 (|rho| <= %.2f with operations and with resources): B %s"
          % (limit, "PASSES" if b_pass else "FAILS"))
    sds = {score: float(np.std(col([x for x in rows if np.isfinite(x[score])], score), ddof=1))
           for score in ("ILSC_mean",) + SCORES}
    return sds, b_pass


# ----------------------------------------------------------------------------
# Test 2: D-33's perturbation, the same draws
# ----------------------------------------------------------------------------

def perturbation_test(pl, sds, scores_path, n_services):
    rng = np.random.default_rng(config.SEED)
    picked, _q3 = inject_mod.top_quartile_services(scores_path, pl, n_services)
    with open(D33_DRAWS, newline="", encoding="utf-8") as fh:
        ref = {(r["service"], r["condition"], int(r["level"]), int(r["draw"])): r["ILSC"]
               for r in csv.DictReader(fh)}
    metrics = ("ILSC",) + SCORES

    def score(idx):
        opset = pl.opset(idx)
        sc = score_set([pl.ops[i] for i in idx], opset)
        return {"ILSC": sim.ilsc_mean(opset), **{m: sc[m] for m in SCORES}}

    rows, worst = [], 0.0
    for si, (name, meta) in enumerate(picked, 1):
        base_idx = pl.by_service[name]
        provider = pl.provider_of[base_idx[0]]
        base = score(base_idx)
        print("  [%2d/%d] %-38s ILSC=%.3f B=%s W=%s"
              % (si, len(picked), meta["title"][:38], base["ILSC"],
                 "%.3f" % base["B"] if np.isfinite(base["B"]) else "undef",
                 "%.3f" % base["W"] if np.isfinite(base["W"]) else "undef"), flush=True)
        for cond in inject_mod.CONDITIONS:
            for level in inject_mod.LEVELS:
                for draw in range(inject_mod.DRAWS):
                    if level == 0:
                        s = base
                    else:
                        don = inject_mod.donor_indices(pl, name, provider, cond, rng, level)
                        s = ({m: NAN for m in metrics} if don is None
                             else score(list(base_idx) + don))
                    v = ref.get((name, cond, level, draw))
                    if v not in (None, "", "nan") and np.isfinite(s["ILSC"]):
                        worst = max(worst, abs(float(v) - s["ILSC"]))
                    rows.append({"service": name, "title": meta["title"], "condition": cond,
                                 "level": level, "draw": draw, **s})
    print("ILSC against D-33's stored draws: max |diff| = %.2e" % worst)
    if worst > DRAWS_TOL:
        sys.exit("draws do NOT match D-33 - stopping")
    with open(OUT_DRAWS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    services = sorted({r["service"] for r in rows})
    levels = inject_mod.LEVELS

    def mean_at(svc, metric, cond, lv):
        v = [r[metric] for r in rows if r["service"] == svc and r["condition"] == cond
             and r["level"] == lv and np.isfinite(r[metric])]
        return float(np.mean(v)) if v else NAN

    summary = []
    for m in metrics:
        gaps, slopes = [], {c: [] for c in inject_mod.CONDITIONS}
        for svc in services:
            sl = {c: inject_mod.ols_slope(levels, [mean_at(svc, m, c, lv) for lv in levels])
                  for c in inject_mod.CONDITIONS}
            for c in inject_mod.CONDITIONS:
                if np.isfinite(sl[c]):
                    slopes[c].append(sl[c])
            gaps.append(sl["cross_provider"] - sl["same_provider"])
        g = [x for x in gaps if np.isfinite(x)]
        p, _n = inject_mod.sign_flip_p(g)
        sd = sds["ILSC_mean" if m == "ILSC" else m]
        base_defined = sum(1 for svc in services
                           if np.isfinite(mean_at(svc, m, "cross_provider", 0)))
        summary.append({
            "metric": m,
            **{"slope_" + c: float(np.mean(slopes[c])) for c in inject_mod.CONDITIONS},
            "mean_gap": float(np.mean(g)), "median_gap": float(np.median(g)),
            "n_services_gap_negative": sum(1 for x in g if x < 0), "n_services": len(g),
            "n_services_defined_at_level_0": base_defined, "sign_flip_p": p,
            "corpus_sd": sd, "gap_in_sd": float(np.mean(g)) / sd if sd > 0 else NAN})
    with open(OUT_CMP, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    print()
    print("%-7s %10s %10s %10s %9s %8s %7s %7s %9s"
          % ("score", "same_svc", "same_prov", "cross_prov", "gap", "gap/SD", "neg", "lvl0", "p"))
    for s in summary:
        print("%-7s %10.4f %10.4f %10.4f %9.4f %8.3f %4d/%-2d %7d %9.2g"
              % (s["metric"], s["slope_same_service"], s["slope_same_provider"],
                 s["slope_cross_provider"], s["mean_gap"], s["gap_in_sd"],
                 s["n_services_gap_negative"], s["n_services"],
                 s["n_services_defined_at_level_0"], s["sign_flip_p"]))
    b = next(s for s in summary if s["metric"] == "B")
    b_pass = b["mean_gap"] < 0 and b["sign_flip_p"] < 0.05
    print()
    print("Test 2 (gap negative, sign-flip p < 0.05): B %s" % ("PASSES" if b_pass else "FAILS"))
    return b_pass


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def selftest():
    # two resources, two operations each
    S = np.array([[1.0, 0.8, 0.2, 0.4],
                  [0.8, 1.0, 0.1, 0.3],
                  [0.2, 0.1, 1.0, 0.6],
                  [0.4, 0.3, 0.6, 1.0]])
    d = decompose(S, ["a", "a", "b", "b"])
    assert abs(d["W"] - 0.7) < 1e-12 and abs(d["B"] - 0.25) < 1e-12, d
    assert abs(d["mean"] - 0.4) < 1e-12 and abs(d["s"] - 1 / 3) < 1e-12, d
    assert abs(d["s"] * d["W"] + (1 - d["s"]) * d["B"] - d["mean"]) < 1e-12, d
    assert abs(d["B_res"] - 0.25) < 1e-12, d
    # unbalanced: a has three operations, b and c one each
    S = np.ones((5, 5))
    S[:3, 3] = S[3, :3] = 0.2
    S[:3, 4] = S[4, :3] = 0.4
    S[3, 4] = S[4, 3] = 0.9
    d = decompose(S, ["a", "a", "a", "b", "c"])
    assert abs(d["B"] - 2.7 / 7) < 1e-12 and abs(d["B_res"] - 0.5) < 1e-12, d
    assert abs(d["W"] - 1.0) < 1e-12 and d["n_same"] == 3 and d["n_diff"] == 7, d
    # one resource: B undefined; all different: W undefined and B is the mean
    d = decompose(S, ["a"] * 5)
    assert np.isnan(d["B"]) and np.isnan(d["B_res"]) and abs(d["W"] - d["mean"]) < 1e-12, d
    d = decompose(S, list("abcde"))
    assert np.isnan(d["W"]) and abs(d["B"] - d["mean"]) < 1e-12, d
    assert abs(rank_rho(np.array([1.0, 2, 3, 4]), np.array([2.0, 4, 6, 9])) - 1) < 1e-12
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description="D-36: within/between-resource split of ILSC_mean.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--n-services", type=int, default=20)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()

    if os.environ.get("PYTHONHASHSEED") != "0":       # F-08: fix the sibling tie-break
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))

    pl = pool_mod.load_pool(include_oversized=False)
    sds, pass1 = corpus_test(corpus_rows(pl))
    print()
    pass2 = perturbation_test(pl, sds, args.scores, args.n_services)
    print()
    print("D-36: Test 1 %s, Test 2 %s" % ("pass" if pass1 else "fail",
                                          "pass" if pass2 else "fail"))


if __name__ == "__main__":
    main()

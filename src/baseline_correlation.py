"""
ILSC - Exp. 4b: which metric best predicts code-level relatedness?

**Why this experiment exists.** Exp. 4 compared ILSC with SIDC and LoCmsg on two
grounds, and neither survives a hard reading:

  * *Perturbation sensitivity* - ILSC beats SIDC but **loses to LoCmsg**.
  * *Discriminating power* - ILSC saturates on 0% of the corpus against 35.8%
    and 77.0%. But ILSC is a mean of six continuous similarities while the
    baselines are proportions over pair counts, so a reviewer can fairly answer
    that we have shown ILSC is **more continuous**, not more **valid**. Comparing
    interquartile ranges across metrics on different scales is not a like-for-like
    test.

The test that settles it is the one neither of those is: **against an external
ground truth, which metric better predicts that two operations are related?**
Experiment 3 already supplies that ground truth - `Sim_code`, the Jaccard of the
code-level entity sets from the code dig - so the comparison costs nothing new
and is not decided by the metrics' scales.

How the baselines are made pair-level
-------------------------------------
SIDC and LoCmsg are service-level scores, but both are defined by counting a
**pair predicate**, and it is that predicate which is compared here:

    SIDC_pair(Oi,Oj)   = 1 if the two operations share >= 1 data type, else 0
    LoCmsg_pair(Oi,Oj) = 1 if their message terms intersect, else 0
                         (the complement of LoCmsg's own predicate, so that
                          higher means more related for all three metrics)

Averaging either predicate over a service's pairs reproduces the published
service-level metric exactly, so nothing has been redefined - the comparison is
against the baselines as their authors specify them, one level down.

**The baselines keep their own inputs.** They read `param_names` and
`schema_names` in full: no availability mask, no D-26 boilerplate exclusion, no
generic-schema exclusion. Giving them ILSC's preprocessing would be implementing
a better metric and calling it the baseline.

What a fair reading requires
----------------------------
Two of the three predictors are **binary**, so a Spearman coefficient is not
directly comparable with ILSC's continuous one - a binary predictor is bounded
by its own coarseness. Three complementary views are therefore reported:

  * **Spearman rho** against `Sim_code`, with a bootstrap CI;
  * **AUC** - the probability that a randomly chosen *related* pair is scored
    above a randomly chosen *unrelated* one, which is scale-free and handles a
    binary predictor natively;
  * **point-biserial style group separation** - mean predictor value for pairs
    with `Sim_code` = 0 versus > 0.

AUC is the primary figure: it is the one measure of the three that a binary and
a continuous predictor can be compared on without advantaging either.

Outputs:
    results/baseline_correlation.csv    per condition x metric
    figures/fig8_baseline_auc.pdf

Usage:
    python src/baseline_correlation.py
"""

import argparse
import csv
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402

import figstyle as fs                            # noqa: E402
import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import bench_prepare as bp                       # noqa: E402
import baselines as bl                           # noqa: E402
import code_correlation as cc                    # noqa: E402

PREDICTORS = ("ILSC", "SIDC_pair", "LoCmsg_pair")


def auc(scores, labels):
    """P(score of a related pair > score of an unrelated one), ties at 0.5.

    The Mann-Whitney U statistic normalised. Scale-free, and it treats a binary
    predictor fairly - which a correlation coefficient does not.
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    sv = s[order]
    i = 0
    while i < len(sv):                            # average tied ranks
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    r_pos = ranks[y].sum()
    n1, n0 = len(pos), len(neg)
    return float((r_pos - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def bootstrap_auc(scores, labels, by_service, n_boot, rng):
    """Cluster bootstrap over services - pairs within a service are dependent."""
    services = sorted(by_service)
    if len(services) < 2:
        return float("nan"), float("nan")
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(services), size=len(services))
        s, y = [], []
        for k in pick:
            for idx in by_service[services[k]]:
                s.append(scores[idx])
                y.append(labels[idx])
        a = auc(s, y)
        if np.isfinite(a):
            vals.append(a)
    if len(vals) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def collect(args):
    """Every benchmark pair with all three predictors and the code ground truth."""
    entities = cc.load_entities()
    emb = emb_mod.Embeddings(args.cache)
    rows = []
    for name in sorted(os.listdir(args.parsed_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(args.parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        system, service = doc.get("system", ""), doc.get("service", "")
        if system not in cc.ENTITY_FILES:
            continue
        ops = doc["operations"]
        ent = [entities.get((system, service, o["method"].upper(), o["path"]))
               for o in ops]

        # baseline pair predicates, on the baselines' own unfiltered inputs
        types = [bl.op_types(o) for o in ops]
        terms = [bl.op_terms(o) for o in ops]

        oset = sim.OpSet.from_service(doc, emb, name)
        for r in sim.pair_table(oset):
            i, j = r["i"], r["j"]
            ei, ej = ent[i], ent[j]
            if ei is None or ej is None:
                continue
            sc = cc.jaccard(ei, ej)
            if sc is None:
                continue
            rows.append({
                "system": system, "service": service,
                "op_i": r["op_i"], "op_j": r["op_j"],
                "sim_code": sc,
                "ILSC": r["sim"],
                "SIDC_pair": 1.0 if (types[i] & types[j]) else 0.0,
                "LoCmsg_pair": 1.0 if (terms[i] & terms[j]) else 0.0,
            })
    return rows


def run(args):
    from scipy import stats
    rng = np.random.default_rng(config.SEED)
    rows = collect(args)
    if not rows:
        sys.exit("no benchmark pairs - run src/bench_prepare.py first")

    out = []
    for cond, system, label in cc.CONDITIONS:
        sub = [r for r in rows if r["system"] == system]
        if not sub:
            continue
        by_service = {}
        for k, r in enumerate(sub):
            by_service.setdefault(r["service"], []).append(k)
        y = np.array([r["sim_code"] for r in sub])
        related = y > 0

        print("\n" + "=" * 72)
        print("%s  (%s, %s)" % (cond, system, label))
        print("=" * 72)
        print("  %d pairs over %d services; %d related (Sim_code > 0), %d not"
              % (len(sub), len(by_service), int(related.sum()), int((~related).sum())))
        print("\n  %-12s %8s %9s %20s %10s %10s"
              % ("predictor", "AUC", "rho", "95% CI (cluster)", "mean|rel", "mean|unrel"))

        for m in PREDICTORS:
            x = np.array([r[m] for r in sub], dtype=float)
            a = auc(x, related)
            lo, hi = bootstrap_auc(x, related, by_service, args.bootstrap, rng)
            rho = float(stats.spearmanr(x, y).statistic) if x.std() > 0 else float("nan")
            mr = float(x[related].mean()) if related.any() else float("nan")
            mu = float(x[~related].mean()) if (~related).any() else float("nan")
            print("  %-12s %8.4f %9.4f   [%.3f, %.3f]   %10.4f %10.4f"
                  % (m, a, rho, lo, hi, mr, mu))
            out.append({"condition": cond, "system": system, "predictor": m,
                        "n_pairs": len(sub), "n_services": len(by_service),
                        "auc": round(a, 6), "auc_ci_lo": round(lo, 4),
                        "auc_ci_hi": round(hi, 4),
                        "spearman_vs_sim_code": round(rho, 6),
                        "mean_when_related": round(mr, 6),
                        "mean_when_unrelated": round(mu, 6)})

        best = max((d for d in out if d["condition"] == cond), key=lambda d: d["auc"])
        ilsc = next(d for d in out if d["condition"] == cond and d["predictor"] == "ILSC")
        print("\n  best predictor of code relatedness: **%s** (AUC %.4f)"
              % (best["predictor"], best["auc"]))
        if best["predictor"] == "ILSC":
            others = [d for d in out if d["condition"] == cond and d["predictor"] != "ILSC"]
            beaten = [d for d in others if d["auc_ci_hi"] < ilsc["auc_ci_lo"]]
            print("  ILSC wins; its CI clears %d of %d baselines outright."
                  % (len(beaten), len(others)))
        else:
            print("  ILSC does NOT win this condition. Report it.")

    path = os.path.join(config.RESULTS_DIR, "baseline_correlation.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        for r in out:
            w.writerow(r)
    print("\nwrote %s" % path)

    print("\n" + "=" * 72)
    print("READING")
    print("=" * 72)
    print("  AUC is the primary figure: it is scale-free, so a binary predictor")
    print("  and a continuous one can be compared without advantaging either.")
    print("  This is the head-to-head the interquartile-range comparison in")
    print("  Exp. 4 could not deliver - it tests which metric better predicts an")
    print("  EXTERNAL ground truth rather than which has the wider spread.")

    figure(out)


def figure(out):
    fs.use()
    conds = [c for c, _s, _l in cc.CONDITIONS if any(d["condition"] == c for d in out)]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    width = 0.26
    xs = np.arange(len(conds))
    for i, m in enumerate(PREDICTORS):
        col, _mk, _ls = fs.series(i)
        vals = [next((d["auc"] for d in out if d["condition"] == c and d["predictor"] == m),
                     np.nan) for c in conds]
        los = [next((d["auc"] - d["auc_ci_lo"] for d in out
                     if d["condition"] == c and d["predictor"] == m), 0) for c in conds]
        his = [next((d["auc_ci_hi"] - d["auc"] for d in out
                     if d["condition"] == c and d["predictor"] == m), 0) for c in conds]
        ax.bar(xs + (i - 1) * width, vals, width * 0.9, color=col, label=m,
               yerr=[los, his], capsize=2.5, error_kw={"linewidth": 0.9})
    ax.axhline(0.5, color=fs.INK_MUTED, linewidth=0.9, linestyle=":")
    ax.annotate("chance", xy=(len(conds) - 0.5, 0.5), xytext=(0, 3),
                textcoords="offset points", ha="right", fontsize=7.5,
                color=fs.INK_SECONDARY)
    ax.set_xticks(xs, [c.replace("_", " ") for c in conds])
    ax.set_ylabel("AUC vs code relatedness")
    ax.set_ylim(0.35, 1.0)
    ax.set_title("Which metric predicts code-level relatedness? (Exp. 4b)")
    ax.legend()
    ax.grid(axis="y")
    p = fs.finish(fig, os.path.join(config.FIGURES_DIR, "fig8_baseline_auc.pdf"))
    print("wrote %s" % p)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 4b - predictive head-to-head.")
    ap.add_argument("--parsed-dir", default=bp.BENCH_PARSED)
    ap.add_argument("--cache", default=bp.BENCH_CACHE)
    ap.add_argument("--bootstrap", type=int, default=2000)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

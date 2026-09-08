"""
ILSC - Experiment 5: are the rankings stable under the choices we made?

H3: ILSC service rankings are stable under reasonable variations of the feature
weights and the threshold tau.

This is also where **D-24's deferred question** gets answered. Gate 1 came out
MARGINAL and the weights were deliberately not tuned, on the grounds that fitting
six weights to ten services is fitting to the test. The honest place to ask
whether the weights matter is here, over 2,136 services.

What is varied
--------------
**Weights.** Each feature's weight is moved by +/-20% and +/-40% in turn and the
six weights renormalised - 24 configurations plus the pinned 1/6 baseline. Moving
one at a time is what isolates a feature's influence; moving all six together
would confound them. The four schemes tested at Gate 1 are included as well, so
the two analyses can be read against each other.

**tau.** The full grid 0.30-0.70 in steps of 0.05 (`config.TAU_GRID`), for
`ILSC_tau` and for the connected-component count of the similarity graph.

What is *not* varied here, and why
----------------------------------
`DROP_VERSION_TOKENS` (D-15) is the third knob the plan names. It cannot be swept
in this pass: it changes the tokenizer, so it changes `T(Oi)`, so it changes the
**f1 embeddings**. Sweeping it honestly requires a full re-parse and re-embed of
the corpus, not a reweighting. `--version-tokens` runs that comparison from two
prepared caches; without them the run says the knob is unmeasured rather than
quietly reporting a two-knob sensitivity analysis as if it were three.

Efficiency note
---------------
Per-feature similarities and the mask are computed **once per service** and then
reweighted for all 29 configurations, because the weights only change the final
weighted average. Re-scoring the corpus 29 times from scratch would take half an
hour to produce numbers that are one dot product apart.

Outputs:
    results/weight_sensitivity.csv   per service x configuration ILSC_mean
    results/kendalls_w.csv           rank concordance across configurations
    results/tau_sweep.csv            ILSC_tau and components across the grid
    figures/fig6_tau_sweep.pdf

Usage:
    python src/sensitivity.py
    python src/sensitivity.py --primary-only --no-components
"""

import argparse
import csv
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402

import figstyle as fs                        # noqa: E402

import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import ilsc as ilsc_mod                          # noqa: E402

DELTAS = (-0.40, -0.20, 0.20, 0.40)


def weight_configs():
    """(name, normalised 6-vector) for every configuration under test."""
    base = np.full(sim.NF, 1.0 / sim.NF)
    out = [("baseline", base.copy())]
    for k, f in enumerate(sim.FEATURES):
        for d in DELTAS:
            w = base.copy()
            w[k] *= (1.0 + d)
            out.append(("%s%+d%%" % (f, int(d * 100)), w / w.sum()))
    # the schemes examined at Gate 1, so D-24 and Exp. 5 can be compared directly
    for name, raw in (("gate1_path_schema", [1, 0.5, 2, 1, 2, 1]),
                      ("gate1_semantic", [3, 0.5, 1, 0.5, 2, 2]),
                      ("gate1_lexical", [0, 1, 1, 1, 0, 0]),
                      ("f1_only", [1, 0, 0, 0, 0, 0])):
        w = np.array(raw, dtype=float)
        out.append((name, w / w.sum()))
    return out


def kendalls_w(rank_matrix):
    """Kendall's W over (configurations x services) ranks, tie-corrected.

    W = 1 means every configuration produces the same ordering; W = 0 means no
    agreement at all.
    """
    m, n = rank_matrix.shape
    if m < 2 or n < 2:
        return float("nan")
    R = rank_matrix.sum(axis=0)
    S = float(((R - R.mean()) ** 2).sum())

    # tie correction, per configuration
    T = 0.0
    for i in range(m):
        _vals, counts = np.unique(rank_matrix[i], return_counts=True)
        T += float(((counts ** 3) - counts).sum())
    denom = (m ** 2) * (n ** 3 - n) - m * T
    return 12.0 * S / denom if denom > 0 else float("nan")


def rank_of(values):
    """Average ranks, ties shared."""
    v = np.asarray(values, dtype=float)
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(len(v), dtype=float)
    sv = v[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def score_service_all(opset, configs, taus, want_components):
    """One pass over a service's pairs -> ILSC_mean per config, ILSC_tau per tau."""
    n = opset.n
    n_pairs = n * (n - 1) // 2
    totals = np.zeros(len(configs))
    tau_counts = np.zeros(len(taus))
    if n_pairs == 0:
        return totals, tau_counts, {}, 0

    W = np.array([w for _name, w in configs])            # (C, 6)
    uf = ilsc_mod.UnionFind(n) if want_components else None
    ufs = {t: ilsc_mod.UnionFind(n) for t in taus} if want_components else {}

    for i0, i1, _s, per, mask in sim.pair_blocks(opset):
        sel = sim.triu_selector(i0, i1, n)
        p = per[sel]                                     # (P, 6)
        m = mask[sel].astype("float64")                  # (P, 6)
        # Sim under every configuration at once: (P,6)x(6,C) with a masked denom
        num = (p * m) @ W.T                              # (P, C)
        den = m @ W.T                                    # (P, C)
        with np.errstate(divide="ignore", invalid="ignore"):
            s_all = np.where(den > 0, num / np.where(den == 0, 1, den), 0.0)
        totals += s_all.sum(axis=0)

        baseline = s_all[:, 0]
        for ti, t in enumerate(taus):
            tau_counts[ti] += float((baseline >= t).sum())

        if want_components:
            rows, cols = np.nonzero(sel)
            for ti, t in enumerate(taus):
                hit = baseline >= t
                for a, j in zip(rows[hit], cols[hit]):
                    ufs[t].union(i0 + int(a), int(j))

    comps = {}
    if want_components:
        for t, u in ufs.items():
            comps[t] = len({u.find(i) for i in range(n)})
    return totals / n_pairs, tau_counts / n_pairs, comps, n_pairs


def run(args):
    emb = emb_mod.Embeddings(args.cache)
    manifest = ilsc_mod.load_manifest(args.manifest)
    configs = weight_configs()
    taus = list(config.TAU_GRID)
    names = [n for n, _w in configs]
    print("%d weight configurations, %d tau values" % (len(configs), len(taus)))

    files = sorted(n for n in os.listdir(args.parsed_dir) if n.endswith(".json"))
    if args.limit:
        files = files[:args.limit]

    rows, tau_rows = [], []
    t0 = time.time()
    for i, name in enumerate(files, 1):
        if i % 200 == 0:
            print("  ... %d/%d  (%.0fs)" % (i, len(files), time.time() - t0), flush=True)
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        meta = manifest.get(clean, {})
        oversized = str(meta.get("oversized", "")).strip().lower() in ("1", "true", "yes")
        if args.primary_only and oversized:
            continue
        if name not in emb:
            continue
        with open(os.path.join(args.parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = sim.OpSet.from_service(doc, emb, name)
        if oset.n < 2:
            continue
        want_comp = (not args.no_components
                     and oset.n <= ilsc_mod.COMPONENT_MAX_OPERATIONS)
        means, tau_dens, comps, n_pairs = score_service_all(oset, configs, taus, want_comp)

        rows.append({"clean_file": clean, "title": doc.get("title", ""),
                     "source": doc.get("source", ""), "oversized": int(oversized),
                     "n_operations": oset.n,
                     **{names[k]: means[k] for k in range(len(names))}})
        tau_rows.append({"clean_file": clean, "n_operations": oset.n,
                         **{"tau_%.2f" % t: tau_dens[ti] for ti, t in enumerate(taus)},
                         **{"comp_%.2f" % t: comps.get(t, "") for t in taus}})

    if not rows:
        sys.exit("no services scored")
    print("\nscored %d services in %.0fs" % (len(rows), time.time() - t0))

    # ---- weights ----------------------------------------------------------
    mat = np.array([[r[n] for r in rows] for n in names])        # (C, S)
    ranks = np.array([rank_of(mat[i]) for i in range(len(names))])
    W_all = kendalls_w(ranks)
    pm = [i for i, n in enumerate(names) if "%" in n]            # the +/-20/40 family
    W_pm = kendalls_w(ranks[pm]) if len(pm) > 1 else float("nan")

    from scipy import stats
    base = mat[0]
    print("\n" + "=" * 72)
    print("WEIGHT SENSITIVITY  (H3)")
    print("=" * 72)
    print("  Kendall's W, +/-20/40%% family only : %.4f" % W_pm)
    print("  Kendall's W, all %2d configurations : %.4f" % (len(names), W_all))
    print("\n  Spearman against the pinned baseline, worst first:")
    per_cfg = []
    for i, n in enumerate(names):
        if i == 0:
            continue
        rho = float(stats.spearmanr(base, mat[i]).statistic)
        shift = float(np.mean(np.abs(mat[i] - base)))
        per_cfg.append((rho, shift, n))
    for rho, shift, n in sorted(per_cfg)[:8]:
        print("    %-22s rho = %.4f   mean |dILSC| = %.4f" % (n, rho, shift))
    worst_pm = min((c for c in per_cfg if "%" in c[2]), default=None)
    if worst_pm:
        print("\n  Worst of the +/-20/40%% family: %s at rho = %.4f"
              % (worst_pm[2], worst_pm[0]))

    # ---- tau --------------------------------------------------------------
    print("\n" + "=" * 72)
    print("TAU SWEEP")
    print("=" * 72)
    print("  %6s %12s %14s %14s" % ("tau", "mean ILSC_t", "mean comps", "services w/ comps"))
    tau_summary = []
    for ti, t in enumerate(taus):
        dens = [r["tau_%.2f" % t] for r in tau_rows]
        comps = [r["comp_%.2f" % t] for r in tau_rows if r["comp_%.2f" % t] != ""]
        tau_summary.append({"tau": t, "mean_ilsc_tau": float(np.mean(dens)),
                            "median_ilsc_tau": float(np.median(dens)),
                            "mean_components": float(np.mean(comps)) if comps else float("nan"),
                            "n_services_components": len(comps)})
        print("  %6.2f %12.4f %14.2f %14d"
              % (t, tau_summary[-1]["mean_ilsc_tau"],
                 tau_summary[-1]["mean_components"], len(comps)))

    write(rows, names, tau_rows, tau_summary, ranks, names, W_all, W_pm, per_cfg, taus)
    figure(tau_summary, taus)
    return rows


def write(rows, names, tau_rows, tau_summary, ranks, cfg_names, W_all, W_pm,
          per_cfg, taus):
    p = os.path.join(config.RESULTS_DIR, "weight_sensitivity.csv")
    cols = ["clean_file", "title", "source", "oversized", "n_operations"] + names
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote %s" % p)

    p = os.path.join(config.RESULTS_DIR, "kendalls_w.csv")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["statistic", "value", "note"])
        w.writerow(["kendalls_w_pm_family", "%.6f" % W_pm,
                    "the +/-20/40% perturbations only - the H3 test"])
        w.writerow(["kendalls_w_all_configs", "%.6f" % W_all,
                    "including the deliberately extreme Gate 1 schemes"])
        w.writerow(["n_services", len(rows), ""])
        w.writerow([])
        w.writerow(["configuration", "spearman_vs_baseline", "mean_abs_delta_ilsc"])
        for rho, shift, n in sorted(per_cfg):
            w.writerow([n, "%.6f" % rho, "%.6f" % shift])
    print("wrote %s" % p)

    p = os.path.join(config.RESULTS_DIR, "tau_sweep.csv")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tau_summary[0]))
        w.writeheader()
        for r in tau_summary:
            w.writerow(r)
    print("wrote %s" % p)


def figure(tau_summary, taus):
    """Two stacked panels sharing one x-axis - deliberately NOT a twin axis.

    Edge density and component count are different measures on different scales.
    Putting them on two y-scales in one frame lets whoever draws it decide where
    the curves cross, which is the most misleading thing a chart can do. Stacked
    panels keep the shared x-axis that makes them comparable and drop the false
    crossing point entirely.
    """
    fs.use()
    x = [d["tau"] for d in tau_summary]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.2, 4.6), sharex=True,
                                   gridspec_kw={"hspace": 0.16})

    c, m, ls = fs.series(0)
    ax1.plot(x, [d["mean_ilsc_tau"] for d in tau_summary], marker=m, linestyle=ls,
             color=c)
    ax1.set_ylabel(r"mean ILSC$_\tau$")
    ax1.set_title(r"Edge density and graph fragmentation across the $\tau$ grid")
    ax1.grid(axis="y")

    c, m, ls = fs.series(1)
    ax2.plot(x, [d["mean_components"] for d in tau_summary], marker=m, linestyle=ls,
             color=c)
    ax2.set_ylabel("mean components")
    ax2.set_xlabel(r"threshold $\tau$")
    ax2.set_xticks(x)
    ax2.grid(axis="y")

    for ax, lab in ((ax1, "edge density"), (ax2, "connected components")):
        ax.axvline(config.TAU_DEFAULT, color=fs.INK_MUTED, linewidth=0.9,
                   linestyle=":", zorder=0)
        ax.annotate(lab, xy=(0.985, 0.9), xycoords="axes fraction",
                    ha="right", va="top", fontsize=8, color=fs.INK_SECONDARY)
    ax1.annotate(r"pinned $\tau$ = %.2f" % config.TAU_DEFAULT,
                 xy=(config.TAU_DEFAULT, 1.0), xycoords=("data", "axes fraction"),
                 xytext=(4, -9), textcoords="offset points",
                 fontsize=7.5, color=fs.INK_MUTED)

    p = fs.finish(fig, os.path.join(config.FIGURES_DIR, "fig6_tau_sweep.pdf"))
    print("wrote %s" % p)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 5 - weight and tau sensitivity.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--primary-only", action="store_true", default=True)
    ap.add_argument("--all-services", dest="primary_only", action="store_false",
                    help="include oversized services (D-17 sensitivity population)")
    ap.add_argument("--no-components", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

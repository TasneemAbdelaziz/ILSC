"""
ILSC - Experiment 3 (Gate 2): does interface similarity track code relatedness?

H1 [v3]: interface-level pairwise similarity correlates with code-based
structural relatedness **at the operation-pair level**.

For every within-service operation pair the interface side gives `Sim(Oi,Oj)`
from the engine, and the code side gives

    Sim_code(Oi,Oj) = Jaccard(entities_i, entities_j)

from the code dig. The two are correlated with Spearman's rho - not Pearson.
`Sim_code` is a heavily tied five-to-twelve level variable, not a continuous one,
and Pearson on it would be reporting a number its own assumptions do not support.

**The two systems are never pooled (D-16).** Sock Shop's specifications are
hand-written and independent of its code; Train Ticket's were generated from its
code by Springfox introspection, so its correlation is partly circular by
construction. Reporting one pooled coefficient would average a clean estimate
with an inflated one and describe neither. `rho_independent` and `rho_derived`
are reported side by side, and the distance between them is the estimate of how
much specification-code derivation inflates the correlation - a finding a
single-system design cannot produce.

Two confidence intervals, deliberately
--------------------------------------
Pairs inside one service are not independent observations: they share operations,
and a service with n operations contributes C(n,2) pairs that move together. So
two intervals are reported for every coefficient:

  **pair bootstrap**     resamples pairs. Narrow, and *overstates* precision by
                         ignoring the clustering. Reported because it is what a
                         reader would compute by default.
  **cluster bootstrap**  resamples whole services. Wider and honest about the
                         real number of independent units - which for Sock Shop
                         is 4, not 122 (F-04).

Where the two disagree sharply, the cluster interval is the one to quote.

Gate 2 (proposal Sec. 12): pair-level rho < 0.4 means diagnose before writing -
tokenisation, weights, or entity-extraction quality. rho in 0.4-0.6 is reframed
honestly as "moderate correlation, complementary signal".

Outputs:
    results/code_correlation_pairs.csv    every pair, both similarities
    results/code_correlation_summary.csv  rho per condition and level, with CIs
    results/discordance.csv               the pairs worth explaining in prose
    figures/fig4_pair_scatter.pdf         pair level, discordant cases marked
    figures/fig5_service_scatter.pdf      service level

Usage:
    python src/code_correlation.py
    python src/code_correlation.py --bootstrap 5000
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

import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import bench_prepare as bp                       # noqa: E402

CONDITIONS = (
    ("independent", "sockshop", "hand-written specs"),
    ("derived", "trainticket", "specs generated from source"),
)

ENTITY_FILES = {
    "sockshop": "endpoint_entities.csv",
    "trainticket": "endpoint_entities_trainticket.csv",
}

# A pair is discordant when the two sides disagree strongly. These bounds only
# select cases for written explanation; no result depends on them.
HIGH_INTERFACE, LOW_CODE = 0.55, 0.0
LOW_INTERFACE, HIGH_CODE = 0.30, 1.0


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------

def load_entities():
    """(system, service, METHOD, path) -> set of entity names."""
    out = {}
    for system, fname in ENTITY_FILES.items():
        path = os.path.join(config.RESULTS_DIR, fname)
        if not os.path.exists(path):
            print("  missing %s - %s will be skipped" % (fname, system))
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                key = (system, r["service"], r["method"].upper(), r["path"])
                out[key] = {e for e in r["entities"].split("|") if e}
    return out


def jaccard(a, b):
    if not a and not b:
        return None            # neither side touches an entity: no evidence
    return len(a & b) / len(a | b)


# ----------------------------------------------------------------------------
# Pair table
# ----------------------------------------------------------------------------

def build_pairs(entities, cache_dir, parsed_dir):
    emb = emb_mod.Embeddings(cache_dir)
    rows, unmatched = [], 0
    for name in sorted(os.listdir(parsed_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        system, service = doc.get("system", ""), doc.get("service", "")
        if system not in ENTITY_FILES:
            continue
        ops = doc["operations"]
        ent = []
        for o in ops:
            key = (system, service, o["method"].upper(), o["path"])
            if key not in entities:
                unmatched += 1
            ent.append(entities.get(key))

        oset = sim.OpSet.from_service(doc, emb, name)
        for r in sim.pair_table(oset):
            ei, ej = ent[r["i"]], ent[r["j"]]
            if ei is None or ej is None:
                continue                       # endpoint absent from the code dig
            sc = jaccard(ei, ej)
            if sc is None:
                continue                       # both sides entity-free: no evidence
            rows.append({
                "system": system, "service": service,
                "op_i": r["op_i"], "op_j": r["op_j"],
                "sim_interface": r["sim"], "sim_code": sc,
                "entities_i": "|".join(sorted(ei)), "entities_j": "|".join(sorted(ej)),
                **{f: r[f] for f in sim.FEATURES},
            })
    return rows, unmatched


# ----------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------

def spearman(x, y):
    from scipy import stats
    if len(x) < 3:
        return float("nan"), float("nan")
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan"), float("nan")
    r = stats.spearmanr(x, y)
    return float(r.statistic), float(r.pvalue)


def bootstrap_ci(rows, by_service, n_boot, rng):
    """(pair-bootstrap CI, cluster-bootstrap CI) for Spearman rho."""
    x = np.array([r["sim_interface"] for r in rows])
    y = np.array([r["sim_code"] for r in rows])
    n = len(rows)
    if n < 5:
        return (float("nan"),) * 4

    pair_vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        r, _p = spearman(x[idx], y[idx])
        if np.isfinite(r):
            pair_vals.append(r)

    services = sorted(by_service)
    clus_vals = []
    if len(services) >= 2:
        for _ in range(n_boot):
            pick = rng.integers(0, len(services), size=len(services))
            xs, ys = [], []
            for k in pick:
                for rr in by_service[services[k]]:
                    xs.append(rr["sim_interface"])
                    ys.append(rr["sim_code"])
            r, _p = spearman(np.array(xs), np.array(ys))
            if np.isfinite(r):
                clus_vals.append(r)

    def ci(v):
        if len(v) < 20:
            return float("nan"), float("nan")
        return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))

    return ci(pair_vals) + ci(clus_vals)


def tie_profile(y):
    vals, counts = np.unique(np.round(y, 6), return_counts=True)
    top = counts.max() / len(y) if len(y) else float("nan")
    return len(vals), 100.0 * top


# ----------------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------------

def run(args):
    rng = np.random.default_rng(config.SEED)
    entities = load_entities()
    if not entities:
        sys.exit("no entity files found - run the code dig first")
    rows, unmatched = build_pairs(entities, args.cache, args.parsed_dir)
    if not rows:
        sys.exit("no pairs could be joined")

    print("joined %d within-service pairs (%d operations had no code row)"
          % (len(rows), unmatched))

    summary = []
    for cond, system, label in CONDITIONS:
        sub = [r for r in rows if r["system"] == system]
        if not sub:
            print("\n%s (%s): no pairs" % (cond, system))
            continue
        by_service = {}
        for r in sub:
            by_service.setdefault(r["service"], []).append(r)
        # a service whose code side is constant contributes nothing to rho
        varying = {s: v for s, v in by_service.items()
                   if len({round(r["sim_code"], 6) for r in v}) > 1}

        x = np.array([r["sim_interface"] for r in sub])
        y = np.array([r["sim_code"] for r in sub])
        rho, p = spearman(x, y)
        lo_p, hi_p, lo_c, hi_c = bootstrap_ci(sub, by_service, args.bootstrap, rng)
        n_levels, top_share = tie_profile(y)

        print("\n" + "=" * 72)
        print("rho_%s   (%s, %s)" % (cond, system, label))
        print("=" * 72)
        print("  pairs                       %d over %d services" % (len(sub), len(by_service)))
        print("  services with code variance %d  (the rest cannot inform rho)"
              % len(varying))
        print("  Sim_code levels             %d, largest holds %.1f%% of pairs"
              % (n_levels, top_share))
        print("  Spearman rho                %.4f   (p = %.3g)" % (rho, p))
        print("  95%% CI, pair bootstrap      [%.3f, %.3f]" % (lo_p, hi_p))
        print("  95%% CI, cluster bootstrap   [%.3f, %.3f]   <- quote this one"
              % (lo_c, hi_c))

        # service level: mean interface similarity vs mean code similarity
        svc_x = [float(np.mean([r["sim_interface"] for r in v])) for v in by_service.values()]
        svc_y = [float(np.mean([r["sim_code"] for r in v])) for v in by_service.values()]
        srho, sp = spearman(np.array(svc_x), np.array(svc_y))
        print("  service-level rho           %.4f  (n = %d services%s)"
              % (srho, len(svc_x),
                 ", too few to interpret" if len(svc_x) < 8 else ""))

        summary.append({
            "condition": cond, "system": system, "spec_origin": label,
            "n_pairs": len(sub), "n_services": len(by_service),
            "n_services_with_variance": len(varying),
            "sim_code_levels": n_levels, "largest_tie_pct": round(top_share, 2),
            "rho_pair": round(rho, 6), "p_pair": p,
            "ci_pair_lo": round(lo_p, 4), "ci_pair_hi": round(hi_p, 4),
            "ci_cluster_lo": round(lo_c, 4), "ci_cluster_hi": round(hi_c, 4),
            "rho_service": round(srho, 6) if np.isfinite(srho) else "",
            "p_service": sp,
        })

    verdict(summary)
    write_outputs(rows, summary, args)
    return summary


def verdict(summary):
    print("\n" + "=" * 72)
    print("GATE 2")
    print("=" * 72)
    ind = next((s for s in summary if s["condition"] == "independent"), None)
    der = next((s for s in summary if s["condition"] == "derived"), None)

    if ind and der:
        gap = der["rho_pair"] - ind["rho_pair"]
        print("  rho_independent  %.4f   (Sock Shop, hand-written)" % ind["rho_pair"])
        print("  rho_derived      %.4f   (Train Ticket, generated from source)"
              % der["rho_pair"])
        print("  difference       %+.4f   <- the derivation-inflation estimate (D-16)"
              % gap)
        if gap > 0:
            print("  Positive, as D-16 predicts: correlating an interface against the")
            print("  code it was generated from reads higher. This is why the two are")
            print("  never pooled.")
        else:
            print("  NOT positive. D-16 expected derivation to inflate the estimate;")
            print("  it did not. Report that rather than the expectation.")

    primary = ind or der
    if not primary:
        print("  no coefficient computed")
        return
    r = primary["rho_pair"]
    if r >= 0.6:
        print("\n  Gate 2: PASS (rho >= 0.6)")
    elif r >= 0.4:
        print("\n  Gate 2: PASS with the honest reframing the proposal specifies -")
        print("  'moderate correlation, complementary signal'. The interface and the")
        print("  code carry partly independent information, which is arguably the")
        print("  more interesting finding.")
    else:
        print("\n  Gate 2: BELOW THRESHOLD (rho < 0.4) on the primary condition.")
        print("  Proposal instruction: diagnose before writing - tokenisation,")
        print("  feature weights, or entity-extraction quality.")
    if primary["n_services_with_variance"] < 3:
        print("\n  READ WITH CARE (F-04): only %d service(s) on this condition have any"
              % primary["n_services_with_variance"])
        print("  code-side variance, so the coefficient is close to a single-service")
        print("  result. The cluster-bootstrap interval, not the point estimate, is")
        print("  what should appear in the paper.")


def write_outputs(rows, summary, args):
    pairs_path = os.path.join(config.RESULTS_DIR, "code_correlation_pairs.csv")
    cols = ["system", "service", "op_i", "op_j", "sim_interface", "sim_code",
            "entities_i", "entities_j"] + list(sim.FEATURES)
    with open(pairs_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    sum_path = os.path.join(config.RESULTS_DIR, "code_correlation_summary.csv")
    if summary:
        with open(sum_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(summary[0]))
            w.writeheader()
            for r in summary:
                w.writerow(r)

    disc = [r for r in rows
            if (r["sim_interface"] >= HIGH_INTERFACE and r["sim_code"] <= LOW_CODE)
            or (r["sim_interface"] <= LOW_INTERFACE and r["sim_code"] >= HIGH_CODE)]
    disc.sort(key=lambda r: -abs(r["sim_interface"] - r["sim_code"]))
    disc_path = os.path.join(config.RESULTS_DIR, "discordance.csv")
    with open(disc_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols + ["kind"], extrasaction="ignore")
        w.writeheader()
        for r in disc:
            r = dict(r)
            r["kind"] = ("interface_high_code_low"
                         if r["sim_interface"] > r["sim_code"] else
                         "code_high_interface_low")
            w.writerow(r)

    print("\nwrote %s (%d pairs)" % (pairs_path, len(rows)))
    print("wrote %s" % sum_path)
    print("wrote %s (%d discordant pairs)" % (disc_path, len(disc)))
    if disc:
        print("\n  the sharpest discordant cases - these need paragraph explanations:")
        for r in disc[:6]:
            print("   %-11s %-24s interface %.2f  code %.2f"
                  % (r["system"], r["service"][:24], r["sim_interface"], r["sim_code"]))
            print("       %s" % r["op_i"][:64])
            print("       %s" % r["op_j"][:64])

    figures(rows, summary)


def figures(rows, summary):
    os.makedirs(config.FIGURES_DIR, exist_ok=True)
    colours = {"sockshop": "#b2182b", "trainticket": "#2166ac"}

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.9), sharey=True)
    for ax, (cond, system, label) in zip(axes, CONDITIONS):
        sub = [r for r in rows if r["system"] == system]
        if not sub:
            ax.set_visible(False)
            continue
        x = np.array([r["sim_interface"] for r in sub])
        y = np.array([r["sim_code"] for r in sub])
        # jitter y only, so tied code levels are visible as bands
        jitter = (np.random.default_rng(config.SEED).random(len(y)) - 0.5) * 0.035
        ax.scatter(x, y + jitter, s=11, alpha=0.35, color=colours.get(system, "grey"),
                   edgecolors="none")
        s = next((d for d in summary if d["condition"] == cond), None)
        if s:
            ax.set_title(r"$\rho_{%s}$ = %.3f   (n = %d pairs)"
                         % (cond, s["rho_pair"], s["n_pairs"]), fontsize=9.5)
        ax.set_xlabel("interface similarity  Sim$(O_i,O_j)$")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.08, 1.08)
        ax.grid(alpha=0.25, linewidth=0.6)
    axes[0].set_ylabel("code similarity  Jaccard(entities)")
    fig.suptitle("Interface vs code relatedness, by specification origin (D-16)",
                 fontsize=10)
    fig.tight_layout()
    p4 = os.path.join(config.FIGURES_DIR, "fig4_pair_scatter.pdf")
    fig.savefig(p4, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote %s" % p4)

    fig, ax = plt.subplots(figsize=(5.0, 3.9))
    for cond, system, label in CONDITIONS:
        sub = [r for r in rows if r["system"] == system]
        if not sub:
            continue
        by = {}
        for r in sub:
            by.setdefault(r["service"], []).append(r)
        xs = [np.mean([r["sim_interface"] for r in v]) for v in by.values()]
        ys = [np.mean([r["sim_code"] for r in v]) for v in by.values()]
        ax.scatter(xs, ys, s=34, alpha=0.8, color=colours.get(system, "grey"),
                   label="%s (n=%d services)" % (system, len(xs)))
    ax.set_xlabel("mean interface similarity")
    ax.set_ylabel("mean code similarity")
    ax.set_title("Service level", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(alpha=0.25, linewidth=0.6)
    fig.tight_layout()
    p5 = os.path.join(config.FIGURES_DIR, "fig5_service_scatter.pdf")
    fig.savefig(p5, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote %s" % p5)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 3 - code correlation (Gate 2).")
    ap.add_argument("--parsed-dir", default=bp.BENCH_PARSED)
    ap.add_argument("--cache", default=bp.BENCH_CACHE)
    ap.add_argument("--bootstrap", type=int, default=2000)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

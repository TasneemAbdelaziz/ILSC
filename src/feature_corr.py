"""
ILSC - Day 6 metric track: the inter-feature correlation matrix (Fig 9).

Sec. 10, Day 5 [v3]: "Compute the inter-feature correlation matrix over all
pairs. If any pair of features correlates above ~0.85, say so in the paper and
discuss whether the weight scheme should reflect it."

This exists to pre-empt the obvious reviewer question - *why six features if
they measure the same thing?* - and to give the equal 1/6 weights an empirical
defence rather than an aesthetic one.

Two things it does that a naive correlation would get wrong
-----------------------------------------------------------
**Pairwise-complete, not listwise.** A pair where f6 is masked has no f6 value
at all; it is not a zero. Dropping every pair that is missing *any* feature
(listwise deletion) would restrict the matrix to fully-documented pairs, which
are a minority and a biased one - exactly the pairs where the mask never fires.
Each cell is therefore computed on the pairs where **both** of its two features
are available, and the n for each cell is reported alongside it.

**Sampled across services, not concatenated within one.** Correlating over all
pairs of one huge service would describe that service. Pairs are drawn service
by service, capped per service, so no single specification dominates - the same
reasoning as D-17, applied to a different statistic.

Both Pearson (the proposal asks for it) and Spearman are reported. Several
features are bounded, spiky and zero-inflated - Jaccard on short token sets is
0 or 1 far more often than a Pearson correlation assumes - so if the two
disagree, Spearman is the one to trust and the disagreement is itself worth a
sentence in the paper.

Outputs:
    results/feature_correlation.csv     long form: fa, fb, pearson, spearman, n
    figures/fig9_feature_correlation.pdf

Usage:
    python src/feature_corr.py
    python src/feature_corr.py --max-pairs-per-service 2000 --include-oversized
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
import ilsc as ilsc_mod                          # noqa: E402

HIGH = 0.85                                      # the threshold the proposal names


def collect(parsed_dir, cache_dir, manifest_path, max_per_service,
            include_oversized, limit, seed):
    """Sample pairs across services; return (values, mask) arrays of shape (P, 6)."""
    rng = np.random.default_rng(seed)
    emb = emb_mod.Embeddings(cache_dir)
    manifest = ilsc_mod.load_manifest(manifest_path)
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    if limit:
        files = files[:limit]

    vals, masks = [], []
    n_services = 0
    for i, name in enumerate(files, 1):
        if i % 250 == 0:
            print("  ... %d/%d services, %s pairs"
                  % (i, len(files), "{:,}".format(sum(len(v) for v in vals))), flush=True)
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        row = manifest.get(clean, {})
        oversized = str(row.get("oversized", "")).strip().lower() in ("1", "true", "yes")
        if oversized and not include_oversized:
            continue
        if name not in emb:
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = sim.OpSet.from_service(doc, emb, name)
        if oset.n < 2:
            continue

        got_v, got_m = [], []
        for i0, i1, _s, per, mask in sim.pair_blocks(oset):
            sel = sim.triu_selector(i0, i1, oset.n)
            got_v.append(per[sel])
            got_m.append(mask[sel])
        v = np.concatenate(got_v) if got_v else np.zeros((0, sim.NF))
        m = np.concatenate(got_m) if got_m else np.zeros((0, sim.NF), dtype=bool)
        if len(v) > max_per_service:
            pick = rng.choice(len(v), size=max_per_service, replace=False)
            v, m = v[pick], m[pick]
        vals.append(v)
        masks.append(m)
        n_services += 1

    V = np.concatenate(vals) if vals else np.zeros((0, sim.NF))
    M = np.concatenate(masks) if masks else np.zeros((0, sim.NF), dtype=bool)
    print("  sampled %s pairs from %d services" % ("{:,}".format(len(V)), n_services))
    return V, M, n_services


def _rank(x):
    """Average ranks, ties shared - what Spearman needs."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype="float64")
    ranks[order] = np.arange(len(x), dtype="float64")
    # average tied groups
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def _corr(a, b):
    if len(a) < 3:
        return float("nan")
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return float("nan")
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def matrices(V, M):
    P = np.full((sim.NF, sim.NF), np.nan)
    S = np.full((sim.NF, sim.NF), np.nan)
    N = np.zeros((sim.NF, sim.NF), dtype="int64")
    for a in range(sim.NF):
        for b in range(sim.NF):
            both = M[:, a] & M[:, b]
            N[a, b] = int(both.sum())
            if N[a, b] < 3:
                continue
            xa, xb = V[both, a], V[both, b]
            P[a, b] = _corr(xa, xb)
            S[a, b] = _corr(_rank(xa), _rank(xb))
    return P, S, N


def figure(S, N, path):
    fig, ax = plt.subplots(figsize=(5.6, 4.9))
    im = ax.imshow(S, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(sim.NF), sim.FEATURES)
    ax.set_yticks(range(sim.NF), sim.FEATURES)
    for a in range(sim.NF):
        for b in range(sim.NF):
            if not np.isfinite(S[a, b]):
                continue
            strong = abs(S[a, b]) > 0.55
            ax.text(b, a, "%.2f" % S[a, b], ha="center", va="center", fontsize=8.5,
                    color="white" if strong else "black",
                    fontweight="bold" if abs(S[a, b]) >= HIGH and a != b else "normal")
    ax.set_title("Inter-feature rank correlation over within-service pairs",
                 fontsize=9.5, pad=10)
    fig.colorbar(im, ax=ax, fraction=0.046, label="Spearman $\\rho$")
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def run(args):
    V, M, n_services = collect(args.parsed_dir, args.cache, args.manifest,
                               args.max_pairs_per_service, args.include_oversized,
                               args.limit, config.SEED)
    if len(V) == 0:
        sys.exit("no pairs sampled")
    P, S, N = matrices(V, M)

    print("\nSpearman (upper) / Pearson (lower), pairwise-complete\n")
    print("        " + "".join("%9s" % f for f in sim.FEATURES))
    for a, fa in enumerate(sim.FEATURES):
        cells = []
        for b in range(sim.NF):
            v = S[a, b] if b >= a else P[a, b]
            cells.append("%9s" % ("--" if not np.isfinite(v) else "%.3f" % v))
        print("  %-6s%s" % (fa, "".join(cells)))

    print("\navailability of each feature, as a share of sampled pairs:")
    for a, fa in enumerate(sim.FEATURES):
        print("   %-4s %6.2f%%" % (fa, 100.0 * N[a, a] / len(V)))

    flagged = [(sim.FEATURES[a], sim.FEATURES[b], S[a, b], N[a, b])
               for a in range(sim.NF) for b in range(a + 1, sim.NF)
               if np.isfinite(S[a, b]) and abs(S[a, b]) >= HIGH]
    print("\nfeature pairs correlating at |rho| >= %.2f: %d" % (HIGH, len(flagged)))
    for fa, fb, r, n in flagged:
        print("   %s-%s  rho=%.3f  n=%s" % (fa, fb, r, "{:,}".format(n)))
    if not flagged:
        print("   none - the six features are not redundant, and the equal 1/6")
        print("   weighting is not concealing a duplicated signal.")

    out = os.path.join(config.RESULTS_DIR, args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["feature_a", "feature_b", "pearson", "spearman", "n_pairs_both_available"])
        for a in range(sim.NF):
            for b in range(sim.NF):
                w.writerow([sim.FEATURES[a], sim.FEATURES[b],
                            "" if not np.isfinite(P[a, b]) else "%.6f" % P[a, b],
                            "" if not np.isfinite(S[a, b]) else "%.6f" % S[a, b],
                            int(N[a, b])])
    print("\nwrote %s" % out)

    fig_path = os.path.join(config.FIGURES_DIR, "fig9_feature_correlation.pdf")
    figure(S, N, fig_path)
    print("wrote %s" % fig_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inter-feature correlation (Fig 9).")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--out", default="feature_correlation.csv")
    ap.add_argument("--max-pairs-per-service", type=int, default=2000)
    ap.add_argument("--include-oversized", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

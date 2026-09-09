"""
ILSC - construct validity under size control, and size-stratified thresholds.

**Why this script exists.** Two results in this study are entangled and neither
can be read without the other.

  1. ``ILSC_mean`` falls with service size: Spearman rho = -0.55 against
     ``n_operations`` over the primary corpus. Nothing in the metric corrects for
     this, and ``ILSC_norm`` cannot: D-21 established that E[ILSC_rand(n)] is flat
     in n, so the normalisation is an affine rescale that inherits the size
     dependence in full.

  2. The provider-matched gate (D-29) compares a single-capability service against
     a many-capability service from the same publisher and finds +0.105. But the
     single-capability side is a median of 9 operations against 52 - smaller in 15
     of 16 pairs - so the design confounds capability count with size, and a
     size-matched null reproduces the effect (p = 0.335 against that null).

The author's tag count and the operation count are themselves correlated at
Spearman +0.667, which is *why* a 16-pair matched design cannot separate them.
A paired design at that sample size has no way to hold one fixed while the other
varies. The corpus does: 1,570 services carry at least one author tag, over 503
providers.

So this script runs the analysis the matched gate was reaching for, on the whole
corpus instead of sixteen pairs:

    ILSC_mean ~ log2(n_tags) + log2(n_operations) + provider fixed effects

with standard errors clustered by provider, because services from one publisher
share house style and are not independent observations. If the coefficient on
log2(n_tags) survives with the size term in the model, then ILSC responds to how
many capabilities a service declares and not only to how large it is - which is
the construct claim, tested rather than asserted.

It also derives the **size-stratified quartile thresholds** that finding (1)
requires. A single pooled threshold grades a service largely on how many
operations it declares; a practitioner could move a service from red to green by
splitting its specification. Thresholds are therefore published per size band.

Outputs:
    results/construct_validity.csv     regression models M1-M4
    results/size_thresholds.csv        quartiles per size band, pooled and S1-only
    figures/fig11_size_and_tags.pdf    the two effects, side by side

Usage:
    python src/construct_validity.py
"""

import argparse
import collections
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

TAG_CACHE = os.path.join(config.ROOT, ".cache", "author_tags.json")

# Fixed in advance, on the operation-count distribution rather than on any score:
# the corpus median is 16 and p95 is 136, so these bands split the mass roughly
# evenly without being chosen to separate ILSC.
BANDS = [(3, 5), (6, 10), (11, 20), (21, 50), (51, 200)]


def load(scores_path):
    """Primary-population rows joined to the author tag count."""
    with open(TAG_CACHE, encoding="utf-8") as fh:
        tags = json.load(fh)
    rows = []
    with open(scores_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("oversized", "")).lower() not in ("false", "0", ""):
                continue
            rows.append({
                "clean_file": r["clean_file"],
                "provider": r["provider"],
                "source": r["source"],
                "n_operations": float(r["n_operations"]),
                "ilsc": float(r["ILSC_mean"]),
                "n_tags": tags.get(r["clean_file"]),
            })
    return rows


def ols_cluster(X, y, clusters):
    """OLS with cluster-robust (CR1) standard errors.

    Services from one provider share documentation conventions, a specification
    generator and often a template, so treating them as independent draws would
    report a precision the design does not have. The cluster is the provider.
    """
    XtXi = np.linalg.pinv(X.T @ X)
    beta = XtXi @ X.T @ y
    resid = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    for c in set(clusters):
        m = clusters == c
        s = X[m].T @ resid[m]
        meat += np.outer(s, s)
    n_obs, k = X.shape
    n_grp = len(set(clusters))
    adj = (n_grp / (n_grp - 1.0)) * ((n_obs - 1.0) / (n_obs - k))
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi * adj))
    r2 = 1.0 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return beta, se, r2, n_grp


def run(args):
    from scipy import stats

    rows = load(args.scores)
    print("primary services: %d" % len(rows))

    # ---------------------------------------------------------------- size effect
    N = np.array([r["n_operations"] for r in rows])
    S = np.array([r["ilsc"] for r in rows])
    rho_size, p_size = stats.spearmanr(N, S)
    print("\nSpearman(ILSC_mean, n_operations) = %+.4f  p = %.3g" % (rho_size, p_size))

    # ------------------------------------------------------- size-band thresholds
    src = np.array([r["source"] for r in rows])
    band_rows = []
    for label, mask_extra in (("all", np.ones(len(S), bool)), ("S1", src == "S1")):
        for lo, hi in BANDS:
            m = (N >= lo) & (N <= hi) & mask_extra
            if m.sum() < 20:
                continue
            v = S[m]
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            band_rows.append({
                "population": label, "band": "%d-%d" % (lo, hi), "n": int(m.sum()),
                "min": round(float(v.min()), 6), "q1": round(float(q1), 6),
                "median": round(float(med), 6), "q3": round(float(q3), 6),
                "max": round(float(v.max()), 6), "mean": round(float(v.mean()), 6),
            })
        m = mask_extra
        v = S[m]
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        band_rows.append({
            "population": label, "band": "all", "n": int(m.sum()),
            "min": round(float(v.min()), 6), "q1": round(float(q1), 6),
            "median": round(float(med), 6), "q3": round(float(q3), 6),
            "max": round(float(v.max()), 6), "mean": round(float(v.mean()), 6),
        })

    out_bands = os.path.join(config.ROOT, "results", "size_thresholds.csv")
    with open(out_bands, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(band_rows[0].keys()))
        w.writeheader()
        w.writerows(band_rows)
    print("\nsize-stratified thresholds -> %s" % out_bands)
    print("  %-6s %-8s %6s %8s %8s %8s" % ("pop", "band", "n", "Q1", "median", "Q3"))
    for r in band_rows:
        print("  %-6s %-8s %6d %8.4f %8.4f %8.4f"
              % (r["population"], r["band"], r["n"], r["q1"], r["median"], r["q3"]))

    # ------------------------------------------------------------- the regression
    lab = [r for r in rows if r["n_tags"] is not None and r["n_tags"] >= 1]
    prov = np.array([r["provider"] for r in lab])
    y = np.array([r["ilsc"] for r in lab])
    lt = np.log2(np.array([float(r["n_tags"]) for r in lab]))
    lg = np.log2(np.array([r["n_operations"] for r in lab]))
    one = np.ones(len(y))
    print("\nservices carrying >= 1 author tag: %d over %d providers"
          % (len(lab), len(set(prov))))
    print("Spearman(n_tags, n_operations) = %+.4f  <- why a 16-pair matched design"
          " cannot separate them" % stats.spearmanr(
              [r["n_tags"] for r in lab], [r["n_operations"] for r in lab])[0])

    counts = collections.Counter(prov)
    fe = sorted(p for p, c in counts.items() if c >= args.min_provider_services)
    fe_cols = [(prov == p).astype(float) for p in fe]

    models = [
        ("M1", ["const", "log2_tags"], np.column_stack([one, lt])),
        ("M2", ["const", "log2_ops"], np.column_stack([one, lg])),
        ("M3", ["const", "log2_tags", "log2_ops"], np.column_stack([one, lt, lg])),
        ("M4", ["const", "log2_tags", "log2_ops"],
         np.column_stack([one, lt, lg] + fe_cols)),
    ]

    out = []
    for name, keep, X in models:
        beta, se, r2, n_grp = ols_cluster(X, y, prov)
        fe_note = ("+ %d provider fixed effects" % len(fe)) if name == "M4" else ""
        print("\n%s: ILSC ~ %s %s" % (name, " + ".join(keep[1:]), fe_note))
        print("   n = %d  clusters = %d  R2 = %.4f" % (len(y), n_grp, r2))
        for i, term in enumerate(keep):
            t = beta[i] / se[i]
            p = 2.0 * (1.0 - stats.norm.cdf(abs(t)))
            if term != "const":
                print("     %-11s beta %+.5f  SE %.5f  t %+6.2f  p %.3g"
                      % (term, beta[i], se[i], t, p))
            out.append({
                "model": name, "term": term,
                "beta": round(float(beta[i]), 6), "se_cluster": round(float(se[i]), 6),
                "t": round(float(t), 4), "p": float(p),
                "n": len(y), "n_clusters": n_grp, "r2": round(float(r2), 4),
                "provider_fe": len(fe) if name == "M4" else 0,
            })

    # partial rank correlation, distribution-free companion to M3
    ry = stats.rankdata(y)
    rt = stats.rankdata(lt)
    rn = stats.rankdata(lg)

    def resid(a, b):
        A = np.column_stack([np.ones(len(b)), b])
        return a - A @ np.linalg.lstsq(A, a, rcond=None)[0]

    pr, pp = stats.pearsonr(resid(ry, rn), resid(rt, rn))
    print("\npartial Spearman(ILSC, tags | operations) = %+.4f  p = %.3g" % (pr, pp))
    out.append({
        "model": "partial_spearman", "term": "tags|ops",
        "beta": round(float(pr), 6), "se_cluster": "", "t": "", "p": float(pp),
        "n": len(y), "n_clusters": len(set(prov)), "r2": "", "provider_fe": 0,
    })
    out.append({
        "model": "spearman", "term": "ilsc~n_operations",
        "beta": round(float(rho_size), 6), "se_cluster": "", "t": "",
        "p": float(p_size), "n": len(rows), "n_clusters": "", "r2": "",
        "provider_fe": 0,
    })

    out_reg = os.path.join(config.ROOT, "results", "construct_validity.csv")
    with open(out_reg, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("regression -> %s" % out_reg)

    # -------------------------------------------------------------------- figure
    fs.use()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.9))

    labels = ["%d-%d" % b for b in BANDS]
    data = [S[(N >= lo) & (N <= hi)] for lo, hi in BANDS]
    bp = ax1.boxplot(data, labels=labels, showfliers=False, widths=0.6,
                     patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor(fs.BLUE)
        patch.set_alpha(0.35)
    for med in bp["medians"]:
        med.set_color(fs.INK)
        med.set_linewidth(1.6)
    ax1.set_xlabel("operations per service")
    ax1.set_ylabel("ILSC$_{mean}$")
    ax1.set_title(r"(a) ILSC falls with size ($\rho=-0.55$)", fontsize=8)

    tg = np.array([float(r["n_tags"]) for r in lab])
    tb = [(1, 1), (2, 3), (4, 6), (7, 12), (13, 999)]
    tlabels = ["1", "2-3", "4-6", "7-12", "13+"]
    tdata, tkeep = [], []
    for (lo, hi), lb in zip(tb, tlabels):
        m = (tg >= lo) & (tg <= hi)
        if m.sum() > 20:
            tdata.append(y[m])
            tkeep.append("%s\n(n=%d)" % (lb, m.sum()))
    bp2 = ax2.boxplot(tdata, labels=tkeep, showfliers=False, widths=0.6,
                      patch_artist=True)
    for patch in bp2["boxes"]:
        patch.set_facecolor(fs.ORANGE)
        patch.set_alpha(0.35)
    for med in bp2["medians"]:
        med.set_color(fs.INK)
        med.set_linewidth(1.6)
    ax2.set_xlabel("author-declared capabilities (tags)")
    ax2.set_title(r"(b) and with declared capabilities", fontsize=8)

    out_fig = os.path.join(config.ROOT, "figures", "fig11_size_and_tags.pdf")
    fig.tight_layout()
    fs.finish(fig, out_fig)
    print("figure -> %s" % out_fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scores", default=os.path.join(config.ROOT, "results",
                                                     "ilsc_scores.csv"))
    ap.add_argument("--min-provider-services", type=int, default=5,
                    help="providers with at least this many services get a fixed "
                         "effect in M4")
    run(ap.parse_args())


if __name__ == "__main__":
    main()

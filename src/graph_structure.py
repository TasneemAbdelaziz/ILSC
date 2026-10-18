"""
ILSC - similarity-graph structure.  SECONDARY, descriptive analysis.

It never changes an ILSC score. It asks one question, raised by the review
(concern 5): does the per-service similarity graph carry information that
ILSC_mean - a mean over pairs - hides? Two services can share a mean while one
is a single tight group and the other is several groups weakly tied together.

The groups found here are called SIMILARITY COMMUNITIES, not functional or
business communities: a group of operations that are similar to each other
need not be a separate responsibility (a payroll service may split into
employees / salaries / deductions and still be one capability).

Per service (primary population, n >= config.GRAPH_MIN_OPERATIONS):

  W           the full Sim(Oi, Oj) matrix from similarity.pair_blocks, diagonal 0.
              Its upper-triangle mean is re-checked against ILSC_mean in
              results/ilsc_scores.csv, so a rebuilt embedding cache is verified
              before anything is reported.
  spectral    normalised Laplacian L = I - D^-1/2 W D^-1/2, eigenvalues
              0 = l1 <= l2 <= ...;  k_spectral = argmax over k <= n//2 of the
              eigengap l(k+1) - l(k) (a community holds two operations on
              average at most); lambda2 = algebraic connectivity, a continuous
              "how separable" indicator. Labels: k-means on the row-normalised
              first k eigenvectors (Ng-Jordan-Weiss), seeded, 10 restarts.
  louvain     networkx louvain_communities on the weighted graph, resolution
              config.GRAPH_LOUVAIN_RESOLUTION, seed config.SEED; modularity Q.
  components  connected components of {Sim >= tau} for every tau in
              config.TAU_GRID - the thresholded view ILSC already reports.
  resources   leaf resource of each operation (size_mechanism.leaf_resources).

Analyses (results/graph_structure_summary.csv):
  1. same-mean        deciles of ILSC_mean; eta^2 = share of an indicator's
                      variance explained by the decile. Low eta^2 means the
                      indicator varies among services with about the same mean.
  2. threshold        rank stability of n_components across tau.
  3. resource align.  ARI / NMI of each partition against the resource labels,
                      and against the same labels shuffled (seeded) as a null.
  4. method agreement ARI between the spectral and Louvain partitions.
Not done here: capability-preserving tests (no capability labels exist; D-03,
D-04) and incremental validity (the independent evidence is still to be chosen).

Inputs:  results/ilsc_scores.csv, parsed/, the embedding cache (src/embed.py)
Outputs: results/graph_structure.csv          one row per analysed service
         results/graph_structure_summary.csv  every test, tidy
         results/graph_structure_deciles.csv  per ILSC_mean decile
"""

import argparse
import collections
import csv
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                         # noqa: E402
import embed as emb_mod                               # noqa: E402
import similarity as sim                              # noqa: E402
from size_mechanism import leaf_resources, spearman, partial_spearman  # noqa: E402

KMEANS_RESTARTS = 10
INDICATORS = ("k_spectral_share", "lambda2", "k_louvain_share", "modularity", "components_share_tau050")


# --------------------------------------------------------------------------
# graph construction and the three structural views
# --------------------------------------------------------------------------

def sim_matrix(oset):
    n = oset.n
    W = np.zeros((n, n), dtype="float64")
    for i0, i1, s, _per, _mask in sim.pair_blocks(oset):
        W[i0:i1, :] = s
    W = (W + W.T) / 2.0
    np.fill_diagonal(W, 0.0)
    return W


def _kmeans(X, k, seed):
    """Best of KMEANS_RESTARTS seeded k-means runs (lowest inertia)."""
    from scipy.cluster.vq import kmeans2
    best, best_inertia = None, math.inf
    for r in range(KMEANS_RESTARTS):
        rng = np.random.default_rng(seed + r)
        try:
            cent, lab = kmeans2(X, k, minit="++", rng=rng)
        except TypeError:                      # older scipy spells it `seed`
            cent, lab = kmeans2(X, k, minit="++", seed=rng)
        inertia = float(((X - cent[lab]) ** 2).sum())
        if inertia < best_inertia:
            best, best_inertia = lab, inertia
    return best


def spectral(W, seed):
    n = W.shape[0]
    d = W.sum(axis=1)
    d[d <= 0] = 1.0                            # isolated node: keep L defined
    dinv = 1.0 / np.sqrt(d)
    L = np.eye(n) - dinv[:, None] * W * dinv[None, :]
    vals, vecs = np.linalg.eigh(L)
    vals = np.clip(vals, 0.0, None)
    kmax = max(1, n // 2)
    gaps = vals[1:kmax + 1] - vals[:kmax]      # gaps[k-1] = l(k+1) - l(k)
    k = int(np.argmax(gaps)) + 1
    if k == 1:
        labels = np.zeros(n, dtype=int)
    else:
        X = vecs[:, :k]
        X = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
        labels = _kmeans(X, k, seed)
    return k, float(gaps[k - 1]), float(vals[1]), labels


def louvain(W, seed):
    import networkx as nx
    n = W.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    iu = np.triu_indices(n, 1)
    for i, j, w in zip(iu[0], iu[1], W[iu]):
        if w > 0:
            G.add_edge(int(i), int(j), weight=float(w))
    comms = nx.community.louvain_communities(G, weight="weight",
                                             resolution=config.GRAPH_LOUVAIN_RESOLUTION, seed=seed)
    q = nx.community.modularity(G, comms, weight="weight", resolution=config.GRAPH_LOUVAIN_RESOLUTION)
    labels = np.zeros(n, dtype=int)
    for c, members in enumerate(sorted(comms, key=lambda s: min(s))):
        for m in members:
            labels[m] = c
    return len(comms), float(q), labels


def components(W, tau):
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    return int(connected_components(csr_matrix(W >= tau), directed=False)[0])


# --------------------------------------------------------------------------
# partition agreement (no sklearn: both measures are short)
# --------------------------------------------------------------------------

def _c2(x):
    return x * (x - 1) / 2.0


def ari(a, b):
    n = len(a)
    nij = collections.Counter(zip(a, b))
    sa = sum(_c2(v) for v in collections.Counter(a).values())
    sb = sum(_c2(v) for v in collections.Counter(b).values())
    s = sum(_c2(v) for v in nij.values())
    exp = sa * sb / _c2(n)
    mx = (sa + sb) / 2.0
    return float("nan") if mx == exp else (s - exp) / (mx - exp)


def nmi(a, b):
    n = len(a)
    pa = np.array(list(collections.Counter(a).values())) / n
    pb = np.array(list(collections.Counter(b).values())) / n
    ha, hb = -(pa * np.log(pa)).sum(), -(pb * np.log(pb)).sum()
    if ha + hb == 0:
        return float("nan")
    ca, cb = collections.Counter(a), collections.Counter(b)
    mi = sum((v / n) * math.log((v / n) / ((ca[x] / n) * (cb[y] / n)))
             for (x, y), v in collections.Counter(zip(a, b)).items())
    return 2.0 * mi / (ha + hb)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def eta_squared(values, groups):
    v = np.asarray(values, dtype=float)
    g = np.asarray(groups)
    ok = np.isfinite(v)
    v, g = v[ok], g[ok]
    tot = ((v - v.mean()) ** 2).sum()
    if tot == 0:
        return float("nan")
    between = sum(len(v[g == k]) * (v[g == k].mean() - v.mean()) ** 2 for k in np.unique(g))
    return float(between / tot)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Similarity-graph structure (secondary analysis).")
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", default=config.RESULTS_DIR)
    args = ap.parse_args(argv)

    emb = emb_mod.Embeddings(args.cache)
    with open(os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"), newline="", encoding="utf-8") as fh:
        scores = [r for r in csv.DictReader(fh)
                  if r["oversized"] in ("0", "") and int(r["n_operations"]) >= config.GRAPH_MIN_OPERATIONS]
    if args.limit:
        scores = scores[: args.limit]

    taus = list(config.TAU_GRID)
    rows, max_diff = [], 0.0
    for idx, r in enumerate(scores):
        name = r["clean_file"].rsplit(".", 1)[0] + ".json"
        with open(os.path.join(config.PARSED_DIR, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = sim.OpSet.from_service(doc, emb, name)
        W = sim_matrix(oset)
        n = oset.n
        mean_check = float(W[np.triu_indices(n, 1)].mean())
        diff = abs(mean_check - float(r["ILSC_mean"]))
        max_diff = max(max_diff, diff)

        res = leaf_resources([o["path"] for o in doc["operations"]])
        res_ids = {x: i for i, x in enumerate(sorted(set(res)))}
        res_lab = np.array([res_ids[x] for x in res])
        null_lab = np.random.default_rng(config.SEED + idx).permutation(res_lab)

        k_s, gap, lam2, lab_s = spectral(W, config.SEED)
        k_l, q, lab_l = louvain(W, config.SEED)
        comps = {t: components(W, t) for t in taus}

        row = {
            "clean_file": r["clean_file"], "title": r["title"], "provider": r["provider"],
            "source": r["source"], "n_operations": n, "ILSC_mean": round(float(r["ILSC_mean"]), 6),
            "ilsc_recomputed_abs_diff": "%.2e" % diff,
            "n_resources": len(res_ids),
            "k_spectral": k_s, "k_spectral_share": round(k_s / n, 6),
            "eigengap": round(gap, 6), "lambda2": round(lam2, 6),
            "k_louvain": k_l, "k_louvain_share": round(k_l / n, 6), "modularity": round(q, 6),
            "ari_spectral_resource": round(ari(lab_s, res_lab), 6),
            "nmi_spectral_resource": round(nmi(lab_s, res_lab), 6),
            "ari_louvain_resource": round(ari(lab_l, res_lab), 6),
            "nmi_louvain_resource": round(nmi(lab_l, res_lab), 6),
            "ari_spectral_resource_null": round(ari(lab_s, null_lab), 6),
            "ari_louvain_resource_null": round(ari(lab_l, null_lab), 6),
            "ari_spectral_louvain": round(ari(lab_s, lab_l), 6),
            "components_share_tau050": round(comps[config.TAU_DEFAULT] / n, 6),
        }
        for t in taus:
            row["components_tau_%.2f" % t] = comps[t]
        rows.append(row)
        if (idx + 1) % 100 == 0:
            print("  ... %d/%d" % (idx + 1, len(scores)), flush=True)

    # ---------------- deciles of ILSC_mean (rank-based, equal counts) -------------
    N = len(rows)
    order = sorted(range(N), key=lambda i: rows[i]["ILSC_mean"])
    for rank, i in enumerate(order):
        rows[i]["mean_decile"] = rank * config.GRAPH_MEAN_BINS // N + 1

    summary = []

    def add(test, value, n, note=""):
        summary.append({"test": test, "value": ("%.4f" % value) if isinstance(value, float) else value,
                        "n_services": n, "note": note})

    add("max |recomputed ILSC_mean - ilsc_scores.csv|", max_diff, N,
        "embedding-cache check: must be ~0 before anything else is read")
    ilsc = [x["ILSC_mean"] for x in rows]
    size = [x["n_operations"] for x in rows]
    dec = [x["mean_decile"] for x in rows]
    for ind in INDICATORS:
        v = [x[ind] for x in rows]
        add("eta2(%s ~ ILSC_mean decile)" % ind, eta_squared(v, dec), N,
            "share of variance explained by the mean; low = information the mean hides")
        add("rho(%s, ILSC_mean)" % ind, spearman(v, ilsc), N)
        add("partial rho(%s, ILSC_mean | size)" % ind, partial_spearman(v, ilsc, size), N)

    # threshold stability of the component view
    for a, b in ((0.30, 0.50), (0.45, 0.55), (0.50, 0.70), (0.30, 0.70)):
        add("rho(n_components tau=%.2f, tau=%.2f)" % (a, b),
            spearman([x["components_tau_%.2f" % a] for x in rows], [x["components_tau_%.2f" % b] for x in rows]), N,
            "rank stability of the thresholded view")
    for t in taus:
        add("median n_components at tau=%.2f" % t,
            float(np.median([x["components_tau_%.2f" % t] for x in rows])), N)

    # resource alignment and method agreement
    for key in ("ari_spectral_resource", "nmi_spectral_resource", "ari_louvain_resource",
                "nmi_louvain_resource", "ari_spectral_resource_null", "ari_louvain_resource_null",
                "ari_spectral_louvain"):
        v = np.array([x[key] for x in rows], dtype=float)
        v = v[np.isfinite(v)]
        add("median %s" % key, float(np.median(v)) if len(v) else float("nan"), len(v),
            "NaN rows (a single-group partition on both sides) dropped")
    add("median k_spectral", float(np.median([x["k_spectral"] for x in rows])), N)
    add("median k_louvain", float(np.median([x["k_louvain"] for x in rows])), N)
    add("share of services with k_spectral = 1", float(np.mean([x["k_spectral"] == 1 for x in rows])), N)
    add("rho(k_spectral, n_resources)", spearman([x["k_spectral"] for x in rows], [x["n_resources"] for x in rows]), N)
    add("rho(k_louvain, n_resources)", spearman([x["k_louvain"] for x in rows], [x["n_resources"] for x in rows]), N)

    # per-decile table
    deciles = []
    for d in range(1, config.GRAPH_MEAN_BINS + 1):
        sub = [x for x in rows if x["mean_decile"] == d]
        row = {"mean_decile": d, "n_services": len(sub),
               "ilsc_min": round(min(x["ILSC_mean"] for x in sub), 4),
               "ilsc_max": round(max(x["ILSC_mean"] for x in sub), 4)}
        for ind in INDICATORS:
            v = np.array([x[ind] for x in sub], dtype=float)
            row[ind + "_q1"] = round(float(np.percentile(v, 25)), 4)
            row[ind + "_median"] = round(float(np.median(v)), 4)
            row[ind + "_q3"] = round(float(np.percentile(v, 75)), 4)
        deciles.append(row)

    os.makedirs(args.out_dir, exist_ok=True)
    for fname, data in (("graph_structure.csv", rows), ("graph_structure_summary.csv", summary),
                        ("graph_structure_deciles.csv", deciles)):
        with open(os.path.join(args.out_dir, fname), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)

    print("analysed %d services (n >= %d)" % (N, config.GRAPH_MIN_OPERATIONS))
    for s in summary:
        print("  %-62s %9s  n=%-5s %s" % (s["test"], s["value"], s["n_services"], s["note"]))


if __name__ == "__main__":
    main()

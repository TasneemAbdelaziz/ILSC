"""
ILSC - Day 3 metric track (Mohamed): the two null models.

Sec. 6 asks for E[ILSC_rand(n)] under two restrictions, so that

    ILSC_norm(S) = (ILSC_mean(S) - E[ILSC_rand(n)]) / (1 - E[ILSC_rand(n)])

answers two different questions:

  **global**    is this service more coherent than an arbitrary bag of API
                operations? A weak bar - a banking operation and a weather
                operation are trivially unrelated.
  **provider**  is it more coherent than an arbitrary bag of operations from the
                same provider? The harder question. Provider replaces the
                proposal's *domain* restriction, which has no label source left
                after D-03 and D-04 - see **D-18**.

Why this does not do 1,000 n-sets per size, and why that is better
------------------------------------------------------------------
ILSC_mean is a mean over the C(n,2) pairs of a drawn set. For a set drawn at
random from a pool, those pairs are exchangeable, so

    E[ILSC_mean(random n-set)] = E[Sim(Oa, Ob)]  for a single random pair

**for every n.** The expectation the normalisation needs is therefore a constant
in n, and estimating it by drawing n-sets is an extremely expensive way to
estimate the mean of one random pair. Following the proposal literally would
cost about 1.3 billion pair evaluations to recover a number obtainable from a
few hundred thousand.

So this module does both, deliberately:

1. **The estimator** - a large random-pair sample (``--pair-samples``), which is
   what feeds ILSC_norm. Its standard error is reported.
2. **The check** - full n-set draws at a grid of sizes (``--verify-sizes``),
   1,000 draws each as specified, whose only job is to confirm the curve is flat
   in n. If it is not flat, the assumption above is wrong and the estimator must
   be replaced; the run says so loudly.

The flatness of E[ILSC_rand(n)] is itself reportable: it means ILSC_norm is an
affine rescaling of ILSC_mean, so it cannot reorder services and every
rank-based result (Gate 1, Exp. 5's Kendall's W) is identical on either.

Outputs:
    results/null_model.csv       the expectations, per model and per provider
    results/null_model_bysize.csv  the flatness check

Usage:
    python src/null_models.py
    python src/null_models.py --pair-samples 500000 --verify-sizes 3,5,10,25,50,100,200
    python src/null_models.py --include-oversized      # sensitivity population
"""

import argparse
import csv
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                   # noqa: E402
import pool as pool_mod                         # noqa: E402
import similarity as sim                        # noqa: E402

# A provider pool smaller than this cannot support an estimate of its own; those
# providers fall back to the global expectation, marked in the output.
MIN_PROVIDER_OPERATIONS = 50


# ----------------------------------------------------------------------------
# The estimator: E[Sim] over random pairs
# ----------------------------------------------------------------------------

def expected_sim(pool, idx, n_samples, rng, weights=None, exclude_same_service=True,
                 chunk=4096):
    """Monte-Carlo E[Sim(Oa,Ob)] over random pairs drawn from ``idx``.

    ``exclude_same_service`` matters. The null model asks what an *arbitrary*
    bag of operations looks like; a bag assembled by chance would rarely contain
    two operations from one service, and leaving them in would import exactly
    the within-service coherence the null is supposed to be free of. Pairs that
    land in the same service are resampled.
    """
    idx = np.asarray(idx)
    if len(idx) < 2:
        return float("nan"), float("nan"), 0
    svc = np.array([pool.service_of[i] for i in idx])

    total, total_sq, got = 0.0, 0.0, 0
    while got < n_samples:
        take = min(chunk, n_samples - got)
        a = rng.integers(0, len(idx), size=take * 2)
        b = rng.integers(0, len(idx), size=take * 2)
        keep = a != b
        if exclude_same_service:
            keep &= svc[a] != svc[b]
        a, b = a[keep][:take], b[keep][:take]
        if len(a) == 0:
            break
        vals = _pair_sims(pool, idx[a], idx[b], weights)
        total += float(vals.sum())
        total_sq += float((vals ** 2).sum())
        got += len(vals)

    if got == 0:
        return float("nan"), float("nan"), 0
    mean = total / got
    var = max(total_sq / got - mean * mean, 0.0)
    return mean, float(np.sqrt(var / got)), got


def _pair_sims(pool, ia, ib, weights=None):
    """Sim for the aligned pairs (ia[k], ib[k]) - vectorised, no n^2 matrix."""
    w = sim.DEFAULT_WEIGHTS if weights is None else np.asarray(weights, dtype="float64")
    m = len(ia)
    per = np.zeros((m, sim.NF), dtype="float64")
    avail = np.zeros((m, sim.NF), dtype=bool)

    # f1 / f6 - cosine of aligned rows, clamped (D-20)
    per[:, 0] = np.clip((pool.T[ia] * pool.T[ib]).sum(axis=1), 0.0, 1.0)
    per[:, 5] = np.clip((pool.D[ia] * pool.D[ib]).sum(axis=1), 0.0, 1.0)
    avail[:, 0] = True
    avail[:, 5] = (np.linalg.norm(pool.D[ia], axis=1) > 0) & \
                  (np.linalg.norm(pool.D[ib], axis=1) > 0)

    # f2..f5 from the pool's precomputed sets - no per-pair set construction.
    sets, f2_ok = pool.sets, pool.f2_ok
    for r in range(m):
        a_i, b_i = ia[r], ib[r]
        sa, sb = sets[a_i], sets[b_i]
        for k in range(4):
            col = k + 1
            A, B = sa[k], sb[k]
            if not A or not B:
                continue
            if col == 1 and not (f2_ok[a_i] and f2_ok[b_i]):
                continue                       # f2 also needs a usable operationId
            avail[r, col] = True
            inter = len(A & B)
            den = min(len(A), len(B)) if col == 4 else len(A) + len(B) - inter
            per[r, col] = inter / den if den else 0.0

    wm = avail * w[None, :]
    den = wm.sum(axis=1)
    num = (wm * per).sum(axis=1)
    return np.where(den > 0, num / np.where(den == 0, 1, den), 0.0)


# ----------------------------------------------------------------------------
# The check: full n-set draws at a grid of sizes
# ----------------------------------------------------------------------------

def bysize_draws(pool, idx, sizes, draws, rng, weights=None):
    """1,000 (default) random n-sets per size, scored in full. The flatness check."""
    idx = np.asarray(idx)
    out = []
    for n in sizes:
        if n > len(idx):
            continue
        t0 = time.time()
        vals = np.empty(draws, dtype="float64")
        for d in range(draws):
            pick = rng.choice(len(idx), size=n, replace=False)
            vals[d] = sim.ilsc_mean(pool.opset(idx[pick]), weights)
        out.append({
            "n": n, "draws": draws,
            "expected_ilsc": float(vals.mean()),
            "sd_over_draws": float(vals.std(ddof=1)) if draws > 1 else float("nan"),
            "seconds": round(time.time() - t0, 1),
        })
        print("    n=%-4d E=%.5f  sd=%.5f  (%.0fs)"
              % (n, out[-1]["expected_ilsc"], out[-1]["sd_over_draws"], out[-1]["seconds"]),
              flush=True)
    return out


# ----------------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------------

def run(args):
    rng = np.random.default_rng(config.SEED)
    pl = pool_mod.load_pool(include_oversized=args.include_oversized, limit=args.limit)
    all_idx = np.arange(len(pl))

    print("\nglobal null - %s random pairs" % "{:,}".format(args.pair_samples), flush=True)
    t0 = time.time()
    g_mean, g_se, g_n = expected_sim(pl, all_idx, args.pair_samples, rng)
    print("  E[ILSC_rand] = %.5f  (SE %.5f, %s pairs, %.0fs)"
          % (g_mean, g_se, "{:,}".format(g_n), time.time() - t0))

    rows = [{"model": "global", "provider": "", "expected_ilsc": g_mean,
             "std_error": g_se, "pairs_sampled": g_n,
             "pool_operations": len(pl), "fallback_to_global": 0}]

    print("\nprovider-restricted null (D-18) - %d providers" % len(pl.by_provider), flush=True)
    per_provider = args.pair_samples // 20
    n_fallback = 0
    n_single_service = 0
    for prov, idx in sorted(pl.by_provider.items(), key=lambda kv: -len(kv[1])):
        # Two ways a provider cannot support a null model of its own. Too few
        # operations is the obvious one. The second is subtler and bit us: a
        # provider whose operations all sit in ONE service has no cross-service
        # pair to draw, so every sample is rejected and the estimate comes back
        # NaN. Both fall back to the global expectation, marked in the output -
        # a null model estimated from nothing is not an estimate.
        n_services = len({pl.service_of[i] for i in idx})
        if len(idx) < MIN_PROVIDER_OPERATIONS or n_services < 2:
            rows.append({"model": "provider", "provider": prov,
                         "expected_ilsc": g_mean, "std_error": g_se,
                         "pairs_sampled": 0, "pool_operations": len(idx),
                         "fallback_to_global": 1})
            n_fallback += 1
            n_single_service += int(len(idx) >= MIN_PROVIDER_OPERATIONS and n_services < 2)
            continue
        m, se, k = expected_sim(pl, idx, per_provider, rng)
        if not np.isfinite(m):
            rows.append({"model": "provider", "provider": prov,
                         "expected_ilsc": g_mean, "std_error": g_se,
                         "pairs_sampled": 0, "pool_operations": len(idx),
                         "fallback_to_global": 1})
            n_fallback += 1
            continue
        rows.append({"model": "provider", "provider": prov, "expected_ilsc": m,
                     "std_error": se, "pairs_sampled": k,
                     "pool_operations": len(idx), "fallback_to_global": 0})
    est = [r for r in rows if r["model"] == "provider" and not r["fallback_to_global"]]
    print("  %d providers estimated, %d fell back to global"
          % (len(est), n_fallback))
    print("    (< %d operations, or all operations inside a single service: %d)"
          % (MIN_PROVIDER_OPERATIONS, n_single_service))
    if est:
        vals = np.array([r["expected_ilsc"] for r in est], dtype=float)
        med = float(np.median(vals))
        above = int((vals > g_mean).sum())
        print("  provider E[ILSC_rand]: min %.4f  median %.4f  max %.4f"
              % (vals.min(), med, vals.max()))
        print("  global is %.4f; %d of %d providers sit above it (%.0f%%)"
              % (g_mean, above, len(vals), 100.0 * above / len(vals)))
        print("  the restricted null is %s"
              % ("stricter (higher) as intended" if med > g_mean
                 else "NOT stricter - report this rather than assuming it"))

    out = os.path.join(config.RESULTS_DIR, args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["model", "provider", "expected_ilsc",
                                           "std_error", "pairs_sampled",
                                           "pool_operations", "fallback_to_global"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote %s" % out)

    if args.verify_sizes:
        sizes = [int(s) for s in args.verify_sizes.split(",") if s.strip()]
        print("\nflatness check - %d draws per size, full ILSC_mean each" % args.draws)
        bs = bysize_draws(pl, all_idx, sizes, args.draws, rng)
        out2 = os.path.join(config.RESULTS_DIR, args.out_bysize)
        with open(out2, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["n", "draws", "expected_ilsc",
                                               "sd_over_draws", "seconds"])
            w.writeheader()
            for r in bs:
                w.writerow(r)
        print("wrote %s" % out2)
        if bs:
            vals = [r["expected_ilsc"] for r in bs]
            spread = max(vals) - min(vals)
            print("\n  E[ILSC_rand(n)] across sizes: %.5f .. %.5f  (spread %.5f)"
                  % (min(vals), max(vals), spread))
            print("  pair-sample estimator:        %.5f" % g_mean)
            if spread < 0.01:
                print("  FLAT in n, as theory predicts - the estimator is sound and")
                print("  ILSC_norm is an affine rescaling of ILSC_mean.")
            else:
                print("  NOT FLAT (spread >= 0.01). The exchangeability argument does not")
                print("  hold here; do not use the pair-sample estimator without explaining why.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC null models (Sec. 6, D-18).")
    ap.add_argument("--pair-samples", type=int, default=400000)
    ap.add_argument("--verify-sizes", default="3,5,10,25,50,100,200")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--include-oversized", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="null_model.csv")
    ap.add_argument("--out-bysize", default="null_model_bysize.csv")
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

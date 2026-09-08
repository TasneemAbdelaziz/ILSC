"""
ILSC - Day 7: perturbation (Exp. 2) and the monotonicity + contrast checker.

H2 [v3]: *ILSC degrades significantly more under foreign-domain operation
injection than under same-domain injection of equal size.*

The v2 form of H2 - "ILSC degrades under injection" - is close to a tautology:
inserting a dissimilar item into a mean-similarity score must lower it by
construction. What carries evidential weight is the **contrast** against a
size-matched control, so this module never reports a drop without the control
beside it. The headline is the gap between the curves, not either curve.

Three conditions, from D-05
---------------------------
Domain labels were rejected (D-03, D-04), so *provider proximity* stands in for
semantic distance, exactly as it does for the null model (D-18):

  ``same_service``   inject from a different service of the same provider that
                     is closest in title - the nearest thing to "same domain"
                     this corpus can express. The **strongest control**.
  ``same_provider``  inject from any other service of the same provider.
  ``cross_provider`` inject from a service of a different provider. The
                     **treatment** - the foreign-domain condition.

Levels 0/1/2/3/5 injected operations, 10 draws each (``config``). Level 0 is the
unperturbed service and is computed once, not ten times, because it has no
randomness - the CSV still carries ten identical rows so that every downstream
group-by has the same shape.

What the checker asserts
------------------------
1. **Monotonicity** in the treatment: ILSC(0) > ILSC(1) > ILSC(2) > ILSC(3) >
   ILSC(5). Counted per service and reported as "k of N perfectly monotonic".
2. **Contrast**: the degradation slope (OLS of mean ILSC on level) under
   ``cross_provider`` should be steeper - more negative - than under
   ``same_provider``. Tested paired across services with an exact sign-flip
   permutation test, which assumes only that the labels are exchangeable within
   a service.

Outputs:
    results/perturbation_raw.csv       service x condition x level x draw
    results/perturbation_summary.csv   per service: slopes, monotonicity, gap
    figures/fig3_perturbation.pdf      two curves with error bars

Usage:
    python src/inject.py                       # needs results/ilsc_scores.csv
    python src/inject.py --n-services 20
    python src/inject.py --check-only          # re-run the checker on existing raw
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

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402

import figstyle as fs                        # noqa: E402

import config                                    # noqa: E402
import pool as pool_mod                          # noqa: E402
import similarity as sim                         # noqa: E402

CONDITIONS = config.PERTURBATION_CONDITIONS      # same_service, same_provider, cross_provider
LEVELS = config.PERTURBATION_LEVELS              # 0, 1, 2, 3, 5
DRAWS = config.PERTURBATION_DRAWS                # 10


# ----------------------------------------------------------------------------
# Choosing the 20 services
# ----------------------------------------------------------------------------

def top_quartile_services(scores_path, pool, n_services):
    """The top-quartile services by ILSC_mean, one per provider.

    One per provider matters: without it the sample fills up with whichever
    provider happens to publish many similar specifications, and the
    ``same_provider`` control would then be drawn from near-duplicates of the
    service being perturbed. ``MAX_SERVICES_PER_PROVIDER_IN_EXPERIMENT`` in
    config is the pinned bound.
    """
    with open(scores_path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["ILSC_mean"] not in ("", "nan")]
    rows = [r for r in rows if str(r.get("oversized", "0")) in ("0", "", "False", "false")]
    if not rows:
        sys.exit("no usable rows in %s" % scores_path)

    vals = np.array([float(r["ILSC_mean"]) for r in rows])
    q3 = float(np.percentile(vals, 75))
    cand = [r for r in rows if float(r["ILSC_mean"]) >= q3]
    cand.sort(key=lambda r: -float(r["ILSC_mean"]))

    # a service is only usable if the pool can supply every condition
    per_provider, picked = {}, []
    cap = config.MAX_SERVICES_PER_PROVIDER_IN_EXPERIMENT
    name_by_clean = {m["clean_file"]: n for n, m in pool.meta.items()}
    for r in cand:
        if len(picked) >= n_services:
            break
        prov = r["provider"]
        if per_provider.get(prov, 0) >= cap:
            continue
        name = name_by_clean.get(r["clean_file"])
        if name is None or name not in pool.by_service:
            continue
        same_prov_other = [i for i in pool.by_provider.get(prov, [])
                           if pool.service_of[i] != name]
        if len(same_prov_other) < max(LEVELS):
            continue                       # cannot build the control - skip, do not fake it
        picked.append((name, r))
        per_provider[prov] = per_provider.get(prov, 0) + 1
    print("selected %d services from the top quartile (ILSC_mean >= %.4f), "
          "max %d per provider" % (len(picked), q3, cap))
    return picked, q3


# ----------------------------------------------------------------------------
# Injection
# ----------------------------------------------------------------------------

def donor_indices(pool, name, provider, condition, rng, k):
    """k pool indices to inject, drawn according to the condition."""
    own = set(pool.by_service.get(name, []))
    if condition == "cross_provider":
        cand = [i for i in range(len(pool)) if pool.provider_of[i] != provider]
    elif condition == "same_provider":
        cand = [i for i in pool.by_provider.get(provider, []) if i not in own]
    else:                                   # same_service: nearest sibling service
        sibling = _nearest_sibling(pool, name, provider)
        if sibling is None:
            return None
        cand = list(pool.by_service[sibling])
    if len(cand) < k:
        return None
    return [cand[j] for j in rng.choice(len(cand), size=k, replace=False)]


def _nearest_sibling(pool, name, provider):
    """The same provider's service whose title shares most tokens with this one."""
    import parse_spec as ps
    mine = set(ps.tokenize(pool.meta[name]["title"]))
    best, best_score = None, -1
    for other in {pool.service_of[i] for i in pool.by_provider.get(provider, [])}:
        if other == name:
            continue
        t = set(ps.tokenize(pool.meta[other]["title"]))
        score = len(mine & t) / max(len(mine | t), 1)
        if score > best_score:
            best, best_score = other, score
    return best


def run_injection(pool, picked, out_path, rng):
    rows = []
    for si, (name, meta) in enumerate(picked, 1):
        base_idx = pool.by_service[name]
        provider = pool.provider_of[base_idx[0]]
        base = sim.ilsc_mean(pool.opset(base_idx))
        print("  [%2d/%d] %-40s n=%-4d ILSC0=%.4f"
              % (si, len(picked), meta["title"][:40], len(base_idx), base), flush=True)

        for cond in CONDITIONS:
            for level in LEVELS:
                for draw in range(DRAWS):
                    if level == 0:
                        val = base                      # deterministic; see docstring
                    else:
                        don = donor_indices(pool, name, provider, cond, rng, level)
                        if don is None:
                            val = float("nan")
                        else:
                            val = sim.ilsc_mean(pool.opset(list(base_idx) + don))
                    rows.append({
                        "service": name, "title": meta["title"], "provider": provider,
                        "n_operations": len(base_idx), "condition": cond,
                        "level": level, "draw": draw, "ILSC_mean": val,
                        "delta_from_level0": val - base,
                    })

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["service", "title", "provider",
                                           "n_operations", "condition", "level",
                                           "draw", "ILSC_mean", "delta_from_level0"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote %s (%s rows)" % (out_path, "{:,}".format(len(rows))))
    return rows


# ----------------------------------------------------------------------------
# The checker
# ----------------------------------------------------------------------------

def ols_slope(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 2 or x.std() == 0:
        return float("nan")
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())


def sign_flip_p(diffs, n_perm=200000, rng=None):
    """Exact-if-small, Monte-Carlo-if-large sign-flip test that mean(diffs) < 0.

    Assumes only that the sign of each service's difference is exchangeable
    under the null - no normality, which a slope difference over 20 services
    does not earn.
    """
    d = np.asarray([x for x in diffs if np.isfinite(x)], dtype=float)
    n = len(d)
    if n == 0:
        return float("nan"), 0
    observed = d.mean()
    if n <= 20:                                   # 2^20 = 1,048,576 - enumerate
        count, total = 0, 0
        for bits in range(1 << n):
            signs = np.array([1.0 if (bits >> i) & 1 else -1.0 for i in range(n)])
            total += 1
            if (d * signs).mean() <= observed + 1e-15:
                count += 1
        return count / total, total
    rng = rng or np.random.default_rng(config.SEED)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, n))
    stats = (signs * d[None, :]).mean(axis=1)
    return float((stats <= observed + 1e-15).mean()), n_perm


def check(rows, out_path, fig_path):
    by = {}
    for r in rows:
        key = (r["service"], r["condition"], int(r["level"]))
        by.setdefault(key, []).append(float(r["ILSC_mean"]))
    services = sorted({r["service"] for r in rows})
    title_of = {r["service"]: r["title"] for r in rows}
    n_of = {r["service"]: int(r["n_operations"]) for r in rows}

    def mean_at(svc, cond, lv):
        v = [x for x in by.get((svc, cond, lv), []) if np.isfinite(x)]
        return float(np.mean(v)) if v else float("nan")

    summary, mono_count, usable = [], 0, 0
    for svc in services:
        curves = {c: [mean_at(svc, c, lv) for lv in LEVELS] for c in CONDITIONS}
        treat = curves["cross_provider"]
        monotonic = all(np.isfinite(treat[i]) and np.isfinite(treat[i + 1])
                        and treat[i] > treat[i + 1] for i in range(len(treat) - 1))
        mono_count += int(monotonic)
        slopes = {c: ols_slope(LEVELS, curves[c]) for c in CONDITIONS}
        gap = slopes["cross_provider"] - slopes["same_provider"]
        if np.isfinite(gap):
            usable += 1
        row = {"service": svc, "title": title_of[svc], "n_operations": n_of[svc],
               "monotonic_treatment": int(monotonic),
               "ILSC_level0": treat[0], "slope_gap_cross_minus_same": gap}
        for c in CONDITIONS:
            row["slope_" + c] = slopes[c]
            for lv, v in zip(LEVELS, curves[c]):
                row["%s_L%d" % (c, lv)] = v
        summary.append(row)

    gaps = [r["slope_gap_cross_minus_same"] for r in summary]
    p, n_perm = sign_flip_p(gaps)

    print("\n" + "=" * 72)
    print("MONOTONICITY  (treatment = cross_provider)")
    print("=" * 72)
    print("  perfectly monotonic: %d of %d services" % (mono_count, len(services)))
    for r in summary:
        if not r["monotonic_treatment"]:
            print("    not monotonic: %-40s %s" % (
                r["title"][:40],
                " ".join("%.4f" % r["cross_provider_L%d" % lv] for lv in LEVELS)))

    print("\n" + "=" * 72)
    print("CONTRAST  (the headline: the gap, not the drop)")
    print("=" * 72)
    print("  mean degradation slope per injected operation:")
    for c in CONDITIONS:
        s = [r["slope_" + c] for r in summary if np.isfinite(r["slope_" + c])]
        print("    %-16s %+.5f   (n=%d)" % (c, np.mean(s) if s else float("nan"), len(s)))
    g = [x for x in gaps if np.isfinite(x)]
    print("\n  slope gap (cross_provider - same_provider), paired per service:")
    print("    mean   %+.5f" % (np.mean(g) if g else float("nan")))
    print("    median %+.5f" % (np.median(g) if g else float("nan")))
    print("    negative for %d of %d services  (negative = treatment degrades faster)"
          % (sum(1 for x in g if x < 0), len(g)))
    print("    sign-flip p (one-sided, gap < 0) = %.5f over %s assignments"
          % (p, "{:,}".format(n_perm)))
    verdict = "POSITIVE" if (p < 0.05 and np.mean(g) < 0) else "NOT ESTABLISHED"
    print("\n  H2 contrast: %s" % verdict)
    if verdict != "POSITIVE":
        print("  Gate 2's instruction applies: diagnose before writing - weights,")
        print("  tokenisation, or the provider proximity proxy itself (D-05).")

    cols = ["service", "title", "n_operations", "monotonic_treatment", "ILSC_level0",
            "slope_gap_cross_minus_same"] + ["slope_" + c for c in CONDITIONS] \
        + ["%s_L%d" % (c, lv) for c in CONDITIONS for lv in LEVELS]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in summary:
            w.writerow({k: r.get(k, "") for k in cols})
    print("\nwrote %s" % out_path)

    figure(summary, fig_path)
    print("wrote %s" % fig_path)
    return summary


CONDITION_LABEL = {
    "same_service": "same-provider nearest sibling",
    "same_provider": "same-provider (control)",
    "cross_provider": "cross-provider (treatment)",
}


def condition_style(cond):
    """Colour, marker and linestyle for a condition - assigned by its fixed
    position in CONDITIONS, never by rank, so a condition wears the same colour
    in Fig 3 and Fig 7."""
    return fs.series(CONDITIONS.index(cond))


def figure(summary, path):
    fs.use()
    fig, ax = plt.subplots(figsize=(5.4, 3.8))
    for c in CONDITIONS:
        col, mk, ls = condition_style(c)
        lab = CONDITION_LABEL.get(c, c)
        means, errs = [], []
        for lv in LEVELS:
            vals = [r["%s_L%d" % (c, lv)] for r in summary
                    if np.isfinite(r.get("%s_L%d" % (c, lv), np.nan))]
            means.append(np.mean(vals) if vals else np.nan)
            errs.append(np.std(vals, ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else 0.0)
        ax.errorbar(LEVELS, means, yerr=errs, marker=mk, linestyle=ls, color=col,
                    label=lab, capsize=2.5)
    ax.set_xlabel("injected operations")
    ax.set_ylabel("ILSC$_{mean}$")
    ax.set_title("Degradation under injection, by provider proximity (D-05)")
    ax.set_xticks(LEVELS)
    ax.legend()
    ax.grid(axis="y")
    fs.finish(fig, path)


def run(args):
    raw_path = os.path.join(config.RESULTS_DIR, args.out_raw)
    sum_path = os.path.join(config.RESULTS_DIR, args.out_summary)
    fig_path = os.path.join(config.FIGURES_DIR, "fig3_perturbation.pdf")

    if args.check_only:
        with open(raw_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        return check(rows, sum_path, fig_path)

    rng = np.random.default_rng(config.SEED)
    pl = pool_mod.load_pool(include_oversized=False, limit=args.limit)
    picked, _q3 = top_quartile_services(args.scores, pl, args.n_services)
    if not picked:
        sys.exit("no services could be selected - run src/ilsc.py first")
    rows = run_injection(pl, picked, raw_path, rng)
    return check(rows, sum_path, fig_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 2 perturbation + checker.")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--n-services", type=int, default=20)
    ap.add_argument("--out-raw", default="perturbation_raw.csv")
    ap.add_argument("--out-summary", default="perturbation_summary.csv")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

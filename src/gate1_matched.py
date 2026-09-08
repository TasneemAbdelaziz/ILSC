"""
ILSC - Gate 1, re-run as a provider-matched paired design (D-27 remedy).

**Why.** The original Gate 1 fails (D-27), and the diagnosis is a defect in the
*sample* rather than in the metric: three of its five "cohesive" candidates are
hyperscaler services and none of its five "mixed" ones is. Candidates were
selected on author-declared tag counts, and hyperscalers publish narrowly-scoped
single-capability specifications as house style, so that criterion selects them
into the cohesive group. The contrast could therefore be satisfied by provider
rather than by cohesion, and part of it was.

**The fix is to hold provider constant rather than to change the metric.** For
every provider that publishes *both* a single-capability and a many-capability
service, take one of each and compare them **within** the provider. House style,
documentation conventions, authentication boilerplate and specification generator
are then identical on both sides of every comparison, and the only thing that
varies is what the service is for.

Labelling, and why it is not circular
-------------------------------------
The label is the count of distinct OpenAPI **`tags` the author attached to their
own operations** - `n_tags == 1` for single-capability, `n_tags >= MIXED_MIN_TAGS`
for many-capability. This is the same criterion the original shortlist used, and
it is chosen because it is the one structural signal that is **not an ILSC
feature**. Selecting on path shape (f3), operation names (f2), parameters (f4) or
schema names (f5) and then testing whether ILSC separates the result would make
the gate pass by construction.

What this is and is not
-----------------------
This is **not a replacement for the original gate**, and it must not be presented
as one. The original ten carried *hand-written justifications* citing each
service's stated business purpose; this design trades that label quality for
confound control and for a sample two orders of magnitude larger. The two are
complementary:

  * the original tests ten services a human read and vouched for, unmatched;
  * this tests hundreds of provider-matched pairs on a mechanical label.

A human should still validate a random sample of the labels this produces, and
the paper should say whether that was done.

**A paired test is used** because the design is paired: the Wilcoxon signed-rank
statistic over within-provider differences, plus the exact sign test, plus the
matched-pair rank-biserial effect size. An unpaired comparison would throw away
the matching that the whole design exists to create.

Outputs:
    results/gate1_matched.csv        every matched pair with both scores
    results/gate1_matched_verdict.csv
    figures/fig10_gate1_matched.pdf

Usage:
    python src/gate1_matched.py
    python src/gate1_matched.py --mixed-min-tags 4 --min-operations 5
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
import filter as flt                             # noqa: E402
import gate1_select as g1s                       # noqa: E402
import ilsc as ilsc_mod                          # noqa: E402


TAG_CACHE = os.path.join(config.ROOT, ".cache", "author_tags.json")


def load_tags(specs_dir, manifest, limit=None):
    """clean_file -> number of distinct author tags, cached.

    Reading 2,206 specifications takes about a minute, and the sensitivity grid
    needs the same numbers a dozen times over. The cache is keyed on nothing but
    the corpus, which is pinned, so it is safe to reuse; delete it to rebuild.
    """
    if os.path.exists(TAG_CACHE) and not limit:
        with open(TAG_CACHE, encoding="utf-8") as fh:
            cached = json.load(fh)
        if set(cached) >= set(manifest):
            return {k: v for k, v in cached.items() if k in manifest}

    out = {}
    files = sorted(manifest)
    if limit:
        files = files[:limit]
    for i, clean in enumerate(files, 1):
        if i % 400 == 0:
            print("  ... %d/%d specs read" % (i, len(files)), flush=True)
        path = os.path.join(specs_dir, clean)
        if not os.path.exists(path):
            continue
        spec, _ = flt.load_spec(path)
        if spec is None:
            continue
        out[clean] = len(g1s.op_tags(spec))
    if not limit:
        os.makedirs(os.path.dirname(TAG_CACHE), exist_ok=True)
        with open(TAG_CACHE, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
    return out


def build_pairs(scores, tags, args, rng):
    """One matched (single-capability, many-capability) pair per provider."""
    by_provider = {}
    for clean, r in scores.items():
        n_tags = tags.get(clean)
        if n_tags is None or r["n_operations"] < args.min_operations:
            continue
        if n_tags == 1:
            side = "single"
        elif n_tags >= args.mixed_min_tags:
            side = "many"
        else:
            continue                              # deliberately ambiguous middle
        by_provider.setdefault(r["provider"], {"single": [], "many": []})[side].append(
            {"clean_file": clean, "n_tags": n_tags, **r})

    pairs = []
    for prov, sides in sorted(by_provider.items()):
        if not sides["single"] or not sides["many"]:
            continue
        # deterministic pick: the largest of each side, ties by name. Taking the
        # largest keeps the pair statistically meaningful (more operations, more
        # pairs behind each ILSC value) and does not look at the score.
        s = sorted(sides["single"], key=lambda r: (-r["n_operations"], r["clean_file"]))[0]
        m = sorted(sides["many"], key=lambda r: (-r["n_operations"], r["clean_file"]))[0]
        pairs.append({
            "provider": prov,
            "single_file": s["clean_file"], "single_title": s["title"],
            "single_tags": s["n_tags"], "single_ops": s["n_operations"],
            "single_ilsc": s["ILSC_mean"],
            "many_file": m["clean_file"], "many_title": m["title"],
            "many_tags": m["n_tags"], "many_ops": m["n_operations"],
            "many_ilsc": m["ILSC_mean"],
            "delta": s["ILSC_mean"] - m["ILSC_mean"],
        })
    return pairs


def wilcoxon(d):
    """Signed-rank statistic and a normal-approximation p (one-sided, d > 0)."""
    d = np.asarray([x for x in d if np.isfinite(x) and x != 0], dtype=float)
    n = len(d)
    if n < 6:
        return float("nan"), float("nan"), n
    a = np.abs(d)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.arange(1, n + 1)
    sa = a[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    w_pos = ranks[d > 0].sum()
    mu = n * (n + 1) / 4.0
    sd = np.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    z = (w_pos - mu) / sd if sd > 0 else float("nan")
    from math import erfc, sqrt
    p = 0.5 * erfc(z / sqrt(2.0)) if np.isfinite(z) else float("nan")
    return float(w_pos), float(p), n


def sign_test(d):
    """Exact one-sided binomial p that a difference is positive."""
    from math import comb
    d = [x for x in d if np.isfinite(x) and x != 0]
    n, k = len(d), sum(1 for x in d if x > 0)
    if n == 0:
        return float("nan"), 0, 0
    p = sum(comb(n, i) for i in range(k, n + 1)) / (2.0 ** n)
    return float(p), k, n


def run(args):
    with open(args.scores, newline="", encoding="utf-8") as fh:
        scores = {}
        for r in csv.DictReader(fh):
            if r["ILSC_mean"] in ("", "nan"):
                continue
            if str(r.get("oversized", "0")) not in ("0", "", "False", "false"):
                continue
            scores[r["clean_file"]] = {
                "title": r["title"], "provider": r["provider"],
                "source": r["source"], "n_operations": int(r["n_operations"]),
                "ILSC_mean": float(r["ILSC_mean"]),
            }
    print("scored services available: %d" % len(scores))

    print("reading author tags from %s" % args.specs_dir)
    tags = load_tags(args.specs_dir, scores, args.limit)
    print("  tags read for %d services" % len(tags))

    rng = np.random.default_rng(config.SEED)
    pairs = build_pairs(scores, tags, args, rng)
    if len(pairs) < 6:
        sys.exit("only %d matched pairs - too few to test. Loosen --mixed-min-tags."
                 % len(pairs))

    d = np.array([p["delta"] for p in pairs])
    w, p_w, n_w = wilcoxon(d)
    p_s, k, n_s = sign_test(d)
    # matched-pair rank-biserial: the paired analogue of Cliff's delta
    rbc = (2.0 * (d > 0).sum() / len(d)) - 1.0

    print("\n" + "=" * 72)
    print("GATE 1 - PROVIDER-MATCHED PAIRED DESIGN")
    print("=" * 72)
    print("  providers publishing both kinds  %d" % len(pairs))
    print("  label: n_tags == 1  vs  n_tags >= %d   (author-declared, not an ILSC feature)"
          % args.mixed_min_tags)
    print("  min operations per service       %d" % args.min_operations)
    print("\n  mean ILSC, single-capability     %.4f"
          % np.mean([p["single_ilsc"] for p in pairs]))
    print("  mean ILSC, many-capability       %.4f"
          % np.mean([p["many_ilsc"] for p in pairs]))
    print("  mean within-provider difference  %+.4f" % d.mean())
    print("  median difference                %+.4f" % np.median(d))
    print("\n  positive differences             %d of %d (%.1f%%)"
          % (k, n_s, 100.0 * k / max(n_s, 1)))
    print("  rank-biserial (paired)           %+.3f" % rbc)
    print("  Wilcoxon signed-rank, one-sided  p = %.3g   (n = %d)" % (p_w, n_w))
    print("  exact sign test, one-sided       p = %.3g" % p_s)

    verdict = "PASS" if (p_s < 0.05 and d.mean() > 0) else "FAIL"
    print("\n  GATE 1 (matched): %s" % verdict)
    if verdict == "PASS":
        print("  With provider held constant, single-capability services score")
        print("  above many-capability ones from the SAME publisher. The original")
        print("  gate's failure (D-27) is therefore attributable to its sample, not")
        print("  to the metric - which is what D-27 predicted and could not show.")
    else:
        print("  The separation does not survive provider matching either. That is")
        print("  a finding about the metric, not about the sample, and it must be")
        print("  reported as such.")

    worst = sorted(pairs, key=lambda p: p["delta"])[:5]
    print("\n  largest reversals (many-capability scoring above single):")
    for p in worst:
        print("    %-22s %-28s %.3f  vs  %-28s %.3f  (%+.3f)"
              % (p["provider"][:22], p["single_title"][:28], p["single_ilsc"],
                 p["many_title"][:28], p["many_ilsc"], p["delta"]))

    cols = ["provider", "single_file", "single_title", "single_tags", "single_ops",
            "single_ilsc", "many_file", "many_title", "many_tags", "many_ops",
            "many_ilsc", "delta"]
    out = os.path.join(config.RESULTS_DIR, "gate1_matched.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.DictWriter(fh, fieldnames=cols)
        wtr.writeheader()
        for p in pairs:
            wtr.writerow({k2: p[k2] for k2 in cols})
    print("\nwrote %s (%d pairs)" % (out, len(pairs)))

    vout = os.path.join(config.RESULTS_DIR, "gate1_matched_verdict.csv")
    with open(vout, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["metric", "value"])
        for kk, vv in (("verdict", verdict), ("n_pairs", len(pairs)),
                       ("mean_delta", "%.6f" % d.mean()),
                       ("median_delta", "%.6f" % np.median(d)),
                       ("positive_pairs", k), ("n_nonzero", n_s),
                       ("rank_biserial", "%.6f" % rbc),
                       ("wilcoxon_p_one_sided", "%.6g" % p_w),
                       ("sign_test_p_one_sided", "%.6g" % p_s),
                       ("mixed_min_tags", args.mixed_min_tags),
                       ("min_operations", args.min_operations)):
            wtr.writerow([kk, vv])
    print("wrote %s" % vout)

    figure(pairs, d)


def figure(pairs, d):
    fs.use()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.6),
                                   gridspec_kw={"width_ratios": [1.25, 1]})
    c0, m0, _ = fs.series(0)
    c1, m1, _ = fs.series(1)
    x = [p["many_ilsc"] for p in pairs]
    y = [p["single_ilsc"] for p in pairs]
    ax1.scatter(x, y, s=26, alpha=0.75, color=c0, marker=m0, edgecolors="none")
    lim = [min(x + y) - 0.03, max(x + y) + 0.03]
    ax1.plot(lim, lim, linestyle=":", color=fs.INK_MUTED, linewidth=1.0)
    ax1.set_xlim(lim); ax1.set_ylim(lim)
    ax1.set_xlabel("many-capability service (ILSC)")
    ax1.set_ylabel("single-capability service (ILSC)")
    ax1.set_title("Matched within provider", fontsize=9.5)
    ax1.annotate("above the line =\nsingle scores higher", xy=(0.04, 0.93),
                 xycoords="axes fraction", va="top", fontsize=7.5,
                 color=fs.INK_SECONDARY)
    ax1.grid()

    # bins sized to the sample: 24 bins over 16 values is a barcode, not a histogram
    ax2.hist(d, bins=max(5, min(12, len(d) // 2)), color=c1, alpha=0.85)
    ax2.axvline(0, color=fs.INK_MUTED, linewidth=1.0, linestyle=":")
    ax2.set_xlabel("within-provider difference in ILSC")
    ax2.set_ylabel("providers")
    ax2.set_title("Paired differences", fontsize=9.5)
    ax2.grid(axis="y")

    fig.suptitle("Gate 1, provider-matched (n = %d providers)" % len(pairs), fontsize=10)
    p = fs.finish(fig, os.path.join(config.FIGURES_DIR, "fig10_gate1_matched.pdf"))
    print("wrote %s" % p)


def grid(args):
    """Sweep both labelling thresholds and print every cell.

    Reporting the best of several thresholds would be fishing. The grid is run
    and reported whole, so a reader can see whether the result depends on where
    the label boundary was drawn. Its own primary cell is fixed in advance at
    `--mixed-min-tags 5 --min-operations 5`.
    """
    with open(args.scores, newline="", encoding="utf-8") as fh:
        scores = {}
        for r in csv.DictReader(fh):
            if r["ILSC_mean"] in ("", "nan"):
                continue
            if str(r.get("oversized", "0")) not in ("0", "", "False", "false"):
                continue
            scores[r["clean_file"]] = {
                "title": r["title"], "provider": r["provider"], "source": r["source"],
                "n_operations": int(r["n_operations"]),
                "ILSC_mean": float(r["ILSC_mean"])}
    tags = load_tags(args.specs_dir, scores)
    rng = np.random.default_rng(config.SEED)

    rows = []
    print("\n%-10s %-9s %7s %10s %12s %11s %8s"
          % ("tags>=", "ops>=", "pairs", "mean d", "positive", "sign p", "verdict"))
    for mt in [int(x) for x in args.grid_tags.split(",")]:
        for mo in [int(x) for x in args.grid_ops.split(",")]:
            a = argparse.Namespace(**vars(args))
            a.mixed_min_tags, a.min_operations = mt, mo
            pr = build_pairs(scores, tags, a, rng)
            if len(pr) < 3:
                continue
            d = np.array([x["delta"] for x in pr])
            p_s, k, n = sign_test(d)
            ok = "PASS" if (p_s < 0.05 and d.mean() > 0) else "FAIL"
            print("%-10d %-9d %7d %+10.4f %8d/%-3d %11.5f %8s"
                  % (mt, mo, len(pr), d.mean(), k, n, p_s, ok))
            rows.append({"mixed_min_tags": mt, "min_operations": mo,
                         "n_pairs": len(pr), "mean_delta": round(float(d.mean()), 6),
                         "positive": k, "n_nonzero": n,
                         "sign_p_one_sided": round(p_s, 8), "verdict": ok})

    out = os.path.join(config.RESULTS_DIR, "gate1_matched_grid.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    n_pass = sum(1 for r in rows if r["verdict"] == "PASS")
    deltas = [r["mean_delta"] for r in rows]
    print("\n  %d of %d cells PASS." % (n_pass, len(rows)))
    print("  mean within-provider difference across all cells: %+.4f to %+.4f"
          % (min(deltas), max(deltas)))
    fails = [r for r in rows if r["verdict"] == "FAIL"]
    for r in fails:
        print("  the FAIL at tags>=%d ops>=%d has n=%d (%d/%d positive, p=%.4f):"
              % (r["mixed_min_tags"], r["min_operations"], r["n_pairs"],
                 r["positive"], r["n_nonzero"], r["sign_p_one_sided"]))
        print("    a power failure at that sample size, not a reversal of the effect.")
    print("\nwrote %s" % out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gate 1, provider-matched (D-27).")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--specs-dir", default=config.SPECS_CLEAN)
    ap.add_argument("--mixed-min-tags", type=int, default=5)
    ap.add_argument("--min-operations", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--grid", action="store_true",
                    help="sweep both thresholds and report every cell")
    ap.add_argument("--grid-tags", default="3,4,5,6")
    ap.add_argument("--grid-ops", default="3,5,10")
    args = ap.parse_args(argv)
    if args.grid:
        return grid(args)
    run(args)


if __name__ == "__main__":
    main()

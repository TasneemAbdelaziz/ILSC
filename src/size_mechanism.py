"""
ILSC — why does ILSC_mean fall with service size?  (diagnostic, no metric change)

ILSC_mean correlates with operation count at Spearman -0.55 on the primary
population. The null expectation E[ILSC_rand(n)] is flat in n (D-21), so the
formula itself carries no mechanical size bias. This script tests where the
dependence actually comes from, and finds that it is carried by the number of
distinct RESOURCES a service exposes, not by its operation count.

Definitions
-----------
operation   METHOD + path (the unit ILSC compares).
resource    the thing an operation acts on, read off its path: the LAST path
            segment that is neither a template parameter ('{id}') nor a version
            marker ('v1', 'v2.1'). '/customers/{id}/cards' -> 'cards'.
            This is a heuristic proxy, not a validated label: action segments
            ('/users/{id}/activate' -> 'activate') count as resources, and
            '/login' and '/register' count as two resources although both act
            on the user.
root        the coarser alternative that was tried first and does NOT explain
            the dependence: the first segment after the longest path prefix
            shared by every operation of the service. Kept so the negative
            result is reproducible.

Tests
-----
1. Spearman of ILSC_mean with size, with resource count, and of the two with
   each other.
2. Spearman partial correlations: size given resources, resources given size.
3. Within each size band, ILSC against resource count.
4. At a fixed resource count, ILSC against size.
5. Path similarity (f3-style Jaccard on the parser's path_tokens) for pairs on
   the same resource vs different resources, by size band. This is a LEXICAL
   proxy for one feature only; the engine's full pairwise Sim is not stored,
   so the same/different split is not computed on ILSC itself. Pairs are
   sampled (at most PAIR_SAMPLE per service, seeded with config.SEED).

Inputs:  results/ilsc_scores.csv, parsed/<service>.json
Outputs: results/size_mechanism.csv           one row per service
         results/size_mechanism_summary.csv   every correlation, tidy
         results/size_mechanism_bands.csv     per size band
"""

import argparse
import csv
import itertools
import json
import math
import os
import random
import re
import statistics as st
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import config  # noqa: E402

PAIR_SAMPLE = 1500
BANDS = [(3, 5), (6, 10), (11, 20), (21, 50), (51, 200)]
FIXED_RESOURCE_COUNTS = (1, 2, 3, 5, 8)
MIN_GROUP = 30
_VERSION = re.compile(r"^v\d+(\.\d+)*$", re.IGNORECASE)


# --------------------------------------------------------------------------
# statistics (Spearman with average ranks for ties; no scipy needed)
# --------------------------------------------------------------------------

def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def _pearson(a, b):
    ma, mb = st.fmean(a), st.fmean(b)
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return float("nan") if den == 0 else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den


def spearman(a, b):
    return _pearson(_ranks(a), _ranks(b))


def partial_spearman(x, y, z):
    """Spearman correlation of x and y, controlling for z."""
    rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
    return (rxy - rxz * ryz) / math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))


# --------------------------------------------------------------------------
# resources
# --------------------------------------------------------------------------

def _segments(path):
    return [s.lower() for s in path.strip("/").split("/")
            if s and not s.startswith("{") and not _VERSION.match(s)]


def leaf_resources(paths):
    out = []
    for p in paths:
        seg = _segments(p)
        out.append(seg[-1] if seg else "<root>")
    return out


def root_resources(paths):
    raw = [p.strip("/").split("/") for p in paths]
    k = 0
    while all(len(s) > k for s in raw) and len({s[k] for s in raw}) == 1:
        k += 1
    out = []
    for s in raw:
        rest = [x.lower() for x in s[k:] if x and not x.startswith("{") and not _VERSION.match(x)]
        out.append(rest[0] if rest else "<root>")
    return out


def same_share(labels):
    counts = {}
    for x in labels:
        counts[x] = counts.get(x, 0) + 1
    n = len(labels)
    return sum(c * (c - 1) // 2 for c in counts.values()) / (n * (n - 1) // 2)


def band_of(n):
    for lo, hi in BANDS:
        if lo <= n <= hi:
            return f"{lo}-{hi}"
    return f">{BANDS[-1][1]}"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--population", choices=("primary", "full"), default="primary",
                    help="primary = <= config.OVERSIZED_MAX_OPERATIONS operations (D-17)")
    args = ap.parse_args(argv)
    cap = config.OVERSIZED_MAX_OPERATIONS if args.population == "primary" else 10 ** 9
    rng = random.Random(config.SEED)

    with open(os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"), newline="", encoding="utf-8") as fh:
        scores = [r for r in csv.DictReader(fh) if int(r["n_operations"]) <= cap]

    rows, lex = [], {}
    for r in scores:
        stem = r["clean_file"].rsplit(".", 1)[0]
        with open(os.path.join(config.PARSED_DIR, stem + ".json"), encoding="utf-8") as fh:
            ops = json.load(fh)["operations"]
        paths = [o["path"] for o in ops]
        leaf, root = leaf_resources(paths), root_resources(paths)
        n = len(ops)
        rows.append({
            "clean_file": r["clean_file"], "title": r["title"], "source": r["source"],
            "n_operations": n, "size_band": band_of(n),
            "n_resources": len(set(leaf)),
            "same_resource_pair_share": round(same_share(leaf), 6),
            "n_roots": len(set(root)),
            "same_root_pair_share": round(same_share(root), 6),
            "ILSC_mean": float(r["ILSC_mean"]),
        })
        idx = list(itertools.combinations(range(n), 2))
        if len(idx) > PAIR_SAMPLE:
            idx = rng.sample(idx, PAIR_SAMPLE)
        for i, j in idx:
            a, b = set(ops[i]["path_tokens"]), set(ops[j]["path_tokens"])
            if a or b:
                lex.setdefault((band_of(n), leaf[i] == leaf[j]), []).append(len(a & b) / len(a | b))

    size = [x["n_operations"] for x in rows]
    ilsc = [x["ILSC_mean"] for x in rows]
    res = [x["n_resources"] for x in rows]
    share = [x["same_resource_pair_share"] for x in rows]
    rshare = [x["same_root_pair_share"] for x in rows]

    summary = []

    def add(test, value, n, note=""):
        summary.append({"test": test, "value": f"{value:+.4f}", "n_services": n, "note": note})

    N = len(rows)
    add("rho(ILSC, size)", spearman(ilsc, size), N, "the dependence being explained")
    add("rho(ILSC, n_resources)", spearman(ilsc, res), N)
    add("rho(n_resources, size)", spearman(res, size), N)
    add("rho(same_resource_pair_share, size)", spearman(share, size), N)
    add("partial rho(ILSC, size | n_resources)", partial_spearman(ilsc, size, res), N,
        "~0: size has no effect once resource count is fixed")
    add("partial rho(ILSC, n_resources | size)", partial_spearman(ilsc, res, size), N,
        "resource count still matters at fixed size")
    add("partial rho(ILSC, size | same_root_pair_share)", partial_spearman(ilsc, size, rshare), N,
        "coarse 'root' definition does NOT explain the dependence (negative result)")
    for lo, hi in BANDS:
        ii = [i for i in range(N) if lo <= size[i] <= hi]
        add(f"rho(ILSC, n_resources) within size {lo}-{hi}",
            spearman([ilsc[i] for i in ii], [res[i] for i in ii]), len(ii))
    for k in FIXED_RESOURCE_COUNTS:
        ii = [i for i in range(N) if res[i] == k]
        if len(ii) >= MIN_GROUP:
            add(f"rho(ILSC, size) at exactly {k} resource(s)",
                spearman([ilsc[i] for i in ii], [size[i] for i in ii]), len(ii),
                f"operations range {min(size[i] for i in ii)}-{max(size[i] for i in ii)}")

    bands = []
    for lo, hi in BANDS:
        b = f"{lo}-{hi}"
        ii = [i for i in range(N) if rows[i]["size_band"] == b]
        same, diff = lex.get((b, True), []), lex.get((b, False), [])
        bands.append({
            "size_band": b, "n_services": len(ii),
            "median_n_resources": st.median(res[i] for i in ii),
            "median_same_resource_pair_share": round(st.median(share[i] for i in ii), 4),
            "median_ops_per_resource": round(st.median(size[i] / res[i] for i in ii), 3),
            "path_jaccard_same_resource": round(st.fmean(same), 4) if same else "",
            "path_jaccard_diff_resource": round(st.fmean(diff), 4) if diff else "",
            "pairs_sampled_same": len(same), "pairs_sampled_diff": len(diff),
            "median_ILSC_mean": round(st.median(ilsc[i] for i in ii), 4),
        })

    suffix = "" if args.population == "primary" else "_full"
    out = lambda name: os.path.join(config.RESULTS_DIR, f"size_mechanism{name}{suffix}.csv")
    for path, data in ((out(""), rows), (out("_summary"), summary), (out("_bands"), bands)):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)

    print(f"population: {args.population} ({N} services)")
    for s in summary:
        print(f"  {s['test']:<52}{s['value']:>9}   n={s['n_services']:<5} {s['note']}")
    print("\n  band     services  resources  same-res pairs  path-Jaccard same/diff  ILSC")
    for b in bands:
        print(f"  {b['size_band']:<9}{b['n_services']:>8}{b['median_n_resources']:>11}"
              f"{100 * b['median_same_resource_pair_share']:>14.0f}%"
              f"{b['path_jaccard_same_resource']:>14}/{b['path_jaccard_diff_resource']:<8}"
              f"{b['median_ILSC_mean']:>7}")


if __name__ == "__main__":
    main()

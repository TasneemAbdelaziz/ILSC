"""
ILSC - Day 4 metric track (Mohamed): the metric itself, over the whole corpus.

Turns the similarity engine into the three published aggregates (Sec. 6):

    ILSC_mean(S) = (2 / n(n-1)) * SUM_{i<j} Sim(Oi,Oj)
    ILSC_tau(S)  = |{(i,j): Sim >= tau}| / (n(n-1)/2)        default tau = 0.50
    ILSC_norm(S) = (ILSC_mean - E[ILSC_rand(n)]) / (1 - E[ILSC_rand(n)])

plus the connected-component count of the similarity graph at tau, which is the
descriptive statistic behind the tau sweep (Exp. 5, Fig 6).

ILSC_norm is filled in only when a null-model table is supplied
(``--null results/null_model.csv``, produced by ``src/null_models.py``); without
one the column is left empty rather than silently defaulting to ILSC_mean.

D-17 is honoured here rather than bolted on afterwards: every service is scored,
the ``oversized`` flag rides along from the manifest, and the summary prints the
PRIMARY (<= 200 operations) and SENSITIVITY (full corpus) figures side by side.
Nothing is filtered away on disk - the caller decides which population to read.

Two services are too large for a component count
------------------------------------------------
Connected components need every edge of the similarity graph enumerated, which
is O(n^2) in *edges*, not in aggregate. Above ``COMPONENT_MAX_OPERATIONS`` the
column is left empty and the service is counted in the summary. At the pinned
value of 2,000 this affects Microsoft Graph and Datto/Autotask PSA - both
already ``oversized``, so the primary analysis is unaffected.

Usage:
    python src/ilsc.py                                   # whole corpus
    python src/ilsc.py --primary-only                    # D-17 primary population
    python src/ilsc.py --limit 50 --out results/smoke.csv
    python src/ilsc.py --null results/null_model.csv     # adds ILSC_norm
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

import config                                   # noqa: E402
import embed as emb_mod                         # noqa: E402
import similarity as sim                        # noqa: E402

COMPONENT_MAX_OPERATIONS = 2000

COLUMNS = [
    "clean_file", "title", "provider", "source", "spec_version",
    "n_operations", "oversized", "n_pairs",
    "ILSC_mean", "ILSC_tau", "ILSC_norm_global", "ILSC_norm_provider",
    "norm_provider_fallback", "tau",
    "n_components", "largest_component",
    "mask_fire_pairs", "mask_fire_pct", "no_evidence_pairs",
] + ["avail_pairs_" + f for f in sim.FEATURES] \
  + ["mean_" + f for f in sim.FEATURES]


# ----------------------------------------------------------------------------
# Connected components of the similarity graph at tau
# ----------------------------------------------------------------------------

class UnionFind:
    __slots__ = ("parent",)

    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def components_at_tau(opset, weights, tau):
    """(n_components, largest_component) of the graph {Sim >= tau}."""
    n = opset.n
    if n == 0:
        return 0, 0
    if n > COMPONENT_MAX_OPERATIONS:
        return None, None
    uf = UnionFind(n)
    for i0, i1, s, _per, _mask in sim.pair_blocks(opset, weights, tau):
        hit = (s >= tau) & sim.triu_selector(i0, i1, n)
        rows, cols = np.nonzero(hit)
        for a, j in zip(rows, cols):
            uf.union(i0 + int(a), int(j))
    sizes = {}
    for i in range(n):
        r = uf.find(i)
        sizes[r] = sizes.get(r, 0) + 1
    return len(sizes), max(sizes.values())


# ----------------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------------

def score_service(doc, emb, name, weights=None, tau=None, want_components=True):
    tau = config.TAU_DEFAULT if tau is None else tau
    oset = sim.OpSet.from_service(doc, emb, name)
    st = sim.service_stats(oset, weights=weights, tau=tau, want_feature_sums=True)

    row = {
        "n_operations": st["n_operations"],
        "n_pairs": st["n_pairs"],
        "ILSC_mean": st["ILSC_mean"],
        "ILSC_tau": st["ILSC_tau"],
        "ILSC_norm_global": "", "ILSC_norm_provider": "",
        "norm_provider_fallback": "",
        "tau": tau,
        "mask_fire_pairs": st["mask_fire_pairs"],
        "mask_fire_pct": (100.0 * st["mask_fire_pairs"] / st["n_pairs"]
                          if st["n_pairs"] else float("nan")),
        "no_evidence_pairs": st["no_evidence_pairs"],
        "n_components": "", "largest_component": "",
    }
    for k, f in enumerate(sim.FEATURES):
        cnt = int(st["feature_pairs"][k])
        row["avail_pairs_" + f] = cnt
        row["mean_" + f] = (st["feature_sum"][k] / cnt) if cnt else float("nan")

    if want_components:
        nc, lc = components_at_tau(oset, weights, tau)
        if nc is not None:
            row["n_components"], row["largest_component"] = nc, lc
    return row


def load_manifest(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["clean_file"]: r for r in csv.DictReader(fh)}


def load_null_table(path):
    """Read results/null_model.csv -> (global_expectation, {provider: expectation}).

    E[ILSC_rand] does not depend on n - see D-21 and the flatness check in
    src/null_models.py - so the table is keyed by model and provider only.
    """
    if not path or not os.path.exists(path):
        return None, {}
    g, byprov = None, {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["model"] == "global":
                g = float(r["expected_ilsc"])
            elif r["model"] == "provider":
                byprov[r["provider"]] = float(r["expected_ilsc"])
    return g, byprov


def parsed_to_clean(name, manifest):
    if name in manifest:
        return name
    stem = os.path.splitext(name)[0]
    for ext in (".yaml", ".yml", ".json"):
        if stem + ext in manifest:
            return stem + ext
    return name


def run(parsed_dir, cache_dir, manifest_path, out_path, tau, weights,
        limit=None, primary_only=False, null_path=None, no_components=False):
    emb = emb_mod.Embeddings(cache_dir)
    manifest = load_manifest(manifest_path)
    null_global, null_provider = load_null_table(null_path)

    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    if limit:
        files = files[:limit]

    rows, skipped, no_comp = [], [], 0
    t0 = time.time()
    for i, name in enumerate(files, 1):
        if i % 100 == 0:
            print("  ... %d/%d  (%.0fs)" % (i, len(files), time.time() - t0), flush=True)
        clean = parsed_to_clean(name, manifest)
        meta = manifest.get(clean, {})
        oversized = str(meta.get("oversized", "")).strip().lower() in ("1", "true", "yes")
        if primary_only and oversized:
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        if name not in emb:
            skipped.append((name, "not in embedding cache"))
            continue
        row = score_service(doc, emb, name, weights, tau,
                            want_components=not no_components)
        row.update({
            "clean_file": clean,
            "title": doc.get("title", ""),
            "provider": doc.get("provider", ""),
            "source": doc.get("source", ""),
            "spec_version": doc.get("spec_version", ""),
            "oversized": int(oversized),
        })
        if null_global is not None:
            row["ILSC_norm_global"] = sim.ilsc_norm(row["ILSC_mean"], null_global)
            # A provider absent from the table has no estimable pool of its own.
            # src/null_models.py already handles that case by falling back to the
            # global expectation and marking it; leaving the column blank here
            # was inconsistent with that, and it silently denied every oversized
            # service a normalised score - the null pool excludes them (D-17), so
            # a provider whose services are all oversized never appears at all.
            e = null_provider.get(row["provider"])
            row["norm_provider_fallback"] = int(e is None)
            row["ILSC_norm_provider"] = sim.ilsc_norm(
                row["ILSC_mean"], null_global if e is None else e)
        if row["n_components"] == "":
            no_comp += 1
        rows.append(row)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})

    print("\nscored %d services in %.0fs -> %s" % (len(rows), time.time() - t0, out_path))
    if skipped:
        print("skipped %d: %s" % (len(skipped), skipped[:3]))
    if no_comp:
        print("component count omitted for %d service(s) above %d operations"
              % (no_comp, COMPONENT_MAX_OPERATIONS))
    summarise(rows, tau)
    write_thresholds(rows, os.path.join(os.path.dirname(out_path), "ilsc_thresholds.csv"))
    print("wrote %s" % os.path.join(os.path.dirname(out_path), "ilsc_thresholds.csv"))
    return rows


# ----------------------------------------------------------------------------
# Summary - always primary beside sensitivity (D-17)
# ----------------------------------------------------------------------------

def _q(vals, p):
    return float(np.percentile(vals, p)) if len(vals) else float("nan")


def summarise(rows, tau):
    prim = [r for r in rows if not r["oversized"]]
    full = rows
    print("\n%-24s %14s %14s" % ("", "PRIMARY (<=%d)" % config.OVERSIZED_MAX_OPERATIONS,
                                 "SENSITIVITY"))
    print("%-24s %14s %14s" % ("services", "{:,}".format(len(prim)), "{:,}".format(len(full))))
    for label, key in (("ILSC_mean", "ILSC_mean"), ("ILSC_tau (t=%.2f)" % tau, "ILSC_tau")):
        a = [r[key] for r in prim if np.isfinite(r[key])]
        b = [r[key] for r in full if np.isfinite(r[key])]
        print("%-24s %14.4f %14.4f" % (label + " mean", np.mean(a) if a else float("nan"),
                                       np.mean(b) if b else float("nan")))
        print("%-24s %14s %14s"
              % ("  Q1 / med / Q3",
                 "%.3f/%.3f/%.3f" % (_q(a, 25), _q(a, 50), _q(a, 75)),
                 "%.3f/%.3f/%.3f" % (_q(b, 25), _q(b, 50), _q(b, 75))))


def thresholds(rows, key="ILSC_mean"):
    """Quartile thresholds, in the Bogner sense: the corpus distribution's cut points."""
    vals = sorted(r[key] for r in rows if isinstance(r[key], float) and np.isfinite(r[key]))
    if not vals:
        return {}
    return {"n": len(vals), "min": vals[0], "q1": _q(vals, 25), "median": _q(vals, 50),
            "q3": _q(vals, 75), "max": vals[-1], "mean": float(np.mean(vals))}


# Populations the threshold table is cut on. S1-only is not optional garnish:
# S1 is the RAMA corpus, so S1-only quartiles are what make these thresholds
# comparable with Bogner's published ones (Sec. 7). Reporting only the pooled
# quartiles would forfeit the comparability the multi-source design was for.
POPULATIONS = (
    ("primary_all", lambda r: not r["oversized"]),
    ("primary_S1", lambda r: not r["oversized"] and r["source"] == "S1"),
    ("primary_S2", lambda r: not r["oversized"] and r["source"] == "S2"),
    ("sensitivity_all", lambda r: True),
    ("sensitivity_S1", lambda r: r["source"] == "S1"),
)

THRESHOLD_KEYS = ("ILSC_mean", "ILSC_tau", "ILSC_norm_global", "ILSC_norm_provider")


def write_thresholds(rows, out_path):
    """The Day 5 threshold table: every metric x every population, side by side."""
    out = []
    for pop, keep in POPULATIONS:
        sub = [r for r in rows if keep(r)]
        for key in THRESHOLD_KEYS:
            t = thresholds(sub, key)
            if not t:
                continue
            out.append({"population": pop, "metric": key, **{k: ("%.6f" % v
                        if isinstance(v, float) else v) for k, v in t.items()}})
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["population", "metric", "n", "min", "q1",
                                           "median", "q3", "max", "mean"])
        w.writeheader()
        for r in out:
            w.writerow(r)

    print("\nquartile thresholds (ILSC_mean)")
    print("  %-18s %6s %8s %8s %8s" % ("population", "n", "Q1", "median", "Q3"))
    for r in out:
        if r["metric"] != "ILSC_mean":
            continue
        print("  %-18s %6s %8s %8s %8s"
              % (r["population"], r["n"], r["q1"][:6], r["median"][:6], r["q3"][:6]))
    print("\n  S1-only quartiles are the ones comparable with Bogner (Sec. 7);")
    print("  the pooled figures are not, because S2 is a different population.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compute ILSC over the corpus.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--out", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--tau", type=float, default=config.TAU_DEFAULT)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--primary-only", action="store_true",
                    help="skip oversized services entirely (D-17 primary population)")
    ap.add_argument("--null", default=None, help="null-model CSV; adds ILSC_norm")
    ap.add_argument("--no-components", action="store_true")
    args = ap.parse_args(argv)

    run(args.parsed_dir, args.cache, args.manifest, args.out, args.tau,
        sim.DEFAULT_WEIGHTS, args.limit, args.primary_only, args.null,
        args.no_components)


if __name__ == "__main__":
    main()

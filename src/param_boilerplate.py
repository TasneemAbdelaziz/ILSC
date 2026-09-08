"""
ILSC - F-05: f5 excludes infrastructural schemas; f4 excludes nothing.

Sec. 6 [v3] excludes a schema from **f5** when it appears on more than
``config.FREQUENT_SCHEMA_RATIO`` (80%) of a service's operations, on the grounds
that such a schema is infrastructural rather than domain-bearing. **No
equivalent rule exists for f4**, whose parameter-name tokens are compared with a
bare Jaccard.

The asymmetry is not harmless. Google attaches ``fields``, ``oauth_token``,
``key``, ``prettyPrint``, ``quotaUser`` and ``alt`` to **100% of its 10,103
operations**; AWS attaches seven ``X-Amz-*`` signing parameters to 99% of its
11,843. These are authentication and serialisation boilerplate with no domain
content, and under Jaccard they make every pair of operations in such a service
look alike.

This module measures what an f5-style exclusion on f4 would do. It **does not
change the metric** - the rule is Sec. 6's to set, and altering a feature after
seeing which services it favours is exactly the move this project refuses
elsewhere (see `docs/discordance.md` §3 on ``Sim_code``). It produces the number
the decision needs.

**What this estimate is and is not.** It re-scores with boilerplate parameters
removed from the f4 token set only. ``T(Oi)`` also contains the parameter
tokens, so a real change would move the **f1 embeddings** too and would require
a re-embed. Holding f1 fixed therefore gives the *f4-only* effect, which is a
**lower bound** on the full change.

Usage:
    python src/param_boilerplate.py
    python src/param_boilerplate.py --ratio 0.8 --limit 400
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

import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import ilsc as ilsc_mod                          # noqa: E402
import parse_spec as ps                          # noqa: E402

BIG3 = ("amazonaws", "googleapis", "azure")


def is_big3(provider):
    return any(k in (provider or "") for k in BIG3)


def strip_boilerplate(doc, ratio):
    """Return operations whose param_tokens drop service-wide boilerplate.

    The rule mirrors f5's exactly: a *parameter name* carried by more than
    `ratio` of a service's operations is infrastructural for that service.
    Applied per service, as f5's is - a parameter that is boilerplate for Google
    may be domain-bearing elsewhere.
    """
    ops = doc["operations"]
    n = len(ops)
    freq = {}
    for o in ops:
        for p in set(o.get("param_names") or []):
            freq[p] = freq.get(p, 0) + 1
    dropped = {p for p, c in freq.items() if n and c / n > ratio}

    out, n_tokens_removed = [], 0
    for o in ops:
        keep = [p for p in (o.get("param_names") or []) if p not in dropped]
        toks = sorted({t for p in keep for t in ps.tokenize(p)})
        n_tokens_removed += max(len(o.get("param_tokens") or []) - len(toks), 0)
        o2 = dict(o)
        o2["param_tokens"] = toks
        out.append(o2)
    return out, dropped, n_tokens_removed


def run(args):
    emb = emb_mod.Embeddings(args.cache)
    manifest = ilsc_mod.load_manifest(args.manifest)
    files = sorted(n for n in os.listdir(args.parsed_dir) if n.endswith(".json"))
    if args.limit:
        files = files[:args.limit]

    rows = []
    for i, name in enumerate(files, 1):
        if i % 400 == 0:
            print("  ... %d/%d" % (i, len(files)), flush=True)
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        meta = manifest.get(clean, {})
        if str(meta.get("oversized", "")).strip().lower() in ("1", "true", "yes"):
            continue
        if name not in emb:
            continue
        with open(os.path.join(args.parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc["n_operations"] < 2:
            continue

        T, D = emb.matrix_T(name), emb.matrix_D(name)
        before = sim.ilsc_mean(sim.OpSet(doc["operations"], T, D))
        ops2, dropped, _n = strip_boilerplate(doc, args.ratio)
        after = sim.ilsc_mean(sim.OpSet(ops2, T, D))
        rows.append({
            "clean_file": clean, "provider": doc.get("provider", ""),
            "big3": int(is_big3(doc.get("provider", ""))),
            "n_operations": doc["n_operations"],
            "n_params_dropped": len(dropped),
            "dropped": "|".join(sorted(dropped)[:8]),
            "ilsc_before": before, "ilsc_after": after, "delta": after - before,
        })

    if not rows:
        sys.exit("no services scored")

    b = np.array([r["delta"] for r in rows if r["big3"]])
    o = np.array([r["delta"] for r in rows if not r["big3"]])
    allv = np.array([r["delta"] for r in rows])
    affected = [r for r in rows if r["n_params_dropped"] > 0]

    print("\n" + "=" * 72)
    print("F-05 - what an f5-style exclusion on f4 would do (ratio > %.2f)" % args.ratio)
    print("=" * 72)
    print("  services scored                    %d" % len(rows))
    print("  with at least one dropped parameter %d (%.1f%%)"
          % (len(affected), 100.0 * len(affected) / len(rows)))
    print("\n  mean change in ILSC_mean:")
    print("    all services            %+.4f" % allv.mean())
    print("    AWS/Google/Azure        %+.4f   (n=%d)" % (b.mean(), len(b)))
    print("    everyone else           %+.4f   (n=%d)" % (o.mean(), len(o)))
    print("    difference              %+.4f   <- how much of the gap this closes"
          % (b.mean() - o.mean()))

    before_b = np.array([r["ilsc_before"] for r in rows if r["big3"]])
    before_o = np.array([r["ilsc_before"] for r in rows if not r["big3"]])
    after_b = np.array([r["ilsc_after"] for r in rows if r["big3"]])
    after_o = np.array([r["ilsc_after"] for r in rows if not r["big3"]])
    gap_before = np.median(before_b) - np.median(before_o)
    gap_after = np.median(after_b) - np.median(after_o)
    print("\n  median ILSC_mean, hyperscalers vs the rest:")
    print("    before   %.4f vs %.4f   gap %+.4f" % (np.median(before_b), np.median(before_o), gap_before))
    print("    after    %.4f vs %.4f   gap %+.4f" % (np.median(after_b), np.median(after_o), gap_after))
    print("    the gap closes by %.1f%%" % (100.0 * (gap_before - gap_after) / gap_before))

    worst = sorted(rows, key=lambda r: r["delta"])[:6]
    print("\n  largest individual drops:")
    for r in worst:
        print("    %-46s %.4f -> %.4f (%+.4f)  dropped: %s"
              % (r["clean_file"][:46], r["ilsc_before"], r["ilsc_after"],
                 r["delta"], r["dropped"][:44]))

    out = os.path.join(config.RESULTS_DIR, "param_boilerplate.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote %s" % out)
    print("\n  This is a LOWER BOUND: T(Oi) contains the parameter tokens too, so a")
    print("  real change would also move the f1 embeddings. The metric is NOT")
    print("  changed here - F-05 records the evidence and Sec. 6 owns the rule.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="F-05 - f4 boilerplate parameters.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--ratio", type=float, default=config.FREQUENT_SCHEMA_RATIO)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

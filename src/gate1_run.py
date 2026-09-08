"""
ILSC - Day 4 metric track: run Gate 1.

Gate 1 (proposal Sec. 12): the five services Tasneem picked as *cohesive* must
score clearly above the five she picked as *mixed*. The picks and the written
reasons were frozen before any score existed (``docs/gate1_expectations.md``,
``results/gate1_candidates.csv``), which is what makes this a test rather than a
demonstration.

The verdict is computed, not eyeballed, on three criteria:

  **separation**  min(cohesive) > max(mixed)  - a clean split with no overlap
  **gap**         mean(cohesive) - mean(mixed), reported with Cliff's delta so
                  a five-against-five comparison is not read as if it were
                  powered
  **exact test**  the one-sided Mann-Whitney/permutation p-value. With 5 v 5 the
                  smallest attainable p is 1/C(10,5) = 0.0040, so a perfect
                  split is significant at 0.05 and nothing less than a near
                  perfect split can be. This is stated because "n = 10" and
                  "p < 0.05" are easy to misread together.

If separation fails, the proposal's instruction is to suspect tokenisation
first, then the weights - so ``--diagnose`` prints the token sets and the
per-feature means for the offending services rather than leaving the reader to
guess.

Outputs:
    results/sanity_check.csv     one row per candidate, sorted by ILSC_mean
    results/gate1_pairs_<id>.csv with --dump-pairs, for the discordant cases

Usage:
    python src/gate1_run.py
    python src/gate1_run.py --diagnose
    python src/gate1_run.py --tau 0.4 --dump-pairs C4,M1
"""

import argparse
import csv
import json
import os
import sys
from itertools import combinations

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                   # noqa: E402
import embed as emb_mod                         # noqa: E402
import similarity as sim                        # noqa: E402
import ilsc as ilsc_mod                         # noqa: E402


def cliffs_delta(a, b):
    """P(a > b) - P(a < b). Non-parametric effect size, no distributional claim."""
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    return (gt - lt) / float(len(a) * len(b))


def exact_p_one_sided(cohesive, mixed):
    """Permutation test: P(rank sum this extreme | labels exchangeable)."""
    vals = list(cohesive) + list(mixed)
    k = len(cohesive)
    observed = sum(cohesive)
    n_ge = 0
    total = 0
    for combo in combinations(range(len(vals)), k):
        total += 1
        if sum(vals[i] for i in combo) >= observed - 1e-12:
            n_ge += 1
    return n_ge / float(total), total


def parsed_name_for(clean_file, parsed_dir):
    """manifest clean_file (maybe .yaml) -> parsed/<stem>.json"""
    stem = os.path.splitext(clean_file)[0]
    for cand in (clean_file, stem + ".json"):
        if os.path.exists(os.path.join(parsed_dir, cand)):
            return cand
    return stem + ".json"


def run(args):
    emb = emb_mod.Embeddings(args.cache)
    with open(args.candidates, newline="", encoding="utf-8") as fh:
        cands = list(csv.DictReader(fh))
    if not cands:
        sys.exit("no candidates in %s" % args.candidates)

    rows = []
    for c in cands:
        name = parsed_name_for(c["clean_file"], args.parsed_dir)
        path = os.path.join(args.parsed_dir, name)
        if not os.path.exists(path) or name not in emb:
            print("  MISSING %s (%s)" % (c["id"], name))
            continue
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = sim.OpSet.from_service(doc, emb, name)
        st = sim.service_stats(oset, tau=args.tau, want_feature_sums=True)
        nc, lc = ilsc_mod.components_at_tau(oset, None, args.tau)
        row = {
            "id": c["id"], "expectation": c["expectation"], "title": c["title"],
            "provider": c["provider"], "source": c["source"],
            "n_operations": st["n_operations"], "n_pairs": st["n_pairs"],
            "ILSC_mean": st["ILSC_mean"], "ILSC_tau": st["ILSC_tau"],
            "tau": args.tau,
            "n_components": nc if nc is not None else "",
            "mask_fire_pct": (100.0 * st["mask_fire_pairs"] / st["n_pairs"]
                              if st["n_pairs"] else float("nan")),
            "n_author_tags": c.get("n_author_tags", ""),
            "why_chosen": c.get("why_chosen", ""),
            "_parsed": name, "_doc": doc, "_opset": oset,
        }
        for k, f in enumerate(sim.FEATURES):
            cnt = int(st["feature_pairs"][k])
            row["mean_" + f] = (st["feature_sum"][k] / cnt) if cnt else float("nan")
            row["availpct_" + f] = 100.0 * cnt / st["n_pairs"] if st["n_pairs"] else float("nan")
        rows.append(row)

    rows.sort(key=lambda r: -r["ILSC_mean"])
    cohesive = [r["ILSC_mean"] for r in rows if r["expectation"] == "cohesive"]
    mixed = [r["ILSC_mean"] for r in rows if r["expectation"] == "mixed"]

    # ---- the table -------------------------------------------------------
    print("\nGATE 1 - ILSC_mean, weights 1/6, tau %.2f\n" % args.tau)
    print("  %-4s %-9s %-34s %4s %8s %8s %6s  %s"
          % ("id", "expected", "title", "ops", "ILSC", "ILSC_t", "comp", "mask%"))
    for r in rows:
        print("  %-4s %-9s %-34s %4d %8.4f %8.4f %6s  %5.1f"
              % (r["id"], r["expectation"], r["title"][:34], r["n_operations"],
                 r["ILSC_mean"], r["ILSC_tau"], r["n_components"], r["mask_fire_pct"]))

    # ---- the verdict -----------------------------------------------------
    print("\n  cohesive  n=%d  mean %.4f  min %.4f" % (len(cohesive), np.mean(cohesive), min(cohesive)))
    print("  mixed     n=%d  mean %.4f  max %.4f" % (len(mixed), np.mean(mixed), max(mixed)))
    gap = float(np.mean(cohesive) - np.mean(mixed))
    delta = cliffs_delta(cohesive, mixed)
    p, total = exact_p_one_sided(cohesive, mixed)
    separated = min(cohesive) > max(mixed)

    print("\n  gap (mean difference)  %+.4f" % gap)
    print("  Cliff's delta          %+.3f   (+1.0 = every cohesive above every mixed)" % delta)
    print("  exact one-sided p      %.4f   over %d label assignments" % (p, total))
    print("  clean separation       %s" % ("YES" if separated else "NO"))
    print("\n  Smallest p attainable with %d v %d is %.4f - read the p-value with that"
          % (len(cohesive), len(mixed), 1.0 / total))
    print("  in mind; the effect size and the clean split carry more here than p.")

    verdict = "PASS" if (separated and delta > 0.8) else (
        "MARGINAL" if delta > 0.5 else "FAIL")
    print("\n  GATE 1: %s" % verdict)
    if verdict != "PASS":
        print("  Proposal instruction: suspect tokenisation first (print tokens and look),")
        print("  then upweight path+schema / downweight name. Fix BEFORE the big run.")
        print("  Run again with --diagnose.")

    # ---- write ------------------------------------------------------------
    cols = ["id", "expectation", "title", "provider", "source", "n_operations",
            "n_pairs", "ILSC_mean", "ILSC_tau", "tau", "n_components",
            "mask_fire_pct", "n_author_tags"] \
        + ["mean_" + f for f in sim.FEATURES] \
        + ["availpct_" + f for f in sim.FEATURES] + ["why_chosen"]
    out = os.path.join(config.RESULTS_DIR, args.out)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("\nwrote %s" % out)

    summary = os.path.join(config.RESULTS_DIR, "gate1_verdict.csv")
    with open(summary, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        for k, v in (("verdict", verdict), ("gap", "%.6f" % gap),
                     ("cliffs_delta", "%.6f" % delta), ("exact_p_one_sided", "%.6f" % p),
                     ("clean_separation", int(separated)),
                     ("cohesive_mean", "%.6f" % np.mean(cohesive)),
                     ("mixed_mean", "%.6f" % np.mean(mixed)),
                     ("cohesive_min", "%.6f" % min(cohesive)),
                     ("mixed_max", "%.6f" % max(mixed)),
                     ("tau", args.tau)):
            w.writerow([k, v])
    print("wrote %s" % summary)

    if args.diagnose:
        diagnose(rows)
    if args.dump_pairs:
        for want in args.dump_pairs.split(","):
            for r in rows:
                if r["id"] == want.strip():
                    dump_pairs(r)
    return verdict


def diagnose(rows):
    print("\n" + "=" * 72)
    print("DIAGNOSTICS - per-feature means (masked pairs only) and availability")
    print("=" * 72)
    print("  %-4s %-9s %s" % ("id", "expected",
                              "  ".join("%-13s" % f for f in sim.FEATURES)))
    for r in rows:
        cells = []
        for f in sim.FEATURES:
            m, a = r["mean_" + f], r["availpct_" + f]
            cells.append("%.3f/%3.0f%%    " % (m, a) if np.isfinite(m) else "  --/%3.0f%%    " % a)
        print("  %-4s %-9s %s" % (r["id"], r["expectation"], "".join(cells)))
    print("\n  (value = mean similarity on pairs where the feature is available;")
    print("   %% = share of pairs where it is available)")

    print("\n  Token sets for the two most surprising services:")
    order = sorted(rows, key=lambda r: (r["ILSC_mean"] if r["expectation"] == "mixed"
                                        else -r["ILSC_mean"]), reverse=True)
    for r in order[:2]:
        print("\n  --- %s (%s, expected %s, ILSC %.4f)"
              % (r["id"], r["title"][:40], r["expectation"], r["ILSC_mean"]))
        for op in r["_doc"]["operations"][:8]:
            print("      %-30s name=%s path=%s schemas=%s"
                  % (op["op_key"][:30], op["name_tokens"][:5],
                     op["path_tokens"][:5], op["domain_schemas"][:4]))


def dump_pairs(row):
    out = os.path.join(config.RESULTS_DIR, "gate1_pairs_%s.csv" % row["id"])
    rows = sim.pair_table(row["_opset"])
    cols = ["op_i", "op_j", "sim"] + list(sim.FEATURES) + ["m_" + f for f in sim.FEATURES]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: -x["sim"]):
            w.writerow(r)
    print("wrote %s (%d pairs)" % (out, len(rows)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run Gate 1.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--candidates",
                    default=os.path.join(config.RESULTS_DIR, "gate1_candidates.csv"))
    ap.add_argument("--out", default="sanity_check.csv")
    ap.add_argument("--tau", type=float, default=config.TAU_DEFAULT)
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--dump-pairs", default=None)
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

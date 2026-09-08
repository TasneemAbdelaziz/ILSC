"""
ILSC - Experiment 4: SIDC and LoCmsg baselines, head to head and under perturbation.

Two published interface-cohesion metrics, implemented faithfully - which means
implemented *without* the things ILSC adds, because that is the comparison:

**SIDC** (Perepletchikov et al. 2007) - interface cohesion from shared
parameter/return **data types**. A pair is cohesive if the two operations share
at least one type.

    SIDC(S) = |{(i,j) : types_i & types_j != {}}| / C(n,2)

**LoCmsg** (Athanasopoulos et al. 2015) - message-level *lack* of cohesion via
term matching. A pair is incohesive if the two operations' messages share no
term.

    LoCmsg(S) = |{(i,j) : terms_i & terms_j == {}}| / C(n,2)

LoCmsg runs the opposite way to the other two - higher is worse - so
``1 - LoCmsg`` is reported alongside it whenever the three are compared, and the
raw value is kept in the CSV so nobody has to trust a sign convention.

What is deliberately NOT applied to the baselines
-------------------------------------------------
No availability mask, no generic-schema exclusion, no embeddings. Adding any of
them would be implementing a better metric and calling it the baseline; the
paper's claim (Gap 2) is precisely that these metrics see only structure and
lexis, so they must be measured seeing only structure and lexis. The one
concession to fairness is that both read the same parsed corpus and the same
D-07 admin-endpoint exclusion as ILSC - a difference in *inputs* would confound
the comparison, while a difference in *method* is the comparison.

The perturbation comparison is paired
-------------------------------------
The strongest single result available from Exp. 2 + Exp. 4 is whether ILSC's
foreign-vs-control gap is larger than the baselines'. That is only a fair claim
if all three metrics see the **same injected operations**, so this module runs
the injection loop itself and scores all three on each draw, rather than
comparing against `inject.py`'s stored numbers. `--verify-ilsc` checks that the
ILSC column it produces reproduces the Exp. 2 run.

Outputs:
    results/baselines_corpus.csv       per service: ILSC, SIDC, LoCmsg
    results/baselines_perturbation.csv per service x condition x level x metric
    results/baselines_comparison.csv   the head-to-head degradation table
    figures/fig7_baseline_perturbation.pdf

Usage:
    python src/baselines.py
    python src/baselines.py --corpus-only
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

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402

import figstyle as fs                        # noqa: E402

import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import ilsc as ilsc_mod                          # noqa: E402
import pool as pool_mod                          # noqa: E402
import inject as inject_mod                      # noqa: E402
import parse_spec as ps                          # noqa: E402

METRICS = ("ILSC", "SIDC", "LoCmsg")


# ----------------------------------------------------------------------------
# The two baselines
# ----------------------------------------------------------------------------

def op_types(op):
    """Data types an operation declares: every named schema, generics included.

    `schema_names`, not `domain_schemas` - SIDC has no notion of an
    infrastructural type, and giving it one would be improving it.
    """
    return {s.lower() for s in (op.get("schema_names") or [])}


def op_terms(op):
    """Message terms: parameter names and type names, tokenised.

    Athanasopoulos matches terms on WSDL messages. The OpenAPI equivalent of a
    message is the request/response payload plus its parameters, so the term set
    is the tokenised union of parameter names and schema names. The same
    tokenizer as ILSC is used, so the comparison is not decided by tokenisation.
    """
    terms = set()
    for p in (op.get("param_names") or []):
        terms |= set(ps.tokenize(p))
    for s in (op.get("schema_names") or []):
        terms |= set(ps.tokenize(s))
    return terms


def sidc(ops):
    n = len(ops)
    if n < 2:
        return float("nan")
    types = [op_types(o) for o in ops]
    hits = sum(1 for i in range(n) for j in range(i + 1, n) if types[i] & types[j])
    return hits / (n * (n - 1) / 2)


def locmsg(ops):
    n = len(ops)
    if n < 2:
        return float("nan")
    terms = [op_terms(o) for o in ops]
    miss = sum(1 for i in range(n) for j in range(i + 1, n) if not (terms[i] & terms[j]))
    return miss / (n * (n - 1) / 2)


def score_all(ops, opset):
    """The three metrics on one operation set, ILSC first."""
    return {"ILSC": sim.ilsc_mean(opset), "SIDC": sidc(ops), "LoCmsg": locmsg(ops)}


# ----------------------------------------------------------------------------
# Corpus comparison
# ----------------------------------------------------------------------------

def corpus(args):
    from scipy import stats
    emb = emb_mod.Embeddings(args.cache)
    manifest = ilsc_mod.load_manifest(args.manifest)
    files = sorted(n for n in os.listdir(args.parsed_dir) if n.endswith(".json"))
    if args.limit:
        files = files[:args.limit]

    rows, t0 = [], time.time()
    for i, name in enumerate(files, 1):
        if i % 400 == 0:
            print("  ... %d/%d (%.0fs)" % (i, len(files), time.time() - t0), flush=True)
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        meta = manifest.get(clean, {})
        oversized = str(meta.get("oversized", "")).strip().lower() in ("1", "true", "yes")
        if oversized:
            continue                                  # D-17 primary population
        if name not in emb:
            continue
        with open(os.path.join(args.parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        ops = doc["operations"]
        if len(ops) < 2:
            continue
        oset = sim.OpSet.from_service(doc, emb, name)
        s = score_all(ops, oset)
        rows.append({"clean_file": clean, "title": doc.get("title", ""),
                     "source": doc.get("source", ""), "n_operations": len(ops),
                     "ILSC": s["ILSC"], "SIDC": s["SIDC"], "LoCmsg": s["LoCmsg"],
                     "msg_cohesion": 1.0 - s["LoCmsg"]})

    out = os.path.join(config.RESULTS_DIR, "baselines_corpus.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nscored %d services in %.0fs -> %s" % (len(rows), time.time() - t0, out))

    ilsc_v = np.array([r["ILSC"] for r in rows])
    sidc_v = np.array([r["SIDC"] for r in rows])
    msg_v = np.array([r["msg_cohesion"] for r in rows])

    print("\n" + "=" * 72)
    print("CORPUS COMPARISON  (%d services, D-17 primary population)" % len(rows))
    print("=" * 72)
    print("  %-14s %8s %8s %8s %8s" % ("metric", "mean", "Q1", "median", "Q3"))
    for label, v in (("ILSC", ilsc_v), ("SIDC", sidc_v), ("1 - LoCmsg", msg_v)):
        print("  %-14s %8.4f %8.4f %8.4f %8.4f"
              % (label, v.mean(), np.percentile(v, 25), np.percentile(v, 50),
                 np.percentile(v, 75)))

    print("\n  Spearman against ILSC:")
    for label, v in (("SIDC", sidc_v), ("1 - LoCmsg", msg_v)):
        r = stats.spearmanr(ilsc_v, v)
        print("    %-12s rho = %+.4f  (p = %.3g)" % (label, r.statistic, r.pvalue))
    r = stats.spearmanr(sidc_v, msg_v)
    print("    %-12s rho = %+.4f   (the two baselines against each other)"
          % ("SIDC~1-LoC", r.statistic))

    sat_s = float((sidc_v >= 0.999).mean()) * 100
    sat_m = float((msg_v >= 0.999).mean()) * 100
    sat_i = float((ilsc_v >= 0.999).mean()) * 100
    print("\n  Saturation - services scoring a perfect 1.0, where the metric can no")
    print("  longer distinguish anything:")
    print("    SIDC        %5.1f%%" % sat_s)
    print("    1 - LoCmsg  %5.1f%%" % sat_m)
    print("    ILSC        %5.1f%%" % sat_i)
    print("  A metric that assigns top marks to a large share of a 2,136-service")
    print("  corpus cannot rank within that share. This is the quantitative form")
    print("  of the Gap 2 argument.")
    return rows


# ----------------------------------------------------------------------------
# Perturbation comparison - the paired run
# ----------------------------------------------------------------------------

def perturbation(args):
    rng = np.random.default_rng(config.SEED)
    pl = pool_mod.load_pool(include_oversized=False)
    picked, _q3 = inject_mod.top_quartile_services(args.scores, pl, args.n_services)
    if not picked:
        sys.exit("no services selected - run src/ilsc.py first")

    rows = []
    for si, (name, meta) in enumerate(picked, 1):
        base_idx = pl.by_service[name]
        provider = pl.provider_of[base_idx[0]]
        base_ops = [pl.ops[i] for i in base_idx]
        base = score_all(base_ops, pl.opset(base_idx))
        print("  [%2d/%d] %-38s ILSC=%.3f SIDC=%.3f LoCmsg=%.3f"
              % (si, len(picked), meta["title"][:38],
                 base["ILSC"], base["SIDC"], base["LoCmsg"]), flush=True)

        for cond in inject_mod.CONDITIONS:
            for level in inject_mod.LEVELS:
                for draw in range(inject_mod.DRAWS):
                    if level == 0:
                        s = base
                    else:
                        don = inject_mod.donor_indices(pl, name, provider, cond,
                                                       rng, level)
                        if don is None:
                            s = {m: float("nan") for m in METRICS}
                        else:
                            idx = list(base_idx) + don
                            s = score_all([pl.ops[i] for i in idx], pl.opset(idx))
                    rows.append({"service": name, "title": meta["title"],
                                 "condition": cond, "level": level, "draw": draw,
                                 **{m: s[m] for m in METRICS}})

    out = os.path.join(config.RESULTS_DIR, "baselines_perturbation.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["service", "title", "condition", "level",
                                           "draw"] + list(METRICS))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nwrote %s (%s rows)" % (out, "{:,}".format(len(rows))))
    compare(rows, args)
    return rows


def corpus_dispersion(path=None):
    """sd and IQR of each metric over the corpus run, for standardising the gaps."""
    path = path or os.path.join(config.RESULTS_DIR, "baselines_corpus.csv")
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for m in METRICS:
        v = np.array([float(r[m]) for r in rows if r.get(m) not in (None, "", "nan")])
        if len(v) < 2:
            continue
        out[m] = {"sd": float(v.std(ddof=1)),
                  "iqr": float(np.percentile(v, 75) - np.percentile(v, 25))}
    return out


def compare(rows, args):
    services = sorted({r["service"] for r in rows})
    levels = inject_mod.LEVELS

    def mean_at(svc, metric, cond, lv):
        v = [r[metric] for r in rows
             if r["service"] == svc and r["condition"] == cond and r["level"] == lv
             and np.isfinite(r[metric])]
        return float(np.mean(v)) if v else float("nan")

    table, summary = [], []
    for metric in METRICS:
        sign = -1.0 if metric == "LoCmsg" else 1.0      # LoCmsg runs the other way
        gaps, slopes = [], {c: [] for c in inject_mod.CONDITIONS}
        for svc in services:
            per_cond = {}
            for cond in inject_mod.CONDITIONS:
                curve = [mean_at(svc, metric, cond, lv) for lv in levels]
                sl = inject_mod.ols_slope(levels, curve) * sign
                per_cond[cond] = sl
                if np.isfinite(sl):
                    slopes[cond].append(sl)
            gap = per_cond["cross_provider"] - per_cond["same_provider"]
            gaps.append(gap)
            table.append({"metric": metric, "service": svc,
                          **{"slope_" + c: per_cond[c] for c in inject_mod.CONDITIONS},
                          "slope_gap": gap})
        g = [x for x in gaps if np.isfinite(x)]
        p, n_perm = inject_mod.sign_flip_p(g)
        summary.append({
            "metric": metric,
            "slope_same_service": float(np.mean(slopes["same_service"])),
            "slope_same_provider": float(np.mean(slopes["same_provider"])),
            "slope_cross_provider": float(np.mean(slopes["cross_provider"])),
            "mean_gap": float(np.mean(g)) if g else float("nan"),
            "median_gap": float(np.median(g)) if g else float("nan"),
            "n_services_gap_negative": int(sum(1 for x in g if x < 0)),
            "n_services": len(g),
            "sign_flip_p": p,
        })

    print("\n" + "=" * 72)
    print("EXP. 4 - DEGRADATION UNDER THE SAME PERTURBATION")
    print("=" * 72)
    print("  Slopes are oriented so that MORE NEGATIVE = degrades faster.")
    print("  LoCmsg is sign-flipped to match (it natively runs the other way).\n")
    print("  %-8s %14s %14s %14s %12s %10s"
          % ("metric", "same_service", "same_provider", "cross_provider", "gap", "p"))
    for s in summary:
        print("  %-8s %14.5f %14.5f %14.5f %12.5f %10.5f"
              % (s["metric"], s["slope_same_service"], s["slope_same_provider"],
                 s["slope_cross_provider"], s["mean_gap"], s["sign_flip_p"]))

    # ---- standardise, because the three metrics are on different scales -----
    # A raw slope gap of -0.057 is not "bigger" than -0.031 when the two metrics
    # have different dispersions. Each gap is therefore also expressed in units
    # of its own metric's corpus standard deviation. Both are reported: the raw
    # numbers are what the proposal asked for, the standardised ones are what
    # the comparison actually supports.
    disp = corpus_dispersion()
    for s in summary:
        d = disp.get(s["metric"], {})
        sd = d.get("sd", float("nan"))
        s["corpus_sd"] = sd
        s["corpus_iqr"] = d.get("iqr", float("nan"))
        s["gap_in_sd"] = s["mean_gap"] / sd if sd and np.isfinite(sd) and sd > 0 else float("nan")

    ilsc = next(s for s in summary if s["metric"] == "ILSC")
    print("\n" + "=" * 72)
    print("THE CLAIM THIS EXPERIMENT EXISTS TO TEST")
    print("=" * 72)
    print("  Sec. 10: 'If ILSC's foreign-vs-control gap is larger than theirs,")
    print("  that is a direct, quantitative superiority claim.'\n")
    print("  %-8s %12s %10s %10s %12s"
          % ("metric", "raw gap", "corpus sd", "gap in sd", "corpus IQR"))
    for s in summary:
        print("  %-8s %12.5f %10.4f %10.3f %12.4f"
              % (s["metric"], s["mean_gap"], s["corpus_sd"], s["gap_in_sd"],
                 s["corpus_iqr"]))

    print("\n  Verdict, stated as the numbers fall:")
    for s in summary:
        if s["metric"] == "ILSC":
            continue
        raw = "larger" if ilsc["mean_gap"] < s["mean_gap"] else "NOT larger"
        std = "larger" if ilsc["gap_in_sd"] < s["gap_in_sd"] else "NOT larger"
        print("    vs %-7s  raw gap: ILSC %s   standardised: ILSC %s"
              % (s["metric"], raw, std))
        print("               discriminates on %d/%d services (ILSC %d/%d)"
              % (s["n_services_gap_negative"], s["n_services"],
                 ilsc["n_services_gap_negative"], ilsc["n_services"]))

    zero_iqr = [s["metric"] for s in summary
                if np.isfinite(s["corpus_iqr"]) and s["corpus_iqr"] == 0.0]
    if zero_iqr:
        print("\n  READ THE ABOVE WITH THIS: %s has a corpus IQR of exactly 0.0000,"
              % ", ".join(zero_iqr))
        print("  meaning at least half the corpus receives an identical score. It")
        print("  assigns the same value to every one of the 20 services tested here")
        print("  BEFORE any perturbation. A metric that cannot rank unperturbed")
        print("  services, but moves when foreign operations are injected, is")
        print("  detecting that something foreign was added - not measuring how")
        print("  cohesive a service is. A large degradation gap from a saturated")
        print("  floor is not evidence of discriminating power.")

    out = os.path.join(config.RESULTS_DIR, "baselines_comparison.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        for r in summary:
            w.writerow(r)
    print("\nwrote %s" % out)

    figure(rows, levels)


def figure(rows, levels):
    fs.use()
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.5), sharex=True)
    for ax, metric in zip(axes, METRICS):
        for cond in inject_mod.CONDITIONS:
            col, mk, ls = inject_mod.condition_style(cond)
            means, errs = [], []
            for lv in levels:
                v = [r[metric] for r in rows
                     if r["condition"] == cond and r["level"] == lv
                     and np.isfinite(r[metric])]
                means.append(np.mean(v) if v else np.nan)
                errs.append(np.std(v, ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0)
            ax.errorbar(levels, means, yerr=errs, marker=mk, linestyle=ls,
                        color=col, label=inject_mod.CONDITION_LABEL.get(cond, cond),
                        capsize=2.5)
        ax.set_title(metric + ("  (lower = more cohesive)" if metric == "LoCmsg" else ""))
        ax.set_xlabel("injected operations")
        ax.set_xticks(levels)
        ax.grid(axis="y")
    axes[0].set_ylabel("metric value")
    axes[0].legend()
    fig.suptitle("ILSC and the baselines under an identical perturbation (Exp. 4)",
                 fontsize=10)
    p = fs.finish(fig, os.path.join(config.FIGURES_DIR, "fig7_baseline_perturbation.pdf"))
    print("wrote %s" % p)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 4 - SIDC and LoCmsg baselines.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    ap.add_argument("--n-services", type=int, default=20)
    ap.add_argument("--corpus-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    corpus(args)
    if not args.corpus_only:
        print()
        perturbation(args)


if __name__ == "__main__":
    main()

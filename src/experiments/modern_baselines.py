"""
ILSC - D-35: CHM, CHD and LoCdom, the name-and-message metrics recent work uses.

**Why.** The 2026-10 literature review found no spec-only cohesion score newer
than these that works on meaning; later papers partition services instead. CHM
and CHD (Jin et al., TSE 2021, Eq. 7-11) are what those papers report, and
LoCdom (Athanasopoulos et al., TSC 2015, Def. 11) is where CHD comes from. They
are also the closest published relatives of ILSC, so ILSC has to beat them
before it can claim that embeddings add anything to name overlap.

**The port (fixed in D-35 before this script ran):**

    fmsg(k, m) = ( J(ret_k, ret_m) + J(par_k, par_m) ) / 2     -> CHM
    fdom(k, m) = J(fterm(k), fterm(m))                         -> CHD

    ret       response schema names
    par       parameter names + request-body schema names
    CHD_sig   fterm = operationId + path + parameter + schema terms (Jin's wording)
    CHD_name  fterm = operationId terms only (LoCdom's wording; = 1 - LoCdom)

J is Jaccard and J(empty, empty) = 0. Action terms are removed from fterm
(`config.BASELINE_ACTION_TERMS`). There is no mask and no D-26 exclusion: as in
D-28, a baseline is measured as published.

**Three tests:**

    corpus      primary population: spread, saturation, correlations
    boundaries  D-31's protocol on Train Ticket A1, A1+S1 and Sock Shop
    perturb     D-33's loop and draws (PYTHONHASHSEED=0), gap in corpus SD

Outputs:
    results/modern_baselines_corpus.csv
    results/modern_baselines_boundaries.csv
    results/modern_baselines_perturbation.csv

Usage:
    python src/experiments/modern_baselines.py [--selftest]
"""

import argparse
import csv
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # src/<group>/ -> repository root
sys.path.insert(0, _ROOT)
import srcpath  # noqa: E402,F401  - puts every src/<group>/ on sys.path

import config                                     # noqa: E402
import filter as flt                              # noqa: E402
import parse_spec as ps                           # noqa: E402
import similarity as sim                          # noqa: E402
import pool as pool_mod                           # noqa: E402
import inject as inject_mod                       # noqa: E402
import embed as emb_mod                           # noqa: E402
import bench_prepare as bp                        # noqa: E402
import dev_boundaries as db                       # noqa: E402
from size_mechanism import leaf_resources, spearman  # noqa: E402

METRICS = ("CHM", "CHD_sig", "CHD_name")
OUT_CORPUS = os.path.join(config.RESULTS_DIR, "modern_baselines_corpus.csv")
OUT_BOUND = os.path.join(config.RESULTS_DIR, "modern_baselines_boundaries.csv")
OUT_PERT = os.path.join(config.RESULTS_DIR, "modern_baselines_perturbation.csv")
D33_DRAWS = os.path.join(config.RESULTS_DIR, "resource_perturbation.csv")
D33_CMP = os.path.join(config.RESULTS_DIR, "resource_perturbation_comparison.csv")


# ----------------------------------------------------------------------------
# The metrics
# ----------------------------------------------------------------------------

def jaccard_matrix(sets):
    """n x n Jaccard of a list of sets; J(empty, empty) = 0, diagonal 0."""
    n = len(sets)
    vocab = {}
    rows, cols = [], []
    for i, s in enumerate(sets):
        for t in s:
            rows.append(i)
            cols.append(vocab.setdefault(t, len(vocab)))
    out = np.zeros((n, n), dtype="float64")
    if not vocab:
        return out
    m = np.zeros((n, len(vocab)), dtype="float64")
    m[rows, cols] = 1.0
    inter = m @ m.T
    size = m.sum(axis=1)
    union = size[:, None] + size[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(union > 0, inter / union, 0.0)
    np.fill_diagonal(out, 0.0)
    return out


def terms(words):
    return {w for w in words if w not in config.BASELINE_ACTION_TERMS}


def signature(op, ret, req, strip_path=None, strip_opid=None, strip_schema=None):
    """The sets one operation contributes to CHM and CHD."""
    opid = op.get("operation_id") if strip_opid is None else strip_opid
    path = op["path"] if strip_path is None else strip_path
    params = op.get("param_names") or []
    fix = strip_schema or (lambda s: s)
    ret = {fix(s) for s in ret}
    req = {fix(s) for s in req}
    name = terms(ps.tokenize(opid) if opid else [])
    sig = set(name) | terms(ps.normalize_path(path))
    for p in params:
        sig |= terms(ps.tokenize(p))
    for s in ret | req:
        sig |= terms(ps.tokenize(s))
    return {"ret": {s.lower() for s in ret},
            "par": {p.lower() for p in params} | {s.lower() for s in req},
            "name": name, "sig": sig}


def pair_matrices(sigs):
    return {"CHM": (jaccard_matrix([s["ret"] for s in sigs])
                    + jaccard_matrix([s["par"] for s in sigs])) / 2.0,
            "CHD_sig": jaccard_matrix([s["sig"] for s in sigs]),
            "CHD_name": jaccard_matrix([s["name"] for s in sigs])}


def service_scores(sigs):
    n = len(sigs)
    if n < 2:
        return {m: 1.0 for m in METRICS}                # Jin Eq. 7 and 10
    iu = np.triu_indices(n, 1)
    return {k: float(W[iu].mean()) for k, W in pair_matrices(sigs).items()}


# ----------------------------------------------------------------------------
# Reading ret / req from the converted specifications
# ----------------------------------------------------------------------------

def raw_messages(spec, doc):
    """{(METHOD, path): (ret, req)} for a parsed document, from its 3.x spec."""
    res = ps.Resolver(spec)
    paths = spec.get("paths") or {}
    out = {}
    for o in doc["operations"]:
        item = paths.get(o["path"]) or {}
        op = next((v for k, v in item.items() if k.lower() == o["method"].lower()), None)
        if not isinstance(op, dict):
            out[(o["method"], o["path"])] = (set(), set())
            continue
        out[(o["method"], o["path"])] = (ps.response_schemas(op, res), ps.request_schemas(op, res))
    return out


def load_corpus(parsed_dir, specs_dir, manifest):
    """{parsed name: [signature per operation]} for the primary population."""
    import ilsc as ilsc_mod
    out, sizes = {}, {}
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    for i, name in enumerate(files, 1):
        if i % 500 == 0:
            print("  ... %d/%d" % (i, len(files)), flush=True)
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        if str(manifest.get(clean, {}).get("oversized", "")).strip().lower() in ("1", "true", "yes"):
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        spec, _reason = flt.load_spec(os.path.join(specs_dir, name))
        msgs = raw_messages(spec or {}, doc)
        sigs = {}
        for o in doc["operations"]:
            ret, req = msgs.get((o["method"], o["path"]), (set(), set()))
            sigs[o["op_key"]] = signature(o, ret, req)
        out[name] = sigs
        sizes[name] = (clean, [o["path"] for o in doc["operations"]])
    return out, sizes


# ----------------------------------------------------------------------------
# Test 1: corpus
# ----------------------------------------------------------------------------

def corpus_test(sigs, sizes):
    scores = {}
    with open(os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            scores[r["clean_file"]] = float(r["ILSC_mean"])
    rows = []
    for name, per in sigs.items():
        clean, paths = sizes[name]
        s = service_scores(list(per.values()))
        rows.append({"clean_file": clean, "n_operations": len(per),
                     "n_resources": len(set(leaf_resources(paths))),
                     "ILSC_mean": scores.get(clean, float("nan")), **s})
    with open(OUT_CORPUS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\ncorpus: %d services" % len(rows))
    print("%-9s %7s %7s %7s %7s %7s %9s %9s %9s %9s"
          % ("metric", "mean", "Q1", "median", "Q3", "IQR", "at>=.999", "rho ILSC", "rho size", "rho res"))
    sds = {}
    v_ilsc = [r["ILSC_mean"] for r in rows]
    v_n = [r["n_operations"] for r in rows]
    v_res = [r["n_resources"] for r in rows]
    for m in METRICS + ("ILSC_mean",):
        v = np.array([r[m] for r in rows], dtype=float)
        sds[m] = float(v.std(ddof=1))
        q1, q2, q3 = np.percentile(v, [25, 50, 75])
        print("%-9s %7.3f %7.3f %7.3f %7.3f %7.3f %8.1f%% %9.3f %9.3f %9.3f"
              % (m, v.mean(), q1, q2, q3, q3 - q1, float((v >= 0.999).mean()) * 100,
                 spearman(list(v), v_ilsc), spearman(list(v), v_n), spearman(list(v), v_res)))
    return sds


# ----------------------------------------------------------------------------
# Test 2: developer boundaries
# ----------------------------------------------------------------------------

def bench_messages(system):
    """{"service METHOD path": (ret, req)} from the converted benchmark specs."""
    out = {}
    for name in sorted(os.listdir(bp.BENCH_PARSED)):
        if not (name.startswith(system + "__") and name.endswith(".json")):
            continue
        with open(os.path.join(bp.BENCH_PARSED, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        spec, _r = flt.load_spec(os.path.join(bp.BENCH3_DIR, name))
        for (m, p), v in raw_messages(spec or {}, doc).items():
            out["%s %s %s" % (doc["service"], m, p)] = v
    return out


def condition_sigs(ops, system, strip, wrappers):
    msgs = bench_messages(system)
    fix = (lambda s: db.OPID_PREFIX.sub("", s)) if strip == "all" else None
    out = []
    for o in ops:
        ret, req = msgs[o["op_key"]]
        ret, req = {s for s in ret if s not in wrappers}, {s for s in req if s not in wrappers}
        out.append(signature(o, ret, req, strip_path=o["path"],
                             strip_opid=o.get("operation_id"), strip_schema=fix))
    return out


def boundaries_test(seed):
    tt = db.load_system(bp.BENCH_PARSED, "trainticket")
    ss = db.load_system(bp.BENCH_PARSED, "sockshop")
    wr = db.load_wrappers("trainticket")
    conds = (("trainticket", "A1_amended", tt, "all", frozenset()),
             ("trainticket", "A1_S1_no_wrapper", tt, "all", wr),
             ("sockshop", "primary", ss, None, frozenset()))
    texts = set()
    for _s, _n, subset, strip, wrap in conds:
        ops = db.build_ops(subset, strip, wrap)[0]
        texts |= {o["T"] for o in ops} | {o["description"] for o in ops if o["description"]}
    texts = sorted(texts)
    vec = dict(zip(texts, emb_mod.embed_texts(texts, "D-35")))

    out = []
    for system, name, subset, strip, wrap in conds:
        ops, services, _l, _xs, _xp = db.build_ops(subset, strip, wrap)
        mats, res = db.predictors(ops, vec, f1_only=True)
        mats.update(pair_matrices(condition_sigs(ops, system, strip, wrap)))
        iu = np.triu_indices(len(ops), 1)
        r = np.array(res)
        same_res = r[iu[0]] == r[iu[1]]
        for stratum, keep in (("all", None), ("diff_resource", ~same_res),
                              ("same_resource", same_res)):
            point, boots, n_pos, n_neg = db.evaluate(mats, services, seed, keep)
            if n_pos == 0 or n_neg == 0:                # an empty stratum, as in E2
                continue
            base = {"system": system, "condition": name, "stratum": stratum,
                    "n_pos": n_pos, "n_neg": n_neg}
            for k in ("ILSC", "f1_only", "resource_pair", "CHM", "CHD_sig", "CHD_name"):
                lo, hi = db.interval(boots[k])
                out.append(dict(base, kind="auc", predictor=k, value=round(point[k], 6),
                                lo=round(lo, 6), hi=round(hi, 6),
                                reading="above chance" if lo > 0.5 else
                                        "below chance" if hi < 0.5 else "chance"))
            for a in ("ILSC", "f1_only"):
                for b in METRICS:
                    lo, hi = db.interval(boots[a] - boots[b])
                    out.append(dict(base, kind="diff", predictor="%s - %s" % (a, b),
                                    value=round(point[a] - point[b], 6),
                                    lo=round(lo, 6), hi=round(hi, 6),
                                    reading="%s better" % a if lo > 0 else
                                            "%s worse" % a if hi < 0 else "indistinguishable"))
    with open(OUT_BOUND, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print()
    print("%-30s %-14s %-24s %7s %17s  %s"
          % ("system / condition", "stratum", "predictor", "value", "95% CI", "reading"))
    for x in out:
        print("%-30s %-14s %-24s %7.3f %17s  %s"
              % (x["system"] + " / " + x["condition"], x["stratum"], x["predictor"], x["value"],
                 "[%.3f, %.3f]" % (x["lo"], x["hi"]), x["reading"]))


# ----------------------------------------------------------------------------
# Test 3: perturbation, on D-33's draws
# ----------------------------------------------------------------------------

def perturbation_test(sigs, sds, scores_path, n_services=20):
    rng = np.random.default_rng(config.SEED)
    pl = pool_mod.load_pool(include_oversized=False)
    picked, _q3 = inject_mod.top_quartile_services(scores_path, pl, n_services)
    with open(D33_DRAWS, newline="", encoding="utf-8") as fh:
        ref = {(r["service"], r["condition"], int(r["level"]), int(r["draw"])): r["ILSC"]
               for r in csv.DictReader(fh)}

    def sig_of(i):
        return sigs[pl.service_of[i]][pl.ops[i]["op_key"]]

    rows, worst = [], 0.0
    for si, (name, meta) in enumerate(picked, 1):
        base_idx = pl.by_service[name]
        provider = pl.provider_of[base_idx[0]]
        base = {"ILSC": sim.ilsc_mean(pl.opset(base_idx)),
                **service_scores([sig_of(i) for i in base_idx])}
        print("  [%2d/%d] %s" % (si, len(picked), meta["title"][:40]), flush=True)
        for cond in inject_mod.CONDITIONS:
            for level in inject_mod.LEVELS:
                for draw in range(inject_mod.DRAWS):
                    if level == 0:
                        s = base
                    else:
                        don = inject_mod.donor_indices(pl, name, provider, cond, rng, level)
                        if don is None:
                            s = {m: float("nan") for m in ("ILSC",) + METRICS}
                        else:
                            idx = list(base_idx) + don
                            s = {"ILSC": sim.ilsc_mean(pl.opset(idx)),
                                 **service_scores([sig_of(i) for i in idx])}
                    v = ref.get((name, cond, level, draw))
                    if v not in (None, "", "nan") and np.isfinite(s["ILSC"]):
                        worst = max(worst, abs(float(v) - s["ILSC"]))
                    rows.append({"service": name, "condition": cond, "level": level,
                                 "draw": draw, **s})
    print("ILSC against D-33's stored draws: max |diff| = %.2e" % worst)
    if worst > 1e-9:
        sys.exit("draws do NOT match D-33 - stopping")

    services = sorted({r["service"] for r in rows})
    levels = inject_mod.LEVELS

    def mean_at(svc, metric, cond, lv):
        v = [r[metric] for r in rows if r["service"] == svc and r["condition"] == cond
             and r["level"] == lv and np.isfinite(r[metric])]
        return float(np.mean(v)) if v else float("nan")

    summary = []
    for m in ("ILSC",) + METRICS:
        gaps = []
        for svc in services:
            sl = {c: inject_mod.ols_slope(levels, [mean_at(svc, m, c, lv) for lv in levels])
                  for c in inject_mod.CONDITIONS}
            gaps.append(sl["cross_provider"] - sl["same_provider"])
        g = [x for x in gaps if np.isfinite(x)]
        p, _n = inject_mod.sign_flip_p(g)
        sd = sds["ILSC_mean" if m == "ILSC" else m]
        summary.append({"metric": m, "mean_gap": float(np.mean(g)), "corpus_sd": sd,
                        "gap_in_sd": float(np.mean(g)) / sd if sd > 0 else float("nan"),
                        "n_services_gap_negative": sum(1 for x in g if x < 0),
                        "n_services": len(g), "sign_flip_p": p})
    with open(OUT_PERT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print()
    print("%-9s %9s %8s %7s %9s" % ("metric", "gap", "gap/SD", "neg", "p"))
    for s in summary:
        print("%-9s %9.4f %8.3f %4d/%-2d %9.2g"
              % (s["metric"], s["mean_gap"], s["gap_in_sd"], s["n_services_gap_negative"],
                 s["n_services"], s["sign_flip_p"]))
    print("(D-33, same draws: see %s)" % os.path.basename(D33_CMP))


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def selftest():
    a = {"cart"}
    W = jaccard_matrix([a, {"cart", "item"}, set(), set()])
    assert abs(W[0, 1] - 0.5) < 1e-12 and W[2, 3] == 0.0 and W[0, 2] == 0.0
    assert ps.tokenize("deleteOrderUsingDELETE") == ["delete", "order", "using", "delete"]
    o = {"operation_id": "deleteOrderUsingDELETE", "path": "/orders/{id}",
         "param_names": ["orderId"]}
    s = signature(o, {"Order"}, set())
    assert s["name"] == {"order"}, s
    assert s["sig"] >= {"order", "orders", "id"}, s
    assert s["par"] == {"orderid"} and s["ret"] == {"order"}, s
    # one pair by hand: CHM = (J(ret) + J(par)) / 2 = (1/2 + 0) / 2
    x = signature({"operation_id": "getA", "path": "/a", "param_names": ["p"]}, {"A", "B"}, set())
    y = signature({"operation_id": "getB", "path": "/b", "param_names": ["q"]}, {"A"}, set())
    assert abs(pair_matrices([x, y])["CHM"][0, 1] - 0.25) < 1e-12
    assert abs(service_scores([x, y])["CHM"] - 0.25) < 1e-12
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description="D-35: CHM, CHD, LoCdom ported to OpenAPI.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scores", default=os.path.join(config.RESULTS_DIR, "ilsc_scores.csv"))
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":       # F-08: the same draws as D-33
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))

    import ilsc as ilsc_mod
    manifest = ilsc_mod.load_manifest(os.path.join(config.RESULTS_DIR, "manifest.csv"))
    print("reading the corpus ...", flush=True)
    sigs, sizes = load_corpus(config.PARSED_DIR, config.SPECS_CLEAN3, manifest)
    sds = corpus_test(sigs, sizes)
    boundaries_test(config.SEED)
    perturbation_test(sigs, sds, args.scores)
    print("\nwrote %s\n      %s\n      %s" % (OUT_CORPUS, OUT_BOUND, OUT_PERT))


if __name__ == "__main__":
    main()

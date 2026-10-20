"""
ILSC - D-31: do pairwise similarities recover the developers' service boundaries?

**The question.** Read Train Ticket as one API of 211 operations. Its developers
split those operations into 34 services. If ILSC's pairwise similarity measures
what belongs together, pairs the developers placed in one service should score
above pairs they placed in different services - and the reference is theirs, not
ours (D-30). Every design choice below was fixed in D-31 before this script
existed; nothing here is tuned.

**Service identity is removed first (F-06).** Every Train Ticket path begins
``/api/v1/<name>service`` and 203 of 211 operationIds begin
``ts-<name>-service.``. Left in, f1, f2 and f3 would read the answer and the test
would pass by construction. Both prefixes are stripped before any token is made,
and every removal is logged.

**Per-service rules become system rules.** D-26's frequent-schema and
frequent-parameter exclusions, and the generic-schema list, are recomputed with
the whole system as the denominator. Computing them per service would feed the
service split into the predictor.

Predictors (pair level):
    ILSC            Sim, six features, availability mask, weights 1/6
    ILSC_no_f2f3    robustness: f2 and f3 weighted 0, the mask renormalises
    SIDC_pair       1 if the two operations share >= 1 data type     (D-28)
    LoCmsg_pair     1 if their message terms intersect               (D-28)
    resource_pair   1 if the first non-parameter segment of the stripped
                    path is the same

Statistics:
    AUC, positive = same service, with a dyadic cluster bootstrap over services
    (2,000 resamples, seed 42). A within-service pair is weighted by its
    service's multiplicity in the resample, a cross-service pair by the product
    of its two services' multiplicities; pairs between two copies of one service
    are not formed. Differences AUC_ILSC - AUC_X use the same resamples.
    Verdict per baseline: better / worse if the 95% interval of the difference
    lies wholly above / below 0, otherwise indistinguishable.
    Secondary: Louvain (seed 42) on each predictor's pair graph, ARI and NMI
    against the developer split.

Conditions:
    trainticket / primary       prefixes stripped, all 211 operations (derived)
    trainticket / no_greeting   sensitivity: stripped /welcome and /hello excluded
    trainticket / unstripped    F-06 diagnostic only, not a result
    sockshop    / primary       27 operations, five developer-written files
                                (independent); no identity removal - its paths
                                name resources, not a deployment prefix
    sockshop    / sun2022       Sun et al.'s own partition of Sock Shop
                                (MsDecomposer result/SockShop1.json), matched to
                                ours by method + path, beside ILSC's Louvain
                                partition scored on the same matched operations

Outputs:
    results/dev_boundaries.csv              condition x predictor
    results/dev_boundaries_strip_log.csv    every prefix removal (amended run A1)
    data/benchmarks/d31_cleaned/            every condition's exact inputs, the
                                            operation table and the full removal
                                            log (see its README.md)

Usage:
    python src/pipeline/bench_prepare.py             (once: convert + parse the benchmarks)
    python src/experiments/dev_boundaries.py
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # src/<group>/ -> repository root
sys.path.insert(0, _ROOT)

import srcpath  # noqa: E402,F401  - puts every src/<group>/ on sys.path
import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import parse_spec as ps                          # noqa: E402
import similarity as sim                         # noqa: E402
import baselines as bl                           # noqa: E402
import bench_prepare as bp                       # noqa: E402
from graph_structure import louvain, ari, nmi    # noqa: E402

PATH_PREFIX = re.compile(r"^/api/v1/[^/]+")
OPID_PREFIX = re.compile(r"^ts-[a-z0-9-]+-service\.")
GREETING = re.compile(r"^/(welcome|hello)/?$", re.IGNORECASE)
N_BOOT = 2000
SUN_RESULT = os.path.join(config.MSDECOMPOSER_DIR, "result", "SockShop1.json")

OUT_CSV = os.path.join(config.RESULTS_DIR, "dev_boundaries.csv")
STRIP_LOG = os.path.join(config.RESULTS_DIR, "dev_boundaries_strip_log.csv")


# ----------------------------------------------------------------------------
# Load and strip
# ----------------------------------------------------------------------------

def load_system(parsed_dir, system):
    """(service, raw operation record) for every operation of one system."""
    out = []
    prefix = system + "__"
    for name in sorted(os.listdir(parsed_dir)):
        if not (name.startswith(prefix) and name.endswith(".json")):
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        for op in doc["operations"]:
            out.append((doc["service"], op))
    if not out:
        sys.exit("no %s services in %s - run src/pipeline/bench_prepare.py first" % (system, parsed_dir))
    return out


def strip_identity(service, op, schemas=False):
    """D-31 item 1 (paths, operationIds) and, with ``schemas``, amendment A1.

    Returns (path, operation_id, schema_names, log row).
    """
    path, opid = op["path"], op.get("operation_id")
    names = list(op.get("schema_names") or [])
    m = PATH_PREFIX.match(path)
    if not m:
        raise AssertionError("%s %s does not begin /api/v1/<segment>" % (service, path))
    new_path = path[m.end():] or "/"
    new_opid = OPID_PREFIX.sub("", opid) if opid else opid
    new_names = sorted({OPID_PREFIX.sub("", s) for s in names}) if schemas else names
    return new_path, new_opid, new_names, {
        "service": service, "method": op["method"],
        "path": path, "path_stripped": new_path,
        "operation_id": opid or "", "operation_id_stripped": new_opid or "",
        "opid_prefix_removed": int(bool(opid) and new_opid != opid),
        "schema_names": "|".join(names), "schema_names_stripped": "|".join(new_names),
        "schema_prefixes_removed": sum(1 for s in names if OPID_PREFIX.match(s)) if schemas else 0,
    }


def load_wrappers(system):
    """S1: schemas whose declared properties are only framework HTTP-wrapper fields."""
    out = set()
    for name in sorted(os.listdir(bp.BENCH3_DIR)):
        if not (name.startswith(system + "__") and name.endswith(".json")):
            continue
        with open(os.path.join(bp.BENCH3_DIR, name), encoding="utf-8") as fh:
            spec = json.load(fh)
        for key, schema in ((spec.get("components") or {}).get("schemas") or {}).items():
            props = {p.lower() for p in ((schema or {}).get("properties") or {})}
            if props and props <= config.FRAMEWORK_WRAPPER_FIELDS:
                out.add(key)
    return out


def resource_of(path):
    for seg in path.split("/"):
        seg = seg.strip()
        if seg and not (seg.startswith("{") and seg.endswith("}")):
            return seg.lower()
    return "<root>"


def build_ops(items, strip, wrappers=frozenset()):
    """Operation records with D-26's rules applied over the whole system.

    ``strip``: None, "path_opid" (D-31 item 1) or "all" (item 1 + amendment A1).
    ``wrappers``: schema names dropped for every predictor (sensitivity S1).
    """
    n = len(items)
    rows, log = [], []
    for service, op in items:
        kept = [s for s in (op.get("schema_names") or []) if s not in wrappers]
        if strip:
            path, opid, names, entry = strip_identity(service, dict(op, schema_names=kept),
                                                      schemas=(strip == "all"))
            log.append(entry)
        else:
            path, opid, names = op["path"], op.get("operation_id"), kept
        rows.append((service, op, path, opid, names))

    sfreq, pfreq = {}, {}
    for _s, op, _p, _o, names in rows:
        for s in set(names):
            sfreq[s] = sfreq.get(s, 0) + 1
        for p in set(op.get("param_names") or []):
            pfreq[p] = pfreq.get(p, 0) + 1
    excl_s = {s for s, c in sfreq.items() if c / n > config.FREQUENT_SCHEMA_RATIO}
    excl_s |= {s for s in sfreq if s.lower() in config.GENERIC_SCHEMAS}
    excl_p = {p for p, c in pfreq.items() if c / n > config.FREQUENT_PARAM_RATIO}

    ops, services = [], []
    for service, op, path, opid, names in rows:
        domain_schemas = sorted(s for s in names if s not in excl_s)
        domain_params = sorted(p for p in (op.get("param_names") or []) if p not in excl_p)
        name_tokens = ps.tokenize(opid) if opid else []
        path_tokens = ps.normalize_path(path)
        param_tokens = sorted({t for p in domain_params for t in ps.tokenize(p)})
        schema_tokens = sorted({t for s in domain_schemas for t in ps.tokenize(s)})
        ops.append({
            "op_key": "%s %s %s" % (service, op["method"], op["path"]),
            "method": op["method"], "path": path, "operation_id": opid,
            "param_names": op.get("param_names") or [],
            "schema_names": names,
            "domain_schemas": domain_schemas,
            "name_tokens": name_tokens, "path_tokens": path_tokens,
            "param_tokens": param_tokens,
            "description": op.get("description"),
            "T": ps.build_T(op["method"], name_tokens, path_tokens, param_tokens, schema_tokens),
        })
        services.append(service)
    return ops, services, log, sorted(excl_s), sorted(excl_p)


# ----------------------------------------------------------------------------
# Predictors
# ----------------------------------------------------------------------------

def sim_matrix(oset, weights=None):
    n = oset.n
    W = np.zeros((n, n), dtype="float64")
    for i0, i1, s, _per, _mask in sim.pair_blocks(oset, weights=weights):
        W[i0:i1, :] = s
    W = (W + W.T) / 2.0
    np.fill_diagonal(W, 0.0)
    return W


def binary_matrix(sets):
    n = len(sets)
    W = np.zeros((n, n), dtype="float64")
    for i in range(n):
        for j in range(i + 1, n):
            if sets[i] & sets[j]:
                W[i, j] = W[j, i] = 1.0
    return W


def predictors(ops, vec, f1_only=False):
    T = np.vstack([vec[o["T"]] for o in ops])
    D = np.zeros_like(T)
    for i, o in enumerate(ops):
        if o["description"]:
            D[i] = vec[o["description"]]
    oset = sim.OpSet(ops, T, D)
    w_no = np.array(sim.DEFAULT_WEIGHTS, dtype="float64")
    w_no[1] = w_no[2] = 0.0
    res = [resource_of(o["path"]) for o in ops]
    W_res = np.array([[1.0 if (i != j and res[i] == res[j]) else 0.0
                       for j in range(len(ops))] for i in range(len(ops))])
    mats = {
        "ILSC": sim_matrix(oset),
        "ILSC_no_f2f3": sim_matrix(oset, weights=w_no),
        "SIDC_pair": binary_matrix([bl.op_types(o) for o in ops]),
        "LoCmsg_pair": binary_matrix([bl.op_terms(o) for o in ops]),
        "resource_pair": W_res,
    }
    if f1_only:                                   # exploratory E1 only
        mats["f1_only"] = sim_matrix(oset, weights=[1.0, 0, 0, 0, 0, 0])
    return mats, res


# ----------------------------------------------------------------------------
# AUC with the dyadic cluster bootstrap
# ----------------------------------------------------------------------------

class SortedScores:
    """One predictor's pair scores, sorted once; AUC under any pair weights."""

    def __init__(self, scores, same):
        self.order = np.argsort(scores, kind="mergesort")
        s = scores[self.order]
        self.gid = np.concatenate([[0], np.cumsum(s[1:] != s[:-1])])
        self.G = int(self.gid[-1]) + 1
        self.pos = same[self.order]

    def auc(self, w):
        w = w[self.order]
        P = np.bincount(self.gid, weights=w * self.pos, minlength=self.G)
        N = np.bincount(self.gid, weights=w * ~self.pos, minlength=self.G)
        below = np.cumsum(N) - N
        den = P.sum() * N.sum()
        return float((P * (below + 0.5 * N)).sum() / den) if den > 0 else float("nan")


def pair_arrays(services):
    ids = {s: k for k, s in enumerate(sorted(set(services)))}
    sid = np.array([ids[s] for s in services])
    iu = np.triu_indices(len(services), 1)
    si, sj = sid[iu[0]], sid[iu[1]]
    return iu, si, sj, si == sj, len(ids)


def evaluate(mats, services, seed, keep=None):
    """AUCs and bootstrap draws; ``keep`` restricts to a subset of pairs (E2)."""
    iu, si, sj, same, S = pair_arrays(services)
    if keep is None:
        keep = np.ones(len(si), dtype=bool)
    si, sj, same = si[keep], sj[keep], same[keep]
    scorers = {k: SortedScores(W[iu][keep], same) for k, W in mats.items()}
    ones = np.ones(len(si))
    point = {k: sc.auc(ones) for k, sc in scorers.items()}

    rng = np.random.default_rng(seed)
    boots = {k: [] for k in mats}
    for _ in range(N_BOOT):
        c = np.bincount(rng.integers(0, S, size=S), minlength=S).astype("float64")
        w = np.where(same, c[si], c[si] * c[sj])
        for k, sc in scorers.items():
            boots[k].append(sc.auc(w))
    boots = {k: np.array(v) for k, v in boots.items()}
    return point, boots, int(same.sum()), int((~same).sum())


def interval(x):
    x = x[np.isfinite(x)]
    return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def run_condition(system, origin, name, items, strip, wrappers, vec, seed, partitions=True):
    ops, services, log, excl_s, excl_p = build_ops(items, strip, wrappers)
    mats, res = predictors(ops, vec)
    point, boots, n_pos, n_neg = evaluate(mats, services, seed)
    rows, ilsc_labels = [], None
    for k in mats:
        lo, hi = interval(boots[k])
        row = {"system": system, "spec_origin": origin,
               "condition": name, "predictor": k, "n_operations": len(ops),
               "n_services": len(set(services)), "n_pos": n_pos, "n_neg": n_neg,
               "auc": round(point[k], 6), "auc_lo": round(lo, 6), "auc_hi": round(hi, 6),
               "diff_ilsc_minus": "", "diff_lo": "", "diff_hi": "", "verdict": "",
               "louvain_k": "", "ari": "", "nmi": ""}
        if k != "ILSC":
            d = boots["ILSC"] - boots[k]
            dlo, dhi = interval(d)
            row.update({"diff_ilsc_minus": round(point["ILSC"] - point[k], 6),
                        "diff_lo": round(dlo, 6), "diff_hi": round(dhi, 6),
                        "verdict": ("ILSC better" if dlo > 0 else
                                    "ILSC worse" if dhi < 0 else "indistinguishable")})
        if partitions:
            if k == "resource_pair":
                labels = res
                row["louvain_k"] = len(set(res))
            else:
                kk, _q, labels = louvain(mats[k], seed)
                row["louvain_k"] = kk
                if k == "ILSC":
                    ilsc_labels = list(labels)
            row["ari"] = round(ari(list(labels), services), 6)
            row["nmi"] = round(nmi(list(labels), services), 6)
        rows.append(row)
    return rows, log, excl_s, excl_p, (ops, services, ilsc_labels)


def sun_rows(ops, services, ilsc_labels):
    """D-31 item 14: Sun et al.'s Sock Shop partition beside ILSC's, same operations."""
    with open(SUN_RESULT, encoding="utf-8") as fh:
        clusters = json.load(fh)
    sun = {}
    for cid, members in clusters.items():
        for m in members:
            method, _, path = str(m).strip().partition(" ")
            sun[(method.upper(), path.strip())] = cid
    keys = [(o["method"].upper(), o["path"]) for o in ops]
    idx = [i for i, k in enumerate(keys) if k in sun]
    dev = [services[i] for i in idx]
    base = {"system": "sockshop", "spec_origin": "independent", "condition": "sun2022",
            "n_operations": len(idx), "n_services": len(set(dev)), "n_pos": "", "n_neg": "",
            "auc": "", "auc_lo": "", "auc_hi": "", "diff_ilsc_minus": "", "diff_lo": "",
            "diff_hi": "", "verdict": ""}
    out = []
    for name, labels in (("Sun_et_al_2022", [sun[keys[i]] for i in idx]),
                         ("ILSC_matched", [ilsc_labels[i] for i in idx])):
        out.append(dict(base, predictor=name, louvain_k=len(set(labels)),
                        ari=round(ari(labels, dev), 6), nmi=round(nmi(labels, dev), 6)))
    unmatched_ours = len(ops) - len(idx)
    unmatched_sun = len(set(sun) - set(keys))
    return out, unmatched_ours, unmatched_sun


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

EXPL_CSV = os.path.join(config.RESULTS_DIR, "dev_boundaries_exploratory.csv")
DATA_DIR = os.path.join(config.ROOT, "data", "benchmarks", "d31_cleaned")

DATA_README = """# D-31 datasets - the exact inputs of every condition

Written by `python src/experiments/dev_boundaries.py` (or `--dataset` for this folder alone).
Nothing here is edited by hand; re-running reproduces every file.

| file | what it holds |
|---|---|
| `operations.csv` | all 238 operations (Train Ticket 211, Sock Shop 27): the original path, operationId and schema names beside their cleaned forms (A1), the schema names after S1, and whether the operation is a greeting endpoint |
| `removed.csv` | every removal, one row each: service-name prefixes (path, operationId, schema name), framework wrappers (S1) and greeting endpoints, with the conditions each one applies to |
| `<system>__<condition>.json` | the operation records one condition feeds its predictors, after every removal, with the condition's settings and D-26's system-level exclusions in the header |

Conditions, as recorded in `docs/DECISIONS.md` D-31:

- `trainticket__primary`: pre-registered; path and operationId prefixes removed
- `trainticket__no_greeting`: pre-registered sensitivity
- `trainticket__unstripped`: F-06 diagnostic; nothing removed
- `trainticket__A1_amended`: amendment A1; schema-name prefixes removed too
- `trainticket__A1_no_greeting`: A1 without the 26 greeting endpoints
- `trainticket__A1_S1_no_wrapper`: A1 plus sensitivity S1, framework wrappers dropped
- `sockshop__primary`: nothing removed; Sock Shop carries no service-name prefix
- `sockshop__S1_no_wrapper`: identical to `sockshop__primary`, since S1 matches nothing there

D-26's frequent-schema and frequent-parameter rules are part of the metric, not
a data removal. They are applied inside the predictors, and each JSON header
lists what they excluded.

**Provenance.**
- Train Ticket comes from the replication package of Mazhar, Wang and Mantyla
  (ISSRE 2026), Zenodo 10.5281/zenodo.21342161, CC-BY-4.0. See
  `data/benchmarks/specs/trainticket/README.md`.
- Sock Shop comes from github.com/microservices-demo, Apache-2.0.
- Sun et al.'s MsDecomposer data has no licence and is **not** copied here.
"""


def write_dataset(plan, systems):
    """Write DATA_DIR: per-condition inputs, the operation table, the removal log.

    ``systems`` maps each system to its full operation list, in load order.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    removed, table = [], []
    wrappers = {}
    for system, origin, name, subset, strip, wrap, _parts in plan:
        ops, services, _log, excl_s, excl_p = build_ops(subset, strip, wrap)
        wrappers.setdefault(system, set()).update(wrap)
        doc = {
            "system": system, "condition": name, "spec_origin": origin,
            "strip": strip or "none",
            "s1_wrappers_removed": sorted(wrap),
            "d26_excluded_schemas": excl_s, "d26_excluded_params": excl_p,
            "n_operations": len(ops), "n_services": len(set(services)),
            "operations": [{
                "service": s, "op_key": o["op_key"], "method": o["method"],
                "path": o["path"], "operation_id": o["operation_id"],
                "param_names": o["param_names"], "schema_names": o["schema_names"],
                "description": o["description"],
            } for s, o in zip(services, ops)],
        }
        with open(os.path.join(DATA_DIR, "%s__%s.json" % (system, name)), "w",
                  encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)

    for system, items in systems.items():
        wr = wrappers.get(system, set())
        # D-07's administrative endpoints never reach the parsed documents; list
        # them here so the folder accounts for every operation of the source specs
        parsed = {(s, o["method"].upper(), o["path"]) for s, o in items}
        for _sys, service, src in bp.spec_files(system):
            spec, _err = bp.flt.load_spec(src)
            for method, path in sorted(bp.flt.operations(spec, drop_admin=False)[0]):
                if (service, method.upper(), path) not in parsed:
                    removed.append({"system": system, "service": service,
                                    "method": method.upper(), "path": path,
                                    "removal": "admin_endpoint (D-07)", "original": path,
                                    "after": "", "applies_to": "all conditions"})
        for service, op in items:
            names = list(op.get("schema_names") or [])
            row = {"system": system, "service": service, "method": op["method"],
                   "path": op["path"], "operation_id": op.get("operation_id") or "",
                   "param_names": "|".join(op.get("param_names") or []),
                   "schema_names": "|".join(names)}
            key = {"system": system, "service": service, "method": op["method"],
                   "path": op["path"]}
            if system == "trainticket":
                path, opid, clean, _e = strip_identity(service, op, schemas=True)
                _p, _o, clean_nw, _e = strip_identity(
                    service, dict(op, schema_names=[s for s in names if s not in wr]),
                    schemas=True)
                greeting = bool(GREETING.match(path))
                removed.append(dict(key, removal="path_prefix", original=op["path"],
                                    after=path, applies_to="all except unstripped"))
                if opid != op.get("operation_id"):
                    removed.append(dict(key, removal="operation_id_prefix",
                                        original=op.get("operation_id"), after=opid,
                                        applies_to="all except unstripped"))
                for s in names:
                    if OPID_PREFIX.match(s):
                        removed.append(dict(key, removal="schema_name_prefix", original=s,
                                            after=OPID_PREFIX.sub("", s),
                                            applies_to="A1_amended, A1_no_greeting, "
                                                       "A1_S1_no_wrapper"))
                for s in names:
                    if s in wr:
                        removed.append(dict(key, removal="framework_wrapper (S1)", original=s,
                                            after="", applies_to="A1_S1_no_wrapper"))
                if greeting:
                    removed.append(dict(key, removal="greeting_endpoint", original=op["path"],
                                        after="", applies_to="no_greeting, A1_no_greeting"))
            else:
                path, opid, clean = op["path"], op.get("operation_id"), names
                clean_nw = [s for s in names if s not in wr]
                greeting = False
            row.update({"path_clean": path, "operation_id_clean": opid or "",
                        "schema_names_clean": "|".join(clean),
                        "schema_names_clean_no_wrapper": "|".join(clean_nw),
                        "wrappers_removed": "|".join(s for s in names if s in wr),
                        "is_greeting": int(greeting)})
            table.append(row)

    for fname, rows in (("operations.csv", table), ("removed.csv", removed)):
        with open(os.path.join(DATA_DIR, fname), "w", newline="", encoding="utf-8") as fh:
            wr_ = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            wr_.writeheader()
            wr_.writerows(rows)
    with open(os.path.join(DATA_DIR, "README.md"), "w", newline="\r\n", encoding="utf-8") as fh:
        fh.write(DATA_README)
    counts = {}
    for r in removed:
        counts[r["removal"]] = counts.get(r["removal"], 0) + 1
    print("dataset folder: %d operations, %d removals %s -> %s"
          % (len(table), len(removed), counts, DATA_DIR))


def exploratory(conditions, vec, seed):
    """E1 (f1 alone) and E2 (strata by resource_pair), declared in D-31."""
    out = []
    for system, name, subset, strip, wrap in conditions:
        ops, services, _log, _xs, _xp = build_ops(subset, strip, wrap)
        mats, res = predictors(ops, vec, f1_only=True)
        iu = np.triu_indices(len(ops), 1)
        r = np.array(res)
        same_res = r[iu[0]] == r[iu[1]]
        for stratum, keep in (("all", None), ("diff_resource", ~same_res),
                              ("same_resource", same_res)):
            point, boots, n_pos, n_neg = evaluate(mats, services, seed, keep)
            if n_pos == 0 or n_neg == 0:
                continue
            base = {"system": system, "condition": name, "stratum": stratum,
                    "n_pos": n_pos, "n_neg": n_neg}
            for k in mats:
                lo, hi = interval(boots[k])
                out.append(dict(base, kind="auc", predictor=k, value=round(point[k], 6),
                                lo=round(lo, 6), hi=round(hi, 6),
                                reading="above chance" if lo > 0.5 else
                                        "below chance" if hi < 0.5 else "chance"))
            for a in ("ILSC", "f1_only"):
                for b in ("SIDC_pair", "LoCmsg_pair", "resource_pair") + (
                        ("ILSC",) if a == "f1_only" else ()):
                    lo, hi = interval(boots[a] - boots[b])
                    out.append(dict(base, kind="diff", predictor="%s - %s" % (a, b),
                                    value=round(point[a] - point[b], 6),
                                    lo=round(lo, 6), hi=round(hi, 6),
                                    reading="%s better" % a if lo > 0 else
                                            "%s worse" % a if hi < 0 else "indistinguishable"))
    with open(EXPL_CSV, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        wr.writeheader()
        wr.writerows(out)
    print("%-30s %-14s %5s %6s  %-28s %7s %17s  %s"
          % ("system / condition", "stratum", "pos", "neg", "predictor", "value", "95% CI", "reading"))
    for x in out:
        print("%-30s %-14s %5d %6d  %-28s %7.3f %17s  %s"
              % (x["system"] + " / " + x["condition"], x["stratum"], x["n_pos"], x["n_neg"],
                 x["predictor"], x["value"], "[%.3f, %.3f]" % (x["lo"], x["hi"]), x["reading"]))
    print()
    print("wrote %s" % EXPL_CSV)


def selftest():
    """The weighted AUC with unit weights must equal the unweighted one."""
    import baseline_correlation as bc
    rng = np.random.default_rng(0)
    s = rng.integers(0, 5, size=300).astype(float)
    y = rng.random(300) < 0.3
    got = SortedScores(s, y).auc(np.ones(300))
    want = bc.auc(s, y)
    assert abs(got - want) < 1e-12, (got, want)
    # integer weights must equal replicating the pairs
    w = rng.integers(0, 3, size=300).astype(float)
    rep = np.repeat(np.arange(300), w.astype(int))
    assert abs(SortedScores(s, y).auc(w) - bc.auc(s[rep], y[rep])) < 1e-12
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--parsed-dir", default=bp.BENCH_PARSED)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", action="store_true",
                    help="write data/benchmarks/d31_cleaned/ only; no scores")
    ap.add_argument("--exploratory", action="store_true",
                    help="D-31 exploratory E1/E2 only; the pre-registered file is not touched")
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return

    head = subprocess.run(["git", "-C", config.MSDECOMPOSER_DIR, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head != config.MSDECOMPOSER_COMMIT:
        sys.exit("msdecomposer is at %r, not the pinned %s" % (head, config.MSDECOMPOSER_COMMIT))

    tt = load_system(args.parsed_dir, "trainticket")
    kept = [it for it in tt if not GREETING.match(strip_identity(it[0], it[1])[0])]
    ss = load_system(args.parsed_dir, "sockshop")
    print("trainticket: %d operations, %d services; %d greeting endpoints"
          % (len(tt), len({s for s, _ in tt}), len(tt) - len(kept)))
    print("sockshop:    %d operations, %d services" % (len(ss), len({s for s, _ in ss})))

    if args.exploratory:
        wr_tt = load_wrappers("trainticket")
        conds = (("trainticket", "A1_amended", tt, "all", frozenset()),
                 ("trainticket", "A1_S1_no_wrapper", tt, "all", wr_tt),
                 ("sockshop", "primary", ss, None, frozenset()))
        texts = set()
        for _sy, _nm, subset, strip, wrap in conds:
            ops = build_ops(subset, strip, wrap)[0]
            texts |= {o["T"] for o in ops} | {o["description"] for o in ops if o["description"]}
        texts = sorted(texts)
        vec = dict(zip(texts, emb_mod.embed_texts(texts, "D-31 exploratory")))
        exploratory(conds, vec, config.SEED)
        return

    wr_tt, wr_ss = load_wrappers("trainticket"), load_wrappers("sockshop")
    print("S1 framework wrappers: trainticket %d schema names, on %d operations | sockshop %d"
          % (len(wr_tt), sum(1 for _s, o in tt if set(o["schema_names"]) & wr_tt), len(wr_ss)))
    none = frozenset()

    # (system, origin, condition, operations, strip, S1 wrappers, partitions)
    plan = (("trainticket", "derived", "primary", tt, "path_opid", none, True),
            ("trainticket", "derived", "no_greeting", kept, "path_opid", none, True),
            ("trainticket", "derived", "unstripped", tt, None, none, False),
            ("trainticket", "derived", "A1_amended", tt, "all", none, True),
            ("trainticket", "derived", "A1_no_greeting", kept, "all", none, True),
            ("trainticket", "derived", "A1_S1_no_wrapper", tt, "all", wr_tt, True),
            ("sockshop", "independent", "primary", ss, None, none, True),
            ("sockshop", "independent", "S1_no_wrapper", ss, None, wr_ss, True))

    write_dataset(plan, {"trainticket": tt, "sockshop": ss})
    if args.dataset:
        return

    # every text any condition needs, embedded once with the pinned model
    texts = set()
    for _sy, _or, _nm, subset, strip, wrap, _pt in plan:
        ops = build_ops(subset, strip, wrap)[0]
        texts |= {o["T"] for o in ops} | {o["description"] for o in ops if o["description"]}
    texts = sorted(texts)
    vec = dict(zip(texts, emb_mod.embed_texts(texts, "D-31")))

    out, strip_log = [], None
    for system, origin, name, subset, strip, wrap, parts in plan:
        rows, log, excl_s, excl_p, keep = run_condition(system, origin, name, subset, strip,
                                                        wrap, vec, config.SEED, partitions=parts)
        out.extend(rows)
        if (system, name) == ("trainticket", "A1_amended"):
            strip_log = log
        print("%s / %s system-level exclusions: schemas %s | params %s"
              % (system, name, excl_s, excl_p))
        if (system, name) == ("sockshop", "primary"):
            srows, un_ours, un_sun = sun_rows(*keep)
            out.extend(srows)
            print("sun2022 match: %d of our %d operations matched; %d of Sun's unmatched"
                  % (len(keep[0]) - un_ours, len(keep[0]), un_sun))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        wr.writeheader()
        wr.writerows(out)
    with open(STRIP_LOG, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(strip_log[0].keys()))
        wr.writeheader()
        wr.writerows(strip_log)

    print("\nprefix removed: opIds %d of %d | schema names %d, on %d operations"
          % (sum(r["opid_prefix_removed"] for r in strip_log), len(strip_log),
             sum(r["schema_prefixes_removed"] for r in strip_log),
             sum(1 for r in strip_log if r["schema_prefixes_removed"])))
    print("%-24s %-15s %7s %17s %9s %19s  %-18s %4s %6s %6s"
          % ("system / condition", "predictor", "AUC", "95% CI", "ILSC-X", "95% CI",
             "verdict", "k", "ARI", "NMI"))
    for r in out:
        auc_s = "%.3f" % r["auc"] if r["auc"] != "" else ""
        ci = "[%.3f, %.3f]" % (r["auc_lo"], r["auc_hi"]) if r["auc_lo"] != "" else ""
        dci = "[%.3f, %.3f]" % (r["diff_lo"], r["diff_hi"]) if r["diff_lo"] != "" else ""
        diff = "%.3f" % r["diff_ilsc_minus"] if r["diff_ilsc_minus"] != "" else ""
        part = ("%4s %6.3f %6.3f" % (r["louvain_k"], r["ari"], r["nmi"])
                if r["ari"] != "" else "")
        print("%-24s %-15s %7s %17s %9s %19s  %-18s %s"
              % (r["system"] + " / " + r["condition"], r["predictor"], auc_s, ci, diff, dci,
                 r["verdict"], part))
    print("\nwrote %s\n      %s" % (OUT_CSV, STRIP_LOG))


if __name__ == "__main__":
    main()

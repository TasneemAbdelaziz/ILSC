"""
ILSC - Day 3 metric track (Mohamed): the six similarity functions and the mask.

This is the engine every experiment sits on. It implements D2/D3 of the
proposal (Sec. 6) exactly:

    Sim(Oi,Oj) = SUM_k ( w_k * m_ijk * sim_k ) / SUM_k ( w_k * m_ijk )

    f1 embedding    cosine of SBERT(T(Oi))          always available
    f2 name         Jaccard of operationId tokens   masked
    f3 path         Jaccard of normalised path tokens
    f4 params       Jaccard of parameter-name tokens masked
    f5 schemas      OVERLAP COEFFICIENT of domain schema names, |A n B|/min(|A|,|B|)
    f6 description  cosine of SBERT(description)     masked
    f7 co-usage     reserved, mask permanently 0

The availability mask m_ijk is 1 only when BOTH operations of the pair carry
feature k; the weights then redistribute over whatever is left. Absence never
counts as dissimilarity - that is the theoretical claim (C1) the whole paper
rests on, and it is why f1's text excludes the description (R2).

Three definitional points, each a judgement this module had to make
------------------------------------------------------------------
**f2's mask is the `f2_codegen` definition**, imported from
``pair_availability`` rather than restated, so the engine and the Day 3
availability study can never drift apart (D-08 fixed the definition; this keeps
it single-sourced).

**A feature whose SET IS EMPTY is unavailable, even when the field is present.**
Jaccard and the overlap coefficient are 0/0 on an empty set, and there is no
defensible value to return: 0 would assert dissimilarity from an absence, which
is precisely what the mask exists to prevent, and 1 would assert identity. So an
``operationId`` that tokenises to nothing (``"v1"``, entirely stopwords) leaves
f2 unavailable although the string is non-empty. This is stricter than the Day 3
study, which only tested the field, and it moves f2 and f3 slightly. It is
recorded as **D-19**; ``--audit`` prints exactly how many operations it affects.

**Cosine is clamped to [0,1].** SBERT cosines are occasionally negative, and the
aggregation assumes each ``sim_k`` lies in [0,1] (ILSC is defined on [0,1] and
mixes cosine with Jaccard, which cannot go negative). Clamping at zero reads a
negative cosine as "no similarity" rather than as evidence of opposition, which
is the only reading the aggregation supports. ``--audit`` counts how often it
fires so the paper can state it.

Usage:
    python src/similarity.py --selftest      # the three handmade pairs + R2
    python src/similarity.py --audit         # corpus-wide mask/clamp incidence
    python src/similarity.py --service <parsed file>   # one service's matrix
"""

import argparse
import json
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                       # noqa: E402
import embed as emb_mod                             # noqa: E402
# f2's primary definition lives in the Day 3 study; import it, never restate it.
from pair_availability import is_codegen_placeholder  # noqa: E402

FEATURES = ("f1", "f2", "f3", "f4", "f5", "f6")
NF = len(FEATURES)

# Initial weights, Sec. 6: neutral 1/6 each. Exp. 5 sweeps these.
DEFAULT_WEIGHTS = np.full(NF, 1.0 / NF, dtype="float64")

# Row-block size for the pair loop. Affects peak memory only, never a result.
BLOCK = 512


def normalise_schema(name):
    """Schema names are matched the way the Day 3 study matches them."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# ----------------------------------------------------------------------------
# An operation set: a service, or any bag of operations (null models, injection)
# ----------------------------------------------------------------------------

class OpSet:
    """n operations with their feature sets, availability flags and vectors.

    Deliberately not tied to a service: Exp. 1's null models draw operations
    from the whole corpus and Exp. 2 injects operations from other services, and
    both need to score a bag of operations that never shared a specification.
    """

    __slots__ = ("n", "avail", "sets", "sizes", "T", "D", "labels")

    def __init__(self, ops, T, D, labels=None):
        self.n = len(ops)
        self.T = T
        self.D = D
        self.labels = labels or [o.get("op_key", str(i)) for i, o in enumerate(ops)]

        # feature token/name sets, index 1..5 (f1 has no set; f6 has no set)
        f2 = [set(o.get("name_tokens") or []) for o in ops]
        f3 = [set(o.get("path_tokens") or []) for o in ops]
        f4 = [set(o.get("param_tokens") or []) for o in ops]
        f5 = [{normalise_schema(s) for s in (o.get("domain_schemas") or [])} for o in ops]

        avail = np.zeros((self.n, NF), dtype=bool)
        avail[:, 0] = True                                     # f1 always
        for i, o in enumerate(ops):
            opid = o.get("operation_id")
            good_id = bool(opid and opid.strip()) and not is_codegen_placeholder(opid)
            avail[i, 1] = good_id and bool(f2[i])              # D-19: set must be non-empty
            avail[i, 2] = bool(f3[i])
            avail[i, 3] = bool(f4[i])
            avail[i, 4] = bool(f5[i])
        # f6 is carried by the embedding cache's -1 sentinel, passed in as a norm
        avail[:, 5] = np.linalg.norm(D, axis=1) > 0 if self.n else False

        self.avail = avail
        self.sets = (f2, f3, f4, f5)
        self.sizes = np.array([[len(s[i]) for s in self.sets] for i in range(self.n)],
                              dtype="int32") if self.n else np.zeros((0, 4), dtype="int32")

    # -- constructors --------------------------------------------------------

    @classmethod
    def from_service(cls, doc, emb, name):
        return cls(doc["operations"], emb.matrix_T(name), emb.matrix_D(name))

    @classmethod
    def from_pool(cls, ops, T, D):
        """ops/T/D already aligned; used by the null models and by inject.py."""
        return cls(ops, T, D)

    # -- the sparse incidence matrices, built once per OpSet ------------------

    def _incidence(self):
        from scipy import sparse
        mats = []
        for s in self.sets:
            vocab = {}
            rows, cols = [], []
            for i, items in enumerate(s):
                for it in items:
                    j = vocab.setdefault(it, len(vocab))
                    rows.append(i)
                    cols.append(j)
            m = sparse.csr_matrix(
                (np.ones(len(rows), dtype="float32"), (rows, cols)),
                shape=(self.n, max(len(vocab), 1)))
            mats.append(m)
        return mats


# ----------------------------------------------------------------------------
# The pair computation
# ----------------------------------------------------------------------------

def _clamp01(x, counter=None):
    if counter is not None:
        counter[0] += int((x < 0).sum())
    return np.clip(x, 0.0, 1.0)


def pair_blocks(opset, weights=None, tau=None, block=BLOCK, clamp_counter=None):
    """Yield (i0, i1, sim, per_feature, mask) for row blocks of the pair matrix.

    ``sim``        (b, n) float32, the aggregated Sim(Oi,Oj)
    ``per_feature``(b, n, 6) float32, each sim_k BEFORE masking
    ``mask``       (b, n, 6) bool,    m_ijk
    Only entries with j > i (global index) are meaningful; callers use the
    triangular selector below.
    """
    w = DEFAULT_WEIGHTS if weights is None else np.asarray(weights, dtype="float64")
    n = opset.n
    if n < 2:
        return
    mats = opset._incidence()
    sizes = opset.sizes

    for i0 in range(0, n, block):
        i1 = min(i0 + block, n)
        b = i1 - i0

        per = np.zeros((b, n, NF), dtype="float32")

        # f1 / f6: cosine, clamped
        per[:, :, 0] = _clamp01(opset.T[i0:i1] @ opset.T.T, clamp_counter)
        per[:, :, 5] = _clamp01(opset.D[i0:i1] @ opset.D.T, clamp_counter)

        # f2, f3, f4: Jaccard;  f5: overlap coefficient
        for k, m in enumerate(mats):
            inter = np.asarray((m[i0:i1] @ m.T).todense(), dtype="float32")
            a = sizes[i0:i1, k][:, None].astype("float32")
            c = sizes[:, k][None, :].astype("float32")
            if k < 3:                                   # f2, f3, f4 -> Jaccard
                den = a + c - inter
            else:                                       # f5 -> overlap coefficient
                den = np.minimum(a, c)
            with np.errstate(divide="ignore", invalid="ignore"):
                per[:, :, k + 1] = np.where(den > 0, inter / den, 0.0)

        mask = opset.avail[i0:i1, None, :] & opset.avail[None, :, :]
        wm = mask * w[None, None, :]
        den = wm.sum(axis=2)
        num = (wm * per).sum(axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            sim = np.where(den > 0, num / den, 0.0).astype("float32")

        yield i0, i1, sim, per, mask


def triu_selector(i0, i1, n):
    """Boolean (b, n) selecting j > i for a row block starting at i0."""
    rows = np.arange(i0, i1)[:, None]
    cols = np.arange(n)[None, :]
    return cols > rows


def service_stats(opset, weights=None, tau=None, want_feature_sums=False):
    """ILSC_mean, ILSC_tau and the mask/evidence bookkeeping for one OpSet."""
    tau = config.TAU_DEFAULT if tau is None else tau
    n = opset.n
    n_pairs = n * (n - 1) // 2
    out = {
        "n_operations": n,
        "n_pairs": n_pairs,
        "ILSC_mean": float("nan"),
        "ILSC_tau": float("nan"),
        "tau": tau,
        "no_evidence_pairs": 0,
        "mask_fire_pairs": 0,
    }
    if want_feature_sums:
        out["feature_sum"] = np.zeros(NF)
        out["feature_pairs"] = np.zeros(NF, dtype="int64")
    if n_pairs == 0:
        return out

    total = 0.0
    over_tau = 0
    no_ev = 0
    mask_fire = 0
    fsum = np.zeros(NF)
    fcnt = np.zeros(NF, dtype="int64")

    for i0, i1, sim, per, mask in pair_blocks(opset, weights, tau):
        sel = triu_selector(i0, i1, opset.n)
        s = sim[sel]
        total += float(s.sum())
        over_tau += int((s >= tau).sum())
        m = mask[sel]
        no_ev += int((~m.any(axis=1)).sum())
        mask_fire += int((~m.all(axis=1)).sum())
        if want_feature_sums:
            p = per[sel]
            fsum += (p * m).sum(axis=0)
            fcnt += m.sum(axis=0)

    out["ILSC_mean"] = total / n_pairs
    out["ILSC_tau"] = over_tau / n_pairs
    out["no_evidence_pairs"] = no_ev
    out["mask_fire_pairs"] = mask_fire
    if want_feature_sums:
        out["feature_sum"] = fsum
        out["feature_pairs"] = fcnt
    return out


def ilsc_mean(opset, weights=None):
    """Just the headline number - the hot path for the null models."""
    n = opset.n
    if n < 2:
        return float("nan")
    total = 0.0
    for i0, i1, sim, _per, _mask in pair_blocks(opset, weights):
        total += float(sim[triu_selector(i0, i1, n)].sum())
    return total / (n * (n - 1) // 2)


def ilsc_norm(mean, expected_random):
    """(ILSC_mean - E[ILSC_rand(n)]) / (1 - E[ILSC_rand(n)]).

    Reported unclipped: a negative value means the service is less coherent than
    an arbitrary bag of operations, which is informative, not an error (Sec. 6).
    """
    if expected_random is None or not np.isfinite(expected_random) or expected_random >= 1.0:
        return float("nan")
    return (mean - expected_random) / (1.0 - expected_random)


def pair_table(opset, weights=None, tau=None):
    """Every pair as a row. For Gate 1 diagnostics and Fig 8 - small services."""
    tau = config.TAU_DEFAULT if tau is None else tau
    rows = []
    for i0, i1, sim, per, mask in pair_blocks(opset, weights, tau):
        for a in range(i1 - i0):
            i = i0 + a
            for j in range(i + 1, opset.n):
                r = {"i": i, "j": j, "op_i": opset.labels[i], "op_j": opset.labels[j],
                     "sim": float(sim[a, j])}
                for k, f in enumerate(FEATURES):
                    r[f] = float(per[a, j, k])
                    r["m_" + f] = int(mask[a, j, k])
                rows.append(r)
    return rows


# ----------------------------------------------------------------------------
# Self-test: the handmade pairs Sec. 10 asks for, including R2
# ----------------------------------------------------------------------------

def _op(op_key, method, path, opid, params, schemas, desc):
    import parse_spec as ps
    name_tokens = ps.tokenize(opid) if opid else []
    return {
        "op_key": op_key, "method": method, "path": path, "operation_id": opid,
        "name_tokens": name_tokens,
        "path_tokens": ps.normalize_path(path),
        "param_tokens": sorted({t for p in params for t in ps.tokenize(p)}),
        "domain_schemas": schemas,
        "description": desc,
    }


_MODEL = [None]


def _embed(texts):
    """Only the self-test embeds live; everything else reads the cache."""
    if _MODEL[0] is None:
        from sentence_transformers import SentenceTransformer
        _MODEL[0] = SentenceTransformer(config.EMBEDDING_MODEL)
    return _MODEL[0].encode(list(texts), convert_to_numpy=True,
                            normalize_embeddings=True).astype("float32")


def _opset_from(ops):
    import parse_spec as ps
    T = _embed([ps.build_T(o["method"], o["name_tokens"], o["path_tokens"],
                           o["param_tokens"],
                           sorted({t for s in o["domain_schemas"] for t in ps.tokenize(s)}))
                for o in ops])
    descs = [o["description"] for o in ops]
    have = [i for i, d in enumerate(descs) if d]
    D = np.zeros((len(ops), T.shape[1]), dtype="float32")
    if have:
        D[have] = _embed([descs[i] for i in have])
    return OpSet(ops, T, D)


def selftest():
    print("Handmade pairs (Sec. 10, Day 3) - weights 1/6, tau %.2f\n" % config.TAU_DEFAULT)
    ok = True

    a = _op("GET /orders/{id}", "GET", "/orders/{id}", "getOrderById",
            ["id"], ["Order", "Item"], "Fetch a single order by its identifier.")
    a2 = _op("GET /orders/{id}", "GET", "/orders/{id}", "getOrderById",
             ["id"], ["Order", "Item"], "Fetch a single order by its identifier.")
    b = _op("POST /orders", "POST", "/orders", "createOrder",
            ["body"], ["Order", "Card", "Address", "Item"], "Create a new order.")
    z = _op("GET /weather/forecast", "GET", "/weather/forecast", "getForecast",
            ["lat", "lon"], ["Forecast", "Station"], "Return the weather forecast.")

    s = pair_table(_opset_from([a, a2]))[0]["sim"]
    print("  identical pair          Sim = %.4f   (expect ~1.0)" % s)
    ok &= s > 0.99

    s = pair_table(_opset_from([a, b]))[0]["sim"]
    print("  related pair            Sim = %.4f   (expect mid-range)" % s)
    ok &= 0.15 < s < 0.95

    s = pair_table(_opset_from([a, z]))[0]["sim"]
    print("  unrelated pair          Sim = %.4f   (expect low)" % s)
    ok &= s < 0.45

    # --- R2: deleting a description must not move f1 -----------------------
    b_nodesc = dict(b)
    b_nodesc["description"] = None
    with_desc = pair_table(_opset_from([a, b]))[0]
    without = pair_table(_opset_from([a, b_nodesc]))[0]
    print("\n  R2 regression - delete one description:")
    print("    f1 with description   %.6f" % with_desc["f1"])
    print("    f1 without            %.6f" % without["f1"])
    print("    m_f6                  %d -> %d" % (with_desc["m_f6"], without["m_f6"]))
    same_f1 = abs(with_desc["f1"] - without["f1"]) < 1e-6
    print("    f1 unchanged          %s   (fails on the v2 design)"
          % ("YES" if same_f1 else "NO"))
    ok &= same_f1 and with_desc["m_f6"] == 1 and without["m_f6"] == 0
    print("    Sim still computes    %.4f" % without["sim"])
    ok &= np.isfinite(without["sim"])

    print("\n%s" % ("all self-tests passed" if ok else "SELF-TEST FAILED"))
    if not ok:
        sys.exit(1)


# ----------------------------------------------------------------------------
# Audit: how often do the two judgement calls above actually fire?
# ----------------------------------------------------------------------------

def audit(parsed_dir, cache_dir, limit=None):
    emb = emb_mod.Embeddings(cache_dir)
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    if limit:
        files = files[:limit]

    n_ops = 0
    empty_after_tokens = np.zeros(NF, dtype="int64")   # field present, set empty
    field_present = np.zeros(NF, dtype="int64")
    available = np.zeros(NF, dtype="int64")
    clamped = [0]                                      # D-20: negative cosines seen
    cosine_cells = 0

    import parse_spec as ps                            # noqa: F401  (tokenizer parity)
    for name in files:
        if name not in emb:
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        ops = doc["operations"]
        oset = OpSet(ops, emb.matrix_T(name), emb.matrix_D(name))
        n_ops += len(ops)
        available += oset.avail.sum(axis=0)
        # D-20 incidence, measured rather than assumed. Counted over the full
        # (b, n) blocks including the lower triangle and the diagonal - the rate
        # is what matters here, and the matrix is symmetric.
        if 2 <= oset.n <= 400:                         # keep the audit cheap
            for i0, i1, _s, _per, _m in pair_blocks(oset, clamp_counter=clamped):
                cosine_cells += 2 * (i1 - i0) * oset.n
        for i, o in enumerate(ops):
            opid = o.get("operation_id")
            good_id = bool(opid and opid.strip()) and not is_codegen_placeholder(opid)
            if good_id:
                field_present[1] += 1
                if not o.get("name_tokens"):
                    empty_after_tokens[1] += 1
            if o.get("path") is not None:
                field_present[2] += 1
                if not o.get("path_tokens"):
                    empty_after_tokens[2] += 1
            if o.get("param_names"):
                field_present[3] += 1
                if not o.get("param_tokens"):
                    empty_after_tokens[3] += 1

    print("audit over %d services, %s operations\n" % (len(files), "{:,}".format(n_ops)))
    print("  feature   available            field present but set EMPTY (D-19)")
    for k, f in enumerate(FEATURES):
        extra = ""
        if field_present[k]:
            extra = "%7s of %s  (%.3f%%)" % (
                "{:,}".format(empty_after_tokens[k]), "{:,}".format(field_present[k]),
                100.0 * empty_after_tokens[k] / field_present[k])
        print("   %-8s %8s (%6.2f%%)   %s"
              % (f, "{:,}".format(available[k]), 100.0 * available[k] / max(n_ops, 1), extra))

    print("\n  D-20 cosine clamping: %s of %s f1/f6 cosine values were negative "
          "(%.4f%%)" % ("{:,}".format(clamped[0]), "{:,}".format(cosine_cells),
                        100.0 * clamped[0] / max(cosine_cells, 1)))
    print("  (measured on services of 2-400 operations, both triangles)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC similarity engine.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--service", default=None, help="parsed file name; print its pairs")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--cache", default=emb_mod.DEFAULT_CACHE)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.audit:
        return audit(args.parsed_dir, args.cache, args.limit)
    if args.service:
        emb = emb_mod.Embeddings(args.cache)
        with open(os.path.join(args.parsed_dir, args.service), encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = OpSet.from_service(doc, emb, args.service)
        st = service_stats(oset)
        print("%s  n=%d  ILSC_mean=%.4f  ILSC_tau=%.4f"
              % (doc["title"], st["n_operations"], st["ILSC_mean"], st["ILSC_tau"]))
        for r in pair_table(oset)[:40]:
            print("  %-34s %-34s sim=%.3f  m=%s"
                  % (r["op_i"][:34], r["op_j"][:34], r["sim"],
                     "".join(str(r["m_" + f]) for f in FEATURES)))
        return
    ap.print_help()


if __name__ == "__main__":
    main()

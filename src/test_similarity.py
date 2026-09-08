"""
ILSC - Day 3-4 metric track (Mohamed): unit tests for the similarity engine.

Run:  python src/test_similarity.py          (no pytest dependency)
      python -m pytest src/test_similarity.py -q      (also works)

The tests are grouped by what would actually break the paper if it were wrong.
The mask tests come first because the mask is the theoretical claim (C1); an
arithmetic slip in Jaccard would produce bad numbers, but a broken mask would
produce a bad *argument*.

Nothing here touches the network except ``test_r2_description_isolation`` and
``test_handmade_pairs``, which need the pinned SBERT model. They are skipped
with a printed notice if it is unavailable, so the algebra can still be checked
on a machine with no model cache.
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                       # noqa: E402
import similarity as sim            # noqa: E402
import parse_spec as ps             # noqa: E402

DIM = 8                             # toy embedding width for the algebra tests


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def op(op_key="GET /x", method="GET", path="/orders/{id}", opid="getOrderById",
       params=("id",), schemas=("Order",), desc="An order."):
    return {
        "op_key": op_key, "method": method, "path": path, "operation_id": opid,
        "name_tokens": ps.tokenize(opid) if opid else [],
        "path_tokens": ps.normalize_path(path),
        "param_tokens": sorted({t for p in params for t in ps.tokenize(p)}),
        "domain_schemas": list(schemas),
        "description": desc,
    }


def toy(ops, t_vecs=None, d_present=None):
    """Build an OpSet with controlled vectors so f1/f6 are exactly known."""
    n = len(ops)
    T = np.zeros((n, DIM), dtype="float32")
    if t_vecs is None:
        T[:, 0] = 1.0                                  # all identical -> f1 = 1
    else:
        for i, v in enumerate(t_vecs):
            T[i, : len(v)] = v
        norms = np.linalg.norm(T, axis=1, keepdims=True)
        T = (T / np.where(norms == 0, 1, norms)).astype("float32")
    D = np.zeros((n, DIM), dtype="float32")
    for i, o in enumerate(ops):
        present = o.get("description") is not None if d_present is None else d_present[i]
        if present:
            D[i, 0] = 1.0
    return sim.OpSet(ops, T, D)


def one_pair(opset):
    return sim.pair_table(opset)[0]


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


# ----------------------------------------------------------------------------
# 1. The availability mask - the theoretical claim
# ----------------------------------------------------------------------------

@case
def test_mask_requires_both_sides():
    """m_ijk = 1 only when BOTH operations carry feature k."""
    a = op(desc="An order.")
    b = op(desc=None)
    r = one_pair(toy([a, b]))
    assert r["m_f6"] == 0, "f6 must be masked when one side has no description"
    r2 = one_pair(toy([a, op(desc="Another order.")]))
    assert r2["m_f6"] == 1


@case
def test_absence_never_lowers_similarity():
    """Deleting a field must not push Sim down - it must leave it out.

    This is the mask's entire purpose. Two operations that agree on everything
    they both have must score 1.0 even when one of them is missing fields.
    """
    a = op(opid="getOrderById", params=("id",), schemas=("Order",), desc="An order.")
    b = op(opid="getOrderById", params=("id",), schemas=("Order",), desc=None)
    r = one_pair(toy([a, b]))
    assert r["m_f6"] == 0
    assert abs(r["sim"] - 1.0) < 1e-6, "masked-out f6 must not drag Sim below 1.0, got %r" % r["sim"]


@case
def test_weights_redistribute_over_available_features():
    """The denominator is SUM w_k m_ijk, not SUM w_k."""
    # identical on f1/f3, no operationId, no params, no schemas, no description:
    # only f1 and f3 are available, so Sim is their average, not their sixth.
    a = op(opid=None, params=(), schemas=(), desc=None)
    b = op(opid=None, params=(), schemas=(), desc=None)
    r = one_pair(toy([a, b]))
    assert [r["m_" + f] for f in sim.FEATURES] == [1, 0, 1, 0, 0, 0]
    assert abs(r["sim"] - 1.0) < 1e-6, "Sim should be 1.0 over the two available features"


@case
def test_f7_is_not_in_the_aggregation():
    """f7 is reserved with mask 0; it must not appear as a seventh weight."""
    assert sim.NF == 6
    assert len(sim.DEFAULT_WEIGHTS) == 6
    assert abs(sim.DEFAULT_WEIGHTS.sum() - 1.0) < 1e-12


@case
def test_empty_set_is_unavailable_not_zero():
    """D-19: a present-but-empty token set leaves the feature unavailable.

    'v1' tokenises to nothing under the pinned stopwords, so f2 has no set to
    compare and must be masked rather than scored 0.
    """
    a = op(opid="v1")
    assert a["name_tokens"] == [], "fixture assumption: 'v1' tokenises to nothing"
    oset = toy([a, op(opid="v1")])
    assert oset.avail[0, 1] == False       # noqa: E712  - explicit is the point
    r = one_pair(oset)
    assert r["m_f2"] == 0


# ----------------------------------------------------------------------------
# 2. The similarity functions
# ----------------------------------------------------------------------------

@case
def test_jaccard_values():
    """f3 = |A n B| / |A u B| on path tokens."""
    a = op(path="/orders/{id}/items")          # {orders, items}
    b = op(path="/orders/{id}/payments")       # {orders, payments}
    r = one_pair(toy([a, b]))
    assert abs(r["f3"] - 1.0 / 3.0) < 1e-6, r["f3"]


@case
def test_f5_is_overlap_coefficient_not_jaccard():
    """f5 = |A n B| / min(|A|,|B|): a subset relationship scores 1.0.

    This is the reason generic schemas are excluded (D2 [v3]) - without the
    exclusion every operation would share Error and f5 would saturate.
    """
    a = op(schemas=("Order",))
    b = op(schemas=("Order", "Card", "Address"))
    r = one_pair(toy([a, b]))
    assert abs(r["f5"] - 1.0) < 1e-6, "subset must give 1.0 under overlap, got %r" % r["f5"]
    # Jaccard would have given 1/3; assert we did not silently use it
    assert abs(r["f5"] - 1.0 / 3.0) > 0.5


@case
def test_disjoint_sets_score_zero_when_available():
    """Available but disjoint is real evidence of dissimilarity, and scores 0."""
    a = op(opid="createOrder", schemas=("Order",))
    b = op(opid="listStations", schemas=("Station",))
    r = one_pair(toy([a, b]))
    assert r["m_f2"] == 1 and r["m_f5"] == 1
    assert r["f2"] == 0.0 and r["f5"] == 0.0


@case
def test_cosine_is_clamped_to_zero():
    """A negative cosine reads as 'no similarity', never as negative evidence."""
    oset = toy([op(), op()], t_vecs=[[1.0, 0.0], [-1.0, 0.0]])
    r = one_pair(oset)
    assert r["f1"] == 0.0, r["f1"]
    assert 0.0 <= r["sim"] <= 1.0


# ----------------------------------------------------------------------------
# 3. Aggregation
# ----------------------------------------------------------------------------

@case
def test_ilsc_mean_is_the_mean_over_all_pairs():
    ops = [op(path="/a"), op(path="/b"), op(path="/c")]
    oset = toy(ops)
    rows = sim.pair_table(oset)
    assert len(rows) == 3, "C(3,2) = 3 pairs"
    st = sim.service_stats(oset)
    assert st["n_pairs"] == 3
    assert abs(st["ILSC_mean"] - np.mean([r["sim"] for r in rows])) < 1e-6


@case
def test_ilsc_tau_is_edge_density():
    ops = [op(path="/orders"), op(path="/orders"), op(path="/weather/forecast")]
    oset = toy(ops)
    rows = sim.pair_table(oset)
    for t in (0.0, 0.5, 1.01):
        st = sim.service_stats(oset, tau=t)
        expect = sum(1 for r in rows if r["sim"] >= t) / len(rows)
        assert abs(st["ILSC_tau"] - expect) < 1e-9, (t, st["ILSC_tau"], expect)


@case
def test_ilsc_norm_is_unclipped():
    """Worse than chance is an informative outcome, not an error (Sec. 6)."""
    assert abs(sim.ilsc_norm(0.5, 0.0) - 0.5) < 1e-12
    assert sim.ilsc_norm(0.10, 0.40) < 0, "must be allowed to go negative"
    assert abs(sim.ilsc_norm(0.7, 0.4) - 0.5) < 1e-12
    assert not np.isfinite(sim.ilsc_norm(0.5, 1.0))


@case
def test_blocking_does_not_change_results():
    """The row-block size is a memory knob and must never move a number."""
    ops = [op(path="/p%d" % i, opid="getThing%d" % i, schemas=("S%d" % (i % 3),))
           for i in range(37)]
    oset = toy(ops, t_vecs=[[np.cos(i), np.sin(i)] for i in range(37)])
    full = sim.service_stats(oset)
    old = sim.BLOCK
    try:
        sim.BLOCK = 4
        small = sim.service_stats(oset)
    finally:
        sim.BLOCK = old
    assert abs(full["ILSC_mean"] - small["ILSC_mean"]) < 1e-9
    assert full["mask_fire_pairs"] == small["mask_fire_pairs"]


@case
def test_pair_counts_add_up():
    ops = [op(path="/p%d" % i, opid=("getThing%d" % i) if i % 2 else None,
              desc="d" if i % 3 else None) for i in range(12)]
    oset = toy(ops)
    st = sim.service_stats(oset, want_feature_sums=True)
    assert st["n_pairs"] == 12 * 11 // 2
    assert st["feature_pairs"][0] == st["n_pairs"], "f1 is always available"
    assert st["mask_fire_pairs"] <= st["n_pairs"]
    assert st["no_evidence_pairs"] == 0, "f1 always available, so evidence always exists"


@case
def test_opset_from_mixed_services():
    """Null models and inject.py score bags of operations from different specs."""
    ops = [op(path="/orders", schemas=("Order",)),
           op(path="/weather", schemas=("Forecast",)),
           op(path="/orders/{id}", schemas=("Order",))]
    oset = sim.OpSet.from_pool(ops, toy(ops).T, toy(ops).D)
    st = sim.service_stats(oset)
    assert st["n_pairs"] == 3 and np.isfinite(st["ILSC_mean"])


# ----------------------------------------------------------------------------
# 4. The R2 regression test - the one that fails on the v2 design
# ----------------------------------------------------------------------------

def _model_available():
    try:
        sim._embed(["probe"])
        return True
    except Exception as exc:                            # noqa: BLE001
        print("    (skipped: SBERT model unavailable - %s)" % type(exc).__name__)
        return False


@case
def test_r2_description_isolation():
    """Two operations identical except one has its description deleted.

    f1 must be bit-identical, because T(Oi) never contained the description.
    This test fails on the v2 design and is the reason R2 exists.
    """
    if not _model_available():
        return
    a = op(desc="Fetch a single order by its identifier.")
    b = op(opid="createOrder", path="/orders", params=("body",),
           schemas=("Order", "Card"), desc="Create a new order.")
    b_no = dict(b)
    b_no["description"] = None

    with_d = sim.pair_table(sim._opset_from([a, b]))[0]
    without = sim.pair_table(sim._opset_from([a, b_no]))[0]
    assert abs(with_d["f1"] - without["f1"]) < 1e-6, \
        "f1 moved when only the description changed: %r vs %r" % (with_d["f1"], without["f1"])
    assert with_d["m_f6"] == 1 and without["m_f6"] == 0
    assert np.isfinite(without["sim"]), "a missing-description pair must still compute"


@case
def test_handmade_pairs():
    """Sec. 10's three pairs with known answers."""
    if not _model_available():
        return
    a = sim._op("GET /orders/{id}", "GET", "/orders/{id}", "getOrderById",
                ["id"], ["Order", "Item"], "Fetch a single order by its identifier.")
    b = sim._op("POST /orders", "POST", "/orders", "createOrder",
                ["body"], ["Order", "Card", "Address", "Item"], "Create a new order.")
    z = sim._op("GET /weather/forecast", "GET", "/weather/forecast", "getForecast",
                ["lat", "lon"], ["Forecast", "Station"], "Return the weather forecast.")
    identical = sim.pair_table(sim._opset_from([a, dict(a)]))[0]["sim"]
    related = sim.pair_table(sim._opset_from([a, b]))[0]["sim"]
    unrelated = sim.pair_table(sim._opset_from([a, z]))[0]["sim"]
    assert identical > 0.99, identical
    assert related > unrelated + 0.2, (related, unrelated)
    assert unrelated < 0.45, unrelated


# ----------------------------------------------------------------------------
# runner
# ----------------------------------------------------------------------------

def main():
    print("ILSC similarity engine - %d tests\n" % len(CASES))
    failed = []
    for fn in CASES:
        try:
            fn()
            print("  PASS  %s" % fn.__name__)
        except AssertionError as exc:
            print("  FAIL  %s\n          %s" % (fn.__name__, exc))
            failed.append(fn.__name__)
        except Exception as exc:                        # noqa: BLE001
            print("  ERROR %s\n          %s: %s" % (fn.__name__, type(exc).__name__, exc))
            failed.append(fn.__name__)
    print("\n%d/%d passed" % (len(CASES) - len(failed), len(CASES)))
    if failed:
        sys.exit("FAILED: " + ", ".join(failed))


# pytest picks these up by name as well
for _fn in CASES:
    globals()[_fn.__name__] = _fn

if __name__ == "__main__":
    main()

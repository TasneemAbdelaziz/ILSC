"""
ILSC — Day 3 (Tasneem): PAIR-level co-availability (the RQ2 headline).

The similarity mask evaluates m_ij,k = 1 only when BOTH operations of a
within-service pair carry feature k. So the per-operation rate (availability.py)
is not the RQ2 number; the pair-level co-availability is.

Features of the similarity equation (proposal Sec. 6 / D2):

  f1 embedding   SBERT of T(O). method+path always exist -> ALWAYS available.
  f3 path        normalised path tokens          -> ALWAYS available.
  f2 name        operationId, non-empty and not an auto-generated placeholder.
  f4 parameters  effective (path-level union op-level) parameters, non-empty.
  f5 schemas     ONE feature: the set of DOMAIN schema NAMES the op touches
                 (request OR response), AFTER removing config.GENERIC_SCHEMAS.
                 If the set is empty post-exclusion, f5 is UNAVAILABLE.
  f6 description operation description, non-empty.

f1 and f3 are always available, so the mask can only ever fire on
{f2, f4, f5, f6}. We therefore report pair-level co-availability for those four,
and the headline: the % of within-service pairs where AT LEAST ONE of the four
is unavailable (the fraction of comparisons where the mask actually fires).

f2 has three definitions, reported as a sensitivity band (per Tasneem):

  f2_nonempty  operationId is a non-empty string.
  f2_codegen   non-empty AND not a syntactic code-generator signature
               (PRIMARY for the headline: a factual property of the string).
  f2_derived   non-empty AND introduces >=1 token beyond {method, path} tokens
               (a semantic judgement about informativeness; misfires on terse
               human names like 'Get Login', so reported but not primary).

Combinatorial identity used throughout (no pair enumeration):
  within a service of n operations, the number of pairs where both sides carry
  feature k is C(a_k, 2), where a_k = operations carrying k; total pairs C(n, 2).
  A pair has ALL four available iff both endpoints carry all four, so
  all-four-available pairs = C(c, 2) with c = operations carrying all four, and
  mask-fires pairs = C(n,2) - C(c,2).

Outputs:
  results/pair_availability.csv          per-service co-availability + mask-fire
  results/pair_availability_summary.csv  corpus table (micro + macro)

'summary' is deliberately NOT a mask feature; it stays in availability.py's
operation-level table as a descriptive statistic only.
"""

import argparse
import csv
import os
import re
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import filter as flt          # noqa: E402
import config                 # noqa: E402
import availability as av     # noqa: E402  reuse the filter-matched op walk + helpers
import matplotlib.pyplot as plt  # noqa: E402  (availability already set Agg backend)

HTTP_VERB_RE = "(get|post|put|delete|patch|head|options|trace)"

# GENERIC_SCHEMAS, normalised the same way schema names are (lower + strip
# non-alphanumerics) so 'ErrorResponse' -> 'errorresponse' matches.
_GENERIC = {re.sub(r"[^a-z0-9]", "", s.lower()) for s in config.GENERIC_SCHEMAS}


# ----------------------------------------------------------------------------
# f2 — three definitions
# ----------------------------------------------------------------------------

def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def is_codegen_placeholder(opid):
    """Syntactic signatures of code generators (factual property of the string).
    Deliberately does NOT flag terse human names like 'Get Login'."""
    s = opid.strip()
    ls = s.lower()
    if "/" in s or "{" in s or "}" in s:               # path baked into the id
        return True
    if re.search(r">\s*" + HTTP_VERB_RE + r"\b", ls):  # 'foo > POST'
        return True
    if re.search(r"using" + HTTP_VERB_RE + r"\b", ls):  # springdoc 'fooUsingGET'
        return True
    if re.search(r"_\d+$", s):                          # 'fooUsingGET_1' disambig
        return True
    return False


def is_derived_placeholder(opid, method, path):
    """Introduces no token beyond {method, path} -> not informative."""
    op_tok = _tokens(opid)
    if not op_tok:
        return True
    return op_tok.issubset(_tokens(method + " " + path))


def f2_flags(op_obj, method, path):
    """Return (f2_nonempty, f2_codegen, f2_derived) booleans."""
    opid = op_obj.get("operationId") if isinstance(op_obj, dict) else None
    if not (isinstance(opid, str) and opid.strip()):
        return False, False, False
    nonempty = True
    codegen = not is_codegen_placeholder(opid)
    derived = not is_derived_placeholder(opid, method, path)
    return nonempty, codegen, derived


# ----------------------------------------------------------------------------
# f5 — domain schema names touched (request OR response), generics removed
# ----------------------------------------------------------------------------

def _collect_schema_refs(node, out):
    """Recursively collect $ref targets that point at a schema/definition."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and ("/schemas/" in v or "/definitions/" in v):
                out.add(v.rsplit("/", 1)[-1])
            else:
                _collect_schema_refs(v, out)
    elif isinstance(node, list):
        for x in node:
            _collect_schema_refs(x, out)


def f5_available(op_obj, version, eff_params):
    """True iff the op touches >=1 NAMED schema that is not a generic schema.

    Named schemas only: an op with purely inline/anonymous schemas touches no
    *name*. No transitive resolution into components (a requestBody/response
    that is itself a component $ref is not followed)."""
    refs = set()
    if version == "2.0":
        for p in eff_params:
            if p.get("in") == "body":
                _collect_schema_refs(p.get("schema"), refs)
        if isinstance(op_obj, dict):
            _collect_schema_refs(op_obj.get("responses"), refs)
    else:
        if isinstance(op_obj, dict):
            _collect_schema_refs(op_obj.get("requestBody"), refs)
            _collect_schema_refs(op_obj.get("responses"), refs)
    domain = {re.sub(r"[^a-z0-9]", "", n.lower()) for n in refs} - _GENERIC
    return len(domain) > 0


# ----------------------------------------------------------------------------
# Per-service audit
# ----------------------------------------------------------------------------

def c2(x):
    return x * (x - 1) // 2


def audit_spec(path):
    spec, reason = flt.load_spec(path)
    if spec is None:
        return None, reason
    reason = flt.structural_check(spec)
    if reason:
        return None, reason
    version = flt.spec_version(spec)
    if version is None:
        return None, "not_openapi_2_or_3"

    ops = list(av.iter_operations(spec))
    # keep the same hard guarantee that our op set == filter.py's
    canonical, _ = flt.operations(spec, drop_admin=True)
    if {(m, p) for m, p, _, _ in ops} != set(canonical):
        raise AssertionError(f"operation set diverged from filter.py for {path}")

    n = len(ops)
    a = {"f2_codegen": 0, "f2_nonempty": 0, "f2_derived": 0,
         "f4_parameters": 0, "f5_schemas": 0, "f6_description": 0}
    c = {"codegen": 0, "nonempty": 0, "derived": 0}  # ops carrying ALL four

    for method, path_str, op_obj, path_item in ops:
        eff = av.effective_parameters(path_item, op_obj)
        f2_ne, f2_cg, f2_dv = f2_flags(op_obj, method, path_str)
        f4 = len(eff) > 0
        f5 = f5_available(op_obj, version, eff)
        f6 = av._nonempty_str(isinstance(op_obj, dict) and op_obj.get("description"))

        a["f2_nonempty"] += f2_ne
        a["f2_codegen"] += f2_cg
        a["f2_derived"] += f2_dv
        a["f4_parameters"] += f4
        a["f5_schemas"] += f5
        a["f6_description"] += f6

        base4 = f4 and f5 and f6
        c["nonempty"] += 1 if (f2_ne and base4) else 0
        c["codegen"] += 1 if (f2_cg and base4) else 0
        c["derived"] += 1 if (f2_dv and base4) else 0

    info = spec.get("info") or {}
    rec = {"spec_version": version, "n_operations": n, "n_pairs": c2(n),
           "title": info.get("title", "")}
    rec.update({f"a_{k}": v for k, v in a.items()})
    rec.update({f"c_all4_{k}": v for k, v in c.items()})
    return rec, None


# ----------------------------------------------------------------------------
# Aggregation / outputs
# ----------------------------------------------------------------------------

COAVAIL_FEATURES = ["f2_codegen", "f2_nonempty", "f2_derived",
                    "f4_parameters", "f5_schemas", "f6_description"]
MASK_DEFS = ["codegen", "nonempty", "derived"]


def _pct(num, den):
    return (100.0 * num / den) if den else None


def _fmt(v):
    return "" if v is None else f"{v:.3f}"


def build_summary(records):
    """Strata are (version x source). The per-source split is required by
    Sec. 7: S1 (Bogner's peer-reviewed corpus) and S2 (the fresh crawl) must be
    reportable separately, not silently pooled. Empty strata are skipped."""
    rows = []
    sources = ["all"] + sorted({r.get("source", "") for r in records} - {""})
    for version, source in [(v, s) for v in ("all", "2.0", "3.x") for s in sources]:
        bucket = _stratum(records, version, source)
        if not bucket:
            continue
        tot_pairs = sum(r["n_pairs"] for r in bucket)
        with_pairs = [r for r in bucket if r["n_pairs"] > 0]

        # per-feature co-availability
        for feat in COAVAIL_FEATURES:
            co = sum(c2(r[f"a_{feat}"]) for r in bucket)
            micro = _pct(co, tot_pairs)
            ratios = [c2(r[f"a_{feat}"]) / r["n_pairs"] for r in with_pairs]
            macro = (100.0 * sum(ratios) / len(ratios)) if ratios else None
            rows.append({"kind": "coavail", "key": feat, "version": version,
                         "source": source,
                         "micro_pct": _fmt(micro), "macro_pct": _fmt(macro),
                         "macro_n_services": len(ratios)})

        # composite mask-fire  (>=1 of the four unavailable)
        for d in MASK_DEFS:
            allfour = sum(c2(r[f"c_all4_{d}"]) for r in bucket)
            micro = _pct(tot_pairs - allfour, tot_pairs)
            ratios = [1 - c2(r[f"c_all4_{d}"]) / r["n_pairs"] for r in with_pairs]
            macro = (100.0 * sum(ratios) / len(ratios)) if ratios else None
            rows.append({"kind": "maskfire", "key": d, "version": version,
                         "source": source,
                         "micro_pct": _fmt(micro), "macro_pct": _fmt(macro),
                         "macro_n_services": len(ratios)})
    return rows


def _stratum(records, version, source):
    bucket = records
    if version != "all":
        bucket = [r for r in bucket if r["spec_version"] == version]
    if source != "all":
        bucket = [r for r in bucket if r.get("source") == source]
    return bucket


def maskfire_distribution(records):
    """Distribution of the per-service mask-fire rate ACROSS services, so a
    single mean cannot hide a split (all-services-~50% vs half-0%/half-100%).
    Reports quartiles, the count of services with 0% mask-fire (complete specs
    the mask never changes), and the % of services where the mask matters."""
    rows = []
    sources = ["all"] + sorted({r.get("source", "") for r in records} - {""})
    for d in MASK_DEFS:
        col = f"c_all4_{d}"
        for version, source in [(v, s) for v in ("all", "2.0", "3.x") for s in sources]:
            bucket = [r for r in _stratum(records, version, source) if r["n_pairs"] > 0]
            if not bucket:
                continue
            vals = sorted(100 * (1 - c2(r[col]) / r["n_pairs"]) for r in bucket)
            n = len(vals)
            zero = sum(1 for v in vals if v == 0.0)
            full = sum(1 for v in vals if v == 100.0)
            q = (statistics.quantiles(vals, n=4, method="inclusive")
                 if n >= 2 else [vals[0], vals[0], vals[0]])
            rows.append({
                "f2_def": d, "version": version, "source": source,
                "n_services": n,
                "zero_count": zero, "zero_pct": f"{100 * zero / n:.3f}",
                "matters_pct": f"{100 * (n - zero) / n:.3f}",
                "full_count": full, "full_pct": f"{100 * full / n:.3f}",
                "min": f"{vals[0]:.3f}", "q1": f"{q[0]:.3f}",
                "median": f"{q[1]:.3f}", "q3": f"{q[2]:.3f}", "max": f"{vals[-1]:.3f}",
                "mean": f"{statistics.fmean(vals):.3f}",
            })
    return rows


def write_distribution(rows, out_path):
    cols = ["f2_def", "version", "source", "n_services", "zero_count", "zero_pct",
            "matters_pct", "full_count", "full_pct",
            "min", "q1", "median", "q3", "max", "mean"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def make_maskfire_histogram(vals_all, vals_2, vals_3, out_path):
    """Fig 2 — the DISTRIBUTION of the per-service mask-fire rate (primary
    f2=codegen), as a histogram. The bimodality (a tower at 0% and a tower at
    100%) is the finding; a bar chart of the mean would hide exactly that."""
    bins = list(range(0, 101, 5))  # 20 bins of 5 percentage points, edges 0..100
    fig, axes = plt.subplots(2, 1, figsize=(9, 8))

    # (a) all services, raw counts — the two towers carry the finding
    ax = axes[0]
    e0 = sum(1 for v in vals_all if v == 0.0)
    e100 = sum(1 for v in vals_all if v == 100.0)
    ax.hist(vals_all, bins=bins, color="#4C72B0", edgecolor="white")
    ax.set_xlim(0, 100)
    ax.set_title(f"(a) All services (n={len(vals_all)})", loc="left", fontsize=10)
    ax.set_ylabel("services")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.annotate(f"{e0} services at exactly 0%\n(complete specs; mask never fires)",
                xy=(2.5, e0), xytext=(18, e0 * 0.88), fontsize=8, va="top",
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate(f"{e100} services at exactly 100%\n(mask fires on every pair)",
                xy=(97.5, e100), xytext=(46, e100 * 1.02), fontsize=8, va="bottom",
                ha="left", arrowprops=dict(arrowstyle="->", lw=0.8))

    # (b) by version, as % of that version's services (n differs, so normalise)
    ax2 = axes[1]
    for vals, color, lab in ((vals_2, "#4C72B0", "OpenAPI 2.0"),
                             (vals_3, "#DD8452", "OpenAPI 3.x")):
        w = [100.0 / len(vals)] * len(vals) if vals else []
        ax2.hist(vals, bins=bins, weights=w, histtype="step", linewidth=1.7,
                 color=color, label=f"{lab} (n={len(vals)})")
    ax2.set_xlim(0, 100)
    ax2.set_title("(b) By version (share of each version's services)", loc="left", fontsize=10)
    ax2.set_xlabel("per-service mask-fire rate  (% of within-service pairs where the mask fires)")
    ax2.set_ylabel("% of services")
    ax2.grid(axis="y", linestyle=":", alpha=0.5)
    ax2.legend(fontsize=8)

    fig.suptitle("Fig 2 — Mask-fire rate is bimodal across services (f2 = codegen)", fontsize=11)
    caption = (
        "Per-service % of within-service pairs where at least one of f2,f4,f5,f6 is unavailable (the mask fires). "
        "Bins of 5 pts; the leftmost bar is dominated by services at exactly 0% (complete specs), the rightmost by "
        "exactly 100%. The bimodality is the point: report 'the mask matters for 66.9% of services', not the 48.6% mean."
    )
    fig.text(0.5, 0.005, caption, ha="center", va="bottom", fontsize=6.5, wrap=True)
    fig.tight_layout(rect=(0, 0.045, 1, 0.97))
    fmt = "pdf" if out_path.lower().endswith(".pdf") else None
    meta = ({"CreationDate": None, "Creator": "ilsc/pair_availability.py", "Producer": ""}
            if fmt == "pdf" else None)
    fig.savefig(out_path, format=fmt, metadata=meta)
    plt.close(fig)


PER_SERVICE_COLUMNS = [
    "clean_file", "title", "provider", "source", "spec_version", "n_operations", "n_pairs",
    "a_f2_codegen", "a_f2_nonempty", "a_f2_derived",
    "a_f4_parameters", "a_f5_schemas", "a_f6_description",
    "c_all4_codegen", "c_all4_nonempty", "c_all4_derived",
    "coavail_pct_f2_codegen", "coavail_pct_f4_parameters",
    "coavail_pct_f5_schemas", "coavail_pct_f6_description",
    "maskfire_pct_codegen", "maskfire_pct_nonempty", "maskfire_pct_derived",
]


def write_per_service(records, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PER_SERVICE_COLUMNS)
        w.writeheader()
        for r in sorted(records, key=lambda x: x["clean_file"]):
            np_ = r["n_pairs"]
            row = {c: r.get(c, "") for c in PER_SERVICE_COLUMNS}
            for feat in ("f2_codegen", "f4_parameters", "f5_schemas", "f6_description"):
                row[f"coavail_pct_{feat}"] = _fmt(_pct(c2(r[f"a_{feat}"]), np_))
            for d in MASK_DEFS:
                row[f"maskfire_pct_{d}"] = _fmt(_pct(np_ - c2(r[f"c_all4_{d}"]), np_))
            w.writerow(row)


def write_summary(rows, out_path):
    cols = ["kind", "key", "version", "source", "micro_pct", "macro_pct",
            "macro_n_services"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Day 3 pair-level co-availability.")
    ap.add_argument("--specs-dir", default=os.path.join(_ROOT, "specs", "clean"))
    ap.add_argument("--out-dir", default=os.path.join(_ROOT, "results"))
    ap.add_argument("--fig", default=os.path.join(_ROOT, "figures", "fig2_maskfire_distribution.pdf"))
    ap.add_argument("--manifest",
                    default=os.path.join(_ROOT, "results", "manifest.csv"),
                    help="supplies provider and the provenance (source) column")
    args = ap.parse_args(argv)

    specs_dir = os.path.abspath(args.specs_dir)
    files = sorted(os.path.join(specs_dir, n) for n in os.listdir(specs_dir)
                   if n.endswith((".json", ".yaml", ".yml")))
    if not files:
        sys.exit(f"no specs in {specs_dir}")

    provider, source_of = {}, {}
    if args.manifest and os.path.exists(args.manifest):
        with open(args.manifest, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                k = r.get("clean_file") or r.get("rel")
                if k:
                    provider[k] = r.get("provider", "")
                    source_of[k] = r.get("source", "")

    records, skips = [], []
    for path in files:
        cf = os.path.basename(path)
        rec, reason = audit_spec(path)
        if rec is None:
            skips.append((cf, reason))
            continue
        rec["clean_file"] = cf
        rec["provider"] = provider.get(cf, "")
        rec["source"] = source_of.get(cf, "")
        records.append(rec)

    os.makedirs(args.out_dir, exist_ok=True)
    write_per_service(records, os.path.join(args.out_dir, "pair_availability.csv"))
    summary = build_summary(records)
    write_summary(summary, os.path.join(args.out_dir, "pair_availability_summary.csv"))
    dist = maskfire_distribution(records)
    write_distribution(dist, os.path.join(args.out_dir, "pair_maskfire_distribution.csv"))

    def maskfire_vals(bucket):
        return [100 * (1 - c2(r["c_all4_codegen"]) / r["n_pairs"])
                for r in bucket if r["n_pairs"] > 0]
    os.makedirs(os.path.dirname(os.path.abspath(args.fig)), exist_ok=True)
    make_maskfire_histogram(
        maskfire_vals(records),
        maskfire_vals([r for r in records if r["spec_version"] == "2.0"]),
        maskfire_vals([r for r in records if r["spec_version"] == "3.x"]),
        args.fig)

    # ---- console report -----------------------------------------------------
    total_pairs = sum(r["n_pairs"] for r in records)
    n2 = sum(1 for r in records if r["spec_version"] == "2.0")
    n3 = sum(1 for r in records if r["spec_version"] == "3.x")
    print(f"services {len(records)} (2.0 {n2}, 3.x {n3})   "
          f"within-service pairs {total_pairs:,}   skipped {len(skips)}")
    look = {(r["kind"], r["key"], r["version"]): r for r in summary}
    print("\nPAIR co-availability (ALL)      micro%    macro%")
    for feat in COAVAIL_FEATURES:
        r = look[("coavail", feat, "all")]
        print(f"  {feat:<16}{r['micro_pct']:>10}{r['macro_pct']:>10}")
    print("\nMASK FIRES  (>=1 of f2,f4,f5,f6 unavailable), ALL   micro%    macro%")
    for d in MASK_DEFS:
        r = look[("maskfire", d, "all")]
        tag = "  <-- PRIMARY" if d == "codegen" else ""
        print(f"  f2={d:<10}{r['micro_pct']:>10}{r['macro_pct']:>10}{tag}")
    # spread of the headline across f2 definitions
    for ver in ("all", "2.0", "3.x"):
        cells = [look[("maskfire", d, ver)]["micro_pct"] for d in MASK_DEFS]
        if any(c == "" for c in cells):
            continue  # empty version bucket (e.g. no 3.x specs)
        vals = [float(c) for c in cells]
        print(f"  micro spread [{ver}] across f2 defs: "
              f"{min(vals):.2f}..{max(vals):.2f}  (range {max(vals)-min(vals):.2f} pts)")

    print("\nMASK-FIRE DISTRIBUTION across services (f2=codegen, PRIMARY)")
    print(f"  {'ver':<5}{'n':>6}{'0%':>7}{'0%pct':>8}{'matters%':>10}"
          f"{'Q1':>8}{'median':>8}{'Q3':>8}{'100%':>7}")
    for r in dist:
        if r["f2_def"] != "codegen":
            continue
        print(f"  {r['version']:<5}{r['n_services']:>6}{r['zero_count']:>7}"
              f"{r['zero_pct']:>8}{r['matters_pct']:>10}{r['q1']:>8}"
              f"{r['median']:>8}{r['q3']:>8}{r['full_count']:>7}")


if __name__ == "__main__":
    main()

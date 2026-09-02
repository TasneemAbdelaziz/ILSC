"""
ILSC — Day 3 (Tasneem): field-availability study.

Reports, across every spec in ``specs/clean/``, the fraction of operations that
carry each documentation field. This is the empirical justification for the
availability mask (RQ2), so the numbers must be exact and the set of operations
must be *identical* to the one ``src/filter.py`` used to build the corpus.

To guarantee that identity rather than approximate it, the operation set is
sourced directly from ``filter.py``: this module imports ``ADMIN_PATHS``,
``HTTP_METHODS``, ``operations`` and ``spec_version`` from it, and asserts per
spec that its own walk yields exactly ``filter.operations(spec)``. No operation
definition is re-derived here.

Fields measured (per operation, admin endpoints already dropped as in filter.py):

  description        operation.description is a non-empty string
  summary            operation.summary is a non-empty string
  operationId        operation.operationId is a non-empty string
  parameters         >=1 effective parameter (path-level + operation-level)
  request_schema     2.0: an ``in: body`` parameter carrying a ``schema``
                     3.x: ``requestBody`` with ``content[*].schema`` (or a $ref)
  response_schema    2.0: any ``responses[code].schema``
                     3.x: any ``responses[code].content[*].schema`` (or a $ref)
  any_schema         request_schema OR response_schema  (mere presence of a
                     schema; reported on its own as a descriptive statistic)

NOTE (see D-08). This module measures per-operation *presence*. It is NOT the
mask feature f5. The mask's f5 is the set of DOMAIN schema NAMES an operation
touches AFTER removing config.GENERIC_SCHEMAS (empty ⇒ unavailable), evaluated
at the PAIR level; that lives in src/pair_availability.py. `any_schema` here
(mere schema presence) is a looser, descriptive quantity and must not be read as
f5. Likewise `summary` below is descriptive only — it is not one of the six
similarity features.

Denominators (decision C, per Tasneem):

  * Every field uses the all-operations denominator, EXCEPT that request_schema
    is reported twice and both are always emitted together:
      - request_schema_rate_body_eligible : denominator = POST/PUT/PATCH ops.
        The honest documentation-completeness number; PRIMARY.
      - request_schema_rate_all_ops       : denominator = all operations.
        Keeps Fig 1 bars comparable with the other fields (which all use the
        all-operations denominator). Shown in the figure; caption states this.

Averaging (decision D): the corpus summary reports BOTH, side by side —
  * micro : operation-weighted (pool all operations across services).
  * macro : per-service mean (each service weighted equally).
Services with a zero denominator (e.g. no POST/PUT/PATCH op, for the body-
eligible request rate) are excluded from that macro mean and the count of
exclusions is logged in the summary.

A local ``$ref`` in a requestBody / response is treated as "schema present"
without resolving it (a referenced body is still a documented body).

Reproducibility notes:
  * Deterministic full census — no sampling, so config.SEED is not used.
  * ``config.MIN_OPERATIONS`` is used only as an input sanity invariant: clean
    survivors must have >= MIN_OPERATIONS operations. Benchmark systems may not
    (D-06), so a violation is logged, not fatal.
  * Admin-path handling comes from filter.py's regex, which is BROADER than the
    ``config.ADMIN_PATHS`` tuple (the tuple is the D-07 list; the corpus was in
    fact built with the regex). This module matches the corpus, i.e. filter.py.
    The discrepancy is flagged here but neither file is modified.

Every skipped spec and every input-invariant violation is logged to
``results/availability_skiplog.csv``.

Outputs:
  results/availability.csv          per-service rates
  results/availability_summary.csv  corpus-level table (micro + macro)
  figures/fig1_availability.pdf     grouped bar chart, vector
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")            # headless, deterministic
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)        # for: import filter
sys.path.insert(0, _ROOT)        # for: import config

import filter as flt             # noqa: E402  operation definition (source of truth)
import config                    # noqa: E402  project constants

# Request-body-eligible methods for the body-eligible denominator (decision C).
BODY_METHODS = ("POST", "PUT", "PATCH")

# Field order used everywhere (CSV columns, summary rows, figure bars).
# (label, record-count-key, denominator-kind)
FIELD_SPECS = [
    ("description",    "n_description",                 "all_ops"),
    ("summary",        "n_summary",                     "all_ops"),
    ("operationId",    "n_operation_id",                "all_ops"),
    ("parameters",     "n_parameters",                  "all_ops"),
    ("request_schema", "n_request_schema",              "all_ops"),
    ("request_schema", "n_request_schema_body_eligible", "body_eligible"),
    ("response_schema", "n_response_schema",            "all_ops"),
    ("any_schema",     "n_any_schema",                  "all_ops"),
]

# Fields drawn in the figure (all use the all-operations denominator so the
# bars are cross-comparable; request_schema here is the all-ops variant).
FIGURE_FIELDS = [
    ("description",     "n_description"),
    ("summary",         "n_summary"),
    ("operationId",     "n_operation_id"),
    ("parameters",      "n_parameters"),
    ("request_schema",  "n_request_schema"),
    ("response_schema", "n_response_schema"),
    ("any_schema",      "n_any_schema"),
]

VERSIONS = ("2.0", "3.x")


# ----------------------------------------------------------------------------
# Extraction (must match filter.py exactly)
# ----------------------------------------------------------------------------

def _param_dicts(obj):
    """Return the parameter objects (dicts only) declared on ``obj``."""
    if not isinstance(obj, dict):
        return []
    params = obj.get("parameters")
    if not isinstance(params, list):
        return []
    return [p for p in params if isinstance(p, dict)]


def effective_parameters(path_item, op_obj):
    """Path-level parameters apply to every operation on the path; union them
    with the operation-level ones. Membership only — no name/in de-duplication,
    since we ask "does this operation expose any parameter at all?"."""
    return _param_dicts(path_item) + _param_dicts(op_obj)


def has_request_schema(op_obj, version, eff_params):
    if version == "2.0":
        return any(p.get("in") == "body" and "schema" in p for p in eff_params)
    if not isinstance(op_obj, dict):
        return False
    body = op_obj.get("requestBody")
    if not isinstance(body, dict):
        return False
    if "$ref" in body:
        return True
    content = body.get("content")
    if isinstance(content, dict):
        return any(isinstance(mv, dict) and "schema" in mv for mv in content.values())
    return False


def has_response_schema(op_obj, version):
    if not isinstance(op_obj, dict):
        return False
    responses = op_obj.get("responses")
    if not isinstance(responses, dict):
        return False
    for code, resp in responses.items():
        if isinstance(code, str) and code.lower().startswith("x-"):
            continue
        if not isinstance(resp, dict):
            continue
        if "$ref" in resp:
            return True
        if version == "2.0":
            if "schema" in resp:
                return True
        else:
            content = resp.get("content")
            if isinstance(content, dict) and any(
                isinstance(mv, dict) and "schema" in mv for mv in content.values()
            ):
                return True
    return False


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def iter_operations(spec):
    """Yield (METHOD, path, op_obj, path_item) for every non-admin operation,
    replicating filter.operations(spec, drop_admin=True) precisely."""
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        is_admin = bool(flt.ADMIN_PATHS.match(str(path)))
        if is_admin:
            continue
        for method in item:
            if method.lower() not in flt.HTTP_METHODS:
                continue
            yield method.upper(), str(path), item[method], item


def audit_spec(path):
    """Return (record, None) or (None, skip_reason) for one spec file."""
    spec, reason = flt.load_spec(path)
    if spec is None:
        return None, reason
    reason = flt.structural_check(spec)
    if reason:
        return None, reason
    version = flt.spec_version(spec)
    if version is None:
        return None, "not_openapi_2_or_3"

    ops = list(iter_operations(spec))

    # Hard guarantee: our operation set is byte-identical to filter.py's.
    canonical, _ = flt.operations(spec, drop_admin=True)
    mine = {(m, p) for m, p, _, _ in ops}
    if mine != set(canonical):
        raise AssertionError(
            f"operation set diverged from filter.py for {path}: "
            f"only_here={mine - set(canonical)} only_filter={set(canonical) - mine}"
        )

    rec = {
        "spec_version": version,
        "n_operations": len(ops),
        "n_body_eligible": 0,
        "n_description": 0,
        "n_summary": 0,
        "n_operation_id": 0,
        "n_parameters": 0,
        "n_request_schema": 0,
        "n_request_schema_body_eligible": 0,
        "n_response_schema": 0,
        "n_any_schema": 0,
    }
    info = spec.get("info") or {}
    rec["title"] = info.get("title", "")

    for method, _path, op_obj, path_item in ops:
        eff = effective_parameters(path_item, op_obj)
        req = has_request_schema(op_obj, version, eff)
        resp = has_response_schema(op_obj, version)
        body_eligible = method in BODY_METHODS

        rec["n_description"] += _nonempty_str(isinstance(op_obj, dict) and op_obj.get("description"))
        rec["n_summary"] += _nonempty_str(isinstance(op_obj, dict) and op_obj.get("summary"))
        rec["n_operation_id"] += _nonempty_str(isinstance(op_obj, dict) and op_obj.get("operationId"))
        rec["n_parameters"] += 1 if eff else 0
        rec["n_request_schema"] += 1 if req else 0
        rec["n_response_schema"] += 1 if resp else 0
        rec["n_any_schema"] += 1 if (req or resp) else 0
        if body_eligible:
            rec["n_body_eligible"] += 1
            if req:
                rec["n_request_schema_body_eligible"] += 1

    return rec, None


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------

def _rate(num, den):
    return (num / den) if den else None


def _fmt_rate(value):
    return "" if value is None else f"{value:.6f}"


def build_summary(records):
    """Return rows for availability_summary.csv, one per (field, denom, version).

    micro = operation-weighted (pool operations);
    macro = per-service mean (each service equal, zero-denominator services
    excluded and counted).
    """
    rows = []
    for version in ("all", "2.0", "3.x"):
        bucket = records if version == "all" else [r for r in records if r["spec_version"] == version]
        for label, count_key, denom_kind in FIELD_SPECS:
            denom_key = "n_operations" if denom_kind == "all_ops" else "n_body_eligible"

            micro_with = sum(r[count_key] for r in bucket)
            micro_den = sum(r[denom_key] for r in bucket)

            per_service, excluded = [], 0
            for r in bucket:
                d = r[denom_key]
                if d:
                    per_service.append(r[count_key] / d)
                else:
                    excluded += 1
            macro = (sum(per_service) / len(per_service)) if per_service else None

            rows.append({
                "field": label,
                "denominator": denom_kind,
                "version": version,
                "micro_n_with": micro_with,
                "micro_n_denom": micro_den,
                "micro_pct": "" if not micro_den else f"{100 * micro_with / micro_den:.3f}",
                "macro_mean_pct": "" if macro is None else f"{100 * macro:.3f}",
                "macro_n_services": len(per_service),
                "macro_n_services_excluded": excluded,
            })
    return rows


def summary_lookup(summary_rows):
    """(field, denominator, version) -> row, for the figure."""
    return {(r["field"], r["denominator"], r["version"]): r for r in summary_rows}


# ----------------------------------------------------------------------------
# Outputs
# ----------------------------------------------------------------------------

PER_SERVICE_COLUMNS = [
    "clean_file", "title", "provider", "spec_version",
    "n_operations", "n_body_eligible",
    "n_description", "n_summary", "n_operation_id", "n_parameters",
    "n_request_schema", "n_request_schema_body_eligible",
    "n_response_schema", "n_any_schema",
    "rate_description", "rate_summary", "rate_operation_id", "rate_parameters",
    "rate_request_schema_all_ops", "rate_request_schema_body_eligible",
    "rate_response_schema", "rate_any_schema",
]


def write_per_service(records, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PER_SERVICE_COLUMNS)
        w.writeheader()
        for r in sorted(records, key=lambda x: x["clean_file"]):
            n = r["n_operations"]
            row = {c: r.get(c, "") for c in PER_SERVICE_COLUMNS}
            row["rate_description"] = _fmt_rate(_rate(r["n_description"], n))
            row["rate_summary"] = _fmt_rate(_rate(r["n_summary"], n))
            row["rate_operation_id"] = _fmt_rate(_rate(r["n_operation_id"], n))
            row["rate_parameters"] = _fmt_rate(_rate(r["n_parameters"], n))
            row["rate_request_schema_all_ops"] = _fmt_rate(_rate(r["n_request_schema"], n))
            row["rate_request_schema_body_eligible"] = _fmt_rate(
                _rate(r["n_request_schema_body_eligible"], r["n_body_eligible"]))
            row["rate_response_schema"] = _fmt_rate(_rate(r["n_response_schema"], n))
            row["rate_any_schema"] = _fmt_rate(_rate(r["n_any_schema"], n))
            w.writerow(row)


SUMMARY_COLUMNS = [
    "field", "denominator", "version",
    "micro_n_with", "micro_n_denom", "micro_pct",
    "macro_mean_pct", "macro_n_services", "macro_n_services_excluded",
]


def write_summary(summary_rows, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        w.writerows(summary_rows)


def write_skiplog(skips, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["clean_file", "reason"])
        w.writerows(skips)


def make_figure(summary_rows, out_path, n_services, n_ops):
    look = summary_lookup(summary_rows)
    labels = [lbl.replace("_", "\n") for lbl, _ in FIGURE_FIELDS]
    x = range(len(FIGURE_FIELDS))
    width = 0.38
    colors = {"2.0": "#4C72B0", "3.x": "#DD8452"}

    def pct(field, version, kind):  # kind: "micro_pct" or "macro_mean_pct"
        row = look.get((field, "all_ops", version))
        if not row or row[kind] == "":
            return 0.0
        return float(row[kind])

    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for ax, kind, title in (
        (axes[0], "micro_pct", "(a) Operation-weighted (micro)"),
        (axes[1], "macro_mean_pct", "(b) Per-service mean (macro)"),
    ):
        for i, version in enumerate(VERSIONS):
            offs = (i - 0.5) * width
            vals = [pct(lbl, version, kind) for lbl, _ in FIGURE_FIELDS]
            bars = ax.bar([xi + offs for xi in x], vals, width,
                          label=f"OpenAPI {version}", color=colors[version])
            ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=7)
        ax.set_ylim(0, 105)
        ax.set_ylabel("% of operations")
        ax.set_title(title, fontsize=10, loc="left")
        ax.grid(axis="y", linestyle=":", alpha=0.5)
        ax.legend(loc="lower right", fontsize=8)

    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(labels, fontsize=8)

    fig.suptitle("Fig 1 — Field availability across specs/clean "
                 f"(n={n_services} services, {n_ops:,} operations)", fontsize=11)
    caption = (
        "Admin endpoints excluded (matching src/filter.py). request_schema shown over ALL operations for "
        "cross-field comparability; the primary documentation-completeness rate uses the body-eligible "
        "(POST/PUT/PATCH) denominator and is reported in results/availability_summary.csv. "
        "any_schema = carries a request OR response schema (schema presence, descriptive; "
        "NOT mask feature f5 -- see D-08 and src/pair_availability.py)."
    )
    fig.text(0.5, 0.005, caption, ha="center", va="bottom", fontsize=6.5, wrap=True)
    fig.tight_layout(rect=(0, 0.045, 1, 0.97))
    # Deterministic PDF: omit the creation timestamp so bytes are reproducible.
    fmt = "pdf" if out_path.lower().endswith(".pdf") else None
    meta = {"CreationDate": None, "Creator": "ilsc/availability.py", "Producer": ""} if fmt == "pdf" else None
    fig.savefig(out_path, format=fmt, metadata=meta)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def load_manifest_ops(manifest_path):
    """clean_file -> n_operations, for a cross-check against the corpus build."""
    out = {}
    with open(manifest_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row.get("clean_file") or row.get("rel")
            if key:
                out[key] = int(row["n_operations"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Day 3 field-availability study.")
    ap.add_argument("--specs-dir", default=os.path.join(_ROOT, "specs", "clean"))
    ap.add_argument("--out-dir", default=os.path.join(_ROOT, "results"))
    ap.add_argument("--fig", default=os.path.join(_ROOT, "figures", "fig1_availability.pdf"))
    ap.add_argument("--manifest", default=None,
                    help="optional manifest.csv to cross-check n_operations per service")
    ap.add_argument("--provider-from-manifest", action="store_true",
                    help="read the provider column from --manifest instead of leaving it blank")
    args = ap.parse_args(argv)

    specs_dir = os.path.abspath(args.specs_dir)
    if not os.path.isdir(specs_dir):
        sys.exit(f"specs dir not found: {specs_dir}")

    files = sorted(
        os.path.join(specs_dir, n) for n in os.listdir(specs_dir)
        if n.endswith((".json", ".yaml", ".yml"))
    )
    if not files:
        sys.exit(f"no specs in {specs_dir}")

    manifest_ops, manifest_provider = {}, {}
    if args.manifest:
        with open(args.manifest, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = row.get("clean_file") or row.get("rel")
                if not key:
                    continue
                manifest_ops[key] = int(row["n_operations"])
                manifest_provider[key] = row.get("provider", "")

    records, skips, invariant_notes = [], [], []
    mismatches = []
    for path in files:
        clean_file = os.path.basename(path)
        rec, reason = audit_spec(path)
        if rec is None:
            skips.append((clean_file, reason))
            continue
        rec["clean_file"] = clean_file
        rec["provider"] = manifest_provider.get(clean_file, "") if args.provider_from_manifest else ""

        # Input invariant (uses config.MIN_OPERATIONS): clean survivors carry
        # >= MIN_OPERATIONS ops. Benchmarks legitimately may not (D-06) -> log.
        if rec["n_operations"] < config.MIN_OPERATIONS:
            invariant_notes.append(
                (clean_file, f"below_MIN_OPERATIONS_{config.MIN_OPERATIONS}:{rec['n_operations']}"))

        # Cross-check against the corpus manifest if given.
        if manifest_ops and clean_file in manifest_ops and manifest_ops[clean_file] != rec["n_operations"]:
            mismatches.append((clean_file, manifest_ops[clean_file], rec["n_operations"]))

        records.append(rec)

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.fig)), exist_ok=True)

    write_per_service(records, os.path.join(args.out_dir, "availability.csv"))
    summary_rows = build_summary(records)
    write_summary(summary_rows, os.path.join(args.out_dir, "availability_summary.csv"))
    write_skiplog(skips + invariant_notes, os.path.join(args.out_dir, "availability_skiplog.csv"))

    total_ops = sum(r["n_operations"] for r in records)
    make_figure(summary_rows, args.fig, len(records), total_ops)

    # ---- console report -----------------------------------------------------
    n2 = sum(1 for r in records if r["spec_version"] == "2.0")
    n3 = sum(1 for r in records if r["spec_version"] == "3.x")
    print(f"services: {len(records)}  (2.0: {n2}, 3.x: {n3})   operations: {total_ops:,}")
    if skips:
        print(f"skipped: {len(skips)} (see availability_skiplog.csv)")
    if invariant_notes:
        print(f"below-MIN_OPERATIONS: {len(invariant_notes)} (logged; expected for benchmarks, D-06)")
    if manifest_ops:
        print(f"manifest cross-check: {len(mismatches)} mismatches"
              + ("" if not mismatches else f" -> {mismatches[:5]}"))
    print()
    print(f"{'field':<16}{'denom':<14}{'ver':<5}{'micro%':>9}{'macro%':>9}")
    for row in summary_rows:
        if row["version"] == "all":
            print(f"{row['field']:<16}{row['denominator']:<14}{row['version']:<5}"
                  f"{row['micro_pct'] or 'NA':>9}{row['macro_mean_pct'] or 'NA':>9}")


if __name__ == "__main__":
    main()

"""
ILSC — Day 5 (Tasneem): benchmark preparation.

Builds the benchmark set for the code-correlation study (Exp. 3) and the
perturbation experiment (Exp. 2), and records **where every specification came
from**. Provenance is data here, not a footnote: D-16 splits Exp. 3 into a
hand-written condition and a generated-from-source condition, and that split is
only auditable if each system carries its origin, source URL and pin.

Systems
-------
sockshop      5 services, Swagger 2.0, specifications **hand-written** and
              independent of the service source code. The independent condition
              in Exp. 3 (rho_independent).
trainticket   34 services, Swagger 2.0, specifications **generated from the
              source** by Springfox `/v2/api-docs` introspection (see D-16).
              Published as one combined document in the replication package of
              arXiv 2607.12101 (Zenodo 10.5281/zenodo.21342161, CC-BY-4.0);
              this script splits it into per-service specifications.

Why the split is needed. ILSC is a *within-service* metric: it compares the
operations of one service against each other. The published Train Ticket
baseline is a single merged document ("Train-ticket All Services Combined"), so
measuring it as-is would treat 34 services as one 211-operation service and
produce C(211,2)=22,155 meaningless cross-service pairs instead of the 794 real
within-service ones. Every operation in the baseline carries exactly one
`ts-*-service` tag, which is Train Ticket's own deployable-service identity, so
the split is read off the artifact rather than guessed.

Splitting rules
---------------
* Group operations by their single `ts-*-service` tag.
* Carry path-level keys (e.g. a shared `parameters` list) onto each path a
  service keeps, so an operation never loses an inherited parameter.
* Prune `definitions` to the **transitive** `$ref` closure reachable from that
  service's operations, then assert no dangling `$ref` remains. Copying all 197
  definitions into all 34 files would be lossless too, but adds ~2.9 MB of
  duplication for a median of 2 direct refs per service.
* Assert the operation multiset is preserved exactly: the union of the per-service
  (METHOD, path) sets must equal the baseline's. A split that gained or lost an
  operation would silently move every pair count downstream.

The operation definition itself is imported from ``filter.py`` (D-07 admin
stripping included), so benchmark and corpus counts mean the same thing. Note
that D-07's regex is root-anchored, so it strips Sock Shop's ``/health`` but
matches nothing in Train Ticket, whose endpoints all sit under ``/api/v1/...``.
Per D-06 the ``< 3 operations`` corpus filter is **not** applied here.

Outputs
-------
  specs/benchmarks/<system>/*.json   per-service specifications
  results/benchmark_manifest.csv     one row per service, with provenance
  results/benchmark_split_log.csv    what the Train Ticket split did, and why
"""

import argparse
import csv
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import filter as flt          # noqa: E402  operation definition (source of truth)

# ---------------------------------------------------------------------------
# Provenance registry. Anything asserted here must be verifiable; where we do
# not have a pin we say so rather than inventing one.
# ---------------------------------------------------------------------------

SYSTEMS = {
    "sockshop": {
        "spec_origin": "hand-written",
        "spec_source_url": "https://github.com/microservices-demo",
        # These five files predate this script (present since Day 1-2) and no
        # upstream commit was recorded for them. Not pinning is a real
        # reproducibility gap; it is stated, not papered over.
        "spec_pin": "UNPINNED (in-repo since Day 1-2; upstream commit not recorded)",
    },
    "trainticket": {
        "spec_origin": "generated-from-source",
        "spec_source_url": "https://doi.org/10.5281/zenodo.21342161",
        "spec_pin": ("zenodo record 21342162; "
                     "sha256:12affbd0c65e81ae2102aa1ddd39a2141f23309d9383e2347fef5aeaddd6a553"),
    },
}

TS_TAG = re.compile(r"^ts-.*-service$")
REF = re.compile(r'"\$ref"\s*:\s*"#/definitions/([^"]+)"')


def c2(n):
    return n * (n - 1) // 2


# ---------------------------------------------------------------------------
# Train Ticket: split the combined baseline into per-service specifications
# ---------------------------------------------------------------------------

def _service_of(op_obj):
    """The single ts-*-service tag identifying the owning service."""
    tags = [t for t in (op_obj.get("tags") or []) if TS_TAG.match(str(t))]
    return tags[0] if len(tags) == 1 else None


def _closure(defs, seeds):
    """Transitive $ref closure over `definitions`, so no split file dangles."""
    seen, stack = set(), list(seeds)
    while stack:
        name = stack.pop()
        if name in seen or name not in defs:
            continue
        seen.add(name)
        stack.extend(REF.findall(json.dumps(defs[name])))
    return seen


def split_trainticket(baseline_path, out_dir):
    with open(baseline_path, encoding="utf-8") as fh:
        base = json.load(fh)

    defs = base.get("definitions") or {}
    per = {}          # service -> {path -> path_item}
    unassigned = []
    baseline_ops = set()

    for path, item in (base.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        shared = {k: v for k, v in item.items()
                  if k.lower() not in flt.HTTP_METHODS}      # e.g. path-level parameters
        for method, op in item.items():
            if method.lower() not in flt.HTTP_METHODS:
                continue
            baseline_ops.add((method.upper(), path))
            svc = _service_of(op) if isinstance(op, dict) else None
            if svc is None:
                unassigned.append((method.upper(), path))
                continue
            bucket = per.setdefault(svc, {})
            entry = bucket.setdefault(path, dict(shared))
            entry[method] = op

    if unassigned:
        raise AssertionError(f"{len(unassigned)} operations carry no single ts-*-service tag: "
                             f"{unassigned[:5]}")

    os.makedirs(out_dir, exist_ok=True)
    log_rows, written_ops = [], set()
    for svc, paths in sorted(per.items()):
        seeds = REF.findall(json.dumps(paths))
        keep = _closure(defs, seeds)
        spec = {
            "swagger": base.get("swagger", "2.0"),
            "info": {
                "title": svc,
                "version": str((base.get("info") or {}).get("version", "")),
                "description": (f"Train Ticket service '{svc}', split from the combined "
                                f"baseline specification (see results/benchmark_split_log.csv)."),
            },
            "paths": paths,
            "definitions": {k: defs[k] for k in sorted(keep)},
        }
        for key in ("host", "basePath", "schemes", "consumes", "produces"):
            if key in base:
                spec[key] = base[key]

        blob = json.dumps(spec, indent=1, sort_keys=False)
        dangling = sorted(set(REF.findall(blob)) - set(spec["definitions"]))
        if dangling:
            raise AssertionError(f"{svc}: dangling $refs after pruning: {dangling[:5]}")

        dest = os.path.join(out_dir, f"{svc}.json")
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(blob)

        ops, _ = flt.operations(spec, drop_admin=True)
        written_ops |= {(m, p) for m, p in ops}
        log_rows.append({
            "system": "trainticket",
            "service": svc,
            "file": os.path.basename(dest),
            "n_operations": len(ops),
            "n_paths": len(paths),
            "n_definitions_kept": len(keep),
            "n_definitions_total": len(defs),
            "reason": "split from combined baseline by ts-*-service tag; "
                      "definitions pruned to transitive $ref closure",
        })

    # the split must neither invent nor lose an operation
    if written_ops != baseline_ops:
        raise AssertionError(
            f"operation set changed in the split: "
            f"lost={sorted(baseline_ops - written_ops)[:5]} "
            f"gained={sorted(written_ops - baseline_ops)[:5]}")
    return log_rows, len(baseline_ops)


# ---------------------------------------------------------------------------
# Scan a prepared system directory
# ---------------------------------------------------------------------------

def scan_system(system, sys_dir):
    rows = []
    for name in sorted(os.listdir(sys_dir)):
        if not name.endswith((".json", ".yaml", ".yml")):
            continue
        path = os.path.join(sys_dir, name)
        spec, reason = flt.load_spec(path)
        if spec is None:
            raise AssertionError(f"{path}: {reason}")
        version = flt.spec_version(spec)
        ops, dropped = flt.operations(spec, drop_admin=True)
        meta = SYSTEMS[system]
        rows.append({
            "system": system,
            "service": os.path.splitext(name)[0],
            "spec_file": f"specs/benchmarks/{system}/{name}",
            "spec_origin": meta["spec_origin"],
            "spec_source_url": meta["spec_source_url"],
            "spec_pin": meta["spec_pin"],
            "spec_version": version,
            "n_operations": len(ops),
            "n_admin_dropped": len(dropped),
            "n_pairs": c2(len(ops)),
        })
    return rows


MANIFEST_COLUMNS = [
    "system", "service", "spec_file", "spec_origin", "spec_source_url", "spec_pin",
    "spec_version", "n_operations", "n_admin_dropped", "n_pairs",
    "system_n_services", "system_n_operations", "system_n_pairs",
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Day 5 benchmark preparation.")
    ap.add_argument("--tt-baseline", default=None,
                    help="path to the Zenodo baseline_spec.json; splits it into "
                         "specs/benchmarks/trainticket/ when given")
    ap.add_argument("--benchmarks-dir", default=os.path.join(_ROOT, "specs", "benchmarks"))
    ap.add_argument("--out-dir", default=os.path.join(_ROOT, "results"))
    args = ap.parse_args(argv)

    split_log = []
    if args.tt_baseline:
        split_log, n_base = split_trainticket(
            args.tt_baseline, os.path.join(args.benchmarks_dir, "trainticket"))
        print(f"train ticket: split {n_base} operations into {len(split_log)} services "
              f"(operation set preserved exactly)")

    rows = []
    for system in sorted(SYSTEMS):
        sys_dir = os.path.join(args.benchmarks_dir, system)
        if not os.path.isdir(sys_dir):
            print(f"  ! {system}: no directory at {sys_dir} — skipped")
            continue
        rows.extend(scan_system(system, sys_dir))

    # per-system totals, written onto every row of that system
    for system in {r["system"] for r in rows}:
        grp = [r for r in rows if r["system"] == system]
        tot_ops = sum(r["n_operations"] for r in grp)
        tot_pairs = sum(r["n_pairs"] for r in grp)
        for r in grp:
            r["system_n_services"] = len(grp)
            r["system_n_operations"] = tot_ops
            r["system_n_pairs"] = tot_pairs

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "benchmark_manifest.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["system"], r["service"])))

    if split_log:
        with open(os.path.join(args.out_dir, "benchmark_split_log.csv"), "w",
                  newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(split_log[0].keys()))
            w.writeheader()
            w.writerows(split_log)

    # ---- report --------------------------------------------------------------
    print(f"\n{'system':<14}{'origin':<24}{'services':>9}{'ops':>7}{'pairs':>8}"
          f"{'0-pair svcs':>13}")
    for system in sorted({r["system"] for r in rows}):
        grp = [r for r in rows if r["system"] == system]
        print(f"{system:<14}{grp[0]['spec_origin']:<24}{len(grp):>9}"
              f"{sum(r['n_operations'] for r in grp):>7}"
              f"{sum(r['n_pairs'] for r in grp):>8}"
              f"{sum(1 for r in grp if r['n_pairs'] == 0):>13}")
    print(f"{'TOTAL':<14}{'':<24}{len(rows):>9}"
          f"{sum(r['n_operations'] for r in rows):>7}"
          f"{sum(r['n_pairs'] for r in rows):>8}")


if __name__ == "__main__":
    main()

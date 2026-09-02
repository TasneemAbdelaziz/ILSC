"""
ILSC - Day 1-2 deliverable: the Gate 1 candidate shortlist.

Sec. 11, Day 1-2: "While filtering, keep a side list for Day 4: 5 obviously
single-domain specs and 5 obviously mixed ones, with a written note on why you
picked each." Gate 1 (Day 4) then requires the 5 cohesive services to score
clearly above the 5 mixed ones.

WHAT THIS SCRIPT IS, AND IS NOT
-------------------------------
It is a *browsing aid*. It surfaces a shortlist with enough context to read,
and nothing more. It does NOT choose the ten services.

That restriction is deliberate. The obvious way to automate the choice would be
to rank services by how many distinct top-level path segments they expose, and
call the diverse ones "mixed". But path tokens are feature f3 of ILSC itself.
Selecting the Gate 1 set with an ILSC feature and then testing whether ILSC
separates that set is circular: the gate would pass by construction and prove
nothing. The same objection applies to picking on operation names (f2),
parameters (f4) or schema names (f5).

So the shortlist below prints the signals as *context for a human reader* and
the final selection is made by reading each service's own account of its
business capability -- the one criterion independent of every ILSC feature. The
written justification for each pick lives in docs/gate1_expectations.md and must
cite the service's stated purpose, not its path structure.

The sheet leads with `n_tags`, the count of distinct OpenAPI `tags` the author
attached to their own operations. It is the one structural column that is not an
ILSC feature, and it is a far better guide than path shape: the AWS RPC-style
specs give every operation its own path, so Amazon Kinesis shows 27 distinct
path roots while doing exactly one thing. Read `tags` and the description; treat
`n_path_roots` as a curiosity.

Usage:
    python src/gate1_select.py                 # writes results/gate1_shortlist.csv
    python src/gate1_select.py --per-bucket 40
"""

import argparse
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import filter as flt                           # noqa: E402
import config                                  # noqa: E402

# Gate 1 is a hand check, so the candidates must be small enough to read in
# full and large enough to have a meaningful pairwise structure.
MIN_OPS, MAX_OPS = 5, 30


def op_tags(spec):
    """The set of OpenAPI `tags` the author attached to operations.

    This is the most useful signal on the sheet, and the only structural one
    that is not an ILSC feature: `tags` are the *author's own* grouping of
    their operations into capability areas. A service whose operations span
    many author-declared tags is multi-capability by its own documentation,
    not by our metric's opinion of it. f1-f6 never look at tags.

    Contrast with path structure, which is feature f3 and is actively
    misleading here: the AWS RPC-over-HTTP specs give every operation its own
    path (#x-amz-target=...), so Amazon Kinesis scores 27 distinct path roots
    while being about exactly one thing.
    """
    tags = set()
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for m, op in item.items():
            if m.lower() in config.HTTP_METHODS and isinstance(op, dict):
                for t in (op.get("tags") or []):
                    if isinstance(t, str) and t.strip():
                        tags.add(t.strip())
    return tags


def path_roots(ops):
    """Distinct first path segments. CONTEXT ONLY - never a selection rule.

    Feature f3 of ILSC. Present on the sheet so a reader can see when it
    disagrees with the tags, never as grounds for a pick."""
    roots = set()
    for _, path in ops:
        parts = [p for p in str(path).split("/") if p and not p.startswith("{")]
        if parts:
            roots.add(parts[0].lower())
    return roots


def describe(spec):
    info = spec.get("info") or {}
    d = str(info.get("description", "") or "").strip().replace("\n", " ")
    return " ".join(d.split())[:300]


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Gate 1 candidate shortlist.")
    ap.add_argument("--specs-dir", default=config.SPECS_CLEAN)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--out", default=os.path.join(config.RESULTS_DIR, "gate1_shortlist.csv"))
    ap.add_argument("--per-bucket", type=int, default=40)
    args = ap.parse_args(argv)

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if MIN_OPS <= int(r["n_operations"]) <= MAX_OPS]
    print("%d services in the readable size band (%d-%d ops)"
          % (len(rows), MIN_OPS, MAX_OPS), flush=True)

    out = []
    for r in rows:
        spec, _ = flt.load_spec(os.path.join(args.specs_dir, r["clean_file"]))
        if spec is None:
            continue
        ops, _ = flt.operations(spec)
        if not ops:
            continue
        n_desc = 0
        for path, item in (spec.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for m, op in item.items():
                if m.lower() in config.HTTP_METHODS and isinstance(op, dict):
                    if str(op.get("description", "") or "").strip():
                        n_desc += 1
        roots = path_roots(ops)
        tags = op_tags(spec)
        out.append({
            "clean_file": r["clean_file"],
            "title": r["title"],
            "provider": r["provider"],
            "source": r["source"],
            "n_operations": len(ops),
            "n_tags": len(tags),
            "tags": "|".join(sorted(tags)[:12]),
            "n_path_roots": len(roots),
            "path_roots": "|".join(sorted(roots)[:12]),
            "pct_described": "%.0f" % (100.0 * n_desc / len(ops)),
            "info_description": describe(spec),
        })

    # Sorted only so a reader can browse the two ends of the range; this
    # ordering is presentation, not selection. Read the descriptions.
    # Ordered by the author's own tag count, with untagged services last so
    # they do not masquerade as single-capability: 0 tags means "the author
    # declared nothing", not "this service does one thing".
    tagged = [r for r in out if r["n_tags"] > 0]
    tagged.sort(key=lambda r: (r["n_tags"], -r["n_operations"]))
    shortlist = tagged[: args.per_bucket] + tagged[-args.per_bucket:]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(shortlist[0].keys()))
        w.writeheader()
        w.writerows(shortlist)

    print("wrote %d candidates to %s" % (len(shortlist), args.out))
    print("\nNEXT: read the candidates and record the ten picks, with a")
    print("justification citing each service's stated business capability,")
    print("in docs/gate1_expectations.md. Do not select on path structure.")


if __name__ == "__main__":
    main()

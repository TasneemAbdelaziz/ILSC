"""
ILSC - API evolution, step 0: is there enough real change to test against?

D-30's evolution line asks whether a service's ILSC at one version relates to
the structural change it undergoes by the next. Before any outcome is chosen,
this script only COUNTS what the data can support. It never reads an ILSC
score, so the outcome can still be fixed blind.

**Where the version pairs come from.** The filter's own scan
(`src/pipeline/filter.py --scan`, cached in `.cache/scan_S*.json`) groups every
spec by (title, host), the key the corpus was deduplicated on. Three kinds of
pair follow:

    cross      the same API in S1 (RAMA, snapshot 2019-12) and in S2
               (APIs.guru, snapshot 2026-04). Ordered in TIME by the two
               snapshots. The S1 side is the version kept in the corpus.
    within_S1  consecutive versions inside RAMA's snapshot, ordered by version
    within_S2  consecutive versions inside APIs.guru's snapshot, ordered by version

**How change is measured.** oasdiff 1.33.0 (`tools/`, checksum-verified)
compares the two specs with documentation excluded
(`-e description,examples,summary,title`). External `$ref`s are never fetched
(`--allow-external-refs=false`): these are downloaded, untrusted files.
oasdiff does not read Swagger 2.0, so every 2.0 side is first converted with
the pipeline's own converter (`src/pipeline/convert.js`, swagger2openapi
7.0.8) into `data/evolution/converted/`.

Outputs:
    results/evolution_feasibility_pairs.csv     one row per pair, with every error
    results/evolution_feasibility_summary.csv   the counts

Usage:
    python src/pipeline/filter.py --scan S1 && python src/pipeline/filter.py --scan S2
    python src/experiments/evolution_feasibility.py [--oasdiff PATH] [--workers 4]
"""

import argparse
import collections
import concurrent.futures as cf
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))   # src/<group>/ -> repository root
sys.path.insert(0, _ROOT)
import srcpath  # noqa: E402,F401  - puts every src/<group>/ on sys.path

import config                                     # noqa: E402

CACHE = os.path.join(config.ROOT, ".cache")
CONVERTED = os.path.join(config.ROOT, "data", "evolution", "converted")
OASDIFF = os.path.join(os.path.dirname(config.ROOT), "tools", "oasdiff-1.33.0", "bin",
                       "oasdiff.exe" if os.name == "nt" else "oasdiff")
OUT_PAIRS = os.path.join(config.RESULTS_DIR, "evolution_feasibility_pairs.csv")
OUT_SUMMARY = os.path.join(config.RESULTS_DIR, "evolution_feasibility_summary.csv")
EXCLUDE = "description,examples,summary,title"
COUNTED = ("endpoints", "paths", "parameters", "schemas", "requestBodies", "responses")


def vk(r):
    return (tuple(r["vkey"][0]), r["vkey"][1])


def load_groups():
    recs = []
    for tag in ("S1", "S2"):
        path = os.path.join(CACHE, "scan_%s.json" % tag)
        if not os.path.exists(path):
            sys.exit("no %s - run: python src/pipeline/filter.py --scan %s" % (path, tag))
        with open(path, encoding="utf-8") as fh:
            recs += json.load(fh)["records"]
    groups = collections.defaultdict(list)
    for r in recs:
        groups[tuple(r["key"])].append(r)
    return groups


def chain(records):
    """One record per distinct version key, oldest first; duplicates by rel order."""
    out = {}
    for r in sorted(records, key=lambda r: (vk(r), r["rel"])):
        out.setdefault(vk(r), r)
    return [out[k] for k in sorted(out)]


def build_pairs(groups):
    pairs = []
    for key, recs in sorted(groups.items()):
        s1 = chain([r for r in recs if r["source"] == "S1"])
        s2 = chain([r for r in recs if r["source"] == "S2"])
        if s1 and s2:
            pairs.append(("cross", s1[-1], s2[-1]))
        for tag, ch in (("within_S1", s1), ("within_S2", s2)):
            for a, b in zip(ch, ch[1:]):
                pairs.append((tag, a, b))
    return pairs


def convert_2x(pairs):
    """Convert every Swagger 2.0 side once; returns {original file: 3.x file}."""
    os.makedirs(CONVERTED, exist_ok=True)
    todo = {}
    for _t, a, b in pairs:
        for r in (a, b):
            if r["spec_version"] == "2.0":
                name = r["source"] + "__" + re.sub(r"[^A-Za-z0-9._-]+", "_", r["rel"]) + ".json"
                todo[r["file"]] = os.path.join(CONVERTED, name)
    need = {k: v for k, v in todo.items() if not os.path.exists(v)}
    if need:
        fd, worklist = tempfile.mkstemp(suffix=".tsv", text=True)
        log = os.path.join(CONVERTED, "_convert_log.csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for src, dst in need.items():
                fh.write(src + "\t" + dst + "\n")
        try:
            subprocess.run(["node", os.path.join(config.ROOT, "src", "pipeline", "convert.js"),
                            worklist, log], cwd=config.ROOT, check=False)
        finally:
            os.unlink(worklist)
    print("Swagger 2.0 sides: %d (%d converted now)" % (len(todo), len(need)))
    return {k: v for k, v in todo.items() if os.path.exists(v)}


def diff(oasdiff, base, rev):
    cmd = [oasdiff, "summary", base, rev, "--allow-external-refs=false",
           "-e", EXCLUDE, "--format", "json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip().splitlines()[-1][:200] if (p.stderr or p.stdout) else "exit %d" % p.returncode
    try:
        return json.loads(p.stdout), ""
    except ValueError:
        return None, "unparseable output"


def main(argv=None):
    ap = argparse.ArgumentParser(description="API evolution, feasibility counts only.")
    ap.add_argument("--oasdiff", default=OASDIFF)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    if not os.path.exists(args.oasdiff):
        sys.exit("oasdiff not found at %s" % args.oasdiff)

    manifest = {}
    with open(os.path.join(config.RESULTS_DIR, "manifest.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            manifest[(r["source"], r["rel"])] = r

    groups = load_groups()
    pairs = build_pairs(groups)
    conv = convert_2x(pairs)
    print("pairs: %s" % dict(collections.Counter(t for t, _a, _b in pairs)))

    def job(i):
        t, a, b = pairs[i]
        fa, fb = conv.get(a["file"], a["file"]), conv.get(b["file"], b["file"])
        missing = [r["rel"] for r in (a, b) if r["spec_version"] == "2.0" and r["file"] not in conv]
        res, err = (None, "conversion failed: " + ", ".join(missing)) if missing else diff(args.oasdiff, fa, fb)
        m = manifest.get((a["source"], a["rel"]))
        row = {
            "pair_type": t, "title": a["title"], "provider": a["provider"],
            "base_source": a["source"], "base_rel": a["rel"], "base_version": a["version_field"],
            "base_spec": a["spec_version"], "base_n_operations": a["n_operations"],
            "base_in_corpus": int(m is not None),
            "base_primary": int(m is not None and str(m.get("oversized", "0")) in ("0", "False", "false", "")),
            "rev_source": b["source"], "rev_rel": b["rel"], "rev_version": b["version_field"],
            "rev_spec": b["spec_version"], "rev_n_operations": b["n_operations"],
            "same_version_string": int(str(a["version_field"]) == str(b["version_field"])),
            "error": err, "any_diff": "",
        }
        details = (res or {}).get("details") or {}
        for k in COUNTED:
            for op in ("added", "deleted", "modified"):
                row["%s_%s" % (k, op)] = (details.get(k) or {}).get(op, 0) if res is not None else ""
        if res is not None:
            row["any_diff"] = int(bool(res.get("diff")))
        return row

    rows = [None] * len(pairs)
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(job, i): i for i in range(len(pairs))}
        for n, f in enumerate(cf.as_completed(futs), 1):
            rows[futs[f]] = f.result()
            if n % 100 == 0:
                print("  ... %d/%d diffed" % (n, len(pairs)), flush=True)

    with open(OUT_PAIRS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    summary = []
    for t in ("cross", "within_S1", "within_S2"):
        rs = [r for r in rows if r["pair_type"] == t]
        ok = [r for r in rs if not r["error"]]
        struct = [r for r in ok if (r["endpoints_added"] or r["endpoints_deleted"])]
        provs = collections.Counter(r["provider"] for r in rs)
        top = provs.most_common(1)[0] if provs else ("", 0)
        summary.append({
            "pair_type": t, "pairs": len(rs), "diffed": len(ok), "errors": len(rs) - len(ok),
            "base_in_primary": sum(r["base_primary"] for r in rs),
            "same_version_string": sum(r["same_version_string"] for r in rs),
            "any_structural_diff": sum(1 for r in ok if r["any_diff"]),
            "endpoints_added_or_deleted": len(struct),
            "endpoints_added_or_deleted_same_version": sum(r["same_version_string"] for r in struct),
            "base_primary_with_endpoint_change": sum(r["base_primary"] for r in struct),
            "providers": len(provs), "top_provider": top[0], "top_provider_pairs": top[1],
        })
    with open(OUT_SUMMARY, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    for s in summary:
        print(s)
    print("wrote %s\n      %s" % (OUT_PAIRS, OUT_SUMMARY))


if __name__ == "__main__":
    main()

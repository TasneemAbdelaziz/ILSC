"""
ILSC - Sec. 7 pipeline step (b): Swagger 2.0 is converted, not discarded (D-01).

Builds specs/clean3/ -- the same corpus as specs/clean/ but uniformly OpenAPI
3.x and uniformly JSON, which is what Mohamed's parser consumes.

  * 3.x specs are re-serialised to JSON unchanged.
  * 2.0 specs are converted with swagger2openapi 7.0.8 (the tool named in the
    proposal), run through src/convert.js.

specs/clean/ is deliberately left as published. The availability study (Day 3)
measures what spec authors actually wrote, and the 2.0-vs-3.x contrast in its
results is a finding; measuring converted files would erase it. See D-11.

Every conversion is verified: the (METHOD, path) operation set of the converted
spec must be identical to the one filter.py extracted from the original. A
conversion that adds, drops or renames an operation would silently change every
pairwise count downstream, so a mismatch is a hard failure, not a warning.

Usage:
    python src/convert.py
    python src/convert.py --limit 50        # smoke test
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))
import config                                  # noqa: E402
import filter as flt                           # noqa: E402


def out_name(clean_file):
    """clean_file -> the uniform-JSON name used inside specs/clean3/."""
    stem, _ = os.path.splitext(clean_file)
    return stem + ".json"


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC step (b): 2.0 -> 3.x conversion.")
    ap.add_argument("--specs-dir", default=config.SPECS_CLEAN)
    ap.add_argument("--out-dir", default=config.SPECS_CLEAN3)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--results-dir", default=config.RESULTS_DIR)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit:
        rows = rows[: args.limit]

    os.makedirs(args.out_dir, exist_ok=True)

    v2 = [r for r in rows if r["spec_version"] == "2.0"]
    v3 = [r for r in rows if r["spec_version"] != "2.0"]
    print("manifest: %d services  (%d x 2.0 to convert, %d x 3.x to re-serialise)"
          % (len(rows), len(v2), len(v3)), flush=True)

    # ---- 3.x: parse and re-serialise as JSON, no semantic change ------------
    reserialised, reserialise_failed = 0, []
    for r in v3:
        src = os.path.join(args.specs_dir, r["clean_file"])
        spec, reason = flt.load_spec(src)
        if spec is None:
            reserialise_failed.append((r["clean_file"], reason))
            continue
        with open(os.path.join(args.out_dir, out_name(r["clean_file"])), "w",
                  encoding="utf-8") as fh:
            # default=str is a guard only: filter._Loader already keeps
            # YAML timestamps as strings.
            json.dump(spec, fh, default=str)
        reserialised += 1
    print("re-serialised %d 3.x specs (%d failed)"
          % (reserialised, len(reserialise_failed)), flush=True)

    # ---- 2.0: swagger2openapi, one node process ----------------------------
    convert_log = os.path.join(args.results_dir, "convert_log.csv")
    if v2:
        fd, worklist = tempfile.mkstemp(suffix=".tsv", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for r in v2:
                fh.write(os.path.join(args.specs_dir, r["clean_file"]) + "\t"
                         + os.path.join(args.out_dir, out_name(r["clean_file"])) + "\n")
        try:
            proc = subprocess.run(
                ["node", os.path.join(_ROOT, "src", "convert.js"), worklist, convert_log],
                cwd=_ROOT, capture_output=True, text=True,
            )
            sys.stderr.write(proc.stderr[-2000:])
            if proc.returncode != 0:
                sys.exit("convert.js failed:\n" + proc.stdout[-2000:])
        finally:
            os.unlink(worklist)

    # ---- verify: operation sets must be identical ---------------------------
    verify_rows, mismatches, missing = [], 0, 0
    for r in rows:
        dest = os.path.join(args.out_dir, out_name(r["clean_file"]))
        if not os.path.exists(dest):
            verify_rows.append((r["clean_file"], r["spec_version"], "", "", "absent"))
            missing += 1
            continue
        orig, _ = flt.load_spec(os.path.join(args.specs_dir, r["clean_file"]))
        conv, _ = flt.load_spec(dest)
        o_ops = set(flt.operations(orig)[0]) if orig else set()
        c_ops = set(flt.operations(conv)[0]) if conv else set()
        status = "ok" if o_ops == c_ops else "op_set_mismatch"
        if status != "ok":
            mismatches += 1
        verify_rows.append((r["clean_file"], r["spec_version"],
                            len(o_ops), len(c_ops), status))

    with open(os.path.join(args.results_dir, "convert_verify.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["clean_file", "spec_version", "n_ops_original",
                    "n_ops_converted", "status"])
        w.writerows(verify_rows)

    ok = sum(1 for r in verify_rows if r[4] == "ok")
    print("\nspecs/clean3: %d/%d verified identical operation sets"
          % (ok, len(verify_rows)))
    print("  absent (conversion failed): %d" % missing)
    print("  operation-set mismatches:   %d" % mismatches)
    if reserialise_failed:
        print("  3.x re-serialise failures:  %d" % len(reserialise_failed))
    print("\nlogs: results/convert_log.csv, results/convert_verify.csv")

    if mismatches:
        sys.exit("FAIL: %d specs changed their operation set during conversion; "
                 "inspect results/convert_verify.csv before using clean3."
                 % mismatches)


if __name__ == "__main__":
    main()

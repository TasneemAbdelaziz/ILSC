"""
ILSC - Exp. 3 prerequisite: convert, parse and embed the benchmark systems.

`src/convert.py` and `src/parse_spec.py` are both driven by
`results/manifest.csv`, which describes the *corpus*. The benchmark systems are
not corpus members - D-06 exempts them from the corpus filters on purpose - so
they need the same three steps applied without the manifest. This module does
that and nothing else, so that `src/code_correlation.py` can assume its inputs
exist.

The steps are the pipeline's own, not re-implementations:

  1. **Convert** every benchmark spec to OpenAPI 3.x JSON with the same pinned
     `swagger2openapi@7.0.8` via `src/convert.js` - all 39 benchmark specs are
     Swagger 2.0. The (METHOD, path) operation set is verified identical before
     and after, exactly as `convert.py` does for the corpus, because a
     conversion that moved an operation would silently break the join to
     `endpoint_entities.csv`.
  2. **Parse** with `parse_spec.parse_service`, the same function the corpus
     uses, so benchmark features are built by identical code.
  3. **Embed** into a *separate* cache. Separate because the corpus cache is
     keyed by parsed filename and mixing 39 benchmark services into it would
     make `--verify` fail against `parsed/`.

D-07 applies here as it does everywhere: `payment`'s `/health` is stripped, so
Sock Shop contributes 27 operations, not 28.

Usage:
    python src/bench_prepare.py
    python src/bench_prepare.py --system sockshop
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                   # noqa: E402
import filter as flt                            # noqa: E402
import parse_spec as ps                         # noqa: E402

BENCH_DIR = os.path.join(config.ROOT, "specs", "benchmarks")
BENCH3_DIR = os.path.join(config.ROOT, "specs", "benchmarks3")
BENCH_PARSED = os.path.join(config.ROOT, "parsed_bench")
BENCH_CACHE = os.path.join(config.ROOT, ".cache", "embeddings_bench")


def spec_files(system=None):
    """(system, service, path) for every benchmark spec."""
    out = []
    for sysname in sorted(os.listdir(BENCH_DIR)):
        d = os.path.join(BENCH_DIR, sysname)
        if not os.path.isdir(d) or (system and sysname != system):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".json") or f.endswith(".yaml"):
                out.append((sysname, os.path.splitext(f)[0], os.path.join(d, f)))
    return out


def parsed_name(system, service):
    """Flat name, system-qualified so two systems cannot collide on a service."""
    return "%s__%s.json" % (system, service)


def convert(files):
    """Run the pinned swagger2openapi over every benchmark spec."""
    os.makedirs(BENCH3_DIR, exist_ok=True)
    fd, worklist = tempfile.mkstemp(suffix=".tsv", text=True)
    log = os.path.join(config.RESULTS_DIR, "benchmark_convert_log.csv")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for system, service, path in files:
            dest = os.path.join(BENCH3_DIR, parsed_name(system, service))
            fh.write(path + "\t" + dest + "\n")
    try:
        proc = subprocess.run(
            ["node", os.path.join(_ROOT, "src", "convert.js"), worklist, log],
            cwd=_ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            sys.exit("convert.js failed:\n" + (proc.stdout or "")[-2000:]
                     + (proc.stderr or "")[-2000:])
    finally:
        os.unlink(worklist)
    print("converted %d benchmark specs -> %s" % (len(files), BENCH3_DIR))


def verify_and_parse(files):
    """Operation-set check, then parse with the corpus parser."""
    os.makedirs(BENCH_PARSED, exist_ok=True)
    ok, mismatches, total_ops = 0, [], 0
    for system, service, src_path in files:
        name = parsed_name(system, service)
        dest = os.path.join(BENCH3_DIR, name)
        if not os.path.exists(dest):
            mismatches.append((name, "conversion absent"))
            continue

        orig, _ = flt.load_spec(src_path)
        conv, _ = flt.load_spec(dest)
        o_ops = set(flt.operations(orig, drop_admin=True)[0]) if orig else set()
        c_ops = set(flt.operations(conv, drop_admin=True)[0]) if conv else set()
        if o_ops != c_ops:
            mismatches.append((name, "operation set changed: +%d / -%d"
                               % (len(c_ops - o_ops), len(o_ops - c_ops))))
            continue

        doc, reason = ps.parse_service(conv, {
            "clean_file": name, "title": "%s/%s" % (system, service),
            "provider": system, "source": "BENCH", "spec_version": "3.x",
        })
        if doc is None:
            mismatches.append((name, reason))
            continue
        doc["system"] = system
        doc["service"] = service
        with open(os.path.join(BENCH_PARSED, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        ok += 1
        total_ops += doc["n_operations"]

    print("parsed  %d/%d benchmark services, %d operations -> %s"
          % (ok, len(files), total_ops, BENCH_PARSED))
    if mismatches:
        print("FAILURES (%d):" % len(mismatches))
        for n, r in mismatches[:10]:
            print("   %-40s %s" % (n, r))
        sys.exit("benchmark preparation failed - Exp. 3 cannot proceed on this")
    return total_ops


def main(argv=None):
    ap = argparse.ArgumentParser(description="Prepare benchmark systems for Exp. 3.")
    ap.add_argument("--system", default=None, help="sockshop | trainticket")
    ap.add_argument("--skip-convert", action="store_true")
    args = ap.parse_args(argv)

    files = spec_files(args.system)
    if not files:
        sys.exit("no benchmark specs under %s" % BENCH_DIR)
    print("%d benchmark specs" % len(files))

    if not args.skip_convert:
        convert(files)
    verify_and_parse(files)

    import embed as emb_mod
    emb_mod.build(BENCH_PARSED, BENCH_CACHE)
    print("\nbenchmark cache ready: %s" % BENCH_CACHE)


if __name__ == "__main__":
    main()

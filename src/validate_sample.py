"""
ILSC - D-02: the strict-validation number.

The corpus is gated on a cheap structural check (filter.structural_check),
because a full openapi-spec-validator pass costs ~0.5 s per spec and rejects on
details that cannot affect ILSC -- an unresolvable external $ref inside an
example, say. D-02 accepts that cost on one condition: that the strict pass
rate be measured on a random sample and reported alongside the cheap gate, so
readers know how much the shortcut let through.

This script produces that second number. Without it D-02 is an unbacked claim.

Sampling is seeded (config.SEED), so the sample is the same on every machine.

Usage:
    python src/validate_sample.py
    python src/validate_sample.py --n 50
"""

import argparse
import csv
import os
import random
import socket
import sys
import time
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))
import config                                  # noqa: E402
import filter as flt                           # noqa: E402

# An external $ref must never turn this into a network benchmark.
socket.setdefaulttimeout(5)


def classify(exc):
    """Collapse an exception into a short, countable reason."""
    name = type(exc).__name__
    msg = str(exc).replace("\n", " ")
    if "Unresolvable" in name or "unresolvable" in msg.lower() or "RefResolution" in name:
        return "unresolvable_ref", msg[:180]
    if "timed out" in msg.lower() or "URLError" in name or "HTTPError" in name:
        return "external_ref_unreachable", msg[:180]
    return name, msg[:180]


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC D-02 strict validation sample.")
    ap.add_argument("--specs-dir", default=config.SPECS_CLEAN)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--out", default=os.path.join(config.RESULTS_DIR,
                                                  "strict_validation_sample.csv"))
    ap.add_argument("--n", type=int, default=config.STRICT_VALIDATION_SAMPLE)
    args = ap.parse_args(argv)

    try:
        from openapi_spec_validator import validate
    except ImportError:
        sys.exit("pip install openapi-spec-validator==0.7.2")

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    n = min(args.n, len(rows))
    sample = random.Random(config.SEED).sample(rows, n)
    print("strict-validating %d of %d survivors (seed %d)" % (n, len(rows), config.SEED),
          flush=True)

    out_rows, reasons = [], Counter()
    n_valid = 0
    t0 = time.time()

    for i, r in enumerate(sample, 1):
        path = os.path.join(args.specs_dir, r["clean_file"])
        spec, load_reason = flt.load_spec(path)
        if spec is None:
            out_rows.append((r["clean_file"], r["source"], r["spec_version"],
                             "load_error", load_reason))
            reasons["load_error"] += 1
            continue
        try:
            validate(spec)
            out_rows.append((r["clean_file"], r["source"], r["spec_version"], "valid", ""))
            n_valid += 1
        except Exception as exc:                          # noqa: BLE001
            reason, detail = classify(exc)
            out_rows.append((r["clean_file"], r["source"], r["spec_version"],
                             "invalid", reason + ": " + detail))
            reasons[reason] += 1
        if i % 25 == 0:
            print("  ... %d/%d  (%.0fs)" % (i, n, time.time() - t0), flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["clean_file", "source", "spec_version", "status", "detail"])
        w.writerows(out_rows)

    pct = 100.0 * n_valid / n if n else 0.0
    print("\n" + "=" * 62)
    print("D-02 strict validation, %d-service random sample (seed %d)" % (n, config.SEED))
    print("=" * 62)
    print("  strictly valid : %d / %d  (%.1f%%)" % (n_valid, n, pct))
    print("  rejected       : %d / %d  (%.1f%%)" % (n - n_valid, n, 100.0 - pct))
    if reasons:
        print("\n  rejection reasons:")
        for reason, count in reasons.most_common():
            print("    %-28s %4d  (%.1f%%)" % (reason, count, 100.0 * count / n))

    # Per-source breakdown: S1 was pre-processed by RAMA, S2 is raw upstream,
    # so their strict pass rates are not expected to be equal.
    print("\n  by source:")
    for tag in sorted({r[1] for r in out_rows}):
        sub = [r for r in out_rows if r[1] == tag]
        ok = sum(1 for r in sub if r[3] == "valid")
        print("    %-4s %3d/%3d  (%.1f%%)" % (tag, ok, len(sub), 100.0 * ok / len(sub)))

    print("\nwritten: %s" % args.out)


if __name__ == "__main__":
    main()

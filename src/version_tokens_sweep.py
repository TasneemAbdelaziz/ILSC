"""
ILSC - Exp. 5, third knob: the DROP_VERSION_TOKENS sweep (D-15).

The weight and tau sweeps are reweightings of a fixed set of vectors.
``DROP_VERSION_TOKENS`` is not: it changes the tokenizer, therefore ``T(Oi)``,
therefore the **f1 embeddings**. Sweeping it honestly means re-parsing and
re-embedding the whole corpus and scoring it again, which is why
``src/sensitivity.py`` refuses to fold it in and reports a two-knob analysis.
This module runs the third knob end to end.

What the knob actually does
---------------------------
``config.TOKEN_STOPWORDS`` already pins ``v1`` and ``v2``, so turning the flag
off does **not** reintroduce those. It only affects ``^v\\d+$`` tokens outside
the pinned pair - ``v0``, ``v3``, ``v10``, and date-like versions such as
``v20180301``. **2,646 of 97,912 operations (2.70%), across 80 of 2,206
services**, tokenise differently.

And they do not merely gain a version token. With the flag off, the letter/digit
splitter turns ``v3`` into ``v`` + ``3``, so **every versioned path in the corpus
comes to share the token ``v``** - which is the inflation D-15 was written to
prevent, in a smaller form. The sweep measures how much that matters.

Method
------
1. Re-parse the corpus with ``ILSC_DROP_VERSION_TOKENS=0`` into ``parsed_nodrop/``.
2. Re-embed it into its own cache - the T texts differ, so the vectors must.
3. Score both corpora and compare, corpus-wide and on the 80 affected services,
   which is where any effect has to show up if it exists at all.

Usage:
    python src/version_tokens_sweep.py                 # full run, ~30 min
    python src/version_tokens_sweep.py --skip-build    # reuse an existing build
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                    # noqa: E402
import embed as emb_mod                          # noqa: E402
import similarity as sim                         # noqa: E402
import ilsc as ilsc_mod                          # noqa: E402

NODROP_PARSED = os.path.join(config.ROOT, "parsed_nodrop")
NODROP_CACHE = os.path.join(config.ROOT, ".cache", "embeddings_nodrop")
VERSION_TOKEN = re.compile(r"^v\d+$")


def affected_services(parsed_dir):
    """Services holding at least one operation whose tokens the knob changes."""
    out = set()
    for name in sorted(os.listdir(parsed_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        for o in doc["operations"]:
            text = str(o["path"]) + " " + (o.get("operation_id") or "")
            for t in re.findall(r"[A-Za-z0-9]+", text):
                if VERSION_TOKEN.match(t.lower()) and t.lower() not in config.TOKEN_STOPWORDS:
                    out.add(name)
                    break
            if name in out:
                break
    return out


def build():
    env = dict(os.environ, ILSC_DROP_VERSION_TOKENS="0")
    print("re-parsing with DROP_VERSION_TOKENS=False -> %s" % NODROP_PARSED, flush=True)
    p = subprocess.run([sys.executable, "-u", os.path.join(_HERE, "parse_spec.py"),
                        "--out-dir", NODROP_PARSED], cwd=_ROOT, env=env)
    if p.returncode != 0:
        sys.exit("re-parse failed")
    print("\nre-embedding -> %s" % NODROP_CACHE, flush=True)
    p = subprocess.run([sys.executable, "-u", os.path.join(_HERE, "embed.py"),
                        "--parsed-dir", NODROP_PARSED, "--out", NODROP_CACHE],
                       cwd=_ROOT, env=env)
    if p.returncode != 0:
        sys.exit("re-embed failed")


def score(parsed_dir, cache_dir, manifest):
    emb = emb_mod.Embeddings(cache_dir)
    out = {}
    for name in sorted(os.listdir(parsed_dir)):
        if not name.endswith(".json") or name not in emb:
            continue
        clean = ilsc_mod.parsed_to_clean(name, manifest)
        row = manifest.get(clean, {})
        if str(row.get("oversized", "")).strip().lower() in ("1", "true", "yes"):
            continue                                     # D-17 primary population
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        oset = sim.OpSet.from_service(doc, emb, name)
        if oset.n < 2:
            continue
        out[name] = sim.ilsc_mean(oset)
    return out


def run(args):
    from scipy import stats
    if not args.skip_build:
        build()
    if not os.path.isdir(NODROP_PARSED):
        sys.exit("no %s - run without --skip-build first" % NODROP_PARSED)

    manifest = ilsc_mod.load_manifest(os.path.join(config.RESULTS_DIR, "manifest.csv"))
    print("\nscoring both corpora", flush=True)
    base = score(config.PARSED_DIR, emb_mod.DEFAULT_CACHE, manifest)
    alt = score(NODROP_PARSED, NODROP_CACHE, manifest)
    shared = sorted(set(base) & set(alt))
    aff = affected_services(config.PARSED_DIR)
    aff_shared = [n for n in shared if n in aff]

    b = np.array([base[n] for n in shared])
    a = np.array([alt[n] for n in shared])
    print("\n" + "=" * 72)
    print("D-15 SWEEP - DROP_VERSION_TOKENS True (pinned) vs False")
    print("=" * 72)
    print("  services compared                 %d" % len(shared))
    print("  of which tokenise differently     %d (%.1f%%)"
          % (len(aff_shared), 100.0 * len(aff_shared) / max(len(shared), 1)))
    print("\n  ILSC_mean, whole primary corpus:")
    print("    pinned (True)    mean %.4f   median %.4f" % (b.mean(), np.median(b)))
    print("    knob off (False) mean %.4f   median %.4f" % (a.mean(), np.median(a)))
    print("    mean shift       %+.4f" % (a.mean() - b.mean()))
    print("    Spearman         %.6f" % stats.spearmanr(b, a).statistic)
    print("    Kendall's tau    %.6f" % stats.kendalltau(b, a).statistic)

    if aff_shared:
        ab = np.array([base[n] for n in aff_shared])
        aa = np.array([alt[n] for n in aff_shared])
        print("\n  restricted to the %d services the knob actually touches:" % len(aff_shared))
        print("    pinned (True)    mean %.4f" % ab.mean())
        print("    knob off (False) mean %.4f" % aa.mean())
        print("    mean shift       %+.4f   <- the number that matters"
              % (aa.mean() - ab.mean()))
        print("    Spearman         %.6f" % stats.spearmanr(ab, aa).statistic)
        worst = sorted(zip(np.abs(aa - ab), aff_shared), reverse=True)[:5]
        print("\n    largest individual moves:")
        for d, n in worst:
            print("      %-52s %.4f -> %.4f  (%+.4f)"
                  % (n[:52], base[n], alt[n], alt[n] - base[n]))

    out = os.path.join(config.RESULTS_DIR, "version_tokens_sweep.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["parsed_file", "affected", "ilsc_drop_true", "ilsc_drop_false", "delta"])
        for n in shared:
            w.writerow([n, int(n in aff), "%.6f" % base[n], "%.6f" % alt[n],
                        "%.6f" % (alt[n] - base[n])])
    print("\nwrote %s" % out)

    rho = stats.spearmanr(b, a).statistic
    print("\n  Reading:")
    if rho > 0.99:
        print("    The ranking is essentially unchanged (rho > 0.99). The knob is a")
        print("    documented choice with a measured, negligible effect on the")
        print("    ordering, and Exp. 5 can now be reported as THREE knobs.")
    else:
        print("    The ranking moves (rho = %.4f). This knob is NOT a free choice and" % rho)
        print("    the paper must report both settings, not just the pinned one.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exp. 5 third knob - D-15 sweep.")
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse an existing parsed_nodrop/ and its cache")
    args = ap.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

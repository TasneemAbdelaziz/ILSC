"""
ILSC — D-17: the oversized-service cap, run as primary + sensitivity.

Above ``config.OVERSIZED_MAX_OPERATIONS`` operations a specification stops
describing a single-capability microservice and starts describing an API gateway
or a whole platform surface. The cap is therefore a **scope** boundary, not a
compute budget: the top of the corpus is Microsoft Graph, Kubernetes, GitHub,
Compute Engine, EC2 and Stripe, none of which is the unit ILSC is defined over.
(Cheaper computation is a side effect and is never the justification.)

Nothing is deleted. Every service keeps its row in ``results/manifest.csv`` and
gains an ``oversized`` flag (1/0), so the sensitivity analysis is always one
filter away and no downstream reader inherits a silently truncated corpus.

Two analyses, always reported together:
  PRIMARY      services with <= OVERSIZED_MAX_OPERATIONS operations
  SENSITIVITY  the full corpus

Quartile thresholds are computed **per service** (the size-robust framing), on
the per-service quantities that exist today. ILSC scores do not exist yet — the
similarity engine is pending — so when they land they must be thresholded under
this same primary/sensitivity protocol. D-17 fixes the protocol, not one table.

Outputs:
  results/manifest.csv              (in place: adds/updates the `oversized` column)
  results/oversized_thresholds.csv  both threshold sets side by side + movement
"""

import csv
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
import config  # noqa: E402

RESULTS = os.path.join(_ROOT, "results")
CAP = config.OVERSIZED_MAX_OPERATIONS


def c2(n):
    return n * (n - 1) // 2


def read(name):
    with open(os.path.join(RESULTS, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --- 1. flag the manifest in place, deleting nothing -------------------------

def flag_manifest():
    path = os.path.join(RESULTS, "manifest.csv")
    rows = read("manifest.csv")
    cols = list(rows[0].keys())
    if "oversized" not in cols:
        cols.append("oversized")
    n_over = 0
    for r in rows:
        over = int(r["n_operations"]) > CAP
        r["oversized"] = "1" if over else "0"
        n_over += over
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows), n_over


# --- 2. per-service measures, joined on clean_file ---------------------------

# (label, source, column, value is already a percentage)
MEASURES = [
    ("operations", "manifest", "n_operations", True),
    ("mask-fire %", "pair", "maskfire_pct_codegen", True),
    ("f2 co-avail %", "pair", "coavail_pct_f2_codegen", True),
    ("f4 co-avail %", "pair", "coavail_pct_f4_parameters", True),
    ("f5 co-avail %", "pair", "coavail_pct_f5_schemas", True),
    ("f6 co-avail %", "pair", "coavail_pct_f6_description", True),
    ("description rate %", "avail", "rate_description", False),
    ("operationId rate %", "avail", "rate_operation_id", False),
    ("parameters rate %", "avail", "rate_parameters", False),
    ("any_schema rate %", "avail", "rate_any_schema", False),
]


def build():
    man = {r["clean_file"]: r for r in read("manifest.csv")}
    pair = {r["clean_file"]: r for r in read("pair_availability.csv")}
    avail = {r["clean_file"]: r for r in read("availability.csv")}
    out = []
    for cf, m in man.items():
        out.append({
            "clean_file": cf,
            "n": int(m["n_operations"]),
            "oversized": m.get("oversized") == "1",
            "manifest": m,
            "pair": pair.get(cf, {}),
            "avail": avail.get(cf, {}),
        })
    return out


def quartiles(vals):
    vals = sorted(v for v in vals if v is not None)
    if len(vals) < 2:
        return (None, None, None)
    q = st.quantiles(vals, n=4, method="inclusive")
    return (q[0], q[1], q[2])


def column_values(recs, src, col, is_pct):
    vals = []
    for r in recs:
        raw = r["manifest"].get(col) if src == "manifest" else (r[src] or {}).get(col)
        x = num(raw)
        if x is not None:
            vals.append(x if is_pct else x * 100.0)
    return vals


MICRO_COLS = {
    "f2": "a_f2_codegen",
    "f4": "a_f4_parameters",
    "f5": "a_f5_schemas",
    "f6": "a_f6_description",
}


def micro(recs, kind):
    """Pair-weighted statistic — the one the cap actually rescues."""
    tot = sum(c2(r["n"]) for r in recs)
    if not tot:
        return None
    if kind == "maskfire":
        allfour = sum(c2(int(r["pair"]["c_all4_codegen"])) for r in recs if r["pair"])
        return 100.0 * (tot - allfour) / tot
    col = MICRO_COLS[kind]
    co = sum(c2(int(r["pair"][col])) for r in recs if r["pair"])
    return 100.0 * co / tot


def main():
    n_all, n_over = flag_manifest()
    recs = build()
    primary = [r for r in recs if not r["oversized"]]
    sens = recs

    def pairs(rs):
        return sum(c2(r["n"]) for r in rs)

    print(f"D-17 cap: > {CAP} operations = oversized  (config.OVERSIZED_MAX_OPERATIONS)")
    print(f"manifest.csv flagged: {n_all} services, {n_over} oversized, 0 deleted\n")
    print(f"{'':<14}{'services':>10}{'operations':>13}{'pairs':>16}")
    for lab, rs in (("PRIMARY", primary), ("SENSITIVITY", sens)):
        print(f"{lab:<14}{len(rs):>10}{sum(r['n'] for r in rs):>13,}{pairs(rs):>16,}")
    print(f"{'excluded':<14}{len(sens) - len(primary):>10}"
          f"{sum(r['n'] for r in sens) - sum(r['n'] for r in primary):>13,}"
          f"{pairs(sens) - pairs(primary):>16,}")

    print("\nPAIR-WEIGHTED (micro) - where the cap bites")
    print(f"{'statistic':<16}{'PRIMARY':>10}{'SENSITIVITY':>13}{'move':>9}")
    for kind, lab in (("maskfire", "mask-fire %"), ("f2", "f2 co-avail %"),
                      ("f4", "f4 co-avail %"), ("f5", "f5 co-avail %"),
                      ("f6", "f6 co-avail %")):
        a, b = micro(primary, kind), micro(sens, kind)
        print(f"{lab:<16}{a:>10.2f}{b:>13.2f}{b - a:>+9.2f}")

    print("\nPER-SERVICE QUARTILE THRESHOLDS  (Q1 / median / Q3)")
    print(f"{'measure':<20}{'PRIMARY':>26}{'SENSITIVITY':>26}{'max|move|':>11}")
    out_rows = []
    for lab, src, col, is_pct in MEASURES:
        p = quartiles(column_values(primary, src, col, is_pct))
        s = quartiles(column_values(sens, src, col, is_pct))
        if p[0] is None or s[0] is None:
            continue
        moves = [abs(s[i] - p[i]) for i in range(3)]
        print(f"{lab:<20}"
              f"{p[0]:>8.2f}{p[1]:>9.2f}{p[2]:>9.2f}"
              f"{s[0]:>8.2f}{s[1]:>9.2f}{s[2]:>9.2f}"
              f"{max(moves):>11.2f}")
        out_rows.append({
            "measure": lab,
            "q1_primary": f"{p[0]:.4f}",
            "median_primary": f"{p[1]:.4f}",
            "q3_primary": f"{p[2]:.4f}",
            "q1_sensitivity": f"{s[0]:.4f}",
            "median_sensitivity": f"{s[1]:.4f}",
            "q3_sensitivity": f"{s[2]:.4f}",
            "d_q1": f"{s[0] - p[0]:+.4f}",
            "d_median": f"{s[1] - p[1]:+.4f}",
            "d_q3": f"{s[2] - p[2]:+.4f}",
            "max_abs_move": f"{max(moves):.4f}",
        })

    with open(os.path.join(RESULTS, "oversized_thresholds.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    worst = max(out_rows, key=lambda r: float(r["max_abs_move"]))
    print(f"\nlargest quartile-boundary movement: {worst['measure']} "
          f"({worst['max_abs_move']} points)")


if __name__ == "__main__":
    main()

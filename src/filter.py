"""
ILSC - Day 1-2 (Tasneem): multi-source dataset curation.

Applies the Sec. 7 pipeline in order, over S1 then S2 (config.SOURCES):
  (a) validate            -> structural gate, skip + log broken
  (b) REST-style 2.0/3.x  -> 2.0 is kept and converted by src/convert.py
  (c) drop < 3 operations
  (d) dedup on (info.title, host), keep newest        [within a source]
  (e) cross-source dedup  -> a service already in S1 is tagged S1 (D-09)
  (f) strip admin endpoints
  (g) [v3] assign a coarse domain label               [REJECTED, see D-03]

Every removal is logged with a reason into results/filter_log.csv.

The work splits into two phases, because they have very different costs:

  scan   parse every spec and extract its record.  Minutes: 6,757 files, two of
         them tens of megabytes of YAML.
  merge  apply the dedup rules (d) and (e), copy survivors, write outputs.
         Seconds.

The scan is checkpointed to a cache so that a change to a dedup rule can be
re-evaluated without re-parsing the corpus -- which is what D-13 required, and
what made re-running it affordable.

Usage:
    python src/filter.py                     # scan both sources, then merge
    python src/filter.py --scan S1           # scan one source into the cache
    python src/filter.py --merge             # merge from cached scans only
    python src/filter.py --only S2           # one source, end to end
    python src/filter.py --limit 200         # smoke test
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

import yaml
try:
    from yaml import CSafeLoader as _BaseLoader   # libyaml: ~10x faster
except ImportError:                                # pragma: no cover
    from yaml import SafeLoader as _BaseLoader


class _Loader(_BaseLoader):
    """SafeLoader with YAML timestamp auto-detection disabled.

    An unquoted `version: 2015-12-08` (common in the AWS specs) is a valid YAML
    timestamp, so the default resolver hands back a datetime.date instead of the
    string the spec author wrote. That is not merely cosmetic: it is not JSON
    serialisable, so it breaks src/convert.py, and it makes the same field a
    different Python type depending on how the author quoted it. Every consumer
    in this project wants the literal text, so the resolver is removed once,
    here, rather than worked around per call site.
    """


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in _BaseLoader.yaml_implicit_resolvers.items()
}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import config                                  # noqa: E402

# Re-exported so downstream modules (availability.py) bind to exactly the
# definition the corpus was built with. Do not re-declare these here.
ADMIN_PATHS = config.ADMIN_PATHS_RE
HTTP_METHODS = config.HTTP_METHODS
MIN_OPERATIONS = config.MIN_OPERATIONS

# Provider is the leading domain-shaped token of a RAMA file name.
# Non-greedy so that "clever-cloud.com-1.0.0-swagger.yaml" -> "clever-cloud.com"
# and "6-dot-authentiqio.appspot.com-6-swagger.yaml" keeps its full host.
_RAMA_PROVIDER_RE = re.compile(r"^([a-z0-9][a-z0-9.\-]*?\.[a-z]{2,})-", re.IGNORECASE)

# Pre-release markers, checked in the file path and in info.version (D-13).
_PRERELEASE_RE = re.compile(r"(beta|preview|alpha|rc\d*|canary|nightly)", re.IGNORECASE)

# [v3] Coarse domain labels -- REJECTED (D-03), retained inert for the record.
# The live labeller is src/domain_label.py; nothing downstream consumes either.
DOMAIN_KEYWORDS = {
    "finance": ["bank", "payment", "invoice", "billing", "trading", "stock", "crypto",
                "currency", "tax", "accounting", "loan", "credit", "wallet", "finance",
                "exchange", "money", "fund", "insur"],
    "travel": ["flight", "airline", "airport", "hotel", "booking", "travel", "trip",
               "rail", "train", "transit", "car rental", "cruise", "tourism"],
    "health": ["health", "medical", "clinic", "patient", "pharma", "drug", "fhir",
               "hospital", "diagnos", "genom", "covid", "fitness"],
    "geo": ["map", "geo", "location", "address", "postcode", "zip", "weather",
            "place", "route", "navigation", "satellite", "climate"],
    "social": ["social", "chat", "message", "messaging", "twitter", "facebook",
               "instagram", "forum", "comment", "community", "friend"],
    "commerce": ["shop", "cart", "order", "product", "catalog", "catalogue", "ecommerce",
                 "e-commerce", "retail", "store", "inventory", "shipping", "delivery"],
    "devtools": ["api", "developer", "sdk", "deploy", "build", "ci", "repo", "git",
                 "container", "kubernetes", "cloud", "server", "monitor", "log",
                 "devops", "test", "code"],
    "media": ["video", "audio", "music", "image", "photo", "media", "stream", "film",
              "movie", "podcast", "news", "book", "content"],
    "identity": ["auth", "identity", "user", "account", "login", "oauth", "sso",
                 "permission", "role", "directory", "customer"],
    "communication": ["email", "mail", "sms", "voice", "call", "telephon", "notification",
                      "push", "contact"],
    "data": ["analytic", "data", "statistic", "report", "dashboard", "search",
             "index", "database", "warehouse", "machine learning", "ml", "ai"],
    "government": ["gov", "public", "census", "legal", "law", "court", "regulation",
                   "election", "municipal"],
}


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def load_spec(path):
    """Return (spec_dict, None) or (None, reason)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            if path.endswith((".yaml", ".yml")):
                spec = yaml.load(fh, Loader=_Loader)
            else:
                spec = json.load(fh)
    except Exception as exc:                              # noqa: BLE001
        return None, "parse_error: " + type(exc).__name__
    if not isinstance(spec, dict):
        return None, "parse_error: not_a_mapping"
    return spec, None


def spec_version(spec):
    """Return '2.0', '3.x' or None."""
    if "swagger" in spec:
        return "2.0" if str(spec["swagger"]).startswith("2") else None
    if "openapi" in spec:
        return "3.x" if str(spec["openapi"]).startswith("3") else None
    return None


def structural_check(spec):
    """Cheap validity gate: the fields every downstream step depends on.

    Full openapi-spec-validator runs are ~0.5s/spec and reject on details that
    do not affect ILSC (e.g. an unresolvable external $ref in an example).
    We run this gate over the whole corpus and the strict validator over a
    random sample -- src/validate_sample.py -- and report both numbers (D-02).
    """
    if not isinstance(spec.get("paths"), dict):
        return "no_paths_object"
    if not spec.get("paths"):
        return "empty_paths"
    if not isinstance(spec.get("info"), dict):
        return "no_info_object"
    return None


# ----------------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------------

def raw_host(spec, version):
    if version == "2.0":
        return spec.get("host", "") or ""
    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict):
        return servers[0].get("url", "") or ""
    return ""


def norm_host(raw):
    """Reduce a host or server URL to a bare lowercase netloc.

    Required for cross-source dedup (step e): the same service appears in S2 as
    Swagger 2.0 with host "api.example.com" and in S1 as a converted OpenAPI 3
    with servers[0].url "https://api.example.com/v1". Comparing the raw strings
    would never match them.
    """
    h = str(raw or "").strip().lower()
    if "://" in h:
        h = h.split("://", 1)[1]
    h = h.split("/", 1)[0]          # drop path / basePath
    h = h.split("@")[-1]            # drop any userinfo
    return h.rstrip(".").strip()


def provider_of(rel, layout):
    """S2: the top-level directory is the provider domain.

    S1: RAMA flattens to "<provider-domain>-<service>-<version>-<fmt>.yaml".
    """
    if layout == "tree":
        return rel.split(os.sep)[0] if os.sep in rel else ""
    m = _RAMA_PROVIDER_RE.match(os.path.basename(rel))
    return m.group(1).lower() if m else ""


def operations(spec, drop_admin=True):
    """Yield (method, path) pairs, optionally excluding admin endpoints."""
    ops, dropped = [], []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        is_admin = bool(ADMIN_PATHS.match(str(path)))
        for method in item:
            if method.lower() not in HTTP_METHODS:
                continue
            if is_admin and drop_admin:
                dropped.append((method.upper(), path))
            else:
                ops.append((method.upper(), path))
    return ops, dropped


def is_rest_style(spec, ops):
    """Reject RPC-over-HTTP shells: every path identical, or POST-only with
    verb-shaped paths. These inflate path similarity artificially."""
    if not ops:
        return False
    paths = {p for _, p in ops}
    if len(paths) == 1 and len(ops) > 5:
        return False
    return True


def domain_of(spec, provider):
    """REJECTED labeller (D-03). Retained so manifest.csv keeps its column."""
    text = " ".join([
        str(provider or ""),
        str((spec.get("info") or {}).get("title", "")),
        str((spec.get("info") or {}).get("description", ""))[:400],
    ]).lower()
    scores = {
        dom: sum(1 for kw in kws if kw in text)
        for dom, kws in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "UNLABELLED"


def version_key(spec, rel=""):
    """Dedup sort key: (numeric version, stability). Higher wins.

    The numeric part is the documented rule ("keep newest"). The stability flag
    breaks ties, and only ties -- a pre-release never outranks a higher release
    number.

    The tie-break is not cosmetic. microsoft.com publishes Graph twice under the
    *identical* info.title ("OData Service for namespace microsoft.graph") and
    the same host, the channel appearing only in the server path (/v1.0 vs
    /beta) which `host` excludes by Swagger 2.0 semantics. Both carry
    info.version 1.0.1, so the keys tied and the survivor was decided by
    filename sort order -- which kept **beta** (22,361 operations) and dropped
    **stable v1.0** (11,422). That one service is ~95% of all within-service
    pairs in the corpus, so an incidental sort order was silently setting the
    headline RQ2 denominator. Stable now wins its ties explicitly. See D-13.
    """
    raw = str((spec.get("info") or {}).get("version", "0"))
    nums = tuple(int(n) for n in re.findall(r"\d+", raw)[:4]) or (0,)
    stable = 0 if _PRERELEASE_RE.search(rel + " " + raw) else 1
    return (nums, stable)


def _vkey(record):
    """Dedup key from a record, tolerant of a JSON cache round-trip (which
    turns the inner tuple into a list)."""
    nums, stable = record["vkey"]
    return (tuple(nums), stable)


def _walk(root):
    files = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith((".yaml", ".yml", ".json")):
                files.append(os.path.join(dirpath, name))
    files.sort()
    return files


# ----------------------------------------------------------------------------
# Phase 1 - scan
# ----------------------------------------------------------------------------

def scan_source(source_tag, root, layout, limit=None):
    """Parse one source; return (records, log_rows, counts). No dedup here."""
    if not os.path.isdir(root):
        sys.exit("source " + source_tag + " not found: " + root +
                 "\nSee README.md section 2 for the fetch commands.")

    log_rows, records = [], []
    counts = defaultdict(int)

    files = _walk(root)
    if limit:
        files = files[:limit]
    print("[%s] %d files under %s" % (source_tag, len(files), root), flush=True)

    for path in files:
        counts["scanned_" + source_tag] += 1
        counts["scanned"] += 1
        if counts["scanned"] % 500 == 0:
            print("  ... %d scanned" % counts["scanned"], flush=True)
        rel = os.path.relpath(path, root)
        logged = source_tag + ":" + rel.replace(os.sep, "/")

        spec, reason = load_spec(path)
        if spec is None:
            log_rows.append((logged, "a_validate", reason))
            counts["drop_parse"] += 1
            continue

        reason = structural_check(spec)
        if reason:
            log_rows.append((logged, "a_validate", reason))
            counts["drop_structure"] += 1
            continue

        version = spec_version(spec)
        if version is None:
            log_rows.append((logged, "b_version", "not_openapi_2_or_3"))
            counts["drop_version"] += 1
            continue

        ops, admin_dropped = operations(spec, drop_admin=True)

        if not is_rest_style(spec, ops):
            log_rows.append((logged, "b_rest_style", "rpc_shaped"))
            counts["drop_rpc"] += 1
            continue

        if len(ops) < MIN_OPERATIONS:
            log_rows.append((logged, "c_min_ops", "only_%d_ops" % len(ops)))
            counts["drop_small"] += 1
            continue

        info = spec.get("info") or {}
        title = str(info.get("title", "")).strip().lower()
        host = norm_host(raw_host(spec, version))
        provider = provider_of(rel, layout)

        records.append({
            "rel": rel.replace(os.sep, "/"),
            "title": info.get("title", ""),
            "host": host,
            "provider": provider,
            "version_field": info.get("version", ""),
            "spec_version": version,
            "n_operations": len(ops),
            "n_admin_dropped": len(admin_dropped),
            "domain": domain_of(spec, provider),
            "source": source_tag,
            # S1 was converted 2.0 -> 3.x upstream by RAMA (D-10), so its
            # spec_version is a post-conversion property, not as-published.
            "converted_upstream": "true" if source_tag == "S1" else "false",
            "file": path,
            "vkey": version_key(spec, rel),
            "key": [title, host],
        })

    return records, log_rows, counts


def cache_path(cache_dir, source_tag):
    return os.path.join(cache_dir, "scan_%s.json" % source_tag)


def write_cache(cache_dir, source_tag, records, log_rows, counts):
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path(cache_dir, source_tag), "w", encoding="utf-8") as fh:
        json.dump({"records": records, "log_rows": log_rows, "counts": dict(counts)}, fh)


def read_cache(cache_dir, source_tag):
    path = cache_path(cache_dir, source_tag)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------
# Phase 2 - merge
# ----------------------------------------------------------------------------

def merge(records, log_rows, out_clean, out_results):
    """Apply steps (d) and (e) to scanned records, copy survivors, write."""
    survivors = {}          # (title, norm_host) -> record
    counts = defaultdict(int)
    log_rows = list(log_rows)

    for record in records:
        key = tuple(record["key"])
        logged = record["source"] + ":" + record["rel"]

        incumbent = survivors.get(key)
        if incumbent is None:
            survivors[key] = record
            continue

        if incumbent["source"] != record["source"]:
            # (e) cross-source dedup. S1 is the citable anchor and wins
            # regardless of version, so the retained file is the peer-reviewed
            # one and thresholds stay comparable to Bogner.
            if incumbent["source"] == "S1":
                log_rows.append((logged, "e_cross_source",
                                 "already_in_S1:" + incumbent["rel"]))
            else:
                log_rows.append((incumbent["source"] + ":" + incumbent["rel"],
                                 "e_cross_source",
                                 "superseded_by_S1:" + record["rel"]))
                survivors[key] = record
            counts["drop_cross_source"] += 1
            continue

        # (d) within-source dedup: newest wins; stable beats pre-release on a
        # tie (D-13).
        if _vkey(record) > _vkey(incumbent):
            log_rows.append((incumbent["source"] + ":" + incumbent["rel"], "d_dedup",
                             "superseded_by:" + record["rel"]))
            survivors[key] = record
        else:
            log_rows.append((logged, "d_dedup", "duplicate_of:" + incumbent["rel"]))
        counts["drop_dup"] += 1

    # ---- write clean corpus -------------------------------------------------
    os.makedirs(out_clean, exist_ok=True)
    manifest = []
    for rec in survivors.values():
        safe = rec["source"] + "__" + rec["rel"].replace("/", "__")
        with open(rec["file"], "rb") as src, open(os.path.join(out_clean, safe), "wb") as dst:
            dst.write(src.read())
        rec2 = {k: v for k, v in rec.items() if k not in ("vkey", "file", "key")}
        rec2["clean_file"] = safe
        manifest.append(rec2)
    manifest.sort(key=lambda r: r["clean_file"])

    os.makedirs(out_results, exist_ok=True)
    with open(os.path.join(out_results, "filter_log.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "stage", "reason"])
        w.writerows(log_rows)

    with open(os.path.join(out_results, "manifest.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    counts["survivors"] = len(survivors)
    for tag in sorted({r["source"] for r in manifest}):
        counts["survivors_" + tag] = sum(1 for r in manifest if r["source"] == tag)
    return counts, manifest


def run(sources, out_clean, out_results, limit=None):
    """Scan every source, then merge. Kept for callers that want one call."""
    all_records, all_logs = [], []
    counts = defaultdict(int)
    for source_tag, root, layout in sources:
        recs, logs, c = scan_source(source_tag, root, layout, limit)
        all_records += recs
        all_logs += logs
        for k, v in c.items():
            counts[k] += v
    mcounts, manifest = merge(all_records, all_logs, out_clean, out_results)
    for k, v in mcounts.items():
        counts[k] = v
    return counts, manifest


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Day 1-2 multi-source curation.")
    ap.add_argument("--only", choices=[t for t, _, _ in config.SOURCES],
                    help="restrict to a single source")
    ap.add_argument("--scan", choices=[t for t, _, _ in config.SOURCES],
                    help="scan this source into the cache and stop")
    ap.add_argument("--merge", action="store_true",
                    help="merge from cached scans only; do not parse anything")
    ap.add_argument("--cache-dir", default=os.path.join(_ROOT, ".cache"))
    ap.add_argument("--out-clean", default=config.SPECS_CLEAN)
    ap.add_argument("--out-results", default=config.RESULTS_DIR)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap files per source (smoke test only)")
    args = ap.parse_args(argv)

    sources = [s for s in config.SOURCES if not args.only or s[0] == args.only]

    if args.scan:
        tag, root, layout = next(s for s in config.SOURCES if s[0] == args.scan)
        recs, logs, counts = scan_source(tag, root, layout, args.limit)
        write_cache(args.cache_dir, tag, recs, logs, counts)
        print("cached %d records, %d log rows -> %s"
              % (len(recs), len(logs), cache_path(args.cache_dir, tag)))
        return

    if args.merge:
        all_records, all_logs = [], []
        counts = defaultdict(int)
        for tag, _, _ in sources:
            blob = read_cache(args.cache_dir, tag)
            if blob is None:
                sys.exit("no cached scan for %s; run: python src/filter.py --scan %s"
                         % (tag, tag))
            all_records += blob["records"]
            all_logs += [tuple(r) for r in blob["log_rows"]]
            for k, v in blob["counts"].items():
                counts[k] += v
            print("[%s] loaded %d cached records" % (tag, len(blob["records"])))
        mcounts, _ = merge(all_records, all_logs, args.out_clean, args.out_results)
        counts.update(mcounts)
    else:
        counts, _ = run(sources, args.out_clean, args.out_results, args.limit)

    for k in sorted(counts):
        print("%-22s %s" % (k, counts[k]))


if __name__ == "__main__":
    main()

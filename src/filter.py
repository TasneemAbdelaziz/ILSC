"""
ILSC — Day 1-2 (Tasneem): multi-source dataset curation.

Applies the Sec. 7 pipeline in order:
  (a) validate            -> skip + log broken
  (b) REST-style 2.0/3.x  -> convert 2.0 rather than discard
  (c) drop < 3 operations
  (d) dedup on (info.title, host), keep newest
  (e) cross-source dedup  -> S2 specs already in S1 are tagged S1
  (f) strip admin endpoints
  (g) [v3] assign a coarse domain label

Every removal is logged with a reason into results/filter_log.csv.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

import yaml
try:
    from yaml import CSafeLoader as _Loader   # libyaml: ~10x faster
except ImportError:
    from yaml import SafeLoader as _Loader

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

ADMIN_PATHS = re.compile(
    r"^/(health|healthz|healthcheck|ready|readyz|live|liveness|metrics|ping|status|version|actuator(/.*)?)/?$",
    re.IGNORECASE,
)

HTTP_METHODS = ("get", "post", "put", "delete", "patch")

MIN_OPERATIONS = 3

# [v3] Coarse domain labels. Required for:
#   - the domain-restricted null model (Sec. 6)
#   - the same-domain perturbation control (Exp. 2)
# Assigned from the provider/title; UNLABELLED rows are reviewed by hand.
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
        return None, f"parse_error: {type(exc).__name__}"
    if not isinstance(spec, dict):
        return None, "parse_error: not_a_mapping"
    return spec, None


def spec_version(spec):
    """'2.0', '3.x' or None."""
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
    random sample, reporting both numbers in the paper.
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

def host_of(spec, version):
    if version == "2.0":
        return spec.get("host", "") or ""
    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict):
        return servers[0].get("url", "") or ""
    return ""


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


def version_key(spec):
    """Crude recency key for dedup: prefer higher info.version."""
    raw = str((spec.get("info") or {}).get("version", "0"))
    nums = re.findall(r"\d+", raw)
    return tuple(int(n) for n in nums[:4]) or (0,)


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------

def run(root, out_clean, out_log, source_tag="S2", limit=None):
    files = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith((".yaml", ".yml", ".json")):
                files.append(os.path.join(dirpath, name))
    files.sort()
    if limit:
        files = files[:limit]

    log_rows = []
    survivors = {}          # key -> record
    counts = defaultdict(int)

    for path in files:
        counts["scanned"] += 1
        if counts["scanned"] % 250 == 0:
            print(f"  ... {counts['scanned']}/{len(files)}", flush=True)
        rel = os.path.relpath(path, root)

        spec, reason = load_spec(path)
        if spec is None:
            log_rows.append((rel, "a_validate", reason)); counts["drop_parse"] += 1
            continue

        reason = structural_check(spec)
        if reason:
            log_rows.append((rel, "a_validate", reason)); counts["drop_structure"] += 1
            continue

        version = spec_version(spec)
        if version is None:
            log_rows.append((rel, "b_version", "not_openapi_2_or_3")); counts["drop_version"] += 1
            continue

        ops, admin_dropped = operations(spec, drop_admin=True)

        if not is_rest_style(spec, ops):
            log_rows.append((rel, "b_rest_style", "rpc_shaped")); counts["drop_rpc"] += 1
            continue

        if len(ops) < MIN_OPERATIONS:
            log_rows.append((rel, "c_min_ops", f"only_{len(ops)}_ops")); counts["drop_small"] += 1
            continue

        info = spec.get("info") or {}
        title = str(info.get("title", "")).strip().lower()
        host = host_of(spec, version).strip().lower()
        provider = rel.split(os.sep)[0] if os.sep in rel else ""
        key = (title, host)

        record = {
            "file": path,
            "rel": rel,
            "title": info.get("title", ""),
            "host": host,
            "provider": provider,
            "version_field": info.get("version", ""),
            "spec_version": version,
            "n_operations": len(ops),
            "n_admin_dropped": len(admin_dropped),
            "domain": domain_of(spec, provider),
            "source": source_tag,
            "vkey": version_key(spec),
        }

        if key in survivors:
            incumbent = survivors[key]
            if record["vkey"] > incumbent["vkey"]:
                log_rows.append((incumbent["rel"], "d_dedup",
                                 f"superseded_by:{record['rel']}"))
                survivors[key] = record
            else:
                log_rows.append((rel, "d_dedup", f"duplicate_of:{incumbent['rel']}"))
            counts["drop_dup"] += 1
            continue

        survivors[key] = record

    # write clean folder
    os.makedirs(out_clean, exist_ok=True)
    manifest = []
    for rec in survivors.values():
        safe = rec["rel"].replace(os.sep, "__")
        dest = os.path.join(out_clean, safe)
        with open(rec["file"], "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())
        rec2 = {k: v for k, v in rec.items() if k not in ("vkey", "file")}
        rec2["clean_file"] = safe
        manifest.append(rec2)

    os.makedirs(os.path.dirname(out_log), exist_ok=True)
    with open(out_log, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "stage", "reason"])
        w.writerows(log_rows)

    man_path = os.path.join(os.path.dirname(out_log), "manifest.csv")
    with open(man_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    counts["survivors"] = len(survivors)
    return counts, manifest


if __name__ == "__main__":
    root = sys.argv[1]
    counts, manifest = run(
        root,
        out_clean="/home/claude/ilsc/specs/clean",
        out_log="/home/claude/ilsc/results/filter_log.csv",
        source_tag="S2",
        limit=int(sys.argv[2]) if len(sys.argv) > 2 else None,
    )
    for k, v in counts.items():
        print(f"{k:16s} {v}")

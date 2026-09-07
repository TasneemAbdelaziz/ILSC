"""
ILSC - Day 1-2 (Mohamed): parser + feature extraction.

Turns the curated corpus into one JSON document per service, holding everything
the similarity engine (Day 3) needs and nothing it does not. Reads
``specs/clean3/`` -- the uniformly OpenAPI 3.x, uniformly JSON corpus that
``src/convert.py`` produces -- so no 2.0/3.x branching is needed here (D-11).

Per operation it extracts:

  method, operationId (or null), path, parameter names, request/response schema
  names, description (or null), summary (or null)

and derives:

  name_tokens   tokenised operationId          -> feature f2
  path_tokens   normalised, tokenised path     -> feature f3
  param_tokens  tokenised parameter names      -> feature f4
  domain_schemas  schema names, generics removed -> feature f5
  T             the embedding text             -> feature f1
  description   kept separate                  -> feature f6

[v3/R2] ``T`` is built WITHOUT the description. In v2 the description appeared
both inside the f1 embedding text and as f6, which double-counted documentation
semantics and -- worse -- meant a missing description silently changed f1 while
the mask still reported f1 as available, defeating the mask. The texts are now
disjoint: each missing field is visible to exactly one mask term. There is a
unit test for this in ``src/test_parse_spec.py``; it fails on the v2 design.

On $ref, deviating from the proposal deliberately
-------------------------------------------------
Sec. 10 says to load specs with ``prance`` because it resolves $ref
automatically. Resolving *everything* would destroy feature f5: f5 is the set of
domain schema *names* an operation touches, and inlining a $ref replaces the
name with its contents. So this module resolves internal ``#/components/...``
pointers where a name or field would otherwise be unreachable (a parameter
declared as ``$ref: '#/components/parameters/PageSize'`` has no name until you
follow it), and records the *target name* for schemas rather than their bodies.
External and unresolvable refs are recorded as-is and counted. This mirrors the
same decision already taken in ``src/convert.py``.

Usage:
    python src/parse_spec.py                 # parse the whole corpus
    python src/parse_spec.py --selftest      # tokenizer / path-normaliser table
    python src/parse_spec.py --spotcheck 5   # re-verify N specs against source
    python src/parse_spec.py --limit 50
"""

import argparse
import json
import os
import random
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import filter as flt                           # noqa: E402  operation source of truth
import config                                  # noqa: E402


# ----------------------------------------------------------------------------
# Tokenisation (Sec. 8, "Parameters")
# ----------------------------------------------------------------------------

_CAMEL_1 = re.compile(r"([a-z0-9])([A-Z])")
# {2,} not + : with + the "acronym" branch fires on a single leading capital
# and splits OAuth into "O Auth". Two or more keeps HTTPServer -> HTTP Server
# while leaving OAuth intact.
_CAMEL_2 = re.compile(r"([A-Z]{2,})([A-Z][a-z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_DIGIT_RUN = re.compile(r"([A-Za-z])(\d+)")
_VERSION = re.compile(r"^v\d+$")


def tokenize(text):
    """lowercase + camelCase/snake_case split + stopword drop.

    getOrderById -> ['order', 'by', 'id']

    Order matters. Stopwords are tested BEFORE letter/digit runs are split,
    because splitting first turns "v2" into "v" + "2" and the pinned stopwords
    `v1`/`v2` can then never match anything. That bug is not cosmetic: nearly
    every Google path begins /v1/, so every within-service pair would have
    shared the tokens "v" and "1", inflating f3 (and f2) across a large part of
    the corpus.
    """
    if not text:
        return []
    s = str(text)
    s = _CAMEL_2.sub(r"\1 \2", s)
    s = _CAMEL_1.sub(r"\1 \2", s)

    out = []
    for part in _SPLIT.split(s):
        if not part:
            continue
        low = part.lower()
        if low in config.TOKEN_STOPWORDS:
            continue
        if config.DROP_VERSION_TOKENS and _VERSION.match(low):
            continue
        for piece in _DIGIT_RUN.sub(r"\1 \2", part).split():
            pl = piece.lower()
            if pl and pl not in config.TOKEN_STOPWORDS:
                out.append(pl)
    return out


def normalize_path(path):
    """/orders/{id}/items -> ['orders', 'items']

    Path parameters are dropped entirely: ``{id}`` is a slot, not a resource,
    and keeping it would make every parameterised path look alike.
    """
    if not path:
        return []
    tokens = []
    for seg in str(path).split("/"):
        seg = seg.strip()
        if not seg or (seg.startswith("{") and seg.endswith("}")):
            continue
        tokens.extend(tokenize(seg))
    return tokens


# ----------------------------------------------------------------------------
# Local $ref resolution
# ----------------------------------------------------------------------------

class Resolver:
    """Follows internal '#/...' JSON pointers, with cycle protection."""

    def __init__(self, spec):
        self.spec = spec
        self.external = 0
        self.unresolved = 0

    def resolve(self, node, _seen=None):
        seen = _seen or set()
        while isinstance(node, dict) and "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                self.external += 1
                return None
            if ref in seen:
                self.unresolved += 1
                return None
            seen.add(ref)
            target = self.spec
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                target, ok = self._step(target, part)
                if not ok:
                    self.unresolved += 1
                    return None
            node = target
        return node

    @staticmethod
    def _step(target, part):
        """One JSON-Pointer hop. Returns (node, ok).

        Handles three things the strict reading does not:
          * list indices, for pointers into `parameters/2`;
          * percent-encoded segments -- DigitalOcean references its own paths as
            `#/paths/~1v2~1databases~1%7Bid%7D~1pools`, encoding the braces of
            `{id}`. JSON Pointer does not percent-decode, so those 204 refs are
            strictly broken, but the author's intent is unambiguous and the
            alternative is silently losing f4/f5 for the whole service.
        """
        if isinstance(target, list):
            try:
                return target[int(part)], True
            except (ValueError, IndexError):
                return None, False
        if not isinstance(target, dict):
            return None, False
        if part in target:
            return target[part], True
        try:
            from urllib.parse import unquote
            decoded = unquote(part)
        except Exception:                                 # noqa: BLE001
            return None, False
        if decoded != part and decoded in target:
            return target[decoded], True
        return None, False

    @staticmethod
    def ref_name(node):
        """Name of a $ref target, e.g. '#/components/schemas/Order' -> 'Order'."""
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            return node["$ref"].rsplit("/", 1)[-1]
        return None


# ----------------------------------------------------------------------------
# Schema-name collection (feature f5)
# ----------------------------------------------------------------------------

def _collect_schema_names(node, res, out, depth=0, seen=None):
    """Walk a schema-bearing node and collect referenced schema NAMES.

    Names, not contents: f5 asks which domain entities an operation touches.
    Inline (anonymous) schemas contribute nothing, which is correct -- an
    unnamed inline object is not a shared domain entity.
    """
    if depth > 6 or not isinstance(node, (dict, list)):
        return
    if isinstance(node, list):
        for item in node:
            _collect_schema_names(item, res, out, depth + 1, seen)
        return

    name = res.ref_name(node)
    if name:
        out.add(name)
        seen = seen or set()
        if name in seen:
            return
        seen.add(name)
        target = res.resolve(node)
        if target is not None:
            _collect_schema_names(target, res, out, depth + 1, seen)
        return

    for key in ("schema", "items", "allOf", "anyOf", "oneOf", "additionalProperties"):
        if key in node:
            _collect_schema_names(node[key], res, out, depth + 1, seen)
    props = node.get("properties")
    if isinstance(props, dict):
        for v in props.values():
            _collect_schema_names(v, res, out, depth + 1, seen)


def request_schemas(op, res):
    out = set()
    body = res.resolve(op.get("requestBody")) if "requestBody" in op else None
    if isinstance(op.get("requestBody"), dict):
        n = res.ref_name(op["requestBody"])
        if n:
            out.add(n)
    if isinstance(body, dict):
        content = body.get("content")
        if isinstance(content, dict):
            for media in content.values():
                if isinstance(media, dict) and "schema" in media:
                    _collect_schema_names(media["schema"], res, out)
    return out


def response_schemas(op, res):
    out = set()
    responses = op.get("responses")
    if not isinstance(responses, dict):
        return out
    for code, resp in responses.items():
        if isinstance(code, str) and code.lower().startswith("x-"):
            continue
        n = res.ref_name(resp) if isinstance(resp, dict) else None
        if n:
            out.add(n)
        resolved = res.resolve(resp) if isinstance(resp, dict) else None
        if not isinstance(resolved, dict):
            continue
        content = resolved.get("content")
        if isinstance(content, dict):
            for media in content.values():
                if isinstance(media, dict) and "schema" in media:
                    _collect_schema_names(media["schema"], res, out)
    return out


# ----------------------------------------------------------------------------
# Parameters (feature f4)
# ----------------------------------------------------------------------------

def parameter_names(path_item, op, res):
    """Path-level parameters apply to every operation on the path; union them
    with the operation-level ones, then de-duplicate on (name, in)."""
    found = {}
    for source in (path_item, op):
        if not isinstance(source, dict):
            continue
        params = source.get("parameters")
        if not isinstance(params, list):
            continue
        for p in params:
            resolved = res.resolve(p) if isinstance(p, dict) else None
            if not isinstance(resolved, dict):
                continue
            name = resolved.get("name")
            if isinstance(name, str) and name.strip():
                found[(name, resolved.get("in", ""))] = name
    return sorted(set(found.values()))


# ----------------------------------------------------------------------------
# The operation record
# ----------------------------------------------------------------------------

def build_T(method, name_tokens, path_tokens, param_tokens, schema_tokens):
    """D1 -- the embedding text for feature f1.

    [METHOD] m [NAME] n [PATH] p [PARAMS] par [SCHEMA] s

    The description is deliberately absent; it enters only through f6 (R2).
    """
    return " ".join([
        "[METHOD]", method.lower(),
        "[NAME]", " ".join(name_tokens),
        "[PATH]", " ".join(path_tokens),
        "[PARAMS]", " ".join(param_tokens),
        "[SCHEMA]", " ".join(schema_tokens),
    ])


def _nonempty(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def parse_service(spec, meta):
    """Return the parsed document for one service, or (None, reason)."""
    res = Resolver(spec)
    ops_expected, _ = flt.operations(spec, drop_admin=True)
    expected = set(ops_expected)

    records = []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in config.HTTP_METHODS:
                continue
            if (method.upper(), path) not in expected:
                continue                       # admin endpoint, already dropped
            if not isinstance(op, dict):
                op = {}

            op_id = _nonempty(op.get("operationId"))
            params = parameter_names(item, op, res)
            schemas = request_schemas(op, res) | response_schemas(op, res)

            records.append({
                "op_key": method.upper() + " " + str(path),
                "method": method.upper(),
                "path": str(path),
                "operation_id": op_id,
                "param_names": params,
                "schema_names": sorted(schemas),
                "description": _nonempty(op.get("description")),
                "summary": _nonempty(op.get("summary")),
            })

    got = {(r["method"], r["path"]) for r in records}
    if got != expected:
        return None, ("operation set diverged from filter.operations(): "
                      "+%d / -%d" % (len(got - expected), len(expected - got)))

    # --- f5 exclusions, computed per service --------------------------------
    # config.GENERIC_SCHEMAS is the fixed list; the >80% rule is per-service
    # (Sec. 6): a schema on nearly every operation carries no domain signal.
    n_ops = len(records)
    freq = {}
    for r in records:
        for s in r["schema_names"]:
            freq[s] = freq.get(s, 0) + 1
    frequent = sorted(s for s, c in freq.items()
                      if n_ops and c / n_ops > config.FREQUENT_SCHEMA_RATIO)
    generic_hit = sorted({s for s in freq if s.lower() in config.GENERIC_SCHEMAS})
    excluded = set(frequent) | {s for s in freq if s.lower() in config.GENERIC_SCHEMAS}

    for r in records:
        r["domain_schemas"] = sorted(s for s in r["schema_names"] if s not in excluded)
        r["name_tokens"] = tokenize(r["operation_id"]) if r["operation_id"] else []
        r["path_tokens"] = normalize_path(r["path"])
        r["param_tokens"] = sorted({t for p in r["param_names"] for t in tokenize(p)})
        schema_tokens = sorted({t for s in r["domain_schemas"] for t in tokenize(s)})
        r["schema_tokens"] = schema_tokens
        r["T"] = build_T(r["method"], r["name_tokens"], r["path_tokens"],
                         r["param_tokens"], schema_tokens)

    records.sort(key=lambda r: r["op_key"])
    return {
        "clean_file": meta.get("clean_file", ""),
        "title": meta.get("title", ""),
        "provider": meta.get("provider", ""),
        "source": meta.get("source", ""),
        "spec_version": meta.get("spec_version", ""),
        "n_operations": n_ops,
        "generic_schemas_excluded": generic_hit,
        "frequent_schemas_excluded": frequent,
        "external_refs": res.external,
        "unresolved_refs": res.unresolved,
        "operations": records,
    }, None


# ----------------------------------------------------------------------------
# Self-test: the tokenizer table Sec. 10 asks to eyeball
# ----------------------------------------------------------------------------

TRICKY_NAMES = [
    "getOrderById", "list_users_v2", "HTTPServerError", "getPetsUsingGET_1",
    "createV2Widget", "OAuth2Token", "delete-all-users", "XMLHttpRequest",
    "postCustomerAddress", "api_v1_listAll",
]
TRICKY_PATHS = [
    "/orders/{id}/items", "/v1/projects/{projectId}/locations",
    "/applicationSecurityGroups/{name}", "/", "/users/{userId}/payment-methods",
]


def selftest():
    print("Tokenizer  (lowercase + camelCase/snake split + stopword drop)")
    print("  stopwords: %s\n" % sorted(config.TOKEN_STOPWORDS))
    for n in TRICKY_NAMES:
        print("  %-22s -> %s" % (n, tokenize(n)))
    print("\nPath normaliser  (drop {params}, split on /)")
    for p in TRICKY_PATHS:
        print("  %-38s -> %s" % (p, normalize_path(p)))
    print("\nT(Oi) -- note there is no description in it (R2):")
    t = build_T("GET", tokenize("getOrderById"), normalize_path("/orders/{id}/items"),
                ["id"], ["order", "item"])
    print("  " + t)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def load_manifest(path):
    import csv
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["clean_file"]: r for r in csv.DictReader(fh)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC Day 1-2 parser.")
    ap.add_argument("--specs-dir", default=config.SPECS_CLEAN3)
    ap.add_argument("--out-dir", default=config.PARSED_DIR)
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--selftest", action="store_true",
                    help="print the tokenizer/path tables and exit")
    ap.add_argument("--spotcheck", type=int, default=0,
                    help="re-verify N parsed services against their specs")
    args = ap.parse_args(argv)

    if args.selftest:
        selftest()
        return

    manifest = load_manifest(args.manifest)
    if args.spotcheck:
        return spotcheck(args, manifest)

    os.makedirs(args.out_dir, exist_ok=True)
    files = sorted(n for n in os.listdir(args.specs_dir) if n.endswith(".json"))
    if args.limit:
        files = files[: args.limit]
    print("parsing %d services from %s" % (len(files), args.specs_dir), flush=True)

    ok, skipped, total_ops = 0, [], 0
    ext_refs = unres_refs = 0
    for i, name in enumerate(files, 1):
        if i % 250 == 0:
            print("  ... %d/%d" % (i, len(files)), flush=True)
        clean_file = _clean_file_for(name, manifest)
        spec, reason = flt.load_spec(os.path.join(args.specs_dir, name))
        if spec is None:
            skipped.append((name, reason))
            continue
        doc, reason = parse_service(spec, manifest.get(clean_file, {"clean_file": clean_file}))
        if doc is None:
            skipped.append((name, reason))
            continue
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        ok += 1
        total_ops += doc["n_operations"]
        ext_refs += doc["external_refs"]
        unres_refs += doc["unresolved_refs"]

    print("\nparsed   %d services, %s operations -> %s"
          % (ok, "{:,}".format(total_ops), args.out_dir))
    print("skipped  %d" % len(skipped))
    for n, r in skipped[:10]:
        print("   %-52s %s" % (n[:52], r))
    print("refs     %d external (not followed), %d unresolved"
          % (ext_refs, unres_refs))


def _clean_file_for(parsed_name, manifest):
    """parsed/<stem>.json came from clean3/<stem>.json, whose manifest key is
    the ORIGINAL clean_file (which may end .yaml)."""
    if parsed_name in manifest:
        return parsed_name
    stem = os.path.splitext(parsed_name)[0]
    for ext in (".yaml", ".yml", ".json"):
        if stem + ext in manifest:
            return stem + ext
    return parsed_name


def spotcheck(args, manifest):
    """Sec. 10, step 8: re-verify N random parsed services against their specs.

    Wrong fields here poison everything downstream, so this compares the parsed
    document back against the source spec rather than trusting the writer.
    """
    files = sorted(n for n in os.listdir(args.out_dir) if n.endswith(".json"))
    picks = random.Random(config.SEED).sample(files, min(args.spotcheck, len(files)))
    print("spot-checking %d parsed services (seed %d)\n" % (len(picks), config.SEED))

    failures = 0
    for name in picks:
        with open(os.path.join(args.out_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        spec, _ = flt.load_spec(os.path.join(args.specs_dir, name))
        expected, _ = flt.operations(spec, drop_admin=True)
        got = {(o["method"], o["path"]) for o in doc["operations"]}

        problems = []
        if got != set(expected):
            problems.append("operation set mismatch")
        for o in doc["operations"]:
            if o["description"] is not None and o["description"] in o["T"]:
                problems.append("description leaked into T (R2 violation): " + o["op_key"])
                break
            if o["operation_id"] and not o["name_tokens"]:
                problems.append("operationId present but no name tokens: " + o["op_key"])
                break
        print("  %-46s ops=%-5d %s" % (doc["title"][:46] or name[:46], len(got),
                                       "OK" if not problems else "FAIL " + problems[0]))
        failures += bool(problems)

    print("\n%d/%d passed" % (len(picks) - failures, len(picks)))
    if failures:
        sys.exit("spot-check failed")


if __name__ == "__main__":
    main()

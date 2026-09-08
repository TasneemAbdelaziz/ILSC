"""
ILSC - Day 7 empirical track: automated endpoint -> entity extraction for Train Ticket.

Exp. 3 needs a code-side entity set for every endpoint. Sock Shop's 27 endpoints
were dug out by hand (``results/endpoint_entities.csv``, ``extraction=manual``).
Train Ticket has **34 services and 211 endpoints**, which is roughly seven times
the work, and D-16 admits it only as a separate ``rho_derived`` condition. Doing
it by hand would cost two weeks the schedule does not have.

Train Ticket is the case where a parser genuinely beats a reader: one language,
one framework, one annotation vocabulary, 34 times over. So this module extracts
mechanically and the accuracy is **measured, not asserted** - a 10-service manual
sample is compared against it and the agreement is reported (``--sample`` writes
the sheet, ``--score`` scores it). An extraction with no agreement figure is a
standard reviewer objection and is not worth having.

How an entity set is derived
----------------------------
1. **The entity vocabulary is global, not per service.** Train Ticket keeps its
   domain model in a shared module - ``ts-common/edu/fudan/common/entity/``,
   ~40 types - and most services declare no entity package of their own. A
   per-service vocabulary therefore finds nothing across half the system: the
   first version of this pass did exactly that and returned an empty set for
   **52% of endpoints**. The vocabulary is now the union of ``ts-common`` and
   every service-local ``entity``/``entities``/``domain`` package, plus anything
   annotated ``@Entity``, ``@Document`` or ``@Table``. Types in ``dto``/
   ``request``/``response``/``config`` packages are excluded, mirroring the
   manual rule in ``docs/responsibilities.md`` §4 - transport shapes are not
   domain entities.

   **Import scoping keeps the global vocabulary from over-matching.** A type
   only counts for a file that actually imports it, or declares it locally. An
   ``import ...entity.*`` admits the whole shared module - that is the author's
   own statement of scope, not an assumption of ours.
2. **The endpoints** from ``@RestController`` classes: the class-level
   ``@RequestMapping`` path concatenated with each method-level mapping, and the
   HTTP verb from the annotation.
3. **The entity set** for a method: the vocabulary names appearing in the
   method's signature, in its body, and in the body of the **one** service-layer
   method it delegates to. One hop, not a full call graph - deeper tracing on a
   codebase this size produces more false positives than it removes false
   negatives, and the sample measures the cost of stopping there.

Known and declared limits
-------------------------
- **One delegation hop.** Entities touched only three layers down are missed.
- **Name matching, not type resolution.** A comment mentioning ``Order`` counts.
  Comments and string literals are stripped first, which removes most of it.
- **Generated specs, generated extraction.** Both sides of Train Ticket's
  ``rho_derived`` are machine-derived. That is exactly why D-16 keeps it out of
  the pooled estimate.
- **F-03 applies.** ``docs/responsibilities.md`` §2 was written from the specs,
  so it must not be used to guide or check this pass. The manual sample must be
  taken from the Java sources.

Usage:
    python src/entity_extract.py --src <train-ticket checkout> --out results/endpoint_entities_trainticket.csv
    python src/entity_extract.py --src ... --sample 10       # blank sheet for manual re-derivation
    python src/entity_extract.py --score results/entity_agreement_sample.csv
"""

import argparse
import csv
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                    # noqa: E402

ENTITY_PKG = re.compile(r"[\\/](entity|entities|domain|model)[\\/]", re.IGNORECASE)
EXCLUDE_PKG = re.compile(r"[\\/](dto|request|response|config|util|utils|exception|"
                         r"async|init|controller|repository|service|security)[\\/]",
                         re.IGNORECASE)
ENTITY_ANNOTATION = re.compile(r"@(Entity|Document|Table)\b")
CLASS_DECL = re.compile(r"\b(?:public\s+|abstract\s+|final\s+)*(?:class|enum)\s+(\w+)")

# Types that are domain-flavoured but are not entities - the mirror of
# GENERIC_SCHEMAS on the interface side, and of docs/responsibilities.md 4.
EXCLUDE_TYPES = {
    "Response", "Request", "Result", "Error", "Exception", "Status", "Message",
    "Page", "PageInfo", "Pagination", "Meta", "Link", "Empty", "Object", "String",
    "List", "Map", "Set", "Date", "UUID", "Boolean", "Integer", "Long", "Float",
    "Double", "HttpHeaders", "HttpEntity", "ResponseEntity", "Logger", "Config",
}

# The argument list is OPTIONAL. A bare `@PostMapping` maps the method onto the
# class-level @RequestMapping path with no sub-path of its own, and Train Ticket
# uses that form for exactly the endpoints you would expect - the collection
# root, `POST /api/v1/auth`, `GET /api/v1/users`. Requiring the parentheses
# silently skipped every one of them.
MAPPING = re.compile(
    r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*(?:\(([^)]*)\))?", re.DOTALL)
PATH_IN_ANN = re.compile(r'(?:value|path)\s*=\s*(?:\{\s*)?"([^"]*)"|^\s*"([^"]*)"')
METHOD_IN_ANN = re.compile(r"RequestMethod\.(GET|POST|PUT|DELETE|PATCH)")
METHOD_DECL = re.compile(r"\)\s*\{")
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
STRING_LIT = re.compile(r'"(?:[^"\\]|\\.)*"')


def scan(src):
    """One lexing pass producing two aligned views of a Java file.

    Returns ``(ann, txt)``, both exactly as long as ``src``:

      ``ann``  comments blanked, **string literals kept** - annotations are read
               from this, so ``@RequestMapping("/api/v1/x")`` still has its path.
      ``txt``  comments *and* literal contents blanked - entity names are matched
               in this, so a log line like ``"[create][Create station]"`` cannot
               make an endpoint look as though it touches ``Station``.

    Equal length is what lets one offset mean the same thing in both views.

    **Why this is a single pass and not two regex substitutions.** The first
    version stripped comments and then strings, with separate regexes. On
    ``return "http://" + serviceName;`` the comment pass saw the ``//`` *inside
    the string literal*, blanked to end of line, and took the closing quote with
    it; the string pass then matched from the next quote in the file and blanked
    everything up to it. One line of ordinary Java silently erased the rest of
    the file, and with it every method body the delegation hop needed. Comments
    and literals cannot be recognised independently - whichever runs first is
    wrong inside the other - so they are recognised together, here.
    """
    n = len(src)
    ann, txt = list(src), list(src)
    i = 0
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                ann[k] = txt[k] = " "
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if src[k] != "\n":              # keep line numbers meaningful
                    ann[k] = txt[k] = " "
            i = j
        elif c in '"\'':
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                if src[j] == "\n":              # unterminated - do not run away
                    break
                j += 1
            for k in range(i + 1, min(j - 1, n)):
                txt[k] = " "
            i = j
        else:
            i += 1
    return "".join(ann), "".join(txt)


def strip_noise(src):
    """The entity-matching view. Kept as a helper for the vocabulary builder."""
    return scan(src)[1]


def service_dirs(root):
    """Top-level ts-*-service module directories."""
    out = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and name.startswith("ts-") and name.endswith("-service"):
            out.append((name, p))
    return out


LANG_MARKERS = ((".java", "Java"), (".go", "Go"), (".py", "Python"),
                (".js", "JavaScript"), (".ts", "TypeScript"), (".cs", "C#"))


def _language_of(root):
    """Best-effort language label for a service that produced no endpoints."""
    counts = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            for ext, lang in LANG_MARKERS:
                if f.endswith(ext):
                    counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "no recognised source files"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def java_files(root):
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + "test" + os.sep in dirpath + os.sep:
            continue
        for f in files:
            if f.endswith(".java"):
                yield os.path.join(dirpath, f)


IMPORT_ENTITY = re.compile(r"import\s+[\w.]*\.(?:entity|entities|domain|model)\.(\w+|\*)\s*;")


def in_scope(raw, global_vocab, local_vocab):
    """Which vocabulary types this file may legitimately refer to.

    Import-scoped, so a global vocabulary cannot match a type the file never
    sees. A wildcard entity import admits the whole shared module.
    """
    scope = set(local_vocab)
    for name in IMPORT_ENTITY.findall(raw):
        if name == "*":
            return set(global_vocab)
        if name in global_vocab:
            scope.add(name)
    return scope


def entity_vocabulary(svc_root):
    """Domain entity class names found anywhere under ``svc_root``."""
    names = set()
    for path in java_files(svc_root):
        raw = _read(path)
        if raw is None:
            continue
        in_entity_pkg = bool(ENTITY_PKG.search(path)) and not EXCLUDE_PKG.search(path)
        annotated = bool(ENTITY_ANNOTATION.search(raw))
        if not (in_entity_pkg or annotated):
            continue
        m = CLASS_DECL.search(strip_noise(raw))
        if not m:
            continue
        # EXCLUDE_TYPES is a guess about generic names; an entity package is the
        # author's own statement. The author wins - `ts-config-service` really
        # does own an entity called `Config`, and blocking the name by pattern
        # emptied every one of that service's endpoints.
        if in_entity_pkg or m.group(1) not in EXCLUDE_TYPES:
            names.add(m.group(1))
    return names


def _read(path):
    for enc in ("utf-8", "latin-1"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except (UnicodeDecodeError, OSError):
            continue
    return None


def _ann_path(args_text):
    """Sub-path from a mapping annotation. `None` means the annotation had no
    argument list at all - a bare `@PostMapping` - which is an empty sub-path,
    not a missing endpoint."""
    if not args_text:
        return ""
    m = PATH_IN_ANN.search(args_text)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def _ann_method(kind, args_text):
    if kind != "Request":
        return kind.upper()
    m = METHOD_IN_ANN.search(args_text or "")
    return m.group(1) if m else "GET"


def _body_after(src, start):
    """The brace-balanced block following position ``start``."""
    i = src.find("{", start)
    if i < 0:
        return ""
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return src[i:]


REPO_DECL = re.compile(
    r"\binterface\s+(\w+)\s+extends\s+[\w.]*Repository\s*<\s*(\w+)", re.DOTALL)
REPO_FIELD = re.compile(r"\b(\w*Repository)\s+(\w+)\s*[;=]")


def repository_map(root):
    """RepositoryTypeName -> the entity it is parameterised on.

    The proposal's instruction is to trace "which repositories, which model
    classes". Matching model-class *names* in a method body finds the second and
    misses the first: a Spring Data method like

        public boolean delete(String id) {
            if (repository.findById(id).isPresent()) { repository.deleteById(id); }
        }

    touches its aggregate root through the repository and never names the entity
    at all - `TrainType` appears only inside a log string, which the lexer
    correctly blanks. Twelve endpoints came back empty for exactly this reason.
    The repository's own generic parameter names the entity, so resolving it
    recovers them.
    """
    out = {}
    for path in java_files(root):
        raw = _read(path)
        if raw is None or "Repository" not in raw:
            continue
        for repo, entity in REPO_DECL.findall(strip_noise(raw)):
            out[repo] = entity
    return out


def _repo_fields(src, repo_map):
    """field name -> entity, for repository-typed fields declared in this file."""
    out = {}
    for repo_type, field in REPO_FIELD.findall(src):
        if repo_type in repo_map:
            out[field] = repo_map[repo_type]
    return out


def _entities_via_repositories(text, fields, repo_map):
    """Entities reached through a repository reference in ``text``."""
    found = set()
    for field, entity in fields.items():
        if re.search(r"\b%s\s*\." % re.escape(field), text):
            found.add(entity)
    for repo_type, entity in repo_map.items():          # direct type reference
        if re.search(r"\b%s\b" % re.escape(repo_type), text):
            found.add(entity)
    return found


def service_layer_bodies(svc_root, repo_map, global_vocab=None, local_vocab=None):
    """method name -> list of (body, repository fields, entity scope of its file).

    The scope travels with the body. A controller often imports one entity while
    the service it delegates to imports the whole shared module: `BasicController`
    imports only `entity.Travel`, but `BasicServiceImpl` imports `entity.*` and
    its body touches `TravelResult`, `TrainType` and `Route`. Scoping the appended
    text by the *controller's* imports discarded all three. Each body is therefore
    matched against the scope of the file it came from, unioned with the
    controller's own.
    """
    out = {}
    for path in java_files(svc_root):
        # Match on the class name as well as the package. `ts-execute-service`
        # spells its package `serivce`, and a filter keyed only on the directory
        # silently skipped every delegation body in that service - a typo in
        # someone else's repository should not quietly remove a whole service
        # from the extraction.
        base = os.path.basename(path)
        if not (re.search(r"[\\/]ser[a-z]{4}e[\\/]", path, re.IGNORECASE)
                or base.endswith("Service.java") or base.endswith("ServiceImpl.java")):
            continue
        raw = _read(path)
        if raw is None:
            continue
        src = strip_noise(raw)
        fields = _repo_fields(src, repo_map)
        fscope = (in_scope(raw, global_vocab or set(), local_vocab or set())
                  if global_vocab is not None else set())
        for m in re.finditer(r"\b(?:public|protected)\s+[\w<>\[\],\s.?]+\s+(\w+)\s*\(", src):
            body = _body_after(src, m.end())
            if body:
                out.setdefault(m.group(1), []).append((body, fields, fscope))
    return out


def extract_service(svc_name, svc_root, global_vocab):
    local_vocab = entity_vocabulary(svc_root)
    repo_map = repository_map(svc_root)
    vocab = set(global_vocab) | local_vocab
    svc_bodies = service_layer_bodies(svc_root, repo_map, vocab, local_vocab)
    rows = []

    for path in java_files(svc_root):
        raw = _read(path)
        if raw is None or "@RestController" not in raw and "@Controller" not in raw:
            continue
        ann_src, src = scan(raw)          # aligned views: annotations / entity names
        scope = in_scope(raw, vocab, local_vocab)
        ctrl_fields = _repo_fields(src, repo_map)

        base = ""
        head = ann_src[: ann_src.find("class ") if "class " in ann_src else len(ann_src)]
        bm = MAPPING.search(head)
        if bm:
            base = _ann_path(bm.group(2))
        consumed_end = bm.end() if bm else 0

        for m in MAPPING.finditer(ann_src, consumed_end):
            kind, ann = m.group(1), m.group(2)
            sub = _ann_path(ann)
            verb = _ann_method(kind, ann)
            body = _body_after(src, m.end())
            sig_end = src.find("{", m.end())
            sig = src[m.end(): sig_end] if sig_end > 0 else ""

            text = sig + " " + body
            via_repo = _entities_via_repositories(body, ctrl_fields, repo_map)
            # one delegation hop into the service layer; each appended body
            # carries its own import scope, unioned with the controller's
            eff_scope = set(scope)
            for called in set(re.findall(r"\.(\w+)\s*\(", body)):
                for b, fields, fscope in svc_bodies.get(called, []):
                    text += " " + b
                    eff_scope |= fscope
                    via_repo |= _entities_via_repositories(b, fields, repo_map)

            found = {v for v in eff_scope
                     if re.search(r"\b%s\b" % re.escape(v), text)}
            # An entity reached only through its repository is still touched.
            found |= (via_repo & vocab)
            full = "/" + "/".join(p for p in (base.strip("/"), sub.strip("/")) if p)
            rows.append({
                "system": "trainticket", "service": svc_name,
                "method": verb, "path": full,
                "operation_id": "",
                "entities": "|".join(sorted(found)),
                "n_entities": len(found),
                "extraction": "automated",
                "evidence": os.path.relpath(path, svc_root).replace("\\", "/"),
                "notes": "one-hop delegation; %d types in scope" % len(eff_scope),
            })
    return rows, vocab


def run(args):
    if not os.path.isdir(args.src):
        sys.exit("source tree not found: %s\nClone FudanSELab/train-ticket first." % args.src)
    svcs = service_dirs(args.src)
    if not svcs:
        sys.exit("no ts-*-service directories under %s" % args.src)

    # The shared module first - most services declare no entities of their own.
    global_vocab = set()
    common = os.path.join(args.src, "ts-common")
    if os.path.isdir(common):
        global_vocab |= entity_vocabulary(common)
        print("shared vocabulary from ts-common: %d entity types" % len(global_vocab))
    for _name, root in svcs:
        global_vocab |= entity_vocabulary(root)
    print("global vocabulary: %d entity types\n" % len(global_vocab))

    all_rows, no_controller = [], []
    for name, root in svcs:
        rows, local_vocab = extract_service(name, root, global_vocab)
        all_rows.extend(rows)
        if not rows:
            no_controller.append((name, _language_of(root)))
        print("  %-34s %3d endpoints  %2d local types" % (name, len(rows), len(local_vocab)))

    if no_controller:
        print("\n%d service(s) yielded no endpoints - this extractor reads Java/Spring"
              " only:" % len(no_controller))
        for name, lang in no_controller:
            print("   %-34s %s" % (name, lang))
        print("  Train Ticket is NOT a pure-Java system. These services need either a")
        print("  per-language extractor or a manual pass; they must not be silently")
        print("  treated as endpoints that touch no entities.")

    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cols = ["system", "service", "method", "path", "operation_id", "entities",
            "n_entities", "extraction", "evidence", "notes"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    empty = sum(1 for r in all_rows if r["n_entities"] == 0)
    print("\n%d services, %d endpoints -> %s" % (len(svcs), len(all_rows), out))
    print("  endpoints with an empty entity set: %d (%.1f%%)"
          % (empty, 100.0 * empty / max(len(all_rows), 1)))
    print("  These are the extraction's visible failures; they are NOT evidence")
    print("  that the endpoint touches nothing. Check them in the sample.")

    if args.sample:
        write_sample(all_rows, args.sample)


def write_sample(rows, k):
    """A blank sheet for independent manual re-derivation (the reliability check)."""
    import random
    rng = random.Random(config.SEED)
    # `/welcome` and `/hello` return a String and touch nothing by construction.
    # They are ~15% of endpoints, so an unfiltered draw fills the sheet with rows
    # whose correct answer is "empty" - agreement on those is free and measures
    # nothing. The reliability figure should describe the endpoints where the
    # extraction actually does work, so they are excluded and that is stated.
    eligible = [r for r in rows
                if not re.search(r"/(welcome|hello)$", r["path"], re.IGNORECASE)]
    by_service = {}
    for r in eligible:
        by_service.setdefault(r["service"], []).append(r)
    if not by_service:
        sys.exit("no eligible endpoints to sample")
    services = rng.sample(sorted(by_service), min(k, len(by_service)))
    picks = [rng.choice(by_service[s]) for s in services]

    out = os.path.join(config.RESULTS_DIR, "entity_agreement_sample.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["service", "method", "path", "evidence",
                    "entities_manual", "entities_automated"])
        for r in picks:
            # automated answer written last so it can be hidden while annotating
            w.writerow([r["service"], r["method"], r["path"], r["evidence"],
                        "", r["entities"]])
    print("\nwrote %s - %d endpoints, one per service." % (out, len(picks)))
    print("  /welcome and /hello are excluded: they return a String and touch")
    print("  nothing by construction, so agreement on them would be free. State")
    print("  that exclusion when reporting the figure.")
    print("  Fill entities_manual FROM THE JAVA SOURCES - F-03: not from")
    print("  docs/responsibilities.md, which was written from the specs. Then:")
    print("    python src/entity_extract.py --score %s" % out)


def score(path):
    """Jaccard agreement between the manual and automated sets.

    An endpoint whose correct answer is *no entities* must be scorable. Writing
    it as a blank cell is indistinguishable from "not yet annotated", so the
    convention is an explicit ``-``. Treating blanks as unannotated silently
    dropped every genuinely-empty endpoint from the sample and biased the figure
    toward the cases where the extractor had something to find.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["entities_manual"].strip()]
    if not rows:
        sys.exit("no annotated rows in %s - fill entities_manual first\n"
                 "  (use '-' for an endpoint that genuinely touches no entity)" % path)
    js, exact = [], 0
    print("\n  %-30s %-28s %s" % ("endpoint", "manual", "automated"))
    for r in rows:
        A = {x for x in r["entities_manual"].split("|") if x}
        B = {x for x in r["entities_automated"].split("|") if x}
        j = len(A & B) / len(A | B) if (A | B) else 1.0
        js.append(j)
        exact += int(A == B)
        print("  %-30s %-28s %-28s  J=%.2f"
              % ((r["service"] + " " + r["path"])[:30],
                 "|".join(sorted(A))[:28], "|".join(sorted(B))[:28], j))
    n = len(js)
    print("\n  endpoints re-derived independently : %d" % n)
    print("  exact set agreement                : %d (%.0f%%)" % (exact, 100.0 * exact / n))
    print("  mean Jaccard agreement             : %.3f" % (sum(js) / n))
    print("  min                                : %.3f" % min(js))
    n_empty = sum(1 for r in rows
                  if not {x for x in r["entities_manual"].split("|")
                          if x and x != "-"})
    print("  of which the correct answer is 'no entities' : %d" % n_empty)
    print("\n  Report this figure with rho_derived. An extraction without an")
    print("  agreement number is a standard reviewer objection (proposal Sec. 11).")
    print("\n  STATE WHAT THIS FIGURE IS. If the annotator could see the")
    print("  entities_automated column while working, this is VERIFICATION of the")
    print("  extractor against its sources: it reliably catches entities *claimed")
    print("  but not present*, and is weaker at catching entities *present but")
    print("  missed*. It is NOT a blind inter-annotator agreement figure, and")
    print("  reporting it as one would overstate it. A blind figure needs the last")
    print("  column hidden and a reader who did not build the extractor.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Train Ticket entity extraction.")
    ap.add_argument("--src", default=None, help="train-ticket checkout root")
    ap.add_argument("--out", default=os.path.join(config.RESULTS_DIR,
                                                  "endpoint_entities_trainticket.csv"))
    ap.add_argument("--sample", type=int, default=0,
                    help="also write a blank N-service sheet for manual re-derivation")
    ap.add_argument("--score", default=None, help="score a filled sample sheet")
    args = ap.parse_args(argv)
    if args.score:
        return score(args.score)
    if not args.src:
        ap.error("--src is required unless --score is given")
    run(args)


if __name__ == "__main__":
    main()

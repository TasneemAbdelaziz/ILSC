"""
ILSC - shared operation pool.

Both the null models (Exp. 1) and the perturbation injector (Exp. 2) need the
same thing: every operation in the corpus as a flat, indexable bag, each row
carrying its parsed features, its embedding rows and the service it came from.
Building that twice would be two chances to build it differently, so it is built
here once.

The pool honours D-17 by default: ``oversized`` services are excluded, because a
null model drawn from a pool that is 84% Microsoft Graph is a statement about
Microsoft Graph. ``--include-oversized`` restores them for the sensitivity run.
"""

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                   # noqa: E402
import embed as emb_mod                         # noqa: E402
import similarity as sim                        # noqa: E402


class Pool:
    """Flat bag of operations with aligned feature records and vectors."""

    def __init__(self, ops, T, D, service_of, provider_of, meta):
        self.ops = ops                  # list of parsed operation dicts
        self.T = T                      # (N, dim) normalised
        self.D = D                      # (N, dim), zero rows where no description
        self.service_of = service_of    # parallel list: parsed file name
        self.provider_of = provider_of  # parallel list: provider string
        self.meta = meta                # per-service manifest row
        self.n = len(ops)

        self.by_provider = {}
        for i, p in enumerate(provider_of):
            self.by_provider.setdefault(p, []).append(i)
        self.by_service = {}
        for i, s in enumerate(service_of):
            self.by_service.setdefault(s, []).append(i)

        # Token sets for f2..f5, built once. The null models sample hundreds of
        # thousands of pairs; rebuilding these per pair made the set arithmetic,
        # not the embeddings, the cost of the run.
        self.sets = []
        self.f2_ok = []
        for o in ops:
            self.sets.append((
                set(o.get("name_tokens") or []),
                set(o.get("path_tokens") or []),
                set(o.get("param_tokens") or []),
                {sim.normalise_schema(s) for s in (o.get("domain_schemas") or [])},
            ))
            opid = o.get("operation_id")
            self.f2_ok.append(bool(opid and opid.strip())
                              and not sim.is_codegen_placeholder(opid))

    def opset(self, idx):
        """An OpSet over the given pool indices."""
        idx = list(idx)
        return sim.OpSet([self.ops[i] for i in idx], self.T[idx], self.D[idx])

    def __len__(self):
        return self.n


def load_manifest(path):
    import csv
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["clean_file"]: r for r in csv.DictReader(fh)}


def _clean_file_for(parsed_name, manifest):
    if parsed_name in manifest:
        return parsed_name
    stem = os.path.splitext(parsed_name)[0]
    for ext in (".yaml", ".yml", ".json"):
        if stem + ext in manifest:
            return stem + ext
    return parsed_name


def load_pool(parsed_dir=None, cache_dir=None, manifest_path=None,
              include_oversized=False, limit=None, verbose=True):
    parsed_dir = parsed_dir or config.PARSED_DIR
    cache_dir = cache_dir or emb_mod.DEFAULT_CACHE
    manifest_path = manifest_path or os.path.join(config.RESULTS_DIR, "manifest.csv")

    emb = emb_mod.Embeddings(cache_dir)
    manifest = load_manifest(manifest_path)
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    if limit:
        files = files[:limit]

    ops, t_rows, d_rows, service_of, provider_of, meta = [], [], [], [], [], {}
    n_oversized = 0
    for name in files:
        if name not in emb:
            continue
        clean = _clean_file_for(name, manifest)
        row = manifest.get(clean, {})
        oversized = str(row.get("oversized", "")).strip().lower() in ("1", "true", "yes")
        if oversized and not include_oversized:
            n_oversized += 1
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        meta[name] = {"clean_file": clean, "title": doc.get("title", ""),
                      "provider": doc.get("provider", ""), "source": doc.get("source", ""),
                      "oversized": oversized, "n_operations": doc["n_operations"]}
        tr, dr = emb.rows_T(name), emb.rows_D(name)
        for i, o in enumerate(doc["operations"]):
            ops.append(o)
            t_rows.append(tr[i])
            d_rows.append(dr[i])
            service_of.append(name)
            provider_of.append(doc.get("provider", ""))

    T = emb.T[t_rows] if t_rows else np.zeros((0, emb.T.shape[1]), dtype="float32")
    D = np.zeros((len(d_rows), emb.D.shape[1]), dtype="float32")
    have = [i for i, r in enumerate(d_rows) if r >= 0]
    if have:
        D[have] = emb.D[[d_rows[i] for i in have]]

    if verbose:
        print("pool: %s operations from %d services%s"
              % ("{:,}".format(len(ops)), len(meta),
                 "" if include_oversized else "  (%d oversized excluded, D-17)" % n_oversized))
    return Pool(ops, T, D, service_of, provider_of, meta)

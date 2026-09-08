"""
ILSC - Day 3 metric track (Mohamed): the embedding cache.

Embeds every operation of the parsed corpus exactly once and writes the result
to disk. Every downstream experiment - Gate 1, Exp. 1, the null models, the
perturbation runs, Exp. 3, Exp. 5 - reads this cache and never calls the model
again. That is not only a speed decision: it is what makes the sensitivity
analyses comparable, because a weight sweep and a tau sweep must be re-scoring
*identical* vectors, not re-embedding text under a possibly different model
revision.

Two caches, deliberately separate (R2 / D1)
-------------------------------------------
``emb_T``  SBERT of ``T(Oi)``    -> feature f1, structural semantics
``emb_D``  SBERT of description  -> feature f6, documentation semantics

``T`` is built by ``src/parse_spec.py`` WITHOUT the description, so the two
texts are disjoint. This is the whole point of R2: a missing description must
move f6's mask term and nothing else. If the two were ever built from
overlapping text, a missing description would silently change f1 while the mask
still reported f1 as available, which defeats the mask - the core theoretical
claim (C1). ``src/test_similarity.py`` has the regression test.

Vectors are L2-normalised on the way out, so cosine similarity downstream is a
plain dot product and no consumer has to remember to normalise.

Deduplication
-------------
Identical texts are embedded once and shared. This is pure economy - the vector
for a given string is the same either way - and it is worth doing: large
generated specs repeat the same ``T`` across dozens of operations, and the same
boilerplate description ("OK", "Successful response") recurs corpus-wide.

Usage:
    python src/embed.py                          # the whole parsed corpus
    python src/embed.py --parsed-dir parsed_bench --out .cache/emb_bench
    python src/embed.py --limit 50               # smoke test
    python src/embed.py --verify                 # re-check an existing cache
"""

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

import config                                     # noqa: E402

DEFAULT_CACHE = os.path.join(config.ROOT, ".cache", "embeddings")

# Batch size only affects speed and peak memory, never the vectors themselves.
BATCH = 256


# ----------------------------------------------------------------------------
# Text collection
# ----------------------------------------------------------------------------

def collect_texts(parsed_dir, limit=None):
    """Walk parsed/ and return (services, t_texts, d_texts).

    ``services`` maps a parsed file name to two row-index lists, one entry per
    operation in the operation order stored by the parser. A description row of
    -1 means the operation has no description, i.e. f6 is unavailable for it.
    The parser already sorts operations by ``op_key``, so this order is stable
    across runs and every consumer can rely on it.
    """
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    if limit:
        files = files[:limit]

    t_texts, t_row = [], {}
    d_texts, d_row = [], {}
    services = {}

    for name in files:
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        t_rows, d_rows = [], []
        for op in doc["operations"]:
            t = op["T"]
            key = hashlib.sha1(t.encode("utf-8")).hexdigest()
            if key not in t_row:
                t_row[key] = len(t_texts)
                t_texts.append(t)
            t_rows.append(t_row[key])

            desc = op.get("description")
            if desc is None:
                d_rows.append(-1)
            else:
                key = hashlib.sha1(desc.encode("utf-8")).hexdigest()
                if key not in d_row:
                    d_row[key] = len(d_texts)
                    d_texts.append(desc)
                d_rows.append(d_row[key])
        services[name] = {"t": t_rows, "d": d_rows}

    return services, t_texts, d_texts


# ----------------------------------------------------------------------------
# Embedding
# ----------------------------------------------------------------------------

def embed_texts(texts, label):
    """Embed a list of strings, L2-normalised, float32."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    if not texts:
        return np.zeros((0, 384), dtype="float32")

    print("  loading %s" % config.EMBEDDING_MODEL, flush=True)
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    print("  embedding %s %s texts (batch %d)"
          % ("{:,}".format(len(texts)), label, BATCH), flush=True)
    vecs = model.encode(
        texts,
        batch_size=BATCH,
        convert_to_numpy=True,
        normalize_embeddings=True,       # cosine becomes a dot product
        show_progress_bar=True,
    )
    return vecs.astype("float32")


def build(parsed_dir, out_dir, limit=None):
    import numpy as np

    print("reading %s" % parsed_dir, flush=True)
    services, t_texts, d_texts = collect_texts(parsed_dir, limit)
    n_ops = sum(len(v["t"]) for v in services.values())
    n_desc = sum(1 for v in services.values() for r in v["d"] if r >= 0)
    print("  %d services, %s operations" % (len(services), "{:,}".format(n_ops)))
    print("  T           %s unique of %s"
          % ("{:,}".format(len(t_texts)), "{:,}".format(n_ops)))
    print("  description %s unique of %s (%s operations have none)"
          % ("{:,}".format(len(d_texts)), "{:,}".format(n_desc),
             "{:,}".format(n_ops - n_desc)))

    emb_t = embed_texts(t_texts, "T")
    emb_d = embed_texts(d_texts, "description")

    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "emb_T.npy"), emb_t)
    np.save(os.path.join(out_dir, "emb_D.npy"), emb_d)
    meta = {
        "model": config.EMBEDDING_MODEL,
        "dim": int(emb_t.shape[1]) if len(emb_t) else 0,
        "normalised": True,
        "parsed_dir": os.path.relpath(parsed_dir, config.ROOT).replace("\\", "/"),
        "n_services": len(services),
        "n_operations": n_ops,
        "n_unique_T": len(t_texts),
        "n_unique_description": len(d_texts),
        "n_operations_without_description": n_ops - n_desc,
        "services": services,
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)

    print("\nwrote %s" % out_dir)
    print("  emb_T.npy  %s" % (emb_t.shape,))
    print("  emb_D.npy  %s" % (emb_d.shape,))
    print("  index.json %d services" % len(services))


# ----------------------------------------------------------------------------
# Loading (the interface every downstream script uses)
# ----------------------------------------------------------------------------

class Embeddings:
    """Read-only view over a built cache.

    ``rows_T(name)`` / ``rows_D(name)`` give per-operation row indices in the
    parser's operation order; -1 in the description rows means "no description",
    which the mask reads as f6 unavailable.
    """

    def __init__(self, cache_dir=DEFAULT_CACHE):
        import numpy as np
        with open(os.path.join(cache_dir, "index.json"), encoding="utf-8") as fh:
            self.meta = json.load(fh)
        self.dir = cache_dir
        self.T = np.load(os.path.join(cache_dir, "emb_T.npy"))
        self.D = np.load(os.path.join(cache_dir, "emb_D.npy"))
        self.services = self.meta["services"]

    def __contains__(self, name):
        return name in self.services

    def rows_T(self, name):
        return self.services[name]["t"]

    def rows_D(self, name):
        return self.services[name]["d"]

    def matrix_T(self, name):
        """(n_ops, dim) normalised matrix for one service, in operation order."""
        return self.T[self.services[name]["t"]]

    def matrix_D(self, name):
        """(n_ops, dim) for one service; rows with no description are zero.

        A zero row can never be mistaken for a real vector downstream because
        the f6 mask is derived from the same -1 sentinel, not from the norm.
        """
        import numpy as np
        rows = self.services[name]["d"]
        out = np.zeros((len(rows), self.D.shape[1]), dtype="float32")
        have = [i for i, r in enumerate(rows) if r >= 0]
        if have:
            out[have] = self.D[[rows[i] for i in have]]
        return out


# ----------------------------------------------------------------------------
# Verification
# ----------------------------------------------------------------------------

def verify(parsed_dir, cache_dir):
    """Re-check a built cache against parsed/ without re-embedding.

    Catches the failure that would be hardest to notice later: a cache built
    from an older parse, whose row lists no longer line up with the operations
    they are supposed to describe.
    """
    import numpy as np
    emb = Embeddings(cache_dir)
    files = sorted(n for n in os.listdir(parsed_dir) if n.endswith(".json"))
    problems, checked = [], 0

    if emb.meta["model"] != config.EMBEDDING_MODEL:
        problems.append("cache model %s != config %s"
                        % (emb.meta["model"], config.EMBEDDING_MODEL))

    for name in files:
        if name not in emb:
            problems.append("%s missing from cache" % name)
            continue
        with open(os.path.join(parsed_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        rows_t, rows_d = emb.rows_T(name), emb.rows_D(name)
        if len(rows_t) != len(doc["operations"]):
            problems.append("%s: %d rows vs %d operations"
                            % (name, len(rows_t), len(doc["operations"])))
            continue
        for i, op in enumerate(doc["operations"]):
            if (op.get("description") is None) != (rows_d[i] < 0):
                problems.append("%s: f6 sentinel disagrees at %s" % (name, op["op_key"]))
                break
        checked += 1

    norms = np.linalg.norm(emb.T, axis=1) if len(emb.T) else np.array([1.0])
    if len(emb.T) and (abs(norms - 1.0).max() > 1e-3):
        problems.append("emb_T not unit-normalised (max deviation %.4g)"
                        % abs(norms - 1.0).max())

    print("verified %d/%d services against %s" % (checked, len(files), parsed_dir))
    print("  model      %s" % emb.meta["model"])
    print("  emb_T      %s   emb_D %s" % (emb.T.shape, emb.D.shape))
    if problems:
        print("\n%d PROBLEM(S):" % len(problems))
        for p in problems[:20]:
            print("   " + p)
        sys.exit("cache verification failed")
    print("  OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description="ILSC embedding cache.")
    ap.add_argument("--parsed-dir", default=config.PARSED_DIR)
    ap.add_argument("--out", default=DEFAULT_CACHE)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verify", action="store_true",
                    help="check an existing cache instead of building one")
    args = ap.parse_args(argv)

    if args.verify:
        verify(args.parsed_dir, args.out)
    else:
        build(args.parsed_dir, args.out, args.limit)


if __name__ == "__main__":
    main()

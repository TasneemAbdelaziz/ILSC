"""Shared configuration. Every script imports from here.

Nothing in this file may be re-declared locally in a script: if a constant is
needed in two places it lives here, so that the corpus, the availability study
and the metric can never drift apart.
"""

import os
import re

SEED = 42

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Sources (Sec. 7). Both pinned; never run against HEAD.
# ---------------------------------------------------------------------------

# S1 - RAMA threshold benchmark (Bogner et al. 2020), the citable anchor.
#   github.com/restful-ma/thresholds :: benchmark-repository/openapi
#   2,619 OpenAPI files. NOTE: RAMA converted every Swagger 2.0 input to
#   OpenAPI 3 upstream (src/convert-openapi-v2.js), so S1 is 100% 3.x and its
#   spec_version is a post-conversion property. See DECISIONS.md D-10.
RAMA_COMMIT = "5b0b2a3322d3b2b7c0e0f2c0c0ad0e524e67bf82"
RAMA_DIR = os.path.join(ROOT, "rama-thresholds", "benchmark-repository", "openapi")

# S2 - APIs.guru current snapshot. 4,138 spec files at this commit.
APIS_GURU_COMMIT = "f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49"
APIS_GURU_DIR = os.path.join(ROOT, "openapi-directory", "APIs")

# Processing order matters: S1 is processed first so that a service present in
# both corpora is credited to S1 (Sec. 7, cross-source dedup). See D-09.
SOURCES = (
    ("S1", RAMA_DIR, "flat"),      # provider parsed from the file name
    ("S2", APIS_GURU_DIR, "tree"),  # provider is the top-level directory
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SPECS_CLEAN = os.path.join(ROOT, "specs", "clean")    # as published (2.0 + 3.x)
SPECS_CLEAN3 = os.path.join(ROOT, "specs", "clean3")  # all 3.x, for the parser
PARSED_DIR = os.path.join(ROOT, "parsed")             # src/parse_spec.py output
RESULTS_DIR = os.path.join(ROOT, "results")
FIGURES_DIR = os.path.join(ROOT, "figures")

# ---------------------------------------------------------------------------
# Sec. 6 preprocessing
# ---------------------------------------------------------------------------

MIN_OPERATIONS = 3

HTTP_METHODS = ("get", "post", "put", "delete", "patch")

# Administrative endpoints (D-07). The regex is the authoritative definition
# and ADMIN_PATHS below is its plain-language expansion for the paper - the two
# are kept in sync deliberately, because an earlier version of this project had
# a 6-entry tuple here and a 12-entry regex in filter.py, and the corpus was
# built with the regex.
#
# The match is anchored on the WHOLE path, so a domain endpoint that merely
# contains one of these words is untouched: /orders/{id}/status is kept,
# a bare /status is dropped.
ADMIN_PATHS = (
    "/health", "/healthz", "/healthcheck",
    "/ready", "/readyz",
    "/live", "/liveness",
    "/metrics", "/ping", "/status", "/version",
    "/actuator/*",
)

ADMIN_PATHS_RE = re.compile(
    r"^/(health|healthz|healthcheck|ready|readyz|live|liveness|metrics|ping"
    r"|status|version|actuator(/.*)?)/?$",
    re.IGNORECASE,
)

# Tokenisation (Sec. 8, Parameters). getOrderById -> {order, by, id}: "get" is
# dropped as a stopword, "by" is kept -- the list is exactly the one the
# proposal pins, and widening it is a sensitivity knob, not a free choice.
TOKEN_STOPWORDS = {"get", "post", "api", "v1", "v2"}

# The pinned list names only v1 and v2, but real specs run to v3+ and the same
# reasoning applies to each: a version marker is not a domain term. This
# generalises the pinned list to any ^v<digits>$ token. It is a knob, and the
# f2/f3 sensitivity analysis should report it.
DROP_VERSION_TOKENS = True

# f5: a schema on more than this share of a service's operations is
# infrastructural rather than domain-bearing (Sec. 6). Applied per service, on
# top of the fixed GENERIC_SCHEMAS list below.
FREQUENT_SCHEMA_RATIO = 0.80

# f5: schemas shared by nearly every operation carry no domain signal
GENERIC_SCHEMAS = {
    "error", "errorresponse", "problem", "pagination", "pageinfo",
    "apiresponse", "status", "meta", "link", "empty",
}

# ---------------------------------------------------------------------------
# Strict validation sample (D-02)
# ---------------------------------------------------------------------------
# The whole corpus is gated on a cheap structural check; openapi-spec-validator
# is run on this many randomly drawn survivors and both numbers are reported.
STRICT_VALIDATION_SAMPLE = 200

# ---------------------------------------------------------------------------
# Exp. 2 - provider-proximity perturbation (see docs/DECISIONS.md, D-05)
# ---------------------------------------------------------------------------
PERTURBATION_LEVELS = (0, 1, 2, 3, 5)
PERTURBATION_DRAWS = 10
PERTURBATION_CONDITIONS = ("same_service", "same_provider", "cross_provider")
MAX_SERVICES_PER_PROVIDER_IN_EXPERIMENT = 3

# ---------------------------------------------------------------------------
# Model, pinned
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TAU_DEFAULT = 0.50
TAU_GRID = [round(0.30 + 0.05 * i, 2) for i in range(9)]

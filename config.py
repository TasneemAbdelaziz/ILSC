"""Shared configuration. Every script imports from here."""

SEED = 42

# APIs.guru corpus, pinned. Never run against HEAD.
APIS_GURU_COMMIT = "f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49"

# Sec. 6 preprocessing
MIN_OPERATIONS = 3
ADMIN_PATHS = ("/health", "/ready", "/live", "/metrics", "/actuator", "/ping")

# f5: schemas shared by nearly every operation carry no domain signal
GENERIC_SCHEMAS = {
    "error", "errorresponse", "problem", "pagination", "pageinfo",
    "apiresponse", "status", "meta", "link", "empty",
}

# Exp. 2 — provider-proximity perturbation (see docs/DECISIONS.md, D-05)
PERTURBATION_LEVELS = (0, 1, 2, 3, 5)
PERTURBATION_DRAWS = 10
PERTURBATION_CONDITIONS = ("same_service", "same_provider", "cross_provider")
MAX_SERVICES_PER_PROVIDER_IN_EXPERIMENT = 3

# Model, pinned
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TAU_DEFAULT = 0.50
TAU_GRID = [round(0.30 + 0.05 * i, 2) for i in range(9)]

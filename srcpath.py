"""Puts every src/<group>/ folder on sys.path.

The scripts live in role folders - pipeline, metric, experiments, analyses,
common - but import one another by plain module name (``import similarity``),
as they did when src/ was flat. Each script inserts the repository root into
sys.path and imports this module before anything else from the project.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GROUPS = ("pipeline", "metric", "experiments", "analyses", "common")
SRC_DIRS = [os.path.join(ROOT, "src", g) for g in GROUPS]

for _d in reversed(SRC_DIRS):
    if _d not in sys.path:
        sys.path.insert(0, _d)

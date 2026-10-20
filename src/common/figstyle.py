"""
ILSC - one figure style for every chart in the paper.

Journals want a consistent visual language and vector output. Before this
module each script picked its own colours, so Fig 3, Fig 4 and Fig 7 used three
different reds for three different things.

The palette
-----------
Categorical slots are assigned **in fixed order and never cycled**, so a colour
means the same thing across figures. The three slots used here are validated as
a set for all-pairs separation:

    worst pair CVD Delta E 9.2 (deutan), normal-vision Delta E 27.6

One caveat carried deliberately: ``AQUA`` sits at 2.74:1 against the light
surface, below the 3:1 contrast target. The rule for that case is *relief* - the
chart must not rely on the colour alone. Every figure here satisfies it three
times over: a legend is always present for two or more series, each series
carries a **distinct marker shape**, and the underlying CSV in ``results/`` is
the table view.

Two rules worth stating because they are easy to break
------------------------------------------------------
**No dual-axis charts.** Plotting two measures against two y-scales lets the
author choose where the lines cross, which is the single most misleading thing a
chart can do. ``fig6`` originally did exactly this - edge density and component
count on a twin axis - and is now two stacked panels sharing one x-axis.

**Text wears ink, never the series colour.** Axis labels, tick labels and titles
stay in the ink tokens; identity is carried by the mark beside them. Colouring a
y-axis label to match its line is the same dual-axis mistake wearing a hat.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402

# Categorical slots, fixed order, never cycled.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
SERIES = (BLUE, ORANGE, AQUA)

# Secondary encoding, paired with the slots above.
MARKERS = ("o", "s", "^")
LINESTYLES = ("-", "--", ":")

# Ink and surface.
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8880"
SURFACE = "#fcfcfb"
GRID = "#d8d7d2"

# Sequential / diverging, for the correlation heat map.
DIVERGING = "RdBu_r"
SEQUENTIAL = "Blues"


def use():
    """Apply the shared rcParams. Call once, before creating any figure."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "axes.labelsize": 8.5,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "axes.edgecolor": INK_MUTED,
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.alpha": 0.9,
        "legend.frameon": False,
        "legend.fontsize": 7.5,
        "lines.linewidth": 1.6,
        "lines.markersize": 4.5,
        "pdf.fonttype": 42,              # embed TrueType, not Type 3 - journals ask
        "ps.fonttype": 42,
        "figure.dpi": 150,
    })


def series(i):
    """(colour, marker, linestyle) for categorical slot i, assigned not cycled."""
    if i >= len(SERIES):
        raise ValueError(
            "slot %d requested but only %d validated slots exist. Fold the extra "
            "series into 'Other' or facet - do not generate a new hue."
            % (i, len(SERIES)))
    return SERIES[i], MARKERS[i], LINESTYLES[i]


def finish(fig, path):
    """Uniform save: tight bounds, vector PDF."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return path

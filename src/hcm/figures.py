"""Figure style and templates for the paper. Engineers build figures to Hanut's spec.

    from hcm import figures
    figures.use_style()
    fig = figures.watchers_chart(df)  # df: unit_id, state, nfhs_rate, recorded_per_100k
    figures.save(fig, "fig1_watchers")
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import paths  # noqa: E402

INK, MUTED, GRID = "#1d1c1a", "#6b6862", "#e3e0d8"
HIGHLIGHT, BASE = "#c2562b", "#8fa3b8"


def use_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.titleweight": "bold",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "xtick.color": MUTED, "ytick.color": MUTED, "legend.frameon": False,
        "figure.figsize": (6.5, 4.0),
    })


def save(fig, name: str) -> list[str]:
    out = paths.ROOT / "paper" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("pdf", "png"):
        p = out / f"{name}.{ext}"
        fig.savefig(p)
        files.append(str(p))
    plt.close(fig)
    return files


def watchers_chart(df: pd.DataFrame, highlight_state: str = "Odisha",
                   x: str = "nfhs_rate", y: str = "recorded_per_100k"):
    """Day-3 'watchers' chart: recorded cases against survey prevalence.

    If records tracked harm, points would rise left to right. A flat or
    falling cloud is the reporting gap the paper is about.
    """
    use_style()
    fig, ax = plt.subplots()
    d = df.dropna(subset=[x, y])
    hi = d["state"].str.lower() == highlight_state.lower()
    ax.scatter(d.loc[~hi, x] * 100, d.loc[~hi, y], s=10, c=BASE, alpha=0.6, lw=0, label="Other districts")
    ax.scatter(d.loc[hi, x] * 100, d.loc[hi, y], s=18, c=HIGHLIGHT, lw=0, label=highlight_state)
    if len(d) > 2:
        b = np.polyfit(d[x] * 100, d[y], 1)
        xs = np.linspace(d[x].min() * 100, d[x].max() * 100, 50)
        ax.plot(xs, np.polyval(b, xs), color=INK, lw=1, ls="--", label="Linear fit")
    ax.set_xlabel("Women 20–24 married before 18, NFHS (%)")
    ax.set_ylabel("Recorded child-marriage cases per 100,000")
    ax.set_title("Recorded cases do not rise with prevalence")
    ax.legend(loc="upper right")
    return fig


def calibration_chart(pred: pd.Series, truth: pd.Series, label: str = "Model"):
    """Predicted vs NFHS-6 district rates, for the out-of-time test (Thu 8 Oct)."""
    use_style()
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.scatter(truth * 100, pred * 100, s=12, c=HIGHLIGHT, lw=0)
    lim = [0, max(truth.max(), pred.max()) * 105]
    ax.plot(lim, lim, color=MUTED, lw=1, ls=":")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("NFHS-6 district rate (%)")
    ax.set_ylabel(f"{label} prediction (%)")
    return fig

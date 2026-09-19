# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib", "numpy", "pandas"]
# ///
"""Figure 2: combined and standalone repository/review-budget artwork."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import BASE


OUT_DIR = BASE / "output"
volume = json.loads((OUT_DIR / "rq1_continuous_models.json").read_text(encoding="utf-8"))
static = json.loads((OUT_DIR / "static_diff_loro_baseline.json").read_text(encoding="utf-8"))

volume_folds = {
    row["repo"]: row
    for row in volume["predictive_validation"]["scenarios"]["volume_components"]["folds"]
}
static_folds = {
    row["held_out_repository"]: row for row in static["folds"]
}
two_class_repositories = [
    repo for repo, row in volume_folds.items() if row["auc"] is not None
]
one_class_repositories = [
    repo for repo, row in volume_folds.items() if row["auc"] is None
]

labels = {
    "astropy/astropy": "Astropy",
    "django/django": "Django",
    "matplotlib/matplotlib": "Matplotlib",
    "psf/requests": "Requests",
    "pydata/xarray": "Xarray",
    "scikit-learn/scikit-learn": "Scikit-learn",
    "sphinx-doc/sphinx": "Sphinx",
    "sympy/sympy": "SymPy",
}

mpl.rcParams.update({
    "font.family": "serif",
    "font.size": 8.2,
    "axes.titlesize": 9,
    "axes.labelsize": 8.5,
    "legend.fontsize": 7.2,
    "xtick.labelsize": 7.2,
    "ytick.labelsize": 7.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

budgets = ["top_10_percent", "top_20_percent"]
budget_labels = []
files_hunks = []
files_hunks_ci = []
static_recall = []
static_ci = []
random_recall = []
for key in budgets:
    simple = volume["predictive_validation"]["scenarios"]["files_and_hunks"]["review_budgets"][key]
    rich = static["metrics"]["review_budgets"][key]
    budget_labels.append(f"{100 * simple['workload_fraction']:.1f}%")
    files_hunks.append(simple["recall"])
    files_hunks_ci.append(simple["recall_repository_bootstrap_ci_95"])
    static_recall.append(rich["recall"])
    static_ci.append(rich["recall_repository_bootstrap_ci_95"])
    random_recall.append(simple["random_expected_recall"])

simple_errors = np.array([
    [value - ci[0] for value, ci in zip(files_hunks, files_hunks_ci)],
    [ci[1] - value for value, ci in zip(files_hunks, files_hunks_ci)],
])
static_errors = np.array([
    [value - ci[0] for value, ci in zip(static_recall, static_ci)],
    [ci[1] - value for value, ci in zip(static_recall, static_ci)],
])


def plot_discrimination(ax):
    x_positions = np.arange(len(two_class_repositories))
    gold_aware_auc = [
        volume_folds[repo]["auc"] for repo in two_class_repositories
    ]
    gold_free_auc = [
        static_folds[repo]["roc_auc"] for repo in two_class_repositories
    ]
    positive_n = np.array([
        volume_folds[repo]["positive_n"] for repo in two_class_repositories
    ])
    sizes = 24 + 8 * np.sqrt(positive_n)

    ax.axhline(0.5, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
    ax.scatter(
        x_positions - 0.15,
        gold_aware_auc,
        s=sizes,
        color="#3F69AA",
        marker="o",
        edgecolor="white",
        linewidth=0.5,
        label="Gold-aware volume components",
        zorder=3,
    )
    ax.scatter(
        x_positions + 0.15,
        gold_free_auc,
        s=sizes,
        color="#B02A37",
        marker="s",
        edgecolor="white",
        linewidth=0.5,
        label="Gold-free 25-feature model",
        zorder=3,
    )
    for index, count in enumerate(positive_n):
        ax.text(
            index,
            1.015,
            f"F={count}",
            ha="center",
            va="bottom",
            fontsize=6.3,
            color="#444444",
        )
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Held-out ROC-AUC")
    ax.set_xticks(
        x_positions,
        [labels[repo] for repo in two_class_repositories],
        rotation=35,
        ha="right",
    )
    ax.set_title("(a) Repository-held-out discrimination")
    ax.legend(loc="lower right", frameon=True, framealpha=0.95)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.7)


def plot_review_budgets(ax):
    x_positions = np.arange(len(budgets))
    width = 0.25
    ax.bar(
        x_positions - width,
        files_hunks,
        width,
        color="#3F69AA",
        label="Gold-free files+hunks",
        yerr=simple_errors,
        capsize=2.5,
        error_kw={"linewidth": 0.8},
    )
    ax.bar(
        x_positions,
        static_recall,
        width,
        color="#B02A37",
        label="Gold-free 25-feature model",
        yerr=static_errors,
        capsize=2.5,
        error_kw={"linewidth": 0.8},
    )
    ax.bar(
        x_positions + width,
        random_recall,
        width,
        color="#B8B8B8",
        label="Random review",
    )
    for positions, values in [
        (x_positions - width, files_hunks),
        (x_positions, static_recall),
        (x_positions + width, random_recall),
    ]:
        for position, value in zip(positions, values):
            ax.text(
                position,
                value + 0.015,
                f"{100 * value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=6.3,
            )
    ax.set_xticks(x_positions, budget_labels)
    # Ranking/selection remains repository-stratified; the denominator is the
    # complete primary cohort. The manuscript caption explains both facts.
    ax.set_xlabel("Review workload (% of all patches)")
    ax.set_ylabel("Failure recall")
    ax.set_ylim(0, 0.60)
    ax.set_title("(b) Practical review budgets")
    ax.legend(loc="upper left", frameon=True, framealpha=0.95)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.7)


OUT_DIR.mkdir(parents=True, exist_ok=True)
pdf_path = OUT_DIR / "fig2_repository_transport.pdf"
png_path = OUT_DIR / "fig2_repository_transport.png"
panel_a_path = OUT_DIR / "fig2_repository_transport_panel_a.pdf"
panel_b_path = OUT_DIR / "fig2_repository_transport_panel_b.pdf"
metadata = {
    "Title": "Repository-held-out discrimination and review-budget utility",
    "Author": "Replication workflow",
    "CreationDate": datetime(2026, 8, 4, tzinfo=timezone.utc),
    "ModDate": datetime(2026, 8, 4, tzinfo=timezone.utc),
}

# Keep the combined artifact for backward compatibility and review convenience.
fig, axes = plt.subplots(
    1,
    2,
    figsize=(7.15, 2.75),
    gridspec_kw={"width_ratios": [1.55, 1]},
)
plot_discrimination(axes[0])
plot_review_budgets(axes[1])
fig.tight_layout(pad=0.8, w_pad=1.2)
fig.savefig(pdf_path, bbox_inches="tight", metadata=metadata)
fig.savefig(png_path, dpi=240, bbox_inches="tight")
plt.close(fig)

# Produce independent vector artwork files for journal submission accessibility.
panel_a_fig, panel_a_ax = plt.subplots(figsize=(4.8, 2.75))
plot_discrimination(panel_a_ax)
panel_a_fig.tight_layout(pad=0.8)
panel_a_fig.savefig(
    panel_a_path,
    bbox_inches="tight",
    metadata={**metadata, "Title": "Repository-held-out discrimination"},
)
plt.close(panel_a_fig)

panel_b_fig, panel_b_ax = plt.subplots(figsize=(3.65, 2.75))
plot_review_budgets(panel_b_ax)
panel_b_fig.tight_layout(pad=0.8)
panel_b_fig.savefig(
    panel_b_path,
    bbox_inches="tight",
    metadata={**metadata, "Title": "Practical review budgets"},
)
plt.close(panel_b_fig)

source_rows = []
for repo in sorted(volume_folds):
    source_rows.append({
        "repo": repo,
        "n": volume_folds[repo]["n"],
        "failure_n": volume_folds[repo]["positive_n"],
        "gold_aware_volume_auc": volume_folds[repo]["auc"],
        "gold_free_static_auc": static_folds[repo]["roc_auc"],
    })
pd.DataFrame(source_rows).to_csv(OUT_DIR / "fig2_repository_transport_data.csv", index=False)

print(f"Two-class repositories: {len(two_class_repositories)}")
print(f"One-class repositories: {len(one_class_repositories)}")
print(f"Saved -> {pdf_path}")
print(f"Saved -> {png_path}")
print(f"Saved -> {panel_a_path}")
print(f"Saved -> {panel_b_path}")

# /// script
# requires-python = ">=3.11"
# dependencies = ["scipy", "numpy", "matplotlib", "pandas"]
# ///
"""Figure 3: combined and standalone patch-volume distribution artwork.

Reads from analysis_dataset.csv (canonical single source of truth).
Computes Fisher exact test with 95% CI and Wilson CIs for proportions.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import fisher_exact, norm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from common import BASE, load_primary_dataset

OUT_DIR = BASE / "output"

# ---------------------------------------------------------------------------
# Load data from canonical CSV
# ---------------------------------------------------------------------------
df = load_primary_dataset()
print(f"Loaded {len(df)} trajectories from the primary binary cohort")

failure_df = df[df["is_full_suite_failure"] == 1]
comparison_df = df[df["is_full_suite_failure"] == 0]
failure_ratios = failure_df["rho"].values
comparison_ratios = comparison_df["rho"].values
display_upper = 300.0
n_failure_above_display = int(np.sum(failure_ratios > display_upper))
n_comparison_above_display = int(np.sum(comparison_ratios > display_upper))
n_above_display = n_failure_above_display + n_comparison_above_display

print(f"Developer-test functional failures: {len(failure_ratios)}")
print(f"No observed developer-test failure: {len(comparison_ratios)}")

# ---------------------------------------------------------------------------
# Fisher's exact test
# ---------------------------------------------------------------------------
n_failure_tail = sum(1 for r in failure_ratios if r < 0.5)
n_failure_rest = len(failure_ratios) - n_failure_tail
n_comparison_tail = sum(1 for r in comparison_ratios if r < 0.5)
n_comparison_rest = len(comparison_ratios) - n_comparison_tail

table = [
    [n_failure_tail, n_failure_rest],
    [n_comparison_tail, n_comparison_rest],
]
odds, p = fisher_exact(table)

# Woolf's method for 95% CI of the odds ratio
log_or = np.log(odds)
se_log_or = np.sqrt(sum(1.0 / x for row in table for x in row))
ci_lo = np.exp(log_or - 1.96 * se_log_or)
ci_hi = np.exp(log_or + 1.96 * se_log_or)

pct_failure_tail = 100 * n_failure_tail / len(failure_ratios)
pct_comparison_tail = 100 * n_comparison_tail / len(comparison_ratios)

# Wilson score CIs for proportions
def wilson_ci(count, n, alpha=0.05):
    """Wilson score interval for a binomial proportion."""
    z = norm.ppf(1 - alpha / 2)
    p_hat = count / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return 100 * max(0, center - margin), 100 * min(1, center + margin)

failure_ci_lo, failure_ci_hi = wilson_ci(n_failure_tail, len(failure_ratios))
comparison_ci_lo, comparison_ci_hi = wilson_ci(
    n_comparison_tail, len(comparison_ratios)
)

print(f"\n{'='*60}")
print(f"RQ1 RESULTS")
print(f"{'='*60}")
print(
    "Developer-test-failure tail (<0.5): "
    f"{n_failure_tail}/{len(failure_ratios)} = {pct_failure_tail:.1f}%"
)
print(f"  Wilson 95% CI: [{failure_ci_lo:.1f}%, {failure_ci_hi:.1f}%]")
print(
    f"No-observed-developer-test-failure tail (<0.5): {n_comparison_tail}/"
    f"{len(comparison_ratios)} = {pct_comparison_tail:.1f}%"
)
print(f"  Wilson 95% CI: [{comparison_ci_lo:.1f}%, {comparison_ci_hi:.1f}%]")
print(f"Fisher exact: OR={odds:.2f}, 95% CI=[{ci_lo:.2f}, {ci_hi:.2f}], p={p:.6f}")

# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"THRESHOLD SENSITIVITY ANALYSIS")
print(f"{'='*60}")
threshold_rows = []
for thresh in [0.3, 0.4, 0.5, 0.6, 0.7]:
    n_pt = sum(1 for r in failure_ratios if r < thresh)
    n_pr = len(failure_ratios) - n_pt
    n_ct = sum(1 for r in comparison_ratios if r < thresh)
    n_cr = len(comparison_ratios) - n_ct
    t_or, t_p = fisher_exact([[n_pt, n_pr], [n_ct, n_cr]])
    threshold_rows.append({
        "threshold": thresh,
        "full_suite_failure_tail": n_pt,
        "full_suite_failure_total": n_pt + n_pr,
        "comparison_tail": n_ct,
        "comparison_total": n_ct + n_cr,
        "odds_ratio": float(t_or),
        "p_value": float(t_p),
    })
    print(f"  thresh={thresh:.1f}  developer-test failure={n_pt}/{n_pt+n_pr} ({100*n_pt/(n_pt+n_pr):.1f}%)  "
          f"comparison={n_ct}/{n_ct+n_cr} ({100*n_ct/(n_ct+n_cr):.1f}%)  "
          f"OR={t_or:.2f}  p={t_p:.4f}")

# Holm adjustment over the five explicitly declared sensitivity thresholds.
order = np.argsort([row["p_value"] for row in threshold_rows])
running_max = 0.0
for rank, index in enumerate(order):
    adjusted = min((len(threshold_rows) - rank) * threshold_rows[index]["p_value"], 1.0)
    running_max = max(running_max, adjusted)
    threshold_rows[index]["holm_p"] = running_max
print("\nHolm-adjusted sensitivity p-values:")
for row in threshold_rows:
    print(f"  threshold={row['threshold']:.1f}: adjusted p={row['holm_p']:.6f}")
tail_holm_p = next(
    row["holm_p"] for row in threshold_rows if row["threshold"] == 0.5
)

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "serif", "font.size": 8,
    "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 7,
    "figure.dpi": 300,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

def ecdf(data):
    sorted_data = np.sort(data)
    y = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
    return sorted_data, y


x_p, y_p = ecdf(failure_ratios)
x_c, y_c = ecdf(comparison_ratios)
labels = [
    f"No observed\ndeveloper-test failure\n($N$={len(comparison_ratios)})",
    f"Developer-test\nfunctional failure\n($N$={len(failure_ratios)})",
]
tail_pcts = [pct_comparison_tail, pct_failure_tail]
bar_colors = ["#2166ac", "#b2182b"]
adjusted_p_label = (
    r"Fisher $p_{\mathrm{Holm}} < 0.001$"
    if tail_holm_p < 0.001
    else rf"Fisher $p_{{\mathrm{{Holm}}}} = {tail_holm_p:.3f}$"
)


def plot_ecdf(ax):
    ax.step(
        x_c,
        y_c,
        where="post",
        color="#2166ac",
        linewidth=1.2,
        label=f"No observed failure ($N$={len(comparison_ratios)})",
    )
    ax.step(
        x_p,
        y_p,
        where="post",
        color="#b2182b",
        linewidth=1.2,
        linestyle="--",
        label=f"Developer-test failure ($N$={len(failure_ratios)})",
    )
    ax.axvline(x=0.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.7)
    ax.annotate(
        r"$\rho = 0.5$",
        xy=(0.5, 0.05),
        xytext=(0.8, 0.12),
        fontsize=6,
        color="gray",
        arrowprops=dict(arrowstyle="->", color="gray", lw=0.5),
    )
    ax.fill_between([0.02, 0.5], 0, 1, color="#b2182b", alpha=0.06)
    ax.annotate(
        "Exploratory\ntail",
        xy=(0.15, 0.25),
        fontsize=6.5,
        color="#b2182b",
        ha="center",
        fontstyle="italic",
    )
    ax.set_xscale("log")
    ax.set_xlim(0.03, display_upper)
    ax.set_xticks([0.1, 0.5, 1, 5, 10, 50, 200])
    ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.tick_params(axis="x", rotation=30)
    ax.set_xlabel(r"Patch volume ratio $\rho$ (agent / developer; log scale)")
    ax.set_ylabel("Cumulative probability")
    ax.legend(
        loc="lower right",
        bbox_to_anchor=(0.995, 0.015),
        fontsize=6.5,
        framealpha=0.72,
        handlelength=1.35,
        handletextpad=0.45,
        borderpad=0.22,
        labelspacing=0.18,
        borderaxespad=0.15,
    )
    ax.annotate(
        f"{n_above_display} observations beyond axis\n"
        f"({n_comparison_above_display} comparison; "
        f"{n_failure_above_display} failure)",
        xy=(0.03, 0.96),
        xycoords="axes fraction",
        fontsize=5.8,
        ha="left",
        va="top",
        color="#444444",
        bbox=dict(
            boxstyle="round,pad=0.25",
            facecolor="white",
            edgecolor="#AAAAAA",
            alpha=0.90,
        ),
    )
    ax.set_title(r"(a) eCDF through $\rho=300$", loc="left")


def plot_tail_proportion(ax):
    bars = ax.bar(
        [0, 1],
        tail_pcts,
        color=bar_colors,
        width=0.55,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(labels)
    ax.set_ylabel(r"Proportion at $\rho < 0.5$ (%)")
    ax.set_ylim(0, max(tail_pcts) * 1.38)
    ax.set_title("(b) Exploratory tail proportion ($\\rho < 0.5$)", loc="left")
    for bar, pct in zip(bars, tail_pcts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            pct + 0.28,
            f"{pct:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color=bar.get_facecolor(),
        )
    ax.annotate(
        f"OR = {odds:.2f} [95% CI: {ci_lo:.2f}, {ci_hi:.2f}]\n"
        f"{adjusted_p_label}",
        xy=(0.03, 0.95),
        xycoords="axes fraction",
        fontsize=6.4,
        ha="left",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="white",
            edgecolor="#999999",
            alpha=0.95,
        ),
    )


OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / "fig2_volume_distribution.pdf"
panel_a_path = OUT_DIR / "fig2_volume_distribution_panel_a.pdf"
panel_b_path = OUT_DIR / "fig2_volume_distribution_panel_b.pdf"
pdf_timestamp = datetime(2026, 7, 23, tzinfo=timezone.utc)

# Keep the combined artifact for backward compatibility and review convenience.
fig, (ax1, ax2) = plt.subplots(
    1,
    2,
    figsize=(7.0, 2.6),
    gridspec_kw={"width_ratios": [1, 1]},
)
plot_ecdf(ax1)
plot_tail_proportion(ax2)
fig.tight_layout(pad=0.8)
fig.savefig(
    out_path,
    bbox_inches="tight",
    pad_inches=0.05,
    metadata={"CreationDate": pdf_timestamp, "ModDate": pdf_timestamp},
)
plt.close(fig)

# Produce independent vector artwork files for journal submission accessibility.
panel_a_fig, panel_a_ax = plt.subplots(figsize=(3.7, 2.6))
plot_ecdf(panel_a_ax)
panel_a_fig.tight_layout(pad=0.8)
panel_a_fig.savefig(
    panel_a_path,
    bbox_inches="tight",
    pad_inches=0.05,
    metadata={
        "Title": "Patch-volume empirical CDF through rho=300",
        "CreationDate": pdf_timestamp,
        "ModDate": pdf_timestamp,
    },
)
plt.close(panel_a_fig)

panel_b_fig, panel_b_ax = plt.subplots(figsize=(3.35, 2.6))
plot_tail_proportion(panel_b_ax)
panel_b_fig.tight_layout(pad=0.8)
panel_b_fig.savefig(
    panel_b_path,
    bbox_inches="tight",
    pad_inches=0.05,
    metadata={
        "Title": "Exploratory patch-volume tail proportion",
        "CreationDate": pdf_timestamp,
        "ModDate": pdf_timestamp,
    },
)
plt.close(panel_b_fig)
print(f"\nSaved -> {out_path}")
print(f"Saved -> {panel_a_path}")
print(f"Saved -> {panel_b_path}")

result = {
    "cohort_n": int(len(df)),
    "full_suite_failure_n": int(len(failure_df)),
    "no_observed_full_suite_failure_n": int(len(comparison_df)),
    "rho_median": float(df["rho"].median()),
    "rho_iqr": [float(df["rho"].quantile(0.25)), float(df["rho"].quantile(0.75))],
    "tail_threshold": 0.5,
    "contingency_table": table,
    "full_suite_failure_tail_pct": pct_failure_tail,
    "full_suite_failure_tail_wilson_ci": [failure_ci_lo, failure_ci_hi],
    "comparison_tail_pct": pct_comparison_tail,
    "comparison_tail_wilson_ci": [comparison_ci_lo, comparison_ci_hi],
    "odds_ratio": float(odds),
    "odds_ratio_ci": [float(ci_lo), float(ci_hi)],
    "fisher_p": float(p),
    "threshold_sensitivity": threshold_rows,
}
(OUT_DIR / "rq1_results.json").write_text(
    json.dumps(result, indent=2), encoding="utf-8"
)
print(f"Saved -> {OUT_DIR / 'rq1_results.json'}")

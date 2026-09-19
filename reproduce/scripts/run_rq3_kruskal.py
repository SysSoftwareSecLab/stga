# /// script
# requires-python = ">=3.11"
# dependencies = ["scipy", "numpy", "pandas", "statsmodels"]
# ///
"""RQ4: issue-matched cross-configuration patch-volume comparison.

The filename is retained for backward compatibility with archived releases.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from common import BASE, TOOL_SPECS, load_resolved_packaged_dataset


TOOLS = ["OpenHands", "CodeStory", "LearnByInteract"]
SEED = 42
N_BOOT = 2000
OUT_DIR = BASE / "output"


def holm_adjust(p_values):
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running_max = 0.0
    for rank, index in enumerate(order):
        value = min((len(p_values) - rank) * p_values[index], 1.0)
        running_max = max(running_max, value)
        adjusted[index] = running_max
    return adjusted


def rank_biserial(differences):
    """Matched-pairs rank-biserial correlation; positive means first > second."""
    nonzero = np.asarray(differences)[np.asarray(differences) != 0]
    ranks = stats.rankdata(np.abs(nonzero))
    signs = np.sign(nonzero)
    denominator = ranks.sum()
    if denominator == 0:
        return 0.0
    return float(
        (ranks[signs > 0].sum() - ranks[signs < 0].sum()) / denominator
    )


def bootstrap_rank_biserial(differences):
    rng = np.random.default_rng(SEED)
    differences = np.asarray(differences)
    values = np.empty(N_BOOT)
    for index in range(N_BOOT):
        sampled = rng.choice(differences, size=len(differences), replace=True)
        values[index] = rank_biserial(sampled)
    return [float(value) for value in np.percentile(values, [2.5, 97.5])]


def effect_interpretation(value):
    absolute = abs(value)
    if absolute < 0.1:
        return "negligible"
    if absolute < 0.3:
        return "small"
    if absolute < 0.5:
        return "moderate"
    return "large"


df = load_resolved_packaged_dataset()
tool_data = {
    tool: df.loc[df["tool"].eq(tool), "rho"].to_numpy()
    for tool in TOOLS
}

print(f"Loaded all resolved packaged patches: N={len(df)}")
descriptive = {}
for tool, values in tool_data.items():
    descriptive[tool] = {
        "n": int(len(values)),
        "median": float(np.median(values)),
        "iqr": [
            float(np.quantile(values, 0.25)),
            float(np.quantile(values, 0.75)),
        ],
    }
    print(
        f"  {tool:<16} N={len(values):>3}, median={np.median(values):.3f}, "
        f"IQR=[{np.quantile(values, 0.25):.3f}, "
        f"{np.quantile(values, 0.75):.3f}]"
    )

# Primary analysis: only issues represented by all three scaffolds. This
# controls issue identity directly and avoids treating repeated issues as
# independent samples.
matched = df.pivot(
    index="instance_id",
    columns="tool",
    values="rho",
).dropna(subset=TOOLS)
complete_issue_ids = set(matched.index)

issue_profiles = (
    df.groupby("instance_id", sort=True)
    .agg(
        repo=("repo", "first"),
        gold_vol=("gold_vol", "first"),
        n_files_gold=("n_files_gold", "first"),
        represented_tools=("tool", "nunique"),
        any_functional_failure=("is_full_suite_failure", "max"),
    )
    .reset_index()
)
issue_profiles["complete_triple"] = issue_profiles["instance_id"].isin(
    complete_issue_ids
)
complete_profiles = issue_profiles[issue_profiles["complete_triple"]]
incomplete_profiles = issue_profiles[~issue_profiles["complete_triple"]]

u_test = stats.mannwhitneyu(
    complete_profiles["gold_vol"], incomplete_profiles["gold_vol"],
    alternative="two-sided",
)
rank_biserial_selection = float(
    2 * u_test.statistic / (len(complete_profiles) * len(incomplete_profiles)) - 1
)
repo_table = pd.crosstab(issue_profiles["repo"], issue_profiles["complete_triple"])
repo_table = repo_table.rename(columns={False: "incomplete", True: "complete"})
for column in ["incomplete", "complete"]:
    if column not in repo_table:
        repo_table[column] = 0
repo_table = repo_table[["complete", "incomplete"]]
complete_distribution = repo_table["complete"] / repo_table["complete"].sum()
incomplete_distribution = repo_table["incomplete"] / repo_table["incomplete"].sum()
repository_total_variation = float(
    0.5 * np.abs(complete_distribution - incomplete_distribution).sum()
)
selection_rows = repo_table.reset_index().to_dict(orient="records")
OUT_DIR.mkdir(exist_ok=True)
repo_table.reset_index().to_csv(
    OUT_DIR / "rq3_complete_case_selection.csv", index=False
)
friedman = stats.friedmanchisquare(*(matched[tool] for tool in TOOLS))
print(
    f"\nPrimary matched analysis: {len(matched)} complete issue triples"
)
print(
    f"Friedman: Q={friedman.statistic:.4f}, p={friedman.pvalue:.8g}"
)

pairwise = []
for first_index in range(len(TOOLS)):
    for second_index in range(first_index + 1, len(TOOLS)):
        first = TOOLS[first_index]
        second = TOOLS[second_index]
        log_difference = (
            np.log(matched[first].to_numpy())
            - np.log(matched[second].to_numpy())
        )
        wilcoxon = stats.wilcoxon(
            log_difference,
            zero_method="wilcox",
            alternative="two-sided",
        )
        effect = rank_biserial(log_difference)
        pairwise.append({
            "first": first,
            "second": second,
            "n_pairs": int(len(log_difference)),
            "median_ratio_first_over_second": float(
                np.median(np.exp(log_difference))
            ),
            "rank_biserial": effect,
            "rank_biserial_ci_95": bootstrap_rank_biserial(log_difference),
            "wilcoxon_p": float(wilcoxon.pvalue),
            "interpretation": effect_interpretation(effect),
        })

adjusted = holm_adjust([row["wilcoxon_p"] for row in pairwise])
print("\nMatched pairwise comparisons:")
for row, adjusted_p in zip(pairwise, adjusted):
    row["holm_p"] = float(adjusted_p)
    print(
        f"  {row['first']} vs {row['second']}: "
        f"rank-biserial={row['rank_biserial']:+.3f} "
        f"[{row['rank_biserial_ci_95'][0]:+.3f}, "
        f"{row['rank_biserial_ci_95'][1]:+.3f}], "
        f"median ratio={row['median_ratio_first_over_second']:.3f}, "
        f"Holm p={row['holm_p']:.6g}"
    )

# Sensitivity analysis: all resolved non-empty rows in a population-averaged
# Gaussian GEE on
# log volume ratio, with issue clustering and developer-patch volume control.
df = df.copy()
df["log_gold_vol"] = np.log1p(df["gold_vol"])
formula = (
    "log_rho ~ log_gold_vol + "
    "C(tool, Treatment(reference='OpenHands')) + C(repo)"
)
gee = smf.gee(
    formula,
    groups="instance_id",
    data=df,
    family=sm.families.Gaussian(),
    cov_struct=sm.cov_struct.Exchangeable(),
).fit()
parameter_names = list(gee.params.index)
parameters = gee.params.to_numpy()
covariance = gee.cov_params().to_numpy()
cs_name = "C(tool, Treatment(reference='OpenHands'))[T.CodeStory]"
li_name = "C(tool, Treatment(reference='OpenHands'))[T.LearnByInteract]"


def gee_contrast(name, weights):
    vector = np.array(
        [weights.get(parameter, 0.0) for parameter in parameter_names]
    )
    estimate = float(vector @ parameters)
    standard_error = float(np.sqrt(vector @ covariance @ vector))
    z_value = estimate / standard_error
    p_value = float(2 * stats.norm.sf(abs(z_value)))
    return {
        "contrast": name,
        "log_ratio": estimate,
        "standard_error": standard_error,
        "ratio": float(np.exp(estimate)),
        "ratio_ci_95": [
            float(np.exp(estimate - 1.96 * standard_error)),
            float(np.exp(estimate + 1.96 * standard_error)),
        ],
        "p_value": p_value,
    }


gee_pairwise = [
    gee_contrast("CodeStory/OpenHands", {cs_name: 1.0}),
    gee_contrast("LearnByInteract/OpenHands", {li_name: 1.0}),
    gee_contrast(
        "CodeStory/LearnByInteract",
        {cs_name: 1.0, li_name: -1.0},
    ),
]
tool_indices = [parameter_names.index(cs_name), parameter_names.index(li_name)]
tool_parameters = parameters[tool_indices]
tool_covariance = covariance[np.ix_(tool_indices, tool_indices)]
tool_wald = float(
    tool_parameters @ np.linalg.inv(tool_covariance) @ tool_parameters
)
tool_p = float(stats.chi2.sf(tool_wald, df=2))

print(
    f"\nAll-cohort GEE sensitivity: tool Wald chi2={tool_wald:.4f}, "
    f"p={tool_p:.8g}"
)
for row in gee_pairwise:
    print(
        f"  {row['contrast']}: ratio={row['ratio']:.3f} "
        f"[{row['ratio_ci_95'][0]:.3f}, {row['ratio_ci_95'][1]:.3f}], "
        f"p={row['p_value']:.6g}"
    )

result = {
    "cohort_definition": (
        "all officially resolved trajectories with packaged patch fields; the "
        "explicit empty patch is retained as zero volume"
    ),
    "cohort_n": int(len(df)),
    "descriptive": descriptive,
    "primary_matched": {
        "complete_issues": int(len(matched)),
        "rows": int(len(matched) * len(TOOLS)),
        "friedman_q": float(friedman.statistic),
        "p_value": float(friedman.pvalue),
        "pairwise": pairwise,
    },
    "complete_case_selection": {
        "all_unique_issues": int(len(issue_profiles)),
        "complete_issue_n": int(len(complete_profiles)),
        "incomplete_issue_n": int(len(incomplete_profiles)),
        "complete_gold_volume_median": float(complete_profiles["gold_vol"].median()),
        "incomplete_gold_volume_median": float(incomplete_profiles["gold_vol"].median()),
        "gold_volume_mann_whitney_u": float(u_test.statistic),
        "gold_volume_mann_whitney_p": float(u_test.pvalue),
        "gold_volume_rank_biserial": rank_biserial_selection,
        "repository_total_variation_distance": repository_total_variation,
        "repository_counts": selection_rows,
    },
    "system_metadata_boundary": {
        "artifact_folders": {
            tool: specification["folder"] for tool, specification in TOOL_SPECS.items()
        },
        "shared_model_claim": (
            "The upstream artifact names all three configurations as Claude 3.5 "
            "Sonnet variants, but it does not establish identical snapshot, sampling "
            "temperature, token budget, or candidate-selection policy."
        ),
    },
    "all_cohort_gee_sensitivity": {
        "formula": formula,
        "clusters": int(df["instance_id"].nunique()),
        "tool_wald_chi2": tool_wald,
        "tool_wald_df": 2,
        "tool_wald_p": tool_p,
        "pairwise": gee_pairwise,
    },
}
OUT_DIR.mkdir(exist_ok=True)
path = OUT_DIR / "rq3_results.json"
path.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"\nSaved -> {path}")

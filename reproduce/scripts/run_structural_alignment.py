# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "scipy", "statsmodels"]
# ///
"""Objective file-level alignment analyses for developer-test failures."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from scipy.optimize import linear_sum_assignment

from common import BASE, load_primary_dataset


OUT_DIR = BASE / "output"
SEED = 42
N_BOOT = 2000
FEATURES = [
    {
        "name": "file_mismatch_10pct",
        "source": "file_jaccard",
        "paired_source": "file_jaccard",
        "paired_direction": -1,
        "label": "file-set mismatch (per 10 percentage points)",
    },
    {
        "name": "log_agent_only_files",
        "source": "n_agent_only_files",
        "paired_source": "n_agent_only_files",
        "paired_direction": 1,
        "label": "log(1 + agent-only files)",
    },
    {
        "name": "log_gold_only_files",
        "source": "n_gold_only_files",
        "paired_source": "n_gold_only_files",
        "paired_direction": 1,
        "label": "log(1 + developer-only files)",
    },
    {
        "name": "artifact_like_agent_only",
        "source": "artifact_like_agent_only",
        "paired_source": "artifact_like_agent_only",
        "paired_direction": 1,
        "label": "artifact-like agent-only path",
    },
]


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
    nonzero = np.asarray(differences)[np.asarray(differences) != 0]
    if len(nonzero) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero))
    signs = np.sign(nonzero)
    return float(
        (ranks[signs > 0].sum() - ranks[signs < 0].sum()) / ranks.sum()
    )


def bootstrap_median_difference(differences):
    rng = np.random.default_rng(SEED)
    differences = np.asarray(differences)
    values = [
        np.median(rng.choice(differences, size=len(differences), replace=True))
        for _ in range(N_BOOT)
    ]
    return [float(v) for v in np.percentile(values, [2.5, 97.5])]


def standardized_mean_difference(first, second):
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    pooled = np.sqrt((np.var(first, ddof=1) + np.var(second, ddof=1)) / 2)
    return 0.0 if pooled == 0 else float((np.mean(first) - np.mean(second)) / pooled)


def optimal_matches(failure_rows, control_rows, file_penalty=0.05, caliper=None):
    """Return order-invariant matches within exact tool/repository strata."""
    matches = []
    for (tool, repo), stratum_failures in failure_rows.groupby(
        ["tool", "repo"], sort=True
    ):
        stratum_failures = stratum_failures.sort_values("instance_id")
        stratum_controls = control_rows[
            control_rows["tool"].eq(tool) & control_rows["repo"].eq(repo)
        ].sort_values("instance_id")
        if not len(stratum_controls):
            continue
        distance = (
            np.abs(
                stratum_failures["log_gold_vol"].to_numpy()[:, None]
                - stratum_controls["log_gold_vol"].to_numpy()[None, :]
            )
            + file_penalty
            * np.abs(
                stratum_failures["n_files_gold"].to_numpy()[:, None]
                - stratum_controls["n_files_gold"].to_numpy()[None, :]
            )
        )
        if caliper is None:
            if len(stratum_controls) < len(stratum_failures):
                raise ValueError(
                    f"Insufficient controls for {tool}/{repo}: "
                    f"{len(stratum_failures)} failures, "
                    f"{len(stratum_controls)} controls"
                )
            failure_indices, control_indices = linear_sum_assignment(distance)
        else:
            # Dummy columns permit unmatched failures. Their large cost makes
            # the assignment maximize feasible matches before minimizing cost.
            n_failures, n_controls = distance.shape
            dummy_cost = (n_failures + 1) * (caliper + 1.0)
            invalid_cost = 2.0 * dummy_cost
            feasible = np.where(distance <= caliper, distance, invalid_cost)
            augmented = np.concatenate(
                [
                    feasible,
                    np.full((n_failures, n_failures), dummy_cost),
                ],
                axis=1,
            )
            failure_indices, assigned_columns = linear_sum_assignment(augmented)
            accepted = assigned_columns < n_controls
            failure_indices = failure_indices[accepted]
            control_indices = assigned_columns[accepted]
        for failure_index, control_index in zip(
            failure_indices, control_indices
        ):
            if caliper is not None and distance[failure_index, control_index] > caliper:
                continue
            matches.append(
                (
                    stratum_failures.index[failure_index],
                    stratum_controls.index[control_index],
                    float(distance[failure_index, control_index]),
                )
            )
    return matches


def materialize_matches(data, matches):
    rows = []
    for pair_id, (failure_index, control_index, matching_distance) in enumerate(
        matches, start=1
    ):
        failure = data.loc[failure_index]
        control = data.loc[control_index]
        row = {
            "pair_id": pair_id,
            "failure_instance_id": failure["instance_id"],
            "control_instance_id": control["instance_id"],
            "tool": failure["tool"],
            "repo": failure["repo"],
            "failure_gold_vol": failure["gold_vol"],
            "control_gold_vol": control["gold_vol"],
            "failure_n_files_gold": failure["n_files_gold"],
            "control_n_files_gold": control["n_files_gold"],
            "matching_distance": matching_distance,
        }
        for feature in FEATURES:
            source = feature["paired_source"]
            row[f"failure_{source}"] = failure[source]
            row[f"control_{source}"] = control[source]
        rows.append(row)
    return pd.DataFrame(rows)


def developer_only_sensitivity(data, matches):
    paired = materialize_matches(data, matches)
    if paired.empty:
        return {
            "pairs": 0,
            "log_gold_volume_smd": None,
            "rank_biserial": None,
            "p_value": None,
            "failure_nonzero_n": 0,
            "control_nonzero_n": 0,
        }
    failure_values = paired["failure_n_gold_only_files"].to_numpy(dtype=float)
    control_values = paired["control_n_gold_only_files"].to_numpy(dtype=float)
    differences = failure_values - control_values
    if np.all(differences == 0):
        p_value = 1.0
    else:
        p_value = float(
            stats.wilcoxon(differences, zero_method="wilcox").pvalue
        )
    failure_log_gold = np.log1p(paired["failure_gold_vol"])
    control_log_gold = np.log1p(paired["control_gold_vol"])
    return {
        "pairs": int(len(paired)),
        "log_gold_volume_smd": standardized_mean_difference(
            failure_log_gold, control_log_gold
        ),
        "rank_biserial": rank_biserial(differences),
        "p_value": p_value,
        "failure_nonzero_n": int(np.sum(failure_values > 0)),
        "control_nonzero_n": int(np.sum(control_values > 0)),
    }


df = load_primary_dataset().reset_index(drop=True)
df["log_gold_vol"] = np.log1p(df["gold_vol"])
df["file_mismatch_10pct"] = 10 * (1 - df["file_jaccard"])
df["log_agent_only_files"] = np.log1p(df["n_agent_only_files"])
df["log_gold_only_files"] = np.log1p(df["n_gold_only_files"])

failures = df[df["is_full_suite_failure"].eq(1)].copy()
controls = df[df["is_full_suite_failure"].eq(0)].copy()

matches = optimal_matches(failures, controls)

if len(matches) != len(failures):
    raise AssertionError("Every functional failure must receive one control")

matched = materialize_matches(df, matches)
matched_failure_rows = df.loc[[failure_index for failure_index, _, _ in matches]]
matched_control_rows = df.loc[[control_index for _, control_index, _ in matches]]
OUT_DIR.mkdir(exist_ok=True)
matched.to_csv(OUT_DIR / "structural_alignment_matched_pairs.csv", index=False)

paired_results = []
for feature in FEATURES:
    source = feature["paired_source"]
    failure_values = matched[f"failure_{source}"].to_numpy(dtype=float)
    control_values = matched[f"control_{source}"].to_numpy(dtype=float)
    differences = feature["paired_direction"] * (failure_values - control_values)
    if source == "artifact_like_agent_only":
        discordant_failure = int(np.sum((failure_values == 1) & (control_values == 0)))
        discordant_control = int(np.sum((failure_values == 0) & (control_values == 1)))
        discordant_n = discordant_failure + discordant_control
        p_value = (
            float(stats.binomtest(
                min(discordant_failure, discordant_control),
                discordant_n,
                0.5,
                alternative="two-sided",
            ).pvalue)
            if discordant_n else 1.0
        )
        paired_results.append({
            "feature": feature["name"],
            "label": feature["label"],
            "test": "exact McNemar",
            "failure_positive_n": int(failure_values.sum()),
            "control_positive_n": int(control_values.sum()),
            "discordant_failure_only": discordant_failure,
            "discordant_control_only": discordant_control,
            "matched_odds_ratio": (
                float(discordant_failure / discordant_control)
                if discordant_control else None
            ),
            "p_value": p_value,
        })
    else:
        if np.all(differences == 0):
            statistic, p_value = 0.0, 1.0
        else:
            test = stats.wilcoxon(differences, zero_method="wilcox")
            statistic, p_value = float(test.statistic), float(test.pvalue)
        paired_results.append({
            "feature": feature["name"],
            "label": feature["label"],
            "test": "paired Wilcoxon",
            "failure_median": float(np.median(failure_values)),
            "control_median": float(np.median(control_values)),
            "failure_nonzero_n": int(np.sum(failure_values > 0)),
            "control_nonzero_n": int(np.sum(control_values > 0)),
            "oriented_median_difference": float(np.median(differences)),
            "oriented_median_difference_ci_95": bootstrap_median_difference(
                differences
            ),
            "rank_biserial": rank_biserial(differences),
            "statistic": statistic,
            "p_value": p_value,
        })

paired_adjusted = holm_adjust([row["p_value"] for row in paired_results])
for row, adjusted in zip(paired_results, paired_adjusted):
    row["holm_p"] = float(adjusted)

# Population-averaged sensitivity using all primary-cohort rows.
gee_results = []
for feature in FEATURES:
    name = feature["name"]
    formula = (
        f"is_full_suite_failure ~ {name} + log_gold_vol + "
        "C(tool, Treatment(reference='OpenHands')) + C(repo)"
    )
    model = smf.gee(
        formula=formula,
        groups="instance_id",
        data=df,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    estimate = float(model.params[name])
    ci = [float(v) for v in model.conf_int().loc[name]]
    gee_results.append({
        "feature": name,
        "label": feature["label"],
        "formula": formula,
        "coefficient": estimate,
        "odds_ratio": float(np.exp(estimate)),
        "odds_ratio_ci_95": [float(np.exp(v)) for v in ci],
        "p_value": float(model.pvalues[name]),
    })

gee_adjusted = holm_adjust([row["p_value"] for row in gee_results])
for row, adjusted in zip(gee_results, gee_adjusted):
    row["holm_p"] = float(adjusted)

failure_log_gold = np.log1p(matched["failure_gold_vol"])
control_log_gold = np.log1p(matched["control_gold_vol"])

balance_rows = []
for name, failure_before, control_before, failure_after, control_after in [
    (
        "log1p developer patch volume",
        failures["log_gold_vol"], controls["log_gold_vol"],
        failure_log_gold, control_log_gold,
    ),
    (
        "developer changed-file count",
        failures["n_files_gold"], controls["n_files_gold"],
        matched["failure_n_files_gold"], matched["control_n_files_gold"],
    ),
]:
    balance_rows.append({
        "covariate": name,
        "smd_before_matching": standardized_mean_difference(
            failure_before, control_before
        ),
        "smd_after_matching": standardized_mean_difference(
            failure_after, control_after
        ),
    })

for categorical in ["tool", "repo"]:
    levels = sorted(df[categorical].unique())
    before_differences = []
    after_differences = []
    for level in levels:
        before_differences.append(
            failures[categorical].eq(level).mean()
            - controls[categorical].eq(level).mean()
        )
        after_differences.append(
            matched_failure_rows[categorical].eq(level).mean()
            - matched_control_rows[categorical].eq(level).mean()
        )
    balance_rows.append({
        "covariate": f"exact {categorical} strata (maximum proportion difference)",
        "smd_before_matching": float(max(abs(v) for v in before_differences)),
        "smd_after_matching": float(max(abs(v) for v in after_differences)),
    })

pd.DataFrame(balance_rows).to_csv(
    OUT_DIR / "structural_alignment_balance.csv", index=False
)

# Design sensitivity for the developer-only-file result. These analyses vary
# only matching choices; the outcome and feature definitions remain fixed.
robustness_specs = []
for file_penalty in [0.0, 0.05, 0.10, 0.20]:
    spec_matches = optimal_matches(
        failures, controls, file_penalty=file_penalty
    )
    payload = developer_only_sensitivity(df, spec_matches)
    payload.update({
        "specification": f"penalty={file_penalty:.2f}, no caliper",
        "file_penalty": file_penalty,
        "caliper": None,
    })
    robustness_specs.append(payload)
for caliper in [0.25, 0.50, 1.00]:
    spec_matches = optimal_matches(
        failures, controls, file_penalty=0.05, caliper=caliper
    )
    payload = developer_only_sensitivity(df, spec_matches)
    payload.update({
        "specification": f"penalty=0.05, caliper={caliper:.2f}",
        "file_penalty": 0.05,
        "caliper": caliper,
    })
    robustness_specs.append(payload)

loro_robustness = []
for excluded_repo in sorted(df["repo"].unique()):
    kept_failures = failures[~failures["repo"].eq(excluded_repo)]
    kept_controls = controls[~controls["repo"].eq(excluded_repo)]
    spec_matches = optimal_matches(kept_failures, kept_controls)
    payload = developer_only_sensitivity(df, spec_matches)
    payload["excluded_repository"] = excluded_repo
    loro_robustness.append(payload)

pd.DataFrame(robustness_specs).to_csv(
    OUT_DIR / "structural_alignment_matching_sensitivity.csv", index=False
)
pd.DataFrame(loro_robustness).to_csv(
    OUT_DIR / "structural_alignment_loro_sensitivity.csv", index=False
)

robustness_summary = {
    "specification_count": len(robustness_specs),
    "positive_direction_count": int(
        sum(row["rank_biserial"] > 0 for row in robustness_specs)
    ),
    "pair_count_range": [
        int(min(row["pairs"] for row in robustness_specs)),
        int(max(row["pairs"] for row in robustness_specs)),
    ],
    "rank_biserial_range": [
        float(min(row["rank_biserial"] for row in robustness_specs)),
        float(max(row["rank_biserial"] for row in robustness_specs)),
    ],
    "loro_repository_count": len(loro_robustness),
    "loro_positive_direction_count": int(
        sum(row["rank_biserial"] > 0 for row in loro_robustness)
    ),
    "loro_rank_biserial_range": [
        float(min(row["rank_biserial"] for row in loro_robustness)),
        float(max(row["rank_biserial"] for row in loro_robustness)),
    ],
}

result = {
    "cohort_n": int(len(df)),
    "failure_n": int(len(failures)),
    "comparison_n": int(len(controls)),
    "matching": {
        "method": (
            "1:1 without-replacement minimum-total-distance assignment within "
            "exact tool and repository strata; distance on log developer volume "
            "plus a small developer-file-count penalty"
        ),
        "pairs": int(len(matched)),
        "unique_control_agent_instances": int(len(matched)),
        "unique_control_issues": int(matched["control_instance_id"].nunique()),
        "log_gold_volume_smd": standardized_mean_difference(
            failure_log_gold, control_log_gold
        ),
        "total_matching_distance": float(matched["matching_distance"].sum()),
        "mean_matching_distance": float(matched["matching_distance"].mean()),
        "max_matching_distance": float(matched["matching_distance"].max()),
        "distance_quantiles": {
            "p25": float(matched["matching_distance"].quantile(0.25)),
            "median": float(matched["matching_distance"].median()),
            "p75": float(matched["matching_distance"].quantile(0.75)),
            "p95": float(matched["matching_distance"].quantile(0.95)),
        },
        "unmatched_failure_n": int(len(failures) - len(matched)),
        "balance": balance_rows,
    },
    "descriptive": {
        "failure_file_jaccard_median": float(failures["file_jaccard"].median()),
        "comparison_file_jaccard_median": float(controls["file_jaccard"].median()),
        "failure_artifact_like_n": int(
            failures["artifact_like_agent_only"].sum()
        ),
        "comparison_artifact_like_n": int(
            controls["artifact_like_agent_only"].sum()
        ),
    },
    "matched_pairwise": paired_results,
    "all_cohort_gee": gee_results,
    "matching_robustness": {
        "interpretation": (
            "Exploratory design sensitivity; raw p-values are reported without "
            "treating alternative matching specifications as new hypotheses."
        ),
        "specifications": robustness_specs,
        "leave_one_repository_out": loro_robustness,
        "summary": robustness_summary,
    },
}

path = OUT_DIR / "structural_alignment_results.json"
path.write_text(json.dumps(result, indent=2), encoding="utf-8")

print(
    f"Structural alignment: N={len(df)}, matched pairs={len(matched)}, "
    f"log-gold SMD={result['matching']['log_gold_volume_smd']:+.3f}"
)
print("Matched comparisons (positive direction means more mismatch in failures):")
for row in paired_results:
    print(
        f"  {row['feature']:<28} raw p={row['p_value']:.6g}, "
        f"Holm p={row['holm_p']:.6g}"
    )
print("All-cohort issue-clustered GEE:")
for row in gee_results:
    print(
        f"  {row['feature']:<28} OR={row['odds_ratio']:.3f}, "
        f"Holm p={row['holm_p']:.6g}"
    )
print(
    "Matching robustness: "
    f"{robustness_summary['positive_direction_count']}/"
    f"{robustness_summary['specification_count']} specifications and "
    f"{robustness_summary['loro_positive_direction_count']}/"
    f"{robustness_summary['loro_repository_count']} leave-one-repository-out "
    "analyses retain a positive developer-only-file effect"
)
print(f"Saved -> {path}")

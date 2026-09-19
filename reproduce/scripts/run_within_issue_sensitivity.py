# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "scipy"]
# ///
"""Within-issue sensitivity analysis for objective structural contrasts."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from common import BASE, load_primary_dataset


OUT_DIR = BASE / "output"
SEED = 42
N_BOOT = 5000
TOLERANCE = 1e-12
FEATURES = {
    "file_mismatch": {
        "label": "File-set mismatch",
        "scale": 100.0,
        "unit": "percentage points",
    },
    "log_agent_only_files": {
        "label": "Agent-only files",
        "scale": 1.0,
        "unit": "log(1 + count)",
    },
    "log_gold_only_files": {
        "label": "Developer-only files",
        "scale": 1.0,
        "unit": "log(1 + count)",
    },
    "artifact_like_agent_only": {
        "label": "Artifact-like path",
        "scale": 100.0,
        "unit": "percentage points",
    },
}


def holm_adjust(p_values):
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running_max = 0.0
    for rank, index in enumerate(order):
        value = min((len(p_values) - rank) * p_values[index], 1.0)
        running_max = max(running_max, value)
        adjusted[index] = running_max
    return adjusted


def bootstrap_intervals(values):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(SEED)
    mean_samples = np.empty(N_BOOT)
    median_samples = np.empty(N_BOOT)
    for index in range(N_BOOT):
        sample = rng.choice(values, size=len(values), replace=True)
        mean_samples[index] = np.mean(sample)
        median_samples[index] = np.median(sample)
    return {
        "mean_ci_95": [
            float(value) for value in np.percentile(mean_samples, [2.5, 97.5])
        ],
        "median_ci_95": [
            float(value) for value in np.percentile(median_samples, [2.5, 97.5])
        ],
    }


data = load_primary_dataset()
data = data.assign(
    file_mismatch=1.0 - data["file_jaccard"].astype(float),
    log_agent_only_files=np.log1p(data["n_agent_only_files"].astype(float)),
    log_gold_only_files=np.log1p(data["n_gold_only_files"].astype(float)),
    artifact_like_agent_only=data["artifact_like_agent_only"].astype(float),
)

rows = []
for instance_id, issue_rows in data.groupby("instance_id", sort=True):
    failures = issue_rows[issue_rows["is_full_suite_failure"].eq(1)]
    controls = issue_rows[issue_rows["is_full_suite_failure"].eq(0)]
    if failures.empty or controls.empty:
        continue
    row = {
        "instance_id": instance_id,
        "repo": issue_rows["repo"].iloc[0],
        "failure_agent_n": int(len(failures)),
        "control_agent_n": int(len(controls)),
    }
    for feature in FEATURES:
        failure_mean = float(failures[feature].mean())
        control_mean = float(controls[feature].mean())
        row[f"failure_{feature}"] = failure_mean
        row[f"control_{feature}"] = control_mean
        row[f"difference_{feature}"] = failure_mean - control_mean
    rows.append(row)

issue_contrasts = pd.DataFrame(rows)
if len(issue_contrasts) != 25:
    raise ValueError(
        f"Expected 25 issues with both outcomes, found {len(issue_contrasts)}"
    )

results = []
for feature, metadata in FEATURES.items():
    raw_differences = issue_contrasts[f"difference_{feature}"].to_numpy(float)
    differences = raw_differences * metadata["scale"]
    positive_n = int(np.sum(differences > TOLERANCE))
    negative_n = int(np.sum(differences < -TOLERANCE))
    tie_n = int(len(differences) - positive_n - negative_n)
    non_tie_n = positive_n + negative_n
    sign_p = (
        float(stats.binomtest(positive_n, non_tie_n, 0.5).pvalue)
        if non_tie_n else 1.0
    )
    intervals = bootstrap_intervals(differences)
    results.append({
        "feature": feature,
        "label": metadata["label"],
        "unit": metadata["unit"],
        "issue_n": int(len(differences)),
        "positive_n": positive_n,
        "negative_n": negative_n,
        "tie_n": tie_n,
        "mean_difference": float(np.mean(differences)),
        "mean_difference_bootstrap_ci_95": intervals["mean_ci_95"],
        "median_difference": float(np.median(differences)),
        "median_difference_bootstrap_ci_95": intervals["median_ci_95"],
        "exact_sign_p": sign_p,
    })

for row, adjusted in zip(results, holm_adjust([row["exact_sign_p"] for row in results])):
    row["holm_p"] = float(adjusted)

payload = {
    "status": "complete_within_issue_sensitivity",
    "design": (
        "Issue-level failure-minus-control contrasts among issues containing "
        "both outcome states. Agent rows are averaged within outcome and issue "
        "before inference, so each issue receives equal weight."
    ),
    "issue_n": int(len(issue_contrasts)),
    "repository_n": int(issue_contrasts["repo"].nunique()),
    "bootstrap_samples": N_BOOT,
    "multiple_testing": "Holm adjustment across four structural features",
    "results": results,
}

OUT_DIR.mkdir(exist_ok=True)
csv_path = OUT_DIR / "structural_alignment_within_issue_contrasts.csv"
json_path = OUT_DIR / "structural_alignment_within_issue_sensitivity.json"
issue_contrasts.to_csv(csv_path, index=False)
json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

print(
    f"Within-issue sensitivity: {len(issue_contrasts)} mixed-outcome issues "
    f"across {issue_contrasts['repo'].nunique()} repositories"
)
for row in results:
    print(
        f"  {row['feature']:<27} +/-/tie="
        f"{row['positive_n']}/{row['negative_n']}/{row['tie_n']}, "
        f"mean delta={row['mean_difference']:+.3f}, "
        f"sign p={row['exact_sign_p']:.6g}, Holm p={row['holm_p']:.6g}"
    )
print(f"Saved -> {json_path}")
print(f"Saved -> {csv_path}")

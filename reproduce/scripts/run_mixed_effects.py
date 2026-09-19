# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "statsmodels", "numpy", "scikit-learn"]
# ///
"""Volume models, repository diagnostics, and repository-held-out prediction.

The primary model uses the two directly observed smoothed volume components
rather than entering a ratio and its denominator together. Repository fixed
effects address observed between-repository outcome and task-mix differences;
issue-level GEE clusters repeated scaffold outputs for the same task.
"""

from __future__ import annotations

import json
import math
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import PerfectSeparationWarning

from common import BASE, load_primary_dataset, load_resolved_packaged_dataset


SEED = 42
OUT_DIR = BASE / "output"
TOOL_TERM = "C(tool, Treatment(reference='OpenHands'))"
REPO_TERM = "C(repo, Treatment(reference='django/django'))"
PRIMARY_FORMULA = (
    "is_full_suite_failure ~ log_ai_vol + log_gold_vol + "
    f"{TOOL_TERM} + {REPO_TERM}"
)
NO_REPO_FORMULA = (
    "is_full_suite_failure ~ log_ai_vol + log_gold_vol + " + TOOL_TERM
)
LORO_COEFFICIENT_FORMULA = (
    "is_full_suite_failure ~ log_ai_vol + log_gold_vol + "
    f"{TOOL_TERM} + C(repo)"
)
RATIO_FORMULA = (
    "is_full_suite_failure ~ log_rho + log_gold_vol + "
    f"{TOOL_TERM} + {REPO_TERM}"
)
ORTHOGONAL_FORMULA = (
    "is_full_suite_failure ~ log_volume_scale + log_volume_difference + "
    f"{TOOL_TERM} + {REPO_TERM}"
)
SPLINE_DF = 3
SPLINE_FORMULA = (
    "is_full_suite_failure ~ "
    f"cr(log_rho, df={SPLINE_DF}, constraints='center') + log_gold_vol + "
    f"{TOOL_TERM} + {REPO_TERM}"
)
ANY_DISCREPANCY_FORMULA = (
    "is_any_recorded_discrepancy ~ log_ai_vol + log_gold_vol + "
    f"{TOOL_TERM} + {REPO_TERM}"
)


def fit_gee(frame: pd.DataFrame, formula: str):
    return smf.gee(
        formula=formula,
        groups="instance_id",
        data=frame,
        family=sm.families.Binomial(),
        cov_struct=Exchangeable(),
    ).fit()


def fit_models(frame: pd.DataFrame, formula: str = PRIMARY_FORMULA):
    gee = fit_gee(frame, formula)
    glm = smf.glm(
        formula=formula,
        data=frame,
        family=sm.families.Binomial(),
    ).fit(cov_type="cluster", cov_kwds={"groups": frame["instance_id"]})
    return gee, glm


def fit_spline_model(frame: pd.DataFrame):
    model = smf.gee(
        formula=SPLINE_FORMULA,
        groups="instance_id",
        data=frame,
        family=sm.families.Binomial(),
        cov_struct=Exchangeable(),
    )
    design = np.asarray(model.exog)
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise ValueError(
            f"Spline design matrix is rank deficient: rank={rank}, "
            f"columns={design.shape[1]}"
        )
    return model.fit(), {
        "rows": int(design.shape[0]),
        "columns": int(design.shape[1]),
        "rank": rank,
        "condition_number": float(np.linalg.cond(design)),
    }


def joint_wald_payload(model, term_prefix: str):
    terms = [name for name in model.params.index if name.startswith(term_prefix)]
    restriction = np.zeros((len(terms), len(model.params)))
    for row, term in enumerate(terms):
        restriction[row, model.params.index.get_loc(term)] = 1.0
    test = model.wald_test(restriction, scalar=True)
    return {
        "terms": terms,
        "chi2": float(test.statistic),
        "df": len(terms),
        "p_value": float(test.pvalue),
    }


def finite_float_or_none(value):
    """Return a JSON-safe float, using null for non-estimable values."""
    number = float(value)
    return number if math.isfinite(number) else None


def model_payload(model):
    intervals = model.conf_int()
    return {
        name: {
            "coefficient": finite_float_or_none(model.params[name]),
            "standard_error": finite_float_or_none(model.bse[name]),
            "p_value": finite_float_or_none(model.pvalues[name]),
            "ci_95": [finite_float_or_none(v) for v in intervals.loc[name]],
            "odds_ratio": finite_float_or_none(np.exp(model.params[name])),
            "odds_ratio_ci_95": [
                finite_float_or_none(np.exp(v)) for v in intervals.loc[name]
            ],
        }
        for name in model.params.index
    }


def make_pipeline(feature_names: list[str]):
    categorical = [name for name in feature_names if name == "tool"]
    numeric = [name for name in feature_names if name != "tool"]
    transformers = []
    if numeric:
        transformers.append((
            "numeric",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            numeric,
        ))
    if categorical:
        transformers.append((
            "categorical",
            OneHotEncoder(handle_unknown="ignore", drop="first"),
            categorical,
        ))
    return Pipeline([
        ("features", ColumnTransformer(transformers)),
        ("model", LogisticRegression(max_iter=5000, random_state=SEED)),
    ])


def calibration_payload(y: np.ndarray, probabilities: np.ndarray):
    if np.unique(y).size != 2:
        return {"intercept": None, "slope": None, "status": "single-class endpoint"}
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=PerfectSeparationWarning)
            fitted = sm.GLM(
                y, sm.add_constant(logits), family=sm.families.Binomial()
            ).fit()
        return {
            "intercept": float(fitted.params[0]),
            "slope": float(fitted.params[1]),
            "status": "estimated",
        }
    except (PerfectSeparationWarning, Exception):
        return {
            "intercept": None,
            "slope": None,
            "status": "not estimable because of separation",
        }


def grouped_predictions(frame: pd.DataFrame, feature_names: list[str]):
    predictions = np.full(len(frame), np.nan)
    fold_rows = []
    for repo in sorted(frame["repo"].unique()):
        test_mask = frame["repo"].eq(repo).to_numpy()
        train_mask = ~test_mask
        model = make_pipeline(feature_names)
        model.fit(
            frame.loc[train_mask, feature_names],
            frame.loc[train_mask, "is_full_suite_failure"],
        )
        fold_predictions = model.predict_proba(frame.loc[test_mask, feature_names])[:, 1]
        predictions[test_mask] = fold_predictions
        y_test = frame.loc[test_mask, "is_full_suite_failure"].to_numpy()
        two_class = np.unique(y_test).size == 2
        fold_rows.append({
            "repo": repo,
            "n": int(test_mask.sum()),
            "positive_n": int(y_test.sum()),
            "positive_prevalence": float(y_test.mean()),
            "auc": float(roc_auc_score(y_test, fold_predictions)) if two_class else None,
            "average_precision": (
                float(average_precision_score(y_test, fold_predictions))
                if y_test.sum() > 0 else None
            ),
            "brier_score": float(brier_score_loss(y_test, fold_predictions)),
            "calibration": calibration_payload(y_test, fold_predictions),
            "mean_prediction": float(fold_predictions.mean()),
        })
    if np.isnan(predictions).any():
        raise AssertionError("Some leave-one-repository-out predictions were not generated")
    return predictions, fold_rows


def repository_bootstrap_metrics(frame: pd.DataFrame, predictions: np.ndarray, n_boot=2000):
    rng = np.random.default_rng(SEED)
    repos = np.array(sorted(frame["repo"].unique()))
    repo_indices = {
        repo: np.flatnonzero(frame["repo"].to_numpy() == repo)
        for repo in repos
    }
    y = frame["is_full_suite_failure"].to_numpy()
    auc_values = []
    ap_values = []
    for _ in range(n_boot):
        sampled = rng.choice(repos, size=len(repos), replace=True)
        indices = np.concatenate([repo_indices[repo] for repo in sampled])
        if np.unique(y[indices]).size == 2:
            auc_values.append(roc_auc_score(y[indices], predictions[indices]))
            ap_values.append(average_precision_score(y[indices], predictions[indices]))
    return {
        "roc_auc_ci_95": [float(v) for v in np.percentile(auc_values, [2.5, 97.5])],
        "average_precision_ci_95": [
            float(v) for v in np.percentile(ap_values, [2.5, 97.5])
        ],
    }


def review_budget_metrics(frame: pd.DataFrame, predictions: np.ndarray):
    y = frame["is_full_suite_failure"].to_numpy()
    selected_by_budget = {0.10: [], 0.20: []}
    repository_rows = {0.10: [], 0.20: []}
    for repo in sorted(frame["repo"].unique()):
        indices = np.flatnonzero(frame["repo"].to_numpy() == repo)
        ordered = indices[np.argsort(-predictions[indices], kind="mergesort")]
        for budget in selected_by_budget:
            k = max(1, math.ceil(budget * len(indices)))
            selected = ordered[:k]
            selected_by_budget[budget].extend(selected.tolist())
            repository_rows[budget].append({
                "repo": repo,
                "positive_n": int(y[indices].sum()),
                "reviewed_n": int(k),
                "captured_n": int(y[selected].sum()),
            })
    payload = {}
    rng = np.random.default_rng(SEED)
    for budget, selected in selected_by_budget.items():
        selected = np.asarray(selected, dtype=int)
        captured = int(y[selected].sum())
        strata = repository_rows[budget]
        recall_samples = []
        precision_samples = []
        for _ in range(2000):
            sampled = rng.choice(len(strata), size=len(strata), replace=True)
            sampled_positive = sum(strata[index]["positive_n"] for index in sampled)
            sampled_reviewed = sum(strata[index]["reviewed_n"] for index in sampled)
            sampled_captured = sum(strata[index]["captured_n"] for index in sampled)
            if sampled_positive:
                recall_samples.append(sampled_captured / sampled_positive)
            precision_samples.append(sampled_captured / sampled_reviewed)
        payload[f"top_{int(budget * 100)}_percent"] = {
            "reviewed_n": int(len(selected)),
            "workload_fraction": float(len(selected) / len(frame)),
            "captured_failures": captured,
            "precision": float(captured / len(selected)),
            "recall": float(captured / y.sum()),
            "precision_repository_bootstrap_ci_95": [
                float(v) for v in np.percentile(precision_samples, [2.5, 97.5])
            ],
            "recall_repository_bootstrap_ci_95": [
                float(v) for v in np.percentile(recall_samples, [2.5, 97.5])
            ],
            "random_expected_recall": float(len(selected) / len(frame)),
            "repository_components": strata,
        }
    return payload


def fold_summary(folds: list[dict]):
    aucs = [row["auc"] for row in folds if row["auc"] is not None]
    aps = [row["average_precision"] for row in folds if row["average_precision"] is not None]
    return {
        "folds_with_two_classes": len(aucs),
        "macro_auc": float(np.mean(aucs)) if aucs else None,
        "macro_average_precision": float(np.mean(aps)) if aps else None,
        "macro_brier_score": float(np.mean([row["brier_score"] for row in folds])),
    }


def repository_profiles(frame: pd.DataFrame):
    rows = []
    for (repo, tool), group in frame.groupby(["repo", "tool"], observed=True):
        rows.append({
            "repo": repo,
            "tool": tool,
            "n": int(len(group)),
            "failure_n": int(group["is_full_suite_failure"].sum()),
            "failure_rate": float(group["is_full_suite_failure"].mean()),
            "unique_issues": int(group["instance_id"].nunique()),
            "median_rho": float(group["rho"].median()),
            "median_ai_volume": float(group["ai_vol"].median()),
            "median_developer_volume": float(group["gold_vol"].median()),
            "empty_diff_n": int(group["is_empty_agent_diff"].sum()),
        })
    return rows


def repository_totals(frame: pd.DataFrame):
    rows = []
    for repo, group in frame.groupby("repo", observed=True):
        rows.append({
            "repo": repo,
            "n": int(len(group)),
            "failure_n": int(group["is_full_suite_failure"].sum()),
            "failure_rate": float(group["is_full_suite_failure"].mean()),
            "unique_issues": int(group["instance_id"].nunique()),
            "tool_n": int(group["tool"].nunique()),
            "median_rho": float(group["rho"].median()),
            "median_ai_volume": float(group["ai_vol"].median()),
            "median_developer_volume": float(group["gold_vol"].median()),
            "empty_diff_n": int(group["is_empty_agent_diff"].sum()),
        })
    return rows


def prepare_features(frame: pd.DataFrame):
    frame = frame.copy()
    frame["log_gold_vol"] = np.log1p(frame["gold_vol"])
    frame["log_ai_vol"] = np.log1p(frame["ai_vol"])
    frame["log_volume_scale"] = 0.5 * (frame["log_ai_vol"] + frame["log_gold_vol"])
    frame["log_volume_difference"] = frame["log_ai_vol"] - frame["log_gold_vol"]
    frame["log_files_ai"] = np.log1p(frame["n_files_ai"])
    frame["log_hunks_ai"] = np.log1p(frame["n_hunks_ai"])
    frame["log_hunks_gold"] = np.log1p(frame["n_hunks_gold"])
    frame["log_agent_only_files"] = np.log1p(frame["n_agent_only_files"])
    frame["log_gold_only_files"] = np.log1p(frame["n_gold_only_files"])
    for slice_name in [
        "source_vol", "test_vol", "artifact_excluded_vol", "comment_excluded_vol"
    ]:
        frame[f"log_ai_{slice_name}"] = np.log1p(frame[f"ai_{slice_name}"])
        frame[f"log_gold_{slice_name}"] = np.log1p(frame[f"gold_{slice_name}"])
    return frame


df = prepare_features(load_primary_dataset().reset_index(drop=True))
print(
    f"Loaded primary cohort: N={len(df)}, developer-test functional failures="
    f"{df['is_full_suite_failure'].sum()}, issues={df['instance_id'].nunique()}, "
    f"repositories={df['repo'].nunique()}"
)

repository_outcome_variation = df.groupby("repo")["is_full_suite_failure"].nunique()
two_class_repositories = sorted(
    repository_outcome_variation[repository_outcome_variation.eq(2)].index
)
single_outcome_repositories = sorted(
    repository_outcome_variation[repository_outcome_variation.lt(2)].index
)
fixed_effect_df = df[df["repo"].isin(two_class_repositories)].copy()
print(
    "Repository-fixed-effect inference cohort: "
    f"N={len(fixed_effect_df)}, failures="
    f"{fixed_effect_df['is_full_suite_failure'].sum()}, "
    f"repositories={len(two_class_repositories)}; "
    f"excluded single-outcome repositories={single_outcome_repositories}"
)

gee, glm = fit_models(fixed_effect_df)
no_repo_gee = fit_gee(df, NO_REPO_FORMULA)
ratio_gee = fit_gee(fixed_effect_df, RATIO_FORMULA)
orthogonal_gee = fit_gee(fixed_effect_df, ORTHOGONAL_FORMULA)
spline_gee, spline_design = fit_spline_model(fixed_effect_df)
spline_joint = joint_wald_payload(spline_gee, "cr(log_rho")

volume_definition_sensitivities = {}
for sensitivity_name, agent_term, gold_term in [
    ("source_only", "log_ai_source_vol", "log_gold_source_vol"),
    ("test_only", "log_ai_test_vol", None),
    (
        "artifact_excluded", "log_ai_artifact_excluded_vol",
        "log_gold_artifact_excluded_vol",
    ),
    (
        "comment_excluded", "log_ai_comment_excluded_vol",
        "log_gold_comment_excluded_vol",
    ),
    ("hunk_counts", "log_hunks_ai", "log_hunks_gold"),
]:
    if sensitivity_name == "test_only" and not fixed_effect_df[
        "log_gold_test_vol"
    ].eq(0).all():
        raise AssertionError(
            "The locked cohort is expected to have zero developer test-only volume"
        )
    developer_term_status = "included"
    if gold_term is None:
        sensitivity_formula = (
            f"is_full_suite_failure ~ {agent_term} + {TOOL_TERM} + {REPO_TERM}"
        )
        developer_term_status = (
            "not estimable: developer test-only volume is constant zero in the "
            "locked cohort"
        )
    else:
        sensitivity_formula = (
            f"is_full_suite_failure ~ {agent_term} + {gold_term} + "
            f"{TOOL_TERM} + {REPO_TERM}"
        )
    fitted = fit_gee(fixed_effect_df, sensitivity_formula)
    volume_definition_sensitivities[sensitivity_name] = {
        "formula": sensitivity_formula,
        "agent_term": agent_term,
        "developer_term": gold_term,
        "developer_term_status": developer_term_status,
        "terms": model_payload(fitted),
    }
adjusted = multipletests(
    [
        row["terms"][row["agent_term"]]["p_value"]
        for row in volume_definition_sensitivities.values()
    ],
    method="holm",
)[1]
for row, holm_p in zip(volume_definition_sensitivities.values(), adjusted):
    row["agent_term_holm_p_across_definitions"] = float(holm_p)

print("\nPRIMARY MODEL: component-volume GEE with repository fixed effects")
print(gee.summary().tables[1])
print("\nSENSITIVITY MODEL: GLM with issue-clustered standard errors")
print(glm.summary().tables[1])
print("\nNONLINEAR RATIO SENSITIVITY: 3-df natural cubic spline GEE")
print(
    f"  Joint spline Wald chi2({spline_joint['df']})="
    f"{spline_joint['chi2']:.4f}, p={spline_joint['p_value']:.6g}"
)

without_large = fixed_effect_df[fixed_effect_df["over_50k_chars"].eq(0)].copy()
gee_under_50k = fit_gee(without_large, PRIMARY_FORMULA)

scenarios = {
    "log_rho_only": {
        "features": ["log_rho"],
        "use_case": "gold-aware benchmark audit",
    },
    "volume_components": {
        "features": ["log_ai_vol", "log_gold_vol"],
        "use_case": "gold-aware benchmark audit",
    },
    "files_and_hunks": {
        "features": ["log_files_ai", "log_hunks_ai"],
        "use_case": "gold-free post-resolution triage",
    },
    "gold_free_volume_slices": {
        "features": [
            "log_ai_source_vol", "log_ai_test_vol",
            "log_ai_artifact_excluded_vol", "log_hunks_ai",
        ],
        "use_case": "gold-free post-resolution triage",
    },
    "source_volume_components": {
        "features": ["log_ai_source_vol", "log_gold_source_vol"],
        "use_case": "gold-aware benchmark audit",
    },
    "full_structural": {
        "features": ["log_ai_vol", "log_gold_vol", "log_files_ai", "log_hunks_ai", "tool"],
        "use_case": "gold-aware benchmark audit",
    },
    "file_alignment": {
        "features": [
            "file_jaccard", "log_agent_only_files", "log_gold_only_files",
            "artifact_like_agent_only", "tool",
        ],
        "use_case": "gold-aware benchmark audit",
    },
    "full_structural_alignment": {
        "features": [
            "log_ai_vol", "log_gold_vol", "log_files_ai", "log_hunks_ai",
            "file_jaccard", "log_agent_only_files", "log_gold_only_files",
            "artifact_like_agent_only", "tool",
        ],
        "use_case": "gold-aware benchmark audit",
    },
}

y = df["is_full_suite_failure"].to_numpy()
positive_prevalence = float(y.mean())
prevalence_brier = float(brier_score_loss(y, np.full(len(y), positive_prevalence)))
prediction_results = {}
prediction_rows = []
print("\nLEAVE-ONE-REPOSITORY-OUT PREDICTION")
for name, specification in scenarios.items():
    features = specification["features"]
    predictions, folds = grouped_predictions(df, features)
    pooled_auc = float(roc_auc_score(y, predictions))
    average_precision = float(average_precision_score(y, predictions))
    bootstrap = repository_bootstrap_metrics(df, predictions)
    brier = float(brier_score_loss(y, predictions))
    prediction_results[name] = {
        "features": features,
        "use_case": specification["use_case"],
        "pooled_auc": pooled_auc,
        "average_precision": average_precision,
        "repository_bootstrap_ci_95": bootstrap["roc_auc_ci_95"],
        "average_precision_repository_bootstrap_ci_95": bootstrap[
            "average_precision_ci_95"
        ],
        "brier_score": brier,
        "pooled_calibration": calibration_payload(y, predictions),
        "macro_metrics": fold_summary(folds),
        "review_budgets": review_budget_metrics(df, predictions),
        "folds": folds,
    }
    for row in folds:
        prediction_rows.append({"scenario": name, **row})
    print(
        f"  {name:<28} pooled AUC={pooled_auc:.3f}, "
        f"macro AUC={prediction_results[name]['macro_metrics']['macro_auc']:.3f}, "
        f"AP={average_precision:.3f}, Brier={brier:.4f}"
    )

all_df = prepare_features(load_resolved_packaged_dataset().reset_index(drop=True))
all_df["is_any_recorded_discrepancy"] = (
    all_df["label_status"].ne("no_observed_full_suite_failure").astype(int)
)
any_gee = fit_gee(all_df, ANY_DISCREPANCY_FORMULA)

loro_coefficient_stability = []
for omitted_repo in two_class_repositories:
    fitted = fit_gee(
        fixed_effect_df[fixed_effect_df["repo"].ne(omitted_repo)],
        LORO_COEFFICIENT_FORMULA,
    )
    loro_coefficient_stability.append({
        "omitted_repository": omitted_repo,
        "n": int(fixed_effect_df["repo"].ne(omitted_repo).sum()),
        "log_ai_vol": model_payload(fitted)["log_ai_vol"],
        "log_gold_vol": model_payload(fitted)["log_gold_vol"],
    })

profiles = repository_profiles(df)
repo_totals = repository_totals(df)
pd.DataFrame(profiles).to_csv(OUT_DIR / "repository_tool_profile.csv", index=False)
pd.DataFrame(repo_totals).to_csv(OUT_DIR / "repository_profile.csv", index=False)
pd.DataFrame(prediction_rows).to_json(
    OUT_DIR / "rq1_loro_fold_metrics.json", orient="records", indent=2
)

result = {
    "cohort": {
        "n": int(len(df)),
        "full_suite_failure_n": int(y.sum()),
        "unique_issues": int(df["instance_id"].nunique()),
        "repositories": int(df["repo"].nunique()),
        "explicit_empty_diff_n": int(df["is_empty_agent_diff"].sum()),
    },
    "repository_fixed_effect_inference_cohort": {
        "n": int(len(fixed_effect_df)),
        "full_suite_failure_n": int(
            fixed_effect_df["is_full_suite_failure"].sum()
        ),
        "unique_issues": int(fixed_effect_df["instance_id"].nunique()),
        "repositories": int(fixed_effect_df["repo"].nunique()),
        "included_two_class_repositories": two_class_repositories,
        "excluded_single_outcome_repositories": single_outcome_repositories,
        "reason": (
            "Repository fixed effects are estimated only where the outcome "
            "varies within repository; single-outcome repositories otherwise "
            "produce separated nuisance intercepts."
        ),
    },
    "primary_use_case": "gold-aware benchmark audit",
    "formula": PRIMARY_FORMULA,
    "primary_gee": {
        "dependence_parameter": float(np.asarray(gee.cov_struct.dep_params).reshape(-1)[0]),
        "terms": model_payload(gee),
    },
    "cluster_robust_glm": {"terms": model_payload(glm)},
    "no_repository_fixed_effect_sensitivity": {
        "formula": NO_REPO_FORMULA,
        "terms": model_payload(no_repo_gee),
    },
    "ratio_parameterization_sensitivity": {
        "formula": RATIO_FORMULA,
        "terms": model_payload(ratio_gee),
    },
    "orthogonal_scale_difference_sensitivity": {
        "formula": ORTHOGONAL_FORMULA,
        "definitions": {
            "log_volume_scale": "0.5 * (log1p(agent volume) + log1p(developer volume))",
            "log_volume_difference": "log1p(agent volume) - log1p(developer volume)",
        },
        "terms": model_payload(orthogonal_gee),
    },
    "volume_feature_correlations": df[
        ["log_ai_vol", "log_gold_vol", "log_rho"]
    ].corr().to_dict(),
    "volume_definition_sensitivities": volume_definition_sensitivities,
    "leave_one_repository_out_coefficient_stability": loro_coefficient_stability,
    "nonlinear_sensitivity": {
        "formula": SPLINE_FORMULA,
        "basis": "natural cubic regression spline",
        "spline_df": SPLINE_DF,
        "design_matrix": spline_design,
        "joint_wald": spline_joint,
        "terms": model_payload(spline_gee),
    },
    "under_50k_sensitivity": {
        "n": int(len(without_large)),
        "excluded_n_from_fixed_effect_cohort": int(
            len(fixed_effect_df) - len(without_large)
        ),
        "terms": model_payload(gee_under_50k),
    },
    "any_recorded_discrepancy_sensitivity": {
        "cohort_n": int(len(all_df)),
        "discrepancy_n": int(all_df["is_any_recorded_discrepancy"].sum()),
        "formula": ANY_DISCREPANCY_FORMULA,
        "terms": model_payload(any_gee),
    },
    "repository_tool_profiles": profiles,
    "repository_profiles": repo_totals,
    "predictive_validation": {
        "positive_prevalence": positive_prevalence,
        "prevalence_only_brier_score": prevalence_brier,
        "pooled_metrics_caution": (
            "Pooled held-out predictions combine repository folds with different "
            "prevalence and score calibration; macro and per-fold metrics are reported."
        ),
        "scenarios": prediction_results,
    },
}
OUT_DIR.mkdir(exist_ok=True)
path = OUT_DIR / "rq1_continuous_models.json"
path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
print(f"\nSaved -> {path}")
print(f"Saved -> {OUT_DIR / 'repository_tool_profile.csv'}")
print(f"Saved -> {OUT_DIR / 'repository_profile.csv'}")
print(f"Saved -> {OUT_DIR / 'rq1_loro_fold_metrics.json'}")

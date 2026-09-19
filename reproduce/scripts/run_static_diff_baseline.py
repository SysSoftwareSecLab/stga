# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "scikit-learn"]
# ///
"""Evaluate a fixed, zero-execution lexical/path final-diff baseline.

This baseline is APCA-inspired in evaluation purpose, but deliberately lighter
than AST- or execution-based APCA systems. Every feature is computed from the
agent's submitted unified diff. Developer patches and outcome labels are not
used during feature extraction.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from common import BASE, TOOL_SPECS, load_primary_dataset, load_tool_predictions


OUT_DIR = BASE / "output"
RANDOM_SEED = 20260722
BOOTSTRAP_REPLICATES = 2000

ARTIFACT_BASENAME = re.compile(
    r"^(?:repro|reproduce|reproducer|debug|scratch|tmp[_-]|temp[_-])",
    re.IGNORECASE,
)
LEXICAL_PATTERNS = {
    "conditional": re.compile(r"^\s*(?:if|elif)\b"),
    "loop": re.compile(r"^\s*(?:for|while)\b"),
    "exception": re.compile(r"\b(?:assert|raise|try|except|finally)\b"),
    "type_guard": re.compile(r"\b(?:isinstance|issubclass|hasattr|getattr)\s*\("),
    "import": re.compile(r"^\s*(?:from|import)\b"),
    "return": re.compile(r"^\s*return\b"),
}

COUNT_FEATURES = [
    "added_lines",
    "deleted_lines",
    "changed_files",
    "hunks",
    "new_files",
    "deleted_files",
    "test_files",
    "docs_config_files",
    "artifact_like_files",
    *[
        f"{direction}_{category}"
        for category in LEXICAL_PATTERNS
        for direction in ("added", "deleted")
    ],
]
RATIO_FEATURES = [
    "deletion_share",
    "test_file_share",
    "python_file_share",
    "docs_config_file_share",
]
MODEL_FEATURES = [f"log1p_{name}" for name in COUNT_FEATURES] + RATIO_FEATURES


def target_path_from_header(line: str) -> str | None:
    """Extract the target path from a conventional git diff header."""
    if line.startswith("diff --git a/") and " b/" in line:
        return line.split(" b/", 1)[1].strip()
    if line.startswith("+++ b/"):
        return line[6:].strip()
    return None


def is_test_path(path: str) -> bool:
    normalized = "/" + path.lower().strip("/")
    name = PurePosixPath(path).name.lower()
    return (
        "/test/" in normalized
        or "/tests/" in normalized
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def is_docs_or_config_path(path: str) -> bool:
    normalized = "/" + path.lower().strip("/")
    suffix = PurePosixPath(path).suffix.lower()
    name = PurePosixPath(path).name.lower()
    return (
        "/doc/" in normalized
        or "/docs/" in normalized
        or suffix in {".md", ".rst", ".txt", ".toml", ".ini", ".cfg", ".yaml", ".yml"}
        or name in {"pyproject.toml", "setup.cfg", "tox.ini"}
    )


def is_artifact_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(
        ARTIFACT_BASENAME.search(pure.name)
        or pure.suffix.lower() == ".ipynb"
    )


def extract_diff_features(patch: str) -> dict[str, float]:
    """Extract fixed path and lexical counts from one submitted unified diff."""
    counts = {name: 0 for name in COUNT_FEATURES}
    changed_paths: set[str] = set()
    current_path: str | None = None

    for line in patch.splitlines():
        header_path = target_path_from_header(line)
        if header_path and header_path != "/dev/null":
            current_path = header_path
            changed_paths.add(header_path)

        if line.startswith("new file mode "):
            counts["new_files"] += 1
            continue
        if line.startswith("deleted file mode "):
            counts["deleted_files"] += 1
            continue
        if line.startswith("@@"):
            counts["hunks"] += 1
            continue
        if line.startswith(("+++", "---")):
            continue

        if line.startswith("+"):
            direction = "added"
            counts["added_lines"] += 1
        elif line.startswith("-"):
            direction = "deleted"
            counts["deleted_lines"] += 1
        else:
            continue

        content = line[1:]
        for category, pattern in LEXICAL_PATTERNS.items():
            if pattern.search(content):
                counts[f"{direction}_{category}"] += 1

    counts["changed_files"] = len(changed_paths)
    counts["test_files"] = sum(is_test_path(path) for path in changed_paths)
    counts["docs_config_files"] = sum(
        is_docs_or_config_path(path) for path in changed_paths
    )
    counts["artifact_like_files"] = sum(
        is_artifact_path(path) for path in changed_paths
    )

    changed_line_n = counts["added_lines"] + counts["deleted_lines"]
    file_n = counts["changed_files"]
    features: dict[str, float] = {
        **{f"log1p_{name}": float(np.log1p(value)) for name, value in counts.items()},
        "deletion_share": counts["deleted_lines"] / changed_line_n if changed_line_n else 0.0,
        "test_file_share": counts["test_files"] / file_n if file_n else 0.0,
        "python_file_share": (
            sum(PurePosixPath(path).suffix.lower() == ".py" for path in changed_paths)
            / file_n
            if file_n
            else 0.0
        ),
        "docs_config_file_share": (
            counts["docs_config_files"] / file_n if file_n else 0.0
        ),
    }
    return features


def build_feature_frame() -> pd.DataFrame:
    primary = load_primary_dataset()
    patch_lookup: dict[tuple[str, str], str] = {}
    for tool in TOOL_SPECS:
        for instance_id, record in load_tool_predictions(tool).items():
            if "model_patch" in record and record["model_patch"] is not None:
                patch_lookup[(tool, instance_id)] = record["model_patch"]

    rows = []
    for row in primary.itertuples(index=False):
        key = (row.tool, row.instance_id)
        if key not in patch_lookup:
            raise ValueError(f"Missing patch for primary row {row.tool}/{row.instance_id}")
        patch = patch_lookup[key]
        rows.append(
            {
                "instance_id": row.instance_id,
                "repo": row.repo,
                "tool": row.tool,
                "is_full_suite_failure": int(row.is_full_suite_failure),
                "is_empty_agent_diff": int(patch == ""),
                **extract_diff_features(patch),
            }
        )
    return pd.DataFrame(rows)


def make_pipeline() -> Pipeline:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    preprocess = ColumnTransformer(
        transformers=[("numeric", numeric, MODEL_FEATURES)],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("preprocess", preprocess),
            (
                "model",
                LogisticRegression(
                    C=1.0,
                    solver="lbfgs",
                    max_iter=5000,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def leave_one_repository_out(frame: pd.DataFrame):
    predictions = np.full(len(frame), np.nan)
    folds = []
    y = frame["is_full_suite_failure"].to_numpy()
    for repo in sorted(frame["repo"].unique()):
        test_mask = frame["repo"].eq(repo).to_numpy()
        train_mask = ~test_mask
        model = make_pipeline()
        model.fit(frame.loc[train_mask, MODEL_FEATURES], y[train_mask])
        fold_predictions = model.predict_proba(
            frame.loc[test_mask, MODEL_FEATURES]
        )[:, 1]
        predictions[test_mask] = fold_predictions
        fold_y = y[test_mask]
        fold_auc = (
            float(roc_auc_score(fold_y, fold_predictions))
            if len(np.unique(fold_y)) == 2
            else None
        )
        folds.append(
            {
                "held_out_repository": repo,
                "train_n": int(train_mask.sum()),
                "test_n": int(test_mask.sum()),
                "test_failure_n": int(fold_y.sum()),
                "test_failure_prevalence": float(fold_y.mean()),
                "roc_auc": fold_auc,
                "average_precision": (
                    float(average_precision_score(fold_y, fold_predictions))
                    if fold_y.sum() > 0 else None
                ),
                "brier_score": float(brier_score_loss(fold_y, fold_predictions)),
                "calibration": calibration_payload(fold_y, fold_predictions),
                "mean_prediction": float(fold_predictions.mean()),
            }
        )
    if np.isnan(predictions).any():
        raise RuntimeError("At least one row did not receive a held-out prediction")
    return predictions, folds


def calibration_payload(y: np.ndarray, probabilities: np.ndarray):
    if np.unique(y).size != 2:
        return {"intercept": None, "slope": None}
    logits = np.log(
        np.clip(probabilities, 1e-6, 1 - 1e-6)
        / (1 - np.clip(probabilities, 1e-6, 1 - 1e-6))
    ).reshape(-1, 1)
    model = LogisticRegression(C=1e6, max_iter=5000, random_state=RANDOM_SEED)
    model.fit(logits, y)
    return {
        "intercept": float(model.intercept_[0]),
        "slope": float(model.coef_[0, 0]),
    }


def review_budget_metrics(frame: pd.DataFrame, predictions: np.ndarray):
    y = frame["is_full_suite_failure"].to_numpy()
    selected_by_budget = {0.10: [], 0.20: []}
    repository_rows = {0.10: [], 0.20: []}
    for repo in sorted(frame["repo"].unique()):
        indices = np.flatnonzero(frame["repo"].eq(repo).to_numpy())
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
    rng = np.random.default_rng(RANDOM_SEED)
    for budget, selected in selected_by_budget.items():
        selected = np.asarray(selected, dtype=int)
        captured = int(y[selected].sum())
        strata = repository_rows[budget]
        recall_samples = []
        precision_samples = []
        for _ in range(BOOTSTRAP_REPLICATES):
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


def repository_bootstrap(frame: pd.DataFrame, predictions: np.ndarray):
    rng = np.random.default_rng(RANDOM_SEED)
    repos = np.array(sorted(frame["repo"].unique()))
    y = frame["is_full_suite_failure"].to_numpy()
    aucs = []
    aps = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_repos = rng.choice(repos, size=len(repos), replace=True)
        sampled_indices = np.concatenate(
            [np.flatnonzero(frame["repo"].eq(repo).to_numpy()) for repo in sampled_repos]
        )
        sample_y = y[sampled_indices]
        if len(np.unique(sample_y)) < 2:
            continue
        sample_predictions = predictions[sampled_indices]
        aucs.append(roc_auc_score(sample_y, sample_predictions))
        aps.append(average_precision_score(sample_y, sample_predictions))
    return {
        "valid_replicates": len(aucs),
        "roc_auc_ci_95": [float(value) for value in np.quantile(aucs, [0.025, 0.975])],
        "average_precision_ci_95": [
            float(value) for value in np.quantile(aps, [0.025, 0.975])
        ],
    }


frame = build_feature_frame().reset_index(drop=True)
predictions, folds = leave_one_repository_out(frame)
y = frame["is_full_suite_failure"].to_numpy()
bootstrap = repository_bootstrap(frame, predictions)

frame["loro_failure_probability"] = predictions
feature_path = OUT_DIR / "static_diff_loro_predictions.csv"
OUT_DIR.mkdir(exist_ok=True)
frame.to_csv(feature_path, index=False)

result = {
    "scope": "zero-execution, agent-final-diff-only lexical and path baseline",
    "model": {
        "estimator": "L2-regularized logistic regression",
        "penalty": "l2",
        "C": 1.0,
        "class_weight": None,
        "hyperparameter_search": False,
        "preprocessing": "median imputation and standardization fitted within each training fold",
    },
    "validation": {
        "scheme": "leave one repository out; pool all held-out predictions",
        "repository_n": int(frame["repo"].nunique()),
        "bootstrap_unit": "repository",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "random_seed": RANDOM_SEED,
    },
    "cohort": {
        "n": int(len(frame)),
        "failure_n": int(y.sum()),
        "failure_prevalence": float(y.mean()),
        "explicit_empty_diff_n": int(frame["is_empty_agent_diff"].sum()),
    },
    "features": {
        "n": len(MODEL_FEATURES),
        "names": MODEL_FEATURES,
        "prohibited_inputs": [
            "developer patch",
            "developer-patch alignment",
            "developer-test outcome label during feature extraction",
            "test execution",
        ],
    },
    "metrics": {
        "pooled_roc_auc": float(roc_auc_score(y, predictions)),
        "pooled_average_precision": float(average_precision_score(y, predictions)),
        "brier_score": float(brier_score_loss(y, predictions)),
        "pooled_calibration": calibration_payload(y, predictions),
        "macro_roc_auc": float(np.mean([
            row["roc_auc"] for row in folds if row["roc_auc"] is not None
        ])),
        "macro_average_precision": float(np.mean([
            row["average_precision"]
            for row in folds if row["average_precision"] is not None
        ])),
        "macro_brier_score": float(np.mean([
            row["brier_score"] for row in folds
        ])),
        "review_budgets": review_budget_metrics(frame, predictions),
        **bootstrap,
    },
    "folds": folds,
}
result_path = OUT_DIR / "static_diff_loro_baseline.json"
result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

print("ZERO-EXECUTION STATIC FINAL-DIFF BASELINE")
print(f"  Cohort: N={len(frame)}, failures={int(y.sum())}, repositories={frame['repo'].nunique()}")
print(f"  Features: {len(MODEL_FEATURES)} fixed lexical/path features")
print(
    f"  Pooled LORO ROC-AUC={result['metrics']['pooled_roc_auc']:.3f} "
    f"95% CI=[{bootstrap['roc_auc_ci_95'][0]:.3f}, {bootstrap['roc_auc_ci_95'][1]:.3f}]"
)
print(
    f"  Average precision={result['metrics']['pooled_average_precision']:.3f} "
    f"95% CI=[{bootstrap['average_precision_ci_95'][0]:.3f}, "
    f"{bootstrap['average_precision_ci_95'][1]:.3f}]"
)
print(f"  Brier score={result['metrics']['brier_score']:.4f}")
print(f"Saved -> {result_path}")
print(f"Saved -> {feature_path}")

"""Shared paths and loaders for the replication package."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent.parent
PATCHDIFF_ROOT = BASE / "external" / "PatchDiff"
PATCHDIFF_RESULTS = PATCHDIFF_ROOT / "results"
PATCHDIFF_DATA = PATCHDIFF_ROOT / "data"

TOOL_SPECS = {
    "OpenHands": {
        "folder": "20241029_OpenHands-CodeAct-2.1-sonnet-20241022_verified",
        "rq1": "RQ1_OpenHands_runall.json",
    },
    "CodeStory": {
        "folder": "20241221_codestory_midwit_claude-3-5-sonnet_swe-search",
        "rq1": "RQ1_CodeStory_runall.json",
    },
    "LearnByInteract": {
        "folder": "20250110_learn_by_interact_claude3.5",
        "rq1": "RQ1_LearnByInteract_runall.json",
    },
}


def require_patchdiff_inputs() -> None:
    """Fail with an actionable message when the official archive is absent."""
    required = [
        PATCHDIFF_DATA / "dataset" / "swebench_verified",
        PATCHDIFF_DATA / "tool_results",
        PATCHDIFF_RESULTS,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        joined = "\n  - ".join(missing)
        raise FileNotFoundError(
            "Official PatchDiff inputs are missing:\n"
            f"  - {joined}\n"
            "Download Zenodo record 17074796 and extract PatchDiff/ to "
            "reproduce/external/PatchDiff/."
        )


def load_gold_patches() -> dict[str, str]:
    from datasets import load_from_disk

    require_patchdiff_inputs()
    dataset_path = PATCHDIFF_DATA / "dataset" / "swebench_verified"
    dataset = load_from_disk(str(dataset_path))
    return {row["instance_id"]: row["patch"] for row in dataset}


def load_tool_predictions(tool: str) -> dict[str, dict]:
    spec = TOOL_SPECS[tool]
    path = PATCHDIFF_DATA / "tool_results" / spec["folder"] / "all_preds.jsonl"
    predictions = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            instance_id = record.get("instance_id") or record.get("isntance_id")
            if instance_id:
                predictions[instance_id] = record
    return predictions


def load_resolved_ids(tool: str) -> set[str]:
    spec = TOOL_SPECS[tool]
    path = PATCHDIFF_DATA / "tool_results" / spec["folder"] / "results.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    return set(result["resolved"])


def load_rq1_labels(tool: str) -> dict[str, str]:
    path = PATCHDIFF_RESULTS / TOOL_SPECS[tool]["rq1"]
    result = json.loads(path.read_text(encoding="utf-8"))
    return {
        instance_id: details.get("difference", "unknown")
        for instance_id, details in result.items()
    }


def load_resolved_packaged_dataset() -> pd.DataFrame:
    """Load all officially resolved trajectories with packaged patch fields."""
    path = BASE / "analysis_dataset.csv"
    df = pd.read_csv(path)
    required = {"label_status", "is_full_suite_failure"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} uses the legacy schema. Run scripts/build_analysis_dataset.py first. "
            f"Missing columns: {sorted(missing)}"
        )
    return df.copy()


def load_resolved_nonempty_dataset() -> pd.DataFrame:
    """Backward-compatible alias; explicit empty patch strings are now retained."""
    return load_resolved_packaged_dataset()


def load_primary_dataset() -> pd.DataFrame:
    """Load the primary full-developer-suite binary cohort."""
    df = load_resolved_packaged_dataset()
    primary = df[df["label_status"].isin(
        ["full_suite_functional_failure", "no_observed_full_suite_failure"]
    )].copy()
    primary["is_full_suite_failure"] = primary["is_full_suite_failure"].astype(int)
    return primary

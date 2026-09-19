# /// script
# requires-python = ">=3.11"
# dependencies = ["datasets", "pandas"]
# ///
"""Build the version-pinned, three-state developer-test analysis cohort.

Only trajectories listed as resolved in the official ICSE 2026 artifact are
eligible. The artifact's RQ1 outcomes come from running all available
developer tests; they are distinct from the generated differentiating-test
outcomes reported in the original paper's RQ2.
"""
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from collections import Counter, defaultdict

from common import (
    BASE,
    PATCHDIFF_DATA,
    PATCHDIFF_RESULTS,
    TOOL_SPECS,
    load_gold_patches,
    load_resolved_ids,
    load_rq1_labels,
    load_tool_predictions,
    require_patchdiff_inputs,
)
from verify_inputs import verify_inputs

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def volume(patch_str: str):
    """Return (added, deleted) non-metadata line counts."""
    added = deleted = 0
    for line in patch_str.split("\n"):
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return added, deleted

def parse_repo(instance_id: str) -> str:
    """django__django-10914 -> django/django"""
    # Split on __ to get owner and repo+issue
    parts = instance_id.split("__", 1)
    if len(parts) >= 2:
        owner = parts[0]
        # Remove trailing issue number: split on last '-'
        repo_issue = parts[1]
        idx = repo_issue.rfind("-")
        repo = repo_issue[:idx] if idx > 0 else repo_issue
        return owner + "/" + repo
    return instance_id

def diff_headers(patch_str: str):
    """Return (n_files, n_hunks) from unified diff."""
    n_files = patch_str.count("diff --git ")
    n_hunks = patch_str.count("\n@@ ")
    return n_files, n_hunks


def is_test_path(path: str) -> bool:
    normalized = "/" + path.lower().strip("/")
    name = Path(path).name.lower()
    return (
        "/test/" in normalized
        or "/tests/" in normalized
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def is_artifact_path(path: str) -> bool:
    pure = Path(path)
    return bool(
        ARTIFACT_BASENAME.search(pure.name)
        or pure.suffix.lower() == ".ipynb"
    )


def volume_slices(patch_str: str) -> dict[str, int]:
    """Count changed lines in transparent path/content-based slices."""
    values = {
        "source_vol": 0,
        "test_vol": 0,
        "artifact_excluded_vol": 0,
        "comment_excluded_vol": 0,
    }
    current_path = ""
    for line in patch_str.splitlines():
        if line.startswith("diff --git a/") and " b/" in line:
            current_path = line.split(" b/", 1)[1].strip()
            continue
        if line.startswith("+++ b/"):
            current_path = line[6:].strip()
            continue
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        content = line[1:].lstrip()
        artifact = is_artifact_path(current_path)
        test = is_test_path(current_path)
        source = Path(current_path).suffix.lower() == ".py" and not test and not artifact
        if source:
            values["source_vol"] += 1
        if test:
            values["test_vol"] += 1
        if not artifact:
            values["artifact_excluded_vol"] += 1
        if not content.startswith("#"):
            values["comment_excluded_vol"] += 1
    return values


def changed_files(patch_str: str):
    """Return normalized target paths from unified-diff headers."""
    files = []
    for line in patch_str.splitlines():
        if line.startswith("diff --git a/"):
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                files.append(parts[1].strip())
        elif line.startswith("+++ b/"):
            files.append(line[6:].strip())
    return list(dict.fromkeys(files))


ARTIFACT_BASENAME = re.compile(
    r"^(?:repro|reproduce|reproducer|debug|scratch|tmp[_-]|temp[_-])",
    re.IGNORECASE,
)


def artifact_like(paths):
    """Conservative path-only signal for likely exploratory artifacts."""
    return [
        path for path in paths
        if ARTIFACT_BASENAME.search(Path(path).name)
        or Path(path).suffix.lower() == ".ipynb"
    ]

require_patchdiff_inputs()
_, input_problems = verify_inputs()
if input_problems:
    details = "\n  - ".join(input_problems)
    raise RuntimeError(
        "Pinned PatchDiff input verification failed:\n"
        f"  - {details}\n"
        "Do not delete coding manifests or private keys. Repair the external "
        "input with: uv run scripts/setup_external_data.py --force"
    )
print("Loading version-pinned PatchDiff and SWE-bench Verified inputs...")
gold = load_gold_patches()

# ---------------------------------------------------------------------------
# build rows
# ---------------------------------------------------------------------------
rows = []
excluded_reasons = defaultdict(int)
exclusions = []
raw_resolved_n = 0
raw_rq1_counts = Counter()

for tool in TOOL_SPECS:
    predictions = load_tool_predictions(tool)
    resolved_ids = load_resolved_ids(tool)
    rq1_labels = load_rq1_labels(tool)
    raw_resolved_n += len(resolved_ids)
    raw_rq1_counts.update(rq1_labels.values())

    unknown_rq1 = set(rq1_labels).difference(resolved_ids)
    if unknown_rq1:
        raise ValueError(
            f"{tool}: {len(unknown_rq1)} RQ1 outcomes are not in the official resolved set"
        )

    for iid in sorted(resolved_ids):
            rec = predictions.get(iid)
            if rec is None:
                excluded_reasons["resolved_prediction_record_missing"] += 1
                exclusions.append({
                    "instance_id": iid,
                    "tool": tool,
                    "reason": "resolved_prediction_record_missing",
                })
                continue
            if "model_patch" not in rec or rec["model_patch"] is None:
                excluded_reasons["resolved_patch_field_missing"] += 1
                exclusions.append({
                    "instance_id": iid,
                    "tool": tool,
                    "reason": "resolved_patch_field_missing",
                })
                continue
            # An explicitly packaged empty string is a submitted zero-volume
            # patch, not missing data. Laplace smoothing keeps rho defined.
            patch = rec["model_patch"]
            if iid not in gold:
                excluded_reasons["no_gold"] += 1
                exclusions.append({
                    "instance_id": iid,
                    "tool": tool,
                    "reason": "no_gold",
                })
                continue

            ai_a, ai_d = volume(patch)
            g_a, g_d = volume(gold[iid])
            ai_slices = volume_slices(patch)
            gold_slices = volume_slices(gold[iid])

            if g_a + g_d == 0:
                excluded_reasons["zero_gold_volume"] += 1
                exclusions.append({
                    "instance_id": iid,
                    "tool": tool,
                    "reason": "zero_gold_volume",
                })
                continue

            rho = (ai_a + ai_d + 1) / (g_a + g_d + 1)
            log_rho = math.log(rho) if rho > 0 else 0.0
            difference = rq1_labels.get(iid)
            if difference == "functionality":
                label_status = "full_suite_functional_failure"
            elif difference == "coding_conventions":
                label_status = "coding_convention_only_failure"
            elif difference is None:
                label_status = "no_observed_full_suite_failure"
            else:
                raise ValueError(f"Unexpected RQ1 label {difference!r} for {tool}/{iid}")
            repo = parse_repo(iid)
            nf_ai, nh_ai = diff_headers(patch)
            nf_gold, nh_gold = diff_headers(gold[iid])
            ai_files = changed_files(patch)
            gold_files = changed_files(gold[iid])
            ai_file_set = set(ai_files)
            gold_file_set = set(gold_files)
            common_files = sorted(ai_file_set.intersection(gold_file_set))
            agent_only_files = sorted(ai_file_set.difference(gold_file_set))
            gold_only_files = sorted(gold_file_set.difference(ai_file_set))
            file_union = ai_file_set.union(gold_file_set)
            file_jaccard = (
                len(common_files) / len(file_union) if file_union else 1.0
            )
            artifact_files = artifact_like(agent_only_files)

            rows.append({
                "instance_id": iid,
                "repo": repo,
                "tool": tool,
                "ai_added": ai_a, "ai_deleted": ai_d,
                "ai_vol": ai_a + ai_d,
                "gold_added": g_a, "gold_deleted": g_d,
                "gold_vol": g_a + g_d,
                **{f"ai_{name}": value for name, value in ai_slices.items()},
                **{f"gold_{name}": value for name, value in gold_slices.items()},
                "rho": round(rho, 10),
                "log_rho": round(log_rho, 10),
                "label_status": label_status,
                "is_full_suite_failure": int(
                    label_status == "full_suite_functional_failure"
                ),
                "patch_chars": len(patch),
                "is_empty_agent_diff": int(patch == ""),
                "over_50k_chars": int(len(patch) > 50000),
                "n_files_ai": nf_ai, "n_hunks_ai": nh_ai,
                "n_files_gold": nf_gold, "n_hunks_gold": nh_gold,
                "ai_changed_files": ";".join(ai_files),
                "gold_changed_files": ";".join(gold_files),
                "n_common_files": len(common_files),
                "n_agent_only_files": len(agent_only_files),
                "n_gold_only_files": len(gold_only_files),
                "file_jaccard": round(file_jaccard, 10),
                "agent_only_files": ";".join(agent_only_files),
                "gold_only_files": ";".join(gold_only_files),
                "artifact_like_agent_only_n": len(artifact_files),
                "artifact_like_agent_only": int(bool(artifact_files)),
                "artifact_like_agent_only_files": ";".join(artifact_files),
            })

# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
label_counts = Counter(r["label_status"] for r in rows)
print(f"Total resolved rows with packaged patches: {len(rows)}")
for label, count in sorted(label_counts.items()):
    print(f"  {label}: {count}")
print(f"Excluded: {dict(excluded_reasons)}")

# per-tool
for tool in ["OpenHands", "CodeStory", "LearnByInteract"]:
    sub = [r for r in rows if r["tool"] == tool]
    counts = Counter(r["label_status"] for r in sub)
    print(f"  {tool}: {len(sub)} total, {dict(sorted(counts.items()))}")

# unique repos
repos = {r["repo"] for r in rows}
print(f"Unique repos: {sorted(repos)} ({len(repos)})")

# unique instances
instances = {r["instance_id"] for r in rows}
print(f"Unique instances: {len(instances)}")

# Per-instance recurrence among developer-test functional failures.
failure_rows = [r for r in rows if r["is_full_suite_failure"]]
by_instance = defaultdict(list)
for r in failure_rows:
    by_instance[r["instance_id"]].append(r["tool"])
agreement = Counter(len(v) for v in by_instance.values())
print(
    "Developer-test-failure recurrence (agents per instance): "
    f"{dict(sorted(agreement.items()))}"
)

# ---------------------------------------------------------------------------
# write CSV
# ---------------------------------------------------------------------------
expected = {
    "full_suite_functional_failure": 68,
    "coding_convention_only_failure": 36,
    "no_observed_full_suite_failure": 773,
}
if dict(label_counts) != expected:
    raise AssertionError(
        f"Version-pinned cohort changed: expected {expected}, observed {dict(label_counts)}"
    )

out = BASE / "analysis_dataset.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
print(f"\nWrote {out} ({len(rows)} rows)")

output_dir = BASE / "output"
output_dir.mkdir(exist_ok=True)
exclusion_path = output_dir / "cohort_exclusions.csv"
with exclusion_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["instance_id", "tool", "reason"])
    writer.writeheader()
    writer.writerows(exclusions)

input_paths = [
    PATCHDIFF_DATA / "dataset" / "swebench_verified" / "data-00000-of-00001.arrow",
]
for tool, spec in TOOL_SPECS.items():
    folder = PATCHDIFF_DATA / "tool_results" / spec["folder"]
    input_paths.extend([folder / "all_preds.jsonl", folder / "results.json"])
    input_paths.append(PATCHDIFF_RESULTS / spec["rq1"])

manifest = {
    "source": "PatchDiff Zenodo record 17074796",
    "doi": "10.5281/zenodo.17074796",
    "source_rq": "RQ1: revalidation with all available developer tests",
    "not_used_as_outcome": (
        "RQ2 generated differentiating-test suspicious-patch labels"
    ),
    "cohort_definition": (
        "Officially resolved trajectories with packaged patches, including explicit empty "
        "patch strings as zero-volume submissions; primary binary analysis "
        "compares full_suite_functional_failure with "
        "no_observed_full_suite_failure and excludes "
        "coding_convention_only_failure."
    ),
    "cohort_flow": {
        "swebench_verified_tasks": len(gold),
        "official_resolved_agent_instances": raw_resolved_n,
        "raw_rq1_functional_failures": raw_rq1_counts["functionality"],
        "raw_rq1_coding_convention_failures": raw_rq1_counts["coding_conventions"],
        "resolved_with_packaged_patch": len(rows),
        "explicit_empty_agent_diffs": sum(r["is_empty_agent_diff"] for r in rows),
        "excluded_resolved_prediction_record_missing": excluded_reasons[
            "resolved_prediction_record_missing"
        ],
        "excluded_resolved_patch_field_missing": excluded_reasons[
            "resolved_patch_field_missing"
        ],
        "excluded_no_gold": excluded_reasons["no_gold"],
        "excluded_zero_gold_volume": excluded_reasons["zero_gold_volume"],
        "analyzable_full_suite_functional_failures": label_counts[
            "full_suite_functional_failure"
        ],
        "primary_binary_cohort": (
            label_counts["full_suite_functional_failure"]
            + label_counts["no_observed_full_suite_failure"]
        ),
    },
    "counts": dict(sorted(label_counts.items())),
    "files": {},
}
expected_flow = {
    "swebench_verified_tasks": 500,
    "official_resolved_agent_instances": 877,
    "raw_rq1_functional_failures": 68,
    "raw_rq1_coding_convention_failures": 36,
    "resolved_with_packaged_patch": 877,
    "explicit_empty_agent_diffs": 1,
    "excluded_resolved_prediction_record_missing": 0,
    "excluded_resolved_patch_field_missing": 0,
    "excluded_no_gold": 0,
    "excluded_zero_gold_volume": 0,
    "analyzable_full_suite_functional_failures": 68,
    "primary_binary_cohort": 841,
}
if manifest["cohort_flow"] != expected_flow:
    raise AssertionError(
        "Version-pinned cohort flow changed: "
        f"expected {expected_flow}, observed {manifest['cohort_flow']}"
    )
for path in input_paths:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest["files"][str(path.relative_to(BASE)).replace("\\", "/")] = {
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }
(output_dir / "input_manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
)
print(f"Wrote {exclusion_path} ({len(exclusions)} rows)")
print(f"Wrote {output_dir / 'input_manifest.json'}")

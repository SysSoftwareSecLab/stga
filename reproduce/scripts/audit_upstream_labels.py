# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas"]
# ///
"""Audit provenance and internal consistency of inherited RQ1 labels.

This audit does not execute developer tests and is therefore not an
independent behavioral revalidation. It verifies that every inherited label
maps to an official resolved prediction, that positive records identify at
least one developer-test discrepancy, and that prediction records and patch
fields are present (including explicit empty strings).
"""

from __future__ import annotations

import json
from collections import Counter

from common import (
    BASE,
    PATCHDIFF_DATA,
    PATCHDIFF_RESULTS,
    TOOL_SPECS,
    load_resolved_ids,
    require_patchdiff_inputs,
)
from verify_inputs import verify_inputs


OUT_DIR = BASE / "output"
require_patchdiff_inputs()
_, verification_problems = verify_inputs()
if verification_problems:
    raise RuntimeError("Pinned-input verification failed: " + "; ".join(verification_problems))

tool_results = []
all_functional = []
all_conventions = []
all_empty = []

for tool, spec in TOOL_SPECS.items():
    prediction_path = (
        PATCHDIFF_DATA / "tool_results" / spec["folder"] / "all_preds.jsonl"
    )
    prediction_records = []
    with prediction_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            instance_id = record.get("instance_id") or record.get("isntance_id")
            prediction_records.append((line_number, instance_id, record))

    ids = [instance_id for _, instance_id, _ in prediction_records]
    duplicate_ids = sorted(
        instance_id for instance_id, count in Counter(ids).items() if count > 1
    )
    prediction_by_id = {instance_id: record for _, instance_id, record in prediction_records}
    resolved = load_resolved_ids(tool)
    rq1_path = PATCHDIFF_RESULTS / spec["rq1"]
    rq1 = json.loads(rq1_path.read_text(encoding="utf-8"))

    outside_resolved = sorted(set(rq1).difference(resolved))
    missing_prediction = sorted(resolved.difference(prediction_by_id))
    missing_patch_field = sorted(
        instance_id
        for instance_id in resolved.intersection(prediction_by_id)
        if "model_patch" not in prediction_by_id[instance_id]
        or prediction_by_id[instance_id]["model_patch"] is None
    )
    empty_patch = sorted(
        instance_id
        for instance_id in resolved.intersection(prediction_by_id)
        if prediction_by_id[instance_id].get("model_patch") == ""
    )

    functional = []
    conventions = []
    malformed = []
    for instance_id, details in rq1.items():
        difference = details.get("difference")
        tests = details.get("oracle_pass_model_fail")
        if difference == "functionality":
            functional.append(instance_id)
            all_functional.append({"tool": tool, "instance_id": instance_id})
        elif difference == "coding_conventions":
            conventions.append(instance_id)
            all_conventions.append({"tool": tool, "instance_id": instance_id})
        else:
            malformed.append({
                "instance_id": instance_id,
                "problem": f"unexpected difference={difference!r}",
            })
        if not isinstance(tests, list) or not tests:
            malformed.append({
                "instance_id": instance_id,
                "problem": "oracle_pass_model_fail is absent, non-list, or empty",
            })

    all_empty.extend({"tool": tool, "instance_id": value} for value in empty_patch)
    tool_results.append({
        "tool": tool,
        "prediction_jsonl_rows": len(prediction_records),
        "prediction_duplicate_instance_ids": duplicate_ids,
        "official_resolved_n": len(resolved),
        "rq1_labeled_n": len(rq1),
        "functional_failure_n": len(functional),
        "coding_convention_n": len(conventions),
        "rq1_ids_outside_official_resolved": outside_resolved,
        "resolved_ids_missing_prediction_record": missing_prediction,
        "resolved_ids_missing_patch_field": missing_patch_field,
        "resolved_ids_with_explicit_empty_patch": empty_patch,
        "malformed_rq1_records": malformed,
    })

problems = []
for row in tool_results:
    for field in [
        "prediction_duplicate_instance_ids",
        "rq1_ids_outside_official_resolved",
        "resolved_ids_missing_prediction_record",
        "resolved_ids_missing_patch_field",
        "malformed_rq1_records",
    ]:
        if row[field]:
            problems.append(f"{row['tool']}: nonempty {field}")

payload = {
    "audit_scope": "provenance and artifact-level internal consistency",
    "independent_behavioral_revalidation_performed": False,
    "limitation": (
        "The audit does not execute SWE-bench environments or developer tests and "
        "cannot verify environment fidelity, flaky-test handling, or behavioral labels."
    ),
    "recommended_independent_campaign": (
        "Re-execute all 68 inherited functionality-positive records, or a preregistered "
        "tool-by-repository stratified sample, using the upstream environment protocol."
    ),
    "totals": {
        "functional_failure_n": len(all_functional),
        "coding_convention_n": len(all_conventions),
        "explicit_empty_patch_n": len(all_empty),
    },
    "explicit_empty_patches": all_empty,
    "tools": tool_results,
    "problems": problems,
    "status": "pass" if not problems else "fail",
}

expected_totals = {
    "functional_failure_n": 68,
    "coding_convention_n": 36,
    "explicit_empty_patch_n": 1,
}
if payload["totals"] != expected_totals:
    raise AssertionError(
        f"Pinned upstream totals changed: expected {expected_totals}, observed {payload['totals']}"
    )
if all_empty != [{"tool": "CodeStory", "instance_id": "django__django-12708"}]:
    raise AssertionError(f"Unexpected explicit-empty-patch records: {all_empty}")
if problems:
    raise AssertionError("Label provenance audit failed: " + "; ".join(problems))

OUT_DIR.mkdir(exist_ok=True)
path = OUT_DIR / "upstream_label_provenance_audit.json"
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Upstream label provenance audit: PASS")
print(f"  Functionality labels: {len(all_functional)}")
print(f"  Coding-convention labels: {len(all_conventions)}")
print(f"  Explicit empty patches: {len(all_empty)}")
print("  Independent behavioral revalidation: NOT PERFORMED")
print(f"Saved -> {path}")

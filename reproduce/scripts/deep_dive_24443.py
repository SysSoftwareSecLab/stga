# /// script
# requires-python = ">=3.11"
# dependencies = ["datasets"]
# ///
"""Materialize the motivating example from the version-pinned local archive."""

from __future__ import annotations

import json

from common import (
    BASE,
    PATCHDIFF_RESULTS,
    TOOL_SPECS,
    load_gold_patches,
    load_tool_predictions,
)


TARGET = "sympy__sympy-24443"
OUT_DIR = BASE / "output"


def volume(patch: str) -> dict[str, int]:
    added = sum(
        line.startswith("+") and not line.startswith("+++")
        for line in patch.splitlines()
    )
    deleted = sum(
        line.startswith("-") and not line.startswith("---")
        for line in patch.splitlines()
    )
    return {"added": added, "deleted": deleted, "total": added + deleted}


gold_patch = load_gold_patches()[TARGET]
payload = {
    "instance_id": TARGET,
    "source": "version-pinned PatchDiff ICSE 2026 artifact",
    "developer_patch": {
        "patch": gold_patch,
        "characters": len(gold_patch),
        "volume": volume(gold_patch),
    },
    "agents": {},
}

for tool, spec in TOOL_SPECS.items():
    prediction = load_tool_predictions(tool)[TARGET]
    patch = prediction.get("model_patch", "")
    rq1_path = PATCHDIFF_RESULTS / spec["rq1"]
    rq1_record = json.loads(rq1_path.read_text(encoding="utf-8"))[TARGET]
    if rq1_record.get("difference") != "functionality":
        raise AssertionError(f"{tool} does not have the expected functional-failure outcome")
    payload["agents"][tool] = {
        "patch": patch,
        "characters": len(patch),
        "volume": volume(patch),
        "full_suite_outcome": rq1_record.get("difference"),
        "developer_pass_agent_fail": rq1_record.get("oracle_pass_model_fail", []),
    }

OUT_DIR.mkdir(exist_ok=True)
path = OUT_DIR / "motivating_example_24443.json"
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

print(f"Motivating example: {TARGET}")
print(f"  developer volume: {payload['developer_patch']['volume']['total']} lines")
for tool, record in payload["agents"].items():
    print(
        f"  {tool:<16} volume={record['volume']['total']} lines, "
        f"failing developer tests={len(record['developer_pass_agent_fail'])}"
    )
print(f"Saved -> {path}")

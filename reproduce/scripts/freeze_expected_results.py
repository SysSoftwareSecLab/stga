# /// script
# requires-python = ">=3.11"
# ///
"""Freeze reviewed generated outputs into EXPECTED_RESULTS.json.

This is a maintainer-only release step. It snapshots files; it does not establish
that the scientific results are correct. Review the outputs and manuscript
claim--evidence mapping before invoking it.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from verify_results import canonical_result_sha256, csv_semantic_summary, file_sha256


BASE = Path(__file__).resolve().parent.parent
EXPECTED_PATH = BASE / "EXPECTED_RESULTS.json"
CONFIRMATION = "reviewed-linux-results"
RESULT_FILES = [
    "analysis_dataset.csv",
    "output/cohort_exclusions.csv",
    "output/input_manifest.json",
    "output/upstream_label_provenance_audit.json",
    "output/repository_tool_profile.csv",
    "output/repository_profile.csv",
    "output/rq1_loro_fold_metrics.json",
    "output/rq1_continuous_models.json",
    "output/static_diff_loro_predictions.csv",
    "output/static_diff_loro_baseline.json",
    "output/structural_alignment_matched_pairs.csv",
    "output/structural_alignment_balance.csv",
    "output/structural_alignment_matching_sensitivity.csv",
    "output/structural_alignment_loro_sensitivity.csv",
    "output/structural_alignment_results.json",
    "output/structural_alignment_within_issue_contrasts.csv",
    "output/structural_alignment_within_issue_sensitivity.json",
    "output/paired_design_sensitivity.json",
    "output/rq3_complete_case_selection.csv",
    "output/rq3_results.json",
    "output/fig2_repository_transport.pdf",
    "output/fig2_repository_transport.png",
    "output/fig2_repository_transport_panel_a.pdf",
    "output/fig2_repository_transport_panel_b.pdf",
    "output/fig2_repository_transport_data.csv",
    "output/fig2_volume_distribution.pdf",
    "output/fig2_volume_distribution_panel_a.pdf",
    "output/fig2_volume_distribution_panel_b.pdf",
    "output/rq1_results.json",
    "output/motivating_example_24443.json",
]


def metadata_for(relative: str) -> dict:
    path = BASE / relative
    if not path.is_file():
        raise FileNotFoundError(f"Required reviewed result is missing: {relative}")
    metadata: dict[str, object] = {
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }
    if path.suffix == ".json":
        content = json.loads(path.read_text(encoding="utf-8"))
        metadata.update({
            "canonical_sha256": canonical_result_sha256(path),
            "semantic_content": content,
            "verification": "raw-canonical-or-semantic",
        })
    elif path.suffix == ".csv":
        metadata.update({
            "canonical_sha256": canonical_result_sha256(path),
            "semantic_summary": csv_semantic_summary(path),
            "verification": "raw-canonical-or-semantic",
        })
    elif path.suffix == ".pdf":
        metadata.update({
            "minimum_bytes": 10_000,
            "verification": "pdf-artifact",
        })
    elif path.suffix == ".png":
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
            raise ValueError(f"Invalid PNG result: {relative}")
        width, height = struct.unpack(">II", data[16:24])
        metadata.update({
            "minimum_bytes": 10_000,
            "width": width,
            "height": height,
            "verification": "png-artifact",
        })
    else:
        raise ValueError(f"Unsupported result type: {relative}")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"Required release confirmation token: {CONFIRMATION}",
    )
    args = parser.parse_args()
    if args.confirm != CONFIRMATION:
        parser.error(f"--confirm must equal {CONFIRMATION!r}")

    payload = {
        "files": {relative: metadata_for(relative) for relative in RESULT_FILES},
        "purpose": (
            "Portable verification metadata for reviewed release-time Linux "
            "analysis results. The public archive does not contain "
            "the precomputed result files."
        ),
        "verification_policy": {
            "json_csv": (
                "Accept an exact byte hash, a canonical structured-content hash, "
                "or a schema-preserving semantic comparison with rtol=1e-7 and "
                "atol=1e-10 for numeric values."
            ),
            "pdf": (
                "Require a nontrivial valid PDF artifact. Numerical values plotted "
                "in figures are verified through companion JSON/CSV results."
            ),
            "png": (
                "Require a nontrivial PNG with the release-time dimensions. "
                "Numerical values are verified through companion JSON/CSV results."
            ),
        },
    }
    EXPECTED_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {EXPECTED_PATH} with {len(RESULT_FILES)} reviewed result files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

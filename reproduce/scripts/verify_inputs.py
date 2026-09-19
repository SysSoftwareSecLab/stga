# /// script
# requires-python = ">=3.11"
# ///
"""Verify the exact PatchDiff v3 inputs before any analysis is run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
EXPECTED_PATH = BASE / "data" / "expected_patchdiff_inputs.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inputs() -> tuple[dict, list[str]]:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    problems: list[str] = []
    for relative, record in expected["files"].items():
        path = BASE / relative
        if not path.is_file():
            problems.append(f"missing: {relative}")
            continue
        actual_bytes = path.stat().st_size
        if actual_bytes != record["bytes"]:
            problems.append(
                f"size mismatch: {relative} "
                f"(expected {record['bytes']}, found {actual_bytes})"
            )
            continue
        actual_hash = file_sha256(path)
        if actual_hash != record["sha256"]:
            problems.append(
                f"SHA-256 mismatch: {relative} "
                f"(expected {record['sha256']}, found {actual_hash})"
            )
    return expected, problems


def main() -> None:
    expected, problems = verify_inputs()
    if problems:
        print("PatchDiff input verification failed:")
        for problem in problems:
            print(f"  - {problem}")
        print()
        print(
            "Use the pinned PatchDiff_0908.7z archive from Zenodo record "
            f"{expected['record']} ({expected['version']})."
        )
        print(
            "Do not delete coding manifests or private keys. Repair the external "
            "input with: uv run scripts/setup_external_data.py --force"
        )
        raise SystemExit(3)
    print(
        "PatchDiff input verification passed: "
        f"{len(expected['files'])} files from record {expected['record']} "
        f"({expected['version']})."
    )


if __name__ == "__main__":
    main()

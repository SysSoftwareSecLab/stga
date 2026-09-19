# /// script
# requires-python = ">=3.11"
# ///
"""Verify outputs against release hashes, structured content, and artifact checks."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import struct
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
EXPECTED_PATH = BASE / "EXPECTED_RESULTS.json"
FLOAT_REL_TOL = 1e-7
FLOAT_ABS_TOL = 1e-10


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_result_sha256(path: Path) -> str:
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        data = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    elif path.suffix == ".csv":
        text = path.read_text(encoding="utf-8-sig")
        rows = list(csv.reader(io.StringIO(text, newline="")))
        data = json.dumps(
            rows,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    else:
        raise ValueError(f"No canonical verifier for {path.suffix}: {path}")
    return hashlib.sha256(data).hexdigest()


def compare_json_values(expected_value, actual_value, location: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(expected_value, bool) or expected_value is None:
        if actual_value != expected_value:
            problems.append(f"{location}: expected {expected_value!r}, found {actual_value!r}")
        return problems
    if isinstance(expected_value, (int, float)) and isinstance(
        actual_value, (int, float)
    ) and not isinstance(actual_value, bool):
        expected_number = float(expected_value)
        actual_number = float(actual_value)
        if math.isnan(expected_number) or math.isnan(actual_number):
            if not (math.isnan(expected_number) and math.isnan(actual_number)):
                problems.append(
                    f"{location}: expected {expected_value!r}, found {actual_value!r}"
                )
            return problems
        if not math.isclose(
            expected_number,
            actual_number,
            rel_tol=FLOAT_REL_TOL,
            abs_tol=FLOAT_ABS_TOL,
        ):
            problems.append(
                f"{location}: expected {expected_value!r}, found {actual_value!r}"
            )
        return problems
    if isinstance(expected_value, str):
        if actual_value != expected_value:
            problems.append(f"{location}: text differs")
        return problems
    if isinstance(expected_value, list):
        if not isinstance(actual_value, list):
            return [f"{location}: expected list, found {type(actual_value).__name__}"]
        if len(expected_value) != len(actual_value):
            return [
                f"{location}: expected {len(expected_value)} items, "
                f"found {len(actual_value)}"
            ]
        for index, (expected_item, actual_item) in enumerate(
            zip(expected_value, actual_value)
        ):
            problems.extend(
                compare_json_values(
                    expected_item,
                    actual_item,
                    f"{location}[{index}]",
                )
            )
            if len(problems) >= 10:
                break
        return problems
    if isinstance(expected_value, dict):
        if not isinstance(actual_value, dict):
            return [f"{location}: expected object, found {type(actual_value).__name__}"]
        if set(expected_value) != set(actual_value):
            missing = sorted(set(expected_value) - set(actual_value))
            extra = sorted(set(actual_value) - set(expected_value))
            return [f"{location}: key mismatch; missing={missing}, extra={extra}"]
        for key in sorted(expected_value):
            problems.extend(
                compare_json_values(
                    expected_value[key],
                    actual_value[key],
                    f"{location}.{key}",
                )
            )
            if len(problems) >= 10:
                break
        return problems
    if actual_value != expected_value:
        problems.append(f"{location}: value differs")
    return problems


def csv_semantic_summary(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    columns = list(reader.fieldnames or [])
    rows = list(reader)
    summary: dict[str, object] = {
        "rows": len(rows),
        "columns": columns,
        "column_summaries": {},
    }
    for column in columns:
        raw_values = [row.get(column, "") for row in rows]
        numeric_values: list[tuple[int, float]] = []
        numeric = True
        for index, raw in enumerate(raw_values):
            value = raw.strip()
            if value == "":
                continue
            try:
                parsed = float(value)
            except ValueError:
                numeric = False
                break
            if not math.isfinite(parsed):
                numeric = False
                break
            numeric_values.append((index + 1, parsed))
        if numeric and numeric_values:
            values = [value for _, value in numeric_values]
            summary["column_summaries"][column] = {
                "kind": "numeric",
                "count": len(values),
                "missing": len(raw_values) - len(values),
                "minimum": min(values),
                "maximum": max(values),
                "sum": math.fsum(values),
                "sum_squares": math.fsum(value * value for value in values),
                "position_weighted_sum": math.fsum(
                    index * value for index, value in numeric_values
                ),
            }
        else:
            encoded = json.dumps(
                raw_values,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            summary["column_summaries"][column] = {
                "kind": "text",
                "values_sha256": hashlib.sha256(encoded).hexdigest(),
            }
    return summary


def compare_csv_summaries(expected_summary: dict, actual_summary: dict) -> list[str]:
    problems: list[str] = []
    if expected_summary["rows"] != actual_summary["rows"]:
        problems.append(
            f"row count: expected {expected_summary['rows']}, "
            f"found {actual_summary['rows']}"
        )
    if expected_summary["columns"] != actual_summary["columns"]:
        problems.append("column names or order differ")
        return problems
    for column in expected_summary["columns"]:
        expected_column = expected_summary["column_summaries"][column]
        actual_column = actual_summary["column_summaries"][column]
        if expected_column["kind"] != actual_column["kind"]:
            problems.append(f"{column}: column type differs")
            continue
        if expected_column["kind"] == "text":
            if expected_column["values_sha256"] != actual_column["values_sha256"]:
                problems.append(f"{column}: text values differ")
            continue
        for key in ("count", "missing"):
            if expected_column[key] != actual_column[key]:
                problems.append(f"{column}.{key}: value differs")
        for key in (
            "minimum",
            "maximum",
            "sum",
            "sum_squares",
            "position_weighted_sum",
        ):
            if not math.isclose(
                float(expected_column[key]),
                float(actual_column[key]),
                rel_tol=FLOAT_REL_TOL,
                abs_tol=FLOAT_ABS_TOL,
            ):
                problems.append(f"{column}.{key}: numeric summary differs")
        if len(problems) >= 10:
            break
    return problems


def main() -> int:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    exact_matches = 0
    canonical_matches = 0
    semantic_matches = 0
    artifact_matches = 0
    for relative, metadata in sorted(expected["files"].items()):
        path = BASE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        actual = file_sha256(path)
        if actual == metadata["sha256"]:
            exact_matches += 1
            continue

        verification = metadata.get("verification", "raw")
        if verification == "raw-canonical-or-semantic":
            try:
                canonical = canonical_result_sha256(path)
            except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
                failures.append(f"cannot parse structured result: {relative} ({exc})")
                continue
            if canonical == metadata["canonical_sha256"]:
                canonical_matches += 1
                continue
            try:
                if path.suffix == ".json":
                    actual_content = json.loads(path.read_text(encoding="utf-8"))
                    semantic_problems = compare_json_values(
                        metadata["semantic_content"],
                        actual_content,
                    )
                else:
                    actual_summary = csv_semantic_summary(path)
                    semantic_problems = compare_csv_summaries(
                        metadata["semantic_summary"],
                        actual_summary,
                    )
            except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
                failures.append(f"cannot semantically verify: {relative} ({exc})")
                continue
            if not semantic_problems:
                semantic_matches += 1
                continue
            failures.append(
                f"content mismatch: {relative} ({'; '.join(semantic_problems[:3])})"
            )
        elif verification == "pdf-artifact":
            data = path.read_bytes()
            minimum_bytes = int(metadata.get("minimum_bytes", 10_000))
            if data.startswith(b"%PDF-") and len(data) >= minimum_bytes:
                artifact_matches += 1
                continue
            failures.append(
                f"invalid PDF artifact: {relative} "
                f"(expected PDF >= {minimum_bytes} bytes, found {len(data)} bytes)"
            )
        elif verification == "png-artifact":
            data = path.read_bytes()
            minimum_bytes = int(metadata.get("minimum_bytes", 10_000))
            valid_signature = data.startswith(b"\x89PNG\r\n\x1a\n")
            dimensions = struct.unpack(">II", data[16:24]) if len(data) >= 24 else None
            expected_dimensions = (
                int(metadata["width"]),
                int(metadata["height"]),
            )
            if (
                valid_signature
                and len(data) >= minimum_bytes
                and dimensions == expected_dimensions
            ):
                artifact_matches += 1
                continue
            failures.append(
                f"invalid PNG artifact: {relative} "
                f"(expected {expected_dimensions[0]}x{expected_dimensions[1]} PNG "
                f">= {minimum_bytes} bytes, found dimensions={dimensions}, "
                f"bytes={len(data)})"
            )
        else:
            failures.append(
                f"hash mismatch: {relative} "
                f"(expected {metadata['sha256']}, found {actual})"
            )

    if failures:
        print("Generated-result verification failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "Generated-result verification passed: "
        f"{len(expected['files'])} files "
        f"({exact_matches} exact-byte, {canonical_matches} canonical-content, "
        f"{semantic_matches} strict-semantic, {artifact_matches} graphic-artifact checks)."
    )
    print("Graphic-artifact checks do not establish numerical or pixel identity; "
          "plotted numbers are checked in the companion JSON/CSV results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

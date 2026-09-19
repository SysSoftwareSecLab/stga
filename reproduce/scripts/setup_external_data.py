# /// script
# requires-python = ">=3.11"
# dependencies = ["py7zr", "requests"]
# ///
"""Download, resume, extract, and verify the pinned PatchDiff v3 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import py7zr
import requests


BASE = Path(__file__).resolve().parent.parent
EXTERNAL = BASE / "external"
TARGET = EXTERNAL / "PatchDiff"
DOWNLOAD_DIR = EXTERNAL / "downloads"
ARCHIVE = DOWNLOAD_DIR / "PatchDiff_0908.7z"
PART = ARCHIVE.with_suffix(".7z.part")
EXTRACT_DIR = EXTERNAL / "_extract_PatchDiff_0908"
EXPECTED_PATH = BASE / "data" / "expected_patchdiff_inputs.json"
DOWNLOAD_URL = (
    "https://zenodo.org/records/17074796/files/"
    "PatchDiff_0908.7z?download=1"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify() -> list[str]:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    problems: list[str] = []
    for relative, record in expected["files"].items():
        path = BASE / relative
        if not path.is_file():
            problems.append(f"missing: {relative}")
            continue
        if path.stat().st_size != record["bytes"]:
            problems.append(f"size mismatch: {relative}")
            continue
        if file_sha256(path) != record["sha256"]:
            problems.append(f"SHA-256 mismatch: {relative}")
    return problems


def download_with_resume() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.is_file():
        print(f"Using existing archive: {ARCHIVE}")
        return

    for attempt in range(1, 11):
        offset = PART.stat().st_size if PART.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(
                DOWNLOAD_URL,
                headers=headers,
                stream=True,
                timeout=(30, 120),
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    print("Server ignored resume request; restarting the download.")
                    offset = 0
                mode = "ab" if offset and response.status_code == 206 else "wb"
                remaining = int(response.headers.get("Content-Length", "0"))
                total = offset + remaining if remaining else 0
                downloaded = offset
                last_report = time.monotonic()
                with PART.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if now - last_report >= 5:
                            if total:
                                print(
                                    f"Downloaded {downloaded / 1048576:.1f}/"
                                    f"{total / 1048576:.1f} MiB"
                                )
                            else:
                                print(f"Downloaded {downloaded / 1048576:.1f} MiB")
                            last_report = now
            PART.replace(ARCHIVE)
            print(f"Download complete: {ARCHIVE}")
            return
        except (requests.RequestException, OSError) as exc:
            print(f"Download attempt {attempt}/10 failed: {exc}")
            if attempt == 10:
                print(f"Partial download retained for resume: {PART}")
                raise
            time.sleep(min(5 * attempt, 30))


def find_extracted_root() -> Path:
    candidates = []
    for result_file in EXTRACT_DIR.rglob("RQ1_OpenHands_runall.json"):
        root = result_file.parent.parent
        if (root / "data").is_dir() and (root / "results").is_dir():
            candidates.append(root)
    if len(candidates) != 1:
        raise RuntimeError(
            "Could not identify one PatchDiff root after extraction. "
            f"Candidates: {candidates}"
        )
    return candidates[0]


def archive_existing_target() -> None:
    if not TARGET.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = EXTERNAL / f"PatchDiff.invalid-{stamp}"
    TARGET.rename(backup)
    print(f"Preserved the previous external input at: {backup}")


def install(force: bool) -> None:
    current = verify()
    if not current:
        print("Pinned PatchDiff inputs are already installed and verified.")
        return
    if TARGET.exists() and not force:
        print("Existing PatchDiff input does not match the pinned v3 files:")
        for problem in current:
            print(f"  - {problem}")
        print("Rerun with --force to preserve it under an .invalid-* name and reinstall.")
        raise SystemExit(3)

    download_with_resume()
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True)
    print(f"Extracting {ARCHIVE.name} ...")
    with py7zr.SevenZipFile(ARCHIVE, mode="r") as archive:
        archive.extractall(path=EXTRACT_DIR)
    extracted_root = find_extracted_root()
    archive_existing_target()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(extracted_root), str(TARGET))
    shutil.rmtree(EXTRACT_DIR)

    problems = verify()
    if problems:
        print("Extracted files do not match the pinned PatchDiff v3 inputs:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(3)
    print("PatchDiff v3 installation and SHA-256 verification completed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Preserve a mismatched PatchDiff directory and reinstall the pinned version.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify existing inputs without downloading or extracting.",
    )
    args = parser.parse_args()
    if args.check_only:
        problems = verify()
        if problems:
            for problem in problems:
                print(problem)
            raise SystemExit(3)
        print("Pinned PatchDiff inputs are present and verified.")
        return
    install(args.force)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\nInterrupted. Partial download retained for resume: {PART}")
        sys.exit(130)

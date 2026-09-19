# r29-docs1: documentation-only edition

Date: 2026-09-04. Analysis code version: 2026-09-04-r29. Manuscript: JSS r6.

## Changes

- Added a root start page, English reproduction guide, Chinese guide, and paper-to-output map.
- Linked the guides from the existing technical README.
- Explicitly separated full reproduction, artwork-only refresh and optional Overleaf synchronization.
- Added Linux commands that preserve setup/run logs, environment information and executed-source hashes.
- Updated this edition's package manifest with documentation provenance and the later user-run acceptance evidence.

All original files except reproduce/README.md and MANIFEST.json are preserved byte-for-byte. Scripts, dependency locks, CITATION.cff author/code metadata, pinned input hashes and EXPECTED_RESULTS.json remain unchanged. The original r29 ZIP is not overwritten. The docs1 archive has its own checksum; its internal directory remains r29.

## Acceptance evidence received after the original r29 release

The user supplied a clean Linux run with setup, all 11 analysis steps and final verification. Its result archive SHA-256 is:

```text
b9bbe2b8ced8ac5935e1bf0a2b1c4999128c88a17bfe8413ea1db3e7d4fc6149
```

The inspected logs record Python 3.12.14, downloading the pinned input, verification of 12 input files, all 11 steps and 30 generated-result checks passing. All 23 structured outputs matched the reference byte-for-byte; all 119 compared JSS r6 numerical macros matched; the four panel PDFs matched manuscript artwork byte-for-byte. Two remaining graphics passed artifact checks, not byte/pixel identity claims.

This is evidence from the supplied logs and returned outputs, not independently monitored server execution or a rerun of upstream PatchDiff developer tests. No new local statistical run was performed to prepare docs1. The complete run used the original r29 code, which is unchanged in this documentation edition; it did not execute a separately changed analysis implementation.

Historical release-state paragraphs in reproduce/README.md and RESULTS_AUDIT.md describe the earlier packaging checks. They are retained as history and supplemented by this later acceptance record, not rewritten to imply that the later run existed at original packaging time.

## Distribution boundary

The docs1 ZIP still excludes generated outputs, upstream data, environments and the manuscript. Readers perform a clean setup + run_all; they do not need the author's returned result archive. Do not publish a private machine path as an artifact URL. Retain existing author metadata until the author confirms changes, and add an assigned public DOI/URL only after deposition.

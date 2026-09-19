# Reproduction guide: r29 GitHub distribution

## 1. What this package does

The package downloads the pinned PatchDiff v3 artifact, verifies its required inputs, constructs the analysis dataset, and runs all downstream statistical analyses and plots for JSS manuscript r6. It does **not** rerun upstream developer tests, generate agent patches, or independently validate behavioral labels. No GPU, model API key, Docker campaign, manual labels, or previous result bundle is required.

The clean archive intentionally has no external inputs, virtual environment, analysis_dataset.csv, or output directory. EXPECTED_RESULTS.json is verification metadata, not an instruction to copy expected results into generated files.

The original documentation archive had the ZIP name `gold_signal_replication_2026-09-04-r29-docs1.zip`. This GitHub distribution preserves the r29 executable code and numerical expectations. The r7 and r8 manuscript revisions update availability information without changing results.

## 2. Prerequisites

- An ordinary CPU machine with network access and a writable working directory.
- Linux: Bash, curl, unzip, tar and sha256sum. Ask your administrator to provide missing tools.
- Python 3.12 and uv: setup attempts to install uv if absent; uv resolves the Python/dependencies using the package configuration. Installation may require network access. Dependencies are in uv.lock; do not run `uv lock --upgrade`.
- Windows: PowerShell and an archive extraction utility; see section 5.
- Internet access to the fixed input archive and dependency distributors. Do not substitute another dataset when a download fails.

No measured minimum RAM, disk requirement, or runtime guarantee is supplied. Allow room for the input archive, extraction, Python environment and outputs; execution time depends on hardware and network. The reviewed input download was about 38.8 MiB, which is not the total installed footprint. Bootstrap and sensitivity steps can take time without frequent console updates.

## 3. Recommended clean Linux run from GitHub

Git is required in addition to the tools above. From a writable directory, copy the complete block into a terminal. The clone command stops if Stress-Testing already exists; use a fresh working directory for a new full run.

```bash
bash <<'BASH'
set -euo pipefail
git clone https://github.com/Sunuywq/Stress-Testing.git
cd Stress-Testing
# To reproduce an exact paper version, check out its cited commit here.
git rev-parse HEAD > source_commit_r29.txt
cd reproduce
export UV_LINK_MODE=copy
sh setup.sh 2>&1 | tee setup_r29_full.log
bash run_all.sh 2>&1 | tee reproduction_r29_full.log
{
  uv --version
  uv run python --version
  uv pip freeze
} > environment_r29.txt
sha256sum ../MANIFEST.json .python-version CITATION.cff uv.lock pyproject.toml \
  requirements.txt EXPECTED_RESULTS.json data/expected_patchdiff_inputs.json \
  setup.sh run_all.sh scripts/*.py > executed_files_r29.sha256
tar -czf ../jss_r29_full_results.tar.gz \
  analysis_dataset.csv output setup_r29_full.log reproduction_r29_full.log \
  environment_r29.txt executed_files_r29.sha256
printf 'Results: %s\n' "$(cd .. && pwd)/jss_r29_full_results.tar.gz"
BASH
```

Preserve source_commit_r29.txt alongside the result bundle. All plots and the final verifier are already part of run_all. To match a cited version, execute `git checkout FULL_COMMIT_SHA` before setup, replacing FULL_COMMIT_SHA with the 40-character commit in the paper's link.

## 3b. Alternative for users who already have the original ZIP

Place the documentation-edition ZIP and its matching .zip.sha256 sidecar in the same directory. Open a terminal in that directory. Copy the entire block:

```bash
bash <<'BASH'
set -euo pipefail
sha256sum -c gold_signal_replication_2026-09-04-r29-docs1.zip.sha256

# Fails safely if this directory already exists; choose a new name in that case.
mkdir r29_clean_run
unzip -q gold_signal_replication_2026-09-04-r29-docs1.zip -d r29_clean_run
cd r29_clean_run/gold_signal_replication_2026-09-04-r29/reproduce
export UV_LINK_MODE=copy

# Input download, extraction and input hash checks.
sh setup.sh 2>&1 | tee setup_r29_full.log
# All 11 steps, including plots and the final result verification.
bash run_all.sh 2>&1 | tee reproduction_r29_full.log

# Record useful environment and executed-source evidence, without credentials.
{
  uv --version
  uv run python --version
  uv pip freeze
} > environment_r29.txt
sha256sum ../MANIFEST.json .python-version CITATION.cff uv.lock pyproject.toml \
  requirements.txt EXPECTED_RESULTS.json data/expected_patchdiff_inputs.json \
  setup.sh run_all.sh scripts/*.py > executed_files_r29.sha256

# Created only if all preceding commands succeeded.
tar -czf ../jss_r29_full_results.tar.gz \
  analysis_dataset.csv output setup_r29_full.log reproduction_r29_full.log \
  environment_r29.txt executed_files_r29.sha256
printf 'Results bundle: %s\n' "$(cd .. && pwd)/jss_r29_full_results.tar.gz"
BASH
```

Keep the logs and original ZIP sidecar. Source/environment hashes improve traceability; they do not constitute independent monitoring of execution. Review logs for personal paths before publicly uploading them.

If using the original r29 ZIP, use its original name and matching sidecar in the first commands. The rest of the workflow is identical. Never mix a docs1 ZIP with the original ZIP's checksum.

## 4. How to recognize success

Both commands must finish successfully. The full-run log should contain:

1. PatchDiff input verification passed for **12 files** from record **17074796 (v3)**.
2. Steps **1/11 through 11/11**, followed by Postflight.
3. `Generated-result verification passed: 30 files (...)`.
4. The final `Done` message.

The 30 files comprise 23 CSV/JSON files (including analysis_dataset.csv), six PDFs and one PNG. All four `*_panel_*.pdf` files must exist. The exact counts inside the verification categories may differ across platforms. The reviewed Linux run had 28 exact-byte matches and two graphic-artifact checks; do not require that exact category split.

Exact-byte matches are strongest byte-level agreement; canonical/strict-semantic checks allow documented serialization or insignificant floating-point differences. Graphic-artifact checks validate file structure/size, not pixel identity: check companion numerical outputs and inspect plots.

Expected checkpoints: 877 total resolved records; primary cohort 841 = 68 failures + 773 comparison records; 36 coding-convention-only records outside the binary cohort; primary-cohort issues 366. See [RESULTS_MAP.md](RESULTS_MAP.md) for paper correspondence.

Do not use `--skip-result-verification` in normal reproduction. Do not modify EXPECTED_RESULTS.json or run freeze_expected_results.py to make a failed run pass.

## 5. Windows alternative

Clone the GitHub repository to a fresh short path and enter its reproduce directory, or extract an existing original ZIP and enter `gold_signal_replication_2026-09-04-r29\reproduce`. For a clone, first use `git clone https://github.com/Sunuywq/Stress-Testing.git`, then `cd Stress-Testing\reproduce`. In PowerShell:

```powershell
$env:UV_LINK_MODE = "copy"
.\setup.ps1
.\run_all.ps1
```

Run the second command only after setup reports success. If execution policy or organizational controls block scripts, follow local policy or use an approved Linux environment; do not disable machine-wide security settings. Reopen PowerShell if newly installed uv is not yet on PATH.

For a pre-extraction checksum, compare the result of `Get-FileHash -Algorithm SHA256 <ZIP path>` with the matching .zip.sha256 file. Windows uses the same dataset, scripts and expected results, but this guide's recorded end-to-end acceptance run was on Linux.

## 6. Three different workflows: do not confuse them

| Workflow | Purpose | Required for a first run? |
|---|---|---|
| setup + run_all | Download pinned inputs and recompute the complete downstream analysis | Yes |
| Artwork-only refresh | Re-export plots from an already verified dataset and statistical outputs | No |
| sync_jss_artwork.py | Copy four generated PDFs into a separately distributed Overleaf directory | No |

The r27-to-r29 migration during development reused verified numerical outputs and re-exported artwork. That historical shortcut is **not** the reproduction procedure for readers. A later clean r29 Linux run completed all 11 steps and was checked against JSS r6.

For maintainers only, from reproduce/, with compatible, verified analysis_dataset.csv and output/ already present:

```bash
uv run python scripts/fig2_repository_transport.py
uv run python scripts/fig2_volume_distribution.py
uv run python scripts/verify_results.py
```

The second plot script also recomputes the exploratory tail/Fisher/Holm results. These commands alone are not an end-to-end statistical rerun.

Optional Overleaf synchronization (replace the placeholder with an actual extracted JSS r6 source path):

```bash
uv run python scripts/sync_jss_artwork.py --results-dir output --paper-dir /path/to/JSS_submission_source_20260904_r6
```

This copies four PDFs; it does not update manuscript prose, tables, macros or references. Figure 1 is editable LaTeX in JSS.tex, not a missing exported PDF.

## 7. Troubleshooting

| Symptom | Action |
|---|---|
| Missing old r27 directory / analysis_dataset.csv | Do not copy old files for first-time reproduction; run clean setup + run_all. |
| Only 26 files pass | Check which version/directory is being executed; r29 expects 30. Do not rename r27 to pretend it is r29. |
| Existing r29_clean_run directory | Choose a different fresh extraction directory; do not overwrite old evidence. |
| Failed hardlink / falling back to copy | Usually harmless; UV_LINK_MODE=copy avoids the warning. |
| Partial download | Rerun setup; it supports resuming. |
| uv missing after setup | Reopen the shell, then retry setup. |
| Input or result hash mismatch | Preserve logs; confirm the code version, locks and input version. Report the mismatch, do not replace the verification baseline. |
| Interrupted analysis | Preserve the interrupted log; rerunning run_all recomputes analyses and can replace outputs. Use a fresh extraction for an unambiguous new full run. |
| Permission denied on run_all.sh | Use bash run_all.sh; setup uses sh setup.sh. |
| ZIP cannot be displayed in a text editor | Normal: extract the binary archive. |
| Missing PDF viewer / LaTeX | Neither is needed for numerical computation. Use a PDF viewer to inspect generated figures; manuscript compilation is separate. |

When seeking help, include the full error, ZIP version/checksum, command, Python/uv versions, logs and result bundle if available. Do not share API keys or unrelated private files.

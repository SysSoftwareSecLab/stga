# Stress-Testing Gold-Aware and Gold-Free Failure Signals

Replication code for **Stress-Testing Gold-Aware and Gold-Free Failure Signals in Resolved SWE-bench Verified Patches**.

This repository contains the verified **r29** downstream analysis of the version-pinned [PatchDiff artifact](https://doi.org/10.5281/zenodo.17074796). The study evaluates gold-aware patch-volume and file-scope audit signals, gold-free review prioritization, and variation across archived agent configurations. The source code, dependency locks, input hashes and expected results are unchanged from the reviewed r29 documentation archive; GitHub packaging and documentation have been updated.

## Quick start

Run these commands in Bash from a writable directory. Git, curl and network access are required; setup installs uv if needed and retrieves the pinned inputs.

```bash
git clone https://github.com/xxx.git
cd /reproduce
export UV_LINK_MODE=copy
sh setup.sh
bash run_all.sh
```

Run the analysis only after setup succeeds. **setup + run_all includes every analysis, plot and verification step.** A successful run completes 11 steps and reports verification passed for **30 files**. No additional plotting command or previous result archive is required.

For a recorded run with error handling and log export, follow the [reproduction guide](REPRODUCTION_GUIDE.md).

## Documentation

- [Reproduction guide](REPRODUCTION_GUIDE.md): requirements, clean Linux run, Windows alternative, success criteria and troubleshooting.
- [Paper-to-output map](RESULTS_MAP.md): where each reported table, figure and result comes from.
- [Technical README](reproduce/README.md): cohort definitions and analysis workflow.
- [Verification and documentation history](DOCUMENTATION_CHANGELOG.md).
- [GitHub publication notes](PUBLICATION_NOTES.md): provenance and package integrity.

## Reproduction boundary

This package reproduces the manuscript's downstream secondary analysis. It downloads and verifies archived PatchDiff RQ1 results; it does **not** rerun the upstream developer-test campaign or generate new agent patches. No GPU, API key, Docker execution or manual labeling is required.

The primary binary cohort contains 841 resolved agent-instance patches: 68 developer-test functional failures and 773 with no observed developer-test failure. The latter is a comparison label, not a claim of semantic correctness. Another 36 coding-convention-only records are excluded from this binary comparison; the full resolved dataset contains 877 records.

The reviewed clean Linux r29 run completed all 11 steps. All 23 structured CSV/JSON outputs matched the reference byte-for-byte; 30 total outputs passed verification. Four independent panel PDFs matched the manuscript artwork byte-for-byte. Graphic-artifact checks do not by themselves establish pixel identity.

## Repository contents

The public source contains scripts, pinned input hashes, locked dependencies and expected-result verification metadata. Upstream data, generated outputs, environments and the manuscript are separate. `setup.sh` retrieves inputs; `run_all.sh` creates `analysis_dataset.csv` and `output/`.

For the exact version used in a paper, use its commit-specific link and record `git rev-parse HEAD`. The default branch may receive later documentation changes. No archival DOI is claimed for this repository.

## License and citation

The downstream code is distributed under the [MIT License](LICENSE). The separately downloaded PatchDiff artifact remains subject to its upstream terms. Citation metadata are in [CITATION.cff](CITATION.cff); cite the upstream data artifact as well when using its data.

Please report reproducibility problems through [GitHub Issues](https://github.com/Sunuywq/Stress-Testing/issues), including the commit, command, environment and relevant error log. Do not post credentials or unrelated private files.

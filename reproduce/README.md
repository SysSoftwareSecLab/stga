# Replication Package: Gold-Aware and Gold-Free Failure Signals

> **First-time users:** start with the [reproduction guide](../REPRODUCTION_GUIDE.md), then use the [paper-to-output map](../RESULTS_MAP.md).
> This is the GitHub distribution of the reviewed r29-docs1 analysis baseline. Code remains r29 and is unchanged.
> A later user-supplied clean Linux run completed all 11 steps and passed 30 output checks; see [documentation and acceptance history](../DOCUMENTATION_CHANGELOG.md).
> **setup + run_all already includes plotting and verification. No extra plotting step or old result bundle is required.**

This package reproduces the quantitative analyses for the associated manuscript
"Stress-Testing Gold-Aware and Gold-Free Failure Signals in Resolved SWE-bench
Verified Patches."

> **Release state (September 4, 2026; r29):** this release preserves the
> independently reviewed r25 Linux numerical baseline and the r27 figure
> corrections and r28 independent artwork. It emits each panel of Figures 2 and 3 as an
> independent vector PDF for accessible journal submission while retaining the
> combined figures for backward compatibility. No statistical method, input,
> numerical result, or expected structured output changed. The clean public
> archive intentionally excludes generated outputs and upstream data; an
> ordinary one-command run must regenerate and verify all 30 files.

This packaging revision was checked by regenerating artwork from frozen results
and by manifest verification, not by a fresh end-to-end statistical run. The
verifier reports exact-byte, canonical-content, strict-semantic and
graphic-artifact checks separately. A graphic-artifact pass is not a claim of
pixel identity or a substitute for checking the companion numerical outputs.

### Alignment with JSS r6

The only change to executable analysis/plotting code since r28 is the label
of Figure 2(b): `Review workload (% of all patches)`. Selection still occurs
separately within each repository; the plotted workload is the selected count
divided by all 841 primary-cohort patches. The manuscript and its standalone
figure-caption file now make that distinction explicit. Models, selection
rules, inputs, random seeds, and numerical expectations are unchanged.

JSS r6 also clarifies interpretation without changing estimates: the archived
LearnByInteract `model_name_or_path` value `openhands` is reported as metadata,
not proof of framework architecture; a non-significant OpenHands/LearnByInteract
comparison does not establish equivalence; the static model's pooled AUC point
estimate 0.411 is below 0.5 but its 95% interval [0.315, 0.549] includes 0.5.
The ratio reparameterization is algebraically equivalent after developer-volume
adjustment. The single seaborn observation retains its defined median 2.44.

The study is a secondary analysis of the version-pinned RQ1 outputs released
with Wang et al.'s ICSE 2026 PatchDiff artifact. It separates two use cases:

1. gold-aware benchmark auditing with agent/developer volume and file-scope
   alignment; and
2. gold-free review prioritization with agent-diff size/structure features and
   a fixed 25-feature lexical/path model.

No manual coding, blind-review worksheet, annotation packet, API key, GPU, or
Docker execution is required by this package.

## Reproduction Boundary

The package reproduces the downstream statistical analysis. It does not rerun
the upstream Docker campaign that executed available developer tests. Instead,
it verifies hashes, identifiers, resolved-list membership, required label
fields, failing-test lists, and the explicit empty patch before consuming the
published RQ1 run-all result files. This is a provenance/integrity audit, not an
independent behavioral validation of the labels.

The analysis does not use Wang et al.'s RQ2 suspicious-patch labels or generated
differentiating tests.

## Data Source

External input:

- PatchDiff replication artifact:
  https://doi.org/10.5281/zenodo.17074796

Required result files:

- `RQ1_OpenHands_runall.json`
- `RQ1_CodeStory_runall.json`
- `RQ1_LearnByInteract_runall.json`

The setup script downloads the archived artifact and verifies the files against
`data/expected_patchdiff_inputs.json`.

Expected layout after setup:

```text
reproduce/
  data/
    expected_patchdiff_inputs.json
  external/
    PatchDiff/
      data/
        dataset/swebench_verified/
        tool_results/
      results/
        RQ1_OpenHands_runall.json
        RQ1_CodeStory_runall.json
        RQ1_LearnByInteract_runall.json
  scripts/
  output/                 created by run_all
```

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- PowerShell on Windows or a POSIX shell on Linux/macOS

The `.python-version` file pins the Python minor release. Dependencies are
locked in `uv.lock`. `requirements.txt` is provided for users who cannot use
uv; it also includes `py7zr`, which is required by the external-data setup
utility.

## Setup

Windows:

```powershell
.\setup.ps1
```

Linux/macOS:

```bash
sh setup.sh
```

To verify an existing external-data installation without downloading:

```powershell
.\setup.ps1 -CheckOnly
```

```bash
sh setup.sh --check-only
```

The setup is resumable. If an interrupted Zenodo download leaves a partial
file, rerun the same command.

## One-Command Reproduction

Windows:

```powershell
.\run_all.ps1
```

Linux/macOS:

```bash
bash run_all.sh
```

Use the explicit shell commands above even if the archived scripts print
`./setup.sh` or `./run_all.sh` as a hint: browser uploads and ZIP extraction may
not preserve executable permissions. No `chmod` step is needed when invoking
`sh setup.sh` and `bash run_all.sh`.

The runner verifies the external inputs, performs eleven automated steps, and
then compares every reported output with the release-time verification
manifest. JSON and CSV outputs accept either an exact byte hash or a
cross-platform canonical-content hash; a schema-preserving comparison with
strict numerical tolerances handles insignificant platform-level floating
point differences. The generated PDFs and PNG are checked as nontrivial
artifacts because their numerical content is independently verified in the
companion JSON/CSV results.

For a deliberate analysis-code revision that changes the result schema,
maintainers may run `.\run_all.ps1 -SkipResultVerification` on Windows or
`bash run_all.sh --skip-result-verification` on Linux/macOS. This option is only
for producing candidate outputs from revised code. Refresh and independently
check `EXPECTED_RESULTS.json` before publishing; ordinary users should not use
the skip option.

## Automated Workflow

1. `build_analysis_dataset.py`
   builds the canonical three-state cohort, retains the explicit empty patch as
   zero volume, computes alternate volume slices, and writes the input manifest.
2. `audit_upstream_labels.py`
   audits input provenance and structural label integrity without claiming to
   rerun the upstream test environments.
3. `run_mixed_effects.py`
   fits the repository-adjusted issue-clustered GEE, parameterization and
   volume-definition sensitivities, per-repository diagnostics, practical
   review budgets, and leave-one-repository-out models.
4. `run_static_diff_baseline.py`
   extracts 25 fixed lexical/path features and evaluates one L2 logistic model
   with leave-one-repository-out prediction.
5. `run_structural_alignment.py`
   computes objective file-set measures, 68 matched failure/control pairs,
   balance diagnostics, repository-adjusted GEEs, matching variations, and
   leave-one-repository-out design checks.
6. `run_within_issue_sensitivity.py`
   analyzes the 25 issues containing both failure states, giving each issue
   equal weight.
7. `run_paired_sensitivity.py`
   computes exact minimum-detectable directional odds ratios for the four
   within-issue file-scope contrasts.
8. `run_rq3_kruskal.py` (legacy filename; this is the RQ4 analysis)
   compares patch-volume distributions on 203 issue-matched configuration
   triples, quantifies complete-case selection, and runs a repository-adjusted
   all-cohort GEE sensitivity analysis.
9. `fig2_repository_transport.py`
   regenerates the per-repository transport and review-budget figure as both a
   combined artifact and two independent vector-panel PDFs.
10. `fig2_volume_distribution.py`
   computes the exploratory patch-volume tail analysis and regenerates its
   distribution figure as both a combined artifact and two independent
   vector-panel PDFs.
11. `deep_dive_24443.py`
   reconstructs the objective motivating-example record from pinned inputs.

The command creates JSON, CSV, six PDFs, and one auxiliary 240-dpi PNG in
`output/`. It does not create LaTeX files or manuscript source. The four
`*_panel_*.pdf` files are the submission-facing artwork; the two combined PDFs
are retained for backward compatibility and side-by-side review.

## Cohort Definition

The pipeline begins with 877 officially resolved agent-instance patches:

| Stage | N |
|---|---:|
| Officially resolved records | 877 |
| Explicit empty packaged agent patches retained as zero volume | 1 |
| Primary binary cohort | 841 |
| Developer-test functional failures | 68 |
| No observed developer-test failure | 773 |
| Coding-convention-only outcomes excluded from the primary comparison | 36 |

One CodeStory record, `django__django-12708`, is a functional-failure record
with an explicitly present empty packaged patch. It is not missing or corrupt.
The pipeline retains it with agent volume zero and computes the smoothed ratio
as `1 / (gold_volume + 1)`.

"No observed developer-test failure" is deliberately not called "correct." The
available developer tests remain an incomplete behavioral oracle.

## Main Expected Results

| Result | Expected value |
|---|---:|
| Primary cohort | 841 |
| Median rho, IQR | 5.8 [2.5, 12.4] |
| Failure tail below rho=0.5 | 8/68, 11.8% |
| Comparison tail below rho=0.5 | 10/773, 1.3% |
| Tail Fisher OR | 10.17 |
| Primary GEE agent-volume beta / p-value | 0.079 / 0.506 |
| Primary GEE developer-volume beta / p-value | 0.348 / 0.085 |
| Spline joint p-value | 0.323 |
| Source-only agent-volume raw / Holm p-value | 0.040 / 0.198 |
| LORO pooled / macro AUC for files+hunks | 0.525 / 0.702 |
| Files+hunks failures captured at 10.7% workload | 15/68 (22.1%) |
| Static 25-feature pooled / macro AUC | 0.411 / 0.501 |
| Developer-only files, matched failure/control nonzero | 18 / 5 |
| Developer-only files, all-cohort GEE OR | 8.22 |
| Mixed-outcome issues | 25 |
| RQ4 resolved patches / complete triples | 877 / 203 |
| RQ4 Friedman Q / p-value | 27.59 / 1.02e-6 |

The direct-volume GEE is the primary inferential model. The study was not
preregistered; threshold, alternate-definition, predictive, file-scope,
within-issue, and configuration analyses are exploratory or sensitivity
analyses. The exact design-sensitivity calculation is not post-hoc observed
power and does not establish equivalence.

Developer test-only volume is identically zero in the locked cohort because
the developer repair and benchmark test patch are separate artifacts. The
revised workflow therefore omits that constant developer covariate from the
test-only sensitivity and records it as not estimable, rather than emitting a
zero coefficient with a `NaN` p-value.

## Generated Outputs

The clean archive initially contains no `output/` directory. A successful run
creates:

```text
analysis_dataset.csv
output/
  cohort_exclusions.csv
  fig2_repository_transport.pdf
  fig2_repository_transport.png
  fig2_repository_transport_panel_a.pdf
  fig2_repository_transport_panel_b.pdf
  fig2_repository_transport_data.csv
  fig2_volume_distribution.pdf
  fig2_volume_distribution_panel_a.pdf
  fig2_volume_distribution_panel_b.pdf
  input_manifest.json
  motivating_example_24443.json
  paired_design_sensitivity.json
  rq1_continuous_models.json
  rq1_loro_fold_metrics.json
  rq1_results.json
  rq3_results.json
  rq3_complete_case_selection.csv
  static_diff_loro_baseline.json
  static_diff_loro_predictions.csv
  repository_profile.csv
  repository_tool_profile.csv
  structural_alignment_balance.csv
  structural_alignment_loro_sensitivity.csv
  structural_alignment_matched_pairs.csv
  structural_alignment_matching_sensitivity.csv
  structural_alignment_results.json
  structural_alignment_within_issue_contrasts.csv
  structural_alignment_within_issue_sensitivity.json
  upstream_label_provenance_audit.json
```

`EXPECTED_RESULTS.json` contains release-time exact and portable verification
metadata for these generated files. `verify_results.py` fails if a required
file is missing or its structured content differs from the frozen result.
Exact hashes remain available for byte-identical reproduction.

`scripts/freeze_expected_results.py` is a maintainer-only release utility. It
requires an explicit confirmation token and snapshots already reviewed
results; it is not called by `run_all` and must never be used to make an
unreviewed candidate run appear verified. Release-time checks are summarized
in `RESULTS_AUDIT.md`.

## Manuscript Separation

The public replication package contains analysis code only. Manuscript source,
journal template files, generated LaTeX tables, and the Overleaf upload ZIP
are maintained separately.

The independent panel PDFs generated by steps 9 and 10 map to JSS source files:

| Generated file under `output/` | JSS artwork file |
|---|---|
| `fig2_repository_transport_panel_a.pdf` | `Figure_2a.pdf` |
| `fig2_repository_transport_panel_b.pdf` | `Figure_2b.pdf` |
| `fig2_volume_distribution_panel_a.pdf` | `Figure_3a.pdf` |
| `fig2_volume_distribution_panel_b.pdf` | `Figure_3b.pdf` |

After completing reproduction, optionally synchronize these four files into an
extracted JSS r6 Overleaf source directory (the helper requires an existing
`JSS.tex` that references all four files):

```bash
python scripts/sync_jss_artwork.py --results-dir output --paper-dir /path/to/JSS_submission_source_20260904_r6
```

The helper validates all four source PDFs and the LaTeX references before
copying, and checks the copied hashes. It does not edit manuscript text,
tables, numerical macros, or the bibliography, and is not part of `run_all.sh`.

LaTeX places the separate artwork files side by side and retains Figures 2 and
3 and their (a)/(b) captions. The combined PDFs and PNG remain available for
backward-compatible inspection; they are not the submission artwork. Figure 1
is editable LaTeX text in `JSS.tex` and is not a missing generated PDF.

Do not run legacy EMSE/ESWA manuscript builders to update the JSS source. The
JSS-specific synchronization helper in the development checkout copies these
four PDFs only; it does not modify research numbers, tables, or other venues.

## License and Citation

The analysis code is released under the MIT License. The separately downloaded
PatchDiff artifact is not redistributed and remains subject to its upstream
terms. Author and release metadata are provided in `CITATION.cff`. After this
exact archive receives a public repository URL or DOI, cite that persistent
release from the manuscript; no downstream DOI is claimed inside this archive.

## Troubleshooting

| Problem | Resolution |
|---|---|
| `uv` is not recognized | Run `setup.ps1` or `setup.sh`; reopen the terminal if PATH changed. |
| PatchDiff is missing | Rerun the setup command. |
| Zenodo download stops | Rerun setup; the partial download is resumed. |
| Input SHA-256 mismatch | Run setup with `-Force` or `--force` to reinstall the pinned archive. |
| Windows path is too long | Extract the release near a drive root, such as `D:\gold-repro`. |
| Result verification fails | Confirm Python/dependency versions and external-input hashes before comparing analysis code. |

## Release Checklist

Before depositing this package:

1. run setup input verification;
2. run the one-command reproduction in a clean extraction;
3. confirm generated-result verification passes for all 30 files;
4. deposit the exact ZIP and its sidecar manifest in a public repository;
5. add the assigned persistent URL or DOI to the manuscript's data-availability
   statement and software reference before submission.

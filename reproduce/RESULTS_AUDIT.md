# Release-time results audit

Release: `2026-09-04-r29`

The inherited r28 code change is restricted to figure packaging and explicit reporting
of verification modes (without changing acceptance rules). It preserves the r27
presentation corrections and additionally generates independent vector PDFs
for panels (a) and (b) of Figures 2 and 3. The expected numerical results remain
the reviewed r25 Linux baseline described below; neither r28 nor r29 claims a new
statistical rerun.

The r29 executable-code change is limited to the Figure 2(b) x-axis label.
Repository-stratified selection, the all-primary-patches workload denominator,
all numerical analysis, and verification acceptance rules are unchanged.
Corresponding JSS r6 prose distinguishes metadata from architecture and
non-detection from equivalence, and explicitly notes that the pooled-AUC
interval includes 0.5. No experimental value is revised.

The release baseline was rebuilt from a Linux run supplied after the post-r24
code repairs. The submitted results archive had SHA-256:

```text
ce811cd2e5e9463991e56527dfe7b4b2c8903b5220452bb7a86079d4518f8093
```

## Historical Linux workflow checks (r25 baseline, not a new r28/r29 run)

- The runner verified 12 pinned PatchDiff v3 inputs from Zenodo record
  `17074796` before analysis.
- All 11 downstream analysis and figure-generation steps completed.
- The r25 Linux run regenerated `analysis_dataset.csv` plus 25 files under
  `output/`; the r28 plotting code adds four submission-facing panel PDFs.
- A complete r28 or r29 run regenerates and verifies 30 files against
  `EXPECTED_RESULTS.json`; verification is exact-byte, canonical-content, or
  strict semantic/artifact validation as appropriate to each file type. This
  describes the expected complete workflow, not a new r28/r29 end-to-end run.
- The test-only sensitivity is valid JSON: the constant developer test-volume
  term is `null` and explicitly marked not estimable.
- The cohort manifest records zero `no_gold` and zero `zero_gold_volume`
  exclusions for the pinned cohort.
- Exact tool/repository matching balance was recomputed from separate failure
  and control rows; both post-match maximum proportion differences are zero.

## Claim--evidence spot checks

| Item | Reviewed result |
|---|---:|
| Resolved records / primary binary cohort | 877 / 841 |
| Functional failures / comparison rows | 68 / 773 |
| Primary GEE agent-volume beta / p | 0.079 / 0.506 |
| Primary GEE developer-volume beta / p | 0.348 / 0.085 |
| Spline joint p | 0.323 |
| Files+hunks failures captured at 10.7% workload | 15/68 (22.1%) |
| Static 25-feature pooled AUC, 95% CI | 0.411 [0.315, 0.549] |
| Developer-only-file GEE OR, Holm p | 8.22 / 0.0063 |
| RQ4 complete triples; Friedman Q / p | 203; 27.59 / 1.02e-6 |

## r28 packaging-only validation (September 4, 2026)

- Replayed the two plotting scripts against frozen reviewed outputs; did not
  execute the model-fitting, bootstrap, or full reproduction workflow.
- Preserved all 26 r27 expectation entries verbatim, including all 23
  structured numerical expectations; added only four PDF-artifact entries.
- The resulting 30-file verification passed: 25 exact-byte matches, two
  canonical-content matches, zero strict-semantic fallbacks, and three
  graphic-artifact checks. These counts describe this check, not a guarantee
  that another platform will use the same verification modes.
- Confirmed all four independent panels contain selectable text and embedded
  non-Type-3 fonts. Their copied JSS files have identical SHA-256 hashes.
- Regression fixtures confirmed that meaningful numerical changes, an invalid
  required PDF, and missing required output are rejected. A graphic-artifact
  check does not establish pixel identity or numerical accuracy by itself.
- Statistical analysis scripts, dependency locks, upstream input expectations,
  and the numerical computation in the volume plotting script are unchanged.

## r29 prose/label alignment validation (September 4, 2026)

- Replayed only `fig2_repository_transport.py` against copied frozen outputs.
  The executable difference from r28 is exactly the x-axis label and its
  explanatory comment; no fitting, bootstrap, selection, or loader changed.
- All 23 JSON/CSV outputs remained byte-identical to the frozen acceptance
  copy, and their expected verification entries were preserved verbatim.
- Updated only the combined Figure 2 PDF/PNG and panel (b) graphic hash/size
  records. The other 27 expected-output entries were preserved.
- Thirty-file verification passed: 27 exact-byte matches, two canonical-content
  matches, zero strict-semantic fallbacks, and one graphic-artifact check.
  Graphic hashes updated after an intentional label revision are not fresh
  independent evidence of statistical reproduction.
- Rechecked the pinned LearnByInteract prediction and result hashes: all 500
  prediction records, including the 301 resolved records, have the archived
  `model_name_or_path` value `openhands`. This is metadata evidence, not proof
  of framework architecture or inheritance.
- JSS r6 retains every result macro, numerical table, equation, and bibliography
  entry. Table 1 changes only the description of archived metadata. Author,
  funding, competing-interest, and acknowledgement information is unchanged.
- The manuscript compiled with no warnings; revised tables, figure captions,
  axis label, and interpretation passages were visually inspected. This is
  not a new full Linux/end-to-end statistical run.

## Validation boundary

This package performs a secondary analysis of published PatchDiff labels. It
checks the upstream artifact's hashes and label provenance but does **not**
rerun the upstream Docker-based developer-test campaign. Therefore this audit
establishes downstream computational reproducibility, not independent
behavioral revalidation of the inherited outcome labels.

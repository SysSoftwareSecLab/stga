# SIGSOFT Empirical Standards Self-Assessment

Assessment date: 2026-08-31

This document records a conservative self-assessment against the ACM SIGSOFT
Empirical Standards. It is an audit aid, not a claim of certification.

Official sources:

- https://www2.sigsoft.org/EmpiricalStandards/docs/standards
- https://www2.sigsoft.org/EmpiricalStandards/docs/supplements

## Applicable Standards

The closest method standards are General, Repository Mining, Data Science, and
Sampling. The Secondary Data Ethics and Open Science supplements also apply.
The reported study contains no manual annotation or qualitative inference.

## Assessment

| Area | Status | Evidence or remaining limitation |
|---|---|---|
| Research problem and contribution | Met | The manuscript distinguishes Wang et al.'s existence result from this study's diagnostic question and staged validation protocol. |
| Units, source, and acquisition | Met | Agent-instance patches, issue clustering, three RQ1 files, cohort flow, exclusions, and SHA-256 hashes are documented. |
| Inclusion and preprocessing | Met | The 877 resolved patches, including the verified zero-length CodeStory diff, form the executable source cohort. The 841-record binary outcome cohort contains 68 functional failures and 773 patches with no observed developer-test failure; 36 coding-convention-only records are retained for sensitivity analysis but excluded from the binary endpoint. |
| Measures and construct validity | Met with limitations | Patch volume, file alignment, and fixed lexical/path features are defined. The manuscript rejects semantic-correctness interpretations of syntactic measures. |
| Quantitative sensitivity | Met | Confidence intervals, alternate patch-volume definitions, repository fixed effects on the 794 rows from eight two-class repositories, an all-row no-repository sensitivity, matching variations, leave-one-repository-out checks, within-issue contrasts, and exact minimum-detectable-effect calculations are reported. |
| Predictive validation | Met | Per-repository and pooled leave-one-repository-out ROC-AUC, average precision, Brier score, uncertainty intervals, prevalence baselines, and fixed review-budget recall are reported. Single-class test repositories are identified rather than assigned undefined ROC-AUC values. |
| Multiple testing | Met | The directly parameterized RQ1 GEE is designated as the primary analysis, not as preregistered confirmation. Other threshold, feature, matching, and portability analyses are exploratory or sensitivity analyses with within-family Holm adjustment where applicable. |
| Sampling and representativeness | Met with limitations | Cohort construction is explicit. Claims remain limited to resolved SWE-bench Verified Python patches from three systems reported to use the Claude 3.5 Sonnet model family; exact inference configurations were not controlled by this secondary study. |
| Secondary-data ethics | Met with a release check | The study reuses public research artifacts and analyzes code patches rather than private human-subject data. The upstream license must be rechecked before final deposit. |
| Open science | Pending final deposit | One-command scripts, locked dependencies, input hashes, expected-result hashes, a clean package, and an MIT license are prepared. The final archive still needs its own immutable public URL or DOI. |

## Consequences for Claims

1. A nonsignificant test is reported as "not detected," not "no effect."
2. Sparse within-issue contrasts do not establish equivalence.
3. RQ4 is a same-model-family descriptive-signal portability check, not a
   causal or model-independent scaffold comparison.
4. The static model bounds only the reported low-cost feature set; it does not
   establish that richer APCA systems fail.

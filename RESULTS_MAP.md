# Paper-to-output map

Paths below are relative to `reproduce/`. Table and figure numbering follows JSS manuscript r6 and its r7/r8 availability-statement revisions. Those revisions preserve the numerical results and artwork. The package generates data and figures, not the complete LaTeX manuscript or its table source.

| Paper item | Producer in scripts/ | Output evidence |
|---|---|---|
| Experimental Design: cohort | build_analysis_dataset.py; audit_upstream_labels.py | analysis_dataset.csv; output/input_manifest.json; output/upstream_label_provenance_audit.json |
| Table 1: configuration provenance | Archived input metadata, not an automatically generated table | external/PatchDiff/data/tool_results/; data/expected_patchdiff_inputs.json; archived predictions/results. The model_name_or_path field does not establish framework architecture. |
| Table 2: repository composition | run_mixed_effects.py | output/repository_profile.csv; output/repository_tool_profile.csv |
| Table 3: volume models | run_mixed_effects.py | output/rq1_continuous_models.json |
| Table 4: file-alignment contrasts | run_structural_alignment.py | output/structural_alignment_results.json; output/structural_alignment_matched_pairs.csv |
| Table 5: matching-design sensitivity | run_structural_alignment.py | output/structural_alignment_matching_sensitivity.csv; output/structural_alignment_balance.csv |
| Table 6: within-issue contrasts | run_within_issue_sensitivity.py | output/structural_alignment_within_issue_sensitivity.json; output/structural_alignment_within_issue_contrasts.csv |
| Table 7: minimum detectable effects | run_paired_sensitivity.py | output/paired_design_sensitivity.json |
| Table 8: paired configuration comparisons | run_rq3_kruskal.py (legacy filename; implements RQ4) | output/rq3_results.json; output/rq3_complete_case_selection.csv |
| Figure 1: motivating example | deep_dive_24443.py | output/motivating_example_24443.json; layout and code excerpts are LaTeX in JSS.tex, not an exported PDF |
| Figure 2(a): repository AUC | run_mixed_effects.py; run_static_diff_baseline.py; fig2_repository_transport.py | output/rq1_loro_fold_metrics.json; output/static_diff_loro_baseline.json; output/fig2_repository_transport_data.csv |
| Figure 2(b): review budgets | run_mixed_effects.py; run_static_diff_baseline.py; fig2_repository_transport.py | output/rq1_continuous_models.json; output/static_diff_loro_baseline.json |
| Figure 3(a): volume eCDF | build_analysis_dataset.py; fig2_volume_distribution.py | analysis_dataset.csv, filtered to the primary binary cohort |
| Figure 3(b): exploratory tail | fig2_volume_distribution.py | output/rq1_results.json |
| RQ3 static-model predictions | run_static_diff_baseline.py | output/static_diff_loro_predictions.csv; output/static_diff_loro_baseline.json |
| RQ2 leave-one-repository sensitivity | run_structural_alignment.py | output/structural_alignment_loro_sensitivity.csv |

## Submission artwork

| Generated file in output/ | Manuscript source filename |
|---|---|
| fig2_repository_transport_panel_a.pdf | Figure_2a.pdf |
| fig2_repository_transport_panel_b.pdf | Figure_2b.pdf |
| fig2_volume_distribution_panel_a.pdf | Figure_3a.pdf |
| fig2_volume_distribution_panel_b.pdf | Figure_3b.pdf |

The two combined PDFs are retained for convenient inspection. The manuscript uses the four independent vector PDFs; the auxiliary PNG is not the submission artwork.

## Numerical checkpoints

- Total resolved records: 877; primary binary records: 841; developer-test failures: 68; comparison records: 773; coding-convention-only records excluded from the binary comparison: 36.
- The complete set has 371 issues; the primary binary cohort has 366. These are different denominators.
- Primary component-volume GEE: agent beta 0.079, p=0.506; inference uses eight two-class repositories, N=794.
- Gold-free files+hunks model: review 90/841 = 10.7%, capture 15/68 = 22.1%; review 172/841 = 20.5%, capture 23/68 = 33.8%.
- The 25-feature static model has different displayed recall values: 13.2% and 23.5%, respectively.
- Static model pooled AUC 0.411, 95% CI [0.315, 0.549]. The interval includes chance; the point estimate alone does not establish worse-than-chance performance.
- Exploratory rho<0.5 tail: 8/68 versus 10/773; OR 10.17; Holm p approximately 0.000139. A printed p=0.0000 is rounding, not a zero probability.
- Figure 3(a) displays through rho=300 with seven observations outside the axis. They remain in the underlying full-cohort calculation.
- Within-issue analysis uses 25 mixed-outcome issues; RQ4 matched configuration analysis uses 203 complete triples.

Exact definitions, seeds and bootstrap counts are in the corresponding scripts. Compare manuscript values at their reported precision, without rounding or replacing stored outputs. Verification supports computational consistency; it does not independently validate the inherited developer-test labels.

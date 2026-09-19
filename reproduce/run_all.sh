#!/bin/bash
# Reproduce all automated analyses for the SWE-bench Verified secondary study.
# Requires: Python 3.12, uv (or pip)

set -e
SKIP_RESULT_VERIFICATION=0
for argument in "$@"; do
    case "$argument" in
        --skip-result-verification) SKIP_RESULT_VERIFICATION=1 ;;
        *) echo "[ERROR] Unknown argument: $argument"; exit 2 ;;
    esac
done
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if ! command -v uv >/dev/null 2>&1; then
    echo "[ERROR] uv is not installed or is not on PATH."
    echo "  Run the one-time setup command: ./setup.sh"
    exit 1
fi
: "${UV_CACHE_DIR:=${TMPDIR:-/tmp}/gold-signal-uv-cache}"
export UV_CACHE_DIR
mkdir -p "$UV_CACHE_DIR"

echo "============================================"
echo " SWE-bench Verified Developer-Test Failure Study"
echo "============================================"
echo ""

# Check data dependencies
if [ ! -d "external/PatchDiff/results" ]; then
    echo "[ERROR] Official PatchDiff archive not found."
    echo "  Run the resumable one-time setup command: ./setup.sh"
    exit 1
fi

mkdir -p output

echo "Preflight: verify pinned PatchDiff v3 inputs ..."
uv run python scripts/verify_inputs.py
echo ""

TOTAL_STEPS=11

echo "Step 1/$TOTAL_STEPS: Build developer-test three-state cohort ..."
uv run python scripts/build_analysis_dataset.py
echo ""

echo "Step 2/$TOTAL_STEPS: Audit upstream label provenance ..."
uv run python scripts/audit_upstream_labels.py
echo ""

echo "Step 3/$TOTAL_STEPS: RQ1/RQ3 - Volume models and repository transport ..."
uv run python scripts/run_mixed_effects.py
echo ""

echo "Step 4/$TOTAL_STEPS: RQ3 - Static final-diff learning baseline ..."
uv run python scripts/run_static_diff_baseline.py
echo ""

echo "Step 5/$TOTAL_STEPS: RQ2 - Structural alignment and robustness ..."
uv run python scripts/run_structural_alignment.py
echo ""

echo "Step 6/$TOTAL_STEPS: RQ2 - Within-issue structural sensitivity ..."
uv run python scripts/run_within_issue_sensitivity.py
echo ""

echo "Step 7/$TOTAL_STEPS: RQ2 - Quantify within-issue design sensitivity ..."
uv run python scripts/run_paired_sensitivity.py
echo ""

echo "Step 8/$TOTAL_STEPS: RQ4 - Cross-configuration comparison ..."
uv run python scripts/run_rq3_kruskal.py
echo ""

echo "Step 9/$TOTAL_STEPS: Build repository-transport figure ..."
uv run python scripts/fig2_repository_transport.py
echo ""

echo "Step 10/$TOTAL_STEPS: Build exploratory tail figure ..."
uv run python scripts/fig2_volume_distribution.py
echo ""

echo "Step 11/$TOTAL_STEPS: Materialize motivating example ..."
uv run python scripts/deep_dive_24443.py
echo ""

if [ -f "EXPECTED_RESULTS.json" ] && [ "$SKIP_RESULT_VERIFICATION" -eq 0 ]; then
    echo "Postflight: verify generated results against the release manifest ..."
    uv run python scripts/verify_results.py
    echo ""
elif [ "$SKIP_RESULT_VERIFICATION" -eq 1 ]; then
    echo "Postflight result verification skipped by explicit maintainer request."
    echo "Refresh EXPECTED_RESULTS.json before publishing this code revision."
    echo ""
fi

echo "============================================"
echo " Done. Analysis results are in reproduce/output/"
echo "============================================"

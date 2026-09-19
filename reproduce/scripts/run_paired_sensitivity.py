# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "scipy"]
# ///
"""Quantify design sensitivity for sparse within-issue structural contrasts."""

from __future__ import annotations

import json

from scipy import stats

from common import BASE


OUT_DIR = BASE / "output"
TARGET_POWER = 0.80
ALPHA_NOMINAL = 0.05
ALPHA_FAMILY = 0.0125


def rejection_set(informative_n: int, alpha: float) -> list[int]:
    return [
        successes
        for successes in range(informative_n + 1)
        if stats.binomtest(successes, informative_n, 0.5).pvalue <= alpha
    ]


def exact_power(informative_n: int, success_probability: float, alpha: float) -> float:
    rejected = rejection_set(informative_n, alpha)
    return float(sum(
        stats.binom.pmf(successes, informative_n, success_probability)
        for successes in rejected
    ))


def minimum_detectable_odds(informative_n: int, alpha: float) -> float | None:
    """Smallest directional odds ratio yielding 80% exact two-sided power."""
    if informative_n == 0 or informative_n not in rejection_set(informative_n, alpha):
        return None
    low, high = 0.5, 1.0 - 1e-12
    for _ in range(100):
        middle = (low + high) / 2
        if exact_power(informative_n, middle, alpha) >= TARGET_POWER:
            high = middle
        else:
            low = middle
    return float(high / (1 - high))


def sensitivity_payload(
    *,
    family: str,
    signal: str,
    total_units: int,
    positive_n: int,
    negative_n: int,
    tie_n: int,
) -> dict:
    informative_n = positive_n + negative_n
    observed_odds = None if negative_n == 0 else positive_n / negative_n
    return {
        "family": family,
        "signal": signal,
        "total_units": total_units,
        "positive_n": positive_n,
        "negative_n": negative_n,
        "tie_n": tie_n,
        "informative_n": informative_n,
        "observed_direction_odds": observed_odds,
        "minimum_detectable_odds_ratio_80pct_power": {
            "two_sided_alpha_0.05": minimum_detectable_odds(
                informative_n, ALPHA_NOMINAL
            ),
            "two_sided_alpha_0.0125": minimum_detectable_odds(
                informative_n, ALPHA_FAMILY
            ),
        },
        "minimum_attainable_two_sided_p": (
            float(stats.binomtest(informative_n, informative_n, 0.5).pvalue)
            if informative_n else 1.0
        ),
    }


within_issue = json.loads(
    (OUT_DIR / "structural_alignment_within_issue_sensitivity.json").read_text(
        encoding="utf-8"
    )
)

rows = []
for row in within_issue["results"]:
    rows.append(sensitivity_payload(
        family="within_issue_structural_contrasts",
        signal=row["feature"],
        total_units=within_issue["issue_n"],
        positive_n=row["positive_n"],
        negative_n=row["negative_n"],
        tie_n=row["tie_n"],
    ))

payload = {
    "status": "complete_exact_within_issue_design_sensitivity",
    "target_power": TARGET_POWER,
    "method": (
        "Conditional exact two-sided binomial power given the observed number "
        "of informative (discordant or non-tied) pairs. The 0.0125 threshold "
        "is a conservative Bonferroni sensitivity benchmark for each four-test "
        "family; it is not presented as the variable Holm rejection boundary."
    ),
    "interpretation": (
        "This is a minimum-detectable-effect analysis, not observed post-hoc "
        "power and not an equivalence test. A null minimum detectable odds "
        "ratio means that discreteness prevents 80% power at any effect size."
    ),
    "rows": rows,
}

path = OUT_DIR / "paired_design_sensitivity.json"
path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Paired design sensitivity -> {path}")
for row in rows:
    nominal = row["minimum_detectable_odds_ratio_80pct_power"][
        "two_sided_alpha_0.05"
    ]
    family = row["minimum_detectable_odds_ratio_80pct_power"][
        "two_sided_alpha_0.0125"
    ]
    nominal_text = "not attainable" if nominal is None else f"{nominal:.2f}"
    family_text = "not attainable" if family is None else f"{family:.2f}"
    print(
        f"  {row['signal']:<25} informative={row['informative_n']:>2}; "
        f"MDE OR alpha=.05={nominal_text}; alpha=.0125={family_text}"
    )

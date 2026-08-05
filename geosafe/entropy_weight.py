"""Transparent entropy-derived objective indicator weighting."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


class EntropyWeightError(ValueError):
    """Raised when objective weights cannot be calculated safely."""


def entropy_weights(
    observations: Mapping[str, Sequence[float | int]],
    *,
    allow_equal_fallback: bool = False,
) -> dict[str, float]:
    """Calculate normalized Shannon-entropy weights for non-negative columns.

    Each key is an indicator and each sequence contains comparable normalized
    observations. Constant indicators receive zero information utility. When
    every indicator is constant, an explicit equal-weight fallback is required.
    """

    if not observations:
        raise EntropyWeightError("At least one indicator is required.")
    lengths = {len(values) for values in observations.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
        raise EntropyWeightError(
            "Every indicator must contain the same two or more observations."
        )

    normalized: dict[str, list[float]] = {}
    for indicator, values in observations.items():
        column = [float(value) for value in values]
        if not all(math.isfinite(value) and value >= 0 for value in column):
            raise EntropyWeightError(
                f"Indicator {indicator!r} contains a negative or non-finite value."
            )
        lower, upper = min(column), max(column)
        normalized[indicator] = (
            [0.0 for _ in column]
            if upper == lower
            else [(value - lower) / (upper - lower) for value in column]
        )

    sample_count = next(iter(lengths))
    entropy_scale = 1.0 / math.log(sample_count)
    divergences: dict[str, float] = {}
    for indicator, column in normalized.items():
        total = sum(column)
        if total <= 0:
            divergences[indicator] = 0.0
            continue
        proportions = [value / total for value in column]
        entropy = -entropy_scale * sum(
            proportion * math.log(proportion)
            for proportion in proportions
            if proportion > 0
        )
        divergences[indicator] = max(0.0, 1.0 - entropy)

    total_divergence = sum(divergences.values())
    if total_divergence <= 0:
        if not allow_equal_fallback:
            raise EntropyWeightError(
                "All indicators are constant; entropy weights are undefined."
            )
        equal = 1.0 / len(observations)
        return {indicator: equal for indicator in observations}
    return {
        indicator: divergence / total_divergence
        for indicator, divergence in divergences.items()
    }

"""Offline references. Prediction-ranked greedy is deliberately NOT an upper bound."""
from __future__ import annotations
import itertools
import math
import numpy as np


def integer_knapsack(weights: list[int], values: list[float], budget: int) -> float:
    """Exact 0/1 DP for integer weights; floating values are subject to roundoff."""
    if len(weights) != len(values) or budget < 0 or not isinstance(budget, int):
        raise ValueError("Invalid knapsack dimensions")
    dp = np.zeros(budget + 1)
    for w, v in zip(weights, values):
        if not isinstance(w, (int, np.integer)) or w < 0 or not math.isfinite(v) or v < 0:
            raise ValueError("Need nonnegative integer costs and finite nonnegative values")
        if w == 0:
            dp += v
        elif w <= budget:
            # RHS evaluated before assignment: each item used at most once.
            dp[w:] = np.maximum(dp[w:], dp[:-w] + v)
    return float(dp[-1])


def brute_force(weights: list[int], values: list[float], budget: int) -> float:
    if len(weights) > 22:
        raise ValueError("Brute-force check limited to 22 items")
    return max((sum(v * x for v, x in zip(values, mask))
                for mask in itertools.product((0, 1), repeat=len(weights))
                if sum(w * x for w, x in zip(weights, mask)) <= budget), default=0.0)


def fractional_optimum(weights: list[float], values: list[float], budget: float) -> float:
    if len(weights) != len(values) or budget < 0:
        raise ValueError("Invalid input")
    value, remaining, items = 0.0, budget, []
    for w, v in zip(weights, values):
        if not math.isfinite(w) or not math.isfinite(v) or w < 0 or v < 0:
            raise ValueError("Invalid weight/value")
        if w == 0:
            value += v
        else:
            items.append((v / w, w))
    for density, w in sorted(items, reverse=True):
        take = min(w, remaining)
        value += take * density
        remaining -= take
        if remaining <= 0:
            break
    return value


def resolved_count_oracle(costs: list[float], resolved: list[int], budget: float) -> int:
    """Exact count oracle for unit-valued successes; no cost rounding or greedy approximation.

    This is a relaxed upper bound: it ignores reservations, workers and deadlines.
    """
    from decimal import Decimal
    remaining = Decimal(str(budget))
    count = 0
    for cost in sorted(Decimal(str(c)) for c, y in zip(costs, resolved) if y == 1):
        if cost < 0:
            raise ValueError("Negative cost")
        if cost > remaining:
            break
        remaining -= cost
        count += 1
    return count

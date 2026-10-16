"""Fresh implementation of Sections 2, 3 and 5 of the supplied manuscript.

All utilization arguments are normalized to [0, 1]. L and U must use the same
units as the density passed to the policy. Theoretical certificates use budget 1.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
from scipy.integrate import quad
from scipy.optimize import brentq


def alpha(L: float, U: float) -> float:
    if not (math.isfinite(L) and math.isfinite(U) and 0 < L < U):
        raise ValueError("Need finite 0 < L < U")
    return 1.0 + math.log(U / L)


def zcl_bound(L: float, U: float, delta: float) -> float:
    a = alpha(L, U)
    if not math.isfinite(delta) or delta < 0:
        raise ValueError("delta must be finite and nonnegative")
    if delta >= 1 - 1 / a:
        return U / L
    return U / (L * delta + U / a * math.exp(-a * delta))


def delayed_exp(beta: float, u: float, delta: float,
                cap: float = math.inf) -> float:
    """Positive finite series of Definition 3.5; optional cap for root bracketing."""
    if beta <= 0 or delta < 0 or not all(map(math.isfinite, (beta, u, delta))):
        raise ValueError("Invalid delayed exponential parameters")
    if u <= 0:
        return 1.0
    if delta == 0:
        return math.exp(min(beta * u, math.log(cap))) if cap < math.inf else math.exp(beta * u)
    n = int(math.floor(u / delta)) + 1
    if n > 100_000:
        raise ValueError("Delay too small for exact finite-series evaluator; use delta=0 or a DDE solver")
    total = 1.0
    for j in range(1, n + 1):
        x = u - (j - 1) * delta
        if x <= 0:
            continue
        logterm = j * (math.log(beta) + math.log(x)) - math.lgamma(j + 1)
        if logterm >= math.log(cap):
            return cap
        term = math.exp(logterm)
        total += term
        if total >= cap:
            return cap
    return total


@lru_cache(maxsize=1024)
def optimal_beta(L: float, U: float, delta: float) -> float:
    a = alpha(L, U)
    if not 0 <= delta <= 1:
        raise ValueError("Design delta must lie in [0,1]")
    if delta == 0:
        return a
    ratio = U / L
    if delta >= 1 - 1 / ratio:
        return ratio
    def endpoint(beta: float) -> float:
        return delayed_exp(beta, 1 - 1 / beta, delta, cap=ratio * 2) - ratio
    lo, hi = 1.0, max(2.0, a)
    while endpoint(hi) < 0:
        hi *= 2
    return float(brentq(endpoint, lo, hi, xtol=1e-11, rtol=1e-13))


@dataclass(frozen=True)
class Threshold:
    L: float
    U: float
    kind: str = "zcl"
    delta: float = 0.0
    forecast: float = 0.0
    band: float = 0.0
    # For independent random nondecreasing step-threshold tests.
    step_edges: tuple[float, ...] = ()
    step_values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        alpha(self.L, self.U)
        if self.kind not in {"zcl", "lag", "band", "fixed", "cap", "step"}:
            raise ValueError("Unknown threshold kind")
        if not 0 <= self.delta <= 1 or self.band < 0:
            raise ValueError("Invalid delay/band")
        if self.kind == "step":
            if len(self.step_values) != len(self.step_edges) + 1:
                raise ValueError("Step values must have one more element than edges")
            if any(not 0 < x < 1 for x in self.step_edges) or tuple(sorted(set(self.step_edges))) != self.step_edges:
                raise ValueError("Invalid step edges")
            if tuple(sorted(self.step_values)) != self.step_values or not all(0 <= x <= self.U for x in self.step_values):
                raise ValueError("Step threshold must be monotone in [0,U]")

    @property
    def beta(self) -> float:
        return optimal_beta(self.L, self.U, self.delta)

    def _zcl(self, z: float) -> float:
        z = min(1.0, max(0.0, z))
        return self.L * math.exp(alpha(self.L, self.U) * z - 1)

    def __call__(self, z: float) -> float:
        z = min(1.0, max(0.0, z))
        if self.kind == "cap":
            return 0.0
        if self.kind == "fixed":
            return self.forecast
        if self.kind == "zcl":
            return self._zcl(z)
        if self.kind == "band":
            return min(max(self.forecast, self._zcl(z - self.band)), self._zcl(z + self.band))
        if self.kind == "step":
            import bisect
            return self.step_values[bisect.bisect_right(self.step_edges, z)]
        b = self.beta
        return self.L if z <= 1 / b else min(self.U, self.L * delayed_exp(b, z - 1 / b, self.delta))

    def kinks(self) -> list[float]:
        a = alpha(self.L, self.U)
        if self.kind == "lag":
            b = self.beta
            if self.delta == 0:
                return [1 / b]
            return [1 / b + j * self.delta for j in range(int(1 / self.delta) + 1)
                    if 1 / b + j * self.delta < 1]
        if self.kind == "step":
            return list(self.step_edges)
        if self.kind == "band":
            out = [self.band, 1 - self.band, 1 / a - self.band, 1 / a + self.band]
            if self.forecast > 0:
                cross = (1 + math.log(self.forecast / self.L)) / a
                out += [cross - self.band, cross + self.band]
            return [x for x in out if 0 < x < 1]
        return [1 / a]


def coverage(phi: Threshold, delta: float, z: float) -> float:
    """J_{phi,delta}(z), evaluated independently by numerical quadrature."""
    if delta < 0 or not 0 <= z <= 1 + 1e-9:
        raise ValueError("Invalid coverage arguments")
    z = min(z, 1.0)
    if z == 0:
        return 0.0
    if phi.kind == "zcl":
        a = alpha(phi.L, phi.U)
        if z <= delta + 1 / a:
            return phi.L * z
        return phi.L * delta + phi._zcl(z - delta) / a
    points = sorted(set([x + delta for x in phi.kinks() if 0 < x + delta < z]
                        + ([delta] if 0 < delta < z else [])))
    val, error = quad(lambda x: max(phi.L, phi(max(0.0, x - delta))), 0, z,
                      points=points, epsabs=1e-9, epsrel=1e-10, limit=max(200, len(points) + 10))
    if error > 1e-6 * max(1.0, abs(val)):
        raise ArithmeticError(f"Unreliable quadrature: error={error}")
    return float(val)

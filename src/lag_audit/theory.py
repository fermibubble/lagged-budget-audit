"""Falsification-oriented finite tests; passing does not establish a universal theorem."""
from __future__ import annotations
import math
import numpy as np
from .engine import Job, Proposal, Policy, replay
from .thresholds import Threshold, alpha, coverage, optimal_beta, zcl_bound
from .oracles import integer_knapsack, fractional_optimum


def audit_instance(jobs: list[Job], policy: Policy, workers: int, units: int) -> dict:
    if policy.density_mode != "reservation":
        raise ValueError("The theorem's density is value/reservation, not expected cost")
    phi = policy.threshold
    for job in jobs:
        if not math.isclose(job.value, job.proposal.expected_value, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("Theorem test requires known values")
        if not phi.L - 1e-9 <= job.value / job.proposal.reservation <= phi.U + 1e-9:
            raise ValueError("Density outside theorem assumptions")
    result = replay(jobs, 1.0, workers, policy, "strict")
    weights_r = [j.proposal.reservation for j in jobs]
    weights_a = [j.actual_cost for j in jobs]
    values = [j.value for j in jobs]
    for w in weights_r + weights_a:
        if not math.isclose(w * units, round(w * units), abs_tol=1e-7):
            raise ValueError("DP oracle requires exact input cost grid")
    optr = integer_knapsack([round(w * units) for w in weights_r], values, units)
    opta = integer_knapsack([round(w * units) for w in weights_a], values, units)
    fracr = fractional_optimum(weights_r, values, 1.0)
    fraca = fractional_optimum(weights_a, values, 1.0)
    gamma = None if any(a <= 0 for a in weights_a) else max((r / a for r, a in zip(weights_r, weights_a)), default=1.0)
    z = min(1.0, result.peak_commitment)
    J = coverage(phi, result.delta, z)
    lam = max(phi.L, phi(z), max(result.room_densities, default=0.0))
    eps = 1e-7 * max(1.0, fracr, fraca, (gamma or 1.0) * lam)
    failures = []
    if result.value + eps < J:
        failures.append("coverage")
    if fracr > result.value + lam - J + eps:
        failures.append("reservation_dual_bound")
    if gamma is not None and fraca > result.value + gamma * lam - J + eps:
        failures.append("actual_cost_dual_bound")
    harmful = bool(result.room_densities) and (phi(z) <= phi.L + 1e-10 or any(d > phi(z) + 1e-9 for d in result.room_densities))
    if gamma is not None and not harmful and phi.kind == "zcl" and opta > gamma * zcl_bound(phi.L, phi.U, result.delta) * result.value + eps:
        failures.append("no_harmful_zcl")
    if gamma is not None and not harmful and phi.kind == "lag" and result.delta <= phi.delta + 1e-10 and opta > gamma * phi.beta * result.value + eps:
        failures.append("no_harmful_lag_optimal")
    return {"failures": failures, "alg": result.value, "opt_r": optr, "opt_a": opta,
            "fractional_opt_r": fracr, "fractional_opt_a": fraca,
            "J": J, "lambda": lam, "gamma": gamma, "delta": result.delta,
            "z_star": z, "harmful_refusal": harmful,
            "reservation_certificate": lam / J if J > 0 else None,
            "actual_cost_certificate": gamma * lam / J if J > 0 and gamma is not None else None,
            "actual_cost_certificate_status": "finite" if gamma is not None and J > 0 else ("zero_actual_cost_unbounded_gamma" if gamma is None else "zero_coverage")}


def random_audit(n: int = 1000, seed: int = 20261014) -> dict:
    rng = np.random.default_rng(seed)
    counterexamples, tested, no_harm, configs = [], 0, 0, {}
    for i in range(n):
        units = int(rng.integers(20, 81))
        ratio = float(rng.choice([2, 10, 100, 1000]))
        kind = ["zcl", "lag", "band", "step"][i % 4]
        signal = ["settled", "committed"][i // 4 % 2]
        refunds = bool(i // 8 % 2)
        edges = (.2, .4, .6, .8)
        step_values = tuple(sorted(rng.uniform(0, ratio, 5)))
        phi = Threshold(1, ratio, kind=kind, delta=float(rng.choice([.05,.1,.2,.3])),
                        forecast=float(rng.uniform(0, ratio)), band=.05,
                        step_edges=edges, step_values=step_values)
        jobs = []
        for t in range(int(rng.integers(1, 35))):
            r = int(rng.integers(1, units + 1))
            a = int(rng.integers(1, r + 1)) if refunds else r
            density = float(rng.choice([1, ratio, math.exp(rng.uniform(0, math.log(ratio)))]))
            value = density * r / units
            jobs.append(Job(Proposal(str(t), r / units, value, r / units), a / units, value,
                            float(rng.integers(1, 30)), float(t * rng.integers(0, 3))))
        workers = int(rng.integers(1, 10))
        row = audit_instance(jobs, Policy(phi, signal), workers, units)
        tested += 1
        no_harm += int(not row["harmful_refusal"])
        label = f"{kind}/{signal}/refunds={refunds}"
        configs[label] = configs.get(label, 0) + 1
        if row["failures"]:
            from dataclasses import asdict
            counterexamples.append({"index": i, "units": units, "workers": workers,
                                    "policy": asdict(Policy(phi, signal)), "jobs": [asdict(j) for j in jobs],
                                    "audit": row})
    return {"seed": seed, "tested_instances": tested, "without_harmful_refusal": no_harm,
            "configurations": configs, "violations": len(counterexamples),
            "counterexamples": counterexamples,
            "interpretation": "Finite numerical tests; not a proof or universal verification."}


def adversary(ratio: float, delta: float, units: int, kind: str) -> dict:
    """Finite endpoint construction in Proposition 3.3, with an explicit half-item filler."""
    phi = Threshold(1, ratio, kind, delta=delta)
    lag_jobs = int(math.floor(delta * units))
    jobs = []
    for i in range(units - 1):
        signal = max(0, i - lag_jobs) / units
        density = max(1, phi(signal))
        r = 1 / units
        jobs.append(Job(Proposal(f"low-{i}", r, density * r, r), r, density * r,
                        lag_jobs + 1.0, float(i)))
    # Without this filler, 1/units room remains and a high-density job fits.
    r = 0.5 / units
    density = max(1, phi(max(0, units - 1 - lag_jobs) / units))
    jobs.append(Job(Proposal("filler", r, density*r, r), r, density*r,
                    lag_jobs + 1.0, float(units - 1)))
    for i in range(units):
        r = 1 / units
        jobs.append(Job(Proposal(f"high-{i}", r, ratio*r, r), r, ratio*r, 1, float(units + 1)))
    result = replay(jobs, 1, units + 2, Policy(phi, "settled"), "strict")
    measured = ratio / result.value  # Exact OPT = ratio: all high jobs fit and no density exceeds ratio.
    target = zcl_bound(1, ratio, delta) if kind == "zcl" else optimal_beta(1, ratio, delta)
    return {"ratio_U_L": ratio, "lag_before_admission_limit": delta, "units": units,
            "kind": kind, "measured_ratio": measured, "asymptotic_target": target,
            "observed_delta_including_item": result.delta,
            "relative_error": abs(measured - target) / target}


def coarse_counterexample() -> dict:
    phi = Threshold(1, 100)
    jobs = []
    k = 0.0
    for i, r in enumerate([.1] * 9 + [.001]):
        density = max(1, phi(k))
        jobs.append(Job(Proposal(str(i), r, density*r, r), r, density*r, .1, float(i)))
        k += r
    for i in range(10):
        jobs.append(Job(Proposal(f"high-{i}", .1, 10, .1), .1, 10, .1, float(10+i)))
    row = audit_instance(jobs, Policy(phi, "committed"), 1, 1000)
    row["measured_ratio"] = row["opt_r"] / row["alg"]
    row["small_item_claim_comparator"] = alpha(1, 100) * math.exp(alpha(1, 100) * .1)
    return row

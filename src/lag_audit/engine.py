"""Deterministic event-driven simulator with an outcome-blind policy interface.

Policy sees Proposal + ledger only. Actual cost, outcome and realized duration
belong to the environment, not the policy. No source patch is ever executed.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import heapq
import math
from .thresholds import Threshold

TOL = 1e-10


@dataclass(frozen=True)
class Proposal:
    id: str
    reservation: float
    expected_value: float
    expected_cost: float

    def __post_init__(self) -> None:
        if not self.id or not all(map(math.isfinite, (self.reservation, self.expected_value, self.expected_cost))):
            raise ValueError("Invalid proposal")
        if self.reservation <= 0 or self.expected_value < 0 or not 0 < self.expected_cost <= self.reservation + TOL:
            raise ValueError("Invalid reservation or prediction")


@dataclass(frozen=True)
class Job:
    proposal: Proposal
    actual_cost: float
    value: float
    duration: float
    arrival: float = 0.0

    def __post_init__(self) -> None:
        if not all(map(math.isfinite, (self.actual_cost, self.value, self.duration, self.arrival))):
            raise ValueError("Non-finite job field")
        if not 0 <= self.actual_cost <= self.proposal.reservation + TOL:
            raise ValueError("Actual cost violates reservation: never silently clip a trace")
        if self.value < 0 or self.duration <= 0 or self.arrival < 0:
            raise ValueError("Invalid job value/time")


@dataclass(frozen=True)
class Policy:
    threshold: Threshold
    signal: str = "committed"
    density_mode: str = "reservation"

    def __post_init__(self) -> None:
        if self.signal not in {"committed", "settled", "expected"}:
            raise ValueError("Unknown price signal")
        if self.density_mode not in {"reservation", "expected"}:
            raise ValueError("Unknown density denominator")

    def density(self, p: Proposal) -> float:
        denominator = p.reservation if self.density_mode == "reservation" else p.expected_cost
        return p.expected_value / denominator

    def price_signal(self, settled: float, reserved: float, expected: float) -> float:
        return settled + ({"committed": reserved, "settled": 0.0, "expected": expected}[self.signal])


@dataclass
class ReplayResult:
    admitted: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    room_densities: list[float] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    spend: float = 0.0
    value: float = 0.0
    value_before_deadline: float = 0.0
    peak_commitment: float = 0.0
    delta: float = 0.0
    makespan: float = 0.0
    total_wait: float = 0.0
    peak_running: int = 0
    completed_before_deadline: int = 0
    completed_after_deadline: int = 0

    def summary(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in {"events", "room_densities"}}


def replay(jobs: list[Job], budget: float, workers: int, policy: Policy,
           queue_mode: str = "strict", deadline: float = math.inf) -> ReplayResult:
    """Three deliberately separate decision semantics.

    strict: paper Section 2, room first, both refusals irrevocable.
    paper: Appendix C batch, price-drop first; room-block at head until settlement.
    defer: scan the available queue, recheck price AND room after any settlement.
    No admission at/after deadline; admitted costs are charged even for late completion.
    """
    if budget <= 0 or not math.isfinite(budget) or workers < 1 or queue_mode not in {"strict", "paper", "defer"}:
        raise ValueError("Invalid replay configuration")
    if len({j.proposal.id for j in jobs}) != len(jobs):
        raise ValueError("Duplicate job IDs")
    ordered = sorted(enumerate(jobs), key=lambda pair: (pair[1].arrival, pair[0]))
    pending: list[Job] = []
    running: list[tuple[float, int, Job]] = []
    result = ReplayResult()
    now = settled = reserved = expected = 0.0
    next_arrival = serial = 0

    def log(kind: str, job: Job, **extra: float | str) -> None:
        result.events.append({"time": now, "kind": kind, "id": job.proposal.id,
                              "settled": settled, "reserved": reserved,
                              "committed": settled + reserved, **extra})

    def drop(job: Job, reason: str) -> None:
        result.rejected[job.proposal.id] = reason
        if reason == "room":
            result.room_densities.append(policy.density(job.proposal))
        log("reject", job, reason=reason)

    while next_arrival < len(ordered) or pending or running:
        while running and running[0][0] <= now + TOL:
            finish, _, job = heapq.heappop(running)
            reserved = max(0.0, reserved - job.proposal.reservation)
            expected = max(0.0, expected - job.proposal.expected_cost)
            settled += job.actual_cost
            result.value += job.value
            if finish <= deadline + TOL:
                result.value_before_deadline += job.value
                result.completed_before_deadline += 1
            else:
                result.completed_after_deadline += 1
            result.makespan = max(result.makespan, finish)
            log("settle", job, actual_cost=job.actual_cost, outcome=job.value)
        while next_arrival < len(ordered) and ordered[next_arrival][1].arrival <= now + TOL:
            pending.append(ordered[next_arrival][1])
            next_arrival += 1
        if settled + reserved > budget + TOL:
            raise AssertionError("Budget cap violation")
        if now >= deadline:
            for job in pending:
                drop(job, "deadline")
            pending.clear()
            for _, job in ordered[next_arrival:]:
                drop(job, "deadline")
            next_arrival = len(ordered)
        cursor = 0
        while cursor < len(pending) and len(running) < workers and now < deadline:
            job = pending[cursor]
            p = job.proposal
            signal = policy.price_signal(settled, reserved, expected)
            if signal > settled + reserved + TOL:
                raise AssertionError("Signal exceeds committed ledger")
            price = policy.threshold(signal / budget)
            density = policy.density(p)
            room = p.reservation <= budget - settled - reserved + TOL
            passes = density + 1e-12 * max(1.0, abs(price)) >= price
            reason = ("room" if not room else "price") if queue_mode == "strict" else ("price" if not passes else "room")
            if not room or not passes:
                if queue_mode == "strict" or (queue_mode == "paper" and not passes):
                    pending.pop(cursor)
                    drop(job, reason)
                    continue
                # Reservation exceeding the whole budget can never be fulfilled.
                if p.reservation > budget + TOL or not running:
                    pending.pop(cursor)
                    drop(job, reason)
                    continue
                log("defer", job, reason=reason, price=price, density=density)
                if queue_mode == "paper":
                    break
                cursor += 1
                continue
            pending.pop(cursor)
            delta = (settled + reserved + p.reservation - signal) / budget
            reserved += p.reservation
            expected += p.expected_cost
            result.peak_commitment = max(result.peak_commitment, (settled + reserved) / budget)
            result.delta = max(result.delta, delta)
            result.admitted.append(p.id)
            result.total_wait += now - job.arrival
            serial += 1
            heapq.heappush(running, (now + job.duration, serial, job))
            result.peak_running = max(result.peak_running, len(running))
            log("admit", job, signal=signal, price=price, density=density, delta=delta)
            if settled + reserved > budget + TOL:
                raise AssertionError("Reservation cap violation")
        future = []
        if running:
            future.append(running[0][0])
        if next_arrival < len(ordered):
            future.append(ordered[next_arrival][1].arrival)
        if pending and math.isfinite(deadline) and now < deadline:
            future.append(deadline)
        if future:
            now = min(future)
        elif pending:
            raise AssertionError("Queue deadlock")
        else:
            break
    result.spend = settled
    return result

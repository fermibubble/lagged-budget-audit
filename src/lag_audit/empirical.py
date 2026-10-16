"""Forward-only per-submission trace replay. No claim of live deployment evaluation."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score
from .data import sha256
from .engine import Job, Proposal, Policy, replay
from .oracles import resolved_count_oracle
from .prediction import Predictor
from .statistics import paired_block_interval
from .thresholds import Threshold

POLICIES = ("hard_cap", "zcl_settled", "zcl_committed", "zcl_expected_inflight",
            "lag_structural", "lag_previous_day", "fixed_warmup", "banded_warmup")


def partition(rows: list[dict], n_blocks: int) -> list[list[dict]]:
    """Disjoint issue groups ordered by PR creation timestamp (a proxy, not issue arrival)."""
    if len({r["submission"] for r in rows}) != 1:
        raise ValueError("Replay runs each submission separately; pooling is a separate future experiment")
    if len({r["instance_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate issues; prevent multi-attempt leakage")
    ordered = sorted(rows, key=lambda r: (r["created_at"], r["instance_id"]))
    if len(rows) < n_blocks * 2:
        raise ValueError("Too few rows for the requested partition")
    return [[ordered[i] for i in idx] for idx in np.array_split(np.arange(len(ordered)), n_blocks)]


def jobs_from(rows: list[dict], probabilities: np.ndarray, costs: np.ndarray,
              reservation: float, duration_mode: str, seconds_per_call: float,
              fixed_duration: float) -> list[Job]:
    jobs = []
    for r, p, c in zip(rows, probabilities, costs):
        if r["actual_cost"] > reservation + 1e-10:
            raise ValueError(f"Reservation exceeded by {r['id']}; do not clip, remove or infer a larger cap from test outcomes")
        if duration_mode == "fixed":
            duration = fixed_duration
        elif duration_mode == "api_calls_proxy":
            if r.get("api_calls") is None:
                raise ValueError("Missing API-call count for duration-proxy experiment")
            duration = max(1, r["api_calls"]) * seconds_per_call
        else:
            raise ValueError("Unsupported modeled duration")
        jobs.append(Job(Proposal(r["id"], reservation, float(p), float(c)),
                        float(r["actual_cost"]), float(r["resolved"]), duration))
    return jobs


def tune_warmup(warmup: list[dict], budget: float, reservation: float, density_mode: str,
                workers: int, queue_mode: str, config: dict) -> tuple[float, float, float]:
    # An inner forward split: success and cost fitting never see validation outcomes.
    split = max(2, int(len(warmup) * .7))
    fitting, validation = warmup[:split], warmup[split:]
    model = Predictor(reservation, config["seed"]).fit(fitting)
    p, c = model.predict(validation)
    densities = p / (reservation if density_mode == "reservation" else c)
    L = max(1e-8, float(np.quantile(densities, .05)))
    U = max(L * 1.001, float(np.quantile(densities, .95)))
    candidates = np.unique(np.r_[0, np.quantile(densities, np.linspace(0, 1, 20))])
    jobs = jobs_from(validation, p, c, reservation, config["duration_mode"],
                     config["seconds_per_call"], config["fixed_duration"])
    scored = []
    for price in candidates:
        result = replay(jobs, budget, workers, Policy(Threshold(L, U, "fixed", forecast=float(price)),
                                                     "committed", density_mode), queue_mode)
        scored.append((result.value, -result.spend, -float(price), float(price)))
    return L, U, max(scored)[3]


def run_experiments(data_path: Path, config: dict, output_dir: Path,
                    allow_incomplete: bool = False) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Results directory must be new; do not overwrite unfavorable runs")
    rows = [json.loads(line) for line in data_path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("No data")
    audit_path = data_path.with_suffix(".audit.json")
    if not audit_path.exists():
        raise ValueError("Ingestion audit is mandatory; use the normalize command")
    audit = json.loads(audit_path.read_text())
    if audit.get("normalized_sha256") != sha256(data_path):
        raise ValueError("Normalized data changed after ingestion audit")
    if not audit.get("complete") and not allow_incomplete:
        raise ValueError("Incomplete archive: inspect exclusions and explicitly use --allow-incomplete for a complete-case sensitivity study")
    if config.get("data_kind") != "real_swebench_trace":
        raise ValueError("Empirical configuration must explicitly identify real_swebench_trace")
    blocks = partition(rows, config["n_blocks"])
    warmup = [r for block in blocks[:config["warmup_blocks"]] for r in block]
    if not 1 <= config["warmup_blocks"] < config["n_blocks"] - 1:
        raise ValueError("Need warm-up and at least two evaluated blocks")
    output_dir.mkdir(parents=True)
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    (output_dir / "config.json").write_text(json.dumps(config, indent=2))
    (output_dir / "splits.json").write_text(json.dumps([[r["instance_id"] for r in b] for b in blocks], indent=2))
    episodes, training_log = [], []
    event_path = output_dir / "ledger.jsonl"
    with event_path.open("w") as log:
        for budget, workers, queue_mode, feedback, density_mode in itertools.product(
                config["budgets"], config["workers"], config["queue_modes"],
                config["feedback_modes"], config["density_modes"]):
            reservation = float(config["reservation"])
            L, U, fixed = tune_warmup(warmup, budget, reservation, density_mode, workers, queue_mode, config)
            for name in config["policies"]:
                if name not in POLICIES:
                    raise ValueError("Unknown policy")
                history = list(warmup)
                previous_delta = min(1, workers * reservation / budget)
                for block_id in range(config["warmup_blocks"], len(blocks)):
                    day = blocks[block_id]
                    model = Predictor(reservation, config["seed"]).fit(history)
                    p, c = model.predict(day)
                    design_delta = min(1, workers * reservation / budget) if name == "lag_structural" else previous_delta
                    kind = {"hard_cap": "cap", "lag_structural": "lag", "lag_previous_day": "lag",
                            "fixed_warmup": "fixed", "banded_warmup": "band"}.get(name, "zcl")
                    signal = "settled" if name in {"zcl_settled", "lag_structural", "lag_previous_day"} else (
                        "expected" if name == "zcl_expected_inflight" else "committed")
                    phi = Threshold(L, U, kind, delta=design_delta, forecast=fixed, band=config["band_width"])
                    policy = Policy(phi, signal, density_mode)
                    jobs = jobs_from(day, p, c, reservation, config["duration_mode"],
                                     config["seconds_per_call"], config["fixed_duration"])
                    result = replay(jobs, budget, workers, policy, queue_mode,
                                    deadline=float(config.get("deadline", math.inf)))
                    densities = p / (reservation if density_mode == "reservation" else c)
                    y = [r["resolved"] for r in day]
                    tag = {"submission": day[0]["submission"], "budget": budget, "workers": workers,
                           "queue_mode": queue_mode, "feedback": feedback, "density_mode": density_mode,
                           "policy": name, "block": block_id}
                    training_log.append({**tag, "training_ids": sorted(model.training_ids),
                                         "test_ids": [r["id"] for r in day]})
                    final_threshold = phi(result.peak_commitment)
                    harmful = sum(d > final_threshold + 1e-9 or final_threshold <= L + 1e-9 for d in result.room_densities)
                    episode = {**tag, "resolved": result.value, "resolved_before_deadline": result.value_before_deadline,
                               "spend": result.spend, "utilization": result.spend / budget,
                               "admitted": len(result.admitted), "offered": len(day),
                               "room_rejections": sum(v == "room" for v in result.rejected.values()),
                               "price_rejections": sum(v == "price" for v in result.rejected.values()),
                               "harmful_refusals_predicted_density": harmful,
                               "delta": result.delta, "design_delta": design_delta,
                               "design_delta_exceeded": result.delta > design_delta + 1e-9,
                               "density_outside_training_range": int(np.sum((densities < L) | (densities > U))),
                               "L": L, "U": U, "warmup_fixed_price": fixed,
                               "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
                               "brier": float(brier_score_loss(y, p)),
                               "cost_mae": float(np.mean(abs(c - np.array([r["actual_cost"] for r in day])))),
                               "oracle_resolved_relaxation": resolved_count_oracle([r["actual_cost"] for r in day], y, budget),
                               "makespan_modeled": result.makespan,
                               "mean_admission_wait": result.total_wait / max(1, len(result.admitted)),
                               "competitive_guarantee_for_realized_outcomes": False}
                    episodes.append(episode)
                    for event in result.events:
                        log.write(json.dumps({**tag, **event}, sort_keys=True) + "\n")
                    previous_delta = result.delta
                    admitted = set(result.admitted)
                    if feedback == "admitted_only":
                        history.extend(r for r in day if r["id"] in admitted)
                    elif feedback == "full_archive":
                        history.extend(day)
                    elif feedback != "frozen_warmup":
                        raise ValueError("Unknown feedback mode")
    (output_dir / "episodes.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in episodes))
    (output_dir / "training_provenance.json").write_text(json.dumps(training_log))
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in episodes:
        key = tuple(row[k] for k in ("budget", "workers", "queue_mode", "feedback", "density_mode"))
        groups[key].append(row)
    comparisons = []
    # Pre-specified comparator, not the worst baseline chosen after results.
    for key, group in groups.items():
        baseline = {r["block"]: r for r in group if r["policy"] == "zcl_settled"}
        for name in config["policies"]:
            if name == "zcl_settled":
                continue
            selected = sorted((r for r in group if r["policy"] == name), key=lambda r: r["block"])
            diffs = [r["resolved"] - baseline[r["block"]]["resolved"] for r in selected]
            comparisons.append({"scenario": dict(zip(("budget", "workers", "queue_mode", "feedback", "density_mode"), key)),
                                "policy": name, "baseline": "zcl_settled",
                                **paired_block_interval(diffs, config["seed"], config["bootstrap_block_length"], config["bootstrap_resamples"])})
    summary = {"data_kind": "real_swebench_trace", "submission": rows[0]["submission"],
               "data_sha256": sha256(data_path), "config_sha256": config_hash,
               "retained_rows": len(rows), "warmup_rows": len(warmup), "episodes": len(episodes),
               "incomplete_archive_acknowledged": allow_incomplete, "ingestion_audit": audit,
               "comparisons": comparisons, "llm_calls_made": 0,
               "limitations": ["One trajectory per issue; no stochastic reruns", "PR creation order is a timing proxy",
                   "Warm-up labels supplied as historical archive; no warm-up budget charged", "Few dependent blocks",
                   "Modeled durations, not measured wall-clock time", "No theorem guarantee for predicted values",
                   "Same public benchmark as manuscript; not an external benchmark holdout",
                   "No pooled-budget, model-switch or LLM-triage experiment in this starter"]}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    text = ["# SWE-bench trace-replay results", "", "This is recorded-trace replay, not fresh SWE-agent execution.",
            f"Data SHA256: `{summary['data_sha256']}`", f"Configuration SHA256: `{config_hash}`", "",
            "## Paired differences versus settled ZCL", "",
            "All pre-specified comparisons are retained, including negative results. Intervals are descriptive, not multiplicity-adjusted.", ""]
    for row in comparisons:
        text.append(f"- {row['scenario']} / {row['policy']}: mean {row['mean_difference']:.3f}; "
                    f"95% block interval [{row['ci95_low']:.3f}, {row['ci95_high']:.3f}].")
    text += ["", "## Limitations", ""] + ["- " + x for x in summary["limitations"]]
    (output_dir / "REPORT.md").write_text("\n".join(text) + "\n")
    return summary

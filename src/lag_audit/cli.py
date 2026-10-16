from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import platform
import sys
from .theory import random_audit, coarse_counterexample, adversary


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent lagged-budget audit; never launches paid agents")
    sub = parser.add_subparsers(dest="command", required=True)
    theory = sub.add_parser("theory")
    theory.add_argument("--instances", type=int, default=3000)
    theory.add_argument("--seed", type=int, default=20261014)
    theory.add_argument("--output", type=Path, default=Path("results/theory"))
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--submission", default="20240620_sweagent_claude3.5sonnet")
    fetch.add_argument("--output", type=Path, default=Path("data/sweagent-sonnet"))
    fetch.add_argument("--github-revision")
    fetch.add_argument("--dataset-revision")
    norm = sub.add_parser("normalize")
    norm.add_argument("--issues", type=Path, required=True)
    norm.add_argument("--trajs", type=Path, required=True)
    norm.add_argument("--results", type=Path, required=True)
    norm.add_argument("--submission", required=True)
    norm.add_argument("--output", type=Path, required=True)
    empirical = sub.add_parser("replay")
    empirical.add_argument("--data", type=Path, required=True)
    empirical.add_argument("--config", type=Path, default=Path("configs/pilot.json"))
    empirical.add_argument("--output", type=Path, default=Path("results/swebench-pilot"))
    empirical.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    if args.command == "fetch":
        from .data import fetch_public
        result = fetch_public(args.output, args.submission, args.github_revision, args.dataset_revision)
    elif args.command == "normalize":
        from .data import normalize
        result = normalize(json.loads(args.issues.read_text()), args.trajs,
                           json.loads(args.results.read_text()), args.submission, args.output)
    elif args.command == "replay":
        from .empirical import run_experiments
        result = run_experiments(args.data, json.loads(args.config.read_text()), args.output, args.allow_incomplete)
        result = {k: v for k, v in result.items() if k not in {"comparisons", "ingestion_audit"}}
    else:
        if args.instances < 1:
            parser.error("--instances must be positive")
        if args.output.exists() and any(args.output.iterdir()):
            parser.error("Output must be a new directory; preserve previous results")
        args.output.mkdir(parents=True, exist_ok=True)
        result = random_audit(args.instances, args.seed)
        result["coarse_counterexample"] = coarse_counterexample()
        result["python"] = platform.python_version()
        import numpy, scipy
        result["numpy"] = numpy.__version__
        result["scipy"] = scipy.__version__
        convergence = [adversary(ratio, lag, units, kind)
                       for ratio in (10, 100, 1000) for lag in (.05, .1, .2, .3)
                       for units in (100, 400, 1600) for kind in ("zcl", "lag")]
        with (args.output / "adversary_convergence.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(convergence[0]))
            writer.writeheader(); writer.writerows(convergence)
        (args.output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False))
        (args.output / "REPORT.md").write_text(
            f"# Local numerical theory audit\n\nSeed: {args.seed}. Random instances: {args.instances}. "
            f"Numerical violations: {result['violations']}.\n\n"
            f"Corrected coarse-item construction ratio: {result['coarse_counterexample']['measured_ratio']:.8f}.\n\n"
            "Adversarial convergence is in the accompanying CSV. Finite instances include the admitted item's size "
            "in delta; asymptotic targets must not be applied blindly to coarse instances.\n\n"
            "These are finite numerical checks, not formal proof verification. No real SWE-bench replay or Codex execution is implied.\n")
        if result["violations"]:
            print(json.dumps(result, indent=2))
            sys.exit(1)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

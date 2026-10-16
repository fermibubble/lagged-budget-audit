"""Public SWE-bench data ingestion. Downloaded code/patches are NEVER executed.

The S3 adapter is for the older SWE-agent submissions used in the manuscript.
It is fail-closed for unknown schemas, ambiguous outcomes, and duplicate traces.
Network integration has NOT been exercised in the packaged local test run.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlparse
import requests
import yaml

DATASET = "princeton-nlp/SWE-bench_Verified"
DEFAULT_SUBMISSION = "20240620_sweagent_claude3.5sonnet"


def parse_suffix_info(payload: bytes) -> dict:
    """Parse a complete root-level info object from a pretty-printed JSON suffix.

    Structural boundary plus JSON decoding avoids searching arbitrary strings for
    numeric costs. Only the newer archive's verified root suffix layout is accepted.
    """
    matches = list(re.finditer(rb'(?m)^  "info": ', payload))
    if len(matches) != 1:
        raise ValueError('Suffix lacks a unique complete root info boundary')
    suffix = json.loads(b'{' + payload[matches[0].start():])
    if set(suffix) != {'info', 'replay_config', 'environment'}:
        raise ValueError('Unknown root suffix schema')
    info = suffix['info']
    parse_trajectory({'info': info})
    return {key: info[key] for key in ('model_stats', 'exit_status', 'swe_agent_hash', 'swe_agent_version') if key in info}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_destination(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if p.is_absolute() or ".." in p.parts or "\\" in relative:
        raise ValueError("Unsafe object path")
    dest = (root / str(p)).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError("Path escapes cache")
    return dest


def parse_trajectory(obj: dict) -> dict:
    """Explicit SWE-agent cost schema; NEVER use cumulative total_cost as instance cost."""
    stats = obj.get("info", {}).get("model_stats", {})
    if "instance_cost" not in stats:
        raise ValueError("Missing info.model_stats.instance_cost; adapter review required")
    cost = stats["instance_cost"]
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        raise ValueError("Invalid per-instance cost")
    calls = stats.get("api_calls", stats.get("instance_api_calls"))
    if calls is not None and (isinstance(calls, bool) or not isinstance(calls, int) or calls < 0):
        raise ValueError("Invalid API-call count")
    return {"actual_cost": float(cost), "api_calls": calls,
            "exit_status": obj.get("info", {}).get("exit_status"),
            "cost_field": "info.model_stats.instance_cost"}


def normalize(dataset_rows: list[dict], trajectory_dir: Path, results: dict,
              submission: str, output: Path) -> dict:
    if not isinstance(results.get("resolved"), list):
        raise ValueError("Official results must contain resolved instance IDs")
    by_id = {r["instance_id"]: r for r in dataset_rows}
    if len(by_id) != len(dataset_rows):
        raise ValueError("Duplicate benchmark instance IDs")
    resolved = set(results["resolved"])
    if not resolved <= set(by_id):
        raise ValueError("Official results have IDs outside the chosen benchmark split")
    unknown_outcomes = set(results.get("no_logs", []))
    paths: dict[str, Path] = {}
    extras, exclusions = [], []
    for path in sorted(trajectory_dir.rglob("*")):
        if not path.is_file() or path.suffix not in {".traj", ".json"}:
            continue
        # Match complete instance name or the conventional instance/trajectory.json form.
        candidates = [x for x in (path.stem, path.parent.name) if x in by_id]
        if not candidates:
            extras.append(str(path.relative_to(trajectory_dir)))
            continue
        instance = candidates[0]
        if instance in paths:
            raise ValueError(f"Duplicate trajectories for {instance}: multiple attempts require an explicit protocol")
        paths[instance] = path
    normalized = []
    for instance, row in sorted(by_id.items()):
        if instance not in paths:
            exclusions.append({"instance_id": instance, "reason": "missing_trajectory"})
            continue
        if instance in unknown_outcomes and instance not in resolved:
            exclusions.append({"instance_id": instance, "reason": "official_no_logs_unknown_outcome"})
            continue
        try:
            info = parse_trajectory(json.loads(paths[instance].read_text()))
            if not row.get("created_at") or not isinstance(row.get("problem_statement"), str):
                raise ValueError("Missing date or problem statement")
        except (ValueError, KeyError, TypeError) as exc:
            exclusions.append({"instance_id": instance, "reason": str(exc)})
            continue
        normalized.append({"id": submission + ":" + instance, "instance_id": instance,
                           "submission": submission, "repo": row["repo"],
                           "problem_statement": row["problem_statement"],
                           "created_at": row["created_at"], "resolved": int(instance in resolved),
                           "trajectory_sha256": sha256(paths[instance]), **info})
    # No difficulty, reference patch, test patch, hints or other agents' outcomes are exported.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in normalized))
    audit = {"submission": submission, "benchmark_rows": len(by_id), "retained": len(normalized),
             "official_resolved": len(resolved), "retained_resolved": sum(r["resolved"] for r in normalized),
             "exclusions": exclusions, "unrecognized_files": extras,
             "complete": not exclusions, "normalized_sha256": sha256(output),
             "label_policy": "no_logs excluded as unknown unless explicitly listed resolved; no_generation counts unresolved"}
    output.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2))
    return audit


def fetch_public(output_dir: Path, submission: str = DEFAULT_SUBMISSION,
                 github_revision: str | None = None, dataset_revision: str | None = None,
                 max_bytes: int = 1_000_000_000) -> dict:
    """Download official public metadata, per-instance costs/outcomes and benchmark text.

    GitHub/HF revisions are resolved ONCE and recorded; S3 objects are content-hashed.
    Public unsigned requests only. Existing output directories are not overwritten.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", submission):
        raise ValueError("Invalid submission name")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Use a new output directory; preserve previous data locks")
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    from datasets import load_dataset
    from huggingface_hub import HfApi
    session = requests.Session()
    session.headers["User-Agent"] = "lagged-budget-independent-audit/0.1"
    def get(url: str) -> requests.Response:
        response = session.get(url, timeout=90)
        response.raise_for_status()
        return response
    github_revision = github_revision or get("https://api.github.com/repos/SWE-bench/experiments/commits/main").json()["sha"]
    dataset_revision = dataset_revision or HfApi().dataset_info(DATASET).sha
    if not re.fullmatch(r"[0-9a-f]{40}", github_revision or "") or not re.fullmatch(r"[0-9a-f]{40}", dataset_revision or ""):
        raise ValueError("Supply immutable 40-character GitHub and Hugging Face revisions")
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/SWE-bench/experiments/{github_revision}/evaluation/verified/{submission}"
    metadata_bytes = get(base + "/metadata.yaml").content
    results_bytes = get(base + "/results/results.json").content
    (output_dir / "metadata.yaml").write_bytes(metadata_bytes)
    (output_dir / "official_results.json").write_bytes(results_bytes)
    metadata = yaml.safe_load(metadata_bytes)
    uri = metadata.get("assets", {}).get("trajs", "")
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or parsed.netloc != "swe-bench-submissions":
        raise ValueError("This adapter supports the verified SWE-agent public S3 archive only; review a new adapter for other assets")
    prefix = parsed.path.lstrip("/").rstrip("/") + "/"
    s3 = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED, retries={"max_attempts": 4}))
    objects = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=parsed.netloc, Prefix=prefix):
        objects.extend(o for o in page.get("Contents", []) if o["Key"].endswith((".traj", ".json")))
    if not objects:
        raise ValueError("No trajectory objects returned: do not fabricate costs")
    if sum(o["Size"] for o in objects) > max_bytes:
        raise ValueError("Public download exceeds the explicit byte limit")
    files = []
    for obj in sorted(objects, key=lambda o: o["Key"]):
        relative = obj["Key"][len(prefix):]
        dest = safe_destination(output_dir / "trajs", relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(parsed.netloc, obj["Key"], str(dest))
        files.append({"source": f"s3://{parsed.netloc}/{obj['Key']}", "path": str(dest.relative_to(output_dir)),
                      "sha256": sha256(dest), "etag": obj.get("ETag"), "bytes": dest.stat().st_size})
    dataset = load_dataset(DATASET, split="test", revision=dataset_revision)
    dataset_rows = list(dataset)
    # Persist sanitized metadata for offline normalization; never commit patches.
    sanitized = [{k: r[k] for k in ("instance_id", "repo", "problem_statement", "created_at")} for r in dataset_rows]
    (output_dir / "issues.json").write_text(json.dumps(sanitized))
    audit = normalize(sanitized, output_dir / "trajs", json.loads(results_bytes), submission,
                      output_dir / "normalized.jsonl")
    lock = {"github_revision": github_revision, "dataset": DATASET, "dataset_revision": dataset_revision,
            "submission": submission, "metadata_url": base + "/metadata.yaml", "files": files,
            "metadata_sha256": sha256(output_dir / "metadata.yaml"),
            "official_results_sha256": sha256(output_dir / "official_results.json"),
            "issues_sha256": sha256(output_dir / "issues.json"), "audit": audit}
    (output_dir / "sources.lock.json").write_text(json.dumps(lock, indent=2))
    return audit

"""Paired, circular moving-block intervals; not independent rotation pseudo-replication."""
from __future__ import annotations
import numpy as np


def paired_block_interval(differences: list[float], seed: int = 20261014,
                          block_length: int = 2, resamples: int = 5000) -> dict:
    x = np.asarray(differences, dtype=float)
    if len(x) < 2 or block_length < 1 or resamples < 100 or not np.all(np.isfinite(x)):
        raise ValueError("Invalid paired bootstrap input")
    rng = np.random.default_rng(seed)
    size = min(block_length, len(x))
    samples = []
    for _ in range(resamples):
        starts = rng.integers(0, len(x), size=int(np.ceil(len(x) / size)))
        indices = np.concatenate([(start + np.arange(size)) % len(x) for start in starts])[:len(x)]
        samples.append(float(x[indices].mean()))
    low, high = np.quantile(samples, [.025, .975])
    return {"mean_difference": float(x.mean()), "ci95_low": float(low), "ci95_high": float(high),
            "paired_blocks": len(x), "bootstrap_block_length": size, "bootstrap_seed": seed,
            "resamples": resamples,
            "interpretation": "Descriptive conditional interval on this trace sequence; few blocks and shared training limit inference."}

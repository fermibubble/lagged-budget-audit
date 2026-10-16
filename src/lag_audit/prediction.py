"""Strict feature allowlist shared by BOTH success and cost predictors."""
from __future__ import annotations
import math
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression, Ridge


def features(row: dict) -> dict:
    # IDs and timestamps are used for partitioning/provenance, not predictive features.
    return {"repo": str(row["repo"]), "log_issue_length": math.log1p(len(row["problem_statement"]))}


class Predictor:
    def __init__(self, reservation: float, seed: int = 20261014):
        self.reservation = reservation
        self.seed = seed
        self.vectorizer = DictVectorizer(sparse=True)
        self.success = None
        self.cost = Ridge(alpha=10.0, solver="lsqr")
        self.constant = .5
        self.training_ids: set[str] = set()

    def fit(self, history: list[dict]) -> "Predictor":
        if not history:
            raise ValueError("Predictor needs an explicit warm-up set")
        self.training_ids = {r["id"] for r in history}
        if len(self.training_ids) != len(history):
            raise ValueError("Duplicate training jobs")
        X = self.vectorizer.fit_transform([features(r) for r in history])
        y = np.array([r["resolved"] for r in history], dtype=int)
        costs = np.array([r["actual_cost"] for r in history], dtype=float)
        if not set(y.tolist()) <= {0, 1} or np.any(costs < 0):
            raise ValueError("Invalid observed label/cost")
        self.constant = float((y.sum() + 1) / (len(y) + 2))
        self.success = None
        if len(set(y.tolist())) == 2:
            self.success = LogisticRegression(C=1.0, max_iter=2000, random_state=self.seed).fit(X, y)
        self.cost.fit(X, costs)
        # Lower bound fitted on observed training costs only; zero-cost failures are valid.
        self.cost_floor = max(1e-6, float(np.quantile(costs, .05)))
        return self

    def predict(self, offered: list[dict], check_disjoint: bool = True) -> tuple[np.ndarray, np.ndarray]:
        if check_disjoint and any(r["id"] in self.training_ids for r in offered):
            raise ValueError("Training/test job overlap")
        X = self.vectorizer.transform([features(r) for r in offered])
        p = np.full(len(offered), self.constant) if self.success is None else self.success.predict_proba(X)[:, 1]
        c = np.clip(self.cost.predict(X), self.cost_floor, self.reservation)
        return np.clip(p, .001, .999), c
